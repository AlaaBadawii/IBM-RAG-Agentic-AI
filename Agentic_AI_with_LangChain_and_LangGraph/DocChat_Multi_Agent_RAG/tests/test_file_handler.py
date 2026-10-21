"""Unit tests for DocumentProcessor in document_processor/file_handler.py.

Every Docling conversion is mocked so the suite runs offline without model
downloads. The mocks stand in for the real ``DocumentConverter`` interface:
``convert(path)`` returning an object with
``document.export_to_markdown() -> str``.
"""

import io
import pickle
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from langchain_core.documents import Document

import document_processor.file_handler as fh
from document_processor.file_handler import DocumentProcessor


DEMO_MARKDOWN = "# Alpha\n\nAlpha body.\n\n## Beta\n\nBeta body.\n"
SINGLE_CHUNK_MARKDOWN = "# Report\n\nBody text.\n"
SAME_TEXT_TWO_SECTIONS = "# Alpha\n\nShared text.\n\n# Beta\n\nShared text.\n"


class FakeConversion:
    def __init__(self, markdown, status=None, pages=None):
        self.document = FakeDocument(markdown)
        self.status = status or fh.ConversionStatus.SUCCESS
        self.pages = [] if pages is None else pages


class FakeDocument:
    def __init__(self, markdown):
        self._markdown = markdown

    def export_to_markdown(self):
        return self._markdown


class FakeConverter:
    """Conversion recorder compatible with DocumentConverter."""

    inits = None
    init_kwargs = None
    converts = None
    conversion_result = None

    def __init__(self, *args, **kwargs):
        FakeConverter.inits.append("init")
        FakeConverter.init_kwargs.append(kwargs)

    def convert(self, path):
        FakeConverter.converts.append(path)
        return FakeConversion(FakeConverter.conversion_result)


def install_fake_converter(
    monkeypatch,
    markdown=DEMO_MARKDOWN,
    fail=False,
    status=None,
):
    """Patch Docling out of the module and return the recorder lists."""
    FakeConverter.inits = []
    FakeConverter.init_kwargs = []
    FakeConverter.converts = []

    def convert_failure(self, path):
        FakeConverter.converts.append(path)
        raise RuntimeError("conversion backend exploded")

    def real_convert(self, path):
        FakeConverter.converts.append(path)
        if fail:
            raise RuntimeError("conversion backend exploded")
        return FakeConversion(markdown, status=status)

    converter_cls = type(
        "RecordingConverter",
        (FakeConverter,),
        {"convert": convert_failure if fail else real_convert},
    )
    monkeypatch.setattr(fh, "DocumentConverter", converter_cls)
    return converter_cls


class StreamlitUpload:
    """Shape of a Streamlit ``UploadedFile``: name/size/getvalue/read/seek."""

    def __init__(self, name, data, size=None):
        self.name = name
        self.size = len(data) if size is None else size
        self._data = data
        self.seeks = []

    def getvalue(self):
        return self._data

    def read(self):
        return self._data

    def seek(self, position):
        self.seeks.append(position)


class StreamlitTextUpload(StreamlitUpload):
    """Streamlit-style upload whose ``getvalue()`` returns decoded text."""

    def __init__(self, name, text, size=None):
        super().__init__(name, text.encode("utf-8"), size=size)

    def getvalue(self):
        return self._data.decode("utf-8")


class BytesStream:
    """Plain readable/seekable stream without name, size, or getvalue()."""

    def __init__(self, data, extension=".md"):
        self._stream = io.BytesIO(data)
        self.seeks = []
        self.extension = extension

    def seek(self, position):
        self.seeks.append(position)
        self._stream.seek(position)

    def read(self):
        return self._stream.read()


class TextStreamNoSeek(BytesStream):
    """Readable stream that cannot seek."""

    def _no_seek(self, position):
        raise OSError("not seekable")

    def __init__(self, data, extension=".md"):
        super().__init__(data, extension=extension)
        self.seek = self._no_seek


class GradioUpload:
    """Shape of Gradio 5 ``FileData``: path/orig_name/size, no read()."""

    def __init__(self, path, orig_name, size=None):
        self.path = str(path)
        self.orig_name = orig_name
        self.size = len(Path(path).read_bytes()) if size is None else size


class GetvalueDictUpload:
    """Upload whose content helpers return an unsupported type."""

    def getvalue(self):
        return {"not": "bytes"}

    def read(self):
        return {"not": "bytes"}


class ReadIntUpload:
    """Stream whose read() returns an unsupported type."""

    def read(self):
        return 42


def _write_disk_upload(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return GradioUpload(path, name)


def _sha(content):
    return DocumentProcessor._generate_hash(content)


def _cache_path(processor, content):
    return processor.cache_dir / f"{_sha(content)}.pkl"


def _read_cache_file(cache_path):
    with open(cache_path, "rb") as handle:
        return pickle.load(handle)


def _write_cache_file(cache_path, data):
    with open(cache_path, "wb") as handle:
        pickle.dump(data, handle)


def _chunk(text, source):
    return Document(page_content=text, metadata={"source": source})


# ---------------------------------------------------------------------------
# 1. Valid upload processing and Markdown splitting
# ---------------------------------------------------------------------------


def test_valid_upload_processed_and_split(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    upload = StreamlitUpload("report.md", DEMO_MARKDOWN.encode("utf-8"))

    chunks = processor.process([upload])

    assert len(chunks) == 2
    assert chunks[0].metadata == {"source": "report.md", "Header 1": "Alpha"}
    assert chunks[1].metadata == {
        "source": "report.md",
        "Header 1": "Alpha",
        "Header 2": "Beta",
    }
    assert "Alpha body." in chunks[0].page_content
    assert "Beta body." in chunks[1].page_content


def test_converter_reused_across_files(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    uploads = [
        StreamlitUpload("a.md", b"first"),
        StreamlitUpload("b.md", b"second"),
        StreamlitUpload("c.md", b"third"),
    ]

    processor.process(uploads)

    assert FakeConverter.inits == ["init"]
    assert len(FakeConverter.converts) == 3


def test_converter_uses_configured_pdf_pipeline_options(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    monkeypatch.setattr(fh.settings, "DOCLING_DO_OCR", True)
    monkeypatch.setattr(fh.settings, "DOCLING_DO_TABLE_STRUCTURE", True)
    monkeypatch.setattr(fh.settings, "DOCLING_DOCUMENT_TIMEOUT", 123.0)

    processor._get_converter()

    format_options = FakeConverter.init_kwargs[0]["format_options"]
    pdf_option = format_options[fh.InputFormat.PDF]
    assert pdf_option.pipeline_cls is fh.StandardPdfPipeline
    assert pdf_option.backend is fh.DoclingParseV2DocumentBackend
    assert pdf_option.pipeline_options.do_ocr is True
    assert pdf_option.pipeline_options.do_table_structure is True
    assert pdf_option.pipeline_options.document_timeout == 123.0


def test_partial_conversion_is_rejected_and_not_cached(processor, monkeypatch):
    install_fake_converter(
        monkeypatch,
        markdown=SINGLE_CHUNK_MARKDOWN,
        status=fh.ConversionStatus.PARTIAL_SUCCESS,
    )
    upload = StreamlitUpload("partial.pdf", b"partial-content")

    chunks = processor.process([upload])

    assert chunks == []
    assert len(FakeConverter.converts) == 1
    assert not _cache_path(processor, b"partial-content").exists()


def test_empty_conversion_is_rejected_and_not_cached(processor, monkeypatch):
    install_fake_converter(monkeypatch, markdown="")

    chunks = processor.process([StreamlitUpload("empty.pdf", b"empty-content")])

    assert chunks == []
    assert not _cache_path(processor, b"empty-content").exists()


def test_txt_upload_does_not_reach_docling_and_is_chunked(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    upload = StreamlitUpload("notes.txt", b"# Plain title\n\nPlain body.\n")

    chunks = processor.process([upload])

    assert FakeConverter.converts == []
    assert len(chunks) == 1
    assert chunks[0].page_content.strip() == "Plain body."
    assert chunks[0].metadata["source"] == "notes.txt"


def test_real_md_conversion_integration(processor):
    """Integration check against the real converter for markdown input."""
    upload = StreamlitUpload(
        "real.md", "# Title\n\nReal body.\n\n## Sub\n\nMore.\n".encode("utf-8")
    )

    chunks = processor.process([upload])

    assert {c.metadata.get("Header 1") for c in chunks} == {"Title"}
    assert any("Real body." in c.page_content for c in chunks)
    assert all(c.metadata["source"] == "real.md" for c in chunks)


# ---------------------------------------------------------------------------
# 2. Byte normalization across upload-object shapes
# ---------------------------------------------------------------------------


def test_read_streamlit_upload_bytes(processor):
    upload = StreamlitUpload("a.bin", b"\x00\x01raw")
    assert DocumentProcessor._read_file_content(upload) == b"\x00\x01raw"


def test_read_streamlit_upload_text_encoded_utf8(processor):
    upload = StreamlitTextUpload("a.txt", "héllo")
    assert DocumentProcessor._read_file_content(upload) == "héllo".encode("utf-8")


def test_read_bytes_stream_restores_position(processor):
    stream = BytesStream(b"stream-bytes")
    stream.seek(20)  # pre-existing position mid-stream

    content = DocumentProcessor._read_file_content(stream)

    assert content == b"stream-bytes"
    # Stream was reset before reading and restored after, even though the
    # original position was mid-stream.
    assert stream.seeks == [20, 0, 0]


def test_read_text_stream_no_seek(processor):
    stream = TextStreamNoSeek(b"no-seek")

    assert DocumentProcessor._read_file_content(stream) == b"no-seek"


def test_read_text_stream_no_seek_survives_read_failure(processor):
    class FailingStream:
        def read(self):
            raise OSError("disk blew up")

        def seek(self, position):
            self.last_seek = position

    stream = FailingStream()
    with pytest.raises(OSError):
        DocumentProcessor._read_file_content(stream)
    # Position was restored even though reading failed.
    assert stream.last_seek == 0


def test_read_gradio_style_disk_path(processor, tmp_path):
    upload = _write_disk_upload(tmp_path, "gradio.md", b"from-disk")

    assert DocumentProcessor._read_file_content(upload) == b"from-disk"


def test_read_name_only_disk_fallback(processor, tmp_path):
    path = tmp_path / "legacy.md"
    path.write_bytes(b"legacy-read")

    reader = type("LegacyUpload", (), {"name": str(path)})

    assert DocumentProcessor._read_file_content(reader()) == b"legacy-read"


def test_read_unsupported_content_types_raise(processor):
    with pytest.raises(TypeError, match="Unsupported upload content type"):
        DocumentProcessor._read_file_content(GetvalueDictUpload())

    with pytest.raises(TypeError, match="Unsupported upload content type"):
        DocumentProcessor._read_file_content(ReadIntUpload())


def test_read_object_without_readable_content_raises(processor):
    with pytest.raises(TypeError, match="does not expose readable content"):
        DocumentProcessor._read_file_content(object())


def test_read_seek_and_read_failures_are_handled(processor):
    class BrokenSeeker:
        def __init__(self):
            self.read_attempts = 0

        def read(self):
            self.read_attempts += 1
            return b"ok"

        def seek(self, position):
            raise OSError("seek rejected")

    assert DocumentProcessor._read_file_content(BrokenSeeker()) == b"ok"


# ---------------------------------------------------------------------------
# 3. Per-file and aggregate size validation
# ---------------------------------------------------------------------------


def test_validate_rejects_oversized_reported_file(processor, monkeypatch):
    monkeypatch.setattr(fh.settings, "MAX_FILE_SIZE", 8)
    upload = StreamlitUpload("big.md", b"0123456789")  # reports 10 bytes

    with pytest.raises(ValueError, match="exceeds the maximum size"):
        processor.validate_files([upload])


def test_validate_allows_file_at_exact_limit(processor, monkeypatch):
    monkeypatch.setattr(fh.settings, "MAX_FILE_SIZE", 10)
    upload = StreamlitUpload("exact.md", b"0123456789")  # exactly 10 bytes

    processor.validate_files([upload])


def test_validate_rejects_total_across_files(processor, monkeypatch):
    monkeypatch.setattr(fh.settings, "MAX_TOTAL_SIZE", 15)
    uploads = [
        StreamlitUpload("one.md", b"0123456789"),  # 10
        StreamlitUpload("two.md", b"012345"),  # 6 -> total 16
    ]

    with pytest.raises(ValueError, match="Total file size exceeds"):
        processor.validate_files(uploads)


def test_validate_ignores_missing_size_metadata(processor):
    upload = type("NamedStream", (), {"name": "stream.md"})()

    # No ``size`` at all: validation must not crash on the missing attribute.
    processor.validate_files([upload])


def test_validate_rejects_unnamed_upload(processor):
    upload = BytesStream(b"data")

    with pytest.raises(ValueError, match="unsupported file type"):
        processor.validate_files([upload])


def test_process_revalidates_real_bytes_when_size_stale(processor, monkeypatch):
    """A lying ``size`` property cannot bypass validation."""
    monkeypatch.setattr(fh.settings, "MAX_FILE_SIZE", 8)
    install_fake_converter(monkeypatch)

    upload = StreamlitUpload("liar.md", b"0123456789", size=1)  # lies
    honest = StreamlitUpload("honest.md", b"honest7")

    chunks = processor.process([upload, honest])

    sources = [c.metadata["source"] for c in chunks]
    assert "liar.md" not in sources
    assert "honest.md" in sources
    # The liar never reached conversion and left no cache entry behind.
    assert not _cache_path(processor, b"0123456789").exists()


def test_process_enforces_total_from_real_bytes(processor, monkeypatch):
    monkeypatch.setattr(fh.settings, "MAX_TOTAL_SIZE", 10)
    install_fake_converter(monkeypatch)

    uploads = [
        StreamlitUpload("big.md", b"0123456789", size=1),  # actually 10
        StreamlitUpload("extra.md", b"zzzzz", size=1),  # would pass alone
    ]

    chunks = processor.process(uploads)

    sources = {chunk.metadata["source"] for chunk in chunks}
    # The second file pushes the running total past the global limit.
    assert "extra.md" not in sources
    assert "big.md" in sources


def test_process_rejects_file_at_boundary_only_over_limit(processor, monkeypatch):
    monkeypatch.setattr(fh.settings, "MAX_FILE_SIZE", 8)
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)

    at_limit = StreamlitUpload("at.md", b"01234567")  # exactly 8
    chunks = processor.process([at_limit])
    assert [c.metadata["source"] for c in chunks] == ["at.md"]

    over_limit = StreamlitUpload(
        "over.md", b"012345678", size=1
    )  # 9 bytes, hidden by a lying size property
    chunks = processor.process([over_limit])
    assert chunks == []
    assert not _cache_path(processor, b"012345678").exists()


# ---------------------------------------------------------------------------
# 4. Unsupported file extensions
# ---------------------------------------------------------------------------


def test_validate_rejects_unsupported_extension(processor):
    upload = StreamlitUpload("payload.exe", b"binary")

    with pytest.raises(ValueError, match="unsupported file type"):
        processor.process([upload])


def test_unsupported_extension_blocks_entire_batch(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    uploads = [
        StreamlitUpload("bad.exe", b"x"),
        StreamlitUpload("good.md", DEMO_MARKDOWN.encode("utf-8")),
    ]

    # Validation is batch-level: raise before any processing begins.
    with pytest.raises(ValueError, match="bad.exe"):
        processor.process(uploads)

    assert FakeConverter.converts == []


# ---------------------------------------------------------------------------
# 5. Cache behavior: hit, miss, expiration
# ---------------------------------------------------------------------------


def test_cache_miss_then_hit(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    content = DEMO_MARKDOWN.encode("utf-8")
    upload = StreamlitUpload("report.md", content)

    first = processor.process([upload])
    cache_file = _cache_path(processor, content)
    assert cache_file.is_file()

    second = processor.process([StreamlitUpload("report.md", content)])

    assert [c.page_content for c in first] == [c.page_content for c in second]
    assert len(FakeConverter.converts) == 1  # second upload was a cache hit


def test_cache_expires_after_24_hours(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    upload = StreamlitUpload("report.md", b"expiring-content")

    processor.process([upload])
    cache_file = _cache_path(processor, b"expiring-content")

    entry = _read_cache_file(cache_file)
    entry["timestamp"] = (datetime.now() - timedelta(hours=25)).timestamp()
    _write_cache_file(cache_file, entry)

    processor.process([StreamlitUpload("report.md", b"expiring-content")])

    assert len(FakeConverter.converts) == 2  # expired entry triggered regeneration


def test_cache_still_valid_under_ttl(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    upload = StreamlitUpload("report.md", b"fresh-content")

    processor.process([upload])
    cache_file = _cache_path(processor, b"fresh-content")

    entry = _read_cache_file(cache_file)
    entry["timestamp"] = (datetime.now() - timedelta(hours=23)).timestamp()
    _write_cache_file(cache_file, entry)

    processor.process([StreamlitUpload("report.md", b"fresh-content")])

    assert len(FakeConverter.converts) == 1


def test_cache_hit_reads_file_only_once(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    upload = StreamlitUpload("report.md", b"single-read")

    processor.process([upload])
    cache_file = _cache_path(processor, b"single-read")

    loads = []
    real_load = pickle.load

    def counting_load(file_object):
        loads.append(file_object.name)
        return real_load(file_object)

    monkeypatch.setattr(pickle, "load", counting_load)
    processor.process([StreamlitUpload("report.md", b"single-read")])

    assert loads == [str(cache_file)]


# ---------------------------------------------------------------------------
# 6. Corrupted / invalid cache entries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"\x00\x01definitely-not-pickle",  # corrupt pickle
        {"chunks": [Document(page_content="x", metadata={})]},  # missing timestamp
        {"timestamp": "not-a-number", "chunks": []},  # invalid timestamp
        {"timestamp": True, "chunks": []},  # bool timestamp masquerading as int
        {"timestamp": datetime.now().timestamp(), "chunks": "nope"},  # bad chunks
        {"timestamp": datetime.now().timestamp(), "chunks": [42, "x"]},
    ],
)
def test_invalid_cache_entries_treated_as_miss_and_recovered(
    processor, monkeypatch, payload
):
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)
    upload = StreamlitUpload("report.md", b"regenerate-me")
    cache_file = _cache_path(processor, b"regenerate-me")

    if isinstance(payload, bytes):
        cache_file.write_bytes(payload)
    else:
        _write_cache_file(cache_file, payload)

    chunks = processor.process([upload])

    assert [c.metadata["source"] for c in chunks] == ["report.md"]
    assert len(FakeConverter.converts) == 1

    # The regenerated entry is valid and gets used afterwards.
    entry = _read_cache_file(cache_file)
    assert all(isinstance(chunk, Document) for chunk in entry["chunks"])


def test_expired_cache_entry_is_regenerated_with_fresh_timestamp(
    processor, monkeypatch
):
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)
    upload = StreamlitUpload("report.md", b"too-old")
    cache_file = _cache_path(processor, b"too-old")

    entry = {
        "timestamp": (datetime.now() - timedelta(hours=48)).timestamp(),
        "chunks": [_chunk("stale text", "stale.md")],
    }
    _write_cache_file(cache_file, entry)

    chunks = processor.process([upload])

    assert [c.metadata["source"] for c in chunks] == ["report.md"]
    refreshed = _read_cache_file(cache_file)
    assert refreshed["chunks"][0].metadata["source"] == "report.md"
    age = datetime.now().timestamp() - refreshed["timestamp"]
    assert 0 <= age < 60  # freshly written


def test_future_timestamped_cache_treated_as_miss(processor, monkeypatch):
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)
    upload = StreamlitUpload("report.md", b"from-the-future")
    cache_file = _cache_path(processor, b"from-the-future")

    entry = {
        "timestamp": (datetime.now() + timedelta(hours=2)).timestamp(),
        "chunks": [_chunk("future text", "future.md")],
    }
    _write_cache_file(cache_file, entry)

    chunks = processor.process([upload])

    assert [c.metadata["source"] for c in chunks] == ["report.md"]
    assert len(FakeConverter.converts) == 1


def test_unreadable_cache_file_recovers(processor, monkeypatch):
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)
    upload = StreamlitUpload("report.md", b"locked-cache")
    cache_file = _cache_path(processor, b"locked-cache")

    cache_file.write_bytes(b"placeholder")
    cache_file.chmod(0o000)  # unreadable

    try:
        chunks = processor.process([upload])
    finally:
        cache_file.chmod(0o644)

    assert [c.metadata["source"] for c in chunks] == ["report.md"]
    assert len(FakeConverter.converts) == 1


# ---------------------------------------------------------------------------
# 7. Identical content uploaded under different filenames (regression)
# ---------------------------------------------------------------------------


def test_identical_bytes_different_names_get_correct_sources(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    content = DEMO_MARKDOWN.encode("utf-8")

    first = processor.process([StreamlitUpload("a.md", content)])
    second = processor.process([StreamlitUpload("b.md", content)])

    assert all(c.metadata["source"] == "a.md" for c in first)
    assert all(c.metadata["source"] == "b.md" for c in second)

    # Re-serving the first filename must not have been corrupted by the
    # second upload's re-attribution.
    third = processor.process([StreamlitUpload("a.md", content)])
    assert all(c.metadata["source"] == "a.md" for c in third)

    # Both uploads share one content-keyed cache file.
    assert len(list(processor.cache_dir.glob("*.pkl"))) == 1


# ---------------------------------------------------------------------------
# 8. Chunk deduplication with metadata-aware keys
# ---------------------------------------------------------------------------


def test_duplicate_text_same_metadata_deduplicated(processor, monkeypatch):
    install_fake_converter(monkeypatch, markdown="# Same\n\nSame paragraph.\n")
    content = b"# Same\n\nSame paragraph.\n"

    chunks = processor.process(
        [
            StreamlitUpload("copy1.md", content),
            StreamlitUpload("copy1.md", content),
        ]
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["source"] == "copy1.md"


def test_identical_text_different_sources_both_kept(processor, monkeypatch):
    install_fake_converter(monkeypatch, markdown="# Header\n\nShared identical text.\n")
    markdown = b"# Header\n\nShared identical text.\n"

    chunks = processor.process(
        [
            StreamlitUpload("one.md", markdown),
            StreamlitUpload("two.md", markdown),
        ]
    )

    sources = [c.metadata["source"] for c in chunks]
    assert sources == ["one.md", "two.md"]
    assert all(c.page_content.strip() == "Shared identical text." for c in chunks)


def test_identical_text_different_metadata_both_kept(processor, cache_dir, monkeypatch):
    install_fake_converter(monkeypatch, markdown=SAME_TEXT_TWO_SECTIONS)
    markdown = b"# Alpha\n\nShared text.\n\n# Beta\n\nShared text.\n"

    chunks = processor.process([StreamlitUpload("sections.md", markdown)])

    headers = [c.metadata["Header 1"] for c in chunks]
    # The repeated text is kept once per distinct section metadata.
    assert headers == ["Alpha", "Beta"]
    assert all(c.metadata["source"] == "sections.md" for c in chunks)


def test_dedup_keeps_metadata_provenance_without_cache_aliases(
    processor, cache_dir, monkeypatch
):
    install_fake_converter(monkeypatch)
    content = b"# X\n\nBody.\n"

    processor.process([StreamlitUpload("first.md", content)])

    # Direct cache inspection: cached chunk still attributes the first name.
    entry = _read_cache_file(_cache_path(processor, content))
    assert entry["chunks"][0].metadata["source"] == "first.md"


# ---------------------------------------------------------------------------
# 9. Metadata preservation through cache hits
# ---------------------------------------------------------------------------


def test_cache_hit_preserves_heading_metadata_and_updates_source(
    processor, monkeypatch
):
    install_fake_converter(monkeypatch, markdown="# Head\n\nBody text.\n")
    content = b"# Head\n\nBody text.\n"

    processor.process([StreamlitUpload("first.md", content)])
    chunks = processor.process([StreamlitUpload("second.md", content)])

    assert chunks[0].metadata["Header 1"] == "Head"
    assert chunks[0].metadata["source"] == "second.md"
    assert "Body text." in chunks[0].page_content


def test_cache_hit_does_not_mutate_cached_entry(processor, monkeypatch):
    install_fake_converter(monkeypatch)
    content = b"# Head\n\nBody text.\n"

    processor.process([StreamlitUpload("first.md", content)])
    cache_file = _cache_path(processor, content)

    processor.process([StreamlitUpload("second.md", content)])

    entry = _read_cache_file(cache_file)
    assert entry["chunks"][0].metadata["source"] == "first.md"


# ---------------------------------------------------------------------------
# 10. Safe cache writing and temporary-file cleanup
# ---------------------------------------------------------------------------


def test_save_to_cache_creates_missing_directory(cache_dir, processor, tmp_path):
    # Wipe the directory: _save_to_cache must recreate it before writing.
    shutil.rmtree(processor.cache_dir)
    cache_path = processor.cache_dir / "abc.pkl"

    processor._save_to_cache([_chunk("t", "s")], cache_path)

    assert cache_path.is_file()
    assert not list(processor.cache_dir.glob("*.tmp"))


def test_save_to_cache_cleanup_on_serialization_failure(processor, monkeypatch):
    import document_processor.file_handler as handler

    def boom(obj, file):
        raise RuntimeError("cannot serialize")

    monkeypatch.setattr(handler.pickle, "dump", boom)
    cache_path = processor.cache_dir / "broken.pkl"

    with pytest.raises(RuntimeError, match="cannot serialize"):
        processor._save_to_cache([_chunk("t", "s")], cache_path)

    assert not cache_path.exists()
    assert not list(processor.cache_dir.glob("*.tmp"))


def test_save_to_cache_cleanup_on_replace_failure(processor, monkeypatch):
    import document_processor.file_handler as handler

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(handler.os, "replace", boom)
    cache_path = processor.cache_dir / "replace-fail.pkl"

    with pytest.raises(OSError, match="replace failed"):
        processor._save_to_cache([_chunk("t", "s")], cache_path)

    assert not cache_path.exists()
    assert not list(processor.cache_dir.glob("*.tmp"))


def test_save_to_cache_does_not_touch_unrelated_files(processor):
    bystander = processor.cache_dir / "innocent.txt"
    bystander.write_bytes(b"do not delete me")
    cache_path = processor.cache_dir / "target.pkl"

    processor._save_to_cache([_chunk("t", "s")], cache_path)

    assert bystander.read_bytes() == b"do not delete me"
    assert cache_path.is_file()


# ---------------------------------------------------------------------------
# 11. Concurrent writes to the same cache key
# ---------------------------------------------------------------------------


def test_concurrent_saves_same_cache_key(processor):
    cache_path = processor.cache_dir / "concurrent.pkl"

    def writer(index):
        chunk = _chunk(f"text {index}", f"src {index}.md")
        processor._save_to_cache([chunk], cache_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(writer, range(24)))

    # The final file is a complete, valid entry written by one of the racers.
    entry = _read_cache_file(cache_path)
    assert isinstance(entry, dict)
    assert all(isinstance(c, Document) for c in entry["chunks"])
    # No leftover temporary files.
    assert list(processor.cache_dir.glob("*.tmp")) == []


def test_concurrent_saves_use_unique_temp_files(processor, monkeypatch):
    """Each writer must use its own temporary path, never a shared name."""
    import document_processor.file_handler as handler

    cache_path = processor.cache_dir / "unique-tmp.pkl"
    observed = []
    lock = threading.Lock()
    real_replace = handler.os.replace

    def spy_replace(src, dst):
        with lock:
            observed.append(Path(src))
        real_replace(src, dst)

    monkeypatch.setattr(handler.os, "replace", spy_replace)

    def writer(index):
        processor._save_to_cache([_chunk(f"t{index}", "s")], cache_path)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(writer, range(12)))

    assert len(observed) == 12
    assert len(set(observed)) == len(observed)  # all temp paths unique
    assert all(p.suffix == ".tmp" for p in observed)
    assert cache_path.is_file()


# ---------------------------------------------------------------------------
# 12. Per-file failures continue the batch
# ---------------------------------------------------------------------------


def test_one_failing_file_does_not_stop_the_batch(processor, monkeypatch):
    import document_processor.file_handler as handler

    FakeConverter.inits = []
    FakeConverter.init_kwargs = []
    FakeConverter.converts = []

    class SelectiveConverter(FakeConverter):
        def convert(self, path):
            FakeConverter.converts.append(path)
            document_bytes = Path(path).read_bytes()
            if b"broken-marker" in document_bytes:
                raise RuntimeError("conversion backend exploded")
            return FakeConversion(DEMO_MARKDOWN)

    monkeypatch.setattr(handler, "DocumentConverter", SelectiveConverter)
    uploads = [
        StreamlitUpload("broken.md", b"broken-marker"),
        StreamlitUpload("healthy.md", DEMO_MARKDOWN.encode("utf-8")),
    ]

    chunks = processor.process(uploads)

    sources = {c.metadata["source"] for c in chunks}
    assert sources == {"healthy.md"}
    # The failed document left no cache entry behind.
    assert not _cache_path(processor, b"broken-marker").exists()


def test_converter_failure_can_be_retried(processor, monkeypatch):
    """A transient-conversion failure leaves no bogus cache behind."""
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN, fail=True)
    upload = StreamlitUpload("report.md", b"retry-me")

    assert processor.process([upload]) == []
    assert _cache_path(processor, b"retry-me").exists() is False

    # Second attempt as a fresh processor instance (the converter failure is
    # retried on a new request) succeeds and populates the cache.
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)
    retry_processor = DocumentProcessor()
    chunks = retry_processor.process([upload])
    assert [c.metadata["source"] for c in chunks] == ["report.md"]
    assert _cache_path(retry_processor, b"retry-me").exists()


def test_unreadable_upload_object_skipped_batch_continues(processor, monkeypatch):
    install_fake_converter(monkeypatch, markdown=SINGLE_CHUNK_MARKDOWN)
    named_broken = type("BrokenUpload", (), {"name": "weird.md"})()
    uploads = [
        named_broken,  # exposes a name, but no readable content
        StreamlitUpload("good.md", b"# H\n\nGood.\n"),
    ]

    chunks = processor.process(uploads)

    assert [c.metadata["source"] for c in chunks] == ["good.md"]
