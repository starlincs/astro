"""Smoke tests for package import."""

import astro
from astro import (
    CanonicalIdResolver,
    FilterFn,
    Pipeline,
    StatisticsRecorder,
    StatScope,
)


def test_package_version() -> None:
    assert astro.__version__ == "1.1.0"


def test_public_exports() -> None:
    assert CanonicalIdResolver is not None
    assert Pipeline is not None
    assert FilterFn is not None
    assert StatScope is not None
    assert StatisticsRecorder is not None
