from core.core.file_processor import FileProcessor

def test_supported_extensions():
    assert FileProcessor.is_supported("a.md")
    assert FileProcessor.is_supported("a.pdf")
    assert not FileProcessor.is_supported("a.zip")
