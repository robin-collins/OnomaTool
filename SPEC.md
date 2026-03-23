# OnomaTool - Software Development Document

## 1. Project Summary

| Field | Value |
|-------|-------|
| **Name** | OnomaTool |
| **Version** | 0.1.0 |
| **License** | MIT |
| **Language** | Python 3.10+ |
| **Package Manager** | uv (run via `uvx onomatool` or `uv run onomatool`) |
| **Build System** | setuptools (via `pyproject.toml`) |
| **Entry Point** | `onomatool.cli:console_script` |
| **Repository** | https://github.com/robin-collins/Onoma |
| **Author** | Robin Collins |

OnomaTool is an AI-powered command-line file renaming tool. It processes files of various types (PDFs, images, documents, SVGs, code, text), extracts their content, sends it to an LLM (OpenAI, Azure OpenAI, or Google Gemini), and receives back intelligent filename suggestions that follow a configurable naming convention. The first suggestion is automatically applied, with built-in conflict resolution to prevent overwrites.

**Design scope**: OnomaTool is a **CLI-only tool**. There is no public Python library API. Internal modules may be imported but are not considered stable.

---

## 2. Architecture Overview

### 2.1 Processing Pipeline

```
User invokes CLI with glob pattern
        |
        v
  File Collector        -- Expands glob pattern to file list
        |
        v
  File Dispatcher       -- Routes each file to the correct processor
        |
   +---------+----------+
   |                     |
   v                     v
TextProcessor    MarkitdownProcessor
   |                     |
   +----------+----------+
              |
              v
      LLM Integration   -- Sends content to OpenAI / Azure / Google
              |
              v
      Conflict Resolver  -- Ensures unique filenames
              |
              v
         Renamer         -- Performs the actual file rename (shutil.move)
```

### 2.2 Module Map

| Module | File | Responsibility |
|--------|------|----------------|
| CLI | `src/onomatool/cli.py` | Argument parsing, orchestration loop, temp dir management |
| Config | `src/onomatool/config.py` | Load/merge TOML config from `~/.onomarc` or custom path |
| File Collector | `src/onomatool/file_collector.py` | Glob pattern expansion via `glob.glob()` |
| File Dispatcher | `src/onomatool/file_dispatcher.py` | Route files to TextProcessor or MarkitdownProcessor by extension |
| Text Processor | `src/onomatool/processors/text_processor.py` | Read text files with encoding detection/conversion |
| Markitdown Processor | `src/onomatool/processors/markitdown_processor.py` | Process PDFs, DOCX, PPTX, SVG, and other formats via MarkItDown library |
| LLM Integration | `src/onomatool/llm_integration.py` | OpenAI / Azure OpenAI / Google Gemini API calls with structured output |
| Models | `src/onomatool/models.py` | Pydantic models for structured LLM responses per naming convention |
| Prompts | `src/onomatool/prompts.py` | Default and configurable prompt templates |
| Conflict Resolver | `src/onomatool/conflict_resolver.py` | Numeric suffix deduplication |
| Renamer | `src/onomatool/renamer.py` | `shutil.move` with extension preservation and conflict resolution |
| Image Utils | `src/onomatool/utils/image_utils.py` | SVG-to-PNG conversion via CairoSVG + Pillow |

---

## 3. CLI Interface

### 3.1 Usage

```
onomatool [-h] [-f FORMAT] [-s] [-v] [-vv] [-d] [-i] [--debug] [--config PATH] pattern
```

### 3.2 Arguments and Flags

| Argument | Short | Type | Description |
|----------|-------|------|-------------|
| `pattern` | - | positional | Glob pattern to match files (e.g., `'*.pdf'`, `'docs/**/*.md'`) |
| `--format` | `-f` | choice | Force file format: `text`, `markdown`, `pdf`, `docx`, `image` (**NOT YET IMPLEMENTED** - parsed but not wired to processors) |
| `--save-config` | `-s` | flag | Write default config to `~/.onomarc` and exit |
| `--verbose` | `-v` | flag | Print basic LLM debug info (provider, model, base URL) |
| `--very-verbose` | `-vv` | flag | Print full LLM request/response details, token counts, schemas |
| `--dry-run` | `-d` | flag | Show intended renames without modifying files |
| `--interactive` | `-i` | flag | After `--dry-run`, prompt user `[y/N]` to confirm renames |
| `--debug` | - | flag | Preserve temp files (SVG PNGs, PDF page images, extracted markdown) |
| `--config` | - | path | Use a custom config file instead of `~/.onomarc` |
| `--undo` | - | flag/arg | **PLANNED**: Reverse a rename session. Optional session ID argument; defaults to most recent |
| `--history` | - | flag | **PLANNED**: List recent rename sessions (ID, timestamp, file count, directory) |
| `--check` | - | flag | **PLANNED**: Verify all system dependencies (LibreOffice, ImageMagick, Cairo) and report status |
| `--exclude` | - | glob | **PLANNED**: Exclude files matching this glob pattern from processing |
| `--sort` | - | choice | **PLANNED**: Sort order for file processing: `name` (default), `size`, `type`, `modified` |

### 3.3 Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unhandled error |
| 130 | User cancelled (Ctrl+C) |

---

## 4. Configuration System

### 4.1 Config File

- **Path**: `~/.onomarc` (default) or custom via `--config`
- **Format**: TOML
- **Generation**: `onomatool --save-config`
- **Merge behavior**: User config is deep-merged over `DEFAULT_CONFIG`. Missing keys in the user file inherit defaults. (**BUG**: current code returns file config OR defaults without merging -- must be fixed.)
- **Validation**: A Pydantic Settings model replaces the plain `DEFAULT_CONFIG` dict. All config values are validated on load with clear error messages. Invalid provider, out-of-range word counts, and empty required fields are rejected at startup. (**PLANNED**: full replacement of dict-based config throughout the codebase.)
- **Versioning**: Config files include a `config_version` key. When loading an older version, the tool auto-migrates by merging old values into the new schema. `--save-config` regenerates with the latest schema while preserving user values.

### 4.2 Configuration Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_provider` | string | `"openai"` | LLM provider: `"openai"`, `"google"`, or `"mock"` (testing) |
| `openai_api_key` | string | `""` | OpenAI API key (also reads `OPENAI_API_KEY` env var) |
| `openai_base_url` | string | `"https://api.openai.com/v1"` | OpenAI-compatible base URL (supports local LLMs) |
| `use_azure_openai` | bool | `false` | Enable Azure OpenAI instead of standard OpenAI |
| `azure_openai_endpoint` | string | `""` | Azure OpenAI resource endpoint URL |
| `azure_openai_api_key` | string | `""` | Azure OpenAI API key (also reads `AZURE_OPENAI_API_KEY` env var) |
| `azure_openai_api_version` | string | `"2024-02-01"` | Azure OpenAI API version |
| `azure_openai_deployment` | string | `""` | Azure deployment name (also reads `AZURE_OPENAI_DEPLOYMENT` env var) |
| `google_api_key` | string | `""` | Google Generative AI API key (also reads `GOOGLE_API_KEY` env var) |
| `llm_model` | string | `"gpt-4o"` | Model name for OpenAI provider |
| `naming_convention` | string | `"snake_case"` | Naming convention for generated filenames |
| `min_filename_words` | int | `5` | Minimum words in generated filenames |
| `max_filename_words` | int | `15` | Maximum words in generated filenames |
| `system_prompt` | string | `""` | Custom system prompt (empty = use built-in default) |
| `user_prompt` | string | `""` | Custom user prompt template (empty = use built-in default) |
| `image_prompt` | string | `""` | Custom image analysis prompt (empty = use built-in default) |
| `max_retries` | int | `0` | **PLANNED**: Max LLM API retry attempts on transient failure (0 = no retry) |
| `retry_delay` | float | `1.0` | **PLANNED**: Base delay in seconds between retries (exponential backoff) |
| `rate_limit_delay` | float | `0.0` | **PLANNED**: Delay in seconds between consecutive LLM API calls (0 = no delay) |
| `history_retention_days` | int | `90` | **PLANNED**: Auto-prune rename history sessions older than this many days |
| `config_version` | int | `1` | **PLANNED**: Schema version for config migration support |
| `markitdown.enable_plugins` | bool | `false` | Enable MarkItDown plugins |
| `markitdown.docintel_endpoint` | string | `""` | Azure Document Intelligence endpoint for MarkItDown |

> **Note on word count limits**: `min_filename_words` and `max_filename_words` are currently loaded but **not enforced** in code. The hardcoded prompt text says "5 to 10 words" regardless of config values. **Fix required**: inject config values into prompt templates and add post-generation validation.

### 4.3 Supported Naming Conventions

| Convention | Config Value | Example Output | Pydantic Model | Regex Pattern |
|------------|-------------|----------------|----------------|---------------|
| Snake Case | `"snake_case"` | `my_document_file` | `SnakeCaseFilenameSuggestions` | `^[a-z0-9]+(_[a-z0-9]+)*$` |
| Camel Case | `"camelCase"` | `myDocumentFile` | `CamelCaseFilenameSuggestions` | `^[a-z0-9]+([A-Z][a-z0-9]*)*$` |
| Kebab Case | `"kebab-case"` | `my-document-file` | `KebabCaseFilenameSuggestions` | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| Pascal Case | `"PascalCase"` | `MyDocumentFile` | `PascalCaseFilenameSuggestions` | `^[A-Z][a-z0-9]*([A-Z][a-z0-9]*)*$` |
| Dot Notation | `"dot.notation"` | `my.document.file` | `DotNotationFilenameSuggestions` | `^[a-z0-9]+(\.[a-z0-9]+)*$` |
| Natural Language | `"natural language"` | `My Document File` | `NaturalLanguageFilenameSuggestions` | `^[A-Za-z0-9]+( [A-Za-z0-9]+)*$` |

Each Pydantic model enforces exactly 3 suggestions, max 128 characters per suggestion, and validates format via `field_validator`.

### 4.4 Environment Variable Fallbacks

| Env Var | Overrides Config Key |
|---------|---------------------|
| `OPENAI_API_KEY` | `openai_api_key` |
| `GOOGLE_API_KEY` | `google_api_key` |
| `AZURE_OPENAI_ENDPOINT` | `azure_openai_endpoint` |
| `AZURE_OPENAI_API_KEY` | `azure_openai_api_key` |
| `AZURE_OPENAI_DEPLOYMENT` | `azure_openai_deployment` |

---

## 5. File Processing

### 5.1 File Routing and Filtering

The `FileDispatcher` routes files based on extension.

**Pre-processing filters** (applied before routing):
- **Non-regular files**: Symlinks, directories, FIFOs, sockets, device files, and broken symlinks are **skipped** with a warning logged. Only `os.path.isfile()` entries are processed.
- **Cross-directory behavior**: Conflict resolution is **per-directory**. Two files in different directories can receive the same name independently. This is standard filesystem behavior.

**Routing by extension**:

**Text Processor** handles:
`.txt`, `.md`, `.note`, `.text`, `.log`, `.csv`, `.json`, `.xml`, `.html`, `.htm`, `.py`, `.js`, `.css`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`

**Markitdown Processor** handles everything else, including:
`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.svg`, and any other extension not in the text list.

### 5.2 Processing Strategies by File Type

| File Type | Strategy | Output to LLM |
|-----------|----------|---------------|
| **Text files** (`.txt`, `.md`, etc.) | `TextProcessor`: encoding detection via chardet, UTF-8 conversion if needed, direct read | Plain text content string |
| **PDF** | `MarkitdownProcessor`: MarkItDown for markdown extraction + PyMuPDF for per-page PNG images | Dict: `{markdown, images[], tempdir}` |
| **PPTX** | `MarkitdownProcessor`: MarkItDown for markdown + LibreOffice PDF conversion + ImageMagick JPEG generation | Dict: `{markdown, images[], tempdir}` |
| **SVG** | CLI converts SVG to PNG via `convert_svg_to_png()`, then MarkItDown for markdown | Image-based LLM analysis (PNG only, never raw SVG) |
| **DOCX, XLSX** | `MarkitdownProcessor`: MarkItDown library conversion to markdown | Plain text content string |
| **Images** (`.jpg`, `.png`, `.webp`, `.gif`, `.bmp`) | Base64-encoded directly in CLI, sent as image input to LLM | Image content via OpenAI vision API |

### 5.3 Multi-Pass LLM Strategy (PDF, PPTX, SVG)

For files that produce both text and images, a three-pass LLM approach is used:

1. **Pass 1 - Image Analysis**: Each page/slide image is sent individually to the LLM for filename suggestions
2. **Pass 2 - Markdown Analysis**: The full extracted markdown content is sent with the first image for context
3. **Pass 3 - Final Synthesis**: A combined prompt includes all prior image suggestions plus the full markdown, asking the LLM for 3 final filename suggestions

The fallback priority is: final suggestions > markdown suggestions > image suggestions.

### 5.4 Encoding Detection

Both `TextProcessor` and `MarkitdownProcessor` implement encoding detection:

1. Read first 10KB of file as raw bytes
2. Run `chardet.detect()` to identify encoding and confidence
3. If detected as `windows-1252`, attempt UTF-8 decode first (chardet commonly misidentifies UTF-8 with special characters)
4. If confidence < 0.7 or encoding is `None`, default to UTF-8
5. If encoding is not UTF-8/ASCII, create a temporary UTF-8 copy for processing
6. Temporary files are cleaned up after processing completes

---

## 6. LLM Integration

### 6.1 Provider Support

| Provider | Client Library | Structured Output | Image Support |
|----------|---------------|-------------------|---------------|
| **OpenAI** | `openai.OpenAI` | Pydantic via `beta.chat.completions.parse()`, fallback to JSON schema | Yes (base64 image_url) |
| **Azure OpenAI** | `openai.AzureOpenAI` | Same as OpenAI | Yes |
| **Google Gemini** | `google.generativeai` | Regex extraction from response text | **No** (planned: add Gemini vision API support) |
| **Mock** | Built-in | Static responses per naming convention | N/A |

### 6.2 Request Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_TOKENS` | 100 | Maximum tokens in LLM response |
| `MAX_CONTENT_CHARS` | 120,000 | Maximum characters sent to LLM (~65K tokens) |
| `MAX_CONSECUTIVE_DIGITS` | 10 | Limit on digit sequences in filenames |

### 6.3 Structured Output Flow (OpenAI)

1. Select Pydantic model based on `naming_convention` config
2. Build messages array (system prompt + user prompt, or image + text prompt)
3. **Try** `client.beta.chat.completions.parse()` with Pydantic `response_format`
4. **Catch** failure, **fallback** to `client.chat.completions.create()` with JSON schema `response_format`
5. Parse response, validate exactly 3 suggestions
6. Return `list[str]` of suggestions

### 6.4 SSL Handling

For local/HTTP endpoints, SSL verification is automatically disabled:
- URLs starting with `http://`
- URLs starting with `https://10.`, `https://127.`, or `https://localhost`

### 6.5 Retry Policy (PLANNED)

LLM API calls should support configurable retry with exponential backoff:

1. On transient failure (timeout, rate limit, 5xx), wait `retry_delay * 2^attempt` seconds
2. Retry up to `max_retries` times (default 0 = fail immediately, current behavior)
3. On permanent failure (auth error, 4xx), fail immediately without retry
4. Log each retry attempt at WARNING level

**Decision rationale**: Configurable rather than always-on, so users opt in. Default of 0 retries preserves current fail-fast behavior.

### 6.6 Rate Limiting (PLANNED)

To prevent runaway API costs on large batches:

- Insert `rate_limit_delay` seconds between consecutive API calls (default 0)
- A single PDF with 20 pages generates 22+ API calls; a batch of 50 PDFs can mean 1000+ calls
- Rate limiting applies to all providers

### 6.7 Token Counting

Token counting uses `tiktoken` for accurate estimation:
- `count_tokens_for_messages()`: Counts tokens for full OpenAI message arrays (handles multimodal content)
- `count_text_tokens()`: Counts tokens for plain text strings
- Falls back to `cl100k_base` encoding if model-specific encoding is unavailable

---

## 7. Conflict Resolution and Renaming

### 7.1 Conflict Resolution Algorithm

```
Input: desired_name, existing_names[]

1. If desired_name not in existing_names: return desired_name
2. Split desired_name into (base, ext)
3. counter = 2
4. Loop:
   a. candidate = "{base}_{counter}{ext}"
   b. If candidate not in existing_names: return candidate
   c. counter++
```

Example: If `report.pdf` exists, the next file becomes `report_2.pdf`, then `report_3.pdf`, etc.

### 7.2 Renaming Behavior

- The **first** of the 3 LLM suggestions is always used (the other two are discarded)
- Generating 3 suggestions is an **LLM quality technique**: forcing multiple outputs improves the quality of each individual suggestion
- The **original file extension** is always preserved regardless of what the LLM suggests
- `shutil.move()` is used for the actual rename operation
- Conflict resolution runs against the current directory listing at rename time

### 7.3 Filename Sanitization (PLANNED)

LLM suggestions must be sanitized for cross-platform safety:

1. Strip characters illegal on Windows: `< > : " / \ | ? *`
2. Reject Windows reserved names: `CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`
3. Enforce max filename length: 255 bytes (Linux/macOS), 260 chars total path (Windows)
4. Strip leading/trailing dots and spaces
5. Replace any remaining problematic characters with underscores

**Decision rationale**: The Pydantic regex patterns (`[a-z0-9_-. ]`) implicitly prevent most OS-illegal characters, but explicit sanitization adds defense-in-depth for edge cases and natural language naming convention.

### 7.4 Undo / Rename History (PLANNED)

All rename operations are logged to an SQLite database for undo capability:

- **Database path**: `~/.onoma_history.db`
- **Schema**: `sessions(id, timestamp, working_dir, file_count)` + `renames(id, session_id, original_path, new_path, timestamp)`
- **`--undo [session-id]`**: Reverses renames from a session. Without an ID, reverses the most recent session. Checks that files haven't been modified since rename before reverting.
- **`--history`**: Lists recent sessions (ID, timestamp, file count, working directory).
- **Session tracking**: Each CLI invocation creates a new session. Failed files are recorded with error status.
- **Data lifecycle**: Sessions older than 90 days are auto-pruned on each run. Configurable via `history_retention_days` config key. No `--clear-history` needed; pruning is automatic.

**Decision rationale**: SQLite chosen over JSON for query support, session tracking, and atomic writes. Session ID selection (not just latest) enables targeted undo without full interactive UI.

### 7.5 Dry-Run Fidelity (PLANNED)

When `--dry-run --interactive` is used, the confirmation flow should:

1. Store fully-resolved final names during dry-run preview
2. At confirmation time, re-resolve conflicts against the current directory state
3. If any names changed from the preview, display a diff showing the changes
4. Prompt for a **second confirmation** before proceeding
5. If names are identical to preview, proceed with single confirmation

**Decision rationale**: Directory contents may change between preview and confirmation. Users should see exactly what will happen before files are moved.

---

## 8. Prompt System

### 8.1 Prompt Templates

Three prompt templates are used, all overridable via config:

| Prompt | Config Key | Template Variables | Used For |
|--------|-----------|-------------------|----------|
| System Prompt | `system_prompt` | None | Sets LLM role as file naming assistant |
| User Prompt | `user_prompt` | `{naming_convention}`, `{content}` | Text/document file analysis |
| Image Prompt | `image_prompt` | `{naming_convention}` | Image and visual content analysis |

### 8.2 Default Prompt Behavior

- **System prompt**: Instructs the LLM to avoid numbers in filenames unless critical
- **User prompt**: Asks for 3 suggestions considering who/what/when/where/why/how, 5-10 words, with rules about number usage and codebase identification
- **Image prompt**: Detailed visual analysis guidelines covering subjects, settings, activities, text content, brands, temporal indicators, with specific rules per image type (screenshots, photographs, diagrams, logos)

### 8.3 Prompt Selection Logic

- If file is an image (`.jpg`, `.png`, `.webp`, `.gif`, `.bmp`, `.svg`): use `image_prompt`
- Otherwise: use `system_prompt` + `user_prompt`
- SVG files raise a `RuntimeError` if sent directly to the LLM (must be converted to PNG first)

---

## 9. Dependencies

### 9.1 Core Python Dependencies

| Package | Min Version | Purpose |
|---------|-------------|---------|
| `markitdown` | 0.1.2 | Unified document-to-markdown conversion |
| `openai` | 1.86.0 | OpenAI and Azure OpenAI API client |
| `google-genai` | 1.20.0 | Google Generative AI client |
| `pydantic` | 2.11.7 | Structured output models and validation |
| `tiktoken` | 0.9.0 | Token counting for OpenAI models |
| `httpx` | 0.28.1 | HTTP client (used by OpenAI for SSL control) |
| `chardet` | 5.2.0 | Automatic file encoding detection |
| `cairosvg` | 2.8.2 | SVG to PNG rendering |
| `pillow` | 11.2.1 | Image processing and resizing |
| `PyMuPDF` | 1.26.1 | PDF page-to-image extraction |
| `tomli` | 2.2.1 | TOML parsing |
| `toml` | 0.10.2 | TOML writing (config save) |

### 9.2 System Dependencies

| Tool | Purpose | Required For |
|------|---------|-------------|
| LibreOffice (`soffice`) | PPTX to PDF conversion | PPTX processing |
| ImageMagick (`convert`) | PDF to JPEG conversion | PPTX slide image generation |
| Cairo libraries | SVG rendering backend | SVG processing |

### 9.3 Development Dependencies (installed via `uv sync --all-extras`)

| Package | Purpose |
|---------|---------|
| `pytest` >= 8.4.0 | Test runner |
| `pytest-cov` >= 4.0.0 | Coverage reporting |
| `ruff` >= 0.12.0 | Linting and formatting |

---

## 10. Testing

### 10.1 Test Suite Overview

| Test File | Scope | Test Count |
|-----------|-------|------------|
| `tests/test_usage_enduser.py` | End-to-end CLI workflows | 5 tests |
| `tests/test_utf8_encoding.py` | Encoding detection and conversion in MarkitdownProcessor | 13 tests |
| `tests/test_config.py` | Config loading, defaults, error handling | 3 tests |
| `tests/test_conflict_resolver.py` | Numeric suffix conflict resolution | 4 tests |
| `tests/test_renamer.py` | File rename, conflict, extension preservation | 3 tests |
| `tests/test_file_collector.py` | Glob pattern matching and recursion | 3 tests |
| `tests/test_file_dispatcher.py` | Processor routing by file extension | 3 tests |
| `tests/test_text_processor.py` | Text file reading, encoding, error handling | 3 tests |

### 10.2 Test Infrastructure

- **Mock provider**: `default_provider = "mock"` returns static suggestions without LLM calls, enabling deterministic tests
- **Mock config**: `tests/mock_config.toml` provides a complete test configuration
- **Test fixtures**: Sample files in `tests/` include `.md` notes (note_0 through note_6), `.docx` resumes, and a `.pdf` brochure
- **Temp directories**: Tests use `tempfile.mkdtemp()` and `tmp_path` fixtures for isolation

### 10.3 Running Tests

```bash
uv run pytest                              # All tests
uv run pytest tests/test_usage_enduser.py  # End-to-end tests
uv run pytest tests/test_utf8_encoding.py  # Encoding tests
uv run pytest --cov=onomatool              # With coverage
```

### 10.4 Running the Tool

```bash
# Direct execution without install (resolves deps automatically)
uvx onomatool '*.pdf'

# From development checkout
uv run onomatool '*.pdf'

# Install as global tool
uv tool install onomatool
onomatool '*.pdf'
```

---

## 11. Code Quality

### 11.1 Linting and Formatting

- **Tool**: Ruff (configured in `pyproject.toml`)
- **Line length**: 88 characters
- **Target version**: Python 3.9+
- **Quote style**: Double quotes
- **Line ending**: LF
- **Import sorting**: isort-compatible via Ruff

### 11.2 Enabled Lint Rules

| Rule Set | Description |
|----------|-------------|
| `E` | pycodestyle errors |
| `F` | pyflakes |
| `W` | pycodestyle warnings |
| `I` | isort (import sorting) |
| `B` | flake8-bugbear |
| `UP` | pyupgrade |
| `C4` | flake8-comprehensions |

`E501` (line-too-long) is ignored in favor of the formatter.

### 11.3 Quality Commands

```bash
uv run ruff check --fix .          # Lint with auto-fix
uv run ruff format .               # Format code
uv run ruff check . && uv run ruff format --check .  # Validate (CI)
```

---

## 12. Safety and Security

### 12.1 File Safety

- **No overwrites**: Conflict resolver ensures unique names before any rename
- **Extension preservation**: Original file extension is always retained
- **Dry-run mode**: Full preview of all changes before execution
- **Interactive confirmation**: Optional user prompt after dry-run
- **Encoding safety**: Original files are never modified; temp copies are used for encoding conversion
- **Temp file cleanup**: Automatic cleanup of all temporary files (unless `--debug`)

### 12.2 API Safety

- **SSL flexibility**: Auto-disables SSL verification only for explicitly local endpoints
- **Content truncation**: File content capped at 120,000 characters before sending to LLM
- **Token limiting**: LLM responses limited to 100 tokens
- **SVG guard**: RuntimeError raised if raw SVG is ever sent directly to LLM (must be PNG)
- **Graceful errors**: All API failures caught and reported without crashing

### 12.3 Sensitive Data

- API keys can be stored in config file or environment variables
- No API keys are logged even in verbose mode
- Base64 image data is redacted in verbose output as `[[base64_image]]`
- Text content is redacted in verbose output as `[[file_content]]` (except for image prompts)

---

## 13. Logging (PLANNED)

### 13.1 Migration from print() to logging

All `print()` calls should be replaced with Python's `logging` module:

| Level | Usage |
|-------|-------|
| `DEBUG` | Encoding detection details, temp file paths, API request/response bodies (replaces `-vv`) |
| `INFO` | File processing progress, rename results (replaces default `print()`) |
| `WARNING` | Skipped files, retry attempts, missing optional dependencies |
| `ERROR` | API failures, file processing errors, encoding failures |

### 13.2 Configuration

- `--verbose` maps to `INFO` level
- `--very-verbose` maps to `DEBUG` level
- Default level: `WARNING` (only errors and skipped files)
- Optional log file output via config key `log_file`

---

## 14. Progress and UX (PLANNED)

### 14.1 Progress Bar

For batch processing, display a progress bar using `tqdm` or `rich`:

- Show: `[current/total] filename ... [elapsed / ETA]`
- Update per-file completion
- Suppress progress bar when output is piped (detect non-TTY)
- Show summary at end: `Processed X files: Y renamed, Z failed, W skipped`

### 14.2 Batch Error Handling

When a file fails mid-batch:

1. Log the error at ERROR level
2. Record the failure in the rename history database (session continues)
3. Continue processing remaining files
4. Print a summary of failures at the end

**Decision rationale**: Continue-on-error is more useful than fail-fast for batch operations. The undo log captures what was actually renamed, enabling selective rollback.

---

## 15. System Dependency Health Check (PLANNED)

### 15.1 `--check` Command

`onomatool --check` verifies all system dependencies:

```
Checking system dependencies...
  Python 3.12.1           OK
  LibreOffice (soffice)   OK (v24.2)
  ImageMagick (convert)   OK (v7.1)
  Cairo libraries         OK
  PyMuPDF                 OK (v1.26.1)
  cairosvg                OK (v2.8.2)

All dependencies satisfied.
```

### 15.2 Runtime Detection

When a file type requires a missing system dependency:

1. Print a clear error message naming the missing tool and how to install it
2. Skip the file (do not silently return `None`)
3. Continue processing other files

**Decision rationale**: Both a proactive check command AND runtime detection are needed. The check command helps at setup time; runtime messages help when processing unexpected file types.

---

## 16. File Filtering (PLANNED)

### 16.1 Exclude Patterns

- `--exclude` flag accepts glob patterns to skip files: `onomatool '**/*' --exclude '*.min.js' --exclude '.git/**'`
- Hidden files (dotfiles) skipped by default unless explicitly matched
- Zero-byte files skipped by default

### 16.2 Sort Order

- `--sort` flag controls processing order: `name` (default), `size`, `type`, `modified`
- Deterministic ordering ensures reproducible batch results across runs

---

## 17. Debug Artifacts (PLANNED)

### 17.1 Dedicated Debug Directory

Replace scattered `/tmp/onoma_*` directories with a centralized debug artifact location:

- **Path**: `~/.onoma_debug/<session-timestamp>/`
- Contains: extracted markdown, page images, SVG PNGs, encoding conversion logs
- Replaces the current hack of anonymous `type('TempDir', ...)` objects
- Old sessions auto-cleaned after 7 days (configurable)

---

## 18. Processor Plugin System (PLANNED)

### 18.1 Plugin Interface

Define a `ProcessorProtocol` that custom processors must implement:

```python
class ProcessorProtocol(Protocol):
    def can_process(self, file_path: str) -> bool: ...
    def process(self, file_path: str) -> ProcessingResult | None: ...
```

### 18.2 Plugin Discovery

- Plugins registered via Python `entry_points` under group `onomatool.processors`
- Config key `extra_processors` can specify module paths for ad-hoc loading
- Built-in processors (Text, Markitdown) always take precedence over plugins for their registered extensions

---

## 19. Target Architecture (PLANNED REFACTOR)

### 19.1 Problem

The CLI orchestration loop (`cli.py`, ~370 lines) contains deeply nested branches handling 4+ result type variants (SVG, PDF/PPTX with images, dict-with-tempdir, plain string). Rename logic is duplicated 4+ times.

### 19.2 Proposed Interfaces

```python
@dataclass
class ProcessingResult:
    """Unified result from any processor."""
    markdown: str = ""
    images: list[str] = field(default_factory=list)
    tempdir: TemporaryDirectory | None = None
    source_path: str = ""
    file_type: str = ""

class RenameOrchestrator:
    """Coordinates the full rename pipeline for a single file."""
    def __init__(self, config: OnomatoolConfig, verbose_level: int, debug: bool): ...
    def process_file(self, file_path: str) -> ProcessingResult | None: ...
    def get_suggestions(self, result: ProcessingResult) -> list[str]: ...
    def execute_rename(self, file_path: str, suggestion: str, dry_run: bool) -> RenameRecord: ...

class LLMProvider(Protocol):
    """Provider interface for swappable LLM backends."""
    def get_suggestions(self, content: str, images: list[str], config: OnomatoolConfig) -> list[str]: ...
    def supports_images(self) -> bool: ...

class SuggestionStrategy(Protocol):
    """Strategy for orchestrating LLM calls based on file type + provider capabilities."""
    def get_suggestions(self, result: ProcessingResult, provider: LLMProvider) -> list[str]: ...

@dataclass
class RenameRecord:
    """Single rename operation for history tracking."""
    original_path: str
    new_path: str
    suggestion_used: str
    all_suggestions: list[str]
    timestamp: datetime
    success: bool
    error: str | None = None

class OnomatoolConfig(BaseSettings):
    """Pydantic Settings model replacing DEFAULT_CONFIG dict."""
    config_version: int = 2
    default_provider: Literal["openai", "google", "mock"] = "openai"
    naming_convention: str = "snake_case"  # validated against NAMING_CONVENTION_MODELS
    min_filename_words: int = Field(default=5, ge=1, le=50)
    max_filename_words: int = Field(default=15, ge=1, le=50)
    # ... all other config keys with types and validators
```

### 19.3 Suggestion Strategies

Strategies are auto-selected based on file type and provider capabilities:

| Strategy | When Used | LLM Calls |
|----------|-----------|-----------|
| `TextOnlySuggestionStrategy` | Text files, DOCX, XLSX; or provider doesn't support images | 1 call (content only) |
| `ImageOnlySuggestionStrategy` | Image files (JPG, PNG, etc.) | 1 call (image only) |
| `MultiPassSuggestionStrategy` | PDF, PPTX, SVG with image-capable provider | N+2 calls (per-page images + markdown + synthesis) |

Strategy selection is automatic with no user override. Simpler providers (Google without image support) automatically degrade to `TextOnlySuggestionStrategy`.

### 19.4 Migration Strategy

1. Introduce `ProcessingResult` dataclass; update processors to return it
2. Introduce `OnomatoolConfig` Pydantic model; replace dict-based config
3. Extract `RenameOrchestrator` from `cli.py` main loop
4. Define `LLMProvider` protocol; refactor OpenAI/Azure/Google into separate provider classes
5. Extract `SuggestionStrategy` implementations from the orchestrator
6. Simplify `cli.py` to argument parsing + orchestrator invocation
7. Each step is independently testable and deployable

### 19.5 Dependency Resilience

The `LLMProvider` protocol abstracts over SDK-specific APIs, providing resilience against:

- **OpenAI SDK beta API changes**: `beta.chat.completions.parse()` is wrapped inside `OpenAIProvider`; if removed, only that class needs updating
- **Google SDK migration**: `google.generativeai` to `google-genai` migration is contained within `GoogleProvider`
- **MarkItDown pre-1.0 instability**: Processor implementations wrap MarkItDown calls with error handling

**CI verification**: Weekly CI runs test against latest dependency versions to detect breakage early.

---

## 20. Implementation Roadmap

### Phase 1: Stabilize + Architecture (P0)

Bug fixes and architectural refactor to create a solid foundation for new features.

| Item | Type | Description |
|------|------|-------------|
| Config deep-merge | Bug fix | `get_config()` must merge user file over `DEFAULT_CONFIG` |
| Word count enforcement | Bug fix | Inject `min/max_filename_words` into prompts; add post-validation |
| `--format` TODO comments | Bug fix | Mark unimplemented code paths with TODO comments |
| Skip non-regular files | Bug fix | Filter out symlinks, FIFOs, etc. before processing |
| `OnomatoolConfig` Pydantic model | Architecture | Replace `DEFAULT_CONFIG` dict with validated Pydantic Settings |
| `ProcessingResult` dataclass | Architecture | Unified processor return type |
| `RenameOrchestrator` extraction | Architecture | Extract from `cli.py` main loop |
| `LLMProvider` protocol | Architecture | Abstract OpenAI/Azure/Google into swappable providers |
| `SuggestionStrategy` pattern | Architecture | Extract multi-pass logic into composable strategies |
| Config versioning | Architecture | Add `config_version` key; auto-migrate old configs |
| Logging migration | Architecture | Replace `print()` with Python `logging` module |

### Phase 2: UX + Safety (P1)

User-facing improvements on the refactored foundation.

| Item | Type | Description |
|------|------|-------------|
| Progress bar | UX | `tqdm`/`rich` progress display for batch processing |
| Undo system (SQLite) | Feature | Rename history database with `--undo`, `--history` |
| History auto-prune | Feature | Auto-delete sessions older than 90 days |
| Filename sanitization | Safety | Cross-platform filename safety rules |
| Retry with backoff | Resilience | Configurable `max_retries` / `retry_delay` |
| Rate limiting | Cost control | Configurable `rate_limit_delay` between API calls |
| `--check` health command | UX | Verify system dependencies |
| Runtime dependency detection | UX | Clear error messages for missing LibreOffice/ImageMagick/Cairo |
| Dry-run fidelity | UX | Re-display diff + second confirmation when names change |
| `--exclude` patterns | Feature | Glob-based file exclusion |
| `--sort` ordering | Feature | Deterministic file processing order |
| Batch error summary | UX | Continue-on-error with end-of-run failure report |

### Phase 3: Extensibility + Parity (P2)

Ecosystem features and provider parity.

| Item | Type | Description |
|------|------|-------------|
| Google Gemini image support | Feature | Add Gemini vision API for image analysis |
| Processor plugin system | Extensibility | `ProcessorProtocol` with `entry_points` discovery |
| `--format` flag implementation | Feature | Wire format override to FileDispatcher |
| Dedicated debug directory | Improvement | Centralized `~/.onoma_debug/` with auto-cleanup |
| Parallel processing | Performance | Async file processing with configurable concurrency |
| Weekly CI dep testing | Infrastructure | Test against latest dependency versions |

---

## 21. Test Requirements

### 21.1 Coverage Target

Minimum 80% line coverage across `src/onomatool/`.

### 21.2 Test Matrix for Planned Features

**Phase 1 Tests:**

| Feature | Required Test Scenarios |
|---------|----------------------|
| Config deep-merge | Partial config inherits defaults; nested `markitdown` section merges; empty config returns all defaults |
| Config validation | Invalid provider rejected; out-of-range word counts rejected; empty API key with cloud provider warns; valid config passes |
| Config versioning | Old version auto-migrates; current version loads cleanly; future version warns |
| ProcessingResult | All processors return ProcessingResult; text-only has empty images; PDF has images+markdown |
| RenameOrchestrator | Processes single file end-to-end; handles processor failure; records history |
| LLMProvider protocol | OpenAI, Azure, Google, Mock all conform to protocol; provider swap doesn't break orchestrator |
| Non-regular file skip | Symlinks skipped with warning; directories skipped; regular files processed |

**Phase 2 Tests:**

| Feature | Required Test Scenarios |
|---------|----------------------|
| Undo system | Undo latest session; undo by session ID; undo with modified file refuses; undo with missing file warns |
| History lifecycle | Auto-prune removes old sessions; recent sessions preserved; empty DB doesn't crash |
| Filename sanitization | Windows-illegal chars stripped; reserved names rejected; path length enforced; clean names pass through |
| Retry | Transient 5xx retried up to max; permanent 4xx not retried; max_retries=0 fails immediately |
| Rate limiting | Delay inserted between calls; delay=0 has no effect |
| Dry-run fidelity | Unchanged names proceed with single confirmation; changed names show diff + re-confirm |
| Progress bar | Displays on TTY; suppressed on pipe; shows correct count |

**Phase 3 Tests:**

| Feature | Required Test Scenarios |
|---------|----------------------|
| Google images | Image files processed with Google provider; non-image files use text-only strategy |
| Plugin system | Custom plugin discovered via entry_points; plugin can_process() respected; built-in takes precedence |
| Format override | `--format pdf` forces MarkitdownProcessor for .txt file; unknown format rejected |

---

## 22. Data Privacy

File contents (text, images, encoded documents) are sent to external LLM APIs (OpenAI, Azure OpenAI, Google) for analysis. Users are responsible for:

- Understanding that file contents leave the local machine when using cloud providers
- Using local LLM endpoints (`openai_base_url = "http://localhost:..."`) for sensitive data
- Configuring Azure OpenAI with private endpoints for enterprise compliance
- Reviewing files before processing with `--dry-run` to verify which files will be sent

The tool does not add any data sensitivity detection or content filtering. The data flow is documented here for transparency.

---

## 23. Decisions Log

Summary of key design decisions made during spec refinement:

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Why generate 3 suggestions if only 1 is used? | LLM quality technique | Requesting multiple outputs forces the LLM to consider more options, improving overall quality |
| 2 | `--format` flag status | Keep as placeholder, add TODO comments | Flag is parsed but unused; document as not-yet-implemented, mark code with TODOs |
| 3 | Config loading behavior | Fix: deep-merge over defaults | Current all-or-nothing loading is a bug; user configs with partial keys should inherit defaults |
| 4 | Word count limits (`min/max_filename_words`) | Fix: enforce them | Config keys exist but have no effect; inject into prompts and add post-validation |
| 5 | Error handling mid-batch | Continue + log to SQLite | Failed files are recorded; processing continues; summary at end |
| 6 | Filename sanitization | Add cross-platform sanitization | Strip OS-illegal chars, enforce length limits, reject reserved names |
| 7 | API cost control | Add configurable rate limiting | Delay between API calls prevents runaway costs on large batches |
| 8 | Google Gemini image support | Add Gemini vision API | Achieve feature parity across all providers |
| 9 | Logging approach | Migrate to Python `logging` module | Replace print() with structured, level-based logging |
| 10 | Undo mechanism | SQLite history database | Full session tracking with `--undo` flag; SQLite for query support |
| 11 | CLI architecture | Refactor with prescribed interfaces | Extract `RenameOrchestrator`, `ProcessingResult`, `LLMProvider` protocol |
| 12 | Parallel processing | Future improvement | Async processing with configurable concurrency; documented but not immediate |
| 13 | Dry-run fidelity | Re-display + second confirmation | If resolved names differ from preview, show diff and re-prompt |
| 14 | LLM retry policy | Configurable (default off) | `max_retries` and `retry_delay` config keys; exponential backoff |
| 15 | Debug temp files | Dedicated `~/.onoma_debug/` directory | Centralized, auto-cleaned, replaces anonymous temp dir hack |
| 16 | Progress indication | Add progress bar (tqdm/rich) | Essential UX for long-running batch operations |
| 17 | System dependency checks | `--check` command + runtime detection | Proactive health check AND clear error messages when dependencies missing |
| 18 | Processor extensibility | Plugin system via entry_points | `ProcessorProtocol` interface with plugin discovery |
| 19 | File filtering | `--exclude` patterns + `--sort` order | Skip hidden/zero-byte files by default; user-configurable sort and exclusion |
| 20 | Cross-directory naming | Per-directory conflict resolution | Files in different directories can share names; standard filesystem semantics |
| 21 | Special files | Skip non-regular files | Symlinks, FIFOs, sockets, broken links skipped with warning |
| 22 | Data privacy | User's responsibility | Document data flow but don't add content filtering; local endpoints available |
| 23 | LLM quality guardrails | Trust the LLM | Format validation is sufficient; users switch models if quality is poor |
| 24 | Dependency resilience | LLMProvider protocol + weekly CI | Abstract providers absorb SDK changes; CI detects breakage early |
| 25 | Config validation | Pydantic Settings model (full replacement) | Replaces DEFAULT_CONFIG dict; type safety throughout codebase |
| 26 | Implementation priority | Bugs + architecture first (Phase 1) | Stabilize foundation before adding features |
| 27 | History lifecycle | Auto-prune by age (90 days) | Configurable retention; automatic cleanup; no manual command needed |
| 28 | Test coverage | Feature test matrix + 80% target | Each feature requires happy path, error path, and edge case tests |
| 29 | Config migration | Versioned config + regenerate command | `config_version` key; `--save-config` merges old values into new schema |
| 30 | Multi-pass ownership | Strategy pattern | `SuggestionStrategy` protocol; auto-selected by file type + provider caps |
| 31 | Strategy override | Auto-select only | No user config override; strategy determined by capabilities |
| 32 | Undo scope | Session ID selection | `--undo [session-id]` + `--history`; all-or-nothing per session |
| 33 | Config model scope | Full Pydantic replacement | All modules receive typed config; bigger change but cleaner long-term |

---

## 24. Project Structure

```
Onoma/
|-- pyproject.toml              # Package metadata, dependencies, build config
|-- requirements.txt            # Pinned dependency versions
|-- MANIFEST.in                 # Distribution file inclusion rules
|-- LICENSE                     # MIT License
|-- README.md                   # User-facing documentation
|-- ARCHITECTURE.md             # Architecture diagrams and design notes
|-- AZURE_OPENAI_SETUP.md      # Azure OpenAI configuration guide
|-- CHANGELOG.md                # Version history
|-- CLAUDE.md                   # AI assistant project instructions
|-- FILETREE.md                 # File tree reference
|-- SPEC.md                     # This document
|-- scripts/
|   |-- build.sh                # Build automation
|   |-- test_install.sh         # Isolated install testing
|   +-- check-format.sh        # Import sorting and formatting
|-- src/onomatool/
|   |-- __init__.py             # Package init, __version__
|   |-- cli.py                  # CLI entry point and orchestration
|   |-- config.py               # TOML config loading
|   |-- file_collector.py       # Glob pattern expansion
|   |-- file_dispatcher.py      # Extension-based processor routing
|   |-- llm_integration.py      # LLM API calls (OpenAI/Azure/Google)
|   |-- models.py               # Pydantic models for structured output
|   |-- prompts.py              # Prompt templates
|   |-- conflict_resolver.py    # Filename deduplication
|   |-- renamer.py              # File rename operations
|   |-- processors/
|   |   |-- markitdown_processor.py  # MarkItDown-based processor
|   |   +-- text_processor.py        # Plain text processor
|   +-- utils/
|       +-- image_utils.py      # SVG-to-PNG conversion
+-- tests/
    |-- mock_config.toml        # Test configuration
    |-- test_config.py          # Config tests
    |-- test_conflict_resolver.py
    |-- test_file_collector.py
    |-- test_file_dispatcher.py
    |-- test_renamer.py
    |-- test_text_processor.py
    |-- test_usage_enduser.py   # End-to-end CLI tests
    |-- test_utf8_encoding.py   # Encoding tests
    |-- note_0.md ... note_6.md # Sample text files
    |-- resume_1.docx, resume_2.docx  # Sample documents
    +-- brochure_1.pdf          # Sample PDF
```
