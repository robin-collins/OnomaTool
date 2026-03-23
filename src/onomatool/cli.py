import argparse
import os
import sys

import tomli_w

from onomatool.config import DEFAULT_CONFIG, get_config
from onomatool.rename_orchestrator import RenameOrchestrator


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
        args = parser.parse_args(args)

        if args.save_config:
            save_default_config()
            print("Default configuration saved to ~/.onomarc")
            return 0

        if not args.pattern:
            parser.error("the following arguments are required: pattern")

        if args.interactive and not args.dry_run:
            parser.error("--interactive must be used with --dry-run")

        if args.format:
            print(
                "Warning: --format is not yet implemented and will be ignored."
            )

        # Handle verbosity levels
        if args.very_verbose:
            verbose_level = 2
        elif args.verbose:
            verbose_level = 1
        else:
            verbose_level = 0

        config = get_config(args.config)
        orchestrator = RenameOrchestrator(
            config=config,
            dry_run=args.dry_run,
            debug=args.debug,
            verbose_level=verbose_level,
        )

        orchestrator.process_files(args.pattern)

        if args.dry_run and args.interactive and orchestrator.planned_renames:
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
        print(f"An error occurred: {e}")
        return 1
    return 0


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
        print(f"Error saving default config: {e}")
        sys.exit(1)


def console_script():
    """Entry point for console_scripts."""
    sys.exit(main())


if __name__ == "__main__":
    console_script()
