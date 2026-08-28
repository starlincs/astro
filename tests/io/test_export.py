"""Tests for chunked CSV/JSONL export helpers."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from astro.io import CsvChunkWriter, JsonlChunkWriter, export_file_dicts, write_export_manifest
from astro.io.export import MANIFEST_FILENAME, ExportFileEntry


def test_csv_chunk_writer_flushes_and_manifest(tmp_path: Path) -> None:
    writer = CsvChunkWriter(
        tmp_path,
        columns=("id", "name"),
        chunk_size=2,
        file_prefix="items",
    )
    writer.write_batch(pl.DataFrame({"id": ["1", "2"], "name": ["a", "b"]}))
    writer.write_batch(pl.DataFrame({"id": ["3"], "name": ["c"]}))

    total_rows, files = writer.finalize()
    assert total_rows == 3
    assert len(files) == 2
    assert files[0].row_count == 2
    assert files[1].row_count == 1
    assert (tmp_path / "items-00001.csv").is_file()


def test_jsonl_chunk_writer_flushes(tmp_path: Path) -> None:
    writer = JsonlChunkWriter(tmp_path, chunk_size=2, file_prefix="docs")
    writer.write_documents([{"id": "1"}, {"id": "2"}, {"id": "3"}])

    total_documents, files = writer.finalize()
    assert total_documents == 3
    assert len(files) == 2


def test_write_export_manifest(tmp_path: Path) -> None:
    write_export_manifest(tmp_path, {"table_name": "items", "total_rows": 0, "files": []})
    payload = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert payload["table_name"] == "items"


def test_export_file_dicts_includes_optional_counts() -> None:
    files = (
        ExportFileEntry(filename="items-00001.csv", size_bytes=10, row_count=2),
        ExportFileEntry(filename="docs-00001.jsonl", size_bytes=20, document_count=3),
    )

    assert export_file_dicts(files) == [
        {"filename": "items-00001.csv", "size_bytes": 10, "row_count": 2},
        {"filename": "docs-00001.jsonl", "size_bytes": 20, "document_count": 3},
    ]


def test_csv_chunk_writer_rejects_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        CsvChunkWriter(tmp_path, columns=("id",), chunk_size=0, file_prefix="items")

    writer = CsvChunkWriter(tmp_path, columns=("id",), chunk_size=2, file_prefix="items")
    with pytest.raises(ValueError, match="missing columns"):
        writer.write_batch(pl.DataFrame({"name": ["a"]}))


def test_csv_chunk_writer_skips_empty_batch(tmp_path: Path) -> None:
    writer = CsvChunkWriter(tmp_path, columns=("id",), chunk_size=2, file_prefix="items")
    writer.write_batch(pl.DataFrame({"id": []}))
    total_rows, files = writer.finalize()
    assert total_rows == 0
    assert files == ()


def test_jsonl_chunk_writer_writes_valid_jsonl(tmp_path: Path) -> None:
    writer = JsonlChunkWriter(tmp_path, chunk_size=2, file_prefix="docs")
    writer.write_documents([{"id": "1", "name": "café"}, {"id": "2"}])

    total_documents, files = writer.finalize()
    assert total_documents == 2
    assert len(files) == 1
    lines = (tmp_path / "docs-00001.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == {"id": "1", "name": "café"}
    assert json.loads(lines[1]) == {"id": "2"}


def test_jsonl_chunk_writer_rejects_invalid_chunk_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        JsonlChunkWriter(tmp_path, chunk_size=-1, file_prefix="docs")
