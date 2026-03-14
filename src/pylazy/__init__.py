"""Public package interface for PyLazy."""

from pylazy.core import GeneratedFunction, connect, createFunction, create_function
from pylazy.exceptions import (
    ConfigurationError,
    GenerationError,
    ProviderError,
    PyLazyError,
    ValidationError,
)
from pylazy.providers import GeminiProvider, OllamaProvider, OpenAIProvider

__all__ = [
    "ConfigurationError",
    "GeminiProvider",
    "GeneratedFunction",
    "GenerationError",
    "OllamaProvider",
    "OpenAIProvider",
    "ProviderError",
    "PyLazyError",
    "ValidationError",
    "connect",
    "createFunction",
    "create_function",
]

__version__ = "0.1.0"
