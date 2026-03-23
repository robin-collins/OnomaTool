"""File dispatcher that routes files to appropriate processors based on type."""

import logging

from .constants import TEXT_EXTENSIONS
from .processors import (
    ProcessorProtocol,
    discover_entry_point_plugins,
    load_extra_processors,
)
from .processors.markitdown_processor import MarkitdownProcessor
from .processors.text_processor import TextProcessor

logger = logging.getLogger(__name__)


class FileDispatcher:
    """Routes files to appropriate processors based on file type"""

    def __init__(self, config: dict, debug: bool = False):
        self.config = config
        self.debug = debug

        self.text_extensions = TEXT_EXTENSIONS

        self.processors: dict[str, object] = {}
        # Initialize text processor for all text extensions
        text_processor = TextProcessor()
        for ext in self.text_extensions:
            self.processors[ext] = text_processor

        # Initialize markitdown processor for other formats
        self.markitdown_processor = MarkitdownProcessor(
            self.config.get("markitdown", {}), debug=debug
        )

        # Load plugins (entry_points + extra_processors from config)
        self._plugins: list[ProcessorProtocol] = []
        self._plugins.extend(discover_entry_point_plugins())
        extra = config.get("extra_processors", [])
        if extra:
            self._plugins.extend(load_extra_processors(extra))
        if self._plugins:
            logger.debug("Loaded %d processor plugin(s)", len(self._plugins))

    def get_processor(
        self, file_path: str, format_override: str | None = None
    ) -> object:
        """Get appropriate processor for the given file.

        Built-in processors take precedence over plugins for their
        registered extensions.
        """
        if format_override:
            if format_override in ("text", "markdown"):
                return TextProcessor()
            # pdf, docx, image all use markitdown
            return self.markitdown_processor

        from pathlib import Path

        file_ext = Path(file_path).suffix.lower()

        # Built-in processors take precedence
        if file_ext in self.text_extensions:
            return self.processors[file_ext]

        # Check plugins (first match wins)
        for plugin in self._plugins:
            if plugin.can_process(file_path):
                return plugin

        return self.markitdown_processor

    def process(self, file_path: str, format_override: str | None = None):
        """Process a file using the appropriate processor."""
        processor = self.get_processor(file_path, format_override)
        return processor.process(file_path)
