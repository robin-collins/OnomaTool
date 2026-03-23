from .processors.markitdown_processor import MarkitdownProcessor
from .processors.text_processor import TextProcessor


class FileDispatcher:
    """Routes files to appropriate processors based on file type"""

    def __init__(self, config: dict, debug: bool = False):
        self.config = config
        self.debug = debug

        # Text file extensions that should be processed directly without MarkItDown
        self.text_extensions = {
            ".txt",
            ".md",
            ".note",
            ".text",
            ".log",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".py",
            ".js",
            ".css",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
        }

        self.processors: dict[str, object] = {}
        # Initialize text processor for all text extensions
        text_processor = TextProcessor()
        for ext in self.text_extensions:
            self.processors[ext] = text_processor

        # Initialize markitdown processor for other formats
        self.markitdown_processor = MarkitdownProcessor(
            self.config.get("markitdown", {}), debug=debug
        )

    def get_processor(self, file_path: str, format_override: str | None = None) -> object:
        """Get appropriate processor for the given file."""
        if format_override:
            if format_override in ("text", "markdown"):
                return TextProcessor()
            # pdf, docx, image all use markitdown
            return self.markitdown_processor

        from pathlib import Path

        file_ext = Path(file_path).suffix.lower()

        if file_ext in self.text_extensions:
            return self.processors[file_ext]
        return self.markitdown_processor

    def process(self, file_path: str, format_override: str | None = None):
        """Process a file using the appropriate processor."""
        processor = self.get_processor(file_path, format_override)
        return processor.process(file_path)
