"""Production-grade Streamlit frontend with Claude LLM, file analysis, and approval workflow."""
from __future__ import annotations

import os
import json
import uuid
import base64
import streamlit as st
from pathlib import Path
from datetime import datetime

# Import production modules
from src.agents.claude_llm import ClaudeLLMClient
from src.agents.llm_backend import get_llm_client
from src.common.file_processor import FileProcessor
from src.common.audit_logger import AuditLogger, AuditAction
from src.orchestrator.approval_workflow import ApprovalWorkflow
from src.common.report_generator import ReportGenerator
from src.common.guardrails import Guardrails, redact_pii, check_sensitive_request
from src.common.metrics import compute_groundedness, compute_usefulness, evaluate_answer
from src.retrieval.retriever import get_retriever
from src.common.test_runner import run_test_suite
from src.orchestrator.pipeline import run_pipeline as run_agent_pipeline
from src.orchestrator.job_store import JobStore
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Page config
st.set_page_config(
    page_title="ProposalForge Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    :root {
        --primary-color: #1f6f6b;
        --secondary-color: #2e5cb8;
        --accent-color: #9a7b1f;
        --success-color: #00A36D;
        --danger-color: #DC143C;
        --warning-color: #FF9500;
    }
    
    .main {
        padding: 2rem;
    }
    
    .sidebar .sidebar-content {
        padding: 2rem 1rem;
    }
    
    h1, h2, h3 {
        color: var(--primary-color);
        font-weight: 700;
    }
    
    .stButton > button {
        background-color: var(--primary-color);
        color: white;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #15514e;
        box-shadow: 0 4px 12px rgba(31, 111, 107, 0.4);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        background-color: rgba(255, 255, 255, 0.18);
        color: #102a43;
        border-radius: 14px 14px 0 0;
        border: 1px solid rgba(255, 255, 255, 0.24);
        backdrop-filter: blur(10px);
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.36);
        color: #0b1d33;
    }
    
    .metric-card {
        background: linear-gradient(135deg, var(--primary-color) 0%, #15514e 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .confidence-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    
    .confidence-high {
        background-color: #d4edda;
        color: #155724;
    }
    
    .confidence-medium {
        background-color: #fff3cd;
        color: #856404;
    }
    
    .confidence-low {
        background-color: #f8d7da;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_user"
if "document_data" not in st.session_state:
    st.session_state.document_data = None
if "documents" not in st.session_state:
    st.session_state.documents = []  # multi-document store
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "approval_requested" not in st.session_state:
    st.session_state.approval_requested = False
if "approval_status" not in st.session_state:
    st.session_state.approval_status = None

# Reset is requested by the sidebar (modal or inline confirm) setting this flag.
# We perform the actual clearing here, at the top of the run, so it never depends
# on dialog/callback internals.
if st.session_state.get("_perform_reset"):
    for _k in list(st.session_state.keys()):
        if _k != "user_id":
            del st.session_state[_k]
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.document_data = None
    st.session_state.documents = []
    st.session_state.analysis_result = None
    st.session_state.conversation_history = []
    st.session_state.approval_requested = False
    st.session_state.approval_status = None
    st.session_state.retriever = None
    st.session_state.retriever_backend = "none"
    st.session_state._just_reset = True

# Initialize services
@st.cache_resource
def get_services():
    """Initialize all services."""
    claude, backend = get_llm_client()
    audit = AuditLogger()
    approval = ApprovalWorkflow()
    report_gen = ReportGenerator()
    guardrails = Guardrails()
    return {
        "claude": claude,
        "backend": backend,
        "audit": audit,
        "approval": approval,
        "report": report_gen,
        "guardrails": guardrails
    }


def compute_groundness(answer: str, context: str) -> float:
    # Kept for backwards compatibility; delegates to the shared metric.
    return compute_groundedness(answer, context)


# ===================== AUTHENTICATION / SESSIONIZATION =====================
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() in ("1", "true", "yes")


@st.cache_resource
def get_auth_store():
    from src.common.auth import AuthStore
    return AuthStore()


def _get_login_background_data_url() -> str:
    image_file = Path(__file__).parent / "2903547.jpg"
    if image_file.exists():
        with open(image_file, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/jpeg;base64,{encoded}"
    return "linear-gradient(135deg, #f8fafc 0%, #d6e3f8 100%)"


def _render_login():
    """Login gate. Blocks the app until the user authenticates."""
    bg_url = _get_login_background_data_url()
    st.markdown(
        f"""
        <style>
            .stApp {{
                background-image: url('{bg_url}');
                background-size: cover;
                background-position: center center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}

            .stApp::before {{
                content: "";
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.32);
                pointer-events: none;
                z-index: 0;
            }}

            .main,
            .main .block-container,
            .stApp > main > div {{
                background: transparent !important;
                box-shadow: none !important;
                padding-top: 0 !important;
            }}

            .stTextInput > div > div,
            .stTabs [data-baseweb="tab-list"],
            .stTabs [data-baseweb="tab-panel"],
            .stTabs [data-baseweb="tab"] {{
                background: transparent !important;
                box-shadow: none !important;
                border: none !important;
            }}

            .login-container {{
                #max-width: 560px;
                #margin: 4rem auto 3rem auto;
                #padding: 2rem 2.25rem;
                #border-radius: 24px;
                #background: rgba(255, 255, 255, 0.14);
                #border: 1px solid rgba(255, 255, 255, 0.24);
                #box-shadow: 0 20px 40px rgba(15, 23, 42, 0.14);
                backdrop-filter: blur(16px);
                color: #102a43;
            }}

            .login-container h2,
            .login-container h1,
            .login-container h3 {{
                color: #102a43;
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                letter-spacing: 0.02em;
            }}

            .login-container .stTextInput > div > div,
            .stTextInput > div > div {{
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
            }}

            .login-container .stTextInput > div > div > input,
            .stTextInput > div > div > input,
            .login-container .stTextInput > div > div > textarea {{
                background: rgba(255, 255, 255, 0.96) !important;
                color: #facc15 !important;
                border-radius: 0.75rem !important;
            }}

            .login-container .stTextInput > label,
            .stTextInput > label {{
                color: #facc15 !important;
            }}

            .login-container .stButton > button {{
                background-color: #38bdf8;
                color: #052438;
                font-weight: 700;
                border-radius: 12px;
                padding: 0.8rem 1.5rem;
            }}

            .login-container .stButton > button:hover {{
                background-color: #0ea5e9;
            }}

            .login-container .stCaption,
            .login-container .stMarkdown {{
                color: rgba(248, 250, 252, 0.78);
            }}

            .login-header {{
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                gap: 0.35rem;
                margin-bottom: 1.5rem;
            }}

            .login-title {{
                font-size: 2rem;
                font-weight: 800;
                color: red;
                letter-spacing: 0.04em;
            }}

            .login-subtitle {{
                font-size: 1rem;
                color: red;
                margin: 0;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-header">'
        '<div class="login-title">Proposal Generator Agent</div>'
        '<div class="login-subtitle">Sign in to continue</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    auth = get_auth_store()
    tab_login, tab_register = st.tabs(["Sign in", "Create account"])
    with tab_login:
        u = st.text_input("Username", key="login_user")
        p = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Sign in", type="primary"):
            token = auth.login(u, p)
            if token:
                st.session_state.auth_user = u.strip().lower()
                st.session_state.auth_token = token
                st.session_state.user_id = u.strip().lower()
                st.rerun()
            else:
                st.error("Invalid username or password.")
        st.caption("Demo login: **admin / admin123** — change this in production "
                   "via DEFAULT_ADMIN_PASSWORD or by creating a new account.")
    with tab_register:
        nu = st.text_input("New username", key="reg_user")
        np_ = st.text_input("New password", type="password", key="reg_pwd")
        if st.button("Create account"):
            if len(np_) < 6:
                st.warning("Password must be at least 6 characters.")
            elif auth.create_user(nu, np_):
                st.success("Account created — switch to Sign in.")
            else:
                st.error("That username already exists or is invalid.")
    st.markdown('</div>', unsafe_allow_html=True)


def _current_user():
    """Return the authenticated username, validating the session token."""
    if not REQUIRE_AUTH:
        return st.session_state.get("auth_user", "demo_user")
    token = st.session_state.get("auth_token")
    if token:
        user = get_auth_store().validate_session(token)
        if user:
            return user
    return None


if REQUIRE_AUTH and _current_user() is None:
    _render_login()
    st.stop()
else:
    # Sessionize: ensure user_id + session_id reflect the logged-in user.
    _u = _current_user()
    if _u:
        st.session_state.user_id = _u


def representative_excerpt(text: str, limit: int = 6000) -> str:
    """Build an excerpt that samples across the whole document (not just the
    start), using the retriever's chunker, so analysis reflects long documents."""
    from src.retrieval.retriever import chunk_text
    chunks = chunk_text(text)
    if not chunks:
        return text[:limit]
    excerpt, used = [], 0
    # Always include the first chunk, then sample evenly through the rest.
    order = [0] + list(range(1, len(chunks), max(1, len(chunks) // 8)))
    for i in order:
        if i < len(chunks) and used + len(chunks[i]) <= limit:
            excerpt.append(chunks[i])
            used += len(chunks[i])
    return "\n\n".join(excerpt) or text[:limit]


services = get_services()

# ===== SIDEBAR =====
with st.sidebar:
    st.markdown("# 🚀 ProposalForge Pro")

    # Signed-in user + logout
    if REQUIRE_AUTH and st.session_state.get("auth_user"):
        lc1, lc2 = st.columns([2, 1])
        lc1.caption(f"👤 Signed in as **{st.session_state.auth_user}**")
        if lc2.button("Logout"):
            try:
                get_auth_store().end_session(st.session_state.get("auth_token"))
            except Exception:
                pass
            for k in ("auth_user", "auth_token"):
                st.session_state.pop(k, None)
            st.rerun()
    st.markdown("---")

    st.markdown("## 📊 Dashboard")
    
    # User info
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Session ID", st.session_state.session_id[:8] + "...")
    with col2:
        st.metric("User", st.session_state.user_id)
    
    st.markdown("---")
    
    # Statistics
    st.markdown("## 📈 Statistics")
    user_stats = services["audit"].get_user_stats(st.session_state.user_id)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Documents", user_stats.get("documents_uploaded", 0))
    with col2:
        st.metric("Queries", user_stats.get("total_queries", 0))
    with col3:
        st.metric("Approvals", user_stats.get("approvals_granted", 0))
    with col4:
        st.metric("Alerts", user_stats.get("guardrails_triggered", 0))
    
    st.markdown("---")
    
    # Settings
    st.markdown("## ⚙️ Settings")
    
    llm_model = st.selectbox("LLM Model", ["Claude 3.5 Sonnet", "Claude 3 Opus"], index=0)
    confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.6, 0.05)
    enable_pii_redaction = st.checkbox("Enable PII Redaction", value=True)
    allow_general_knowledge = st.checkbox(
        "Answer beyond the document", value=True,
        help="If the document doesn't cover the question, answer from general "
             "knowledge (clearly labelled) instead of refusing.")

    st.markdown("---")

    # ---- Reset / start fresh (with confirmation modal) ----
    st.markdown("## 🔄 Session")

    if hasattr(st, "dialog"):
        @st.dialog("Start a fresh session?")
        def _confirm_reset():
            st.markdown("You're about to clear this session. This will remove:")
            st.markdown(
                "- 📄 **Uploaded document** and its search index\n"
                "- 💬 **Chat history** and suggestions\n"
                "- 📋 **Analysis results** and any approvals"
            )
            st.caption("Your account and the audit log history are kept.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Yes, start fresh", width='stretch', type="primary"):
                    st.session_state._perform_reset = True
                    st.rerun()
            with c2:
                if st.button("↩️ Cancel", width='stretch'):
                    st.rerun()

        if st.button("🧹 Reset & Start Fresh", width='stretch',
                     help="Clear the document and chat to begin a new session"):
            _confirm_reset()
    else:
        # Fallback for older Streamlit: inline two-step confirm.
        if not st.session_state.get("_confirm_reset"):
            if st.button("🧹 Reset & Start Fresh", width='stretch'):
                st.session_state._confirm_reset = True
                st.rerun()
        else:
            st.warning("Clear document, chat and analysis?")
            c1, c2 = st.columns(2)
            if c1.button("✅ Yes", width='stretch'):
                st.session_state._perform_reset = True
                st.session_state._confirm_reset = False
                st.rerun()
            if c2.button("↩️ Cancel", width='stretch'):
                st.session_state._confirm_reset = False
                st.rerun()
    
    st.markdown("---")
    
    # Help
    st.markdown("## ❓ Help")
    st.info("""
    **ProposalForge Pro** helps you analyze documents with AI-powered insights.
    
    1. Upload a document (PDF, DOCX, CSV, etc.)
    2. Ask questions about the content
    3. Review the analysis
    4. Request approval
    5. Download the report
    """)

# ===== MAIN CONTENT =====
st.markdown("# 🚀 ProposalForge Pro - Intelligent Document Analysis")
st.markdown("### Powered by Claude AI | Production-Ready Analysis & Approval Workflow")

# One-time "fresh start" feedback after a reset.
if st.session_state.pop("_just_reset", False):
    if hasattr(st, "toast"):
        st.toast("✨ Fresh session ready — upload a document to begin.", icon="🧹")
    st.success("✨ **All clear!** Your session has been reset. Upload a new document to start fresh.")
    try:
        st.balloons()
    except Exception:
        pass

# Create tabs
_tabs = st.tabs(["📤 Upload & Analyze", "💬 Chat & Questions", "🤖 Agent Pipeline", "✅ Approval", "📊 Analytics", "🧾 Audit Logs", "📥 Export", "🧪 Tests & Coverage"])
tab1, tab2, tab_pipeline, tab3, tab4, tab5, tab6, tab7 = _tabs

# ===== TAB 1: UPLOAD & ANALYZE =====
with tab1:
    st.markdown("## 📤 Upload Your Documents")
    st.write("Upload one or more documents (PDF, DOCX, CSV, XLSX, PPTX, TXT, MD). "
             "Each is analyzed, and the chat can answer **across all** of them.")

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_files = st.file_uploader(
            "Choose file(s)",
            type=["pdf", "docx", "csv", "xlsx", "pptx", "txt", "md"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
    with col2:
        analyze_button = st.button("🔍 Analyze", width='stretch')

    def _rebuild_index():
        """Rebuild the combined vector index over all uploaded documents."""
        try:
            retriever = get_retriever()
            retriever.build_documents([
                {"id": d["document_id"], "name": d["filename"], "text": d["content"]}
                for d in st.session_state.documents
            ])
            st.session_state.retriever = retriever
            st.session_state.retriever_backend = retriever.backend
            return retriever
        except Exception as e:
            st.session_state.retriever = None
            st.session_state.retriever_backend = "none"
            st.warning(f"Vector index unavailable ({e}); using plain text context.")
            return None

    if uploaded_files and analyze_button:
        existing_names = {d["filename"] for d in st.session_state.documents}
        added = 0
        progress = st.progress(0.0, text="Processing documents...")
        for n, uploaded_file in enumerate(uploaded_files, 1):
            if uploaded_file.name in existing_names:
                continue  # skip duplicates already loaded
            try:
                temp_path = f"temp/{uploaded_file.name}"
                Path(temp_path).parent.mkdir(exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                document_text = FileProcessor.extract_text(temp_path)
                file_metadata = FileProcessor.get_file_metadata(temp_path)
                doc_id = str(uuid.uuid4())

                services["audit"].log(
                    AuditAction.DOCUMENT_UPLOAD,
                    st.session_state.user_id, st.session_state.session_id, doc_id,
                    {"filename": uploaded_file.name, "size": file_metadata["size_bytes"],
                     "file_type": file_metadata["extension"]},
                )

                analysis = services["claude"].analyze_document(
                    representative_excerpt(document_text))
                services["audit"].log(
                    AuditAction.DOCUMENT_ANALYSIS,
                    st.session_state.user_id, st.session_state.session_id, doc_id,
                    {"analysis_type": "full", "confidence": analysis.get("confidence", 0)},
                    confidence_score=analysis.get("confidence", 0),
                )

                st.session_state.documents.append({
                    "filename": uploaded_file.name,
                    "content": document_text,
                    "metadata": file_metadata,
                    "document_id": doc_id,
                    "uploaded_at": datetime.now().isoformat(),
                    "analysis": analysis,
                })
                added += 1
            except Exception as e:
                st.error(f"❌ {uploaded_file.name}: {e}")
            progress.progress(n / len(uploaded_files), text=f"Processed {n}/{len(uploaded_files)}")
        progress.empty()

        if added:
            # Active document defaults to the most recently added.
            st.session_state.document_data = st.session_state.documents[-1]
            st.session_state.analysis_result = st.session_state.documents[-1]["analysis"]
            retriever = _rebuild_index()
            chunks = len(getattr(retriever, "chunks", [])) if retriever else 0
            st.success(f"✅ Analyzed {added} document(s). "
                       f"Indexed {chunks} chunks across {len(st.session_state.documents)} "
                       f"document(s) using **{st.session_state.retriever_backend}** search.")

    # ---- Documents overview (multi-doc) ----
    if st.session_state.documents:
        st.markdown("---")
        st.markdown(f"## 📚 Documents ({len(st.session_state.documents)})")

        overview = [{
            "Document": d["filename"],
            "Type": d["metadata"]["extension"],
            "Size (MB)": d["metadata"]["size_mb"],
            "Characters": len(d["content"]),
            "Confidence": f"{d['analysis'].get('confidence', 0):.0%}",
        } for d in st.session_state.documents]
        st.dataframe(overview, width='stretch', hide_index=True)

        names = [d["filename"] for d in st.session_state.documents]
        active_name = st.session_state.document_data["filename"] if st.session_state.document_data else names[0]
        idx = names.index(active_name) if active_name in names else 0
        chosen = st.selectbox("🔎 View analysis for:", names, index=idx)
        active = next(d for d in st.session_state.documents if d["filename"] == chosen)
        st.session_state.document_data = active
        st.session_state.analysis_result = active["analysis"]

        cc1, cc2 = st.columns(2)
        if cc1.button("🗑️ Remove this document", width='stretch'):
            st.session_state.documents = [d for d in st.session_state.documents
                                          if d["filename"] != chosen]
            if st.session_state.documents:
                st.session_state.document_data = st.session_state.documents[-1]
                st.session_state.analysis_result = st.session_state.documents[-1]["analysis"]
                _rebuild_index()
            else:
                st.session_state.document_data = None
                st.session_state.analysis_result = None
                st.session_state.retriever = None
                st.session_state.retriever_backend = "none"
            st.rerun()

    # Display analysis results (for the active document)
    if st.session_state.analysis_result:
        st.markdown("---")
        st.markdown(f"## 📋 Analysis — {st.session_state.document_data['filename']}")

        analysis = st.session_state.analysis_result

        # Confidence badge
        confidence = analysis.get("confidence", 0)
        if confidence >= 0.8:
            badge_class = "confidence-high"
            confidence_text = "High"
        elif confidence >= 0.6:
            badge_class = "confidence-medium"
            confidence_text = "Medium"
        else:
            badge_class = "confidence-low"
            confidence_text = "Low"

        st.markdown(f'<span class="confidence-badge {badge_class}">Confidence: {confidence:.1%} ({confidence_text})</span>', unsafe_allow_html=True)

        # Tabs for analysis details
        analysis_tab1, analysis_tab2, analysis_tab3, analysis_tab4 = st.tabs(["Objective", "Challenges", "Solutions", "Insights"])

        with analysis_tab1:
            st.write(analysis.get("objective", ""))

        with analysis_tab2:
            challenges = analysis.get("challenges", [])
            if isinstance(challenges, list):
                for i, challenge in enumerate(challenges, 1):
                    st.write(f"{i}. {challenge}")
            else:
                st.write(challenges)

        with analysis_tab3:
            solutions = analysis.get("proposed_solutions", [])
            if isinstance(solutions, list):
                for i, solution in enumerate(solutions, 1):
                    st.write(f"{i}. {solution}")
            else:
                st.write(solutions)

        with analysis_tab4:
            insights = analysis.get("insights", [])
            if isinstance(insights, list):
                for insight in insights:
                    st.write(f"• {insight}")
            else:
                st.write(insights)

        # Document info
        st.markdown("---")
        st.markdown("## 📄 Document Information")

        if st.session_state.document_data:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Filename", st.session_state.document_data["metadata"]["filename"][:20])
            with col2:
                st.metric("Size", f"{st.session_state.document_data['metadata']['size_mb']} MB")
            with col3:
                st.metric("Type", st.session_state.document_data["metadata"]["extension"])
            with col4:
                st.metric("Characters", len(st.session_state.document_data["content"]))

# ===== TAB 2: CHAT & QUESTIONS =====
def _is_summarize_all(q: str) -> bool:
    low = q.lower()
    has_summary = any(w in low for w in ["summarize", "summary", "summarise", "overview"])
    has_all = any(w in low for w in ["all", "these", "the docs", "the documents",
                                     "each doc", "every doc", "uploaded", "given",
                                     "all files", "the files"])
    return has_summary and (has_all or len(st.session_state.documents) > 1)


def summarize_all_documents(user_query: str):
    """Produce a per-document summary with headings for every uploaded file."""
    st.session_state.conversation_history.append({"role": "user", "content": user_query})
    parts = []
    sources = []
    for d in st.session_state.documents:
        sources.append(d["filename"])
        ctx = representative_excerpt(d["content"], limit=3000)
        ans = services["claude"].answer_question(
            ctx, "Summarize this document in 2-3 sentences.",
            allow_general_knowledge=False)
        summary = ans.get("answer", "").strip()
        # Fall back to the stored analysis objective if the summary is weak.
        if not summary or ans.get("needs_clarification"):
            summary = (d.get("analysis", {}).get("objective") or "")[:400] or "(no summary available)"
        parts.append(f"### 📄 {d['filename']}\n{summary}")
    body = (f"Here is a summary of all **{len(st.session_state.documents)} uploaded "
            f"document(s)**:\n\n" + "\n\n".join(parts))
    st.session_state.conversation_history.append({
        "role": "assistant", "content": body, "sources": sources,
        "mode": services.get("backend", "offline"),
    })


def process_query(user_query: str):
    """Run one chat turn: answer the question, score it, log it, store it."""
    # 0) Input guardrail: refuse requests for sensitive PII/PHI, naming the type.
    sensitive = check_sensitive_request(user_query)
    if sensitive is not None:
        services["audit"].log(
            AuditAction.GUARDRAIL_TRIGGERED,
            st.session_state.user_id, st.session_state.session_id,
            st.session_state.document_data["document_id"] if st.session_state.document_data else "-",
            {"query": user_query, "guardrail": sensitive.guardrail_type.value,
             "category": sensitive.details.get("category"),
             "field": sensitive.details.get("field")},
        )
        st.session_state.conversation_history.append({"role": "user", "content": user_query})
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": (f"🛡️ **Guardrail triggered — PII/PHI Protection "
                        f"(`{sensitive.guardrail_type.value}`)**\n\n{sensitive.message}\n\n"
                        f"I can discuss the document's content in general terms, but I "
                        f"won't reveal or extract personal or health identifiers."),
            "guardrail_block": True,
            "mode": services.get("backend", "offline"),
        })
        return

    # 0b) "Summarize all the documents" → per-document headings + summaries.
    if st.session_state.documents and _is_summarize_all(user_query):
        summarize_all_documents(user_query)
        return

    # Retrieve the most relevant chunks for this question (RAG). Fall back to
    # the leading text if no index is available.
    retriever = st.session_state.get("retriever")
    retrieved = []
    if retriever is not None:
        try:
            retrieved = retriever.search(user_query, top_k=4)
        except Exception:
            retrieved = []
    if retrieved:
        # Prefix each chunk with its source so the model (and metrics) see it.
        context = "\n\n".join(f"[Source: {h['source']}]\n{h['text']}" for h in retrieved)
        sources = []
        for h in retrieved:
            if h["source"] not in sources:
                sources.append(h["source"])
    else:
        context = st.session_state.document_data["content"][:3000]
        sources = [st.session_state.document_data["filename"]] if st.session_state.document_data else []

    # Multi-turn memory: give the model the last couple of exchanges so follow-up
    # questions ("what about the second one?") stay coherent. Guardrails still run
    # on every new query above, so this can't bypass PII/PHI protection.
    recent = [m for m in st.session_state.conversation_history
              if m["role"] in ("user", "assistant") and not m.get("guardrail_block")][-4:]
    if recent:
        convo = "\n".join(f"{m['role'].capitalize()}: {m['content'][:300]}" for m in recent)
        context = f"Conversation so far:\n{convo}\n\n---\nDocument context:\n{context}"

    st.session_state.conversation_history.append({"role": "user", "content": user_query})

    response = services["claude"].answer_question(
        context, user_query,
        allow_general_knowledge=allow_general_knowledge,
    )
    answer = response.get("answer", "")
    confidence = response.get("confidence", 0.0)
    mode = response.get("mode", "claude")

    # Clarification turn: the model needs more info. Show the prompt, don't score it.
    if response.get("needs_clarification"):
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": "🤔 " + answer,
            "needs_clarification": True,
            "mode": mode,
        })
        return

    # Output-side guardrail: if the produced answer would reveal PII/PHI
    # identifiers (catches questions that slipped past the input check, e.g.
    # vaguely-worded autosuggestions), refuse and warn instead of showing it.
    pii_in_answer = services["guardrails"].check_pii(answer)
    if pii_in_answer.triggered:
        services["audit"].log(
            AuditAction.GUARDRAIL_TRIGGERED,
            st.session_state.user_id, st.session_state.session_id,
            st.session_state.document_data["document_id"] if st.session_state.document_data else "-",
            {"query": user_query, "guardrail": "pii_detection",
             "where": "answer", "detail": pii_in_answer.message},
        )
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": (f"🛡️ **Guardrail triggered — PII/PHI Protection "
                        f"(`pii_detection`)**\n\nThe answer to that question would "
                        f"reveal sensitive personal/health information "
                        f"({pii_in_answer.message.replace('PII detected: ', '')}), so I "
                        f"can't show it. I can answer general, non-identifying questions "
                        f"about the document instead."),
            "guardrail_block": True,
            "mode": mode,
        })
        return

    # Evaluation metrics: accuracy = mean(confidence, groundedness, usefulness)
    metrics = evaluate_answer(answer, context, confidence)

    # Guardrails (e.g. low-confidence, PII, relevance).
    guardrail_results = services["guardrails"].run_all_checks(
        answer, query=user_query, confidence=confidence, domain="general"
    )
    triggered = [r for r in guardrail_results if r.triggered]
    if triggered:
        services["audit"].log(
            AuditAction.GUARDRAIL_TRIGGERED,
            st.session_state.user_id,
            st.session_state.session_id,
            st.session_state.document_data["document_id"],
            {"query": user_query, "count": len(triggered),
             "messages": [r.message for r in triggered]},
        )

    # Log the query with full evaluation metrics for the analytics/audit tabs.
    services["audit"].log(
        AuditAction.USER_QUERY,
        st.session_state.user_id,
        st.session_state.session_id,
        st.session_state.document_data["document_id"],
        {
            "query": user_query,
            "confidence": metrics["confidence"],
            "groundedness": metrics["groundedness"],
            "groundness": metrics["groundedness"],
            "usefulness": metrics["usefulness"],
            "accuracy_score": metrics["accuracy_score"],
            "mode": mode,
        },
        confidence_score=metrics["confidence"],
    )

    # Redact PII in the displayed answer if enabled.
    display_answer = redact_pii(answer) if enable_pii_redaction else answer

    st.session_state.conversation_history.append({
        "role": "assistant",
        "content": display_answer,
        "metrics": metrics,
        "mode": mode,
        "sources": sources,
        "guardrails": [r.message for r in triggered],
    })


def render_metrics_badges(metrics: dict, mode: str):
    """Small inline evaluation panel under an assistant answer."""
    badge = {"claude": "🟢 Claude", "groq": "⚡ Groq",
             "offline": "⚪ Offline (grounded)"}.get(mode, "⚪ Offline (grounded)")
    st.caption(f"Answer mode: {badge}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Accuracy", f"{metrics.get('accuracy_score', 0):.0%}")
    m2.metric("Confidence", f"{metrics.get('confidence', 0):.0%}")
    m3.metric("Groundedness", f"{metrics.get('groundedness', 0):.0%}")
    m4.metric("Usefulness", f"{metrics.get('usefulness', 0):.0%}")


with tab2:
    if not st.session_state.document_data:
        st.info("📤 Please upload and analyze a document first.")
    else:
        ndocs = len(st.session_state.documents)
        st.markdown(f"## 💬 Ask Questions Across Your Documents ({ndocs})")
        backend = services.get("backend", "offline")
        mode_label = {
            "groq": "⚡ Groq connected — live LLM answers",
            "claude": "🟢 Claude connected — live LLM answers",
            "local": "🦙 Local LLM (Ollama/vLLM) — live LLM answers",
            "offline": "⚪ Offline mode — answers are extracted directly from your document",
        }.get(backend, "⚪ Offline mode")
        if not services["claude"].online:
            mode_label = "⚪ Offline mode — answers are extracted directly from your document"
        vb = st.session_state.get("retriever_backend", "none")
        vb_label = {"faiss": "FAISS", "pinecone": "Pinecone", "qdrant": "Qdrant",
                    "pgvector": "pgvector", "tfidf": "TF-IDF", "none": "plain text"}.get(vb, vb)
        st.caption(f"Status: {mode_label}  ·  🔎 Retrieval: {vb_label}  ·  📚 {ndocs} document(s) indexed")

        # Process any queued question (from the Send button or a suggestion chip).
        if st.session_state.get("pending_query"):
            q = st.session_state.pending_query
            st.session_state.pending_query = ""
            with st.spinner("🤖 Thinking..."):
                process_query(q)
            st.rerun()

        # Display chat history (with per-answer evaluation metrics).
        for message in st.session_state.conversation_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                if message["role"] == "assistant":
                    if message.get("sources"):
                        st.caption("📎 Sources: " + ", ".join(message["sources"]))
                    if message.get("guardrails"):
                        for g in message["guardrails"]:
                            if g:
                                st.warning(f"⚠️ {g}")
                    if message.get("metrics"):
                        render_metrics_badges(message["metrics"], message.get("mode", "claude"))

        # Auto-suggestions (cached per turn so we don't recompute every rerun).
        st.markdown("### 💡 Suggested Questions")
        turn_count = len(st.session_state.conversation_history)
        last_user_query = next(
            (m["content"] for m in reversed(st.session_state.conversation_history)
             if m["role"] == "user"), ""
        )
        if st.session_state.get("_sugg_turn") != turn_count:
            raw_suggestions = services["claude"].get_auto_suggestions(
                st.session_state.document_data["content"][:1000], last_user_query
            )
            # Never suggest questions that would request sensitive PII/PHI.
            st.session_state["_suggestions"] = [
                s for s in raw_suggestions if check_sensitive_request(s) is None
            ]
            st.session_state["_sugg_turn"] = turn_count
        suggestions = st.session_state.get("_suggestions", [])

        if suggestions:
            cols = st.columns(min(3, len(suggestions)))
            for idx, suggestion in enumerate(suggestions[:3]):
                with cols[idx % len(cols)]:
                    label = suggestion if len(suggestion) <= 60 else suggestion[:57] + "..."
                    if st.button(f"❓ {label}", width='stretch', key=f"suggest_{turn_count}_{idx}"):
                        st.session_state.pending_query = suggestion
                        st.rerun()

        # Query input.
        col1, col2 = st.columns([4, 1])
        with col1:
            user_query = st.text_input(
                "Your question:",
                placeholder="Ask anything about the document...",
                label_visibility="collapsed",
                key=f"chat_input_{turn_count}",
            )
        with col2:
            send_button = st.button("➡️ Send", width='stretch')

        if send_button and user_query:
            st.session_state.pending_query = user_query
            st.rerun()

# ===== AGENT PIPELINE TAB =====
def _risk_gauge_svg(score: int) -> str:
    """Simple animated SVG gauge (0-10)."""
    pct = max(0, min(10, score)) / 10
    angle = -90 + pct * 180
    color = "#16a34a" if score <= 4 else ("#d97706" if score <= 7 else "#dc2626")
    return f"""
    <svg viewBox="0 0 200 120" width="220" height="132">
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="#e5e7eb" stroke-width="16"/>
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="{color}" stroke-width="16"
            stroke-dasharray="251" stroke-dashoffset="{251 - 251*pct}" stroke-linecap="round"/>
      <line x1="100" y1="100" x2="{100 + 70*__import__('math').cos(__import__('math').radians(angle))}"
            y2="{100 + 70*__import__('math').sin(__import__('math').radians(angle))}"
            stroke="#111827" stroke-width="3"/>
      <circle cx="100" cy="100" r="6" fill="#111827"/>
      <text x="100" y="118" text-anchor="middle" font-size="22" font-weight="700" fill="{color}">{score}/10</text>
    </svg>"""


with tab_pipeline:
    st.markdown("## 🤖 Multi-Agent Analysis Pipeline")
    st.caption("Supervisor orchestrates Intake → Retrieval + Research → Report → "
               "Evaluator (RAGAS gate). Runs in DEMO mode with zero API keys.")

    # ---- Webhook inbox: jobs submitted to the FastAPI webhook ----
    with st.expander("📨 Webhook inbox (jobs submitted via the API)", expanded=False):
        ci1, ci2 = st.columns([1, 3])
        if ci1.button("🔄 Check for new jobs", width='stretch'):
            st.rerun()
        try:
            jobs = JobStore().list(limit=15)
        except Exception:
            jobs = []
        if not jobs:
            st.caption("No webhook jobs yet. POST to `/api/v1/pipeline/submit` "
                       "(run `python start.py` or the API server first).")
        else:
            st.dataframe(
                [{"Job": j["id"], "Status": j["status"], "Task": (j["task"] or "")[:60]}
                 for j in jobs], width='stretch', hide_index=True)
            done = [j for j in jobs if j["status"] == "done" and j["result"]]
            if done:
                pick = st.selectbox("Open a finished job", [j["id"] for j in done])
                if st.button("📂 Load job result"):
                    st.session_state.pipeline_result = next(
                        j["result"] for j in done if j["id"] == pick)
                    st.rerun()

    if not st.session_state.documents:
        st.info("📤 Upload at least one document first (Upload & Analyze tab).")
    else:
        demo = not services["claude"].online
        badge = "🟢 LIVE LLM" if not demo else "🟡 DEMO MODE (offline, synthetic reasoning)"
        st.markdown(f"**Mode:** {badge}  ·  **Documents:** {len(st.session_state.documents)}  "
                    f"·  **Retrieval:** {st.session_state.get('retriever_backend','none')}")

        task = st.text_input("Investigation task / question",
                             value="Summarize the objective, key risks, and recommended actions.")
        if st.button("🚀 Run pipeline", use_container_width=False):
            with st.spinner("Agents working..."):
                st.session_state.pipeline_result = run_agent_pipeline(
                    st.session_state.documents, task,
                    retriever=st.session_state.get("retriever"),
                    llm=services["claude"],
                )

        res = st.session_state.get("pipeline_result")
        if res:
            report = res["report"]
            ev = res["evaluation"]

            top = st.columns([1, 2])
            with top[0]:
                st.markdown("### Quality score")
                st.markdown(_risk_gauge_svg(report["score"]), unsafe_allow_html=True)
                gate = ev["gate"]
                (st.success if gate["passed"] else st.warning)(gate["verdict"])
            with top[1]:
                st.markdown("### 🧭 Agent timeline")
                st.dataframe(
                    [{"Agent": t["agent"], "Status": "✅" if t["status"] == "ok" else "❌",
                      "Latency (s)": t["latency_s"], "Summary": t["summary"]}
                     for t in res["traces"]],
                    width='stretch', hide_index=True)
                st.caption(f"run_id `{res['run_id']}` · total {res['latency_s']}s · backend {res['backend']}")

            st.markdown("### 📝 Report")
            st.write(report.get("narrative", ""))
            if report.get("evidence"):
                st.markdown("**Evidence**")
                st.dataframe(
                    [{"Source": e["source"], "Snippet": e["snippet"]} for e in report["evidence"]],
                    width='stretch', hide_index=True)
            if report.get("actions"):
                st.markdown("**Recommended actions**")
                for a in report["actions"]:
                    st.write(f"• {a}")

            st.markdown("### 📊 RAGAS quality gate")
            rc = st.columns(4)
            rc[0].metric("Faithfulness", f"{ev['ragas']['faithfulness']:.0%}")
            rc[1].metric("Relevance", f"{ev['ragas']['answer_relevance']:.0%}")
            rc[2].metric("Context recall", f"{ev['ragas']['context_recall']:.0%}")
            rc[3].metric("Overall", f"{ev['ragas']['overall']:.0%}")
            for reason in ev["gate"]["reasons"]:
                st.caption(f"• {reason}")

            st.markdown("### 🛡️ Guardrail audit")
            st.dataframe(
                [{"Check": g["type"], "Triggered": "⚠️" if g["triggered"] else "✅",
                  "Severity": g["severity"], "Detail": g["message"]}
                 for g in res["guardrail_audit"]],
                width='stretch', hide_index=True)

            st.download_button(
                "📥 Download investigation (JSON)",
                data=json.dumps(res, indent=2, default=str),
                file_name=f"investigation_{res['run_id']}.json",
                mime="application/json")

# ===== TAB 3: APPROVAL =====
with tab3:
    st.markdown("## ✅ Request Human Approval")
    
    if not st.session_state.document_data:
        st.info("📤 Please upload and analyze a document first.")
    elif not st.session_state.analysis_result:
        st.info("🔍 Please complete the analysis first.")
    else:
        st.write("Review the analysis and request approval for report generation.")
        
        # Show analysis summary
        st.markdown("### 📋 Analysis Summary")
        analysis = st.session_state.analysis_result
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Objective", "✓" if analysis.get("objective") else "✗")
        with col2:
            challenges = analysis.get("challenges", [])
            count = len(challenges) if isinstance(challenges, list) else 1
            st.metric("Challenges Identified", count)
        with col3:
            solutions = analysis.get("proposed_solutions", [])
            count = len(solutions) if isinstance(solutions, list) else 1
            st.metric("Solutions Proposed", count)
        
        # Approval request form
        st.markdown("### 📝 Approval Request Form")
        
        approval_name = st.text_input("Your Name (for approval record)")
        approval_comments = st.text_area("Comments or notes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Approve & Request Report", width='stretch'):
                if not approval_name:
                    st.error("Please enter your name")
                else:
                    # Create approval request
                    request_id = services["approval"].create_request(
                        st.session_state.document_data["document_id"],
                        st.session_state.user_id,
                        st.session_state.analysis_result
                    )
                    
                    # Log approval request
                    services["audit"].log(
                        AuditAction.APPROVAL_REQUESTED,
                        st.session_state.user_id,
                        st.session_state.session_id,
                        st.session_state.document_data["document_id"],
                        {
                            "request_id": request_id,
                            "approver": approval_name,
                            "comments": approval_comments
                        }
                    )
                    
                    st.session_state.approval_requested = True
                    st.session_state.approval_status = "pending"
                    
                    st.success(f"✅ Approval requested! Request ID: {request_id[:12]}...")
        
        with col2:
            if st.button("❌ Reject", width='stretch'):
                st.error("Analysis rejected. Please upload a new document.")

# ===== TAB 4: ANALYTICS =====
with tab4:
    st.markdown("## 📊 Analytics Dashboard")

    user_stats = services["audit"].get_user_stats(st.session_state.user_id)
    analytics_summary = services["audit"].get_analytics_summary(st.session_state.user_id)
    evaluation = services["audit"].get_evaluation_metrics(st.session_state.user_id)

    # Top-line KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Documents", user_stats.get("documents_uploaded", 0))
    k2.metric("Queries", user_stats.get("total_queries", 0))
    k3.metric("Accuracy Score", f"{analytics_summary.get('accuracy_score', 0):.1%}")
    k4.metric("Guardrail Alerts", user_stats.get("guardrails_triggered", 0))

    st.markdown("---")
    st.markdown("### 📉 Accuracy components (confidence · groundedness · usefulness)")
    comp1, comp2, comp3 = st.columns(3)
    comp1.metric("Avg. Confidence", f"{evaluation.get('avg_confidence', 0):.1%}")
    comp2.metric("Avg. Groundedness", f"{evaluation.get('avg_groundedness', 0):.1%}")
    comp3.metric("Avg. Usefulness", f"{evaluation.get('avg_usefulness', 0):.1%}")

    # Real per-query accuracy trend (oldest -> newest)
    recent = list(reversed(evaluation.get("recent_queries", [])))
    if recent:
        st.markdown("### 📈 Per-query accuracy over time")
        trend = {
            "Accuracy": [q.get("accuracy_score") or 0 for q in recent],
            "Confidence": [q.get("confidence") or 0 for q in recent],
            "Groundedness": [q.get("groundedness") or 0 for q in recent],
            "Usefulness": [q.get("usefulness") or 0 for q in recent],
        }
        st.line_chart(trend)
    else:
        st.info("Ask a few questions in the Chat tab to populate accuracy analytics.")

    st.markdown("---")
    st.markdown("### 📈 User Statistics")
    stats_data = {
        "Metric": ["Documents Uploaded", "Total Queries", "Approvals Granted", "Alerts Triggered"],
        "Count": [
            user_stats.get("documents_uploaded", 0),
            user_stats.get("total_queries", 0),
            user_stats.get("approvals_granted", 0),
            user_stats.get("guardrails_triggered", 0),
        ]
    }
    st.dataframe(stats_data, width='stretch')
    st.markdown("### 🔍 Analytics Summary")
    st.json(analytics_summary)

# ===== TAB 5: AUDIT LOGS =====
with tab5:
    st.markdown("## 🧾 Audit Logs")
    audit_logs = services["audit"].get_logs(user_id=st.session_state.user_id, limit=200)
    if not audit_logs:
        st.info("No audit event history available yet.")
    else:
        rows = []
        for log in audit_logs:
            details = {}
            try:
                details = json.loads(log["details"])
            except Exception:
                details = {}
            rows.append({
                "timestamp": log["timestamp"],
                "action": log["action"],
                "document_id": log["document_id"],
                "query": details.get("query", ""),
                "confidence": details.get("confidence"),
                "groundness": details.get("groundness"),
                "usefulness": details.get("usefulness"),
                "accuracy_score": details.get("accuracy_score"),
                "details": json.dumps(details, ensure_ascii=False)
            })
        st.dataframe(rows, width='stretch')
        evaluation = services["audit"].get_evaluation_metrics(st.session_state.user_id)
        st.markdown("---")
        st.markdown("### 🔎 Evaluation Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Avg. Confidence", f"{evaluation.get('avg_confidence', 0):.1%}")
        with col2:
            st.metric("Avg. Groundness", f"{evaluation.get('avg_groundness', 0):.1%}")
        with col3:
            st.metric("Avg. Usefulness", f"{evaluation.get('avg_usefulness', 0):.1%}")
        st.metric("Overall Accuracy", f"{evaluation.get('accuracy_score', 0):.1%}")
        st.markdown("### 📊 Evaluation Details")
        st.json(evaluation)

# ===== TAB 6: EXPORT =====
with tab6:
    st.markdown("## 📥 Download Your Report")
    
    if not st.session_state.analysis_result:
        st.info("📋 No analysis available. Please complete the analysis first.")
    else:
        st.markdown("### 📄 Export Formats")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 Download PDF", width='stretch'):
                with st.spinner("📝 Generating PDF..."):
                    try:
                        pdf_path = services["report"].generate_analysis_report(
                            st.session_state.document_data["document_id"],
                            st.session_state.document_data["filename"],
                            st.session_state.analysis_result,
                            st.session_state.conversation_history,
                            format="pdf"
                        )
                        
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download PDF Report",
                                data=f.read(),
                                file_name=Path(pdf_path).name,
                                mime="application/pdf"
                            )
                        
                        # Log download
                        services["audit"].log(
                            AuditAction.REPORT_DOWNLOADED,
                            st.session_state.user_id,
                            st.session_state.session_id,
                            st.session_state.document_data["document_id"],
                            {"format": "pdf"}
                        )
                        
                        st.success("✅ PDF generated successfully!")
                    except Exception as e:
                        st.error(f"Error generating PDF: {e}")
        
        with col2:
            if st.button("📘 Download DOCX", width='stretch'):
                with st.spinner("📝 Generating DOCX..."):
                    try:
                        docx_path = services["report"].generate_analysis_report(
                            st.session_state.document_data["document_id"],
                            st.session_state.document_data["filename"],
                            st.session_state.analysis_result,
                            st.session_state.conversation_history,
                            format="docx"
                        )
                        
                        with open(docx_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download DOCX Report",
                                data=f.read(),
                                file_name=Path(docx_path).name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                        
                        services["audit"].log(
                            AuditAction.REPORT_DOWNLOADED,
                            st.session_state.user_id,
                            st.session_state.session_id,
                            st.session_state.document_data["document_id"],
                            {"format": "docx"}
                        )
                        
                        st.success("✅ DOCX generated successfully!")
                    except Exception as e:
                        st.error(f"Error generating DOCX: {e}")
        
        with col3:
            if st.button("📊 Download JSON", width='stretch'):
                with st.spinner("📊 Generating JSON..."):
                    try:
                        json_path = services["report"].generate_json_report({
                            "document_id": st.session_state.document_data["document_id"],
                            "filename": st.session_state.document_data["filename"],
                            "analysis": st.session_state.analysis_result,
                            "conversation_history": st.session_state.conversation_history,
                            "generated_at": datetime.now().isoformat()
                        })
                        
                        with open(json_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download JSON Report",
                                data=f.read(),
                                file_name=Path(json_path).name,
                                mime="application/json"
                            )
                        
                        services["audit"].log(
                            AuditAction.REPORT_DOWNLOADED,
                            st.session_state.user_id,
                            st.session_state.session_id,
                            st.session_state.document_data["document_id"],
                            {"format": "json"}
                        )
                        
                        st.success("✅ JSON generated successfully!")
                    except Exception as e:
                        st.error(f"Error generating JSON: {e}")

# ===== TAB 7: TESTS & COVERAGE =====
with tab7:
    st.markdown("## 🧪 Test Suite & Coverage")
    st.write("Run the automated test suite and view pass/fail results and code "
             "coverage across the core modules.")

    if st.button("▶️ Run test suite", use_container_width=False):
        with st.spinner("Running pytest with coverage..."):
            st.session_state.test_results = run_test_suite(str(Path(__file__).parent))

    results = st.session_state.get("test_results")
    if not results:
        st.info("Click **Run test suite** to execute the tests and measure coverage.")
    elif not results.get("ok"):
        st.error(results.get("error", "Test run failed."))
        if results.get("output"):
            with st.expander("Output"):
                st.code(results["output"])
    else:
        totals = results["tests"]["totals"]
        coverage = results.get("coverage") or {}

        # KPI row
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total", totals["total"])
        k2.metric("✅ Passed", totals["passed"])
        k3.metric("❌ Failed", totals["failed"] + totals["errors"])
        k4.metric("⏭️ Skipped", totals["skipped"])
        k5.metric("🎯 Coverage", f"{coverage.get('total_percent', 0)}%")

        pass_rate = (totals["passed"] / totals["total"]) if totals["total"] else 0
        st.progress(pass_rate, text=f"Pass rate: {pass_rate:.0%}  ·  "
                                    f"Duration: {totals['duration']:.2f}s")
        if totals["failed"] + totals["errors"] == 0:
            st.success(f"All {totals['passed']} tests passed 🎉")
        else:
            st.warning(f"{totals['failed'] + totals['errors']} test(s) need attention.")

        # Test cases table
        st.markdown("### ✔️ Test cases")
        icon = {"passed": "✅", "failed": "❌", "error": "💥", "skipped": "⏭️"}
        st.dataframe(
            [{"": icon.get(c["status"], ""), "Test": c["name"],
              "Suite": c["suite"].split(".")[-1], "Time (s)": c["time"],
              "Status": c["status"]} for c in results["tests"]["cases"]],
            width='stretch', hide_index=True,
        )

        # Coverage table + chart
        if coverage.get("files"):
            st.markdown("### 🎯 Coverage by module")
            st.dataframe(
                [{"Module": f["file"], "Coverage %": f["percent"],
                  "Covered": f["covered"], "Statements": f["statements"]}
                 for f in coverage["files"]],
                width='stretch', hide_index=True,
            )
            st.bar_chart({f["file"].replace("core/", ""): f["percent"]
                          for f in coverage["files"]})

        with st.expander("Raw test output"):
            st.code(results.get("output", ""))

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;">
    <p><strong>ProposalForge Pro</strong> © 2024 | Powered by Claude AI | Enterprise-Grade Document Analysis</p>
    <p>Session: {}</p>
</div>
""".format(st.session_state.session_id[:12] + "..."), unsafe_allow_html=True)
