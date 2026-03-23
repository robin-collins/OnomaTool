# OnomaTool: AI-Powered File Renamer

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)
![Tests Passing](https://img.shields.io/badge/tests-passing-success?logo=pytest)

---

## What is OnomaTool?

**OnomaTool** is an AI-powered CLI file renaming tool. It processes files of various types (PDFs, images, documents, SVGs, code, text), extracts their content, sends it to an LLM (OpenAI, Azure OpenAI, or Google Gemini), and receives back intelligent filename suggestions that follow a configurable naming convention.

- Rename files in bulk with smart, context-aware suggestions
- Supports PDFs, images, markdown, SVG, PPTX, DOCX, TXT, and more
- Always preserves file extensions
- CLI with dry-run, interactive, verbose, and debug modes
- Configurable via `.onomarc` TOML config file
- Uses Markitdown for unified file processing
- Advanced UTF-8 encoding detection and conversion for text files
- Configurable word count limits for filenames

---

## Installation

OnomaTool uses [`uv`](https://docs.astral.sh/uv/) for package management.

### Run directly with uvx (no install needed)

```bash
# Run OnomaTool without installing it permanently
uvx onomatool '*.pdf'

# With arguments
uvx onomatool '*.jpg' --dry-run --interactive
```

### Install globally with uv

```bash
# Install as a global tool
uv tool install onomatool

# Now available as a command
onomatool '*.pdf'
```

### Install from source for development

```bash
# Clone the repository
git clone https://github.com/robin-collins/Onoma.git
cd Onoma

# Install with uv (creates venv and installs deps automatically)
uv sync

# Run the tool
uv run onomatool '*.pdf'

# Or install in development mode
uv pip install -e .
```

### System Dependencies

For full functionality (SVG, PDF, PPTX processing):

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install libreoffice imagemagick libcairo2 libpango-1.0-0 libpangocairo-1.0-0

# macOS (with Homebrew)
brew install libreoffice imagemagick cairo pango

# Windows: Download and install LibreOffice and ImageMagick
# For SVG support: Cairo system libraries are required by cairosvg
```

---

## Quick Start

### Basic Usage

```bash
# Rename all PDFs in current directory
uvx onomatool '*.pdf'

# Process files in subdirectories
uvx onomatool 'docs/**/*.md'

# Specify file format explicitly
uvx onomatool '*.unknown' --format pdf
```

### Preview Mode

```bash
# See what would be renamed (no changes made)
uvx onomatool '*.jpg' --dry-run

# Interactive confirmation after preview
uvx onomatool '*.pdf' --dry-run --interactive
```

### Debug and Verbose Modes

```bash
# Debug mode - preserve temp files
uvx onomatool '*.svg' --debug

# Verbose mode - see LLM interactions
uvx onomatool '*.docx' --verbose

# Very verbose - full request/response details
uvx onomatool '*.docx' -vv

# Combined modes
uvx onomatool '*.pptx' --debug --verbose --dry-run
```

---

## Configuration

OnomaTool uses a TOML configuration file at `~/.onomarc` or a custom path with `--config`.

### Generate Default Config

```bash
uvx onomatool --save-config
```

### Configuration Options

```toml
# API Configuration
default_provider = "openai"  # or "google" or "mock" (testing)
openai_api_key = "sk-..."
openai_base_url = "https://api.openai.com/v1"  # or local endpoint
google_api_key = "your-google-api-key"

# Azure OpenAI (optional)
use_azure_openai = false
azure_openai_endpoint = ""
azure_openai_api_key = ""
azure_openai_api_version = "2024-02-01"
azure_openai_deployment = ""

# Model and Behavior
llm_model = "gpt-4o"
naming_convention = "snake_case"  # snake_case, camelCase, kebab-case, PascalCase, dot.notation, natural language
min_filename_words = 5
max_filename_words = 15

# Custom Prompts (optional - defaults provided)
system_prompt = ""
user_prompt = ""
image_prompt = ""

# Markitdown Configuration
[markitdown]
enable_plugins = false
docintel_endpoint = ""
```

### Supported Naming Conventions

| Convention | Config Value | Example |
|------------|-------------|---------|
| Snake Case | `"snake_case"` | `my_document_file` |
| Camel Case | `"camelCase"` | `myDocumentFile` |
| Kebab Case | `"kebab-case"` | `my-document-file` |
| Pascal Case | `"PascalCase"` | `MyDocumentFile` |
| Dot Notation | `"dot.notation"` | `my.document.file` |
| Natural Language | `"natural language"` | `My Document File` |

---

## Supported File Types

| File Type | Processing Method | Output |
|-----------|-------------------|---------|
| PDF | Markitdown + PyMuPDF page images | Combined text + image analysis |
| PPTX | Markitdown + LibreOffice slide images | Combined text + image analysis |
| SVG | Convert to PNG + Markitdown | Image analysis only |
| Images (JPG, PNG, etc.) | Base64 encoding | Direct image analysis |
| DOCX | Markitdown processing | Text analysis |
| TXT, MD, NOTE | UTF-8 encoding detection + text processing | Text analysis |
| XLSX | Markitdown processing | Content analysis |
| CSV, JSON, XML, HTML | UTF-8 encoding detection + Markitdown | Content analysis |
| Code Files (PY, JS, CSS, YAML) | UTF-8 encoding detection + text processing | Code analysis |

---

## Development

### Prerequisites

Install [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Setup

```bash
git clone https://github.com/robin-collins/Onoma.git
cd Onoma

# Install all dependencies (creates .venv automatically)
uv sync

# Install with dev dependencies
uv sync --all-extras
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test suites
uv run pytest tests/test_usage_enduser.py    # End-to-end user tests
uv run pytest tests/test_utf8_encoding.py    # UTF-8 encoding tests

# Run with coverage
uv run pytest --cov=onomatool

# Test individual components
uv run pytest tests/test_config.py
uv run pytest tests/test_conflict_resolver.py
uv run pytest tests/test_file_collector.py
uv run pytest tests/test_renamer.py
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check --fix .

# Validate (CI check)
uv run ruff check . && uv run ruff format --check .
```

### Project Structure

```
src/onomatool/
├── cli.py                 # Command-line interface and entry point
├── config.py              # Configuration management (TOML)
├── llm_integration.py     # OpenAI/Azure/Google API integration
├── models.py              # Pydantic models for structured LLM output
├── prompts.py             # Default prompt templates
├── file_dispatcher.py     # File routing logic by extension
├── file_collector.py      # Glob pattern matching
├── conflict_resolver.py   # Filename conflict handling
├── renamer.py             # File renaming operations
├── processors/
│   ├── markitdown_processor.py  # PDF, DOCX, PPTX, SVG, etc.
│   └── text_processor.py       # Plain text with encoding detection
└── utils/
    └── image_utils.py     # SVG-to-PNG conversion
```

---

## Advanced Usage

### Custom Configuration Files

```bash
uvx onomatool '*.pdf' --config /path/to/custom.toml
```

### Local LLM Endpoints

```toml
# In your .onomarc
default_provider = "openai"
openai_base_url = "http://localhost:1234/v1"
openai_api_key = "not-needed-for-local"
```

---

## Safety Features

- **No Overwrites**: Built-in conflict resolution with numeric suffixes
- **Extension Preservation**: Original file extensions always maintained
- **Dry-Run Mode**: Preview all changes before execution
- **Interactive Confirmation**: Approve renames after dry-run preview
- **Temp File Management**: Automatic cleanup (preservable in debug mode)
- **Encoding Safety**: Automatic UTF-8 conversion preserves original files

---

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Run `uv run ruff check --fix . && uv run ruff format .`
5. Submit a pull request

### Development Setup

```bash
git clone https://github.com/robin-collins/Onoma.git
cd Onoma
uv sync --all-extras

# Run tests to verify setup
uv run pytest
```

---

## License

MIT License - see LICENSE file for details.

---

## FAQ

**Q: Does it work on Windows/Mac/Linux?**
A: Yes! Cross-platform support with Python 3.10+.

**Q: Can I use local LLMs?**
A: Yes! Set `openai_base_url` to your local endpoint in `.onomarc`.

**Q: Will it overwrite my files?**
A: Never! Built-in conflict resolution prevents overwrites.

**Q: Can I customize the AI prompts?**
A: Yes! Set `system_prompt`, `user_prompt`, and `image_prompt` in your config.

**Q: How does SVG processing work?**
A: SVGs are converted to PNG images before AI analysis for better results.

**Q: What about files with special characters or different encodings?**
A: OnomaTool automatically detects and converts file encodings to UTF-8.
