import argparse
import os
import sys
import tempfile

import tomli_w

from onomatool.config import DEFAULT_CONFIG, get_config
from onomatool.conflict_resolver import resolve_conflict
from onomatool.file_collector import collect_files
from onomatool.file_dispatcher import FileDispatcher
from onomatool.llm_integration import get_suggestions
from onomatool.renamer import rename_file
from onomatool.utils.image_utils import convert_svg_to_png


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
            verbose_level = 2  # Very verbose
        elif args.verbose:
            verbose_level = 1  # Basic verbose
        else:
            verbose_level = 0  # No verbose output

        config = get_config(args.config)
        files = collect_files(args.pattern)
        dispatcher = FileDispatcher(config, debug=args.debug)

        planned_renames = []

        # List to hold tempdir references in debug mode to prevent garbage collection
        debug_tempdirs = []

        for file_path in files:
            print(f"Processing file: {file_path}")
            _, ext = os.path.splitext(file_path)
            is_svg = ext.lower() == ".svg"
            tempdir = None
            png_path = None
            if is_svg:
                if args.debug:
                    # Create a regular temp directory that won't auto-cleanup
                    tempdir_path = tempfile.mkdtemp(prefix="onoma_svg_")
                    tempdir = type(
                        "TempDir", (), {"name": tempdir_path, "cleanup": lambda: None}
                    )()
                    print(f"[DEBUG] Created tempdir for SVG: {tempdir.name}")
                else:
                    tempdir = tempfile.TemporaryDirectory()
                try:
                    png_path = convert_svg_to_png(file_path, tempdir.name)
                    if args.debug:
                        print(f"[DEBUG] Created PNG: {png_path}")
                except Exception as e:
                    print(f"[SVG ERROR] Could not convert {file_path} to PNG: {e}")
                    if tempdir is not None and not args.debug:
                        tempdir.cleanup()
                    continue
            result = dispatcher.process(file_path)
            if result is None:
                if tempdir is not None and not args.debug:
                    tempdir.cleanup()
                continue
            try:
                # Preserve tempdir references in debug mode
                if result.tempdir is not None and args.debug:
                    debug_tempdirs.append(result.tempdir)
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

                # Determine image paths for LLM analysis
                if is_svg and png_path:
                    image_paths = [png_path]
                elif result.has_images:
                    image_paths = result.images
                else:
                    image_paths = []

                if image_paths:
                    # Multi-modal path: analyze images then combine with markdown
                    all_image_suggestions = []
                    for img_path in image_paths:
                        img_suggestions = get_suggestions(
                            "",
                            verbose_level=verbose_level,
                            file_path=img_path,
                            config=config,
                        )
                        if img_suggestions:
                            all_image_suggestions.append(img_suggestions)
                    flat_image_suggestions = [
                        s for sublist in all_image_suggestions for s in sublist
                    ]
                    ref_image = image_paths[0]
                    md_suggestions = get_suggestions(
                        result.markdown,
                        verbose_level=verbose_level,
                        file_path=ref_image,
                        config=config,
                    )
                    guidance = "\n".join(flat_image_suggestions)
                    final_prompt = (
                        "You have previously suggested the following file names for each "
                        "page/slide/image of the file:\n"
                        f"{guidance}\n"
                        "Now, based on the full document content (markdown below) and the "
                        "above suggestions, generate 3 final file name suggestions that best "
                        "represent the entire file.\n"
                        f"MARKDOWN:\n{result.markdown}"
                    )
                    final_suggestions = get_suggestions(
                        final_prompt,
                        verbose_level=verbose_level,
                        file_path=ref_image,
                        config=config,
                    )
                    suggestions = (
                        final_suggestions
                        or md_suggestions
                        or flat_image_suggestions
                    )
                else:
                    # Text-only path
                    suggestions = get_suggestions(
                        result.markdown,
                        verbose_level=verbose_level,
                        file_path=file_path,
                        config=config,
                    )

                if suggestions:
                    new_name = suggestions[0]
                    directory = os.path.dirname(file_path) or "."
                    _, ext = os.path.splitext(file_path)
                    base_new_name, _ = os.path.splitext(new_name)
                    new_name_with_ext = base_new_name + ext
                    existing_files = os.listdir(directory)
                    final_name = resolve_conflict(
                        new_name_with_ext, existing_files
                    )
                    if args.dry_run:
                        print(
                            f"{os.path.basename(file_path)} --dry-run-> {final_name}"
                        )
                        planned_renames.append((file_path, new_name))
                    else:
                        print(f"{os.path.basename(file_path)} --> {final_name}")
                        rename_file(file_path, new_name)
            finally:
                # Clean up SVG tempdir if not in debug mode
                if tempdir is not None:
                    if args.debug:
                        print(f"[DEBUG] Preserving SVG tempdir: {tempdir.name}")
                    else:
                        tempdir.cleanup()

                # Clean up result tempdir if not in debug mode
                if result.tempdir is not None:
                    if args.debug:
                        print(
                            f"[DEBUG] Preserving {result.file_type.upper()} tempdir: {result.tempdir.name}"
                        )
                    else:
                        result.tempdir.cleanup()

        if args.dry_run and args.interactive and planned_renames:
            confirm = input("\nProceed with these renames? [y/N]: ").strip().lower()
            if confirm == "y":
                for file_path, new_name in planned_renames:
                    directory = os.path.dirname(file_path) or "."
                    _, ext = os.path.splitext(file_path)
                    base_new_name, _ = os.path.splitext(new_name)
                    new_name_with_ext = base_new_name + ext
                    existing_files = os.listdir(directory)
                    final_name = resolve_conflict(new_name_with_ext, existing_files)
                    print(f"{os.path.basename(file_path)} --> {final_name}")
                    rename_file(file_path, new_name)
            else:
                print("Aborted. No files were renamed.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user (Ctrl+C). Exiting gracefully.")
        return 130
    except SystemExit:
        # Allow normal sys.exit() and argparse exits without stack trace
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        return 1
    return 0


def save_default_config():
    """Save default configuration to ~/.onomarc"""
    config_path = os.path.expanduser("~/.onomarc")
    # Ensure llm_model is in the main section and not in markitdown
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
