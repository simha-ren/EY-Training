import streamlit as st
import json
import requests
import time
from groq import Groq

# Optional plotly for advanced charts
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="STM + LTM Budget Planner",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Domain definitions (from the STM / LTM table) ──────────────────────────────
DOMAINS = [
    {"key": "commute",     "name": "Commute",     "icon": "🚆",
     "stm_label": "Current transport funding requests",
     "ltm_label": "Historical infrastructure spending"},
    {"key": "defence",     "name": "Defence",     "icon": "🛡️",
     "stm_label": "Current procurement requests",
     "ltm_label": "Multi-year defence strategy"},
    {"key": "agriculture", "name": "Agriculture", "icon": "🌾",
     "stm_label": "Current crop support needs",
     "ltm_label": "Past subsidy and yield trends"},
    {"key": "government",  "name": "Government",  "icon": "🏛️",
     "stm_label": "Current department demands",
     "ltm_label": "Historical operational expenditure"},
]

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: radial-gradient(1200px 600px at 10% -10%, #1e3a5f 0%, transparent 50%),
                linear-gradient(135deg, #0b1020, #14182e, #1a1530);
    min-height: 100vh;
}
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.04);
    border-right: 1px solid rgba(255,255,255,0.08);
}
[data-testid="stHeader"] { background: transparent; }

.glass-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 14px;
    backdrop-filter: blur(10px);
}
.agent-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 14px;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
}
.agent-card.active { border-color: rgba(99,179,237,0.6); box-shadow: 0 0 24px rgba(99,179,237,0.18); background: rgba(99,179,237,0.06); }
.agent-card.done   { border-color: rgba(72,187,120,0.5); box-shadow: 0 0 16px rgba(72,187,120,0.12); background: rgba(72,187,120,0.05); }
.agent-card.error  { border-color: rgba(252,129,74,0.5); background: rgba(252,129,74,0.05); }

.agent-header { display:flex; align-items:center; gap:12px; margin-bottom:12px; }
.agent-icon {
    font-size:26px; width:44px; height:44px; display:flex; align-items:center;
    justify-content:center; border-radius:12px; background:rgba(255,255,255,0.06);
}
.agent-name { font-size:15px; font-weight:700; color:#e2e8f0; letter-spacing:0.5px; }
.agent-role { font-size:11px; color:#718096; text-transform:uppercase; letter-spacing:1px; }

.status-badge { margin-left:auto; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:600; letter-spacing:0.5px; }
.badge-waiting  { background:rgba(113,128,150,0.2); color:#718096; }
.badge-thinking { background:rgba(99,179,237,0.2);  color:#63b3ed; }
.badge-done     { background:rgba(72,187,120,0.2);  color:#48bb78; }
.badge-error    { background:rgba(252,129,74,0.2);  color:#fc814a; }

.agent-output {
    background:rgba(0,0,0,0.25); border-radius:10px; padding:14px; font-size:13px;
    color:#cbd5e0; line-height:1.7; max-height:300px; overflow-y:auto;
    white-space:pre-wrap; border:1px solid rgba(255,255,255,0.06);
}
.step-pill {
    display:inline-block; background:rgba(159,122,234,0.15);
    border:1px solid rgba(159,122,234,0.3); border-radius:20px;
    padding:4px 14px; margin:4px 4px 4px 0; font-size:12px; color:#d6bcfa;
}
.domain-tag {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(99,179,237,0.10); border:1px solid rgba(99,179,237,0.25);
    border-radius:10px; padding:6px 12px; font-size:13px; color:#bee3f8; font-weight:600;
}
.mem-tag-stm { color:#fbbf24; font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; }
.mem-tag-ltm { color:#34d399; font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; }

.pipeline-row { display:flex; align-items:center; justify-content:center; gap:0; margin:6px 0; }
.pipeline-node { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:8px 14px; font-size:12px; color:#a0aec0; font-weight:600; }
.pipeline-arrow { color:#4a5568; font-size:16px; padding:0 5px; }

.alloc-card {
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);
    border-radius:14px; padding:16px; margin-bottom:12px;
}
.alloc-head { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.alloc-name { font-size:15px; font-weight:700; color:#e2e8f0; }
.alloc-amt  { margin-left:auto; font-size:18px; font-weight:800; color:#90cdf4; }
.alloc-bar-track { background:rgba(255,255,255,0.06); border-radius:8px; height:10px; overflow:hidden; margin:6px 0 10px; }
.alloc-bar-fill  { height:10px; border-radius:8px; background:linear-gradient(90deg,#667eea,#764ba2); }
.alloc-rationale { font-size:12.5px; color:#a0aec0; line-height:1.6; }
.alloc-influence { font-size:11.5px; color:#718096; margin-top:6px; line-height:1.6; }

.final-box {
    background:linear-gradient(135deg, rgba(72,187,120,0.08), rgba(56,178,172,0.08));
    border:1px solid rgba(72,187,120,0.3); border-radius:16px; padding:22px; margin-top:8px;
}
.final-title { color:#48bb78; font-size:14px; font-weight:700; margin-bottom:12px; letter-spacing:0.5px; }

.stTextArea textarea, [data-testid="stTextArea"] textarea {
    background:rgba(255,255,255,0.07) !important; border:1px solid rgba(255,255,255,0.18) !important;
    border-radius:12px !important; color:#f0f4f8 !important; font-size:13px !important;
    caret-color:#63b3ed !important; -webkit-text-fill-color:#f0f4f8 !important;
}
.stTextArea textarea::placeholder, [data-testid="stTextArea"] textarea::placeholder {
    color:rgba(160,174,192,0.6) !important; -webkit-text-fill-color:rgba(160,174,192,0.6) !important;
}
.stTextArea textarea:focus, [data-testid="stTextArea"] textarea:focus {
    border-color:rgba(99,179,237,0.6) !important; box-shadow:0 0 0 2px rgba(99,179,237,0.2) !important;
}
.stNumberInput input, [data-testid="stNumberInput"] input {
    background:rgba(255,255,255,0.07) !important; color:#f0f4f8 !important;
    border:1px solid rgba(255,255,255,0.18) !important; border-radius:10px !important;
    -webkit-text-fill-color:#f0f4f8 !important;
}
.stButton > button {
    background:linear-gradient(135deg,#667eea,#764ba2) !important; color:white !important;
    border:none !important; border-radius:10px !important; padding:10px 24px !important;
    font-weight:600 !important; font-size:14px !important; transition:all 0.2s !important;
}
.stButton > button:hover { transform:translateY(-1px) !important; box-shadow:0 6px 20px rgba(102,126,234,0.4) !important; }
.metric-card { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px; text-align:center; }
.metric-value { font-size:24px; font-weight:700; color:#e2e8f0; }
.metric-label { font-size:11px; color:#718096; text-transform:uppercase; letter-spacing:1px; margin-top:4px; }
.groq-badge { display:inline-flex; align-items:center; gap:6px; background:rgba(249,115,22,0.12); border:1px solid rgba(249,115,22,0.3); border-radius:20px; padding:4px 12px; font-size:11px; color:#fb923c; font-weight:600; }
.stTabs [data-baseweb="tab-list"] { gap:6px; }
.stTabs [data-baseweb="tab"] {
    background:rgba(255,255,255,0.04); border-radius:10px 10px 0 0; color:#a0aec0;
    padding:8px 16px; border:1px solid rgba(255,255,255,0.08);
}
.stTabs [aria-selected="true"] { background:rgba(99,179,237,0.12); color:#e2e8f0 !important; }
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.15); border-radius:4px; }
</style>
""", unsafe_allow_html=True)

# ── Groq client ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_client(api_key: str, backend: str = "Groq", hf_key: str = None):
    """Return a client object for the selected backend.

    - For Groq: returns a Groq client or None when api_key missing.
    - For HuggingFace: returns a small dict {'backend':'hf','key':hf_key}.
    """
    if backend and backend.startswith("HuggingFace"):
        return {"backend": "hf", "key": hf_key}
    # default: Groq
    if not api_key:
        return None
    return Groq(api_key=api_key)
def call_hf(api_key: str, prompt: str, model: str = "gpt2", max_tokens: int = 2000) -> str:
    """Call the Hugging Face Inference API (text-generation) and return generated text.

    Note: requires a valid HF Inference API key and a compatible model name.
    """
    if not api_key:
        raise RuntimeError("Missing Hugging Face API key")
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    try:
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"HuggingFace API error: {e} - {resp.text}")
    data = resp.json()
    # HF returns either a list of dicts with 'generated_text' or other structured outputs
    if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
        return data[0]["generated_text"]
    # Some models return a plain dict or text
    if isinstance(data, dict) and "generated_text" in data:
        return data["generated_text"]
    # Fallback: stringify
    return str(data)

def call_groq(client, system_prompt: str, user_message: str,
              model: str = "llama-3.3-70b-versatile", max_tokens: int = 2000) -> str:
    # client may be None (demo), a Groq client, or a dict for HF backend
    if client is None:
        raise RuntimeError("No client provided to call_groq")
    # Hugging Face backend
    if isinstance(client, dict) and client.get("backend") == "hf":
        prompt = system_prompt + "\n\n" + user_message
        return call_hf(client.get("key"), prompt, model=model, max_tokens=max_tokens)
    # Groq client
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content

def parse_json(raw: str):
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.lstrip("`")
        if clean.lower().startswith("json"):
            clean = clean[4:]
        clean = clean.rstrip("`").strip()
    # grab outermost JSON object if extra text snuck in
    start, end = clean.find("{"), clean.rfind("}")
    if start != -1 and end != -1:
        clean = clean[start:end + 1]
    return json.loads(clean)

# ── Helpers ────────────────────────────────────────────────────────────────────
def build_context(total_budget, currency, fiscal_year, region, inputs):
    """Assemble the STM + LTM context block fed to the Planner."""
    lines = [
        f"FISCAL YEAR: {fiscal_year}",
        f"REGION / CONTEXT: {region or 'General'}",
        f"TOTAL BUDGET AVAILABLE: {total_budget} {currency}",
        "",
        "DOMAIN MEMORY (STM = current-year context, LTM = historical knowledge):",
    ]
    for d in DOMAINS:
        v = inputs[d["key"]]
        lines.append(f"\n— {d['name']} —")
        lines.append(f"  [STM] {d['stm_label']}: requested {v['stm_request']} {currency}. "
                     f"Notes: {v['stm_notes'] or 'none'}")
        lines.append(f"  [LTM] {d['ltm_label']}: historical baseline {v['ltm_baseline']} {currency}. "
                     f"Trends/policy: {v['ltm_notes'] or 'none'}")
    return "\n".join(lines)

def normalize_allocations(allocations, total_budget):
    """Rescale amounts so they sum exactly to the total budget; recompute %."""
    if not allocations:
        return allocations
    s = sum(max(0, float(a.get("amount", 0))) for a in allocations)
    if s <= 0:
        even = total_budget / len(allocations)
        for a in allocations:
            a["amount"] = round(even, 2)
    else:
        factor = total_budget / s
        for a in allocations:
            a["amount"] = round(max(0, float(a.get("amount", 0))) * factor, 2)
    for a in allocations:
        a["percentage"] = round(100 * a["amount"] / total_budget, 1) if total_budget else 0
    return allocations

# ── Agents ─────────────────────────────────────────────────────────────────────
def planner_agent(client, context, total_budget, currency, model):
    system = f"""You are a Budget Planner Agent for a government / organisational annual budget.
You combine Short-Term Memory (STM = the current year's requests and active planning context)
with Long-Term Memory (LTM = historical budgets, multi-year strategy, subsidy trends, regulations
and accumulated domain knowledge) to produce a REALISTIC annual budget allocation across all domains.

Rules:
- The allocations MUST collectively use the full total budget of {total_budget} {currency}.
- Balance current requests (STM) against historical patterns and strategy (LTM). Do not blindly
  fund the largest request; justify trade-offs.
- For each domain explain how STM and LTM each influenced the number.

Respond ONLY with valid JSON, no markdown fences:
{{
  "strategy": "one short paragraph on the overall allocation philosophy combining STM + LTM",
  "allocations": [
    {{
      "domain": "Commute",
      "amount": number,
      "percentage": number,
      "stm_influence": "how the current-year request shaped this",
      "ltm_influence": "how history/strategy shaped this",
      "rationale": "one or two sentences"
    }}
  ],
  "assumptions": ["assumption 1", "assumption 2"]
}}
Include exactly these domains: Commute, Defence, Agriculture, Government."""
    # If no Groq client (demo mode), produce a simple heuristic allocation
    if client is None:
        scores = []
        for d in DOMAINS:
            key = d["key"]
            stm_req = float(inputs.get(key, {}).get("stm_request", 0) or 0)
            ltm_base = float(inputs.get(key, {}).get("ltm_baseline", 0) or 0)
            score = stm_req * 2.0 + ltm_base * 1.0
            scores.append((d["name"], score))
        total_score = sum(s for _, s in scores) or 1.0
        allocs = []
        for name, s in scores:
            amt = round(total_budget * (s / total_score), 2)
            allocs.append({
                "domain": name,
                "amount": amt,
                "percentage": round(100 * amt / total_budget, 1) if total_budget else 0,
                "stm_influence": "Demo: based on current request",
                "ltm_influence": "Demo: based on historical baseline",
                "rationale": "Auto-generated demo allocation combining STM+LTM",
            })
        plan = {"strategy": "Demo allocation combining STM + LTM",
                "allocations": allocs,
                "assumptions": ["Demo run; no Groq API used."]}
        plan["allocations"] = normalize_allocations(plan.get("allocations", []), total_budget)
        return plan

    raw = call_groq(client, system, context, model=model, max_tokens=2200)
    try:
        plan = parse_json(raw)
    except Exception:
        even = total_budget / len(DOMAINS)
        plan = {
            "strategy": "Fallback even split — planner response could not be parsed.",
            "allocations": [{"domain": d["name"], "amount": even, "percentage": 25,
                             "stm_influence": "n/a", "ltm_influence": "n/a",
                             "rationale": "Even fallback split."} for d in DOMAINS],
            "assumptions": ["Planner output unparseable; used even split."],
        }
    plan["allocations"] = normalize_allocations(plan.get("allocations", []), total_budget)
    return plan

def executor_agent(client, context, plan, currency, model):
    alloc_text = "\n".join(
        f"- {a['domain']}: {a['amount']} {currency} ({a['percentage']}%)"
        for a in plan.get("allocations", [])
    )
    system = """You are a Budget Executor Agent. Given the approved allocation, produce a detailed,
well-structured implementation breakdown for EACH domain: what the money funds, priority programmes,
phasing across the year, and how it honours both current needs (STM) and long-term strategy (LTM).
Use clear markdown with a short section per domain. Be specific and realistic."""
    if client is None:
        parts = [f"Implementation plan for {a['domain']}: Allocate {a['amount']} {currency}."
                 f" Priorities: {a.get('rationale','')}." for a in plan.get('allocations', [])]
        return "\n\n".join(parts)
    return call_groq(
        client, system,
        f"CONTEXT:\n{context}\n\nAPPROVED ALLOCATION:\n{alloc_text}\n\nStrategy: {plan.get('strategy','')}",
        model=model, max_tokens=2500,
    )

def validator_agent(client, context, plan, execution, total_budget, currency, model):
    alloc_text = "\n".join(
        f"- {a['domain']}: {a['amount']} {currency} ({a['percentage']}%)"
        for a in plan.get("allocations", [])
    )
    system = """You are a Budget Validator Agent. Review the allocation and implementation plan for
realism, balance between STM (current needs) and LTM (historical strategy), and risk.
Respond ONLY with valid JSON, no markdown fences:
{
  "passed": true or false,
  "score": number 0-100,
  "balance_comment": "one line on how well STM and LTM were balanced",
  "strengths": ["strength 1", "strength 2"],
  "risks": ["risk 1", "risk 2"],
  "summary": "one paragraph quality summary"
}"""
    if client is None:
        # Simple demo validator
        score = 80
        return {"passed": True, "score": score, "balance_comment": "Demo: reasonable balance between STM and LTM",
                "strengths": ["Produces allocations"], "risks": ["Demo heuristics only"],
                "summary": "Demo validation: allocations look reasonable for a demo run."}
    raw = call_groq(
        client, system,
        f"TOTAL BUDGET: {total_budget} {currency}\n\nCONTEXT:\n{context}\n\n"
        f"ALLOCATION:\n{alloc_text}\n\nIMPLEMENTATION:\n{execution[:3000]}",
        model=model,
    )
    try:
        return parse_json(raw)
    except Exception:
        return {"passed": True, "score": 75, "balance_comment": "n/a",
                "strengths": ["Plan produced"], "risks": ["Validator output unparseable"],
                "summary": raw[:300]}

# ── Session state ──────────────────────────────────────────────────────────────
for key in ["history", "plan", "execution", "validation", "elapsed", "ctx_meta"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "history" else None

# Demo callback: set example values (safe to call from any button callback)
def _start_demo():
    st.session_state['demo'] = True
    st.session_state['api_key'] = ""
    st.session_state['total_budget'] = 5000.0
    st.session_state['currency'] = "₹"
    st.session_state['fiscal_year'] = "2026-27"
    st.session_state['region'] = "State of Demo"
    for i, d in enumerate(DOMAINS):
        st.session_state[f"{d['key']}_stm_req"] = 500 + i * 200
        st.session_state[f"{d['key']}_stm_notes"] = f"Demo STM notes for {d['name']}"
        st.session_state[f"{d['key']}_ltm_base"] = 300 + i * 150
        st.session_state[f"{d['key']}_ltm_notes"] = f"Demo LTM notes for {d['name']}"
    # updating session_state in the callback will trigger a rerun

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏦 STM + LTM Budget Planner")
    st.markdown("<div class='groq-badge'>⚡ Planner</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:#718096;font-size:12px;margin:8px 0 16px'>"
                "Planner → Executor → Validator</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**🔌 Backend**")
    backend_choice = st.selectbox("Backend", label_visibility="collapsed", key="backend_choice",
                                  options=["Groq", "HuggingFace (Inference API)"], index=1)

    # Groq API key (optional if using Hugging Face)
    st.markdown("**🔑 Groq API Key (optional)**")
    api_key = st.text_input("Groq API Key", type="password",
                            placeholder="gsk_…", label_visibility="collapsed", key="api_key")

    # Hugging Face key shown only if HF backend selected
    hf_api_key = None
    if backend_choice and backend_choice.startswith("HuggingFace"):
        st.markdown("**🔑 Hugging Face API Key**")
        hf_api_key = st.text_input("Hugging Face API Key", type="password",
                                   placeholder="hf_…", label_visibility="collapsed", key="hf_api_key")

    st.markdown("**🧠 Model**")
    # Backend-specific model widget keys to avoid widget type mismatches
    if backend_choice and backend_choice.startswith("HuggingFace"):
        model_choice_hf = st.text_input("HF Model (e.g. gpt2 or namespace/model)", value="gpt2",
                                         key="model_choice_hf", label_visibility="collapsed")
    else:
        model_choice_groq = st.selectbox(
            "Groq Model", label_visibility="collapsed", key="model_choice_groq",
            options=["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                     "mixtral-8x7b-32768", "gemma2-9b-it"],
        )
    # (HF API key already collected above when HF selected)

    # Demo start moved to main UI (below run button)

    st.markdown("---")
    st.markdown("**💰 Budget Setup**")
    total_budget = st.number_input("Total annual budget", min_value=1.0,
                                    value=1000.0, step=50.0, key="total_budget")
    currency = st.selectbox("Currency", ["Cr ₹", "₹", "$", "€", "£", "units"], index=0, key="currency")
    fiscal_year = st.text_input("Fiscal year", value="2025-26", key="fiscal_year")
    region = st.text_input("Region / context", placeholder="e.g. National, State of …", key="region")

    st.markdown("---")
    st.markdown("**Pipeline**")
    st.markdown("""
<div class='pipeline-row'>
  <div class='pipeline-node'>🧠 Planner</div>
  <div class='pipeline-arrow'>→</div>
  <div class='pipeline-node'>⚙️ Executor</div>
  <div class='pipeline-arrow'>→</div>
  <div class='pipeline-node'>✅ Validator</div>
</div>""", unsafe_allow_html=True)

    st.markdown("**Memory model**")
    st.markdown("""<div style='font-size:12px;color:#718096;line-height:1.9'>
<span class='mem-tag-stm'>STM</span> &nbsp;current-year requests & active planning<br>
<span class='mem-tag-ltm'>LTM</span> &nbsp;historical budgets, trends, policy, strategy<br>
🧠 <b style='color:#a0aec0'>Planner</b> fuses both into a realistic allocation
</div>""", unsafe_allow_html=True)

    if st.session_state.history:
        st.markdown("---")
        st.markdown(f"**Run history ({len(st.session_state.history)})**")
        for h in reversed(st.session_state.history[-5:]):
            sc = h.get("score", "?")
            color = "#48bb78" if isinstance(sc, (int, float)) and sc >= 75 else "#fc814a"
            st.markdown(
                f"<div style='font-size:11px;color:#718096;padding:4px 0;"
                f"border-bottom:1px solid rgba(255,255,255,0.05)'>"
                f"<span style='color:{color};font-weight:700'>{sc}/100</span>"
                f" · FY {h['fy']} · {h['budget']}</div>", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("<h1 style='color:#e2e8f0;font-size:28px;font-weight:800;margin-bottom:4px'>"
            "🏦 Agentic Budget Allocation Planner</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#718096;font-size:14px;margin-bottom:8px'>"
            "Combining <span style='color:#fbbf24;font-weight:600'>STM</span> (current requests) + "
            "<span style='color:#34d399;font-weight:600'>LTM</span> (historical knowledge) across "
            "Commute · Defence · Agriculture · Government — powered by "
            "<span style='color:#fb923c;font-weight:600'>Groq</span></p>", unsafe_allow_html=True)

if st.session_state.get('demo'):
    st.markdown(
        "<div style='padding:10px;border-radius:12px;margin-bottom:12px;background:linear-gradient(90deg,#6b46c1,#b794f4);color:white;font-weight:700'>"
        "DEMO MODE — values prefilled for preview (no Groq API used)</div>", unsafe_allow_html=True)

backend_choice = st.session_state.get('backend_choice', 'Groq')
hf_key = st.session_state.get('hf_api_key')
if backend_choice.startswith("HuggingFace"):
    if not hf_key:
        st.warning("⚠️ Enter your Hugging Face API key in the sidebar to get started.")
    model_choice = st.session_state.get('model_choice_hf', 'gpt2')
else:
    if not st.session_state.get('api_key'):
        st.warning("⚠️ Enter your Groq API key in the sidebar to get started. Get one free at https://console.groq.com")
    model_choice = st.session_state.get('model_choice_groq', 'llama-3.3-70b-versatile')

# ── Domain inputs (tabs) ───────────────────────────────────────────────────────
st.markdown("<div class='glass-card'><b style='color:#e2e8f0'>📥 Domain Inputs</b>"
            "<span style='color:#718096;font-size:12px'> — provide STM (current year) and "
            "LTM (history) for each domain</span></div>", unsafe_allow_html=True)

inputs = {}
tabs = st.tabs([f"{d['icon']}  {d['name']}" for d in DOMAINS])
for tab, d in zip(tabs, DOMAINS):
    with tab:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<span class='mem-tag-stm'>● STM — {d['stm_label']}</span>",
                        unsafe_allow_html=True)
            stm_request = st.number_input(f"Current request ({currency})",
                                          min_value=0.0, value=0.0, step=10.0,
                                          key=f"{d['key']}_stm_req")
            stm_notes = st.text_area("Current-year context / justification",
                                     key=f"{d['key']}_stm_notes", height=110,
                                     placeholder="e.g. urgent fleet expansion, election-year priority…")
        with c2:
            st.markdown(f"<span class='mem-tag-ltm'>● LTM — {d['ltm_label']}</span>",
                        unsafe_allow_html=True)
            ltm_baseline = st.number_input(f"Historical baseline ({currency})",
                                           min_value=0.0, value=0.0, step=10.0,
                                           key=f"{d['key']}_ltm_base")
            ltm_notes = st.text_area("Historical trends / policy / strategy",
                                     key=f"{d['key']}_ltm_notes", height=110,
                                     placeholder="e.g. spend grew 8%/yr, 10-year modernisation plan…")
        inputs[d["key"]] = {"stm_request": stm_request, "stm_notes": stm_notes,
                            "ltm_baseline": ltm_baseline, "ltm_notes": ltm_notes}

col_btn, col_clear, _ = st.columns([2, 1, 6])
with col_btn:
    run_clicked = st.button("▶  Generate Budget Plan", use_container_width=True,
                            disabled=not (api_key or st.session_state.get('demo')))
with col_clear:
    if st.button("Clear", use_container_width=True):
        for k in ["plan", "execution", "validation", "elapsed", "ctx_meta"]:
            st.session_state[k] = None
        st.session_state['demo'] = False
        st.rerun()

# Move demo starter below the run/clear buttons so it's visually lower in the UI
if st.button("Start demo (prefill values)", key="start_demo_main", on_click=_start_demo,
             help="Populate example values and run without Groq API", use_container_width=False):
    pass

# Always show current total budget next to controls so it's visible after allocating
st.markdown(f"<div style='margin-top:8px;color:#a0aec0'>Total budget: <b style='color:#90cdf4'>{st.session_state.get('total_budget', total_budget)} {st.session_state.get('currency', currency)}</b></div>", unsafe_allow_html=True)

st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

# ── Agent card renderer ────────────────────────────────────────────────────────
def agent_card(col, icon, name, role, status="waiting", output="", steps=None):
    badge_map = {
        "waiting":  ("badge-waiting",  "● Waiting"),
        "thinking": ("badge-thinking", "⟳ Working…"),
        "done":     ("badge-done",     "✓ Done"),
        "error":    ("badge-error",    "✗ Error"),
    }
    card_cls = {"thinking": "active", "done": "done", "error": "error"}.get(status, "")
    badge_cls, badge_txt = badge_map.get(status, badge_map["waiting"])
    steps_html = "".join(f"<span class='step-pill'>{s}</span>" for s in steps) if steps else ""
    output_html = f"<div class='agent-output'>{output}</div>" if output else ""
    col.markdown(f"""
<div class='agent-card {card_cls}'>
  <div class='agent-header'>
    <div class='agent-icon'>{icon}</div>
    <div><div class='agent-name'>{name}</div><div class='agent-role'>{role}</div></div>
    <span class='status-badge {badge_cls}'>{badge_txt}</span>
  </div>
  {steps_html}{output_html}
</div>""", unsafe_allow_html=True)

# ── Initial idle state ─────────────────────────────────────────────────────────
if not run_clicked and st.session_state.plan is None:
    agent_card(col1, "🧠", "Planner Agent",   "Fuses STM + LTM → allocation")
    agent_card(col2, "⚙️", "Executor Agent",  "Detailed spend breakdown")
    agent_card(col3, "✅", "Validator Agent", "Scores realism & balance")

# ── Run pipeline ───────────────────────────────────────────────────────────────
# Allow running when either a Groq API key is provided or demo mode is active
if run_clicked and (api_key or st.session_state.get('demo')):
    client = get_client(api_key) if api_key else None
    context = build_context(total_budget, currency, fiscal_year, region, inputs)
    st.session_state.ctx_meta = {"currency": currency, "total": total_budget}
    start = time.time()

    # Planner
    agent_card(col1, "🧠", "Planner Agent", "Fuses STM + LTM → allocation", status="thinking")
    agent_card(col2, "⚙️", "Executor Agent", "Detailed spend breakdown")
    agent_card(col3, "✅", "Validator Agent", "Scores realism & balance")
    with st.spinner("🧠 Planner fusing STM + LTM…"):
        try:
            plan = planner_agent(client, context, total_budget, currency, model_choice)
        except Exception as e:
            # Show a friendly error and fall back to demo/local heuristics
            st.error(f"Groq API error: {e}. Falling back to demo mode.")
            st.session_state['demo'] = True
            client = None
            plan = planner_agent(None, context, total_budget, currency, model_choice)
    st.session_state.plan = plan
    agent_card(col1, "🧠", "Planner Agent", "Fuses STM + LTM → allocation", status="done",
               steps=[f"{a['domain']} {a['percentage']}%" for a in plan.get("allocations", [])],
               output=f"Strategy: {plan.get('strategy','')}")

    # Executor
    agent_card(col2, "⚙️", "Executor Agent", "Detailed spend breakdown", status="thinking")
    with st.spinner("⚙️ Executor drafting implementation…"):
        try:
            execution = executor_agent(client, context, plan, currency, model_choice)
        except Exception as e:
            st.error(f"Executor error: {e}. Falling back to demo executor.")
            st.session_state['demo'] = True
            execution = executor_agent(None, context, plan, currency, model_choice)
    st.session_state.execution = execution
    agent_card(col2, "⚙️", "Executor Agent", "Detailed spend breakdown", status="done",
               output=execution[:600] + ("…" if len(execution) > 600 else ""))

    # Validator
    agent_card(col3, "✅", "Validator Agent", "Scores realism & balance", status="thinking")
    with st.spinner("✅ Validator reviewing…"):
        try:
            validation = validator_agent(client, context, plan, execution,
                                         total_budget, currency, model_choice)
        except Exception as e:
            st.error(f"Validator error: {e}. Falling back to demo validator.")
            st.session_state['demo'] = True
            validation = validator_agent(None, context, plan, execution,
                                         total_budget, currency, model_choice)
    st.session_state.validation = validation
    score = validation.get("score", 0)
    val_out = (
        f"Score: {score}/100  {'✓ Passed' if validation.get('passed') else '✗ Needs work'}\n"
        f"Balance: {validation.get('balance_comment','')}\n\n"
        "Strengths:\n" + "\n".join(f"  • {s}" for s in validation.get("strengths", [])) +
        "\n\nRisks:\n" + "\n".join(f"  • {r}" for r in validation.get("risks", []))
    )
    agent_card(col3, "✅", "Validator Agent", "Scores realism & balance", status="done",
               output=val_out)

    st.session_state.elapsed = round(time.time() - start, 1)
    st.session_state.history.append({"fy": fiscal_year, "budget": f"{total_budget} {currency}",
                                     "score": score})

# ── Restore after rerun ────────────────────────────────────────────────────────
elif st.session_state.plan and not run_clicked:
    plan = st.session_state.plan
    execution = st.session_state.execution or ""
    validation = st.session_state.validation or {}
    score = validation.get("score", 0)
    val_out = (
        f"Score: {score}/100  {'✓ Passed' if validation.get('passed') else '✗ Needs work'}\n"
        f"Balance: {validation.get('balance_comment','')}\n\n"
        "Strengths:\n" + "\n".join(f"  • {s}" for s in validation.get("strengths", [])) +
        "\n\nRisks:\n" + "\n".join(f"  • {r}" for r in validation.get("risks", []))
    )
    agent_card(col1, "🧠", "Planner Agent", "Fuses STM + LTM → allocation", status="done",
               steps=[f"{a['domain']} {a['percentage']}%" for a in plan.get("allocations", [])],
               output=f"Strategy: {plan.get('strategy','')}")
    agent_card(col2, "⚙️", "Executor Agent", "Detailed spend breakdown", status="done",
               output=execution[:600] + ("…" if len(execution) > 600 else ""))
    agent_card(col3, "✅", "Validator Agent", "Scores realism & balance", status="done",
               output=val_out)

# ── Results: metrics + charts + allocation cards ───────────────────────────────
if st.session_state.plan:
    plan = st.session_state.plan
    validation = st.session_state.validation or {}
    meta = st.session_state.ctx_meta or {"currency": currency, "total": total_budget}
    cur, tot = meta["currency"], meta["total"]
    allocs = plan.get("allocations", [])
    score = validation.get("score", 0)
    score_color = "#48bb78" if score >= 75 else "#f6ad55" if score >= 50 else "#fc814a"

    # Metrics
    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    top = max(allocs, key=lambda a: a["amount"]) if allocs else {"domain": "—"}
    for col, val, label, color in [
        (m1, f"{tot} {cur}", "Total budget", "#90cdf4"),
        (m2, f"{score}/100", "Realism score", score_color),
        (m3, top["domain"], "Largest allocation", "#b794f4"),
        (m4, f"{st.session_state.elapsed}s" if st.session_state.elapsed else "—", "Total time", "#63b3ed"),
    ]:
        col.markdown(f"<div class='metric-card'><div class='metric-value' "
                     f"style='color:{color}'>{val}</div><div class='metric-label'>{label}"
                     f"</div></div>", unsafe_allow_html=True)

    # Charts
    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)
    names = [a["domain"] for a in allocs]
    amounts = [a["amount"] for a in allocs]
    palette = ["#667eea", "#48bb78", "#fbbf24", "#fc814a", "#38b2ac", "#b794f4"]

    if HAS_PLOTLY and allocs:
        with cc1:
            st.markdown("<div style='color:#a0aec0;font-size:13px;font-weight:600;"
                        "margin-bottom:4px'>Allocation share</div>", unsafe_allow_html=True)
            donut = go.Figure(go.Pie(labels=names, values=amounts, hole=0.58,
                                     marker=dict(colors=palette[:len(names)]),
                                     textinfo="label+percent"))
            donut.update_layout(showlegend=False, height=320,
                                margin=dict(t=10, b=10, l=10, r=10),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#cbd5e0"))
            st.plotly_chart(donut, use_container_width=True)
        with cc2:
            st.markdown("<div style='color:#a0aec0;font-size:13px;font-weight:600;"
                        "margin-bottom:4px'>STM request vs LTM baseline vs Allocated</div>",
                        unsafe_allow_html=True)
            stm_vals = [inputs[d["key"]]["stm_request"] for d in DOMAINS]
            ltm_vals = [inputs[d["key"]]["ltm_baseline"] for d in DOMAINS]
            bar = go.Figure()
            bar.add_bar(name="STM request", x=names, y=stm_vals, marker_color="#fbbf24")
            bar.add_bar(name="LTM baseline", x=names, y=ltm_vals, marker_color="#34d399")
            bar.add_bar(name="Allocated", x=names, y=amounts, marker_color="#667eea")
            bar.update_layout(barmode="group", height=320,
                              margin=dict(t=10, b=10, l=10, r=10),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#cbd5e0"),
                              legend=dict(orientation="h", y=-0.18),
                              xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                              yaxis=dict(gridcolor="rgba(255,255,255,0.08)"))
            st.plotly_chart(bar, use_container_width=True)
    elif allocs:
        with cc1:
            st.markdown("**Allocation share**")
            st.bar_chart({a["domain"]: a["amount"] for a in allocs})
        with cc2:
            st.info("Install plotly for the richer comparison chart: `pip install plotly`")

    # Allocation cards
    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
    st.markdown("<div style='color:#e2e8f0;font-size:16px;font-weight:700;"
                "margin-bottom:10px'>📊 Allocation Breakdown</div>", unsafe_allow_html=True)
    icon_map = {d["name"]: d["icon"] for d in DOMAINS}
    for a in allocs:
        icon = icon_map.get(a["domain"], "•")
        pct = a.get("percentage", 0)
        st.markdown(f"""
<div class='alloc-card'>
  <div class='alloc-head'>
    <span style='font-size:20px'>{icon}</span>
    <span class='alloc-name'>{a['domain']}</span>
    <span class='alloc-amt'>{a['amount']} {cur} · {pct}%</span>
  </div>
  <div class='alloc-bar-track'><div class='alloc-bar-fill' style='width:{min(pct,100)}%'></div></div>
  <div class='alloc-rationale'>{a.get('rationale','')}</div>
  <div class='alloc-influence'>
    <span class='mem-tag-stm'>STM</span> {a.get('stm_influence','—')}<br>
    <span class='mem-tag-ltm'>LTM</span> {a.get('ltm_influence','—')}
  </div>
</div>""", unsafe_allow_html=True)

    # Assumptions
    if plan.get("assumptions"):
        st.markdown("<div style='color:#a0aec0;font-size:13px;font-weight:600;margin:6px 0'>"
                    "Planner assumptions</div>", unsafe_allow_html=True)
        st.markdown("".join(f"<span class='step-pill'>{x}</span>" for x in plan["assumptions"]),
                    unsafe_allow_html=True)

# ── Full execution + validator summary ─────────────────────────────────────────
if st.session_state.execution:
    st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
    with st.expander("⚙️ Full Implementation Plan (Executor)", expanded=False):
        st.markdown(st.session_state.execution)

    if st.session_state.validation:
        st.markdown(f"""
<div style='margin-top:14px;background:rgba(159,122,234,0.07);
     border:1px solid rgba(159,122,234,0.25);border-radius:16px;padding:20px'>
  <div style='color:#b794f4;font-size:13px;font-weight:700;margin-bottom:8px'>✅ Validator Summary</div>
  <div style='color:#cbd5e0;font-size:14px;line-height:1.7'>
    {st.session_state.validation.get('summary','')}</div>
</div>""", unsafe_allow_html=True)

    # Download the full plan as JSON
    export = {"plan": st.session_state.plan, "execution": st.session_state.execution,
              "validation": st.session_state.validation}
    st.download_button("⬇ Download full plan (JSON)",
                       data=json.dumps(export, indent=2),
                       file_name="budget_plan.json", mime="application/json")