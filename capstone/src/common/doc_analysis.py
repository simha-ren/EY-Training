"""Document & visual analysis.

Turns an uploaded PDF/image/office file into structured content the pipeline
can use, and — when a vision-capable LLM is configured — describes the
architecture diagrams, charts and other figures inside it.

Capability tiers (each degrades gracefully):
  1. Azure Document Intelligence (prebuilt-layout) — text, tables, figure regions.
       Enabled when AZURE_DOCINTEL_ENDPOINT and AZURE_DOCINTEL_KEY are set.
  2. Local text extraction (pypdf / docx / pptx / xlsx / csv / md / txt) — always.
  3. Vision description of figures/pages via the LLM (Claude vision) — enabled
       when CLAUDE_API_KEY (or ANTHROPIC_API_KEY) is set. This is what "analyzes
       diagrams, graphs and visualizations".

Everything is best-effort and never raises to the caller.
"""
from __future__ import annotations

import base64
import os
from typing import Any, Dict, List, Optional


# ----------------------------- capability flags ---------------------------
def azure_docintel_available() -> bool:
    return bool(os.getenv("AZURE_DOCINTEL_ENDPOINT") and os.getenv("AZURE_DOCINTEL_KEY"))


def vision_available() -> bool:
    return bool(os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


# ----------------------------- text + tables ------------------------------
def _azure_layout(data: bytes) -> Optional[Dict[str, Any]]:
    """Extract text, tables and figure count via Azure Document Intelligence."""
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        client = DocumentIntelligenceClient(
            endpoint=os.environ["AZURE_DOCINTEL_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["AZURE_DOCINTEL_KEY"]))
        poller = client.begin_analyze_document(
            "prebuilt-layout", AnalyzeDocumentRequest(bytes_source=data))
        result = poller.result()
        text = result.content or ""
        tables = []
        for t in (result.tables or []):
            tables.append({"rows": t.row_count, "cols": t.column_count})
        figures = len(getattr(result, "figures", []) or [])
        return {"text": text, "tables": tables, "figure_count": figures,
                "source": "azure_document_intelligence"}
    except Exception as e:
        return None


def _local_text(data: bytes, filename: str) -> Dict[str, Any]:
    """Fallback text extraction using the existing FileProcessor."""
    import tempfile
    from src.common.file_processor import FileProcessor
    ext = os.path.splitext(filename)[1].lower() or ".txt"
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data); path = f.name
        text = FileProcessor.extract_text(path)
    except Exception:
        text = ""
    finally:
        try: os.unlink(path)
        except Exception: pass
    return {"text": text or "", "tables": [], "figure_count": 0, "source": "local"}


def extract_content(data: bytes, filename: str) -> Dict[str, Any]:
    """Best available text/table/figure extraction."""
    if azure_docintel_available():
        r = _azure_layout(data)
        if r is not None:
            return r
    return _local_text(data, filename)


# ----------------------------- render to images ---------------------------
def _page_images(data: bytes, filename: str, max_pages: int = 6) -> List[bytes]:
    """Return PNG bytes for each page (PDF via PyMuPDF) or the image itself."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return [data]
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=data, filetype="pdf")
            imgs = []
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                pix = page.get_pixmap(dpi=140)
                imgs.append(pix.tobytes("png"))
            return imgs
        except Exception:
            return []
    return []


# ----------------------------- vision description -------------------------
def describe_visuals(data: bytes, filename: str, max_pages: int = 4) -> Dict[str, Any]:
    """Describe diagrams / charts / visuals using the LLM's vision capability.

    Needs an Anthropic (Claude) key. Returns per-page descriptions covering the
    components, connections and meaning of any architecture diagrams or graphs.
    """
    if not vision_available():
        return {"available": False,
                "note": "Set CLAUDE_API_KEY to analyze diagrams/graphs visually.",
                "descriptions": []}
    images = _page_images(data, filename, max_pages=max_pages)
    if not images:
        return {"available": True, "note": "No renderable pages/images found.",
                "descriptions": []}
    try:
        import anthropic
        client = anthropic.Anthropic(
            api_key=os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        model = os.getenv("CLAUDE_VISION_MODEL", "claude-3-5-sonnet-20241022")
        descriptions = []
        for idx, png in enumerate(images):
            b64 = base64.standard_b64encode(png).decode()
            msg = client.messages.create(
                model=model, max_tokens=700,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64",
                     "media_type": "image/png", "data": b64}},
                    {"type": "text", "text":
                        "This is a page from a technical document. If it contains "
                        "architecture diagrams, flowcharts, graphs or charts, describe "
                        "them precisely: the components/nodes, how they connect, data "
                        "or control flow direction, and what the visual conveys. "
                        "If it also has key numbers in a chart, state them. "
                        "If there is no meaningful visual, reply 'No diagram on this page.'"}]}])
            txt = "".join(getattr(b, "text", "") for b in msg.content) if msg.content else ""
            if txt and "no diagram" not in txt.lower():
                descriptions.append({"page": idx + 1, "description": txt.strip()})
        return {"available": True, "descriptions": descriptions,
                "pages_scanned": len(images)}
    except Exception as e:
        return {"available": True, "error": str(e)[:200], "descriptions": []}


# ----------------------------- combined entry -----------------------------
def analyze_document(data: bytes, filename: str, include_visuals: bool = True) -> Dict[str, Any]:
    """Full analysis: text/tables/figures + (optional) diagram descriptions."""
    content = extract_content(data, filename)
    result: Dict[str, Any] = {
        "filename": filename,
        "extraction_source": content.get("source"),
        "text": content.get("text", ""),
        "text_chars": len(content.get("text", "")),
        "tables": content.get("tables", []),
        "figure_count": content.get("figure_count", 0),
        "visuals": {"available": False, "descriptions": []},
    }
    if include_visuals:
        result["visuals"] = describe_visuals(data, filename)
    return result
