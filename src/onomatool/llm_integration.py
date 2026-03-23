import base64
import functools
import json
import logging
import mimetypes
import os
import re
import threading
import time
from typing import Protocol

import tiktoken

logger = logging.getLogger(__name__)

from onomatool.config import get_config
from onomatool.exceptions import OnomaLLMError
from onomatool.models import (
    generate_json_schema_from_model,
    get_model_for_naming_convention,
)
from onomatool.prompts import get_image_prompt, get_system_prompt, get_user_prompt

# Maximum tokens for LLM response - limits response to 100 tokens
MAX_TOKENS = 100

# Track last API call time for rate limiting (protected by _rate_limit_lock)
_last_call_time: float = 0.0
_rate_limit_lock = threading.Lock()

# Maximum characters to send to LLM (approx 65,535 tokens)
MAX_CONTENT_CHARS = 120_000

# Maximum consecutive digits allowed in a single word
MAX_CONSECUTIVE_DIGITS = 10


class LLMProvider(Protocol):
    """Protocol for LLM provider implementations."""

    def get_suggestions(
        self,
        messages: list[dict],
        pydantic_model: type,
        json_schema: dict,
        model: str,
        verbose_level: int,
    ) -> list[str]: ...

    def supports_images(self) -> bool: ...


class MockProvider:
    """Mock provider for testing — returns static suggestions."""

    MOCK_SUGGESTIONS = {
        "snake_case": ["mock_file_one", "mock_file_two", "mock_file_three"],
        "camelCase": ["mockFileOne", "mockFileTwo", "mockFileThree"],
        "kebab-case": ["mock-file-one", "mock-file-two", "mock-file-three"],
        "PascalCase": ["MockFileOne", "MockFileTwo", "MockFileThree"],
        "dot.notation": ["mock.file.one", "mock.file.two", "mock.file.three"],
        "natural language": ["Mock File One", "Mock File Two", "Mock File Three"],
    }

    def __init__(self, naming_convention: str = "snake_case"):
        self.naming_convention = naming_convention

    def get_suggestions(
        self,
        messages: list[dict],
        pydantic_model: type,
        json_schema: dict,
        model: str,
        verbose_level: int,
    ) -> list[str]:
        return self.MOCK_SUGGESTIONS.get(
            self.naming_convention,
            self.MOCK_SUGGESTIONS["snake_case"],
        )

    def supports_images(self) -> bool:
        return True


class OpenAIProvider:
    """OpenAI and Azure OpenAI provider."""

    def __init__(self, config: dict):
        self.config = config

    def _create_client(self):
        import httpx
        from openai import OpenAI

        use_azure = self.config.get("use_azure_openai", False)

        if use_azure:
            from openai import AzureOpenAI

            azure_endpoint = self.config.get("azure_openai_endpoint") or os.environ.get(
                "AZURE_OPENAI_ENDPOINT"
            )
            azure_api_key = self.config.get("azure_openai_api_key") or os.environ.get(
                "AZURE_OPENAI_API_KEY"
            )
            azure_api_version = self.config.get(
                "azure_openai_api_version", "2024-02-01"
            )

            if not azure_endpoint:
                raise RuntimeError(
                    "Azure OpenAI endpoint is required when use_azure_openai is True"
                )
            if not azure_api_key:
                raise RuntimeError(
                    "Azure OpenAI API key is required when use_azure_openai is True"
                )

            return AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
            )

        base_url = self.config.get("openai_base_url", "https://api.openai.com/v1")
        api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        verify = not self.config.get("allow_insecure_transport", False)
        if not verify:
            logger.warning("SSL verification disabled via allow_insecure_transport config")
        return OpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=httpx.Client(verify=verify),
        )

    def get_suggestions(
        self,
        messages: list[dict],
        pydantic_model: type,
        json_schema: dict,
        model: str,
        verbose_level: int,
    ) -> list[str]:
        client = self._create_client()

        if verbose_level > 0:
            use_azure = self.config.get("use_azure_openai", False)
            if use_azure:
                logger.debug("Using Azure OpenAI")
                logger.debug(
                    "Azure endpoint: %s", self.config.get("azure_openai_endpoint")
                )
                logger.debug(
                    "Azure deployment: %s", self.config.get("azure_openai_deployment")
                )
            else:
                logger.debug("Using OpenAI")
                logger.debug(
                    "Base URL: %s",
                    self.config.get("openai_base_url", "https://api.openai.com/v1"),
                )
            logger.debug("Model: %s", model)
            logger.debug("Pydantic Model: %s", pydantic_model.__name__)

        if verbose_level > 1:
            _log_verbose_request(messages, json_schema, model, self.config)

        # Try structured output with Pydantic first
        try:
            response = client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=pydantic_model,
                max_tokens=MAX_TOKENS,
            )
            parsed_result = response.choices[0].message.parsed
            if parsed_result is None:
                raise RuntimeError("Structured output parsing failed")

            if verbose_level > 0:
                logger.debug("Used structured output with Pydantic model")
                logger.debug("Response: suggestions=%s", parsed_result.suggestions)

            return parsed_result.suggestions

        except Exception as structured_error:
            if verbose_level > 0:
                logger.debug("Structured output failed: %s", structured_error)
                logger.debug("Falling back to JSON schema approach")

            # Fallback to traditional JSON schema approach
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=json_schema,
                max_tokens=MAX_TOKENS,
            )
            result = json.loads(response.choices[0].message.content)
            if not isinstance(result, dict) or "suggestions" not in result:
                raise RuntimeError(
                    "LLM JSON response missing 'suggestions' key."
                ) from None
            suggestions = result["suggestions"]

            if verbose_level > 0:
                logger.debug("Used JSON Schema fallback")
                logger.debug("Response: suggestions=%s", suggestions)

            if verbose_level > 1:
                logger.debug(
                    "Full response content: %s", response.choices[0].message.content
                )

            if not (isinstance(suggestions, list) and len(suggestions) == 3):
                raise RuntimeError(
                    "LLM did not return exactly 3 suggestions."
                ) from None
            return suggestions

    def supports_images(self) -> bool:
        return True


class GoogleProvider:
    """Google Gemini provider."""

    def __init__(self, config: dict):
        self.config = config

    def get_suggestions(
        self,
        messages: list[dict],
        pydantic_model: type,
        json_schema: dict,
        model: str,
        verbose_level: int,
    ) -> list[str]:
        from google import genai
        from google.genai import types

        api_key = self.config.get("google_api_key") or os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)

        if verbose_level > 0:
            logger.debug("Using Google Gemini")
            logger.debug("Model: %s", model)

        # Extract user prompt and image data from messages
        user_prompt = ""
        image_parts: list[types.Part] = []

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    user_prompt = content
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                user_prompt = item.get("text", "")
                            elif item.get("type") == "image_url":
                                image_url_data = item.get("image_url", {})
                                url = (
                                    image_url_data.get("url", "")
                                    if isinstance(image_url_data, dict)
                                    else image_url_data
                                )
                                if url.startswith("data:"):
                                    # Parse data URI: data:<mime>;base64,<data>
                                    header, b64_data = url.split(",", 1)
                                    mime_type = header.split(":")[1].split(";")[0]
                                    image_bytes = base64.b64decode(b64_data)
                                    image_parts.append(
                                        types.Part.from_bytes(
                                            data=image_bytes,
                                            mime_type=mime_type,
                                        )
                                    )
                break

        if verbose_level > 1:
            total_chars = len(user_prompt)
            total_tokens = count_text_tokens(user_prompt, "gpt-4o")
            logger.debug("Total characters in request: %s", total_chars)
            logger.debug("Estimated tokens: %s", total_tokens)
            if image_parts:
                logger.debug("Image parts: %d", len(image_parts))

        # Build contents: text + images
        contents: list = []
        if image_parts:
            contents.append(user_prompt)
            contents.extend(image_parts)
        else:
            contents = user_prompt

        # Use JSON mode with schema for structured output
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "suggestions": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                        }
                    },
                    "required": ["suggestions"],
                },
            ),
        )

        try:
            result = json.loads(response.text)
            suggestions = result["suggestions"]
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fallback to regex if JSON parsing fails
            suggestions = re.findall(r'"([a-zA-Z0-9_\-\. ]{1,128})"', response.text)

        if verbose_level > 0:
            logger.debug("Response: suggestions=%s", suggestions[:3])

        if verbose_level > 1:
            logger.debug("Full response text: %s", response.text)

        if len(suggestions) < 3:
            raise RuntimeError("Google LLM did not return enough suggestions.")
        return suggestions[:3]

    def supports_images(self) -> bool:
        return True


# --- Provider factory ---


def get_provider(config: dict) -> LLMProvider:
    """Get the appropriate LLM provider based on config."""
    provider_name = config.get("default_provider", "openai")
    naming_convention = config.get("naming_convention", "snake_case")

    if provider_name == "mock":
        return MockProvider(naming_convention)
    elif provider_name == "openai":
        return OpenAIProvider(config)
    elif provider_name == "google":
        return GoogleProvider(config)
    else:
        raise RuntimeError(f"Unsupported provider: {provider_name}")


# --- Retry logic ---


def _apply_rate_limit(delay: float, verbose_level: int = 0) -> None:
    """Sleep if needed to enforce rate_limit_delay between consecutive API calls."""
    global _last_call_time
    if delay <= 0:
        return
    with _rate_limit_lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if _last_call_time > 0 and elapsed < delay:
            wait = delay - elapsed
            if verbose_level > 0:
                logger.debug("Rate limit: waiting %.2fs before next API call", wait)
            time.sleep(wait)
        _last_call_time = time.monotonic()


def _is_transient_error(err: Exception) -> bool:
    """Return True if the error is transient and worth retrying."""
    # OpenAI SDK exceptions
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError

        if isinstance(err, (APITimeoutError, APIConnectionError)):
            return True
        if isinstance(err, APIStatusError):
            return err.status_code >= 500 or err.status_code == 429
    except ImportError:
        pass

    # Google SDK exceptions
    err_str = str(err).lower()
    for keyword in ("timeout", "rate limit", "429", "500", "502", "503", "504"):
        if keyword in err_str:
            return True

    return False


def _call_provider_with_retry(
    provider: LLMProvider,
    messages: list[dict],
    pydantic_model: type,
    json_schema: dict,
    model: str,
    verbose_level: int,
    max_retries: int,
    retry_delay: float,
) -> list[str]:
    """Call provider.get_suggestions with exponential backoff on transient errors."""
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return provider.get_suggestions(
                messages, pydantic_model, json_schema, model, verbose_level
            )
        except Exception as err:
            last_error = err
            if not _is_transient_error(err) or attempt >= max_retries:
                raise
            delay = retry_delay * (2**attempt)
            logger.warning(
                "LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                err,
                delay,
            )
            time.sleep(delay)

    # Should not reach here, but just in case
    raise last_error  # type: ignore[misc]


# --- Utility functions ---


def get_pydantic_model_and_schema(naming_convention: str) -> tuple:
    try:
        model_class = get_model_for_naming_convention(naming_convention)
        json_schema = generate_json_schema_from_model(model_class)
        return model_class, json_schema
    except ValueError:
        model_class = get_model_for_naming_convention("snake_case")
        json_schema = generate_json_schema_from_model(model_class)
        return model_class, json_schema


def is_image_file(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_suggestions(
    content: str,
    verbose_level: int = 0,
    file_path: str | None = None,
    config: dict | None = None,
) -> list[str]:
    """Query the configured LLM for filename suggestions."""
    if config is None:
        config = get_config()

    naming_convention = config.get("naming_convention", "snake_case")
    model = config.get("llm_model", "gpt-4o")

    # For Azure, override model with deployment name
    if config.get("use_azure_openai", False):
        azure_deployment = config.get("azure_openai_deployment") or os.environ.get(
            "AZURE_OPENAI_DEPLOYMENT"
        )
        if azure_deployment:
            model = azure_deployment

    pydantic_model, json_schema = get_pydantic_model_and_schema(naming_convention)
    system_prompt = get_system_prompt(config)

    # Truncate content
    truncated_content = content[:MAX_CONTENT_CHARS]
    if len(content) > MAX_CONTENT_CHARS and verbose_level > 0:
        logger.debug(
            "Content truncated from %s to %s characters",
            len(content),
            MAX_CONTENT_CHARS,
        )

    # Detect image files
    is_image = file_path and is_image_file(file_path)
    if is_image:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".svg":
            raise RuntimeError(
                "Raw SVG files must not be sent to the LLM. Convert to PNG first."
            )
        if ext == ".png":
            mime = "image/png"
        else:
            mime, _ = mimetypes.guess_type(file_path)
            if not mime:
                mime = "image/jpeg"
        base64_image = encode_image_base64(file_path)
        image_url = f"data:{mime};base64,{base64_image}"
    else:
        image_url = None

    # Build prompt
    if is_image:
        user_prompt = get_image_prompt(naming_convention, config)
    else:
        user_prompt = get_user_prompt(naming_convention, truncated_content, config)

    # Build messages
    if is_image and image_url:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # Get provider and call with retry
    provider = get_provider(config)
    max_retries = config.get("max_retries", 0)
    retry_delay = config.get("retry_delay", 1.0)
    rate_limit_delay = config.get("rate_limit_delay", 0.0)

    # Apply rate limiting between consecutive API calls
    _apply_rate_limit(rate_limit_delay, verbose_level)

    try:
        result = _call_provider_with_retry(
            provider,
            messages,
            pydantic_model,
            json_schema,
            model,
            verbose_level,
            max_retries,
            retry_delay,
        )
        return result
    except Exception as err:
        provider_name = config.get("default_provider", "openai")
        raise OnomaLLMError(f"{provider_name} LLM call failed: {err}") from err


def _log_verbose_request(
    messages: list[dict], json_schema: dict, model: str, config: dict
) -> None:
    """Log detailed request info for -vv mode."""
    min_words = config.get("min_filename_words", 5)
    max_words = config.get("max_filename_words", 15)
    logger.debug("JSON Schema: %s", json.dumps(json_schema, indent=2))
    logger.debug("Max tokens: %s", MAX_TOKENS)
    logger.debug("Min filename words: %s", min_words)
    logger.debug("Max filename words: %s", max_words)

    has_image = any(
        isinstance(msg.get("content"), list)
        and any(
            isinstance(item, dict) and item.get("type") == "image_url"
            for item in msg["content"]
        )
        for msg in messages
    )
    redact_text = not has_image

    total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
    if has_image:
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total_chars = len(item.get("text", ""))
    total_tokens = count_tokens_for_messages(messages, model)

    logger.debug("Total characters in request: %s", total_chars)
    logger.debug("Estimated tokens: %s", total_tokens)

    redacted = _redact_messages(messages, redact_text=redact_text)
    logger.debug("Messages: %s", json.dumps(redacted, indent=2))

    if redact_text:
        logger.debug("Text content redacted as [[file_content]]")
    else:
        logger.debug("Image content - text not redacted, base64 images redacted")


def _redact_messages(messages: list, redact_text: bool = True) -> list:
    """Redact sensitive content from messages for logging."""

    def redact(msg):
        if not isinstance(msg, dict):
            return msg
        msg = msg.copy()
        if msg.get("type") == "image_url":
            if isinstance(msg.get("image_url"), dict) and "url" in msg["image_url"]:
                msg["image_url"] = {"url": "[[base64_image]]"}
            elif isinstance(msg.get("image_url"), str):
                msg["image_url"] = "[[base64_image]]"
        if redact_text and msg.get("type") == "text":
            msg["text"] = "[[file_content]]"
        if isinstance(msg.get("content"), list):
            msg["content"] = [redact(x) for x in msg["content"]]
        return msg

    return [redact(m) for m in messages]


@functools.lru_cache(maxsize=8)
def _get_tiktoken_encoding(model: str):
    """Get and cache tiktoken encoding for a model."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens_for_messages(messages: list, model: str = "gpt-4o") -> int:
    """Count tokens for OpenAI chat completion messages using tiktoken."""
    encoding = _get_tiktoken_encoding(model)

    tokens_per_message = 3
    tokens_per_name = 1

    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            if key == "content":
                if isinstance(value, str):
                    num_tokens += len(encoding.encode(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and item.get("type") == "text":
                            num_tokens += len(encoding.encode(item.get("text", "")))
            else:
                num_tokens += len(encoding.encode(str(value)))
            if key == "name":
                num_tokens += tokens_per_name

    num_tokens += 3
    return num_tokens


def count_text_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens for a text string using tiktoken."""
    encoding = _get_tiktoken_encoding(model)
    return len(encoding.encode(text))
