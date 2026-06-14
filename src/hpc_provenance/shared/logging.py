"""Centralized logging configuration."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging for the application.

    Called once, from the CLI entry point, before any use case runs.

    Implementation notes:
        - Use a single structured formatter (e.g. key=value or JSON) so
          provenance generation can run unattended in Slurm job
          scripts/epilogs and still produce parseable logs.
    """
    raise NotImplementedError
