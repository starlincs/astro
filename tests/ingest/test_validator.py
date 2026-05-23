"""Ingest validator tests."""

from __future__ import annotations

from pathlib import Path

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
