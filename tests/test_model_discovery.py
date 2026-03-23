"""Tests for the model_discovery module."""

from unittest.mock import MagicMock, patch

import pytest

from onomatool.model_discovery import (
    ModelInfo,
    _extract_base_origin,
    _is_local_url,
    format_model_list,
    list_models,
    list_models_google,
    list_models_openai,
    select_model_interactive,
)

# --- ModelInfo tests ---


class TestModelInfo:
    def test_display_line_basic(self):
        m = ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai")
        assert m.display_line() == "gpt-4o"

    def test_display_line_with_tags(self):
        m = ModelInfo(
            id="llama-3",
            name="Llama 3",
            provider="lmstudio",
            supports_vision=True,
            loaded=True,
            architecture="llama",
            size="8B/Q4_0",
        )
        line = m.display_line()
        assert "vision" in line
        assert "loaded" in line
        assert "llama" in line
        assert "8B/Q4_0" in line

    def test_display_line_verbose_shows_name(self):
        m = ModelInfo(id="gemma-3", name="Gemma 3 Instruct", provider="lmstudio")
        line = m.display_line(verbose=True)
        assert "(Gemma 3 Instruct)" in line

    def test_display_line_verbose_hides_duplicate_name(self):
        m = ModelInfo(id="gpt-4o", name="gpt-4o", provider="openai")
        line = m.display_line(verbose=True)
        assert "(" not in line


# --- Helper function tests ---


class TestHelpers:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("http://localhost:1234/v1", True),
            ("http://127.0.0.1:1234/v1", True),
            ("http://0.0.0.0:1234/v1", True),
            ("https://localhost:1234/v1", True),
            ("https://api.openai.com/v1", False),
            ("http://example.com:1234/v1", False),
        ],
    )
    def test_is_local_url(self, url, expected):
        assert _is_local_url(url) == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("http://localhost:1234/v1", "http://localhost:1234"),
            ("http://127.0.0.1:5000/v1/models", "http://127.0.0.1:5000"),
            ("https://api.openai.com/v1", "https://api.openai.com"),
        ],
    )
    def test_extract_base_origin(self, url, expected):
        assert _extract_base_origin(url) == expected


# --- OpenAI model listing ---


class TestListModelsOpenAI:
    def test_standard_openai(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-4o-mini"},
                {"id": "gpt-3.5-turbo"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        config = {
            "openai_base_url": "https://api.openai.com/v1",
            "openai_api_key": "sk-test",
        }
        with patch("onomatool.model_discovery.httpx.get", return_value=mock_resp):
            models = list_models_openai(config)

        assert len(models) == 3
        assert models[0].provider == "openai"
        ids = [m.id for m in models]
        assert "gpt-4o" in ids

    def test_lmstudio_rich_api(self):
        """When base_url is localhost, try LMStudio REST API first."""
        lms_resp = MagicMock()
        lms_resp.status_code = 200
        lms_resp.json.return_value = {
            "models": [
                {
                    "type": "llm",
                    "key": "gemma-3-12b-it",
                    "display_name": "Gemma 3 12B Instruct",
                    "architecture": "gemma3",
                    "quantization": {"name": "Q4_K_M", "bits_per_weight": 4},
                    "params_string": "12B",
                    "loaded_instances": [{"id": "gemma-3-12b-it", "config": {}}],
                    "max_context_length": 32768,
                    "format": "gguf",
                    "capabilities": {"vision": True, "trained_for_tool_use": False},
                },
                {
                    "type": "embedding",
                    "key": "nomic-embed",
                    "display_name": "Nomic Embed",
                    "quantization": {},
                    "params_string": None,
                    "loaded_instances": [],
                    "max_context_length": 2048,
                    "format": "gguf",
                },
            ]
        }
        lms_resp.raise_for_status = MagicMock()

        config = {
            "openai_base_url": "http://localhost:1234/v1",
            "openai_api_key": "lm-studio",
        }
        with patch("onomatool.model_discovery.httpx.get", return_value=lms_resp):
            models = list_models_openai(config)

        # Embedding models should be filtered out
        assert len(models) == 1
        m = models[0]
        assert m.id == "gemma-3-12b-it"
        assert m.provider == "lmstudio"
        assert m.supports_vision is True
        assert m.loaded is True
        assert m.architecture == "gemma3"
        assert m.size == "12B/Q4_K_M"

    def test_lmstudio_fallback_to_openai(self):
        """If LMStudio REST API fails, fall back to OpenAI /v1/models."""
        openai_resp = MagicMock()
        openai_resp.status_code = 200
        openai_resp.json.return_value = {"data": [{"id": "local-model"}]}
        openai_resp.raise_for_status = MagicMock()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("LMStudio API not available")
            return openai_resp

        config = {
            "openai_base_url": "http://localhost:1234/v1",
            "openai_api_key": "",
        }
        with patch("onomatool.model_discovery.httpx.get", side_effect=side_effect):
            models = list_models_openai(config)

        assert len(models) == 1
        assert models[0].id == "local-model"
        assert models[0].provider == "lmstudio"


# --- Google model listing ---


class TestListModelsGoogle:
    def test_list_google_models(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.0-flash",
                    "displayName": "Gemini 2.0 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                    "inputTokenLimit": 1048576,
                    "outputTokenLimit": 8192,
                },
                {
                    "name": "models/text-embedding-004",
                    "displayName": "Text Embedding",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        config = {"google_api_key": "test-key"}
        with patch("onomatool.model_discovery.httpx.get", return_value=mock_resp):
            models = list_models_google(config)

        # Embedding model should be filtered out (no generateContent)
        assert len(models) == 1
        assert models[0].id == "gemini-2.0-flash"
        assert models[0].supports_vision is True  # gemini-2.x supports vision

    def test_missing_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            config = {"google_api_key": ""}
            with pytest.raises(RuntimeError, match="Google API key required"):
                list_models_google(config)


# --- Provider dispatch ---


class TestListModels:
    def test_dispatch_openai(self):
        config = {
            "default_provider": "openai",
            "openai_base_url": "https://api.openai.com/v1",
            "openai_api_key": "sk-test",
        }
        with patch(
            "onomatool.model_discovery.list_models_openai",
            return_value=[ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai")],
        ):
            models = list_models(config)
        assert len(models) == 1

    def test_dispatch_google(self):
        config = {"default_provider": "google", "google_api_key": "test"}
        with patch(
            "onomatool.model_discovery.list_models_google",
            return_value=[
                ModelInfo(id="gemini-2.0-flash", name="Flash", provider="google")
            ],
        ):
            models = list_models(config)
        assert len(models) == 1

    def test_dispatch_mock(self):
        config = {"default_provider": "mock"}
        models = list_models(config)
        assert len(models) == 1
        assert models[0].id == "mock-model"

    def test_dispatch_unsupported(self):
        config = {"default_provider": "unsupported"}
        with pytest.raises(RuntimeError, match="Unsupported provider"):
            list_models(config)


# --- Formatting ---


class TestFormatModelList:
    def test_empty(self):
        assert format_model_list([]) == "No models found."

    def test_formats_models(self):
        models = [
            ModelInfo(id="model-a", name="Model A", provider="openai"),
            ModelInfo(
                id="model-b",
                name="Model B",
                provider="openai",
                supports_vision=True,
            ),
        ]
        output = format_model_list(models)
        assert "model-a" in output
        assert "model-b" in output
        assert "2 model(s) found" in output
        assert "vision" in output


# --- Interactive selection ---


class TestSelectModelInteractive:
    def test_select_by_number(self):
        models = [
            ModelInfo(id="model-a", name="A", provider="test"),
            ModelInfo(id="model-b", name="B", provider="test"),
        ]
        with patch("builtins.input", return_value="2"):
            result = select_model_interactive(models)
        assert result is not None
        assert result.id == "model-b"

    def test_select_by_name_substring(self):
        models = [
            ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai"),
            ModelInfo(id="gpt-3.5-turbo", name="GPT-3.5", provider="openai"),
        ]
        with patch("builtins.input", return_value="3.5"):
            result = select_model_interactive(models)
        assert result is not None
        assert result.id == "gpt-3.5-turbo"

    def test_cancel_with_q(self):
        models = [ModelInfo(id="m", name="M", provider="test")]
        with patch("builtins.input", return_value="q"):
            result = select_model_interactive(models)
        assert result is None

    def test_empty_models(self):
        result = select_model_interactive([])
        assert result is None

    def test_eof_returns_none(self):
        models = [ModelInfo(id="m", name="M", provider="test")]
        with patch("builtins.input", side_effect=EOFError):
            result = select_model_interactive(models)
        assert result is None
