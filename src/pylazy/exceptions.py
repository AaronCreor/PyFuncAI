"""Shared exception hierarchy for PyLazy."""


class PyLazyError(Exception):
    """Base exception for all library-specific errors."""


class ConfigurationError(PyLazyError):
    """Raised when runtime or provider configuration is incomplete or invalid."""


class ProviderError(PyLazyError):
    """Raised when an upstream model provider request fails."""


class GenerationError(PyLazyError):
    """Raised when PyLazy cannot turn a model response into usable source code."""


class ValidationError(PyLazyError):
    """Raised when generated source violates PyLazy's validation constraints."""
