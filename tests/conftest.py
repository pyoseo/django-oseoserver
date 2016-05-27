"""pytest configuration file."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "unit: run only unit tests"
    )
    config.addinivalue_line(
        "markers",
        "integration: run only integration tests"
    )
