"""Pipeline discovery tests."""

from __future__ import annotations

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
