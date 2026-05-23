"""Shared pytest fixtures for Astro tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pipeline_directory(tmp_path: Path) -> Path:
    pipeline_path = tmp_path / "pipeline.py"
    pipeline_path.write_text(
        """
from pathlib import Path

import polars as pl

from astro import IngestedSource, Pipeline


class TestPipeline(Pipeline):
    name = "test-pipeline"

    def ingest(self, path: Path) -> list[IngestedSource]:
        return [IngestedSource(path=path, data=pl.DataFrame({"value": [1]}))]

    def transform(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        return data

    def validate(self, data: pl.DataFrame, source: Path) -> pl.DataFrame:
        return data


pipeline = TestPipeline()
""",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("id,name\n1,alpha\n", encoding="utf-8")
    return csv_path


@pytest.fixture
def csv_directory(tmp_path: Path) -> Path:
    (tmp_path / "a.csv").write_text("id\n1\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("code\nx\n", encoding="utf-8")
    return tmp_path
