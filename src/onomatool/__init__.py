"""OnomaTool package for AI-powered file renaming."""

__version__ = "0.1.0"

from onomatool.exceptions import (
    OnomaConfigError,
    OnomaConflictError,
    OnomaError,
    OnomaLLMError,
    OnomaProcessingError,
)

__all__ = [
    "OnomaError",
    "OnomaConfigError",
    "OnomaLLMError",
    "OnomaProcessingError",
    "OnomaConflictError",
]
