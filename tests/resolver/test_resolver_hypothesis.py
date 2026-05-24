"""Hypothesis tests for canonical ID resolver."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import polars as pl
from hypothesis import given, settings
from hypothesis import strategies as st

from astro.resolver import CanonicalIdResolver


@given(
    st.lists(
        st.fixed_dictionaries(
            {
                "source_key": st.text(min_size=1, max_size=12, alphabet="abc123"),
                "name": st.text(min_size=1, max_size=12, alphabet="xyz789"),
            }
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda row: row["source_key"],
    )
)
@settings(max_examples=25, deadline=None)
def test_resolver_assigns_stable_ids_for_repeated_keys(rows: list[dict[str, str]]) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        pipeline_dir = Path(temporary_directory) / "pipeline"
        pipeline_dir.mkdir()
        resolver = CanonicalIdResolver(
            pipeline_dir=pipeline_dir,
            name="entities",
            hash_groups={"entry_changed": ["name"]},
        )
        dataframe = pl.DataFrame(rows)
        run_date = date(2026, 5, 24)

        first = resolver.resolve(
            dataframe,
            source_key_column="source_key",
            namespace="entities",
            run_date=run_date,
        )
        second = resolver.resolve(
            dataframe,
            source_key_column="source_key",
            namespace="entities",
            run_date=run_date,
        )

        assert first["canonical_id"].to_list() == second["canonical_id"].to_list()
        assert (second["status"] == "UNCHANGED").all()
