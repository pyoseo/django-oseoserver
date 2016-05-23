"""pytest configuration file."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "unit: run only unit tests"
    )
    config.addinivalue_line(
        "markers",
        "functional: run only functional tests"
    )
