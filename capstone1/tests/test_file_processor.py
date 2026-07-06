"""Unit tests for core.file_processor — type detection and text extraction."""
from pathlib import Path

from core.file_processor import FileProcessor


def test_is_supported_true_for_known_types():
    for name in ("report.pdf", "notes.txt", "data.csv", "sheet.xlsx",
                 "doc.docx", "readme.md"):
        assert FileProcessor.is_supported(name) is True


def test_is_supported_false_for_unknown():
    assert FileProcessor.is_supported("archive.zip") is False
    assert FileProcessor.is_supported("image.png") is False


def test_extract_text_from_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("Hello world from ProposalForge.", encoding="utf-8")
    text = FileProcessor.extract_text(str(p))
    assert "ProposalForge" in text


def test_extract_text_from_md(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nSome **markdown** content.", encoding="utf-8")
    text = FileProcessor.extract_text(str(p))
    assert "markdown" in text


def test_get_file_metadata(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("data", encoding="utf-8")
    meta = FileProcessor.get_file_metadata(str(p))
    assert meta["extension"] == ".txt"
    assert meta["size_bytes"] >= 4
