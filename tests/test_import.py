"""Smoke tests for package import."""

import astro
from astro import CanonicalIdResolver, IngestedSource, Pipeline


def test_package_version() -> None:
    assert astro.__version__ == "0.1.0"


def test_public_exports() -> None:
    assert CanonicalIdResolver is not None
    assert IngestedSource is not None
    assert Pipeline is not None
