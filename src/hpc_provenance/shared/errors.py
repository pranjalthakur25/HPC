"""Errors raised outside the domain layer (configuration, CLI, etc.)."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for errors raised by the application/config/presentation layers."""


class ConfigurationError(ApplicationError):
    """Raised when ``Settings`` or ``Container`` cannot resolve a valid configuration."""
