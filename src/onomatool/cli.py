import argparse
import logging
import os
import sys

import tomli_w

from onomatool.config import DEFAULT_CONFIG, get_config
from onomatool.history import RenameHistory
from onomatool.model_discovery import (
    format_model_list,
    list_models,
    select_model_interactive,
)
from onomatool.rename_orchestrator import RenameOrchestrator

logger = logging.getLogger(__name__)


def main(args=None):
    try:
        if args is None:
            args = sys.argv[1:]
        parser = argparse.ArgumentParser(
            description="Onoma - AI-powered file renaming tool",
            epilog="Configuration is loaded from ~/.onomarc (TOML format)",
            add_help=False,
        )
        parser.add_argument(
            "-h", "--help", action="help", help="Show this help message and exit"
        )
        parser.add_argument(
            "pattern",
            nargs="?",
            help="Glob pattern to match files (e.g., '*.pdf', 'docs/**/*.md')",
        )
        parser.add_argument(
            "-f",
            "--format",
            help="Force specific file format processing (optional)",
            choices=["text", "markdown", "pdf", "docx", "image"],
            metavar="FORMAT",
        )
        parser.add_argument(
            "-s",
            "--save-config",
            action="store_true",
            help="Save default configuration to ~/.onomarc and exit",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Print basic LLM debugging information",
        )
        parser.add_argument(
            "-vv",
            "--very-verbose",
            action="store_true",
            help="Print detailed LLM request and response for debugging",
        )
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help="Show intended renames but do not modify any files",
        )
        parser.add_argument(
            "-i",
            "--interactive",
            action="store_true",
            help=(
                "With --dry-run, prompt for confirmation and then perform the renames "
                "using the dry-run suggestions"
            ),
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help=(
                "Do not delete temporary files created for SVG, PDF, or PPTX processing; "
                "print their paths."
            ),
        )
        parser.add_argument(
            "--config",
            help="Specify a configuration file to use",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Check system dependency health and exit",
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            metavar="PATTERN",
            help="Glob patterns to exclude from processing (can be repeated)",
        )
        parser.add_argument(
            "--sort",
            choices=["name", "size", "modified"],
            help="Sort order for file processing (not yet implemented)",
        )
        parser.add_argument(
            "--undo",
            nargs="?",
            const="latest",
            default=None,
            metavar="SESSION_ID",
            help="Undo a rename session (defaults to most recent)",
        )
        parser.add_argument(
            "--history",
            action="store_true",
            help="Show recent rename sessions",
        )
        parser.add_argument(
            "--list-models",
            action="store_true",
            help="List available models from the configured AI provider and exit",
        )
        parser.add_argument(
            "--select-model",
            action="store_true",
            help="Interactively select a model from the provider and save to config",
        )
        args = parser.parse_args(args)

        if args.check:
            return run_health_check()

        if args.save_config:
            save_default_config()
            logger.info("Default configuration saved to ~/.onomarc")
            return 0

        if args.undo is not None:
            return _handle_undo(args.undo)

        if args.history:
            return _handle_history()

        if args.list_models:
            return _handle_list_models(args)

        if args.select_model:
            return _handle_select_model(args)

        if not args.pattern:
            parser.error("the following arguments are required: pattern")

        if args.interactive and not args.dry_run:
            parser.error("--interactive must be used with --dry-run")

        format_override = args.format

        sort_order = args.sort

        # Handle verbosity levels
        if args.very_verbose:
            verbose_level = 2
        elif args.verbose:
            verbose_level = 1
        else:
            verbose_level = 0

        # Configure logging to output to stdout for better CLI integration
        logging.basicConfig(
            level=logging.DEBUG
            if verbose_level >= 2
            else logging.INFO
            if verbose_level >= 1
            else logging.WARNING,
            format="[%(levelname)s] %(message)s",
            stream=sys.stdout,
        )

        config = get_config(args.config)
        with RenameHistory() as history:
            history.prune(config.get("history_retention_days", 90))
            orchestrator = RenameOrchestrator(
                config=config,
                dry_run=args.dry_run,
                debug=args.debug,
                verbose_level=verbose_level,
                exclude_patterns=args.exclude,
                history=history,
                sort_order=sort_order,
                format_override=format_override,
            )

            orchestrator.process_files(args.pattern)

            if args.dry_run and args.interactive and orchestrator.planned_renames:
                # Check if re-resolved names differ from dry-run preview
                changes = orchestrator.check_planned_renames()
                if changes:
                    print("\nNote: Some names changed since dry-run preview:")
                    for file_path, dry_name, actual_name in changes:
                        print(
                            f"  {os.path.basename(file_path)}: {dry_name} -> {actual_name}"
                        )
                    confirm = (
                        input("\nProceed with updated renames? [y/N]: ").strip().lower()
                    )
                else:
                    confirm = input("\nProceed with these renames? [y/N]: ").strip().lower()
                if confirm == "y":
                    orchestrator.execute_planned_renames()
                else:
                    print("Aborted. No files were renamed.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user (Ctrl+C). Exiting gracefully.")
        return 130
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1
    return 0


def _handle_undo(session_arg: str) -> int:
    """Handle --undo command."""
    history = RenameHistory()
    session_id = None if session_arg == "latest" else int(session_arg)
    results = history.undo_session(session_id)
    history.close()

    ok_count = 0
    for r in results:
        if r["status"] == "ok":
            print(r["message"])
            ok_count += 1
        elif r["status"] == "warning":
            print(f"Warning: {r['message']}")
        else:
            print(f"Error: {r['message']}")

    if ok_count > 0:
        print(f"\nUndid {ok_count} rename(s)")
    return 0


def _handle_history() -> int:
    """Handle --history command."""
    history = RenameHistory()
    sessions = history.list_sessions()
    history.close()

    if not sessions:
        print("No rename sessions found.")
        return 0

    print(f"{'ID':>6}  {'Timestamp':25s}  {'Files':>5}  {'Directory'}")
    print("-" * 70)
    for s in sessions:
        print(
            f"{s['id']:>6}  {s['timestamp']:25s}  {s['file_count']:>5}  {s['working_dir']}"
        )
    return 0


def _handle_list_models(args) -> int:
    """Handle --list-models command."""
    config = get_config(args.config)
    verbose = args.verbose or args.very_verbose

    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(levelname)s] %(message)s",
            stream=sys.stdout,
        )

    try:
        models = list_models(config)
        print(format_model_list(models, verbose=verbose))
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def _handle_select_model(args) -> int:
    """Handle --select-model command: interactive picker that saves to config."""
    config = get_config(args.config)
    config_path = args.config or os.path.expanduser("~/.onomarc")

    try:
        models = list_models(config)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    selected = select_model_interactive(models)
    if selected is None:
        print("No model selected.")
        return 0

    # Update config with the selected model
    config["llm_model"] = selected.id
    print(f"\nSelected: {selected.id}")

    # Save to config file
    try:
        import tomli

        existing = {}
        config_path = os.path.expanduser(config_path)
        if os.path.exists(config_path):
            with open(config_path, "rb") as f:
                existing = tomli.load(f)

        existing["llm_model"] = selected.id
        with open(config_path, "wb") as f:
            tomli_w.dump(existing, f)
        print(f'Saved llm_model = "{selected.id}" to {config_path}')
    except Exception as e:
        print(f"Warning: Could not save config: {e}", file=sys.stderr)
        print(f'Manually set llm_model = "{selected.id}" in {config_path}')
        return 1

    return 0


def run_health_check() -> int:
    """Check system dependencies and print status."""
    import shutil
    import subprocess

    checks = []

    # Python version
    checks.append(("Python", sys.version.split()[0], True))

    # Core Python packages
    for pkg_name, import_name in [
        ("markitdown", "markitdown"),
        ("openai", "openai"),
        ("google-genai", "google.genai"),
        ("tomli", "tomli"),
        ("pydantic", "pydantic"),
        ("tiktoken", "tiktoken"),
        ("chardet", "chardet"),
        ("cairosvg", "cairosvg"),
        ("Pillow", "PIL"),
        ("PyMuPDF", "fitz"),
    ]:
        try:
            mod = __import__(import_name.split(".")[0])
            version = getattr(mod, "__version__", "installed")
            checks.append((pkg_name, version, True))
        except ImportError:
            checks.append((pkg_name, "MISSING", False))

    # System tools
    for tool in ["soffice", "convert"]:
        path = shutil.which(tool)
        if path:
            try:
                result = subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                version = (
                    result.stdout.split("\n")[0][:50] if result.stdout else "found"
                )
            except Exception:
                version = "found"
            checks.append((tool, version, True))
        else:
            checks.append((tool, "MISSING", False))

    # Print results
    all_ok = True
    for name, version, ok in checks:
        status = "OK" if ok else "MISSING"
        print(f"  {name:20s} {version:30s} [{status}]")
        if not ok:
            all_ok = False

    if all_ok:
        print("\nAll dependencies OK.")
    else:
        print("\nSome dependencies are missing. Install them for full functionality.")

    return 0 if all_ok else 1


def save_default_config():
    """Save default configuration to ~/.onomarc"""
    config_path = os.path.expanduser("~/.onomarc")
    config = DEFAULT_CONFIG.copy()
    if "markitdown" in config and "llm_model" in config["markitdown"]:
        del config["markitdown"]["llm_model"]
    config["llm_model"] = config.get("llm_model", "gpt-4o")
    config["image_prompt"] = config.get("image_prompt", "")
    config["min_filename_words"] = config.get("min_filename_words", 5)
    config["max_filename_words"] = config.get("max_filename_words", 15)
    try:
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)
    except Exception as e:
        logger.error(f"Error saving default config: {e}")
        sys.exit(1)


def console_script():
    """Entry point for console_scripts."""
    sys.exit(main())


if __name__ == "__main__":
    console_script()
