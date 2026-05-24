"""Pipeline discovery tests."""

from __future__ import annotations

import sys
from pathlib import Path

from astro.pipeline.discovery import (
    discover_pipeline,
    get_pipeline_instance,
    load_pipeline_module,
)


def test_discover_pipeline_returns_path_when_present(pipeline_directory: Path) -> None:
    pipeline_path = discover_pipeline(pipeline_directory)
    assert pipeline_path == pipeline_directory / "pipeline.py"


def test_discover_pipeline_returns_none_when_missing(tmp_path: Path) -> None:
    assert discover_pipeline(tmp_path) is None


def test_load_pipeline_module_imports_user_pipeline(pipeline_directory: Path) -> None:
    module = load_pipeline_module(pipeline_directory)
    assert module is not None
    assert hasattr(module, "pipeline")


def test_get_pipeline_instance_returns_pipeline_object(pipeline_directory: Path) -> None:
    pipeline = get_pipeline_instance(pipeline_directory)
    assert pipeline is not None
    assert pipeline.name == "test-pipeline"


def test_load_pipeline_module_does_not_leak_sys_path(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "pipeline.py"
    pipeline_path.write_text(
        """
from astro import Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.steps import StepContext
import pandera.polars as pa

class DemoFile(AstroFileSpec):
    ingest_name = "demo"

def step(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None

class DemoPipeline(Pipeline):
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="demo",
            source_pattern="demo.csv",
            schema=pa.DataFrameSchema({"id": pa.Column(str)}, strict="filter"),
        ),
    ]
    def configure_steps(self) -> None:
        self.add_step("No-op", step, [DemoFile()])

pipeline = DemoPipeline()
""",
        encoding="utf-8",
    )
    original_path = list(sys.path)
    load_pipeline_module(tmp_path)
    assert sys.path == original_path
