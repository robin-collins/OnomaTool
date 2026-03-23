"""MarkItDown-based processor for documents, PDFs, PPTX, and SVG."""

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)
from markitdown import MarkItDown

from onomatool.constants import TEXT_EXTENSIONS
from onomatool.models import ProcessingResult
from onomatool.utils.encoding import (
    cleanup_temp_encoding_file,
    detect_encoding,
    ensure_utf8_file,
)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
try:
    from PIL import Image, ImageDraw
    from pptx import Presentation
except ImportError:
    Presentation = None
    Image = None
    ImageDraw = None
try:
    import cairosvg
except ImportError:
    cairosvg = None


def _make_tempdir(prefix: str, debug: bool):
    """Create a temp directory. In debug mode, it won't auto-cleanup."""
    if debug:
        tempdir_path = tempfile.mkdtemp(prefix=prefix)
        return type("TempDir", (), {"name": tempdir_path, "cleanup": lambda: None})()
    return tempfile.TemporaryDirectory()


def _save_debug_markdown(tempdir, text_content: str) -> None:
    """Save extracted markdown to tempdir for debug inspection."""
    markdown_path = os.path.join(tempdir.name, "extracted_content.md")
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(text_content)


def _extract_pdf_images(file_path: str, tempdir) -> list[str]:
    """Extract page images from a PDF using PyMuPDF."""
    images = []
    doc = fitz.open(file_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        img_path = os.path.join(tempdir.name, f"page_{page_num + 1}.png")
        pix.save(img_path)
        images.append(img_path)
    doc.close()
    return images


def _extract_pptx_images(file_path: str, tempdir) -> list[str] | None:
    """Convert PPTX to PDF via soffice, then extract page images via PyMuPDF.

    Returns list of image paths, or None on failure.
    """
    basename = os.path.splitext(os.path.basename(file_path))[0]
    pdf_path = os.path.join(tempdir.name, f"{basename}.pdf")

    soffice_result = subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            file_path,
            "--outdir",
            tempdir.name,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if soffice_result.returncode != 0 or not os.path.exists(pdf_path):
        return None

    if fitz is None:
        return None

    images = []
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        img_path = os.path.join(tempdir.name, f"{basename}_{page_num + 1}.png")
        pix.save(img_path)
        images.append(img_path)
    doc.close()
    return images if images else None


class MarkitdownProcessor:
    """Processor for multiple formats using markitdown library with UTF-8 encoding support."""

    def __init__(self, config: dict, debug: bool = False):
        self.config = config
        self.debug = debug
        docintel_endpoint = config.get("docintel_endpoint")
        self.md = MarkItDown(
            enable_plugins=config.get("enable_plugins", False),
            docintel_endpoint=docintel_endpoint or None,
            llm_model=config.get("llm_model", "gpt-4o"),
        )

    # Delegate encoding methods to shared utils (preserve API for existing callers)
    def detect_encoding(self, file_path: str) -> str:
        return detect_encoding(file_path)

    def ensure_utf8_file(self, file_path: str) -> str:
        return ensure_utf8_file(file_path, debug=self.debug)

    def cleanup_temp_encoding_file(self, original_path: str, temp_path: str):
        return cleanup_temp_encoding_file(original_path, temp_path)

    def process(self, file_path: str) -> ProcessingResult | None:
        """Process a file using markitdown with proper UTF-8 encoding handling."""
        utf8_file_path = None
        try:
            utf8_file_path = self.ensure_utf8_file(file_path)
            ext = os.path.splitext(file_path)[1].lower()

            result = self._convert_with_fallback(utf8_file_path, ext, file_path)
            if result is None:
                return None

            if ext == ".pdf" and fitz is not None:
                return self._process_pdf(file_path, result)
            if ext == ".pptx":
                return self._process_pptx(file_path, result)
            if ext == ".svg":
                return self._process_svg(file_path, result)
            return self._process_generic(file_path, ext, result)

        except UnicodeDecodeError as e:
            logger.error("Unicode decode error processing %s: %s", file_path, e)
            return None
        except Exception as e:
            logger.error("Failed to process %s: %s", file_path, e)
            return None
        finally:
            if utf8_file_path:
                cleanup_temp_encoding_file(file_path, utf8_file_path)

    def _convert_with_fallback(self, utf8_file_path: str, ext: str, file_path: str):
        """Try MarkItDown conversion, fall back to direct text read on Unicode errors."""
        try:
            return self.md.convert(utf8_file_path)
        except Exception as conversion_error:
            error_str = str(conversion_error)
            is_unicode_error = (
                "UnicodeDecodeError" in error_str or "ascii" in error_str.lower()
            )
            if is_unicode_error and ext in TEXT_EXTENSIONS:
                try:
                    with open(utf8_file_path, encoding="utf-8", errors="replace") as f:
                        content = f.read()

                    class MockResult:
                        def __init__(self, text):
                            self.text_content = text

                    return MockResult(content)
                except Exception as e:
                    logger.error("Fallback text read failed for %s: %s", file_path, e)
                    raise conversion_error from None
            raise

    def _process_pdf(self, file_path: str, result) -> ProcessingResult:
        tempdir = _make_tempdir("onoma_pdf_", self.debug)
        images = _extract_pdf_images(file_path, tempdir)
        if self.debug:
            _save_debug_markdown(tempdir, result.text_content)
        return ProcessingResult(
            markdown=result.text_content,
            images=images,
            tempdir=tempdir,
            source_path=file_path,
            file_type="pdf",
        )

    def _process_pptx(self, file_path: str, result) -> ProcessingResult | None:
        tempdir = _make_tempdir("onoma_pptx_", self.debug)
        try:
            images = _extract_pptx_images(file_path, tempdir)
            if images is None:
                return None
            if self.debug:
                _save_debug_markdown(tempdir, result.text_content)
            return ProcessingResult(
                markdown=result.text_content,
                images=images,
                tempdir=tempdir,
                source_path=file_path,
                file_type="pptx",
            )
        except Exception as e:
            logger.error("PPTX slide image extraction failed for %s: %s", file_path, e)
            return None

    def _process_svg(self, file_path: str, result) -> ProcessingResult:
        if self.debug and result.text_content:
            tempdir = _make_tempdir("onoma_svg_md_", self.debug)
            _save_debug_markdown(tempdir, result.text_content)
            return ProcessingResult(
                markdown=result.text_content,
                tempdir=tempdir,
                source_path=file_path,
                file_type="svg",
            )
        return ProcessingResult(
            markdown=result.text_content,
            source_path=file_path,
            file_type="svg",
        )

    def _process_generic(self, file_path: str, ext: str, result) -> ProcessingResult:
        file_ext = ext.lstrip(".")
        if self.debug and result.text_content:
            tempdir = _make_tempdir(f"onoma_{file_ext}_", self.debug)
            _save_debug_markdown(tempdir, result.text_content)
            return ProcessingResult(
                markdown=result.text_content,
                tempdir=tempdir,
                source_path=file_path,
                file_type=file_ext,
            )
        return ProcessingResult(
            markdown=result.text_content,
            source_path=file_path,
            file_type=file_ext,
        )
