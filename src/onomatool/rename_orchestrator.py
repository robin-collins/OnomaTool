"""RenameOrchestrator — coordinates file processing, suggestion, and rename."""

import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

from tqdm import tqdm

from onomatool.conflict_resolver import resolve_conflict
from onomatool.file_collector import collect_files
from onomatool.file_dispatcher import FileDispatcher
from onomatool.models import ProcessingResult
from onomatool.renamer import rename_file
from onomatool.sanitizer import sanitize_filename
from onomatool.suggestion_strategy import select_strategy
from onomatool.history import RenameHistory
from onomatool.utils.image_utils import convert_svg_to_png

logger = logging.getLogger(__name__)

DEBUG_DIR = os.path.expanduser("~/.onoma_debug")
DEBUG_RETENTION_DAYS = 7


def _cleanup_old_debug_sessions(base_dir: str, retention_days: int = DEBUG_RETENTION_DAYS) -> None:
    """Remove debug session directories older than retention_days."""
    if not os.path.isdir(base_dir):
        return
    cutoff = datetime.now() - timedelta(days=retention_days)
    for entry in os.scandir(base_dir):
        if entry.is_dir():
            try:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                if mtime < cutoff:
                    shutil.rmtree(entry.path)
                    logger.debug("Cleaned up old debug session: %s", entry.name)
            except OSError:
                pass


class RenameOrchestrator:
    """Orchestrates file processing, LLM suggestions, and renaming."""

    def __init__(
        self,
        config: dict,
        dry_run: bool = False,
        debug: bool = False,
        verbose_level: int = 0,
        exclude_patterns: list[str] | None = None,
        history: "RenameHistory | None" = None,
        sort_order: str | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.debug = debug
        self.verbose_level = verbose_level
        self.exclude_patterns = exclude_patterns or []
        self.sort_order = sort_order
        self.dispatcher = FileDispatcher(config, debug=debug)
        self.planned_renames: list[tuple[str, str]] = []
        self._debug_tempdirs: list = []
        self.renamed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.history = history
        self._session_id: int | None = None
        self._debug_session_dir: str | None = None
        if self.debug:
            _cleanup_old_debug_sessions(DEBUG_DIR)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._debug_session_dir = os.path.join(DEBUG_DIR, timestamp)
            os.makedirs(self._debug_session_dir, exist_ok=True)
            logger.debug("Debug output directory: %s", self._debug_session_dir)

    def process_files(self, pattern: str) -> None:
        """Process all files matching the glob pattern."""
        import fnmatch

        files = collect_files(pattern)

        # Filter out hidden files (dotfiles) and zero-byte files
        filtered = []
        for f in files:
            basename = os.path.basename(f)
            if basename.startswith("."):
                logger.debug("Skipping hidden file: %s", f)
                continue
            if os.path.getsize(f) == 0:
                logger.debug("Skipping zero-byte file: %s", f)
                continue
            filtered.append(f)
        files = filtered

        if self.exclude_patterns:
            files = [
                f
                for f in files
                if not any(fnmatch.fnmatch(f, ep) for ep in self.exclude_patterns)
            ]

        # Sort files
        if self.sort_order == "name":
            files.sort(key=lambda f: os.path.basename(f).lower())
        elif self.sort_order == "size":
            files.sort(key=lambda f: os.path.getsize(f))
        elif self.sort_order == "modified":
            files.sort(key=lambda f: os.path.getmtime(f))

        # Create history session for non-dry-run
        if self.history and not self.dry_run:
            self._session_id = self.history.create_session(os.getcwd())

        use_progress = sys.stderr.isatty() and len(files) > 1
        iterator = tqdm(
            files,
            desc="Processing",
            unit="file",
            disable=not use_progress,
            file=sys.stderr,
        )

        for file_path in iterator:
            if use_progress:
                iterator.set_postfix_str(os.path.basename(file_path), refresh=True)
            self._process_single_file(file_path)

        if len(files) > 0:
            action = "planned" if self.dry_run else "renamed"
            print(
                f"\nProcessed {len(files)} files: "
                f"{self.renamed_count} {action}, "
                f"{self.failed_count} failed, "
                f"{self.skipped_count} skipped"
            )

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
                self.failed_count += 1
                return

        # Process file content
        result = self.dispatcher.process(file_path)
        if result is None:
            self._cleanup_tempdir(svg_tempdir)
            self.skipped_count += 1
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
                self.renamed_count += 1
            else:
                self.skipped_count += 1
        except Exception as e:
            logger.error("Failed to process %s: %s", file_path, e)
            self.failed_count += 1
            if self.history and self._session_id is not None:
                self.history.record_rename(
                    self._session_id, file_path, file_path, status="error"
                )
        finally:
            self._cleanup_tempdir(svg_tempdir)
            self._cleanup_result_tempdir(result)

    def _convert_svg(self, file_path: str) -> tuple:
        """Convert SVG to PNG, returns (tempdir, png_path) or (tempdir, None) on failure."""
        if self.debug and self._debug_session_dir:
            basename = os.path.splitext(os.path.basename(file_path))[0]
            tempdir_path = os.path.join(self._debug_session_dir, f"svg_{basename}")
            os.makedirs(tempdir_path, exist_ok=True)
            tempdir = type(
                "TempDir", (), {"name": tempdir_path, "cleanup": lambda: None}
            )()
            logger.debug("Created debug dir for SVG: %s", tempdir.name)
        else:
            tempdir = tempfile.TemporaryDirectory()

        try:
            png_path = convert_svg_to_png(file_path, tempdir.name)
            if self.debug:
                logger.debug("Created PNG: %s", png_path)
            return tempdir, png_path
        except Exception as e:
            logger.error("Could not convert %s to PNG: %s", file_path, e)
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
            new_path = os.path.join(directory, final_name)
            print(f"{os.path.basename(file_path)} --> {final_name}")
            rename_file(file_path, new_name)
            if self.history and self._session_id is not None:
                self.history.record_rename(
                    self._session_id, file_path, new_path
                )

    def execute_planned_renames(self) -> None:
        """Execute renames that were planned during dry-run."""
        if self.history:
            self._session_id = self.history.create_session(os.getcwd())

        for file_path, new_name in self.planned_renames:
            directory = os.path.dirname(file_path) or "."
            _, ext = os.path.splitext(file_path)
            base_new_name, _ = os.path.splitext(new_name)
            new_name_with_ext = base_new_name + ext
            existing_files = os.listdir(directory)
            final_name = resolve_conflict(new_name_with_ext, existing_files)
            new_path = os.path.join(directory, final_name)
            print(f"{os.path.basename(file_path)} --> {final_name}")
            rename_file(file_path, new_name)
            if self.history and self._session_id is not None:
                self.history.record_rename(
                    self._session_id, file_path, new_path
                )

    def _log_debug_info(self, result: ProcessingResult) -> None:
        """Log debug info for result tempdirs."""
        if result.tempdir is not None and self.debug:
            self._debug_tempdirs.append(result.tempdir)
            logger.debug(
                "Created tempdir for %s: %s", result.file_type.upper(), result.tempdir.name
            )
            for img_path in result.images:
                logger.debug("Created image: %s", img_path)
            markdown_path = os.path.join(
                result.tempdir.name, "extracted_content.md"
            )
            if os.path.exists(markdown_path):
                logger.debug("Created markdown: %s", markdown_path)

    def _cleanup_tempdir(self, tempdir) -> None:
        """Clean up a tempdir unless in debug mode."""
        if tempdir is None:
            return
        if self.debug:
            logger.debug("Preserving tempdir: %s", tempdir.name)
        else:
            tempdir.cleanup()

    def _cleanup_result_tempdir(self, result: ProcessingResult) -> None:
        """Clean up result tempdir unless in debug mode."""
        if result.tempdir is None:
            return
        if self.debug:
            logger.debug(
                "Preserving %s tempdir: %s", result.file_type.upper(), result.tempdir.name
            )
        else:
            result.tempdir.cleanup()
