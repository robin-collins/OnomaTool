"""RenameOrchestrator — coordinates file processing, suggestion, and rename."""

import os
import tempfile

from onomatool.conflict_resolver import resolve_conflict
from onomatool.file_collector import collect_files
from onomatool.file_dispatcher import FileDispatcher
from onomatool.models import ProcessingResult
from onomatool.renamer import rename_file
from onomatool.sanitizer import sanitize_filename
from onomatool.suggestion_strategy import select_strategy
from onomatool.utils.image_utils import convert_svg_to_png


class RenameOrchestrator:
    """Orchestrates file processing, LLM suggestions, and renaming."""

    def __init__(
        self,
        config: dict,
        dry_run: bool = False,
        debug: bool = False,
        verbose_level: int = 0,
    ):
        self.config = config
        self.dry_run = dry_run
        self.debug = debug
        self.verbose_level = verbose_level
        self.dispatcher = FileDispatcher(config, debug=debug)
        self.planned_renames: list[tuple[str, str]] = []
        self._debug_tempdirs: list = []

    def process_files(self, pattern: str) -> None:
        """Process all files matching the glob pattern."""
        files = collect_files(pattern)
        for file_path in files:
            print(f"Processing file: {file_path}")
            self._process_single_file(file_path)

    def _process_single_file(self, file_path: str) -> None:
        """Process a single file through the full pipeline."""
        _, ext = os.path.splitext(file_path)
        is_svg = ext.lower() == ".svg"

        # Handle SVG conversion
        svg_tempdir = None
        png_path = None
        if is_svg:
            svg_tempdir, png_path = self._convert_svg(file_path)
            if png_path is None:
                return

        # Process file content
        result = self.dispatcher.process(file_path)
        if result is None:
            self._cleanup_tempdir(svg_tempdir)
            return

        try:
            self._log_debug_info(result)

            # Determine image paths
            if is_svg and png_path:
                image_paths = [png_path]
            elif result.has_images:
                image_paths = result.images
            else:
                image_paths = []

            # Get suggestions via strategy
            strategy = select_strategy(image_paths)
            suggestions = strategy.get_suggestions(
                result, file_path, image_paths, self.config, self.verbose_level
            )

            # Execute rename
            if suggestions:
                self._execute_rename(file_path, suggestions[0])
        finally:
            self._cleanup_tempdir(svg_tempdir)
            self._cleanup_result_tempdir(result)

    def _convert_svg(self, file_path: str) -> tuple:
        """Convert SVG to PNG, returns (tempdir, png_path) or (tempdir, None) on failure."""
        if self.debug:
            tempdir_path = tempfile.mkdtemp(prefix="onoma_svg_")
            tempdir = type(
                "TempDir", (), {"name": tempdir_path, "cleanup": lambda: None}
            )()
            print(f"[DEBUG] Created tempdir for SVG: {tempdir.name}")
        else:
            tempdir = tempfile.TemporaryDirectory()

        try:
            png_path = convert_svg_to_png(file_path, tempdir.name)
            if self.debug:
                print(f"[DEBUG] Created PNG: {png_path}")
            return tempdir, png_path
        except Exception as e:
            print(f"[SVG ERROR] Could not convert {file_path} to PNG: {e}")
            if not self.debug:
                tempdir.cleanup()
            return None, None

    def _execute_rename(self, file_path: str, new_name: str) -> None:
        """Sanitize, resolve conflicts, and rename (or plan rename in dry-run)."""
        new_name = sanitize_filename(new_name)
        directory = os.path.dirname(file_path) or "."
        _, ext = os.path.splitext(file_path)
        base_new_name, _ = os.path.splitext(new_name)
        new_name_with_ext = base_new_name + ext
        existing_files = os.listdir(directory)
        final_name = resolve_conflict(new_name_with_ext, existing_files)

        if self.dry_run:
            print(f"{os.path.basename(file_path)} --dry-run-> {final_name}")
            self.planned_renames.append((file_path, new_name))
        else:
            print(f"{os.path.basename(file_path)} --> {final_name}")
            rename_file(file_path, new_name)

    def execute_planned_renames(self) -> None:
        """Execute renames that were planned during dry-run."""
        for file_path, new_name in self.planned_renames:
            directory = os.path.dirname(file_path) or "."
            _, ext = os.path.splitext(file_path)
            base_new_name, _ = os.path.splitext(new_name)
            new_name_with_ext = base_new_name + ext
            existing_files = os.listdir(directory)
            final_name = resolve_conflict(new_name_with_ext, existing_files)
            print(f"{os.path.basename(file_path)} --> {final_name}")
            rename_file(file_path, new_name)

    def _log_debug_info(self, result: ProcessingResult) -> None:
        """Log debug info for result tempdirs."""
        if result.tempdir is not None and self.debug:
            self._debug_tempdirs.append(result.tempdir)
            print(
                f"[DEBUG] Created tempdir for {result.file_type.upper()}: {result.tempdir.name}"
            )
            for img_path in result.images:
                print(f"[DEBUG] Created image: {img_path}")
            markdown_path = os.path.join(
                result.tempdir.name, "extracted_content.md"
            )
            if os.path.exists(markdown_path):
                print(f"[DEBUG] Created markdown: {markdown_path}")

    def _cleanup_tempdir(self, tempdir) -> None:
        """Clean up a tempdir unless in debug mode."""
        if tempdir is None:
            return
        if self.debug:
            print(f"[DEBUG] Preserving tempdir: {tempdir.name}")
        else:
            tempdir.cleanup()

    def _cleanup_result_tempdir(self, result: ProcessingResult) -> None:
        """Clean up result tempdir unless in debug mode."""
        if result.tempdir is None:
            return
        if self.debug:
            print(
                f"[DEBUG] Preserving {result.file_type.upper()} tempdir: {result.tempdir.name}"
            )
        else:
            result.tempdir.cleanup()
