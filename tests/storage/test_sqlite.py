"""Storage stub tests."""

from pathlib import Path

from astro.storage import PipelineStore


def test_pipeline_store_default_db_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = PipelineStore()
    assert store.db_path == tmp_path / ".astro" / "stats.db"


def test_pipeline_store_custom_db_path(tmp_path: Path) -> None:
    custom_path = tmp_path / "custom" / "stats.db"
    store = PipelineStore(db_path=custom_path)
    assert store.db_path == custom_path
