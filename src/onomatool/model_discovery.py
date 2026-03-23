"""Model discovery for listing available models from AI providers.

Supports OpenAI, Google Gemini, and LMStudio (auto-detected via localhost base URL).
When a local LMStudio server is detected, the richer /api/v1/models endpoint is used
to retrieve additional metadata like vision capabilities and architecture info.
"""

import logging
import os
from dataclasses import dataclass, field

import httpx

from onomatool.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Normalized model information across providers."""

    id: str
    name: str
    provider: str
    supports_vision: bool = False
    architecture: str | None = None
    size: str | None = None
    loaded: bool = False
    extra: dict = field(default_factory=dict)

    def display_line(self, verbose: bool = False) -> str:
        """Format a single-line display string for this model."""
        parts = [self.id]
        tags = []
        if self.supports_vision:
            tags.append("vision")
        if self.loaded:
            tags.append("loaded")
        if self.architecture:
            tags.append(self.architecture)
        if self.size:
            tags.append(self.size)
        if tags:
            parts.append(f"[{', '.join(tags)}]")
        if verbose and self.name != self.id:
            parts.append(f"({self.name})")
        return "  ".join(parts)


def _is_local_url(url: str) -> bool:
    """Check if a URL points to a local server (likely LMStudio)."""
    for prefix in (
        "http://localhost",
        "http://127.0.0.1",
        "http://0.0.0.0",
        "https://localhost",
        "https://127.0.0.1",
    ):
        if url.startswith(prefix):
            return True
    return False


def _extract_base_origin(base_url: str) -> str:
    """Extract scheme://host:port from a base URL like http://localhost:1234/v1."""
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    port_part = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port_part}"


def list_models_openai(config: dict) -> list[ModelInfo]:
    """List models from an OpenAI-compatible endpoint.

    If the endpoint is a local server (e.g. LMStudio), also tries the
    richer /api/v1/models endpoint for additional metadata.
    """
    base_url = config.get("openai_base_url", "https://api.openai.com/v1")
    api_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or ""

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    is_local = _is_local_url(base_url)
    verify = not is_local

    # Try LMStudio's richer REST API first for local servers
    if is_local:
        try:
            return _list_models_lmstudio(base_url, headers, verify)
        except Exception as e:
            logger.debug("LMStudio REST API unavailable, falling back to OpenAI: %s", e)

    # Standard OpenAI /v1/models endpoint
    models_url = base_url.rstrip("/") + "/models"
    try:
        resp = httpx.get(models_url, headers=headers, verify=verify, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Failed to list models from {models_url}: {e}") from e

    models = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        models.append(
            ModelInfo(
                id=model_id,
                name=model_id,
                provider="openai" if not is_local else "lmstudio",
            )
        )

    models.sort(key=lambda m: m.id)
    return models


def _list_models_lmstudio(
    base_url: str, headers: dict, verify: bool
) -> list[ModelInfo]:
    """List models from LMStudio's native /api/v1/models endpoint."""
    origin = _extract_base_origin(base_url)
    api_url = f"{origin}/api/v1/models"

    resp = httpx.get(api_url, headers=headers, verify=verify, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()

    models = []
    for m in data.get("models", []):
        model_type = m.get("type", "llm")
        if model_type != "llm":
            continue

        model_key = m.get("key", "")
        capabilities = m.get("capabilities", {})
        quantization = m.get("quantization", {})

        quant_name = ""
        if quantization:
            quant_name = quantization.get("name") or ""

        size_label = m.get("params_string") or ""
        if quant_name and size_label:
            size_label = f"{size_label}/{quant_name}"
        elif quant_name:
            size_label = quant_name

        models.append(
            ModelInfo(
                id=model_key,
                name=m.get("display_name", model_key),
                provider="lmstudio",
                supports_vision=capabilities.get("vision", False),
                architecture=m.get("architecture"),
                size=size_label or None,
                loaded=len(m.get("loaded_instances", [])) > 0,
                extra={
                    "max_context_length": m.get("max_context_length"),
                    "format": m.get("format"),
                    "trained_for_tool_use": capabilities.get(
                        "trained_for_tool_use", False
                    ),
                },
            )
        )

    models.sort(key=lambda m: (not m.loaded, m.id))
    return models


def list_models_google(config: dict) -> list[ModelInfo]:
    """List models from Google Gemini API."""
    api_key = config.get("google_api_key") or os.environ.get("GOOGLE_API_KEY") or ""
    if not api_key:
        raise RuntimeError(
            "Google API key required. Set google_api_key in ~/.onomarc or GOOGLE_API_KEY env var."
        )

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    params = {"key": api_key}

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Failed to list Google models: {e}") from e

    models = []
    for m in data.get("models", []):
        model_name = m.get("name", "")
        # API returns "models/gemini-1.5-pro" — strip prefix for usability
        model_id = model_name.removeprefix("models/")

        # Filter to generative models only
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue

        # Vision support: models with vision in name or multimodal input
        supports_vision = "vision" in model_id.lower() or any(
            "image" in (t or "").lower()
            for t in m.get("supportedGenerationMethods", [])
        )
        # Gemini 1.5+ and 2.0+ models generally support vision
        if any(
            model_id.startswith(p)
            for p in ("gemini-1.5", "gemini-2", "gemini-exp", "gemini-pro-vision")
        ):
            supports_vision = True

        models.append(
            ModelInfo(
                id=model_id,
                name=m.get("displayName", model_id),
                provider="google",
                supports_vision=supports_vision,
                extra={
                    "input_token_limit": m.get("inputTokenLimit"),
                    "output_token_limit": m.get("outputTokenLimit"),
                },
            )
        )

    models.sort(key=lambda m: m.id)
    return models


def list_models(config: dict | None = None) -> list[ModelInfo]:
    """List models for the currently configured provider."""
    if config is None:
        config = get_config()

    provider = config.get("default_provider", "openai")

    if provider == "openai":
        return list_models_openai(config)
    elif provider == "google":
        return list_models_google(config)
    elif provider == "mock":
        return [
            ModelInfo(id="mock-model", name="Mock Model", provider="mock"),
        ]
    else:
        raise RuntimeError(f"Unsupported provider for model listing: {provider}")


def format_model_list(models: list[ModelInfo], verbose: bool = False) -> str:
    """Format a list of models for display."""
    if not models:
        return "No models found."

    lines = []
    provider = models[0].provider if models else "unknown"
    lines.append(f"Available models ({provider}):")
    lines.append("")

    for i, model in enumerate(models, 1):
        lines.append(f"  {i:3d}. {model.display_line(verbose)}")

    lines.append("")
    lines.append(f"{len(models)} model(s) found.")
    return "\n".join(lines)


def select_model_interactive(
    models: list[ModelInfo],
) -> ModelInfo | None:
    """Present an interactive model picker. Returns selected ModelInfo or None."""
    if not models:
        print("No models available.")
        return None

    print(format_model_list(models, verbose=True))
    print()

    while True:
        try:
            choice = input("Select model number (or 'q' to cancel): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if choice.lower() in ("q", "quit", ""):
            return None

        try:
            idx = int(choice)
            if 1 <= idx <= len(models):
                return models[idx - 1]
            print(f"Please enter a number between 1 and {len(models)}.")
        except ValueError:
            # Try matching by model ID substring
            matches = [m for m in models if choice.lower() in m.id.lower()]
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                print(f"Ambiguous match ({len(matches)} models). Use a number instead.")
            else:
                print("Invalid input. Enter a number or model name.")
