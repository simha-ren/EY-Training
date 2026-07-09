"""ProposalForge UI upgrades — in-chat charts + off-topic relevance gate.

Drop-in module used by src/ui/app_prod.py. No other files need to change beyond
three small hooks in app_prod.py (see MODIFICATIONS.md).

Design goals:
  * Works ONLINE (LLM emits grounded chart JSON) and OFFLINE (parses numeric
    series out of the retrieved context / CSV-like tables) — so a live demo
    never shows an empty chart.
  * Off-topic detection is conservative: it only fires when documents are loaded
    AND the question has no lexical grounding in them, so genuine document
    questions are never wrongly blocked.
"""
from __future__ import annotations

import re
import json
from typing import Optional, List, Dict


# --------------------------------------------------------------------------- #
#  Chart intent + extraction                                                  #
# --------------------------------------------------------------------------- #
_CHART_WORDS = re.compile(
    r"\b(chart|graph|plot|trend|trends|visuali[sz]e|visuali[sz]ation|bar chart|"
    r"line chart|over (the )?(last |past |next )?\d+\s*(year|years|quarter|quarters|month|months)|"
    r"year[- ]on[- ]year|growth curve|show me the (numbers|data))\b", re.I)


def chart_intent(query: str) -> bool:
    """True when the user is asking to SEE data as a chart."""
    return bool(_CHART_WORDS.search(query or ""))


_STOP = set("the a an of to in for and or is are on with this that what which how why "
            "when who from as at by be it its into show me give the numbers data".split())


def _tok(s: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]{3,}", (s or "").lower()) if w not in _STOP]


def _numbers_from_context(context: str, query: str) -> Optional[Dict]:
    """Offline fallback — pull a labelled numeric series out of CSV/table text.

    Recognises lines like  '2021, 95, 310'  or  'FY22 | 180 | 610'  and years/
    quarters as x-axis labels. Returns a chart spec or None.
    """
    rows = []
    for ln in (context or "").splitlines():
        parts = re.split(r"[|,\t]| {2,}", ln.strip())
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) < 2:
            continue
        label = parts[0]
        nums = []
        for p in parts[1:]:
            m = re.search(r"-?\d[\d,\.]*", p.replace("%", "").replace("INR", ""))
            if m:
                try:
                    nums.append(float(m.group(0).replace(",", "")))
                except ValueError:
                    pass
        if nums and re.search(r"(19|20)\d{2}|FY\d{2}|Q\d|Year\s*\d|Wk\d", label, re.I):
            rows.append((label, nums))
    if len(rows) < 2:
        return None
    width = min(len(r[1]) for r in rows)
    x = [r[0] for r in rows]
    series = {f"series {i+1}": [r[1][i] for r in rows] for i in range(min(width, 3))}
    return {"kind": "line", "title": "Trend from your documents", "x": x, "series": series}


def build_chart(query: str, context: str, client, online: bool) -> Optional[Dict]:
    """Return a chart spec {kind,title,x,series} grounded in the documents, or None."""
    # 1) ONLINE — ask the model for grounded chart JSON.
    if online and hasattr(client, "complete"):
        try:
            raw = client.complete(
                "You extract chart-ready data from documents. Reply with ONLY strict "
                "JSON, no prose, no code fences.",
                "From the document context, produce data to answer the user's chart "
                "request. Use ONLY numbers present or clearly implied in the context.\n"
                'JSON schema: {"kind":"line|bar","title":"...","x":["label",...],'
                '"series":{"Series name":[num,...]}}\n'
                "If the context has no chartable numbers, reply exactly: {}\n\n"
                f"User request: {query}\n\nContext:\n{context[:5000]}")
            raw = re.sub(r"```json|```", "", raw or "").strip()
            a, b = raw.find("{"), raw.rfind("}")
            if a >= 0 and b > a:
                spec = json.loads(raw[a:b + 1])
                if spec.get("x") and spec.get("series"):
                    spec.setdefault("kind", "line")
                    spec.setdefault("title", "Chart")
                    return spec
        except Exception:
            pass
    # 2) OFFLINE — parse numbers out of the retrieved context.
    return _numbers_from_context(context, query)


def render_chart(st, spec: Dict) -> None:
    """Render a chart spec inside a Streamlit chat message."""
    try:
        import pandas as pd
    except Exception:
        st.caption("(install pandas to render charts)")
        return
    x = spec.get("x") or []
    series = spec.get("series") or {}
    if not x or not series:
        return
    n = len(x)
    data = {k: (list(v) + [None] * n)[:n] for k, v in series.items()}
    df = pd.DataFrame(data, index=x)
    st.markdown(f"**📈 {spec.get('title','Chart')}**")
    if (spec.get("kind") or "line").lower().startswith("bar"):
        st.bar_chart(df)
    else:
        st.line_chart(df)


# --------------------------------------------------------------------------- #
#  Off-topic relevance gate                                                   #
# --------------------------------------------------------------------------- #
def relevance(query: str, context: str) -> float:
    """Lexical overlap between the query and the retrieved context (0..1)."""
    q = set(_tok(query))
    c = set(_tok(context))
    if not q:
        return 1.0
    return len(q & c) / len(q)


def offtopic_banner(query: str, context: str, docs: list, retrieved: list,
                    domains: Optional[List[str]] = None) -> Optional[str]:
    """Return a heads-up banner when a question looks outside the uploaded knowledge.

    Fires only when documents ARE loaded and there is essentially no grounding.
    We still answer afterwards (general knowledge), but the banner tells the user
    the answer is not from their documents — satisfying 'hey, it's not related'.
    """
    if not docs:
        return None                      # no knowledge yet — nothing to be off-topic from
    score = relevance(query, context)
    grounded = bool(retrieved) and score >= 0.15
    if grounded:
        return None
    doms = ", ".join(sorted({d.get("domain", "General") for d in docs})) or "your documents"
    return (f"🧭 **Heads up — this looks outside your uploaded knowledge** "
            f"({doms}). I couldn't find it in your documents, so the answer below "
            f"is general knowledge, not grounded in your sources.")


# --------------------------------------------------------------------------- #
#  Downloadable report — embedded chart (graphs/visualizations requirement)   #
# --------------------------------------------------------------------------- #
def _count(analysis: dict, key: str) -> int:
    v = (analysis or {}).get(key, "") or ""
    if isinstance(v, list):
        return len([x for x in v if str(x).strip()])
    return len([ln for ln in str(v).splitlines() if ln.strip()])


def add_report_chart(document, docs: list) -> None:
    """Embed a 'challenges vs proposed solutions per document' chart into a docx.

    Uses matplotlib when installed (crisp PNG); otherwise falls back to a
    dependency-free shaded-table bar chart so the report always has a visual.
    """
    if not docs:
        return
    names = [(d.get("name", "doc")[:24]) for d in docs]
    challenges = [_count(d.get("analysis", {}), "Current solutions") for d in docs]
    solutions = [_count(d.get("analysis", {}), "Proposed solutions") for d in docs]

    # --- rich path: matplotlib PNG ---
    try:
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from docx.shared import Inches
        x = range(len(names))
        fig, ax = plt.subplots(figsize=(6.6, 3.4))
        ax.bar([i - 0.2 for i in x], challenges, width=0.4, label="Current challenges", color="#E9950C")
        ax.bar([i + 0.2 for i in x], solutions, width=0.4, label="Proposed solutions", color="#12A5B0")
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=25, ha="right", fontsize=8)
        ax.set_title("Challenges vs Proposed Solutions by Document", fontsize=11, fontweight="bold")
        ax.legend(frameon=False, fontsize=8)
        ax.grid(axis="y", color="#eef2f6")
        fig.tight_layout()
        buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130); plt.close(fig)
        buf.seek(0)
        document.add_heading("Portfolio at a glance", level=1)
        document.add_picture(buf, width=Inches(6.0))
        return
    except Exception:
        pass

    # --- fallback path: shaded-table bar chart (no extra deps) ---
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    document.add_heading("Portfolio at a glance", level=1)
    document.add_paragraph("Current challenges (amber) vs proposed solutions (teal) per document:")
    maxv = max([1] + challenges + solutions)

    def shade(cell, hexcolor):
        tcPr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement("w:shd"); sh.set(qn("w:fill"), hexcolor); tcPr.append(sh)

    tbl = document.add_table(rows=0, cols=2)
    for nm, ch, so in zip(names, challenges, solutions):
        for label, val, color in ((f"{nm} — challenges", ch, "E9950C"),
                                   (f"{nm} — solutions", so, "12A5B0")):
            row = tbl.add_row().cells
            row[0].text = f"{label} ({val})"
            bar = row[1]
            blocks = int(round((val / maxv) * 20))
            bar.text = "█" * max(blocks, 1)
            shade(bar, color)
