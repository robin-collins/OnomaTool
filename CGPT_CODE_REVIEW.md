# Deep Code Review: `src/onomatool`

## Scope

This review covers all Python source files under `src/onomatool`:

- `__init__.py`
- `cli.py`
- `config.py`
- `conflict_resolver.py`
- `file_collector.py`
- `file_dispatcher.py`
- `history.py`
- `llm_integration.py`
- `models.py`
- `processors/__init__.py`
- `processors/markitdown_processor.py`
- `processors/text_processor.py`
- `prompts.py`
- `rename_orchestrator.py`
- `renamer.py`
- `sanitizer.py`
- `suggestion_strategy.py`
- `utils/image_utils.py`

## Review Method

The analysis focused on the requested dimensions:

1. **Code documentation & commenting**
2. **Security analysis**
3. **Error detection & code quality**
4. **Omissions & missed opportunities**
5. **Enhancement recommendations**

Severity levels used in this report:

- **Critical** – likely data loss, security compromise, or production outage
- **High** – serious correctness/security problem with realistic failure modes
- **Medium** – maintainability, reliability, or defense-in-depth issue
- **Low** – style, documentation, clarity, or non-blocking quality issue

---

## Executive Summary

The codebase is generally readable, modular, and supported by a comparatively strong automated test suite. The strongest areas are configuration validation (`config.py`), model validation (`models.py`), and a reasonably clean separation between orchestration, dispatching, processing, and LLM integration.

The most important issues found are:

1. **Unsafe transport behavior for custom OpenAI endpoints**: TLS verification is disabled for `http://`, `https://localhost`, and RFC1918-style hosts, which weakens transport security and can normalize insecure deployments.
2. **Rename/history race leading to incorrect audit trail and undo failures**: the orchestrator pre-computes the destination name, while `rename_file()` recomputes conflict resolution internally, so the path recorded in history can diverge from the actual path renamed.
3. **Undo logic replays error entries**: failed operations are stored in history and then processed by undo, creating noisy or misleading results instead of skipping non-successful rows.
4. **Error handling is too silent in several places**: broad `except Exception` blocks often return `None` or fall back to defaults without enough logging to diagnose failures.
5. **The Gemini integration is parser-fragile**: it extracts quoted strings from free-form model output instead of enforcing a structured response contract.

---

## High-Priority Findings

### 1. TLS verification is disabled for some configured OpenAI endpoints

- **Severity:** High
- **Category:** Security / transport security
- **Files:** `src/onomatool/llm_integration.py`
- **References:** lines 121-129

#### Why this matters

`OpenAIProvider._create_client()` disables certificate verification whenever `openai_base_url` starts with `http://`, `https://10.`, `https://127.`, or `https://localhost`.

That means a deployment can silently run without TLS verification simply because the base URL looks “local”. This is risky for:

- developer laptops on untrusted Wi-Fi,
- containerized environments where `localhost` may front a reverse proxy,
- internal enterprise networks where MITM is still possible,
- accidental reuse of insecure settings in production-like environments.

#### Problematic code

```python
verify = not base_url.startswith(
    ("http://", "https://10.", "https://127.", "https://localhost")
)
return OpenAI(
    base_url=base_url,
    api_key=api_key,
    http_client=httpx.Client(verify=verify),
)
```

#### Impact

- Weakens confidentiality/integrity of prompts and model outputs.
- Makes API keys more exposed on misconfigured internal networks.
- Creates a surprising security policy based purely on string prefixes.

#### Recommendation

- Default to `verify=True` always.
- If insecure local development is needed, expose an explicit config flag such as `allow_insecure_transport=false`.
- Log a prominent warning when insecure transport is enabled.
- Consider rejecting plain `http://` by default unless the user opts in.

---

### 2. Rename conflict resolution is computed twice, which can corrupt history and break undo

- **Severity:** High
- **Category:** Correctness / data integrity / concurrency
- **Files:** `src/onomatool/rename_orchestrator.py`, `src/onomatool/renamer.py`
- **References:** `rename_orchestrator.py` lines 260-280 and 303-319; `renamer.py` lines 16-29

#### Why this matters

The orchestrator computes `final_name` and `new_path` before renaming, but it then calls `rename_file(file_path, new_name)`. Inside `rename_file()`, the directory is re-scanned and conflicts are resolved again.

If anything changes between the orchestrator’s calculation and the actual move—another thread, another process, or even another rename in the same directory—the actual destination may differ from the one stored in history.

#### Problematic flow

```python
# rename_orchestrator.py
existing_files = os.listdir(directory)
final_name = resolve_conflict(new_name_with_ext, existing_files)
new_path = os.path.join(directory, final_name)
rename_file(file_path, new_name)
history.record_rename(self._session_id, file_path, new_path)
```

```python
# renamer.py
existing_files = os.listdir(directory)
final_name = resolve_conflict(new_name_with_ext, existing_files)
final_path = os.path.join(directory, final_name)
shutil.move(original_path, final_path)
```

#### Impact

- Undo can target the wrong path.
- Rename history ceases to be a reliable audit trail.
- Bugs become timing-dependent and hard to reproduce.

#### Recommendation

- Resolve conflicts exactly once.
- Change `rename_file()` to accept the fully resolved target path, or return the actual destination path that was used.
- Record history using the path returned by the move operation, not a predicted path.
- Add a regression test covering simultaneous renames into the same directory.

---

### 3. Undo processes failed/error history rows instead of filtering to successful renames

- **Severity:** High
- **Category:** Reliability / undo semantics
- **Files:** `src/onomatool/history.py`, `src/onomatool/rename_orchestrator.py`
- **References:** `history.py` lines 123-168; `rename_orchestrator.py` lines 224-231

#### Why this matters

When processing fails, the orchestrator records a history row with `status="error"` and identical old/new paths. `undo_session()` does not filter these entries out; it attempts to undo every row in reverse order.

#### Problematic behavior

```python
# rename_orchestrator.py
self.history.record_rename(
    self._session_id, file_path, file_path, status="error"
)
```

```python
# history.py
renames = self.get_session_renames(session_id)
for rename in reversed(renames):
    original = rename["original_path"]
    new = rename["new_path"]
    ...
```

#### Impact

- Undo output contains misleading warnings/errors for operations that never succeeded.
- Mixed-success sessions are harder for users to interpret.
- Future session replay/reporting logic is built on ambiguous history semantics.

#### Recommendation

- Filter undo candidates to `status == "ok"` only.
- Consider storing a richer event model: `planned`, `renamed`, `failed`, `undone`.
- Update CLI output to report “N successful renames available to undo”.

---

## Medium-Priority Findings

### 4. Broad exception swallowing hides configuration failures and can cause unsafe fallback behavior

- **Severity:** Medium
- **Category:** Error handling / observability
- **Files:** `src/onomatool/config.py`
- **References:** lines 89-101

#### Why this matters

`get_config()` warns on `ValidationError`, but silently swallows all other exceptions and returns default configuration.

That means malformed TOML, permission issues, partial filesystem failures, or encoding errors can all make the application continue with defaults without telling the user what went wrong.

#### Problematic code

```python
        except ValidationError as e:
            logger.warning("Configuration validation error: %s", e)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()
```

#### Impact

- A user may think their custom provider/API key/model is loaded when it is not.
- Silent fallback can trigger calls to a different provider than intended.
- Diagnosing config issues becomes unnecessarily difficult.

#### Recommendation

- Log unexpected exceptions at warning or error level with the config path.
- Consider failing fast for syntax/permission errors unless an explicit “best effort” mode is requested.
- Return a structured error object to the CLI so it can explain the fallback.

---

### 5. Text and MarkItDown processors suppress too many failures and return `None`

- **Severity:** Medium
- **Category:** Reliability / maintainability / observability
- **Files:** `src/onomatool/processors/text_processor.py`, `src/onomatool/processors/markitdown_processor.py`
- **References:** `text_processor.py` lines 115-138; `markitdown_processor.py` lines 206-267 and 372-420

#### Why this matters

Both processors catch broad exceptions and often return `None`, which the orchestrator treats as a skip. In practice, operational failures and real defects can look identical to unsupported files.

#### Example

```python
except Exception:
    if utf8_file_path and utf8_file_path != file_path:
        self.cleanup_temp_encoding_file(file_path, utf8_file_path)
    return None
```

#### Impact

- Real failures are hidden as normal skip behavior.
- Production incidents are harder to diagnose.
- Metrics for “failed” vs “skipped” become unreliable.

#### Recommendation

- Distinguish between:
  - unsupported file type,
  - dependency missing,
  - parse failure,
  - transient IO error,
  - malformed input.
- Return structured failure metadata or raise typed exceptions.
- Log at least one actionable message before suppressing the exception.

---

### 6. Gemini response parsing is brittle and not schema-enforced

- **Severity:** Medium
- **Category:** Security / robustness / prompt-injection resilience
- **Files:** `src/onomatool/llm_integration.py`
- **References:** lines 290-308

#### Why this matters

The Gemini integration relies on a regex that extracts quoted strings from `response.text`. This is much weaker than the Pydantic/JSON-schema approach used for OpenAI.

#### Problematic code

```python
suggestions = re.findall(r'"([a-zA-Z0-9_\-\. ]{1,128})"', response.text)
...
return suggestions[:3]
```

#### Risks

- Any quoted text in the model output may be treated as a filename suggestion.
- Prompt injection in document/image content can more easily influence parsing.
- The naming-convention contract is not actually enforced here.

#### Recommendation

- Use Gemini structured response facilities if available.
- Validate the returned strings with the same Pydantic model used elsewhere.
- Reject outputs that do not match the selected naming convention.

---

### 7. Dynamic plugin loading is effectively arbitrary code execution and needs a clearer trust boundary

- **Severity:** Medium
- **Category:** Security / extensibility design
- **Files:** `src/onomatool/file_dispatcher.py`, `src/onomatool/processors/__init__.py`, `src/onomatool/config.py`
- **References:** `file_dispatcher.py` lines 54-60; `processors/__init__.py` lines 21-51 and 56-81; `config.py` line 58

#### Why this matters

`extra_processors` accepts module/class strings from config and imports them dynamically. Entry-point plugins are also instantiated automatically. This is legitimate for a trusted desktop tool, but it is a code-execution boundary that is not documented as such.

#### Impact

- A malicious or tampered config can import attacker-controlled code.
- The operational security model is unclear for shared environments.

#### Recommendation

- Document clearly that plugins/configured processors are trusted code.
- Consider an allowlist option or a “disable plugins” safe mode.
- Log which plugin module/class was loaded and from where.

---

### 8. Prompt templating can fail at runtime due to unvalidated custom placeholders

- **Severity:** Medium
- **Category:** Error handling / configuration robustness
- **Files:** `src/onomatool/prompts.py`
- **References:** lines 15-39 and 46 onward

#### Why this matters

Custom `user_prompt` and `image_prompt` strings are interpolated with `.format(...)` but there is no validation that the template contains only supported placeholders.

A user-provided prompt containing `{unknown_key}` will raise `KeyError` at runtime.

#### Recommendation

- Validate prompt templates when loading config.
- Either reject unsupported placeholders or use a safe formatter with clearer error messages.
- Add docs listing the supported variables explicitly.

---

### 9. Health check coverage is useful but does not validate runtime compatibility of external tools

- **Severity:** Medium
- **Category:** Operations / diagnostics
- **Files:** `src/onomatool/cli.py`
- **References:** lines 245-308

#### Why this matters

`run_health_check()` verifies package imports and binary presence, but it does not verify that tools such as `soffice`, `convert`, CairoSVG, or PDF/image processing paths actually work together for representative documents.

#### Recommendation

- Add an optional `--check --deep` mode that performs a small end-to-end smoke test on temporary sample files.
- Report whether PDF page rasterization and PPTX conversion are actually functional, not just installed.

---

## Low-Priority Findings

### 10. Documentation quality is uneven for the most complex modules

- **Severity:** Low
- **Category:** Documentation & commenting
- **Files:** `src/onomatool/llm_integration.py`, `src/onomatool/rename_orchestrator.py`, `src/onomatool/processors/markitdown_processor.py`, `src/onomatool/cli.py`

#### Observations

- Several simple modules are documented well (`history.py`, `models.py`, `suggestion_strategy.py`).
- The most complex files rely heavily on inline readability rather than explicit design documentation.
- `llm_integration.py` in particular contains multiple provider implementations, retry logic, transport configuration, token counting, logging redaction, and prompt assembly in one file with limited top-level explanation.

#### Missing documentation opportunities

- Expected invariants for rename planning vs execution
- Trust/security model for plugins and custom endpoints
- Why some processors silently return `None`
- How provider-specific parsing differs and why

#### Recommendation

- Add short module-level architecture notes to the largest files.
- Add docstrings for non-obvious helper functions and cross-module invariants.
- Document why broad fallbacks exist and when they are expected.

---

### 11. `MarkitdownProcessor` mixes too many responsibilities

- **Severity:** Low
- **Category:** Maintainability / design
- **Files:** `src/onomatool/processors/markitdown_processor.py`

#### Why this matters

This class currently handles:

- encoding detection,
- UTF-8 conversion,
- MarkItDown invocation,
- PDF rasterization,
- PPTX-to-PDF conversion,
- ImageMagick invocation,
- debug tempdir behavior,
- SVG special handling.

That makes the file harder to test, reason about, and evolve.

#### Recommendation

Split into focused collaborators, for example:

- `EncodingNormalizer`
- `DocumentConverter`
- `PdfImageExtractor`
- `PptxRasterizer`
- `DebugArtifactManager`

---

### 12. Some dead or questionable artifacts suggest incomplete cleanup

- **Severity:** Low
- **Category:** Code quality / housekeeping
- **Files:** `src/onomatool/llm_integration.py`, `src/onomatool/processors/markitdown_processor.py`

#### Observations

- `MAX_CONSECUTIVE_DIGITS` in `llm_integration.py` appears unused.
- Optional imports such as `requests`, `Presentation`, `Image`, and `ImageDraw` are not clearly used in the visible implementation paths.
- `if self.debug: pass` appears repeatedly, which adds noise without behavior.

#### Recommendation

- Remove unused constants/imports.
- Replace no-op debug branches with actual debug logging or delete them.
- Run a linter configured to flag dead code and unused symbols.

---

## Omissions & Missed Opportunities

### Input validation and defensive programming

- `cli.py` accepts `--undo SESSION_ID` and converts it with `int(session_arg)` without a user-friendly validation error path for non-numeric values.
- `file_collector.py` does not guard against extremely large glob expansions or duplicate matches from overlapping patterns.
- `rename_orchestrator.py` does not enforce an upper bound on file count processed in one batch, which could cause unexpectedly large LLM usage.

### Logging and observability

- Failures in config loading, encoding conversion, processor fallback, and external command execution are not surfaced consistently.
- There is no structured summary of failure reasons by category at the end of a run.
- There is no request correlation/session identifier attached to logs outside of history.

### Performance opportunities

- `resolve_conflict()` takes a `list[str]`; repeated membership checks are `O(n)`. For large directories, a `set[str]` would be cheaper.
- PDF and PPTX processing are synchronous and may become the bottleneck well before LLM latency.
- `os.listdir()` is called multiple times in rename flows; using cached directory state or atomic target creation could reduce churn.

### Test coverage gaps worth closing

The test suite is broad, but I still recommend adding focused tests for:

- insecure transport flag behavior for custom OpenAI endpoints,
- rename/history divergence when the destination changes between planning and move,
- undo skipping `status != "ok"` rows,
- prompt-template validation failures from user config,
- partial failures in external tool pipelines (`soffice` succeeds, `convert` fails, etc.) with explicit user-visible diagnostics.

---

## File-by-File Notes

### Stronger modules

- **`config.py`**: good use of Pydantic validation and version migration scaffolding.
- **`models.py`**: strong validation model and clear naming-convention-specific constraints.
- **`sanitizer.py`**: sensible cross-platform filename hygiene with extension-preserving truncation.
- **`suggestion_strategy.py`**: simple and understandable strategy abstraction.

### Modules needing the most attention

- **`llm_integration.py`**: too many responsibilities, provider asymmetry, transport/security concerns.
- **`rename_orchestrator.py`**: core correctness risks around rename planning/history coupling.
- **`processors/markitdown_processor.py`**: large, exception-heavy, and operationally complex.

---

## Recommended Remediation Plan

### Phase 1 — Correctness and security

1. Make transport verification opt-out rather than heuristic.
2. Refactor rename flow so the actual destination path is computed once and returned.
3. Filter undo to successful rename events only.
4. Add explicit logging for config-load failures and processor exceptions.

### Phase 2 — Robustness

5. Replace Gemini regex parsing with schema-backed validation.
6. Validate prompt templates during config loading.
7. Add structured error categories for processor failures.

### Phase 3 — Maintainability

8. Split `markitdown_processor.py` into smaller units.
9. Split `llm_integration.py` into provider adapters, retry/policy, and logging/redaction helpers.
10. Add architecture notes to the major modules.

---

## Suggested Architecture Improvements

### Provider abstraction

Create a provider contract that returns a normalized response object, e.g.:

```python
@dataclass
class SuggestionResponse:
    suggestions: list[str]
    raw_text: str | None = None
    provider: str = ""
```

This would let every provider share the same validation and logging pipeline.

### Rename transaction model

Represent rename operations explicitly:

```python
@dataclass
class PlannedRename:
    source_path: str
    target_path: str
    strategy: str
    session_id: int | None
```

Then pass `target_path` all the way through to the final atomic move.

### Processor result model

Extend `ProcessingResult` or add a sibling error type:

```python
@dataclass
class ProcessingFailure:
    source_path: str
    reason: str
    recoverable: bool
```

This would make skipped-vs-failed behavior visible and testable.

---

## Conclusion

This is a promising codebase with a good foundation, especially in modular structure and automated testing. The biggest risks are not stylistic; they are **integrity and robustness issues at the seams**: transport configuration, rename/history consistency, and silent failure handling.

If only three fixes are prioritized, they should be:

1. **Fix rename/history divergence**
2. **Eliminate insecure transport heuristics**
3. **Stop swallowing important failures silently**

Those changes would materially improve security, user trust, and operability without requiring a full redesign.
