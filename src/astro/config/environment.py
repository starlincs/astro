"""Resolve starlincs data environment directories for pipeline runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENVIRONMENT_LOCAL_FILENAME = "environment.local"
DATA_ENV_VAR = "DATA_ENV"
PAF_ENV_VAR = "PAF_ENV"
DEFAULT_ENVIRONMENT_NAME = "dev"


@dataclass(frozen=True, slots=True)
class DataEnvironment:
    """Paths for one named data environment under ``data/environments/<name>/``."""

    root: Path
    env_file: Path
    name: str

    def sqlite_db(self, pipeline: str) -> Path:
        return self.root / "sqlite" / f"{pipeline}.db"

    @property
    def typesense_data_dir(self) -> Path:
        return self.root / "typesense"


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _read_environment_name(root: Path) -> str:
    env_name = _parse_env_file(root / ".env").get("ENV_NAME", "").strip()
    return env_name or root.name


def _resolve_data_env_root(pipeline_dir: Path) -> Path:
    data_env = os.environ.get(DATA_ENV_VAR, "").strip()
    if data_env:
        return _resolve_path(pipeline_dir, data_env)

    local_file = pipeline_dir / ENVIRONMENT_LOCAL_FILENAME
    if local_file.is_file():
        local_data_env = _parse_env_file(local_file).get(DATA_ENV_VAR, "").strip()
        if local_data_env:
            return _resolve_path(pipeline_dir, local_data_env)

    paf_env = os.environ.get(PAF_ENV_VAR, "").strip()
    if paf_env:
        return (pipeline_dir / "../../data/environments" / paf_env).resolve()

    return (pipeline_dir / f"../../data/environments/{DEFAULT_ENVIRONMENT_NAME}").resolve()


def resolve_data_environment(pipeline_dir: Path) -> DataEnvironment:
    """Resolve the data environment root for a pipeline directory."""
    root = _resolve_data_env_root(pipeline_dir)
    return DataEnvironment(
        root=root,
        env_file=root / ".env",
        name=_read_environment_name(root),
    )


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a dotenv file without overriding existing env vars."""
    for key, value in _parse_env_file(path).items():
        if key not in os.environ:
            os.environ[key] = value


def load_data_environment_env(data_env: DataEnvironment) -> None:
    """Load Typesense and related settings from the environment ``.env`` file."""
    load_env_file(data_env.env_file)
