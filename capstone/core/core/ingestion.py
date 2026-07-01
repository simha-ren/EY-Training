"""Ingestion pipeline (doc Section 2.3).

Files -> layout/text extraction -> section-aware chunking (preserving source
offsets for citations) -> domain normalization/tagging. Embedding + indexing
happens in store.py. Mirrors ingestion/{extract,chunk,normalize,embed}.py.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .config import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS, DATA_DIR


@dataclass
class Chunk:
    id: str
    domain: str
    source: str          # file name shown in citations
    section: str         # nearest heading, for citation context
    text: str
    start: int           # char offset in source (preserved for citations)
    end: int
    sensitivity: str = "normal"   # normalizer tag (normal | sensitive)
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------- extract ---
def extract_text(path: Path) -> str:
    """Layout/text extraction. PDF via pypdf; text/markdown read directly."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            import io

            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    return data.decode("utf-8", errors="ignore")


# ------------------------------------------------------------------ chunk ---
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def _sections(text: str):
    """Yield (heading, body, start_offset) splitting on markdown headings."""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        yield ("", text, 0)
        return
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield (heading, text[body_start:body_end].strip(), body_start)


def _split_body(body: str, base_offset: int):
    """Greedy char-window chunking with overlap, preserving offsets."""
    body = body.strip()
    if not body:
        return
    if len(body) <= CHUNK_TARGET_CHARS:
        yield (body, base_offset, base_offset + len(body))
        return
    paras = re.split(r"\n\s*\n", body)
    buf, buf_start, cursor = "", base_offset, base_offset
    for para in paras:
        if buf and len(buf) + len(para) > CHUNK_TARGET_CHARS:
            yield (buf.strip(), buf_start, buf_start + len(buf))
            tail = buf[-CHUNK_OVERLAP_CHARS:]
            buf = tail + "\n\n" + para
            buf_start = cursor - len(tail)
        else:
            buf = (buf + "\n\n" + para) if buf else para
            if not buf.strip():
                buf_start = cursor
        cursor += len(para) + 2
    if buf.strip():
        yield (buf.strip(), buf_start, buf_start + len(buf))


# -------------------------------------------------------------- normalize ---
_SENSITIVE_HINTS = ("patient", "phi", "diagnosis", "medical record")


def _tag_sensitivity(domain: str, text: str) -> str:
    low = text.lower()
    if domain == "healthcare" and any(h in low for h in _SENSITIVE_HINTS):
        return "sensitive"
    return "normal"


def chunk_document(text: str, domain: str, source: str) -> List[Chunk]:
    chunks: List[Chunk] = []
    for heading, body, sec_offset in _sections(text):
        for piece, start, end in _split_body(body, sec_offset):
            chunks.append(
                Chunk(
                    id=uuid.uuid4().hex[:12],
                    domain=domain,
                    source=source,
                    section=heading or source,
                    text=piece,
                    start=start,
                    end=end,
                    sensitivity=_tag_sensitivity(domain, piece),
                )
            )
    return chunks


# ---------------------------------------------------------------- loaders ---
def load_seed_corpus() -> List[Chunk]:
    """Load all bundled per-domain seed documents from data/<domain>/*."""
    chunks: List[Chunk] = []
    for domain_dir in sorted(DATA_DIR.iterdir()):
        if not domain_dir.is_dir():
            continue
        domain = domain_dir.name
        for f in sorted(domain_dir.glob("*")):
            if f.suffix.lower() not in (".md", ".txt", ".pdf"):
                continue
            text = extract_text(f)
            chunks.extend(chunk_document(text, domain, f.name))
    return chunks


def ingest_upload(data: bytes, filename: str, domain: str) -> List[Chunk]:
    text = extract_text_from_bytes(data, filename)
    return chunk_document(text, domain, filename)
