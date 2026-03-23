# OnomaTool — Comprehensive Test Specifications

## 1. Overview

### 1.1 Purpose
This document defines the complete test specifications for OnomaTool, covering every module in `src/onomatool/`, every planned feature in the beads task list, and every deficiency in the existing test suite. Tests are organized by module, then by category (unit, integration, edge case, security, performance).

### 1.2 Coverage Target
Minimum **80% line coverage** across `src/onomatool/` (SPEC §21.1).

### 1.3 Test Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| `tests/conftest.py` | Shared fixtures | `EXAMPLE_FILES_DIR`, `MOCK_CONFIG`, `work_dir`, `copy_example_file` |
| `tests/mock_config.toml` | Mock LLM config | `default_provider = "mock"` for deterministic tests |
| `example_files/` | Read-only samples | `.md`, `.docx`, `.pdf`, `.png`, `.jpg` files (permissions: `r--r--r--`) |

### 1.4 Conventions
- Test files: `tests/test_<module>.py`
- Test functions: `test_<behavior_under_test>[_<scenario>]`
- Destructive tests (rename, move, delete) MUST use `work_dir` or `copy_example_file` fixtures
- Read-only tests MAY reference `example_files/` directly
- All temp directories auto-cleaned via fixture teardown
- Mock provider used for all tests that don't specifically test LLM integration

---

## 2. Test Infrastructure Updates (Existing Tests)

### 2.1 tests/test_config.py — UPDATES REQUIRED

**Current state**: 3 tests. Uses `toml.dumps()` directly. Does not test deep-merge, validation, or env var fallbacks.

| Test Case | Status | Change Required |
|-----------|--------|-----------------|
| `test_get_config_default` | KEEP | No change needed |
| `test_get_config_valid` | UPDATE | Replace `toml.dumps()` with `tomli`-compatible write (aligns with bug `OnomaTool-crp`) |
| `test_get_config_error` | UPDATE | Remove monkeypatch of `toml.load`; instead write genuinely invalid TOML content |

**New tests to add:**

#### TC-CFG-001: Config deep-merge preserves defaults for missing keys
- **Precondition**: Config file contains only `default_provider = "mock"`
- **Steps**: Load config via `get_config(path)`
- **Expected**: Returned dict contains `default_provider = "mock"` AND `llm_model = "gpt-4o"` AND `naming_convention = "snake_case"` AND nested `markitdown.enable_plugins = false`
- **Validates**: Bug fix `OnomaTool-v8d`

#### TC-CFG-002: Config deep-merge handles nested markitdown section
- **Precondition**: Config file contains `[markitdown]\nenable_plugins = true` but no top-level keys
- **Steps**: Load config
- **Expected**: `markitdown.enable_plugins = true`, all top-level keys inherit defaults

#### TC-CFG-003: Empty config file returns all defaults
- **Precondition**: Config file exists but is empty (0 bytes)
- **Steps**: Load config
- **Expected**: Result equals `DEFAULT_CONFIG`

#### TC-CFG-004: Environment variable fallback for OPENAI_API_KEY
- **Precondition**: No config file; env var `OPENAI_API_KEY=test-key-123` set
- **Steps**: Load config, check `openai_api_key`
- **Expected**: Value is `"test-key-123"`
- **Validates**: SPEC §4.4

#### TC-CFG-005: Config file value takes precedence over env var
- **Precondition**: Config file has `openai_api_key = "from-file"`, env var `OPENAI_API_KEY=from-env`
- **Steps**: Load config
- **Expected**: Value is `"from-file"`

#### TC-CFG-006: All env var fallbacks work (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, GOOGLE_API_KEY)
- **Steps**: Set each env var, load config with no file
- **Expected**: Each config key populated from its env var

### 2.2 tests/test_conflict_resolver.py — UPDATES REQUIRED

**Current state**: 4 tests. All pass. Missing edge cases.

| Test Case | Status | Change Required |
|-----------|--------|-----------------|
| `test_no_conflict` | KEEP | No change |
| `test_single_conflict` | KEEP | No change |
| `test_multiple_conflicts` | KEEP | No change |
| `test_conflict_with_number_suffix` | KEEP | No change |

**New tests to add:**

#### TC-CR-001: Conflict resolution with no extension
- **Input**: `desired_name="README"`, `existing_names=["README"]`
- **Expected**: Returns `"README_2"`

#### TC-CR-002: Conflict resolution with dotfile
- **Input**: `desired_name=".gitignore"`, `existing_names=[".gitignore"]`
- **Expected**: Returns `".gitignore_2"` (os.path.splitext behavior)

#### TC-CR-003: Conflict resolution with multiple dots
- **Input**: `desired_name="archive.tar.gz"`, `existing_names=["archive.tar.gz"]`
- **Expected**: Returns `"archive.tar_2.gz"` (splitext splits on last dot)

#### TC-CR-004: Large number of conflicts (performance)
- **Input**: 1000 existing files `file.txt`, `file_2.txt` ... `file_1000.txt`
- **Expected**: Returns `"file_1001.txt"` in < 100ms

#### TC-CR-005: Empty existing_names list
- **Input**: `desired_name="file.txt"`, `existing_names=[]`
- **Expected**: Returns `"file.txt"`

### 2.3 tests/test_renamer.py — UPDATES REQUIRED

**Current state**: 3 tests. All pass. Missing: no-op line 21 bug test, cross-directory behavior.

**New tests to add:**

#### TC-RN-001: Renamer does not leave dead code artifacts
- **Validates**: Bug `OnomaTool-866` (line 21 no-op)
- **Steps**: Rename a file; verify only one new file exists in directory
- **Expected**: No side effects from the unused `os.path.join()` call

#### TC-RN-002: Rename across directories is not supported
- **Steps**: Call `rename_file("/tmp/a/file.txt", "new_name.txt")`
- **Expected**: File renamed within `/tmp/a/`, not moved elsewhere

#### TC-RN-003: Rename preserves file content
- **Steps**: Write known content, rename, read renamed file
- **Expected**: Content identical after rename

#### TC-RN-004: Rename with unicode filename
- **Steps**: Create file `café.txt`, rename to `renamed.txt`
- **Expected**: Succeeds without error

### 2.4 tests/test_usage_enduser.py — UPDATES REQUIRED

**Current state**: 5 tests. All pass after conftest.py refactor.

**New tests to add:**

#### TC-E2E-001: Exit code 0 on success
- Already covered by `test_basic_rename`. KEEP.

#### TC-E2E-002: Exit code 130 on Ctrl+C
- **Steps**: Monkeypatch `collect_files` to raise `KeyboardInterrupt`
- **Expected**: `main()` returns 130

#### TC-E2E-003: Exit code 1 on unhandled error
- **Steps**: Monkeypatch `collect_files` to raise `RuntimeError`
- **Expected**: `main()` returns 1

#### TC-E2E-004: --interactive without --dry-run is rejected
- **Steps**: `main(["*.txt", "--config", MOCK_CONFIG, "--interactive"])`
- **Expected**: SystemExit raised (argparse error)

#### TC-E2E-005: No pattern argument shows error
- **Steps**: `main(["--config", MOCK_CONFIG])`
- **Expected**: SystemExit raised

#### TC-E2E-006: --save-config creates ~/.onomarc
- **Steps**: `main(["--save-config"])` with monkeypatched home dir
- **Expected**: Config file created, return 0

#### TC-E2E-007: Multiple files in batch all get renamed
- **Steps**: Copy `note_0.md` and `note_1.md` to work_dir, run with glob
- **Expected**: Both files renamed to mock suggestions

#### TC-E2E-008: Interactive mode with 'N' aborts
- **Steps**: Monkeypatch input to return "N"
- **Expected**: No files renamed, "Aborted" in output

### 2.5 tests/test_utf8_encoding.py — UPDATES REQUIRED

**Current state**: 13 tests, 1 FAILING (`test_unicode_decode_error_handling`).

#### TC-UTF8-FIX-001: Fix test_unicode_decode_error_handling
- **Problem**: Test mocks `self.processor.md.convert` to raise `UnicodeDecodeError`, but `process()` has a fallback that reads `.txt` files directly when MarkItDown fails with Unicode errors. So the result is the file content, not `None`.
- **Fix**: Either (a) assert `result` is a string containing the em dash content (matching actual behavior), or (b) use a non-text extension (`.bin`) so the fallback doesn't trigger.
- **Recommended**: Option (a) — the fallback is correct behavior; the test expectation is wrong.

### 2.6 tests/test_file_collector.py — UPDATES REQUIRED

**New tests to add:**

#### TC-FC-001: Symlinks are included by glob (pre-filter test)
- **Steps**: Create a symlink in tmp_path, glob for it
- **Expected**: Symlink path appears in results (filtering happens later, not in collector)

#### TC-FC-002: Empty glob pattern returns empty list
- **Steps**: `collect_files("")`
- **Expected**: Returns `[]`

#### TC-FC-003: Pattern with special characters
- **Steps**: Create file `file [1].txt`, glob for `*[[]1]*.txt`
- **Expected**: File found

### 2.7 tests/test_file_dispatcher.py — NO CHANGES NEEDED
Current 3 tests adequately cover routing logic.

### 2.8 tests/test_text_processor.py — UPDATES REQUIRED

**New tests to add:**

#### TC-TP-001: Read only first 10KB for encoding detection
- **Validates**: Bug `OnomaTool-l1k`
- **Steps**: Create a 1MB file, mock `chardet.detect`, call `detect_encoding`
- **Expected**: `chardet.detect` receives ≤ 10240 bytes

#### TC-TP-002: Process large file without memory issues
- **Steps**: Create 10MB text file, call `process()`
- **Expected**: Returns content string, completes in < 5s

#### TC-TP-003: Process file with BOM (UTF-8-SIG)
- **Steps**: Write file with UTF-8 BOM prefix `\xef\xbb\xbf`
- **Expected**: Content returned without BOM characters

---

## 3. Configuration System Tests (Phase 1 — OnomaTool-cex, OnomaTool-v8d, OnomaTool-crp, OnomaTool-36p)

### 3.1 OnomatoolConfig Pydantic Model (test_config_model.py)

#### TC-CM-001: Valid config loads without error
- **Input**: All fields set to valid values
- **Expected**: `OnomatoolConfig` instance created, all fields accessible with correct types

#### TC-CM-002: Invalid provider rejected
- **Input**: `default_provider = "invalid_provider"`
- **Expected**: `ValidationError` raised, message mentions allowed values

#### TC-CM-003: Out-of-range min_filename_words rejected
- **Input**: `min_filename_words = 0`
- **Expected**: `ValidationError` (ge=1 constraint)

#### TC-CM-004: Out-of-range max_filename_words rejected
- **Input**: `max_filename_words = 100`
- **Expected**: `ValidationError` (le=50 constraint)

#### TC-CM-005: min > max filename words rejected
- **Input**: `min_filename_words = 20`, `max_filename_words = 5`
- **Expected**: `ValidationError` with cross-field validation

#### TC-CM-006: Empty API key with cloud provider warns
- **Input**: `default_provider = "openai"`, `openai_api_key = ""`
- **Expected**: Warning logged or validation error (depending on design choice)

#### TC-CM-007: Mock provider does not require API key
- **Input**: `default_provider = "mock"`, no API keys set
- **Expected**: Config loads successfully

#### TC-CM-008: Default values match SPEC §4.2
- **Steps**: Create `OnomatoolConfig()` with no arguments
- **Expected**: Every field matches its documented default

#### TC-CM-009: Naming convention validated against NAMING_CONVENTION_MODELS
- **Input**: `naming_convention = "SCREAMING_SNAKE"`
- **Expected**: `ValidationError`

#### TC-CM-010: Config serialization round-trip
- **Steps**: Create config, dump to TOML, reload
- **Expected**: All values preserved

### 3.2 Config Versioning (test_config_versioning.py)

#### TC-CV-001: Current version loads cleanly
- **Input**: Config file with `config_version = 2`
- **Expected**: Loads without migration

#### TC-CV-002: Old version auto-migrates
- **Input**: Config file with `config_version = 1` and old-style keys
- **Expected**: Migrated to version 2 schema, user values preserved

#### TC-CV-003: Future version warns
- **Input**: Config file with `config_version = 99`
- **Expected**: Warning logged, loads with best-effort parsing

#### TC-CV-004: Missing config_version treated as version 1
- **Input**: Config file with no `config_version` key
- **Expected**: Treated as version 1, migration applied

#### TC-CV-005: --save-config preserves user values
- **Steps**: Load config with custom values, run save_default_config
- **Expected**: Saved file has latest schema version AND user's custom values

### 3.3 TOML Package Alignment (OnomaTool-crp)

#### TC-TOML-001: Config loading uses tomli (not toml)
- **Steps**: Verify `import tomli` in config.py, no `import toml` for reading
- **Expected**: Only `tomli` used for TOML parsing

#### TC-TOML-002: Config saving produces valid TOML
- **Steps**: Save config, reload with `tomli.load()`
- **Expected**: No parse errors

---

## 4. Pydantic Models Tests (test_models.py)

### 4.1 Existing Coverage Gaps

The current codebase has NO test file for `models.py`. All tests below are new.

#### TC-MOD-001: Each naming convention model exists in NAMING_CONVENTION_MODELS
- **Steps**: Iterate over all 6 conventions
- **Expected**: `get_model_for_naming_convention()` returns a class for each

#### TC-MOD-002: Unsupported naming convention raises ValueError
- **Input**: `get_model_for_naming_convention("UNKNOWN")`
- **Expected**: `ValueError` raised

#### TC-MOD-003: SnakeCaseFilenameSuggestions validates correctly
- **Valid**: `["my_file_name", "another_file", "third_suggestion"]`
- **Invalid**: `["MyFileName", "another_file", "third"]` — first item fails
- **Expected**: Valid passes, invalid raises `ValidationError`

#### TC-MOD-004: CamelCaseFilenameSuggestions validates correctly
- **Valid**: `["myFileName", "anotherFile", "thirdSuggestion"]`
- **Invalid**: `["my_file_name", "x", "y"]`

#### TC-MOD-005: KebabCaseFilenameSuggestions validates correctly
- **Valid**: `["my-file-name", "another-file", "third-suggestion"]`

#### TC-MOD-006: PascalCaseFilenameSuggestions validates correctly
- **Valid**: `["MyFileName", "AnotherFile", "ThirdSuggestion"]`

#### TC-MOD-007: DotNotationFilenameSuggestions validates correctly
- **Valid**: `["my.file.name", "another.file", "third.suggestion"]`

#### TC-MOD-008: NaturalLanguageFilenameSuggestions validates correctly
- **Valid**: `["My File Name", "Another File", "Third Suggestion"]`

#### TC-MOD-009: Exactly 3 suggestions required
- **Input**: List of 2 suggestions
- **Expected**: `ValidationError`

#### TC-MOD-010: Suggestion > 128 chars rejected
- **Input**: One suggestion with 129 characters
- **Expected**: `ValidationError`

#### TC-MOD-011: Empty suggestion rejected
- **Input**: `["valid_name", "", "another"]`
- **Expected**: `ValidationError`

#### TC-MOD-012: generate_json_schema_from_model produces valid OpenAI format
- **Steps**: Generate schema for `SnakeCaseFilenameSuggestions`
- **Expected**: Dict has `type: "json_schema"`, `json_schema.name: "suggestions"`, `json_schema.schema` contains `properties`

---

## 5. Prompt System Tests (test_prompts.py)

### 5.1 Existing Coverage Gaps

No test file exists for `prompts.py`. All tests below are new.

#### TC-PR-001: get_system_prompt returns default when config has empty string
- **Input**: `config = {"system_prompt": ""}`
- **Expected**: Returns `DEFAULT_SYSTEM_PROMPT`

#### TC-PR-002: get_system_prompt returns custom when config has value
- **Input**: `config = {"system_prompt": "Custom prompt"}`
- **Expected**: Returns `"Custom prompt"`

#### TC-PR-003: get_user_prompt interpolates naming_convention and content
- **Steps**: Call with `naming_convention="kebab-case"`, `content="test content"`
- **Expected**: Result contains `"test content"` (from `{content}` template var)

#### TC-PR-004: get_image_prompt interpolates naming_convention
- **Steps**: Call with `naming_convention="PascalCase"`
- **Expected**: Result contains `"PascalCase"`

#### TC-PR-005: Custom user_prompt template is used when configured
- **Input**: `config = {"user_prompt": "Custom: {content}"}`
- **Expected**: Returns `"Custom: <the content>"`

#### TC-PR-006: Word count limits injected into prompts (OnomaTool-5lu)
- **Validates**: Bug fix — prompts currently hardcode "five and ten words"
- **Input**: `config = {"min_filename_words": 3, "max_filename_words": 8}`
- **Expected**: Prompt text contains "3" and "8" (not "five" and "ten")

---

## 6. LLM Integration Tests (test_llm_integration.py)

### 6.1 Existing Coverage Gaps

No test file exists for `llm_integration.py`. All tests below are new.

### 6.2 Mock Provider

#### TC-LLM-001: Mock provider returns 3 suggestions for each naming convention
- **Steps**: For each of the 6 conventions, call `get_suggestions("content", config=mock_config)`
- **Expected**: Each returns a list of exactly 3 strings matching the convention

#### TC-LLM-002: Mock provider default is snake_case
- **Input**: `naming_convention = "UNKNOWN"` (falls back to snake_case in mock)
- **Expected**: Returns `["mock_file_one", "mock_file_two", "mock_file_three"]`

### 6.3 Content Handling

#### TC-LLM-003: Content truncated at MAX_CONTENT_CHARS
- **Input**: Content string of 200,000 characters
- **Expected**: Only first 120,000 chars sent to provider (verify via mock)

#### TC-LLM-004: SVG file raises RuntimeError
- **Input**: `file_path="test.svg"` (not converted to PNG)
- **Expected**: `RuntimeError("Raw SVG files must not be sent to the LLM")`

#### TC-LLM-005: Image file detection works for all supported extensions
- **Steps**: Test `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.svg`
- **Expected**: `is_image_file()` returns `True` for all

#### TC-LLM-006: Non-image extensions return False
- **Steps**: Test `.txt`, `.pdf`, `.docx`, `.py`
- **Expected**: `is_image_file()` returns `False`

### 6.4 SSL Handling (SPEC §6.4)

#### TC-LLM-007: SSL disabled for http:// URLs
- **Steps**: Set `openai_base_url = "http://localhost:1234/v1"`, mock OpenAI client
- **Expected**: `httpx.Client(verify=False)` used

#### TC-LLM-008: SSL disabled for https://10.x URLs
- **Input**: `openai_base_url = "https://10.0.0.1/v1"`
- **Expected**: `verify=False`

#### TC-LLM-009: SSL disabled for https://127.x URLs
- **Input**: `openai_base_url = "https://127.0.0.1/v1"`
- **Expected**: `verify=False`

#### TC-LLM-010: SSL enabled for public URLs
- **Input**: `openai_base_url = "https://api.openai.com/v1"`
- **Expected**: `verify=True`

### 6.5 Token Counting (SPEC §6.7)

#### TC-LLM-011: count_text_tokens returns positive int for non-empty text
- **Input**: `"Hello world"`
- **Expected**: Returns int > 0

#### TC-LLM-012: count_text_tokens returns 0 for empty string
- **Input**: `""`
- **Expected**: Returns 0

#### TC-LLM-013: count_tokens_for_messages handles multimodal content
- **Input**: Message with text + image_url content
- **Expected**: Returns int > 0, does not crash on image items

#### TC-LLM-014: Token counting falls back to cl100k_base for unknown model
- **Input**: `model="nonexistent-model-xyz"`
- **Expected**: Returns a count (uses fallback encoding)

### 6.6 Pydantic Model Selection

#### TC-LLM-015: get_pydantic_model_and_schema returns correct model per convention
- **Steps**: For each convention, call `get_pydantic_model_and_schema()`
- **Expected**: Model class matches `NAMING_CONVENTION_MODELS[convention]`

#### TC-LLM-016: Unknown convention falls back to snake_case
- **Input**: `naming_convention = "INVALID"`
- **Expected**: Returns `SnakeCaseFilenameSuggestions` model

### 6.7 Azure OpenAI (SPEC §6.1)

#### TC-LLM-017: Azure requires endpoint, api_key, and deployment
- **Steps**: Set `use_azure_openai = True` but leave endpoint empty
- **Expected**: `RuntimeError` mentioning missing endpoint

#### TC-LLM-018: Azure deployment overrides model name
- **Steps**: Set `azure_openai_deployment = "my-deployment"`
- **Expected**: Model used in API call is `"my-deployment"`

### 6.8 Google Provider (OnomaTool-vlc)

#### TC-LLM-019: Google provider uses correct import path
- **Validates**: Bug `OnomaTool-vlc`
- **Expected**: Import matches `google-genai` package (not old `google.generativeai`)

#### TC-LLM-020: Google provider extracts suggestions via regex
- **Steps**: Mock Gemini response with 3 quoted strings
- **Expected**: Returns list of 3 suggestions

---

## 7. File Processing Tests

### 7.1 Non-Regular File Filtering (OnomaTool-fu7) — test_file_filtering.py

#### TC-FF-001: Symlinks are skipped with warning
- **Steps**: Create symlink in work_dir, process file list
- **Expected**: Symlink skipped, warning logged

#### TC-FF-002: Directories are skipped
- **Steps**: Include a directory path in file list
- **Expected**: Directory skipped

#### TC-FF-003: Broken symlinks are skipped
- **Steps**: Create symlink pointing to nonexistent target
- **Expected**: Skipped with warning

#### TC-FF-004: Regular files are processed
- **Steps**: Include a regular `.txt` file
- **Expected**: File processed normally

#### TC-FF-005: FIFOs are skipped (Linux only)
- **Steps**: Create a named pipe with `os.mkfifo()`
- **Expected**: Skipped with warning

### 7.2 MarkitdownProcessor — test_markitdown_processor.py

#### TC-MP-001: PDF returns dict with markdown, images, and tempdir
- **Steps**: Process `brochure_1.pdf` from example_files (read-only reference)
- **Expected**: Result is dict with keys `markdown`, `images`, `tempdir`; images list non-empty

#### TC-MP-002: DOCX returns string content
- **Steps**: Process `resume_1.docx`
- **Expected**: Result is a non-empty string

#### TC-MP-003: Unknown extension processed via MarkItDown
- **Steps**: Process a `.xyz` file
- **Expected**: MarkItDown attempted (may fail gracefully)

#### TC-MP-004: Debug mode creates persistent temp directories
- **Steps**: Process PDF with `debug=True`
- **Expected**: Tempdir not auto-cleaned, path printed

#### TC-MP-005: Non-debug mode cleans up temp directories
- **Steps**: Process PDF with `debug=False`, check temp path after
- **Expected**: Tempdir cleaned up

### 7.3 Image Utils — test_image_utils.py

#### TC-IU-001: SVG to PNG conversion produces valid PNG
- **Steps**: Convert a simple SVG file
- **Expected**: Output file exists, is valid PNG, max dimension 1024px

#### TC-IU-002: Missing cairosvg raises RuntimeError
- **Steps**: Mock `import cairosvg` to raise `ImportError`
- **Expected**: `RuntimeError` with install instructions

#### TC-IU-003: Invalid SVG raises error
- **Steps**: Pass a non-SVG file (e.g., text file renamed to .svg)
- **Expected**: Error raised or handled gracefully

#### TC-IU-004: Aspect ratio preserved in conversion
- **Steps**: Convert a wide SVG (2000x500)
- **Expected**: Output PNG is 1024x256 (or similar ratio)

---

## 8. Filename Sanitization Tests (Phase 2 — OnomaTool-mvm) — test_sanitization.py

#### TC-SAN-001: Windows-illegal characters stripped
- **Input**: `'my<file>name:with"bad|chars?here*'`
- **Expected**: `'myfilenamewithbadcharshere'` or underscore-replaced variant

#### TC-SAN-002: Windows reserved names rejected
- **Input**: `"CON"`, `"PRN"`, `"AUX"`, `"NUL"`, `"COM1"`, `"LPT1"`
- **Expected**: Each replaced or suffixed (e.g., `"CON_file"`)

#### TC-SAN-003: Filename length enforced at 255 bytes
- **Input**: 300-character filename
- **Expected**: Truncated to ≤ 255 bytes

#### TC-SAN-004: Leading/trailing dots stripped
- **Input**: `"...hidden_file..."`
- **Expected**: `"hidden_file"`

#### TC-SAN-005: Leading/trailing spaces stripped
- **Input**: `"  spaced name  "`
- **Expected**: `"spaced name"`

#### TC-SAN-006: Clean filename passes through unchanged
- **Input**: `"perfectly_valid_filename"`
- **Expected**: Same string returned

#### TC-SAN-007: Case-insensitive reserved name check
- **Input**: `"con"`, `"Con"`, `"CON"`
- **Expected**: All three caught

---

## 9. Architecture Tests — ProcessingResult (Phase 1 — OnomaTool-2fa)

File: `test_processing_result.py`

#### TC-PR-001: ProcessingResult default fields
- **Steps**: Create `ProcessingResult()`
- **Expected**: `markdown=""`, `images=[]`, `tempdir=None`, `source_path=""`, `file_type=""`

#### TC-PR-002: ProcessingResult with all fields populated
- **Steps**: Create with markdown, images list, tempdir, source_path, file_type
- **Expected**: All fields accessible and correct

#### TC-PR-003: TextProcessor returns ProcessingResult (after refactor)
- **Steps**: Process a `.txt` file
- **Expected**: Returns `ProcessingResult` with `markdown` set, `images` empty

#### TC-PR-004: MarkitdownProcessor returns ProcessingResult for PDF
- **Steps**: Process a `.pdf` file
- **Expected**: Returns `ProcessingResult` with `markdown` set, `images` non-empty, `tempdir` set

#### TC-PR-005: MarkitdownProcessor returns ProcessingResult for DOCX
- **Steps**: Process a `.docx` file
- **Expected**: Returns `ProcessingResult` with `markdown` set, `images` empty

---

## 10. Architecture Tests — LLMProvider Protocol (Phase 1 — OnomaTool-mnj)

File: `test_llm_providers.py`

#### TC-LP-001: MockProvider conforms to LLMProvider protocol
- **Steps**: `isinstance(MockProvider(), LLMProvider)` or structural check
- **Expected**: True

#### TC-LP-002: OpenAIProvider conforms to LLMProvider protocol
- **Expected**: Has `get_suggestions()` and `supports_images()` methods

#### TC-LP-003: AzureOpenAIProvider conforms to LLMProvider protocol
- **Expected**: Same interface as OpenAIProvider

#### TC-LP-004: GoogleProvider conforms to LLMProvider protocol
- **Expected**: Has required methods

#### TC-LP-005: MockProvider.supports_images() returns False
- **Expected**: `False` (mock doesn't need image support)

#### TC-LP-006: OpenAIProvider.supports_images() returns True
- **Expected**: `True`

#### TC-LP-007: GoogleProvider.supports_images() returns False (until Phase 3)
- **Expected**: `False` (no Gemini vision yet)

#### TC-LP-008: Provider swap does not break orchestrator
- **Steps**: Create orchestrator with MockProvider, swap to another, process file
- **Expected**: Both work without errors

#### TC-LP-009: Unsupported provider string raises error
- **Input**: `default_provider = "nonexistent"`
- **Expected**: `RuntimeError("Unsupported provider")`

---

## 11. Architecture Tests — RenameOrchestrator (Phase 1 — OnomaTool-09s)

File: `test_rename_orchestrator.py`

#### TC-RO-001: process_file returns ProcessingResult for text file
- **Steps**: Orchestrator processes a `.txt` file
- **Expected**: Returns `ProcessingResult` with content

#### TC-RO-002: process_file returns None for unsupported file
- **Steps**: Process a file that causes processor failure
- **Expected**: Returns `None`, no crash

#### TC-RO-003: get_suggestions returns list of 3 strings
- **Steps**: Call with a valid `ProcessingResult`
- **Expected**: Returns `list[str]` with 3 items

#### TC-RO-004: execute_rename moves file in non-dry-run
- **Steps**: Call with `dry_run=False`
- **Expected**: File moved, `RenameRecord.success = True`

#### TC-RO-005: execute_rename does not move file in dry-run
- **Steps**: Call with `dry_run=True`
- **Expected**: File unchanged, `RenameRecord` still returned for preview

#### TC-RO-006: execute_rename preserves original extension
- **Steps**: File is `test.md`, suggestion is `new_name.txt`
- **Expected**: Renamed to `new_name.md`

#### TC-RO-007: execute_rename resolves conflicts
- **Steps**: Target name already exists in directory
- **Expected**: Numeric suffix appended

#### TC-RO-008: Orchestrator handles processor failure gracefully
- **Steps**: Mock processor to raise exception
- **Expected**: File skipped, no crash, error logged

---

## 12. Architecture Tests — SuggestionStrategy (Phase 1 — OnomaTool-mq4)

File: `test_suggestion_strategies.py`

#### TC-SS-001: TextOnlySuggestionStrategy makes 1 LLM call
- **Steps**: Process text file with mock provider
- **Expected**: Provider `get_suggestions` called exactly once

#### TC-SS-002: ImageOnlySuggestionStrategy makes 1 LLM call
- **Steps**: Process image file with mock provider
- **Expected**: Provider called once with image data

#### TC-SS-003: MultiPassSuggestionStrategy makes N+2 calls for N-page PDF
- **Steps**: ProcessingResult with 3 images
- **Expected**: Provider called 5 times (3 images + 1 markdown + 1 synthesis)

#### TC-SS-004: Strategy auto-selected by file type
- **Steps**: Text file -> TextOnly, Image -> ImageOnly, PDF -> MultiPass
- **Expected**: Correct strategy for each

#### TC-SS-005: Provider without image support degrades to TextOnly
- **Steps**: PDF file but provider.supports_images() = False
- **Expected**: TextOnlySuggestionStrategy used

#### TC-SS-006: MultiPass fallback priority
- **Steps**: Final suggestions = None, markdown suggestions = None
- **Expected**: Falls back to image suggestions

---

## 13. Undo System Tests (Phase 2 — OnomaTool-cq5, OnomaTool-61h)

File: `test_undo_system.py`

#### TC-UNDO-001: Rename session recorded in SQLite
- **Steps**: Rename a file via orchestrator
- **Expected**: `sessions` table has 1 row, `renames` table has 1 row

#### TC-UNDO-002: --undo reverses most recent session
- **Steps**: Rename file A->B, then run `--undo`
- **Expected**: B renamed back to A

#### TC-UNDO-003: --undo with session ID reverses specific session
- **Steps**: Create 2 sessions, undo session 1
- **Expected**: Only session 1 renames reversed

#### TC-UNDO-004: Undo refuses if file modified since rename
- **Steps**: Rename A->B, modify B's content, attempt undo
- **Expected**: Refusal with warning message

#### TC-UNDO-005: Undo warns if file missing
- **Steps**: Rename A->B, delete B, attempt undo
- **Expected**: Warning logged, continues gracefully

#### TC-UNDO-006: --history lists sessions
- **Steps**: Create 3 sessions
- **Expected**: Output contains 3 session entries with ID, timestamp, count

#### TC-UNDO-007: Empty database doesn't crash
- **Steps**: Run `--undo` with no sessions
- **Expected**: "No sessions found" message

#### TC-UNDO-008: Auto-prune removes sessions older than 90 days
- **Steps**: Insert session with timestamp 91 days ago, run CLI
- **Expected**: Old session deleted, recent sessions preserved

#### TC-UNDO-009: history_retention_days config respected
- **Steps**: Set `history_retention_days = 7`, insert 8-day-old session
- **Expected**: Session pruned

#### TC-UNDO-010: Failed files recorded with error status
- **Steps**: Process batch where 1 file fails
- **Expected**: Failure recorded in renames table with error field

---

## 14. Retry and Rate Limiting Tests (Phase 2 — OnomaTool-bm3, OnomaTool-yy7)

File: `test_retry_rate_limit.py`

#### TC-RET-001: max_retries=0 fails immediately
- **Steps**: Mock provider raises transient error, `max_retries=0`
- **Expected**: RuntimeError raised after 1 attempt

#### TC-RET-002: Transient 5xx retried up to max_retries
- **Steps**: Mock returns 500 twice then succeeds, `max_retries=3`
- **Expected**: 3 calls total, success on third

#### TC-RET-003: Permanent 4xx not retried
- **Steps**: Mock returns 401, `max_retries=3`
- **Expected**: Fails after 1 attempt

#### TC-RET-004: Exponential backoff timing
- **Steps**: `retry_delay=1.0`, mock fails 3 times
- **Expected**: Delays are ~1s, ~2s, ~4s (verify with time.monotonic)

#### TC-RET-005: Retry attempts logged at WARNING
- **Steps**: Enable retries, mock transient failure
- **Expected**: WARNING log entries for each retry

#### TC-RL-001: rate_limit_delay inserts pause between calls
- **Steps**: `rate_limit_delay=0.5`, process 3 files
- **Expected**: Total time >= 1.0s (2 gaps between 3 calls)

#### TC-RL-002: rate_limit_delay=0 has no effect
- **Steps**: `rate_limit_delay=0.0`, process 3 files
- **Expected**: No artificial delay

#### TC-RL-003: Rate limiting applies to all providers
- **Steps**: Test with mock, verify delay mechanism exists
- **Expected**: Delay logic is provider-agnostic

---

## 15. Progress Bar and Batch Error Tests (Phase 2 — OnomaTool-69a, OnomaTool-5rd)

File: `test_progress_batch.py`

#### TC-PB-001: Progress bar displays on TTY
- **Steps**: Mock `sys.stdout.isatty()` to return True, process batch
- **Expected**: Progress output contains file count

#### TC-PB-002: Progress bar suppressed on pipe
- **Steps**: Mock `isatty()` to return False
- **Expected**: No progress bar characters in output

#### TC-PB-003: Summary shows correct counts
- **Steps**: Process 5 files (3 succeed, 1 fails, 1 skipped)
- **Expected**: Summary: "3 renamed, 1 failed, 1 skipped"

#### TC-BE-001: Failed file doesn't abort batch
- **Steps**: Mock processor to fail on file 2 of 5
- **Expected**: Files 3-5 still processed

#### TC-BE-002: Failure summary printed at end
- **Steps**: 2 files fail in batch
- **Expected**: End-of-run output lists both failures

#### TC-BE-003: Failures recorded in history DB
- **Steps**: Process batch with failures
- **Expected**: Failed renames in DB with error status

---

## 16. CLI Flags and Filtering Tests (Phase 2 — OnomaTool-vcq, OnomaTool-87i, OnomaTool-e6t)

File: `test_cli_flags.py`

#### TC-CLI-001: --undo flag parsed
- **Steps**: `main(["--undo"])` (with stub implementation)
- **Expected**: Does not raise unrecognized argument error

#### TC-CLI-002: --history flag parsed
- **Steps**: `main(["--history"])`
- **Expected**: Parsed without error

#### TC-CLI-003: --check flag parsed
- **Steps**: `main(["--check"])`
- **Expected**: Parsed without error

#### TC-CLI-004: --exclude flag accepts glob
- **Steps**: `main(["*.txt", "--exclude", "*.log"])`
- **Expected**: Parsed, exclude pattern stored

#### TC-CLI-005: --sort flag accepts valid choices
- **Steps**: `main(["*.txt", "--sort", "name"])` for each of name/size/type/modified
- **Expected**: All accepted

#### TC-CLI-006: --sort rejects invalid choice
- **Steps**: `main(["*.txt", "--sort", "invalid"])`
- **Expected**: argparse error

#### TC-EX-001: --exclude filters matching files
- **Steps**: Files `a.txt`, `b.log`, `c.txt`; exclude `*.log`
- **Expected**: Only `a.txt` and `c.txt` processed

#### TC-EX-002: Hidden files skipped by default
- **Steps**: Files `.hidden`, `visible.txt`; no explicit include
- **Expected**: Only `visible.txt` processed

#### TC-EX-003: Zero-byte files skipped by default
- **Steps**: Create empty file alongside non-empty file
- **Expected**: Empty file skipped

#### TC-SORT-001: --sort name processes alphabetically
- **Steps**: Files `c.txt`, `a.txt`, `b.txt`
- **Expected**: Processed in order a, b, c

#### TC-SORT-002: --sort size processes smallest first
- **Steps**: Files of 100B, 10B, 50B
- **Expected**: Processed in order 10B, 50B, 100B

#### TC-SORT-003: --sort modified processes oldest first
- **Steps**: Files with different mtimes
- **Expected**: Oldest processed first

---

## 17. Dry-Run Fidelity and Health Check Tests (Phase 2 — OnomaTool-dhl, OnomaTool-25j)

File: `test_dryrun_fidelity.py`

#### TC-DRF-001: Unchanged names proceed with single confirmation
- **Steps**: Dry-run, no dir changes, confirm
- **Expected**: Single prompt, renames applied

#### TC-DRF-002: Changed names show diff and re-confirm
- **Steps**: Dry-run preview, add conflicting file before confirm
- **Expected**: Diff displayed, second confirmation prompted

#### TC-DRF-003: Second confirmation rejected aborts
- **Steps**: Names changed, user answers "N" to second prompt
- **Expected**: No renames performed

File: `test_health_check.py`

#### TC-HC-001: --check reports Python version
- **Expected**: Output contains `Python` and a version number

#### TC-HC-002: --check reports LibreOffice status
- **Expected**: Output contains `LibreOffice` and OK or MISSING

#### TC-HC-003: --check reports ImageMagick status
- **Expected**: Output contains `ImageMagick` and OK or MISSING

#### TC-HC-004: --check reports Cairo status
- **Expected**: Output contains `Cairo` and OK or MISSING

#### TC-HC-005: Missing dependency shows install instructions at runtime
- **Steps**: Mock `soffice` as absent, process a PPTX
- **Expected**: Error message names missing tool and how to install

---

## 18. Logging Migration Tests (Phase 1 — OnomaTool-ojn)

File: `test_logging.py`

#### TC-LOG-001: Default log level is WARNING
- **Steps**: Run with no verbosity flags
- **Expected**: Only WARNING+ messages in output

#### TC-LOG-002: --verbose sets INFO level
- **Steps**: Run with `-v`
- **Expected**: INFO messages appear (provider, model)

#### TC-LOG-003: --very-verbose sets DEBUG level
- **Steps**: Run with `-vv`
- **Expected**: DEBUG messages appear (schemas, token counts)

#### TC-LOG-004: No print() calls remain in source
- **Steps**: Grep `src/onomatool/` for bare `print(` calls
- **Expected**: Zero matches (all replaced with logging)

#### TC-LOG-005: API keys never logged
- **Steps**: Set verbose, run with API key configured
- **Expected**: Key value does not appear in any log output

#### TC-LOG-006: Base64 image data redacted in logs
- **Steps**: Process image with `-vv`
- **Expected**: `[[base64_image]]` appears, no raw base64

---

## 19. Phase 3 Feature Tests

### 19.1 Google Gemini Image Support (OnomaTool-8gv) — test_gemini_vision.py

#### TC-GV-001: Image files processed with Google provider
- **Steps**: Configure Google provider, process .jpg
- **Expected**: Gemini vision API called with image data

#### TC-GV-002: Non-image files use text-only strategy
- **Steps**: Configure Google provider, process .txt
- **Expected**: Text-only strategy used, no vision call

#### TC-GV-003: GoogleProvider.supports_images() returns True after update
- **Expected**: `True` (feature parity achieved)

### 19.2 Processor Plugin System (OnomaTool-xi5) — test_plugin_system.py

#### TC-PL-001: Custom plugin discovered via entry_points
- **Steps**: Register mock plugin via entry_points, init FileDispatcher
- **Expected**: Plugin loaded and available

#### TC-PL-002: Plugin can_process() respected
- **Steps**: Plugin returns False for `.txt`
- **Expected**: Built-in TextProcessor used instead

#### TC-PL-003: Built-in processor takes precedence
- **Steps**: Plugin also handles `.md` extension
- **Expected**: TextProcessor used, not plugin

#### TC-PL-004: Plugin returning ProcessingResult works end-to-end
- **Steps**: Plugin processes custom extension, returns valid result
- **Expected**: LLM receives content, rename succeeds

### 19.3 Format Override (OnomaTool-m2p) — test_format_override.py

#### TC-FO-001: --format pdf forces MarkitdownProcessor for .txt file
- **Steps**: `main(["test.txt", "--format", "pdf", "--config", MOCK_CONFIG])`
- **Expected**: MarkitdownProcessor used instead of TextProcessor

#### TC-FO-002: Unknown format rejected
- **Steps**: `main(["test.txt", "--format", "unknown"])`
- **Expected**: argparse error

### 19.4 Debug Directory (OnomaTool-c08) — test_debug_directory.py

#### TC-DD-001: Debug artifacts go to ~/.onoma_debug/
- **Steps**: Process with `--debug`, check artifact location
- **Expected**: Files in `~/.onoma_debug/<timestamp>/`, not `/tmp/`

#### TC-DD-002: Session directories auto-cleaned after 7 days
- **Steps**: Create debug dir with 8-day-old timestamp, trigger cleanup
- **Expected**: Old directory removed

#### TC-DD-003: No type('TempDir', ...) hack objects remain
- **Steps**: Grep source for `type('TempDir'` or `type("TempDir"`
- **Expected**: Zero matches

---

## 20. Security and Safety Tests

File: `test_security.py`

#### TC-SEC-001: Content truncated before LLM call
- **Steps**: 200K char content with mock provider
- **Expected**: Provider receives ≤ 120,000 chars

#### TC-SEC-002: Max tokens enforced in LLM request
- **Steps**: Inspect mock call kwargs
- **Expected**: `max_tokens=100`

#### TC-SEC-003: SVG guard prevents raw SVG to LLM
- **Steps**: Call `get_suggestions()` with `file_path="test.svg"`
- **Expected**: `RuntimeError` raised

#### TC-SEC-004: shutil.move used for rename (not os.rename)
- **Steps**: Inspect renamer.py source or mock
- **Expected**: `shutil.move` called

#### TC-SEC-005: Original file extension always preserved
- **Steps**: Rename `test.md` with suggestion `new_name.txt`
- **Expected**: Result is `new_name.md`

#### TC-SEC-006: Conflict resolution prevents overwrites
- **Steps**: Target name exists in directory
- **Expected**: Numeric suffix appended, no overwrite

#### TC-SEC-007: No API keys in verbose output
- **Steps**: Run with `-vv`, config with `openai_api_key = "sk-secret123"`
- **Expected**: `"sk-secret123"` not in stdout/stderr

---

## 21. Performance Benchmarks

File: `test_performance.py` (marked with `@pytest.mark.slow`)

#### TC-PERF-001: Conflict resolution with 1000 existing files < 100ms
- **Steps**: `resolve_conflict("f.txt", ["f.txt", "f_2.txt", ..., "f_1000.txt"])`
- **Expected**: Completes in < 100ms

#### TC-PERF-002: Token counting for large message array < 500ms
- **Steps**: 50-message array, each 1000 tokens
- **Expected**: `count_tokens_for_messages()` < 500ms

#### TC-PERF-003: File collector with 10,000 files < 2s
- **Steps**: Create 10K files in tmp, glob `*.txt`
- **Expected**: Returns all in < 2s

#### TC-PERF-004: Config loading < 50ms
- **Steps**: Load config from file 100 times
- **Expected**: Average < 50ms per load

---

## 22. Test Execution Matrix

### Running all test categories

```bash
uv run pytest                                    # All tests
uv run pytest -m "not slow"                      # Skip performance
uv run pytest tests/test_usage_enduser.py        # End-to-end only
uv run pytest --cov=onomatool --cov-report=html  # Coverage report
```

### Pytest markers to add in `pyproject.toml`

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m not slow')",
    "integration: marks integration tests requiring external deps",
]
```

### Test file to module mapping

| Test File | Module Under Test | Category |
|-----------|-------------------|----------|
| `test_config.py` | `config.py` | Unit |
| `test_config_model.py` | `config.py` (Pydantic) | Unit |
| `test_config_versioning.py` | `config.py` | Unit |
| `test_models.py` | `models.py` | Unit |
| `test_prompts.py` | `prompts.py` | Unit |
| `test_llm_integration.py` | `llm_integration.py` | Unit + Integration |
| `test_llm_providers.py` | LLMProvider classes | Unit |
| `test_conflict_resolver.py` | `conflict_resolver.py` | Unit |
| `test_renamer.py` | `renamer.py` | Unit |
| `test_file_collector.py` | `file_collector.py` | Unit |
| `test_file_dispatcher.py` | `file_dispatcher.py` | Unit |
| `test_file_filtering.py` | Pre-processing filters | Unit |
| `test_text_processor.py` | `text_processor.py` | Unit |
| `test_utf8_encoding.py` | `markitdown_processor.py` | Unit |
| `test_markitdown_processor.py` | `markitdown_processor.py` | Integration |
| `test_image_utils.py` | `image_utils.py` | Unit |
| `test_processing_result.py` | `ProcessingResult` | Unit |
| `test_rename_orchestrator.py` | `RenameOrchestrator` | Integration |
| `test_suggestion_strategies.py` | Strategy classes | Unit |
| `test_sanitization.py` | Filename sanitizer | Unit |
| `test_undo_system.py` | SQLite history | Integration |
| `test_retry_rate_limit.py` | Retry/rate logic | Unit |
| `test_progress_batch.py` | Progress + batch errors | Integration |
| `test_cli_flags.py` | CLI argument parsing | Unit |
| `test_dryrun_fidelity.py` | Dry-run re-resolution | Integration |
| `test_health_check.py` | `--check` command | Integration |
| `test_logging.py` | Logging migration | Unit |
| `test_security.py` | Safety invariants | Unit |
| `test_performance.py` | Benchmarks | Performance |
| `test_usage_enduser.py` | Full CLI pipeline | End-to-end |
| `test_gemini_vision.py` | Google vision | Integration |
| `test_plugin_system.py` | Plugin discovery | Integration |
| `test_format_override.py` | `--format` flag | Integration |
| `test_debug_directory.py` | Debug artifacts | Integration |

---

## 23. Acceptance Criteria Summary

All phases are considered complete when:

1. **Coverage**: ≥ 80% line coverage across `src/onomatool/`
2. **Zero failures**: `uv run pytest` exits 0 (excluding `@pytest.mark.slow` if not on CI)
3. **All naming conventions**: 6 conventions tested with valid and invalid inputs
4. **All providers**: Mock, OpenAI, Azure, Google tested (mock for unit, others mocked for integration)
5. **All file types**: `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.svg`, `.jpg`, `.png` have at least one test path
6. **Destructive isolation**: Every test that renames/moves files uses `work_dir` fixture
7. **Read-only enforcement**: `example_files/` remains `r--r--r--` after test suite completes
8. **No regressions**: Existing 37 tests continue passing after each phase
