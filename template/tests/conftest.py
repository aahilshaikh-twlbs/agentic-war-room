"""Pytest config for the template suite.

Integration tests (cross-process / real-daemon runtime proofs for Feature C) are
marked `@pytest.mark.integration` and SKIPPED by default — they require the
coordination mailbox package on sys.path and spawn real processes. Run them with
`--runintegration` (see docs and the plan §5).
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runintegration", action="store_true", default=False,
        help="run @integration tests (cross-process runtime proofs)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: cross-process/runtime integration test (opt-in)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runintegration"):
        return
    skip = pytest.mark.skip(reason="needs --runintegration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
