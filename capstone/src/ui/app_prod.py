"""ProposalForge Agent — Copilot-Studio-style UI.

One combined Overview page (Details + Knowledge on the left, Test/Chat on the
right) plus Agents, Evaluation, Analytics and Test Suites. No login. Answers are
grounded in the uploaded knowledge, guardrailed for PII/PHI, and the chat
suggests follow-ups based on the previous question. Reads PDFs/images including
architecture diagrams & charts via Azure Document Intelligence + LLM vision.
"""
from __future__ import annotations

import os
import re
import io
import csv
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.agents.llm_backend import get_llm_client
from src.retrieval.retriever import get_retriever
from src.common.file_processor import FileProcessor
from src.common import doc_analysis, guardrails as gr
from src.common.load_tester import run_load_test
from src.common.diagnostics import system_status
from src.common.test_runner import run_test_suite

# --------------------------------------------------------------------------- #
st.set_page_config(page_title="ProposalForge Agent", page_icon="🤖",
                   layout="wide", initial_sidebar_state="collapsed")

# ------------------------------- colourful theme --------------------------- #
st.markdown("""
<style>
:root{--ink:#16233B;--teal:#0F9AA8;--tealD:#0B7A86;--amber:#E9950C;--violet:#5B5BD6;}
.block-container{padding-top:1.2rem;}
/* centered gradient title banner */
.pf-hero{background:linear-gradient(120deg,#16233B 0%,#0F9AA8 60%,#3FBFD4 100%);
  color:#fff;border-radius:18px;padding:22px 26px;text-align:center;margin-bottom:14px;
  box-shadow:0 8px 24px rgba(15,154,168,.25);}
.pf-hero h1{margin:0;font-size:34px;font-weight:800;letter-spacing:.3px;}
.pf-hero p{margin:.35rem 0 0;font-size:15px;opacity:.95;}
.pf-badge{display:inline-block;padding:3px 12px;border-radius:999px;font-weight:700;font-size:13px;}
.pf-badge.on{background:#DCFCE7;color:#166534;} .pf-badge.off{background:#FEF3C7;color:#92400E;}
.pf-dom{display:inline-block;padding:2px 10px;border-radius:999px;background:#E8F6F8;color:#0B7A86;font-weight:700;font-size:12px;}
/* coloured tab bar */
.stTabs [data-baseweb="tab-list"]{gap:8px;}
.stTabs [data-baseweb="tab"]{background:#EEF3F8;border-radius:12px 12px 0 0;padding:10px 18px;font-weight:700;color:#33415C;}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#0F9AA8,#3FBFD4);color:#fff;}
/* pill buttons */
div[data-testid="stButton"]>button{border-radius:999px;border:1px solid #CFE0E3;font-weight:600;}
div[data-testid="stButton"]>button:hover{border-color:#0F9AA8;color:#0F9AA8;}
h3,h4{color:#16233B;}
</style>
""", unsafe_allow_html=True)

# ------------------------------- resources --------------------------------- #
@st.cache_resource
def get_client(provider: str = "claude"):
    return get_llm_client(provider)          # (client, backend) with failover

@st.cache_resource
def get_guard():
    return gr.Guardrails()

@st.cache_resource
def get_engine():
    from src.orchestrator.engine import Engine
    return Engine()

DOMAINS = {
    "Finance": ["loan", "credit", "invest", "revenue", "bank", "interest", "capital",
                "portfolio", "risk", "subsidy", "budget", "tax", "roi", "cash"],
    "Healthcare": ["patient", "clinical", "diagnos", "treatment", "hospital", "phi",
                   "medical", "disease", "drug", "therapy", "care", "health"],
    "Agriculture": ["crop", "farm", "soil", "irrigation", "yield", "pest", "harvest",
                    "seed", "fertiliz", "livestock", "agri", "millet"],
}

def classify_domain(text: str) -> str:
    t = (text or "").lower()
    best, score = "General", 0
    for d, kws in DOMAINS.items():
        s = sum(1 for k in kws if k in t)
        if s > score:
            best, score = d, s
    return best

# ------------------------------- session ----------------------------------- #
def _init():
    ss = st.session_state
    ss.setdefault("documents", [])
    ss.setdefault("history", [])            # [{role,content,confidence,sources,domain,blocked}]
    ss.setdefault("retriever", None)
    ss.setdefault("retriever_backend", "none")
    ss.setdefault("agent_name", "ProposalForge Agent")
    ss.setdefault("agent_description",
                  "Answers questions about your proposals & documents across "
                  "Finance, Healthcare and Agriculture — grounded, cited and safe.")
    ss.setdefault("agent_instructions", "")
    ss.setdefault("guardrail_hits", 0)
    ss.setdefault("audit", [])
    ss.setdefault("uid", "user")
    ss.setdefault("sid", uuid.uuid4().hex[:8])
_init()

provider = st.session_state.get("llm_provider", "Claude")
client, backend = get_client(provider.lower())
guard = get_guard()
online = bool(getattr(client, "online", False))

# ------------------------------- helpers ----------------------------------- #
def rebuild_index():
    docs = [{"id": d["id"], "name": d["name"], "text": d["text"]}
            for d in st.session_state.documents]
    try:
        r = get_retriever()
        r.build_documents(docs)
        st.session_state.retriever = r
        st.session_state.retriever_backend = getattr(r, "backend", "none")
    except Exception as e:
        st.session_state.retriever = None
        st.session_state.retriever_backend = "none"
        st.warning(f"Vector index unavailable ({e}); using plain-text context.")

def audit(action: str, detail: str = ""):
    st.session_state.audit.insert(0, {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": st.session_state.uid, "action": action, "detail": str(detail)[:180]})
    st.session_state.audit = st.session_state.audit[:300]

def _audit_csv(rows) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["time", "user", "action", "detail"])
    w.writeheader(); w.writerows(rows)
    return buf.getvalue()

_LABELS = {"OBJECTIVE": "Objective", "CURRENT SOLUTIONS": "Current solutions",
           "PROPOSED SOLUTIONS": "Proposed solutions", "INSIGHTS": "Insights"}

def _parse_sections(raw: str) -> dict:
    out = {v: "" for v in _LABELS.values()}
    cur = None
    for line in raw.splitlines():
        s = line.strip()
        head = s.upper().rstrip(":").strip()
        if head in _LABELS:
            cur = _LABELS[head]; continue
        if cur and s:
            out[cur] += (("\n" if out[cur] else "") + s.lstrip("-•* ").strip())
    return out

def analyze_fields(text: str) -> dict:
    """Objective / Current solutions / Proposed solutions / Insights for a doc."""
    if online and hasattr(client, "complete"):
        try:
            raw = client.complete(
                "You analyze business and proposal documents. Be concise.",
                "Extract these four sections as short bullet lines using these EXACT "
                "headers:\nOBJECTIVE:\nCURRENT SOLUTIONS:\nPROPOSED SOLUTIONS:\nINSIGHTS:\n\n"
                f"Document:\n{text[:6000]}")
            if raw and "OBJECTIVE" in raw.upper():
                return _parse_sections(raw)
        except Exception:
            pass
    # offline / fallback via the structured analyzer
    a = {}
    try:
        a = client.analyze_document(text[:6000])
    except Exception:
        a = {}
    fmt = lambda v: "\n".join(v) if isinstance(v, list) else (v or "")
    return {"Objective": fmt(a.get("objective", "")),
            "Current solutions": fmt(a.get("challenges", [])),
            "Proposed solutions": fmt(a.get("proposed_solutions", [])),
            "Insights": fmt(a.get("insights", []))}

def ingest_files(files, scan_visuals: bool):
    added = 0
    names = {d["name"] for d in st.session_state.documents}
    for uf in files:
        if uf.name in names:
            continue
        try:
            raw = bytes(uf.getbuffer())
            ext = os.path.splitext(uf.name)[1].lower()
            is_img = ext in (".png", ".jpg", ".jpeg")
            # text: local for docs; Azure DI / vision for images or when scanning
            if is_img:
                text = ""
            else:
                p = Path("temp"); p.mkdir(exist_ok=True)
                fp = p / uf.name; fp.write_bytes(raw)
                text = FileProcessor.extract_text(str(fp))
            visuals = {"available": False, "descriptions": []}
            if scan_visuals or is_img:
                da = doc_analysis.analyze_document(raw, uf.name, include_visuals=True)
                visuals = da.get("visuals", visuals)
                if not text:
                    text = da.get("text") or "\n\n".join(
                        f"[Figure p{d['page']}] {d['description']}"
                        for d in visuals.get("descriptions", []))
            dom = classify_domain(text or uf.name)
            st.session_state.documents.append({
                "id": uuid.uuid4().hex, "name": uf.name, "text": text or "",
                "domain": dom, "visuals": visuals,
                "analysis": analyze_fields(text or uf.name),
                "chars": len(text or ""), "at": datetime.now().strftime("%H:%M")})
            audit("KNOWLEDGE_UPLOAD",
                  f"{uf.name} · topic={dom} · {len(text or '')} chars"
                  + (" · visuals scanned" if (scan_visuals or is_img) else ""))
            added += 1
        except Exception as e:
            st.error(f"❌ {uf.name}: {e}")
    if added:
        rebuild_index()
    return added

def followups(last_q: str, last_a: str):
    try:
        raw = client.get_auto_suggestions((last_a or "")[:1500], last_q or "")
        out = [s for s in raw if not guard.check_pii(s).triggered]
        return out[:3]
    except Exception:
        return []

def _grounded(answer: str, context: str) -> float:
    a = set(re.findall(r"[a-z]{4,}", (answer or "").lower()))
    c = set(re.findall(r"[a-z]{4,}", (context or "").lower()))
    return round(len(a & c) / max(1, len(a)), 2) if a else 0.0

def answer_query(q: str):
    ss = st.session_state
    # input guardrail
    gin = guard.check_pii(q)
    ss.history.append({"role": "user", "content": q})
    audit("QUERY", q)
    if gin.triggered:
        ss.guardrail_hits += 1
        audit("GUARDRAIL_BLOCK", f"input · {gin.message}")
        ss.history.append({"role": "assistant", "blocked": True,
            "content": f"🛡️ **Guardrail — PII/PHI protection.** {gin.message}. "
                       "I can discuss the documents in general terms but won't reveal "
                       "personal or health identifiers."})
        return
    # retrieve grounded context
    sources, retrieved = [], []
    r = ss.retriever
    if r is not None:
        try:
            retrieved = r.search(q, top_k=4)
        except Exception:
            retrieved = []
    if retrieved:
        context = "\n\n".join(f"[Source: {h['source']}]\n{h['text']}" for h in retrieved)
        for h in retrieved:
            if h["source"] not in sources:
                sources.append(h["source"])
    elif ss.documents:
        context = ss.documents[-1]["text"][:3000]
        sources = [ss.documents[-1]["name"]]
    else:
        context = ""
    # short memory
    recent = [m for m in ss.history if m["role"] in ("user", "assistant")
              and not m.get("blocked")][-4:]
    if recent:
        convo = "\n".join(f"{m['role'].capitalize()}: {m['content'][:280]}" for m in recent)
        context = f"Conversation so far:\n{convo}\n\n---\nDocument context:\n{context}"
    instr = (ss.agent_instructions or "").strip()
    if instr:
        context = f"Agent instructions (follow these):\n{instr}\n\n---\n{context}"
    # answer (allow general knowledge only when no knowledge is loaded, so it
    # still answers ANY domain, but prefers the uploaded documents)
    resp = client.answer_question(context, q, allow_general_knowledge=not bool(ss.documents))
    ans = resp.get("answer", "")
    conf = float(resp.get("confidence", 0.0))
    # output guardrail
    gout = guard.check_pii(ans)
    if gout.triggered:
        ss.guardrail_hits += 1
        audit("GUARDRAIL_REDACT", "answer contained PII/PHI — redacted")
        ans = gr.redact_pii(ans)
    ss.history.append({"role": "assistant", "content": ans, "confidence": conf,
                       "sources": sources, "domain": classify_domain(q),
                       "grounded": _grounded(ans, context)})

# ------------------------------- centered title ---------------------------- #
st.markdown(
    '<div class="pf-hero"><h1>🤖 ProposalForge Agent</h1>'
    '<p>Multi-document agent for any domain — grounded, cited & guardrailed · '
    'reads text, tables & diagrams</p></div>', unsafe_allow_html=True)

tab_over, tab_agents, tab_eval, tab_analytics, tab_activity, tab_tests = st.tabs(
    ["🏠 Overview", "🤖 Agents", "🧪 Evaluation", "📊 Analytics", "🧾 Activity", "✅ Test Suites"])

# =========================== OVERVIEW ====================================== #
with tab_over:
    st.markdown(f"### {st.session_state.agent_name}  "
                + (f'<span class="pf-badge on">● Ready · {backend}</span>' if online
                   else '<span class="pf-badge off">● Offline mode</span>'),
                unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap="large")

    # ---------- LEFT: Details + Knowledge ----------
    with left:
        with st.container(border=True):
            st.markdown("#### 🧩 Details")
            st.text_input("Name", key="agent_name")
            st.text_area("Description", key="agent_description", height=68)
            st.markdown("**Select your agent's model**")
            st.selectbox("Model", ["Claude", "Groq"], index=0, key="llm_provider",
                         label_visibility="collapsed",
                         help="Falls back to the other provider, then offline, if a key is missing.")
            st.caption(f"Active backend: `{backend}`  ·  "
                       + ("🟢 live LLM" if online else "⚪ offline"))
            st.markdown("**Instructions**")
            st.text_area("Instructions", key="agent_instructions", height=96,
                         label_visibility="collapsed",
                         placeholder="Describe what the agent should do, its tone and rules. "
                                     "These guide every answer.")

        with st.container(border=True):
            st.markdown("#### 📚 Knowledge")
            st.caption("Add data, files and resources to inform answers. "
                       "PDFs & images are scanned for text, tables and diagrams.")
            files = st.file_uploader(
                "Add knowledge",
                type=["pdf", "docx", "csv", "xlsx", "pptx", "txt", "md", "png", "jpg", "jpeg"],
                accept_multiple_files=True, label_visibility="collapsed")
            c1, c2 = st.columns([1, 1])
            scan = c1.checkbox("🖼️ Scan diagrams & charts", value=False,
                               help="Azure Document Intelligence (text/tables) + LLM vision "
                                    "for architecture diagrams/graphs. Needs keys to activate.")
            if c2.button("🔍 Add to knowledge", use_container_width=True):
                if files:
                    with st.spinner("Processing…"):
                        n = ingest_files(files, scan)
                    st.success(f"Added {n} file(s). Indexed with "
                               f"`{st.session_state.retriever_backend}` search.")
                else:
                    st.info("Choose file(s) first.")
            docs = st.session_state.documents
            if docs:
                st.markdown(f"**{len(docs)} source(s)** · index "
                            f"`{st.session_state.retriever_backend}`")
                # Highlighted analysis of the most recently added document.
                latest = docs[-1]
                with st.container(border=True):
                    st.markdown(f"##### 📋 Analysis · {latest['name']}")
                    an = latest.get("analysis", {})
                    for sec in ("Objective", "Current solutions",
                                "Proposed solutions", "Insights"):
                        val = (an.get(sec) or "").strip()
                        st.markdown(f"**{sec}**")
                        if val:
                            for ln in val.splitlines():
                                st.markdown(f"- {ln}" if not ln.startswith("-") else ln)
                        else:
                            st.caption("—")
                for i, d in enumerate(docs):
                    with st.expander(f"📄 {d['name']}  ·  {d['domain']}  ·  {d['chars']} chars"):
                        an = d.get("analysis", {})
                        for sec in ("Objective", "Current solutions",
                                    "Proposed solutions", "Insights"):
                            v = (an.get(sec) or "").strip()
                            if v:
                                st.markdown(f"**{sec}:** {v}")
                        vis = d.get("visuals", {})
                        if vis.get("descriptions"):
                            st.markdown("**Diagrams / visuals:**")
                            for v in vis["descriptions"]:
                                st.caption(f"p{v.get('page','?')}: {v.get('description','')[:400]}")
                        elif vis.get("available") is False and vis.get("note"):
                            st.caption(vis["note"])
                        if st.button("Remove", key=f"rm_{i}"):
                            audit("KNOWLEDGE_REMOVE", d["name"])
                            st.session_state.documents.pop(i)
                            rebuild_index(); st.rerun()
            else:
                st.info("No knowledge yet — add a document to start.")

    # ---------- RIGHT: Test your agent (chat) ----------
    with right:
        with st.container(border=True):
            st.markdown("#### 💬 Test your agent")
            if not online:
                st.warning("No online LLM connected — answers are offline extraction. "
                           "Set **CLAUDE_API_KEY** or **GROQ_API_KEY** for live answers.")
            with st.chat_message("assistant"):
                st.write(f"Hello, I'm {st.session_state.agent_name}. "
                         "How can I help you today?")
            for m in st.session_state.history:
                with st.chat_message(m["role"]):
                    st.write(m["content"])
                    if m["role"] == "assistant" and not m.get("blocked"):
                        meta = []
                        if m.get("domain") and m["domain"] != "General":
                            meta.append(f'<span class="pf-dom">{m["domain"]}</span>')
                        st.markdown(" ".join(meta), unsafe_allow_html=True)
                        if m.get("sources"):
                            st.caption("📎 " + ", ".join(m["sources"]))
                        if m.get("confidence") is not None:
                            st.caption(f"confidence {m['confidence']:.0%} · "
                                       f"grounded {m.get('grounded',0):.0%}")

            # follow-ups based on the PREVIOUS question
            last_q = next((m["content"] for m in reversed(st.session_state.history)
                           if m["role"] == "user"), "")
            last_a = next((m["content"] for m in reversed(st.session_state.history)
                           if m["role"] == "assistant"), "")
            if last_q:
                fups = followups(last_q, last_a)
                if fups:
                    st.markdown("**💡 Follow-up questions**")
                    fcols = st.columns(len(fups))
                    for i, f in enumerate(fups):
                        if fcols[i].button(f"❓ {f[:48]}", key=f"f_{len(st.session_state.history)}_{i}"):
                            with st.spinner("🤖 Thinking…"):
                                answer_query(f)
                            st.rerun()

            q = st.chat_input("Ask a question or describe what you need")
            if q:
                with st.spinner("🤖 Thinking…"):
                    answer_query(q)
                st.rerun()

# =========================== AGENTS (LangGraph) ============================ #
with tab_agents:
    st.markdown("### 🤖 Agents — LangGraph pipeline")
    st.caption("Route → Guardrails → Retrieve → Generate → Suggest. Runs on the live "
               "LLM when a key is set. Identifies the topic and answers any domain.")
    if not online:
        st.warning("No online LLM connected — set CLAUDE_API_KEY or GROQ_API_KEY for live "
                   "pipeline answers (not assumptions).")
    aq = st.text_input("Ask the agent pipeline", placeholder="e.g. What is the objective and key risk?")
    if st.button("▶️ Run pipeline") and aq:
        with st.spinner("Running LangGraph pipeline…"):
            try:
                turn = get_engine().ask_graph(aq)
                dom = getattr(turn, "domain", None) or classify_domain(aq)
                st.markdown(f'**Domain:** <span class="pf-dom">{dom}</span>',
                            unsafe_allow_html=True)
                ans = getattr(turn, "answer", None)
                st.write(ans.text if ans else getattr(turn, "message", "(no answer)"))
                if getattr(turn, "follow_ups", None):
                    st.markdown("**Follow-ups:** " + " · ".join(turn.follow_ups))
                st.caption("Pipeline nodes: route → guard → retrieve → generate → suggest")
            except Exception as e:
                st.error(f"Pipeline error: {e}")

# =========================== EVALUATION ==================================== #
with tab_eval:
    st.markdown("### 🧪 Evaluation")
    st.caption("Runs a small grounded-answer check over your knowledge and reports "
               "confidence and groundedness per question.")
    default_qs = "What is the main objective?\nWhat are the key risks?\nWho is eligible?"
    qs = st.text_area("Questions (one per line)", value=default_qs, height=90)
    if st.button("▶️ Run evaluation"):
        if not st.session_state.documents:
            st.info("Add knowledge in the Overview tab first.")
        else:
            rows, gs, cs = [], [], []
            r = st.session_state.retriever
            for q in [x.strip() for x in qs.splitlines() if x.strip()]:
                ret = []
                if r is not None:
                    try: ret = r.search(q, top_k=4)
                    except Exception: ret = []
                ctx = "\n\n".join(h["text"] for h in ret) or \
                      st.session_state.documents[-1]["text"][:3000]
                resp = client.answer_question(ctx, q, allow_general_knowledge=False)
                a = resp.get("answer", ""); conf = float(resp.get("confidence", 0))
                g = _grounded(a, ctx); gs.append(g); cs.append(conf)
                rows.append({"Question": q, "Confidence": f"{conf:.0%}",
                             "Grounded": f"{g:.0%}", "Answer": a[:120] + "…"})
            m1, m2, m3 = st.columns(3)
            m1.metric("Avg confidence", f"{(sum(cs)/len(cs)):.0%}" if cs else "—")
            m2.metric("Avg groundedness", f"{(sum(gs)/len(gs)):.0%}" if gs else "—")
            m3.metric("Questions", len(rows))
            st.dataframe(rows, use_container_width=True, hide_index=True)
            audit("EVALUATION", f"{len(rows)} questions · avg grounded "
                  f"{(sum(gs)/len(gs)):.0%}" if gs else f"{len(rows)} questions")

# =========================== ANALYTICS ===================================== #
with tab_analytics:
    st.markdown("### 📊 Analytics")
    hist = st.session_state.history
    asks = [m for m in hist if m["role"] == "user"]
    ans = [m for m in hist if m["role"] == "assistant" and not m.get("blocked")]
    confs = [m["confidence"] for m in ans if m.get("confidence") is not None]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📚 Documents", len(st.session_state.documents))
    c2.metric("💬 Questions", len(asks))
    c3.metric("🎯 Avg confidence", f"{(sum(confs)/len(confs)):.0%}" if confs else "—")
    c4.metric("🛡️ Guardrail hits", st.session_state.guardrail_hits)
    doms = {}
    for d in st.session_state.documents:
        doms[d["domain"]] = doms.get(d["domain"], 0) + 1
    if doms:
        st.markdown("**Knowledge by domain**")
        st.bar_chart(doms)
    if confs:
        st.markdown("**Answer confidence over time**")
        st.line_chart({"confidence": confs})

# =========================== ACTIVITY (audit log) ========================= #
with tab_activity:
    st.markdown("### 🧾 Activity — audit log")
    st.caption("Every knowledge upload, question, and guardrail event is recorded "
               "here for this session.")
    aud = st.session_state.audit
    if aud:
        by = {}
        for a in aud:
            by[a["action"]] = by.get(a["action"], 0) + 1
        cc = st.columns(len(by) or 1)
        for i, (k, v) in enumerate(by.items()):
            cc[i % len(cc)].metric(k.replace("_", " ").title(), v)
        st.dataframe(aud, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download audit log (CSV)", data=_audit_csv(aud),
                           file_name="audit_log.csv", mime="text/csv")
    else:
        st.info("No activity yet — upload knowledge or ask a question in Overview.")

# =========================== TEST SUITES =================================== #
with tab_tests:
    st.markdown("### ✅ Test Suites")
    # system status
    st.markdown("#### 🩺 System status")
    if st.button("🔄 Refresh status"):
        st.session_state._sys = system_status()
    s = st.session_state.get("_sys") or system_status()
    cols = st.columns(4)
    cols[0].metric("LLM", s["llm"].get("backend", "—"))
    cols[1].metric("Vector DB", s["vector_db"].get("backend", "—"))
    cols[2].metric("Tracing", s["tracing"].get("provider", "—"))
    cols[3].metric("Azure Monitor", "on" if s["observability"].get("azure_monitor") else "off")

    st.divider()
    st.markdown("#### 🧪 Unit tests & coverage")
    if st.button("▶️ Run test suite"):
        with st.spinner("Running pytest…"):
            st.session_state._tests = run_test_suite(str(Path(__file__).resolve().parents[2]))
    tr = st.session_state.get("_tests")
    if tr and tr.get("ok"):
        t = tr["tests"]["totals"]
        a, b, c, d = st.columns(4)
        a.metric("Total", t["total"]); b.metric("Passed", t["passed"])
        c.metric("Failed", t["failed"] + t["errors"])
        d.metric("Coverage", f"{tr.get('coverage',{}).get('total_percent','?')}%")
    elif tr:
        st.error(tr.get("error", "Test run failed"))

    st.divider()
    st.markdown("#### 🚀 Load test (end-to-end)")
    st.caption("Phased per-endpoint latency & sustained RPS vs budgets "
               "(health <50ms, retrieve <150ms, end-to-end p95 <5s).")
    lc1, lc2, lc3 = st.columns(3)
    base = lc1.text_input("Target API base URL",
                          value=os.getenv("SELF_API_BASE", "http://127.0.0.1:8001"))
    users = lc2.slider("Concurrent users", 1, 50, 10)
    dur = lc3.slider("Duration (s)", 3, 60, 8)
    if st.button("▶️ Run load test"):
        with st.spinner(f"Load testing {base}…"):
            st.session_state._load = run_load_test(base, users, dur)
    lr = st.session_state.get("_load")
    if lr and lr.get("ok"):
        agg = lr["aggregate"]
        a, b, c = st.columns(3)
        a.metric("🔥 Peak RPS", agg["peak_rps"]); b.metric("Requests", agg["total_requests"])
        c.metric("Result", "PASS ✅" if agg["all_pass"] else "FAIL ❌")
        st.dataframe([{"Endpoint": r["endpoint"], "RPS": r["rps"], "p50 (ms)": r["p50_ms"],
                       "p95 (ms)": r["p95_ms"], "Budget (ms)": r["budget_ms"],
                       "Status": r["status"]} for r in lr["endpoints"]],
                     use_container_width=True, hide_index=True)

st.markdown("<hr><p style='text-align:center;color:#5C6B82'>"
            "<b>ProposalForge Agent</b> · LangGraph agentic RAG · Claude/Groq · Pinecone · "
            "Azure Monitor</p>", unsafe_allow_html=True)
