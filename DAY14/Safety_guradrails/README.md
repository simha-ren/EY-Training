# CreditLens Production Pipeline with Safety Guardrails

**FinanceGuard AI** — Deploying a hardened production pipeline for credit policy assistant with full safety stack compliance

## 🎯 Project Overview

Following FinanceGuard's bias audit (Lab 1), the board has approved a production-grade pipeline for **CreditLens**, an AI-powered credit policy assistant. This project builds and benchmarks a complete safety stack that processes natural language queries from loan officers while maintaining compliance with RBI guidelines and data privacy regulations.

**Key Objective**: Deploy before Q4 regulatory deadline with full auditability and safety guarantees.

---

## 📋 Core Requirements

The production pipeline must:

- ✅ **Accept** natural language queries from loan officers
- ✅ **Pre-process** with PII redaction and intent moderation guardrails
- ✅ **Retrieve** relevant context from RAG knowledge base (RBI guidelines, loan policy docs)
- ✅ **Generate** compliant responses via LLM (GPT-4o or mock)
- ✅ **Filter** output for toxicity, hallucination risk, and PII leaks
- ✅ **Log** latency, cost, safety triggers, and audit events
- ✅ **Audit** all decisions in DPDP-compliant format

---

## 🏗️ Architecture Overview

```
Loan Officer Query
       ↓
   [PII Redaction] ← spaCy NER + regex
       ↓
   [Input Guardrails] ← intent moderation, jailbreak detection
       ├─ PASS → Continue
       └─ FAIL → Redirect + Log
       ↓
   [RAG Retrieval] ← FAISS/LlamaIndex search
       ↓
   [LLM Generation] ← GPT-4o or mock LLM
       ↓
   [Output Guardrails] ← PII leak, guarantee checks
       ├─ PASS → Continue
       └─ FAIL → Reject + Log
       ↓
   [Safety Classifier] ← Llama Guard style (toxicity, bias, hallucination)
       ↓
   [Final Response] ← Safe, compliant output
       ↓
   [Audit Log] ← DPDP-compliant event store
```

### Component Breakdown

| Component | Purpose | Implementation |
|-----------|---------|-----------------|
| **PII Redaction** | Remove sensitive data (phone, email, SSN, account numbers) | spaCy NER + regex patterns |
| **Input Guardrails** | Block harmful intents (PII sharing, jailbreaks, off-topic queries) | Rule engine simulation (NeMo-style) |
| **RAG Retrieval** | Fetch relevant policy documents and RBI guidelines | FAISS (LangChain) or VectorStoreIndex (LlamaIndex) |
| **LLM Generation** | Generate contextual responses based on query + retrieved docs | GPT-4o or mock LLM for simulation |
| **Output Guardrails** | Check for PII disclosure and unsafe guarantees in response | Pattern matching + semantic analysis |
| **Safety Classifier** | Evaluate response across harm categories (toxicity, bias, hallucination) | Llama Guard-style classifier |
| **Metrics Logger** | Record latency, token usage, cost, and safety events | Timestamped event store |
| **Audit Log** | DPDP-compliant immutable record of all pipeline events | Structured JSON with user consent tracking |

---

## 🚀 Core Tasks Implementation

### 1. LangChain Pipeline with Guardrails

Build the retrieval-augmented generation pipeline with integrated safety guardrails.

**Key Files:**
- `langchain_pipeline.py` — Core retriever → guardrail → LLM → filter chain

**Components:**
```python
from langchain.chains import RetrievalQA
from langchain.retrievers import FAISS
from langchain.llms import OpenAI

# Initialize RAG chain
retriever = FAISS.from_documents(policy_docs, embeddings)
qa_chain = RetrievalQA.from_chain_type(
    llm=OpenAI(model="gpt-4o", temperature=0.3),
    chain_type="stuff",
    retriever=retriever
)

# Wrap with guardrails (see next section)
```

### 2. NeMo-Style Guardrails Rule Engine

Implement input validation guardrails using a rules engine that checks intent, topic, and safety.

**Rules:**
- ❌ Block: `intent=share_pii` (e.g., "send me customer IDs")
- ❌ Block: `intent=make_decision` (e.g., "approve this loan")
- ❌ Block: `intent=off_topic` (e.g., "tell me a joke")
- ❌ Block: `jailbreak_pattern` (e.g., "ignore your guidelines")
- ✅ Allow: `intent=policy_question` (e.g., "what's the loan term limit?")

**Implementation:**
```python
class InputGuardrails:
    def __init__(self):
        self.rules = {
            'share_pii': r'(customer|applicant|SSN|account|phone)\s+(list|ID|number|data)',
            'make_decision': r'(approve|reject|deny|accept)\s+(this\s+)?(loan|application)',
            'jailbreak': r'(ignore|bypass|forget|override).+(guideline|rule|policy)',
        }
    
    def check(self, query: str) -> Tuple[bool, str]:
        for rule_name, pattern in self.rules.items():
            if re.search(pattern, query, re.IGNORECASE):
                return False, f"Blocked: {rule_name}"
        return True, "Passed"
```

### 3. Output Safety Classifier (Llama Guard Style)

Implement a secondary safety filter that evaluates response quality across multiple dimensions.

**Safety Categories:**
- 🔴 **Toxicity**: Offensive language, harassment
- 🔴 **Hallucination**: Invented facts, contradictions
- 🔴 **Bias**: Discriminatory content
- 🔴 **PII Leak**: Exposure of sensitive data
- 🔴 **Guarantee**: Absolute promises outside policy

**Implementation:**
```python
class SafetyClassifier:
    categories = {
        'toxicity': ['offensive', 'abusive', 'harassing'],
        'hallucination': ['invented', 'contradicts', 'unsupported'],
        'bias': ['discriminatory', 'stereotyping', 'prejudicial'],
        'pii_leak': ['phone', 'email', 'SSN', 'account'],
        'guarantee': ['will', 'guaranteed', 'certainly', 'always'],
    }
    
    def score(self, text: str) -> Dict[str, float]:
        scores = {}
        for category, keywords in self.categories.items():
            match_count = sum(1 for kw in keywords if kw in text.lower())
            scores[category] = match_count / max(len(keywords), 1)
        return scores
    
    def is_safe(self, text: str, threshold: float = 0.3) -> bool:
        scores = self.score(text)
        return all(s < threshold for s in scores.values())
```

### 4. PII Redaction with spaCy NER

Identify and redact personally identifiable information using Named Entity Recognition.

**PII Types:**
- Email addresses (regex: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`)
- Phone numbers (regex: `\d{10}|\d{3}-\d{3}-\d{4}`)
- SSN (regex: `\d{3}-\d{2}-\d{4}`)
- Account numbers (regex: `ACC\d{8}`)
- Person names (spaCy: `PERSON` entity)

**Implementation:**
```python
import spacy
from typing import Tuple

class PIIRedactor:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{10}|\d{3}-\d{3}-\d{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'account': r'\bACC\d{8}\b',
        }
    
    def redact(self, text: str) -> Tuple[str, List[str]]:
        redacted = text
        pii_found = []
        
        # Regex-based redaction
        for pii_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                pii_found.append((pii_type, match.group()))
                redacted = redacted.replace(match.group(), f'[{pii_type.upper()}]')
        
        # NER-based redaction for person names
        doc = self.nlp(redacted)
        for ent in doc.ents:
            if ent.label_ == 'PERSON':
                pii_found.append(('person', ent.text))
                redacted = redacted.replace(ent.text, '[PERSON]')
        
        return redacted, pii_found
```

### 5. Full Pipeline with Metrics Logging

Integrate all components into a unified pipeline with comprehensive logging.

**Key Metrics:**
- ⏱️ **Latency**: Query → response time (ms)
- 💰 **Cost**: Token usage × model pricing
- 🚨 **Safety Triggers**: Count of guardrail blocks
- 📝 **PII Events**: Number of redactions per query
- 🎯 **Retrieval Quality**: Relevance score of fetched docs
- ✅ **Safety Score**: Output classifier confidence

**Implementation:**
```python
import time
import json
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class QueryMetrics:
    query_id: str
    timestamp: str
    query_length: int
    pii_redacted: int
    input_guard_passed: bool
    retrieval_docs: int
    llm_tokens_used: int
    estimated_cost: float
    output_guard_passed: bool
    safety_score: float
    total_latency_ms: float
    response_length: int

class MetricsLogger:
    def __init__(self, log_file: str = "metrics.jsonl"):
        self.log_file = log_file
    
    def log_metrics(self, metrics: QueryMetrics):
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(asdict(metrics)) + '\n')

class ProductionPipeline:
    def __init__(self, model_id="gpt-4o"):
        self.redactor = PIIRedactor()
        self.input_guards = InputGuardrails()
        self.output_guards = OutputGuardrails()
        self.classifier = SafetyClassifier()
        self.retriever = RAGRetriever()
        self.llm = OpenAI(model_id=model_id)
        self.logger = MetricsLogger()
    
    def process_query(self, query: str, user_id: str) -> str:
        start_time = time.time()
        query_id = f"{user_id}_{int(start_time * 1000)}"
        
        # Step 1: PII Redaction
        redacted_query, pii_found = self.redactor.redact(query)
        
        # Step 2: Input Guardrails
        input_passed, input_reason = self.input_guards.check(redacted_query)
        if not input_passed:
            self._log_and_return(
                query_id, query, pii_found, False, 0, 0, 0.0,
                "Input guardrail blocked: " + input_reason, time.time() - start_time
            )
            return f"Query blocked: {input_reason}"
        
        # Step 3: RAG Retrieval
        docs = self.retriever.retrieve(redacted_query)
        context = "\n".join([doc.page_content for doc in docs[:5]])
        
        # Step 4: LLM Generation
        prompt = f"Context: {context}\n\nQuestion: {redacted_query}\n\nAnswer:"
        response = self.llm.predict(prompt)
        
        # Step 5: Output Guardrails
        output_passed, output_reason = self.output_guards.check(response)
        if not output_passed:
            self._log_and_return(
                query_id, query, pii_found, True, len(docs), len(response.split()),
                0.0, "Output guardrail blocked: " + output_reason, time.time() - start_time
            )
            return f"Response blocked: {output_reason}"
        
        # Step 6: Safety Classifier
        safety_scores = self.classifier.score(response)
        is_safe = self.classifier.is_safe(response)
        safety_score = 1.0 - max(safety_scores.values()) if safety_scores else 1.0
        
        # Log metrics
        total_latency = (time.time() - start_time) * 1000
        metrics = QueryMetrics(
            query_id=query_id,
            timestamp=datetime.now().isoformat(),
            query_length=len(query),
            pii_redacted=len(pii_found),
            input_guard_passed=input_passed,
            retrieval_docs=len(docs),
            llm_tokens_used=len(response.split()),
            estimated_cost=0.03 * (len(redacted_query) + len(response)) / 1000,
            output_guard_passed=output_passed,
            safety_score=safety_score,
            total_latency_ms=total_latency,
            response_length=len(response)
        )
        self.logger.log_metrics(metrics)
        
        return response if is_safe else "Response failed safety check. Escalating to human review."
```

---

## 🎓 Extension Tasks

### Ext 1: LlamaIndex for Retrieval Comparison

Benchmark LlamaIndex against LangChain's FAISS retriever for retrieval faithfulness.

```bash
python ext1_llamaindex_comparison.py --model gpt-4o --dataset qa_dataset.json
```

**Metrics to track:**
- Retrieval precision (relevance of top-5 docs)
- Semantic similarity between query and retrieved docs
- Token efficiency vs. LangChain FAISS

### Ext 2: LangGraph Human-in-the-Loop

Implement LangGraph for high-value loans requiring human review.

```bash
python ext2_langraph_hitl.py --threshold 100000
```

**Workflow:**
1. Query → Pipeline processing
2. If loan amount > threshold → Flag for human review
3. Human reviews guardrail decisions
4. Logs human feedback for model retraining

### Ext 3: Cost Benchmarking

Compare cost-per-query: GPT-4o vs. on-premises Llama-3 estimate.

```bash
python ext3_cost_benchmark.py --duration 1h
```

**Output:**
- GPT-4o cost per 1000 queries
- Llama-3 infrastructure cost amortized
- Break-even analysis

### Ext 4: FastAPI Wrapper with Rate Limiting

Deploy the pipeline as a REST API with rate limiting and authentication.

```bash
python -m uvicorn ext4_api:app --host 0.0.0.0 --port 8000
```

**Endpoints:**
- `POST /query` — Submit a query
- `GET /metrics/{query_id}` — Retrieve query metrics
- `GET /health` — Health check
- Rate limit: 10 queries/min per API key

### Ext 5: DPDP-Compliant Audit Log Schema

Design an immutable audit log schema for data privacy compliance.

```bash
python ext5_audit_schema.py --export audit_schema.json
```

**Schema includes:**
- Query content (encrypted)
- User consent timestamp
- Guardrail decisions
- Response (hashed)
- Data retention policy

---

## 📊 Outputs & Results

After running the pipeline, you'll generate:

1. **metrics.jsonl** — Line-delimited JSON of all query metrics
2. **audit_log.json** — DPDP-compliant audit trail
3. **safety_report.csv** — Summary of guardrail triggers
4. **cost_analysis.html** — Interactive cost breakdown

### Sample Metrics Output

```json
{
  "query_id": "user123_1687456000000",
  "timestamp": "2024-06-18T14:00:00Z",
  "query_length": 42,
  "pii_redacted": 1,
  "input_guard_passed": true,
  "retrieval_docs": 5,
  "llm_tokens_used": 150,
  "estimated_cost": 0.0045,
  "output_guard_passed": true,
  "safety_score": 0.95,
  "total_latency_ms": 1250,
  "response_length": 180
}
```

---

## 📦 Installation & Setup

### Prerequisites

- Python 3.9+
- OpenAI API key (or HuggingFace for open-source models)
- spaCy language model
- FAISS library

### Installation

```bash
# Clone or download the project
git clone https://github.com/financeguard/creditlens-pipeline.git
cd creditlens-pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Set up environment variables
echo "OPENAI_API_KEY=sk_test_..." > .env
echo "RBI_DOCS_PATH=./data/rbi_guidelines/" >> .env
```

### requirements.txt

```
langchain==0.1.0
llamaindex==0.9.0
openai==1.3.0
faiss-cpu==1.7.4
spacy==3.7.2
pandas==2.0.0
numpy==1.24.0
python-dotenv==1.0.0
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.0.0
```

---

## 🏢 Production Deployment Checklist

- [ ] Audit all guardrail rule sets (legal + compliance review)
- [ ] Benchmark latency on production hardware (target <2s p95)
- [ ] Set up monitoring for guardrail trigger rates (alert if >5% of queries)
- [ ] Configure encrypted secrets for API keys and model credentials
- [ ] Enable request logging and audit trail (DPDP-compliant)
- [ ] Implement circuit breaker for LLM API failures
- [ ] Set up on-call rotation for safety escalations
- [ ] Deploy canary release to 5% of traffic for 1 week
- [ ] Load test with 100 concurrent queries
- [ ] Train loan officers on system limitations and escalation paths
- [ ] Document guardrail decisions and appeal process
- [ ] Schedule quarterly guardrail rule review with compliance

---

## 📚 Documentation

### Key Files

```
creditlens-pipeline/
├── README.md (you are here)
├── requirements.txt
├── .env.example
├── core/
│   ├── pii_redactor.py
│   ├── input_guardrails.py
│   ├── rag_retriever.py
│   ├── output_guardrails.py
│   └── safety_classifier.py
├── pipeline.py (main ProductionPipeline class)
├── logger.py (MetricsLogger & AuditLog)
├── extensions/
│   ├── ext1_llamaindex_comparison.py
│   ├── ext2_langraph_hitl.py
│   ├── ext3_cost_benchmark.py
│   ├── ext4_api.py
│   └── ext5_audit_schema.py
├── tests/
│   ├── test_pii_redaction.py
│   ├── test_guardrails.py
│   └── test_safety_classifier.py
└── data/
    ├── rbi_guidelines/
    └── sample_queries.jsonl
```


## 🔍 Monitoring & Observability

Monitor these metrics in production:

- **Safety**: Guardrail block rate, safety classifier average score
- **Performance**: P50/P95/P99 latency, QPS (queries per second)
- **Cost**: Tokens per query, estimated monthly LLM cost
- **Compliance**: Audit log completeness, PII redaction success rate

---
