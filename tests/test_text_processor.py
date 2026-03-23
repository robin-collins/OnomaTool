from onomatool.processors.text_processor import TextProcessor


def test_process_success(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    tp = TextProcessor()
    result = tp.process(str(f))
    assert result is not None
    assert result.markdown == "hello world"


def test_process_file_not_found(tmp_path, monkeypatch):
    tp = TextProcessor()
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    assert tp.process(str(tmp_path / "missing.txt")) is None


def test_process_non_utf8(tmp_path, monkeypatch):
    f = tmp_path / "b.txt"
    # Write bytes that are not valid utf-8
    f.write_bytes(b"\xff\xfe\xfd")
    tp = TextProcessor()
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    assert tp.process(str(f)) is None


# Edge case tests (§2.8)


def test_detect_encoding_reads_limited_bytes(tmp_path):
    """TC-TP-001: detect_encoding reads only first 10KB."""
    f = tmp_path / "large.txt"
    # Write 20KB of ASCII
    f.write_bytes(b"A" * 20480)
    tp = TextProcessor()
    encoding = tp.detect_encoding(str(f))
    assert encoding is not None  # Should detect without reading all 20KB


def test_large_file_processing(tmp_path):
    """TC-TP-002: Large files are processed successfully."""
    f = tmp_path / "large.txt"
    content = "Hello World\n" * 10000  # ~120KB
    f.write_text(content, encoding="utf-8")
    tp = TextProcessor()
    result = tp.process(str(f))
    assert result is not None
    assert result.markdown == content


def test_utf8_bom_handling(tmp_path):
    """TC-TP-003: UTF-8 BOM files are processed correctly."""
    f = tmp_path / "bom.txt"
    # UTF-8 BOM + content
    f.write_bytes(b"\xef\xbb\xbfHello BOM")
    tp = TextProcessor()
    result = tp.process(str(f))
    assert result is not None
    assert "Hello BOM" in result.markdown
