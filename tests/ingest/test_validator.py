"""Ingest validator tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import pytest

from astro.ingest.validator import IngestValidationError, match_ingest_files
from astro.pipeline import IngestFileSpec


def test_match_ingest_files_returns_one_match_per_spec(
    sample_ingest_spec: IngestFileSpec,
    source_directory: Path,
) -> None:
    matches = match_ingest_files(source_directory, [sample_ingest_spec])
    assert len(matches) == 1
    assert matches[0].spec.name == "establishments"
    assert matches[0].source_path.name == "edubase20260522.csv"


def test_match_ingest_files_errors_when_required_file_missing(
    sample_ingest_spec: IngestFileSpec,
    tmp_path: Path,
) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(IngestValidationError, match="No source file matched"):
        match_ingest_files(empty_dir, [sample_ingest_spec])


def test_match_ingest_files_errors_on_unexpected_extra_file(
    sample_ingest_spec: IngestFileSpec,
    source_directory: Path,
) -> None:
    (source_directory / "extra.csv").write_text("x\n", encoding="utf-8")

    with pytest.raises(IngestValidationError, match="Unexpected files"):
        match_ingest_files(source_directory, [sample_ingest_spec])


def test_match_ingest_files_errors_on_subdirectory(
    sample_ingest_spec: IngestFileSpec,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "nested").mkdir()

    with pytest.raises(IngestValidationError, match="files only"):
        match_ingest_files(source_dir, [sample_ingest_spec])


def _optional_spec(name: str, pattern: str) -> IngestFileSpec:
    return IngestFileSpec(
        name=name,
        source_pattern=pattern,
        schema=pa.DataFrameSchema({"id": pa.Column(str)}, strict="filter"),
        optional=True,
    )


def test_match_ingest_files_skips_absent_optional_spec(
    sample_ingest_spec: IngestFileSpec,
    source_directory: Path,
) -> None:
    optional = _optional_spec("extras", "extras*.csv")
    matches = match_ingest_files(source_directory, [sample_ingest_spec, optional])

    assert len(matches) == 1
    assert matches[0].spec.name == "establishments"


def test_match_ingest_files_matches_present_optional_spec(
    sample_ingest_spec: IngestFileSpec,
    source_directory: Path,
) -> None:
    optional = _optional_spec("extras", "extras*.csv")
    (source_directory / "extras20260522.csv").write_text("id\n1\n", encoding="utf-8")

    matches = match_ingest_files(source_directory, [sample_ingest_spec, optional])

    assert len(matches) == 2
    assert {match.spec.name for match in matches} == {"establishments", "extras"}


def test_match_ingest_files_all_optional_requires_at_least_one_match(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    optional_a = _optional_spec("alpha", "alpha*.csv")
    optional_b = _optional_spec("beta", "beta*.csv")

    with pytest.raises(IngestValidationError, match="At least one ingest file"):
        match_ingest_files(source_dir, [optional_a, optional_b])


def test_match_ingest_files_all_optional_one_present(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "alpha.csv").write_text("id\n1\n", encoding="utf-8")
    optional_a = _optional_spec("alpha", "alpha*.csv")
    optional_b = _optional_spec("beta", "beta*.csv")

    matches = match_ingest_files(source_dir, [optional_a, optional_b])

    assert len(matches) == 1
    assert matches[0].spec.name == "alpha"


def test_match_ingest_files_errors_when_required_missing_with_optional_present(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "extras.csv").write_text("id\n1\n", encoding="utf-8")
    required = IngestFileSpec(
        name="establishments",
        source_pattern="edubase*.csv",
        schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
    )
    optional = _optional_spec("extras", "extras*.csv")

    with pytest.raises(IngestValidationError, match="No source file matched"):
        match_ingest_files(source_dir, [required, optional])
