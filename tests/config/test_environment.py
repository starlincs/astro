"""Tests for data environment resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from astro.config.environment import (
    DataEnvironment,
    load_data_environment_env,
    resolve_data_environment,
)


def test_resolve_from_environment_local(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    env_root = tmp_path / "environments" / "staging"
    env_root.mkdir(parents=True)
    (pipeline_dir / "environment.local").write_text(
        f"DATA_ENV={env_root}\n",
        encoding="utf-8",
    )

    data_env = resolve_data_environment(pipeline_dir)

    assert data_env.root == env_root.resolve()
    assert data_env.env_file == env_root / ".env"
    assert data_env.name == "staging"


def test_resolve_data_env_env_var_overrides_local_file(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    local_root = tmp_path / "local-env"
    override_root = tmp_path / "override-env"
    local_root.mkdir()
    override_root.mkdir()
    (pipeline_dir / "environment.local").write_text(
        f"DATA_ENV={local_root}\n",
        encoding="utf-8",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("DATA_ENV", str(override_root))
        data_env = resolve_data_environment(pipeline_dir)

    assert data_env.root == override_root.resolve()


def test_resolve_relative_data_env_from_pipeline_dir(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipelines" / "gias"
    pipeline_dir.mkdir(parents=True)
    env_root = tmp_path / "data" / "environments" / "dev"
    env_root.mkdir(parents=True)
    (pipeline_dir / "environment.local").write_text(
        "DATA_ENV=../../data/environments/dev\n",
        encoding="utf-8",
    )

    data_env = resolve_data_environment(pipeline_dir)

    assert data_env.root == env_root.resolve()


def test_resolve_default_dev_environment(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipelines" / "gias"
    pipeline_dir.mkdir(parents=True)
    expected = (pipeline_dir / "../../data/environments/dev").resolve()

    data_env = resolve_data_environment(pipeline_dir)

    assert data_env.root == expected
    assert data_env.name == "dev"


def test_resolve_paf_env_fallback(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipelines" / "gias"
    pipeline_dir.mkdir(parents=True)
    expected = (pipeline_dir / "../../data/environments/staging").resolve()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("DATA_ENV", raising=False)
        monkeypatch.setenv("PAF_ENV", "staging")
        data_env = resolve_data_environment(pipeline_dir)

    assert data_env.root == expected
    assert data_env.name == "staging"


def test_sqlite_db_paths(tmp_path: Path) -> None:
    root = tmp_path / "environments" / "dev"
    data_env = DataEnvironment(root=root, env_file=root / ".env", name="dev")

    assert data_env.sqlite_db("paf") == root / "sqlite" / "paf.db"
    assert data_env.sqlite_db("gias") == root / "sqlite" / "gias.db"
    assert data_env.typesense_data_dir == root / "typesense"


def test_load_data_environment_env_does_not_override_existing(tmp_path: Path) -> None:
    env_root = tmp_path / "dev"
    env_root.mkdir()
    (env_root / ".env").write_text(
        "TYPESENSE_API_KEY=from-file\nTYPESENSE_HOST=http://example:8108\n",
        encoding="utf-8",
    )
    data_env = DataEnvironment(root=env_root, env_file=env_root / ".env", name="dev")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("TYPESENSE_API_KEY", "existing")
        monkeypatch.delenv("TYPESENSE_HOST", raising=False)
        load_data_environment_env(data_env)
        assert os.environ["TYPESENSE_API_KEY"] == "existing"
        assert os.environ["TYPESENSE_HOST"] == "http://example:8108"


def test_environment_name_from_env_file(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    env_root = tmp_path / "environments" / "custom-dir"
    env_root.mkdir(parents=True)
    (env_root / ".env").write_text("ENV_NAME=production\n", encoding="utf-8")
    (pipeline_dir / "environment.local").write_text(
        f"DATA_ENV={env_root}\n",
        encoding="utf-8",
    )

    data_env = resolve_data_environment(pipeline_dir)

    assert data_env.name == "production"
