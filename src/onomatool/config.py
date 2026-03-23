import logging
import os
from enum import Enum
from typing import Any

import tomli
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


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


CURRENT_CONFIG_VERSION = 1


class OnomatoolConfig(BaseModel):
    config_version: int = Field(default=CURRENT_CONFIG_VERSION, ge=1)
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
    max_retries: int = Field(default=0, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.0, le=60.0)
    rate_limit_delay: float = Field(default=0.0, ge=0.0, le=60.0)
    history_retention_days: int = Field(default=90, ge=1, le=3650)
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
            raw = _migrate_config(raw)
            validated = OnomatoolConfig(**raw)
            result = validated.model_dump(mode="python")
            # Convert enums back to strings for dict consumers
            result["default_provider"] = str(validated.default_provider.value)
            result["naming_convention"] = str(validated.naming_convention.value)
            return result
        except ValidationError as e:
            logger.warning("Configuration validation error: %s", e)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def _migrate_config(raw: dict) -> dict:
    """Migrate config from older versions to the current schema.

    Old configs without config_version are treated as version 1.
    Each migration step upgrades one version at a time.
    """
    version = raw.get("config_version", 1)
    if version >= CURRENT_CONFIG_VERSION:
        return raw

    raw = raw.copy()

    # Future migrations go here, e.g.:
    # if version < 2:
    #     # Migrate from v1 to v2
    #     raw.setdefault("new_field", "default_value")
    #     version = 2

    raw["config_version"] = CURRENT_CONFIG_VERSION
    logger.info("Migrated config from version %d to %d", version, CURRENT_CONFIG_VERSION)
    return raw
