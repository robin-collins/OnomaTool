"""Tests for --format flag override functionality."""

import pytest

from onomatool.file_dispatcher import FileDispatcher
from onomatool.processors.markitdown_processor import MarkitdownProcessor
from onomatool.processors.text_processor import TextProcessor


class TestFormatOverride:
    """Test FileDispatcher format_override parameter."""

    @pytest.fixture
    def config(self):
        """Basic config for FileDispatcher."""
        return {"markitdown": {}}

    @pytest.fixture
    def dispatcher(self, config):
        """Create FileDispatcher instance."""
        return FileDispatcher(config, debug=False)

    def test_no_override_uses_extension_based_routing_text(self, dispatcher):
        """No format override uses extension-based routing for text files."""
        processor = dispatcher.get_processor("test.txt")
        assert isinstance(processor, TextProcessor)

    def test_no_override_uses_extension_based_routing_pdf(self, dispatcher):
        """No format override uses extension-based routing for PDF files."""
        processor = dispatcher.get_processor("test.pdf")
        assert isinstance(processor, MarkitdownProcessor)

    def test_format_override_text_forces_text_processor_for_pdf(self, dispatcher):
        """format_override='text' forces TextProcessor even for .pdf."""
        processor = dispatcher.get_processor("test.pdf", format_override="text")
        assert isinstance(processor, TextProcessor)

    def test_format_override_pdf_forces_markitdown_for_txt(self, dispatcher):
        """format_override='pdf' forces MarkitdownProcessor even for .txt."""
        processor = dispatcher.get_processor("test.txt", format_override="pdf")
        assert isinstance(processor, MarkitdownProcessor)

    def test_format_override_markdown_forces_text_processor(self, dispatcher):
        """format_override='markdown' forces TextProcessor."""
        processor = dispatcher.get_processor("test.pdf", format_override="markdown")
        assert isinstance(processor, TextProcessor)

    def test_format_override_image_forces_markitdown_processor(self, dispatcher):
        """format_override='image' forces MarkitdownProcessor."""
        processor = dispatcher.get_processor("test.txt", format_override="image")
        assert isinstance(processor, MarkitdownProcessor)

    def test_format_override_docx_forces_markitdown_processor(self, dispatcher):
        """format_override='docx' forces MarkitdownProcessor."""
        processor = dispatcher.get_processor("test.txt", format_override="docx")
        assert isinstance(processor, MarkitdownProcessor)

    def test_format_override_none_uses_default_behavior(self, dispatcher):
        """format_override=None uses default extension-based behavior."""
        # Text file -> TextProcessor
        processor = dispatcher.get_processor("test.txt", format_override=None)
        assert isinstance(processor, TextProcessor)

        # PDF file -> MarkitdownProcessor
        processor = dispatcher.get_processor("test.pdf", format_override=None)
        assert isinstance(processor, MarkitdownProcessor)

    def test_format_override_text_for_various_extensions(self, dispatcher):
        """format_override='text' works for various file extensions."""
        extensions = [".pdf", ".docx", ".png", ".jpg", ".html"]
        for ext in extensions:
            processor = dispatcher.get_processor(f"test{ext}", format_override="text")
            assert isinstance(processor, TextProcessor), f"Failed for extension {ext}"

    def test_format_override_pdf_for_various_extensions(self, dispatcher):
        """format_override='pdf' works for various file extensions."""
        extensions = [".txt", ".md", ".json", ".csv", ".py"]
        for ext in extensions:
            processor = dispatcher.get_processor(f"test{ext}", format_override="pdf")
            assert isinstance(processor, MarkitdownProcessor), f"Failed for extension {ext}"

    def test_format_override_takes_precedence_over_extension(self, dispatcher):
        """format_override always takes precedence over file extension."""
        # Markdown file with text override -> TextProcessor
        processor = dispatcher.get_processor("test.md", format_override="pdf")
        assert isinstance(processor, MarkitdownProcessor)

        # PDF file with text override -> TextProcessor
        processor = dispatcher.get_processor("test.pdf", format_override="text")
        assert isinstance(processor, TextProcessor)

    def test_text_extension_routing_without_override(self, dispatcher):
        """Text extensions route to TextProcessor without override."""
        text_extensions = [".txt", ".md", ".py", ".js", ".json", ".csv", ".xml"]
        for ext in text_extensions:
            processor = dispatcher.get_processor(f"test{ext}")
            assert isinstance(processor, TextProcessor), f"Failed for extension {ext}"

    def test_non_text_extension_routing_without_override(self, dispatcher):
        """Non-text extensions route to MarkitdownProcessor without override."""
        non_text_extensions = [".pdf", ".docx", ".pptx", ".jpg", ".png"]
        for ext in non_text_extensions:
            processor = dispatcher.get_processor(f"test{ext}")
            assert isinstance(processor, MarkitdownProcessor), f"Failed for extension {ext}"
