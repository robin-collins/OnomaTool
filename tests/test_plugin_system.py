"""Tests for processor plugin system via entry_points.

TEST_SPECS §19.2: 4 tests TC-PL-001 to TC-PL-004.
- Plugin discovered via entry_points
- can_process() respected by dispatcher
- Built-in processors take precedence over plugins
- Plugin ProcessingResult works end-to-end
"""

from unittest.mock import MagicMock, patch

from onomatool.file_dispatcher import FileDispatcher
from onomatool.models import ProcessingResult
from onomatool.processors import ProcessorProtocol, discover_entry_point_plugins


class FakePlugin:
    """A fake processor plugin that implements ProcessorProtocol."""

    def can_process(self, file_path: str) -> bool:
        return file_path.endswith(".xyz")

    def process(self, file_path: str) -> ProcessingResult | None:
        return ProcessingResult(
            markdown=f"Processed by FakePlugin: {file_path}",
            source_path=file_path,
            file_type="xyz",
        )


class BadPlugin:
    """A plugin that does NOT implement ProcessorProtocol (missing process method)."""

    def can_process(self, file_path: str) -> bool:
        return True


class TestPluginDiscovery:
    """Tests for plugin discovery via entry_points."""

    def test_plugin_discovered_via_entry_points(self):
        """TC-PL-001: Plugins registered via entry_points group are discovered.

        When a package registers an entry_point in the 'onomatool.processors' group,
        discover_entry_point_plugins() should find and instantiate it.
        """
        mock_ep = MagicMock()
        mock_ep.name = "fake_plugin"
        mock_ep.load.return_value = FakePlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = discover_entry_point_plugins()

        assert len(plugins) == 1
        assert isinstance(plugins[0], FakePlugin)
        mock_ep.load.assert_called_once()

    def test_can_process_respected_by_dispatcher(self):
        """TC-PL-002: FileDispatcher respects can_process() when routing files.

        When a plugin's can_process() returns True for a file extension,
        the dispatcher should route that file to the plugin. When it returns False,
        the file should fall through to the default processor.
        """
        config = {}
        dispatcher = FileDispatcher(config)
        # Inject our fake plugin
        plugin = FakePlugin()
        dispatcher._plugins = [plugin]

        # .xyz should be handled by FakePlugin
        processor = dispatcher.get_processor("document.xyz")
        assert isinstance(processor, FakePlugin)

        # .pdf should NOT be handled by FakePlugin (can_process returns False)
        processor = dispatcher.get_processor("document.pdf")
        assert processor.__class__.__name__ == "MarkitdownProcessor"

    def test_builtin_takes_precedence_over_plugin(self):
        """TC-PL-003: Built-in processors take precedence over plugins for registered extensions.

        Even if a plugin's can_process() returns True for .txt or .md,
        the built-in TextProcessor should still handle those extensions.
        """
        config = {}
        dispatcher = FileDispatcher(config)

        # Create a greedy plugin that claims to handle everything
        greedy_plugin = MagicMock(spec=ProcessorProtocol)
        greedy_plugin.can_process.return_value = True
        dispatcher._plugins = [greedy_plugin]

        # Built-in text extensions should still use TextProcessor
        for ext in [".txt", ".md", ".json", ".py", ".csv"]:
            processor = dispatcher.get_processor(f"file{ext}")
            assert processor.__class__.__name__ == "TextProcessor", (
                f"Expected TextProcessor for {ext}, got {processor.__class__.__name__}"
            )
            # Plugin's can_process should NOT have been called for built-in extensions
            # (dispatcher checks built-in first)

    def test_plugin_processing_result_works_e2e(self, tmp_path):
        """TC-PL-004: Plugin returning ProcessingResult works through the dispatcher.

        A plugin that returns a valid ProcessingResult should have its result
        returned correctly through FileDispatcher.process().
        """
        config = {}
        dispatcher = FileDispatcher(config)

        plugin = FakePlugin()
        dispatcher._plugins = [plugin]

        # Create a dummy .xyz file
        test_file = tmp_path / "data.xyz"
        test_file.write_text("custom format data")

        result = dispatcher.process(str(test_file))

        assert isinstance(result, ProcessingResult)
        assert "FakePlugin" in result.markdown
        assert result.file_type == "xyz"
        assert result.source_path == str(test_file)


class TestPluginEdgeCases:
    """Edge case tests for plugin system."""

    def test_invalid_plugin_skipped_gracefully(self):
        """Plugins that fail to load are skipped with a warning, not crash."""
        mock_ep = MagicMock()
        mock_ep.name = "broken_plugin"
        mock_ep.load.side_effect = ImportError("Module not found")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = discover_entry_point_plugins()

        assert len(plugins) == 0

    def test_non_conforming_plugin_skipped(self):
        """Plugins that don't implement ProcessorProtocol are skipped."""
        mock_ep = MagicMock()
        mock_ep.name = "bad_plugin"
        mock_ep.load.return_value = BadPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = discover_entry_point_plugins()

        # BadPlugin lacks process() method, so it shouldn't pass isinstance check
        # Note: runtime_checkable Protocol checks only method existence
        assert len(plugins) == 0

    def test_no_plugins_registered(self):
        """When no plugins are registered, discover returns empty list."""
        with patch("importlib.metadata.entry_points", return_value=[]):
            plugins = discover_entry_point_plugins()

        assert plugins == []
