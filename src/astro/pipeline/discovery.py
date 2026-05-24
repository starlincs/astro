"""Discover and load pipeline.py from external project directories."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections.abc import Iterator
from contextlib import contextmanager
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


def _module_name_for(pipeline_path: Path) -> str:
    digest = hashlib.sha256(str(pipeline_path.resolve()).encode()).hexdigest()[:16]
    return f"astro_user_pipeline_{digest}"


@contextmanager
def _pipeline_import_path(pipeline_directory: str) -> Iterator[None]:
    added = False
    if pipeline_directory not in sys.path:
        sys.path.insert(0, pipeline_directory)
        added = True
    try:
        yield
    finally:
        if added:
            sys.path.remove(pipeline_directory)


def load_pipeline_module(directory: Path | None = None) -> ModuleType | None:
    """Import pipeline.py from the given directory as a Python module."""
    pipeline_path = discover_pipeline(directory)
    if pipeline_path is None:
        return None

    module_name = _module_name_for(pipeline_path)
    spec = importlib.util.spec_from_file_location(module_name, pipeline_path)
    if spec is None or spec.loader is None:
        return None

    pipeline_directory = str(pipeline_path.parent.resolve())
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        with _pipeline_import_path(pipeline_directory):
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
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
