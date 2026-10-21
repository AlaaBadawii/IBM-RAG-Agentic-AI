import hashlib
import json
import os
import pickle
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Support running this file directly or importing it as a module.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docling.backend.docling_parse_v2_backend import (  # noqa: E402
    DoclingParseV2DocumentBackend,
)
from docling.datamodel.base_models import ConversionStatus, InputFormat  # noqa: E402
from docling.datamodel.pipeline_options import PdfPipelineOptions  # noqa: E402
from docling.document_converter import DocumentConverter, PdfFormatOption  # noqa: E402
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_text_splitters import MarkdownHeaderTextSplitter  # noqa: E402

from config.settings import settings  # noqa: E402
from utils.logging import logger  # noqa: E402


class DocumentProcessor:
    """Validate, process, cache, and deduplicate uploaded documents."""

    CACHE_TTL = timedelta(hours=24)

    def __init__(self) -> None:
        self.headers = [
            ("#", "Header 1"),
            ("##", "Header 2"),
        ]

        self.cache_dir = Path(settings.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.allowed_extensions = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in settings.ALLOWED_TYPES
        }

        # Docling pipelines and models are initialized on first convert and
        # cached on the converter instance, so it is reused across files.
        # A DocumentConverter is not documented as thread-safe, which matches
        # this class processing files sequentially.
        self._converter: DocumentConverter | None = None

    def _get_converter(self) -> DocumentConverter:
        """Return the lazily created, reused Docling converter.

        Docling defaults to OCR and table-structure extraction for PDFs. Both
        models are expensive and OCR is unnecessary for PDFs that already have
        a text layer, so the defaults are configurable and disabled by default.
        A per-document timeout prevents an unexpectedly expensive conversion
        from blocking the request indefinitely.
        """
        if self._converter is None:
            pipeline_options = PdfPipelineOptions(
                do_ocr=settings.DOCLING_DO_OCR,
                do_table_structure=settings.DOCLING_DO_TABLE_STRUCTURE,
                document_timeout=settings.DOCLING_DOCUMENT_TIMEOUT,
            )
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=StandardPdfPipeline,
                        backend=DoclingParseV2DocumentBackend,
                        pipeline_options=pipeline_options,
                    )
                }
            )
            logger.info(
                "Docling PDF pipeline initialized "
                f"(do_ocr={settings.DOCLING_DO_OCR}, "
                f"do_table_structure={settings.DOCLING_DO_TABLE_STRUCTURE}, "
                f"document_timeout={settings.DOCLING_DOCUMENT_TIMEOUT}s)"
            )
        return self._converter

    def validate_files(self, files: list[Any]) -> None:
        """Validate extensions and framework-reported sizes before processing.

        ``size`` is only a cheap pre-check: it can be missing, stale, or
        inaccurate, so ``process`` re-validates the actual byte counts once
        each file's content is read.
        """
        total_reported_size = 0

        for file in files:
            reported_size = getattr(file, "size", None)

            if isinstance(reported_size, int) and not isinstance(reported_size, bool):
                total_reported_size += reported_size

                if reported_size > settings.MAX_FILE_SIZE:
                    raise ValueError(
                        f"File {self._resolve_file_name(file)} exceeds the "
                        f"maximum size of {settings.MAX_FILE_SIZE} bytes."
                    )

            extension = Path(self._resolve_file_name(file) or "").suffix.lower()

            if extension not in self.allowed_extensions:
                raise ValueError(
                    f"File {self._resolve_file_name(file)} has an unsupported file type."
                )

        if total_reported_size > settings.MAX_TOTAL_SIZE:
            raise ValueError(
                "Total file size exceeds the maximum limit of "
                f"{settings.MAX_TOTAL_SIZE} bytes."
            )

    def process(self, files: list[Any]) -> list[Document]:
        """Process uploaded files, reuse valid caches, and deduplicate chunks."""
        self.validate_files(files)

        all_chunks: list[Document] = []
        seen_keys: set[str] = set()
        total_bytes = 0

        for file in files:
            try:
                file_name = self._resolve_file_name(file) or "unknown"

                file_content = self._read_file_content(file)
                file_hash = self._generate_hash(file_content)
                cache_path = self.cache_dir / f"{file_hash}.pkl"

                # ``size`` may be missing or inaccurate, so enforce the size
                # limits on the actual bytes before any expensive conversion.
                content_size = len(file_content)

                if content_size > settings.MAX_FILE_SIZE:
                    raise ValueError(
                        f"File {file_name} exceeds the maximum size of "
                        f"{settings.MAX_FILE_SIZE} bytes."
                    )

                total_bytes += content_size

                if total_bytes > settings.MAX_TOTAL_SIZE:
                    raise ValueError(
                        "Total file size exceeds the maximum limit of "
                        f"{settings.MAX_TOTAL_SIZE} bytes."
                    )

                cache_entry = self._load_cache_entry(cache_path)

                if cache_entry is not None:
                    logger.info(f"Loading from cache: {file_name}")
                    # Cached chunks belong to whichever upload happened to
                    # populate the cache first, so re-attribute every chunk to
                    # this upload without mutating the shared cache entry.
                    chunks = self._attribute_source(cache_entry["chunks"], file_name)
                else:
                    logger.info(f"Processing and caching: {file_name}")

                    chunks = self._process_file(file_name, file_content)
                    self._save_to_cache(chunks, cache_path)

                # Remove chunks that are exact duplicates of earlier chunks in
                # this batch. The key covers content and metadata so chunks
                # from different sources or sections are never dropped: the
                # repeated text would silently lose a valid citation target.
                for chunk in chunks:
                    chunk_key = self._dedup_key(chunk)

                    if chunk_key not in seen_keys:
                        all_chunks.append(chunk)
                        seen_keys.add(chunk_key)

            except Exception:
                logger.exception(
                    f"Failed to process {self._resolve_file_name(file) or 'unknown'}"
                )
                continue

        logger.info(f"Total unique chunks: {len(all_chunks)}")
        return all_chunks

    @staticmethod
    def _resolve_file_name(file: Any) -> str | None:
        """Best-effort filename for any supported upload object shape.

        Gradio's ``FileData`` carries the upload on disk in ``path`` and the
        original name in ``orig_name``, while Streamlit-style uploads expose
        ``name`` and ``read()``/``getvalue()`` directly.
        """
        for attribute in ("name", "orig_name"):
            value = getattr(file, attribute, None)

            if isinstance(value, str) and value:
                return value

        path = getattr(file, "path", None)

        if isinstance(path, str) and path:
            return Path(path).name

        return None

    @staticmethod
    def _attribute_source(
        chunks: list[Document],
        file_name: str,
    ) -> list[Document]:
        """Copy chunks with ``source`` re-attributed to the current upload."""
        return [
            Document(
                page_content=chunk.page_content,
                metadata={**chunk.metadata, "source": file_name},
            )
            for chunk in chunks
        ]

    @staticmethod
    def _read_file_content(file: Any) -> bytes:
        """Read an uploaded file as bytes without assuming its name is a disk path.

        Supported upload shapes, in order: objects with ``getvalue()``
        (Streamlit uploads), readable streams (resetting and restoring the
        position when possible), and uploads that only reference a file on
        disk (Gradio's ``path``, or ``name`` when it is an existing path).
        Text content is normalized by encoding it as UTF-8.
        """
        if hasattr(file, "getvalue"):
            content = file.getvalue()

            if isinstance(content, str):
                return content.encode("utf-8")

            if isinstance(content, (bytes, bytearray, memoryview)):
                return bytes(content)

            raise TypeError(
                f"Unsupported upload content type: {type(content).__name__}"
            )

        if hasattr(file, "read"):
            can_seek = hasattr(file, "seek")

            if can_seek:
                try:
                    file.seek(0)
                except (OSError, ValueError):
                    pass

            try:
                content = file.read()
            finally:
                if can_seek:
                    try:
                        file.seek(0)
                    except (OSError, ValueError):
                        pass

            if isinstance(content, str):
                return content.encode("utf-8")

            if isinstance(content, (bytes, bytearray, memoryview)):
                return bytes(content)

            raise TypeError(
                f"Unsupported upload content type: {type(content).__name__}"
            )

        disk_path = getattr(file, "path", None)

        if not (isinstance(disk_path, str) and disk_path and Path(disk_path).is_file()):
            name = getattr(file, "name", None)
            disk_path = (
                name
                if isinstance(name, str) and name and Path(name).is_file()
                else None
            )

        if disk_path is not None:
            return Path(disk_path).read_bytes()

        raise TypeError("Upload object does not expose readable content.")

    def _process_file(
        self,
        file_name: str,
        file_content: bytes,
    ) -> list[Document]:
        """Convert a supported document to Markdown and split by headers."""
        extension = Path(file_name).suffix.lower()

        if extension not in self.allowed_extensions:
            logger.warning(f"Skipping unsupported file type: {file_name}")
            return []

        if extension == ".txt":
            # The installed Docling version (2.15.0) has no plain-text
            # backend, so a ``.txt`` upload would always fail conversion.
            # Plain text is treated directly as Markdown-compatible input
            # and chunked with the same splitter.
            markdown = file_content.decode("utf-8")
        else:
            # Docling's converter accepts filesystem paths. Write uploaded
            # bytes to a temporary file when the upload is not on disk.
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"document{extension}"
                temp_path.write_bytes(file_content)

                logger.info(f"Starting Docling conversion: {file_name}")
                started = time.perf_counter()

                try:
                    result = self._get_converter().convert(str(temp_path))
                except Exception:
                    elapsed = time.perf_counter() - started
                    logger.exception(
                        f"Docling conversion failed after {elapsed:.2f}s: {file_name}"
                    )
                    raise

                elapsed = time.perf_counter() - started
                status = result.status
                page_count = len(result.pages)
                logger.info(
                    f"Docling conversion finished in {elapsed:.2f}s: {file_name} "
                    f"(status={status.value}, pages={page_count})"
                )

                # ``DocumentConverter.convert`` treats PARTIAL_SUCCESS as
                # non-fatal. A timeout or per-page failure must not be cached
                # and presented as a complete document.
                if status != ConversionStatus.SUCCESS:
                    raise RuntimeError(
                        f"Docling conversion for {file_name} finished with "
                        f"status {status.value}; refusing an incomplete document."
                    )

                markdown = result.document.export_to_markdown()

        if not markdown.strip():
            raise ValueError(
                f"No readable text was extracted from {file_name}. "
                "If this is a scanned PDF, enable DOCLING_DO_OCR."
            )

        splitter = MarkdownHeaderTextSplitter(self.headers)
        chunks = splitter.split_text(markdown)

        if not chunks:
            raise ValueError(f"No readable text chunks were extracted from {file_name}.")

        # Attach the original filename to each chunk's metadata.
        for chunk in chunks:
            chunk.metadata["source"] = file_name

        return chunks

    @staticmethod
    def _generate_hash(content: bytes) -> str:
        """Generate a SHA-256 hash of the provided bytes."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _dedup_key(chunk: Document) -> str:
        """Hash the chunk content together with its metadata.

        Text alone is not a sufficient deduplication key: identical text from
        a different source (or under different headings) is a distinct
        retrieval/citation target, so it must not be dropped.
        """
        payload = json.dumps(
            {"content": chunk.page_content, "metadata": chunk.metadata},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _save_to_cache(
        self,
        chunks: list[Document],
        cache_path: Path,
    ) -> None:
        """Persist processed chunks and the cache creation timestamp."""
        cache_data = {
            "timestamp": datetime.now().timestamp(),
            "chunks": chunks,
        }

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning(f"Could not create cache directory: {self.cache_dir}")
            raise

        # Unique temporary file per writer: concurrent saves for the same
        # cache key must not race on a shared ``.tmp`` path. ``mkstemp``
        # creates the file next to the final cache file, keeping the atomic
        # same-filesystem ``os.replace`` behavior.
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.cache_dir,
            prefix=f"{cache_path.stem}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        closed = False

        try:
            with os.fdopen(descriptor, "wb") as cache_file:
                closed = True
                pickle.dump(cache_data, cache_file)

            # Avoid exposing a partially written cache file.
            os.replace(temporary_path, cache_path)
        finally:
            # ``os.replace`` moved the temporary file away, so cleanup only
            # applies to remaining failures; cleanup errors must not hide
            # the original exception.
            try:
                if not closed:
                    os.close(descriptor)
            except OSError:
                logger.warning(
                    f"Could not close temporary cache file: {temporary_path}"
                )

            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    f"Could not remove temporary cache file: {temporary_path}"
                )

    def _load_cache_entry(self, cache_path: Path) -> dict[str, Any] | None:
        """Return a structurally valid and unexpired cache entry, else None.

        Cache files are trusted local data: untrusted pickle files cannot be
        made safe by post-load validation because deserialization executes
        code before any check. The single read covers both expiry and
        structural validation, so a cache hit deserializes each file once.
        """
        if not cache_path.is_file():
            return None

        try:
            with open(cache_path, "rb") as cache_file:
                data = pickle.load(cache_file)

            if not isinstance(data, dict):
                raise ValueError("Cache entry is not a dictionary.")

            timestamp = data.get("timestamp")

            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                raise ValueError("Cache entry has an invalid timestamp.")

            self._validate_cached_chunks(data)

            cache_time = datetime.fromtimestamp(timestamp)
            cache_age = datetime.now() - cache_time

            if not timedelta(0) <= cache_age < self.CACHE_TTL:
                raise ValueError("Cache entry is expired or future-dated.")

            return data

        except (
            OSError,
            EOFError,
            pickle.UnpicklingError,
            AttributeError,
            ValueError,
            TypeError,
            OverflowError,
            ImportError,
        ):
            logger.warning(f"Invalid or expired cache: {cache_path}")
            return None

    @staticmethod
    def _validate_cached_chunks(data: dict[str, Any]) -> None:
        """Raise ``ValueError`` unless the entry holds valid document chunks."""
        chunks = data.get("chunks")

        if not isinstance(chunks, list) or not all(
            isinstance(chunk, Document) for chunk in chunks
        ):
            raise ValueError("Cache contains invalid document chunks.")
