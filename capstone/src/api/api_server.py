"""FastAPI backend server for production deployment."""
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv
import json
import uuid
from datetime import datetime

# Import production modules
from src.agents.claude_llm import ClaudeLLMClient
from src.common.file_processor import FileProcessor
from src.common.audit_logger import AuditLogger, AuditAction
from src.orchestrator.approval_workflow import ApprovalWorkflow
from src.common.report_generator import ReportGenerator
from src.common.guardrails import Guardrails
from src.common.metrics import evaluate_answer

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="ProposalForge Pro API",
    description="Production-grade document analysis API powered by Claude",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter (sliding window; built via Kiro SDD — .kiro/specs/rate-limiter/)
from src.api.rate_limiter import install_rate_limiter
install_rate_limiter(app)

# Initialize services
from src.agents.llm_backend import get_llm_client
claude, LLM_BACKEND = get_llm_client()
audit_logger = AuditLogger()
approval_workflow = ApprovalWorkflow()
report_generator = ReportGenerator()
guardrails = Guardrails()

# Request/Response models
class DocumentUploadRequest(BaseModel):
    filename: str
    content: str


class AnalysisRequest(BaseModel):
    document_id: str
    content: str


class QueryRequest(BaseModel):
    document_id: str
    query: str
    context: str


class PipelineRequest(BaseModel):
    query: str
    context: str
    document_id: Optional[str] = None


class ApprovalRequestModel(BaseModel):
    request_id: str
    approved_by: str
    comments: Optional[str] = ""


class ReportGenerationRequest(BaseModel):
    document_id: str
    filename: str
    format: str = "pdf"  # pdf, docx, json


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "ProposalForge Pro API"
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics exposition (scraped by Prometheus/Grafana)."""
    from fastapi import Response
    from src.common.observability import metrics_payload
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.post("/api/v1/pipeline/run")
async def pipeline_run(request: PipelineRequest, user_id: str = "api_user"):
    """Run the multi-agent analysis pipeline over provided context (synchronous)."""
    from src.orchestrator.pipeline import run_pipeline
    from src.retrieval.retriever import get_retriever
    retriever = get_retriever()
    retriever.build(request.context, "api-doc", "api-document")
    documents = [{"filename": "api-document", "content": request.context,
                  "metadata": {"extension": ".txt"}, "document_id": "api-doc"}]
    result = run_pipeline(documents, request.query, retriever=retriever, llm=claude)
    return {"success": True, "result": result}


class RetrieveRequest(BaseModel):
    query: str
    context: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None  # [{filename, content}]
    top_k: int = 4


@app.get("/api/v1/status")
async def system_status_endpoint():
    """Live backend wiring (LLM connector, vector DB, tracing, Azure Monitor)."""
    from src.common.diagnostics import system_status
    return system_status()


class BidScoreRequest(BaseModel):
    # Provide explicit criterion scores (0-100), or opportunity text, or both.
    scores: Optional[dict] = None
    text: Optional[str] = None
    weights: Optional[dict] = None


@app.post("/api/v1/bid/score")
async def bid_score(request: BidScoreRequest):
    """Bid / No-Bid recommendation (see .kiro/specs/bid-no-bid/)."""
    from src.agents.bid_scoring import score_bid, analyze_opportunity
    scores = request.scores
    signals, domain, hint = [], "General", ""
    if not scores and request.text:
        a = analyze_opportunity(request.text, llm=claude)
        scores = a["suggested_scores"]
        signals, domain, hint = a["signals"], a["detected_domain"], a["rationale_hint"]
    result = score_bid(scores or {}, request.weights)
    result.signals = signals
    result.detected_domain = domain
    payload = result.to_dict()
    if hint:
        payload["analysis_hint"] = hint
    return payload


class ComplianceRequest(BaseModel):
    rfp_text: str
    response_text: str = ""


@app.post("/api/v1/compliance/matrix")
async def compliance_matrix(request: ComplianceRequest):
    """Requirements traceability matrix (see .kiro/specs/compliance-matrix/)."""
    from src.agents.compliance_matrix import build_matrix
    result = build_matrix(request.rfp_text, request.response_text, llm=claude)
    return result.to_dict()


@app.post("/api/v1/retrieve")
async def retrieve_only(request: RetrieveRequest):
    """Retrieval only — NO LLM call. Fast path used to measure retrieval latency
    (target < 50ms with a local vector backend) and to power multi-doc search."""
    from src.retrieval.retriever import get_retriever
    retriever = get_retriever()
    docs = request.documents or ([{"filename": "api-document", "content": request.context}]
                                 if request.context else [])
    if not docs:
        raise HTTPException(status_code=400, detail="Provide 'context' or 'documents'.")
    for i, d in enumerate(docs):
        retriever.build(d.get("content", ""), d.get("document_id", f"doc-{i}"),
                        d.get("filename", f"doc-{i}"))
    hits = retriever.search(request.query, top_k=request.top_k)
    return {"success": True, "backend": getattr(retriever, "backend", "unknown"),
            "count": len(hits), "hits": hits}


class MultiDocRequest(BaseModel):
    query: str
    documents: List[Dict[str, Any]]   # [{filename, content, document_id?}]


@app.post("/api/v1/analyze/multi")
async def analyze_multi(request: MultiDocRequest, user_id: str = "api_user"):
    """Multi-document analysis using the configured LLM connector.

    Builds one retriever across all supplied documents (namespace-isolated per
    doc), runs the multi-agent pipeline over the combined corpus, and returns a
    grounded, cross-document answer with per-source citations."""
    from src.orchestrator.pipeline import run_pipeline
    from src.retrieval.retriever import get_retriever
    if not request.documents:
        raise HTTPException(status_code=400, detail="Provide at least one document.")
    retriever = get_retriever()
    documents = []
    for i, d in enumerate(request.documents):
        did = d.get("document_id", f"doc-{i}")
        content = d.get("content", "")
        fname = d.get("filename", f"document-{i}")
        retriever.build(content, did, fname)
        documents.append({"filename": fname, "content": content,
                          "metadata": {"extension": Path(fname).suffix or ".txt"},
                          "document_id": did})
    result = run_pipeline(documents, request.query, retriever=retriever, llm=claude)
    try:
        audit_logger.log(AuditAction.DOCUMENT_ANALYSIS, user_id, "api-session",
                         document_id=f"multi:{len(documents)}",
                         details={"documents": len(documents), "backend": LLM_BACKEND})
    except Exception:
        pass
    return {"success": True, "backend": LLM_BACKEND,
            "document_count": len(documents), "result": result}


def _run_pipeline_job(job_id: str, task: str, context: str):
    """Background worker: run the pipeline and persist the result to the job store."""
    from src.orchestrator.pipeline import run_pipeline
    from src.retrieval.retriever import get_retriever
    from src.orchestrator.job_store import JobStore
    store = JobStore()
    try:
        store.set_status(job_id, "running")
        retriever = get_retriever()
        retriever.build(context, job_id, "webhook-document")
        documents = [{"filename": "webhook-document", "content": context,
                      "metadata": {"extension": ".txt"}, "document_id": job_id}]
        result = run_pipeline(documents, task, retriever=retriever, llm=claude)
        store.set_result(job_id, result, status="done")
        try:
            from src.common.notifications import notify_pipeline_complete
            notify_pipeline_complete(result)
        except Exception as e:
            print(f"notify failed: {e}")
    except Exception as e:
        store.set_result(job_id, {"error": str(e)}, status="error")
        try:
            from src.common.notifications import get_notifier
            get_notifier().notify("pipeline_error", "Pipeline failed",
                                  f"Job {job_id} errored: {e}", {"job_id": job_id})
        except Exception:
            pass


@app.post("/api/v1/pipeline/submit")
async def pipeline_submit(request: PipelineRequest, background_tasks: BackgroundTasks,
                          user_id: str = "api_user"):
    """Webhook: accept a task, run the pipeline in the background, return instantly.

    The dashboard polls /api/v1/pipeline/jobs (or the shared job store) and shows
    the finished investigation automatically.
    """
    from src.orchestrator.job_store import JobStore
    from src.common import servicebus
    store = JobStore()
    job_id = store.submit(request.query, request.context)
    if servicebus.is_enabled() and servicebus.enqueue_job(job_id, request.query, request.context):
        # A separate worker (worker.py) will process it from the queue.
        return {"status": "accepted", "job_id": job_id, "dispatch": "servicebus"}
    background_tasks.add_task(_run_pipeline_job, job_id, request.query, request.context)
    return {"status": "accepted", "job_id": job_id, "dispatch": "background"}


@app.get("/api/v1/pipeline/jobs")
async def pipeline_jobs(limit: int = 25):
    """List recent pipeline jobs (status + summary)."""
    from src.orchestrator.job_store import JobStore
    jobs = JobStore().list(limit=limit)
    return {"success": True, "jobs": [{k: v for k, v in j.items() if k != "result"}
                                      for j in jobs]}


@app.get("/api/v1/pipeline/jobs/{job_id}")
async def pipeline_job(job_id: str):
    """Fetch one job including its full result."""
    from src.orchestrator.job_store import JobStore
    job = JobStore().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"success": True, "job": job}


# Document Analysis Endpoints
@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...), user_id: str = "api_user"):
    """Upload and process document."""
    try:
        # Validate file type
        if not FileProcessor.is_supported(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Save file
        temp_path = f"temp/{file.filename}"
        Path(temp_path).parent.mkdir(exist_ok=True)
        
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Extract text
        document_content = FileProcessor.extract_text(temp_path)
        file_metadata = FileProcessor.get_file_metadata(temp_path)
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Log upload
        audit_logger.log(
            AuditAction.DOCUMENT_UPLOAD,
            user_id,
            document_id,
            document_id,
            {
                "filename": file.filename,
                "size": file_metadata["size_bytes"],
                "file_type": file_metadata["extension"]
            }
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "size": file_metadata["size_mb"],
            "content_length": len(document_content),
            "uploaded_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/documents/{document_id}/analyze")
async def analyze_document(document_id: str, request: AnalysisRequest, user_id: str = "api_user"):
    """Analyze document with Claude."""
    try:
        # Analyze
        analysis = claude.analyze_document(request.content)
        
        # Log analysis
        audit_logger.log(
            AuditAction.DOCUMENT_ANALYSIS,
            user_id,
            document_id,
            document_id,
            {
                "analysis_type": "full",
                "confidence": analysis.get("confidence", 0)
            },
            confidence_score=analysis.get("confidence", 0)
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "analysis": analysis,
            "analyzed_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/documents/{document_id}/query")
async def query_document(document_id: str, request: QueryRequest, user_id: str = "api_user"):
    """Answer question about document."""
    try:
        # Answer query
        response = claude.answer_question(request.context, request.query)
        answer = response.get("answer", "")
        confidence = response.get("confidence", 0.0)
        mode = response.get("mode", "claude")

        # Evaluation metrics (accuracy = mean of confidence/groundedness/usefulness)
        metrics = evaluate_answer(answer, request.context, confidence)

        # Run guardrails
        guardrail_results = guardrails.run_all_checks(
            answer,
            query=request.query,
            confidence=confidence,
            domain="general"
        )
        
        triggered = [r for r in guardrail_results if r.triggered]
        
        # Log query with full evaluation metrics
        audit_logger.log(
            AuditAction.USER_QUERY,
            user_id,
            document_id,
            document_id,
            {
                "query": request.query,
                "confidence": metrics["confidence"],
                "groundedness": metrics["groundedness"],
                "groundness": metrics["groundedness"],
                "usefulness": metrics["usefulness"],
                "accuracy_score": metrics["accuracy_score"],
                "mode": mode,
                "guardrails_triggered": len(triggered)
            },
            confidence_score=metrics["confidence"]
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "query": request.query,
            "answer": answer,
            "mode": mode,
            "evaluation": metrics,
            "guardrails": [
                {
                    "type": r.guardrail_type.value,
                    "triggered": r.triggered,
                    "message": r.message,
                    "severity": r.severity
                }
                for r in guardrail_results
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/documents/{document_id}/suggestions")
async def get_suggestions(document_id: str, request: QueryRequest, user_id: str = "api_user"):
    """Autosuggestion route: relevant follow-up questions for a document."""
    try:
        suggestions = claude.get_auto_suggestions(request.context, request.query)
        return {
            "success": True,
            "document_id": document_id,
            "suggestions": suggestions,
            "count": len(suggestions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Approval Endpoints
@app.post("/api/v1/approvals/create")
async def create_approval(
    document_id: str,
    analysis: Dict[str, Any],
    user_id: str = "api_user"
):
    """Create approval request."""
    try:
        request_id = approval_workflow.create_request(document_id, user_id, analysis)
        
        audit_logger.log(
            AuditAction.APPROVAL_REQUESTED,
            user_id,
            document_id,
            document_id,
            {"request_id": request_id}
        )
        
        return {
            "success": True,
            "request_id": request_id,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/approvals/{request_id}/approve")
async def approve_request(request_id: str, request: ApprovalRequestModel, user_id: str = "api_user"):
    """Approve analysis request."""
    try:
        success = approval_workflow.approve_request(
            request_id,
            request.approved_by,
            request.comments
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Request not found")
        
        audit_logger.log(
            AuditAction.APPROVAL_GRANTED,
            user_id,
            request_id,
            request_id,
            {"approved_by": request.approved_by}
        )
        
        return {
            "success": True,
            "request_id": request_id,
            "status": "approved",
            "approved_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/approvals/{request_id}/reject")
async def reject_request(request_id: str, request: ApprovalRequestModel, user_id: str = "api_user"):
    """Reject analysis request."""
    try:
        success = approval_workflow.reject_request(
            request_id,
            request.approved_by,
            request.comments
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return {
            "success": True,
            "request_id": request_id,
            "status": "rejected",
            "rejected_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Report Generation Endpoints
@app.post("/api/v1/reports/generate")
async def generate_report(
    request: ReportGenerationRequest,
    analysis: Dict[str, Any],
    conversation_history: List[Dict] = None,
    user_id: str = "api_user"
):
    """Generate report in specified format."""
    try:
        conversation_history = conversation_history or []
        
        report_path = report_generator.generate_analysis_report(
            request.document_id,
            request.filename,
            analysis,
            conversation_history,
            format=request.format
        )
        
        audit_logger.log(
            AuditAction.REPORT_GENERATED,
            user_id,
            request.document_id,
            request.document_id,
            {
                "format": request.format,
                "report_path": report_path
            }
        )
        
        return {
            "success": True,
            "document_id": request.document_id,
            "format": request.format,
            "report_path": report_path,
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Audit Endpoints
@app.get("/api/v1/audit/logs")
async def get_audit_logs(
    user_id: str = None,
    action: str = None,
    limit: int = 100
):
    """Get audit logs."""
    try:
        logs = audit_logger.get_logs(user_id=user_id, action=action, limit=limit)
        return {
            "success": True,
            "count": len(logs),
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/audit/stats")
async def get_user_stats(user_id: str):
    """Get user statistics."""
    try:
        stats = audit_logger.get_user_stats(user_id)
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/summary")
async def get_analytics_summary(user_id: str = None):
    """Get analytics summary and accuracy score."""
    try:
        analytics = audit_logger.get_analytics_summary(user_id)
        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/accuracy")
async def get_accuracy_score(user_id: str = None):
    """Get accuracy score route (composite of confidence/groundedness/usefulness)."""
    try:
        analytics = audit_logger.get_analytics_summary(user_id)
        return {
            "success": True,
            "accuracy_score": analytics.get("accuracy_score", 0),
            "details": analytics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/evaluation")
async def get_evaluation_metrics(user_id: str = None):
    """Get detailed evaluation metrics: avg confidence, groundedness,
    usefulness, composite accuracy, and a per-query breakdown."""
    try:
        evaluation = audit_logger.get_evaluation_metrics(user_id)
        return {
            "success": True,
            "evaluation": evaluation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Error handling
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail, "status_code": exc.status_code},
    )


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8001))
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "production") != "production"
    )
