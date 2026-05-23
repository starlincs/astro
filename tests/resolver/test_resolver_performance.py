"""Performance tests for canonical ID resolver."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from astro.resolver import CanonicalIdResolver


@pytest.mark.integration
def test_resolve_75k_rows_within_performance_budget(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    resolver = CanonicalIdResolver(
        pipeline_dir,
        "establishments",
        {
            "entry_changed": "*all",
            "address_changed": ["address1", "postcode"],
        },
    )
    data = pl.DataFrame(
        {
            "source_key": [f"file:{index}" for index in range(75_000)],
            "address1": [f"{index} High Street" for index in range(75_000)],
            "postcode": ["AB1 2CD"] * 75_000,
            "owner": ["trust-a"] * 75_000,
        }
    )

    started = time.perf_counter()
    result = resolver.resolve(
        data,
        source_key_column="source_key",
        namespace="establishments",
        run_date=date(2026, 5, 22),
    )
    elapsed = time.perf_counter() - started

    assert result.height == 75_000
    assert result["status"].eq("NEW").all()
    assert elapsed < 5.0
