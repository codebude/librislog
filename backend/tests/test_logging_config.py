"""Tests for app.logging_config module."""

import logging
from collections.abc import Generator

import pytest

from app.logging_config import configure_logging


@pytest.fixture(autouse=True)
def cleanup_handlers() -> Generator[None, None, None]:
    """Remove all 'app' logger handlers after each test."""
    yield
    logger = logging.getLogger("app")
    logger.handlers.clear()


def test_configure_logging_twice_updates_level() -> None:
    """Second call updates the existing handler's level instead of adding a duplicate."""
    configure_logging("DEBUG")
    logger = logging.getLogger("app")
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG

    configure_logging("WARNING")
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.WARNING
