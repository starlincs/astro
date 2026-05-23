"""Shared pytest fixtures for Astro tests."""

from __future__ import annotations

from pathlib import Path

import pandera.polars as pa
import pytest
from typer.testing import CliRunner

from astro.pipeline import IngestFileSpec


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_ingest_spec() -> IngestFileSpec:
    return IngestFileSpec(
        name="establishments",
        source_pattern="edubase*.csv",
        schema=pa.DataFrameSchema(
            {
                "URN": pa.Column(str),
                "EstablishmentName": pa.Column(str),
            },
            strict="filter",
        ),
    )


@pytest.fixture
def pipeline_directory(tmp_path: Path, sample_ingest_spec: IngestFileSpec) -> Path:
    pipeline_path = tmp_path / "pipeline.py"
    pipeline_path.write_text(
        """
from astro import Pipeline
from astro.pipeline import AstroFileSpec, ExecutionMode, IngestFileSpec
from astro.pipeline.steps import StepContext
from astro.pipeline.files import AstroFile
import pandera.polars as pa


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_noop(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


class TestPipeline(Pipeline):
    name = "test-pipeline"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema(
                {
                    "URN": pa.Column(str),
                    "EstablishmentName": pa.Column(str),
                },
                strict="filter",
            ),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("No-op", step_noop, [EstablishmentsFile()])


pipeline = TestPipeline()
""",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase20260522.csv").write_text(
        "URN,EstablishmentName\n100001,Example School\n",
        encoding="utf-8",
    )
    return source_dir


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
