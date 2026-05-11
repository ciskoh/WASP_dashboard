import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: requires credentials and network access"
    )
