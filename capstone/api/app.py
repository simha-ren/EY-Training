"""ProposalForge - Versatile Multi-Domain RAG Copilot (Streamlit frontend).

Implements the doc's interface: a single chat with a left rail to pin a domain
or stay on auto-route, citation chips on answers, and a three-layer autosuggest
(domain confirmation chips, query type-ahead, follow-up suggestions).
"""
from __future__ import annotations

import os

import streamlit as st

from core.config import llm_settings
from core.engine import Engine
from core.llm import LLMClient

st.set_page_config(page_title="ProposalForge", page_icon="🧭", layout="wide")

DOMAIN_COLORS = {
    "finance": "#1f6f6b",
    "healthcare": "#2e5cb8",
    "agriculture": "#9a7b1f",
}

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1180px;}
.pf-title {font-size: 1.9rem; font-weight: 800; letter-spacing:-.02em; margin-bottom:.1rem;}
.pf-sub {color:#5b6660; font-size:.95rem; margin-bottom:1.1rem;}
.pf-badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem;
  font-weight:700; color:#fff; letter-spacing:.02em; vertical-align:middle;}
.pf-cite {display:inline-flex; gap:.35rem; align-items:center; background:#eef3f2;
  border:1px solid #d7e0dd; border-radius:8px; padding:6px 10px; margin:3px 6px 3px 0;
  font-size:.8rem; color:#1c2321;}
.pf-cite b {color:#1f6f6b;}
.pf-route {font-size:.78rem; color:#6b746f; margin:.1rem 0 .5rem 0;}
.pf-disc {font-size:.78rem; color:#8a5a17; background:#fdf6e9; border:1px solid #f0e2c4;
  padding:8px 12px; border-radius:8px; margin-top:.5rem;}
.pf-conf-wrap {height:7px; background:#e7e4dc; border-radius:4px; overflow:hidden; margin:.2rem 0 .6rem 0;}
.pf-conf-bar {height:7px; border-radius:4px;}
.stChatMessage {border-radius:12px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------- engine ---
@st.cache_resource(show_spinner="Indexing the three-domain knowledge base...")
def get_engine() -> Engine:
    return Engine()


engine = get_engine()
DOMAINS = engine.domains

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pin" not in st.session_state:
    st.session_state.pin = "auto"
if "pending_submit" not in st.session_state:
    st.session_state.pending_submit = None  # (query, confirmed_domain)


def domain_badge(key: str) -> str:
    cfg = DOMAINS[key]
    color = DOMAIN_COLORS.get(key, "#444")
    return f'<span class="pf-badge" style="background:{color}">{cfg.emoji} {cfg.label}</span>'


def queue_submit(query: str, confirmed_domain=None):
    st.session_state.pending_submit = (query, confirmed_domain)


# --------------------------------------------------------------- sidebar ---
with st.sidebar:
    st.markdown("### 🧭 Domain rail")
    pin_options = ["auto"] + list(DOMAINS.keys())
    labels = {"auto": "🔀 Auto-route"} | {k: f"{DOMAINS[k].emoji} {DOMAINS[k].label}" for k in DOMAINS}
    st.session_state.pin = st.radio(
        "Routing", pin_options, format_func=lambda k: labels[k],
        index=pin_options.index(st.session_state.pin), label_visibility="collapsed",
    )
    st.caption("Auto-route detects the domain per message. Pin one to force it.")

    st.divider()
    st.markdown("### 📈 Knowledge base")
    stats = engine.stats()
    for k in DOMAINS:
        st.markdown(
            f"{domain_badge(k)} &nbsp; **{stats.get(k, 0)}** chunks",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("### ➕ Add knowledge")
    up = st.file_uploader("Upload .md / .txt / .pdf", type=["md", "txt", "pdf"],
                          label_visibility="collapsed")
    up_domain = st.selectbox("Index into domain", list(DOMAINS.keys()),
                             format_func=lambda k: DOMAINS[k].label)
    if up is not None and st.button("Ingest document", use_container_width=True):
        n = engine.add_document(up.getvalue(), up.name, up_domain)
        st.success(f"Ingested '{up.name}' → {n} chunks into {DOMAINS[up_domain].label}.")

    st.divider()
    st.markdown("### ⚙️ Model")
    online = engine.llm.online
    st.caption(("🟢 LLM connected — composed answers" if online
                else "⚪ Offline mode — grounded extractive answers (no key needed)"))
    with st.expander("Connect an LLM (optional)"):
        provider = st.selectbox("Provider", ["openai", "azure"])
        key = st.text_input("API key", type="password")
        model = st.text_input("Model / deployment", value="gpt-4o-mini")
        endpoint = st.text_input("Azure endpoint (azure only)", value="")
        if st.button("Apply", use_container_width=True):
            os.environ["PF_LLM_PROVIDER"] = provider
            os.environ["PF_LLM_API_KEY"] = key
            os.environ["PF_LLM_MODEL"] = model
            os.environ["PF_AZURE_ENDPOINT"] = endpoint
            engine.llm = LLMClient(llm_settings())
            st.success("LLM settings applied." if engine.llm.online else "Still offline — check the key.")
            st.rerun()


# --------------------------------------------------------------- header ---
st.markdown('<div class="pf-title">ProposalForge</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="pf-sub">One copilot, three domains, zero guesswork — '
    'finance · healthcare · agriculture, auto-routed and citation-backed.</div>',
    unsafe_allow_html=True,
)

tab_chat, tab_kb, tab_eval, tab_arch = st.tabs(
    ["💬 Chat", "📚 Knowledge base", "📊 Evaluation", "🏗️ Architecture"]
)


# ----------------------------------------------------------- renderers ---
def render_route(route):
    if not route or route.domain is None:
        return
    color = DOMAIN_COLORS.get(route.domain, "#444")
    pct = int(round(route.confidence * 100))
    st.markdown(
        f'<div class="pf-route">Routed to {domain_badge(route.domain)} '
        f'· confidence {pct}% · {route.mode}</div>'
        f'<div class="pf-conf-wrap"><div class="pf-conf-bar" '
        f'style="width:{pct}%;background:{color}"></div></div>',
        unsafe_allow_html=True,
    )


def render_citations(citations):
    if not citations:
        return
    chips = "".join(
        f'<span class="pf-cite"><b>[{c.n}]</b> {c.source} · {c.section}</span>'
        for c in citations
    )
    st.markdown(chips, unsafe_allow_html=True)
    with st.expander(f"Show {len(citations)} source snippet(s)"):
        for c in citations:
            st.markdown(f"**[{c.n}] {c.source}** — _{c.section}_")
            st.caption(c.snippet + "…")


def render_assistant(msg):
    render_route(msg.get("route"))
    status = msg["status"]
    if status == "answer":
        st.markdown(msg["text"])
        render_citations(msg["citations"])
        if msg.get("disclaimer"):
            st.markdown(f'<div class="pf-disc">⚠️ {msg["disclaimer"]}</div>', unsafe_allow_html=True)
        if msg.get("cross_hint"):
            ch = msg["cross_hint"]
            st.info("🔀 " + ch["text"])
        if msg.get("follow_ups"):
            st.caption("Suggested follow-ups")
            cols = st.columns(len(msg["follow_ups"]))
            for col, q in zip(cols, msg["follow_ups"]):
                col.button(q, key=f"fu_{msg['idx']}_{q}", use_container_width=True,
                           on_click=queue_submit, args=(q,))
    elif status in ("clarify", "refuse"):
        st.markdown(msg["text"])
        if msg.get("disclaimer"):
            st.markdown(f'<div class="pf-disc">⚠️ {msg["disclaimer"]}</div>', unsafe_allow_html=True)
    elif status == "ask_domain":
        st.markdown(msg["text"])
        opts = msg["suggestions"] or list(DOMAINS.keys())
        cols = st.columns(len(opts))
        for col, d in zip(cols, opts):
            col.button(f"{DOMAINS[d].emoji} {DOMAINS[d].label}",
                       key=f"chip_{msg['idx']}_{d}", use_container_width=True,
                       on_click=queue_submit, args=(msg["origin_query"], d))


# --------------------------------------------------------------- chat ---
with tab_chat:
    # render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["text"])
            else:
                render_assistant(msg)

    # starter / type-ahead suggestions when no input yet
    if not st.session_state.messages:
        st.caption("Try one of these — or ask your own:")
        active = None if st.session_state.pin == "auto" else st.session_state.pin
        starters = engine.typeahead("", active)[:6]
        cols = st.columns(2)
        for i, q in enumerate(starters):
            cols[i % 2].button(q, key=f"start_{i}", use_container_width=True,
                               on_click=queue_submit, args=(q,))

    prompt = st.chat_input("Ask about finance, healthcare or agriculture…")
    if prompt:
        queue_submit(prompt)


# ----------------------------------------------- process queued submit ---
def process(query: str, confirmed_domain):
    st.session_state.messages.append({"role": "user", "text": query})
    pin = None if st.session_state.pin == "auto" else st.session_state.pin
    turn = engine.ask(query, pinned=pin, confirmed_domain=confirmed_domain)
    idx = len(st.session_state.messages)
    msg = {
        "role": "assistant", "idx": idx, "status": turn.status,
        "route": turn.route, "text": turn.message, "origin_query": query,
        "suggestions": turn.route.suggestions if turn.route else [],
        "disclaimer": turn.disclaimer, "citations": [], "follow_ups": [],
        "cross_hint": turn.cross_hint,
    }
    if turn.status == "answer" and turn.answer:
        msg["text"] = turn.answer.text
        msg["citations"] = turn.answer.citations
        msg["follow_ups"] = turn.follow_ups
    st.session_state.messages.append(msg)


if st.session_state.pending_submit is not None:
    q, cd = st.session_state.pending_submit
    st.session_state.pending_submit = None
    process(q, cd)
    st.rerun()


# --------------------------------------------------------- KB tab ---
with tab_kb:
    st.markdown("#### Per-domain knowledge namespaces")
    st.caption("Each domain is isolated — a finance query never retrieves agriculture chunks.")
    for k in DOMAINS:
        cfg = DOMAINS[k]
        with st.expander(f"{cfg.emoji} {cfg.label} — {engine.stats().get(k,0)} chunks"):
            srcs = sorted({c.source for c in engine.store.chunks if c.domain == k})
            st.write("**Sources:** " + ", ".join(srcs))
            st.write("**Guardrail:** " + cfg.guardrails.get("disclaimer", "—"))


# --------------------------------------------------------- eval tab ---
with tab_eval:
    st.markdown("#### RAGAS-style evaluation")
    st.caption("Offline metric proxies on a golden set (doc Section 7). "
               "Targets: routing ≥0.95 · context recall ≥0.90 · citation coverage ≥0.95.")
    if st.button("Run evaluation"):
        from eval.evaluate import run_eval
        res = run_eval(engine)
        s = res["summary"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Routing accuracy", f"{s['routing_accuracy']:.0%}")
        c2.metric("Retrieval hit@k", f"{s['retrieval_hit@k']:.0%}")
        c3.metric("Context recall", f"{s['context_recall']:.0%}")
        c4.metric("Citation coverage", f"{s['citation_coverage']:.0%}")
        st.dataframe(res["rows"], use_container_width=True)


# --------------------------------------------------------- arch tab ---
with tab_arch:
    st.markdown("#### Request-time flow (doc Sections 2–3)")
    st.code(
        "message\n"
        "  ──▶ Domain Router  (keyword + TF-IDF centroid → domain + confidence)\n"
        "        ├─ confident ──────────────▶ retrieve\n"
        "        ├─ ambiguous ─▶ autosuggest chips ─▶ (user confirms) ─▶ retrieve\n"
        "        └─ unknown ───▶ ask user to pick a domain\n"
        "  ──▶ Guardrails     (refuse out-of-scope · gap-detect → clarify)\n"
        "  ──▶ Retrieval      (hybrid search within the domain namespace + re-rank)\n"
        "  ──▶ Composer       (grounded answer + inline [n] citations · PII redaction)\n"
        "  ──▶ Suggest        (follow-ups · cross-domain hop hints)\n",
        language="text",
    )
    st.markdown("#### Five agents (doc Section 3)")
    st.table({
        "Agent": ["Orchestrator", "Reasoning/Router", "Retrieval", "Generation", "Doc Normalizer"],
        "Maps to": ["engine.ask loop", "router.py", "store.retrieve", "generation.compose", "ingestion.py"],
    })
