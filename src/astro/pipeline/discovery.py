"""Discover and load pipeline.py from external project directories."""

import importlib.util
from pathlib import Path
from types import ModuleType

from astro.pipeline.base import Pipeline

PIPELINE_FILENAME = "pipeline.py"


def discover_pipeline(directory: Path | None = None) -> Path | None:
    """Return the path to pipeline.py if it exists in the given directory."""
    search_dir = directory or Path.cwd()
    pipeline_path = search_dir / PIPELINE_FILENAME
    if pipeline_path.is_file():
        return pipeline_path
    return None


def load_pipeline_module(directory: Path | None = None) -> ModuleType | None:
    """Import pipeline.py from the given directory as a Python module."""
    pipeline_path = discover_pipeline(directory)
    if pipeline_path is None:
        return None

    spec = importlib.util.spec_from_file_location("astro_user_pipeline", pipeline_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_pipeline_instance(directory: Path | None = None) -> Pipeline | None:
    """Return the Pipeline instance exported by pipeline.py, if present."""
    module = load_pipeline_module(directory)
    if module is None:
        return None

    pipeline = getattr(module, "pipeline", None)
    if isinstance(pipeline, Pipeline):
        return pipeline
    return None
