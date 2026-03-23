"""Shared encoding detection and UTF-8 normalization utilities."""

import logging
import os
import tempfile

import chardet

from onomatool.constants import TEXT_EXTENSIONS

logger = logging.getLogger(__name__)


def detect_encoding(file_path: str) -> str:
    """Detect the encoding of a text file using chardet.

    Returns detected encoding string (defaults to 'utf-8' if detection fails).
    """
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read(10240)
            if not raw_data:
                return "utf-8"

            result = chardet.detect(raw_data)
            encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0)

            # Handle chardet misidentifying UTF-8 as Windows-1252
            if encoding and encoding.lower() == "windows-1252":
                try:
                    raw_data.decode("utf-8")
                    return "utf-8"
                except UnicodeDecodeError:
                    pass

            if not encoding or confidence < 0.7:
                return "utf-8"

            return encoding

    except Exception as e:
        logger.warning("Encoding detection failed for %s: %s", file_path, e)
        return "utf-8"


def ensure_utf8_file(file_path: str, debug: bool = False) -> str:
    """Ensure a file is UTF-8 encoded, creating a temp copy if needed.

    Returns path to UTF-8 encoded file (original if already UTF-8).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in TEXT_EXTENSIONS:
        return file_path

    detected_encoding = detect_encoding(file_path)

    if detected_encoding.lower() in ("utf-8", "utf8"):
        try:
            with open(file_path, encoding="utf-8") as test_file:
                test_file.read(1024)
            if not debug:
                return file_path
        except UnicodeDecodeError:
            pass
    elif detected_encoding.lower() == "ascii":
        if not debug:
            return file_path

    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="onoma_utf8_")
        with (
            open(file_path, encoding=detected_encoding, errors="replace") as source,
            os.fdopen(temp_fd, "w", encoding="utf-8") as target,
        ):
            target.write(source.read())
        return temp_path
    except Exception as e:
        logger.warning("UTF-8 conversion failed for %s: %s", file_path, e)
        try:
            if "temp_path" in locals():
                os.unlink(temp_path)
        except (OSError, FileNotFoundError):
            pass
        return file_path


def cleanup_temp_encoding_file(original_path: str, temp_path: str) -> None:
    """Clean up temporary UTF-8 file if it's different from original."""
    if temp_path != original_path:
        try:
            os.unlink(temp_path)
        except Exception as e:
            logger.warning("Failed to clean up temp file %s: %s", temp_path, e)
