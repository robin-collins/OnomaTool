"""Tests for image utilities, specifically SVG to PNG conversion."""

import os

import pytest

from onomatool.utils.image_utils import convert_svg_to_png

# Minimal valid SVG content for testing
VALID_SVG_SIMPLE = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
<rect width="100" height="100" fill="red"/>
</svg>"""

INVALID_SVG_CONTENT = """<this is not valid svg content at all>"""


def test_convert_svg_to_png_with_valid_simple_svg(tmp_path):
    """TC-IU-001: Test convert_svg_to_png with a valid simple SVG string."""
    # Create a minimal SVG file
    svg_file = tmp_path / "test.svg"
    svg_file.write_text(VALID_SVG_SIMPLE, encoding="utf-8")

    # Convert to PNG
    png_path = convert_svg_to_png(str(svg_file), str(tmp_path))

    # Verify the conversion succeeded and returned a path
    assert png_path is not None
    assert isinstance(png_path, str)


def test_convert_svg_to_png_returns_png_extension(tmp_path):
    """TC-IU-002: Test convert_svg_to_png returns a path ending in .png."""
    # Create a minimal SVG file
    svg_file = tmp_path / "test.svg"
    svg_file.write_text(VALID_SVG_SIMPLE, encoding="utf-8")

    # Convert to PNG
    png_path = convert_svg_to_png(str(svg_file), str(tmp_path))

    # Verify the path ends with .png
    assert png_path.endswith(".png")


def test_convert_svg_to_png_with_invalid_svg_raises_or_fails(tmp_path):
    """TC-IU-003: Test convert_svg_to_png with invalid SVG content raises an exception or returns gracefully."""
    # Create an invalid SVG file
    svg_file = tmp_path / "invalid.svg"
    svg_file.write_text(INVALID_SVG_CONTENT, encoding="utf-8")

    # Attempt conversion - should raise an error (ParseError, RuntimeError, etc.)
    with pytest.raises(Exception):  # noqa: B017
        convert_svg_to_png(str(svg_file), str(tmp_path))


def test_convert_svg_to_png_output_file_exists(tmp_path):
    """TC-IU-004: Test convert_svg_to_png output file actually exists after conversion."""
    # Create a minimal SVG file
    svg_file = tmp_path / "test.svg"
    svg_file.write_text(VALID_SVG_SIMPLE, encoding="utf-8")

    # Convert to PNG
    png_path = convert_svg_to_png(str(svg_file), str(tmp_path))

    # Verify the output file exists
    assert os.path.exists(png_path)
    assert os.path.isfile(png_path)


def test_convert_svg_to_png_with_nonexistent_input_file_raises_error(tmp_path):
    """TC-IU-005: Test convert_svg_to_png with nonexistent input file raises an error."""
    # Attempt to convert a file that doesn't exist
    nonexistent_file = tmp_path / "does_not_exist.svg"

    # Should raise FileNotFoundError or similar
    with pytest.raises((FileNotFoundError, OSError)):
        convert_svg_to_png(str(nonexistent_file), str(tmp_path))
