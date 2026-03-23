"""Custom exception hierarchy for OnomaTool."""


class OnomaError(Exception):
    """Base exception for all OnomaTool errors."""


class OnomaConfigError(OnomaError):
    """Configuration loading or validation error."""


class OnomaLLMError(OnomaError):
    """LLM provider communication or response error."""


class OnomaProcessingError(OnomaError):
    """File processing error."""


class OnomaConflictError(OnomaError):
    """Filename conflict resolution error."""
