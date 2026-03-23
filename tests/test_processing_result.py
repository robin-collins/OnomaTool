"""Tests for the ProcessingResult dataclass."""

from onomatool.models import ProcessingResult


class TestProcessingResult:
    """Test suite for ProcessingResult dataclass."""

    def test_default_fields(self):
        """TC-PR-001: Test default fields (empty markdown, empty images list, None tempdir, empty source_path, empty file_type)."""
        result = ProcessingResult()

        assert result.markdown == ""
        assert result.images == []
        assert result.tempdir is None
        assert result.source_path == ""
        assert result.file_type == ""

    def test_all_fields_populated(self):
        """TC-PR-002: Test all fields populated with valid data."""
        tempdir_obj = object()  # Mock temporary directory object
        result = ProcessingResult(
            markdown="# Document Title\n\nSome content here.",
            images=["/path/to/image1.png", "/path/to/image2.png"],
            tempdir=tempdir_obj,
            source_path="/path/to/source/document.pdf",
            file_type="pdf",
        )

        assert result.markdown == "# Document Title\n\nSome content here."
        assert result.images == ["/path/to/image1.png", "/path/to/image2.png"]
        assert result.tempdir is tempdir_obj
        assert result.source_path == "/path/to/source/document.pdf"
        assert result.file_type == "pdf"

    def test_has_images_property_with_images(self):
        """TC-PR-003: Test has_images property returns True when images list is non-empty."""
        result = ProcessingResult(
            markdown="Content",
            images=["/path/to/image.png"],
            source_path="/path/to/doc.pdf",
        )

        assert result.has_images is True

    def test_has_images_property_without_images(self):
        """TC-PR-003: Test has_images property returns False when images list is empty."""
        result = ProcessingResult(markdown="Content", source_path="/path/to/doc.txt")

        assert result.has_images is False

    def test_minimal_creation_with_markdown_and_source_path(self):
        """TC-PR-004: Test that ProcessingResult can be created with just markdown and source_path."""
        result = ProcessingResult(
            markdown="Simple text content", source_path="/path/to/file.txt"
        )

        assert result.markdown == "Simple text content"
        assert result.source_path == "/path/to/file.txt"
        assert result.images == []
        assert result.tempdir is None
        assert result.file_type == ""

    def test_images_defaults_to_empty_list_not_none(self):
        """TC-PR-005: Test that images defaults to empty list (not None)."""
        result = ProcessingResult()

        assert result.images is not None
        assert result.images == []
        assert isinstance(result.images, list)

    def test_has_images_with_multiple_images(self):
        """Test has_images property with multiple images."""
        result = ProcessingResult(
            images=[
                "/path/to/image1.png",
                "/path/to/image2.png",
                "/path/to/image3.png",
            ]
        )

        assert result.has_images is True
        assert len(result.images) == 3

    def test_empty_string_vs_none_for_string_fields(self):
        """Test that string fields default to empty string, not None."""
        result = ProcessingResult()

        assert result.markdown is not None
        assert result.source_path is not None
        assert result.file_type is not None
        assert isinstance(result.markdown, str)
        assert isinstance(result.source_path, str)
        assert isinstance(result.file_type, str)

    def test_mutable_default_for_images_list(self):
        """Test that each instance gets its own images list (no shared mutable default)."""
        result1 = ProcessingResult()
        result2 = ProcessingResult()

        result1.images.append("/path/to/image.png")

        assert len(result1.images) == 1
        assert len(result2.images) == 0
        assert result1.images is not result2.images
