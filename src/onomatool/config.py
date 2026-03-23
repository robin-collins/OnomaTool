import os
from enum import Enum
from typing import Any

import tomli
from pydantic import BaseModel, Field, ValidationError, field_validator


class Provider(str, Enum):
    openai = "openai"
    google = "google"
    mock = "mock"


class NamingConvention(str, Enum):
    snake_case = "snake_case"
    camelCase = "camelCase"
    kebab_case = "kebab-case"
    PascalCase = "PascalCase"
    dot_notation = "dot.notation"
    natural_language = "natural language"


class MarkitdownConfig(BaseModel):
    enable_plugins: bool = False
    docintel_endpoint: str = ""


class OnomatoolConfig(BaseModel):
    default_provider: Provider = Provider.openai
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_deployment: str = ""
    use_azure_openai: bool = False
    google_api_key: str = ""
    naming_convention: NamingConvention = NamingConvention.snake_case
    llm_model: str = "gpt-4o"
    min_filename_words: int = Field(default=5, ge=1, le=50)
    max_filename_words: int = Field(default=15, ge=1, le=100)
    system_prompt: str = ""
    user_prompt: str = ""
    image_prompt: str = ""
    markitdown: MarkitdownConfig = MarkitdownConfig()

    @field_validator("max_filename_words")
    @classmethod
    def max_gte_min(cls, v, info):
        min_words = info.data.get("min_filename_words")
        if min_words is not None and v < min_words:
            raise ValueError(
                f"max_filename_words ({v}) must be >= min_filename_words ({min_words})"
            )
        return v


# Keep DEFAULT_CONFIG as a dict for backward compatibility
DEFAULT_CONFIG = OnomatoolConfig().model_dump(mode="python")
# Restore string values for enums so dict consumers get plain strings
DEFAULT_CONFIG["default_provider"] = "openai"
DEFAULT_CONFIG["naming_convention"] = "snake_case"


def get_config(config_path: str | None = None) -> dict[str, Any]:
    """
    Load configuration from the given config_path or from ~/.onomarc if not specified.
    Validates via OnomatoolConfig Pydantic model.
    Returns the config as a dict, or DEFAULT_CONFIG if loading fails.
    """
    if config_path is None:
        config_path = os.path.expanduser("~/.onomarc")
    else:
        config_path = os.path.expanduser(config_path)
    if os.path.exists(config_path):
        try:
            with open(config_path, "rb") as f:
                raw = tomli.load(f)
            validated = OnomatoolConfig(**raw)
            result = validated.model_dump(mode="python")
            # Convert enums back to strings for dict consumers
            result["default_provider"] = str(validated.default_provider.value)
            result["naming_convention"] = str(validated.naming_convention.value)
            return result
        except ValidationError as e:
            print(f"Configuration validation error: {e}")
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()
