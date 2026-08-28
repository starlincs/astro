"""Chunked CSV/JSONL export helpers for pipeline SQLite and Typesense artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import polars as pl

MANIFEST_FILENAME = "manifest.json"
ConcatHow = Literal["vertical", "vertical_relaxed"]


@dataclass(frozen=True)
class ExportFileEntry:
    """Metadata for one exported chunk file."""

    filename: str
    size_bytes: int
    row_count: int | None = None
    document_count: int | None = None

    def as_dict(self) -> dict[str, int | str]:
        payload: dict[str, int | str] = {
            "filename": self.filename,
            "size_bytes": self.size_bytes,
        }
        if self.row_count is not None:
            payload["row_count"] = self.row_count
        if self.document_count is not None:
            payload["document_count"] = self.document_count
        return payload


class CsvChunkWriter:
    """Write SQLite-importable CSV files in fixed-size chunks."""

    def __init__(
        self,
        output_directory: Path,
        *,
        columns: tuple[str, ...],
        chunk_size: int,
        file_prefix: str,
        concat_how: ConcatHow = "vertical_relaxed",
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")

        self.output_directory = output_directory
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.columns = columns
        self.chunk_size = chunk_size
        self.file_prefix = file_prefix
        self.concat_how = concat_how

        self._buffer_frames: list[pl.DataFrame] = []
        self._buffer_rows = 0
        self._current_file_index = 0
        self._total_rows = 0
        self._files: list[ExportFileEntry] = []

    @property
    def rows_written(self) -> int:
        return self._total_rows + self._buffer_rows

    @property
    def files_written(self) -> int:
        return len(self._files)

    @property
    def latest_file_row_count(self) -> int:
        if not self._files:
            return 0
        return int(self._files[-1].row_count or 0)

    @property
    def files(self) -> tuple[ExportFileEntry, ...]:
        return tuple(self._files)

    def write_batch(self, batch: pl.DataFrame) -> None:
        missing_columns = [column for column in self.columns if column not in batch.columns]
        if missing_columns:
            raise ValueError(f"Batch is missing columns: {missing_columns}")

        selected = batch.select(list(self.columns))
        if selected.is_empty():
            return

        self._buffer_frames.append(selected)
        self._buffer_rows += selected.height
        while self._buffer_rows >= self.chunk_size:
            self._flush_buffer()

    def finalize(self) -> tuple[int, tuple[ExportFileEntry, ...]]:
        if self._buffer_rows:
            self._flush_buffer()
        return self._total_rows, tuple(self._files)

    def _flush_buffer(self) -> None:
        if not self._buffer_frames:
            return

        combined = pl.concat(self._buffer_frames, how=self.concat_how)
        if combined.height > self.chunk_size:
            to_write = combined.head(self.chunk_size)
            remainder = combined.slice(self.chunk_size)
            self._buffer_frames = [remainder]
            self._buffer_rows = remainder.height
        else:
            to_write = combined
            self._buffer_frames = []
            self._buffer_rows = 0

        self._current_file_index += 1
        filename = f"{self.file_prefix}-{self._current_file_index:05d}.csv"
        output_path = self.output_directory / filename
        to_write.write_csv(output_path)

        row_count = to_write.height
        self._total_rows += row_count
        self._files.append(
            ExportFileEntry(
                filename=filename,
                row_count=row_count,
                size_bytes=output_path.stat().st_size,
            )
        )


class JsonlChunkWriter:
    """Write Typesense JSONL export files in fixed-size chunks."""

    def __init__(
        self,
        output_directory: Path,
        *,
        chunk_size: int,
        file_prefix: str,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")

        self.output_directory = output_directory
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size
        self.file_prefix = file_prefix

        self._buffer: list[dict[str, object]] = []
        self._current_file_index = 0
        self._total_documents = 0
        self._files: list[ExportFileEntry] = []

    @property
    def documents_written(self) -> int:
        return self._total_documents + len(self._buffer)

    @property
    def files_written(self) -> int:
        return len(self._files)

    @property
    def latest_file_document_count(self) -> int:
        if not self._files:
            return 0
        return int(self._files[-1].document_count or 0)

    @property
    def files(self) -> tuple[ExportFileEntry, ...]:
        return tuple(self._files)

    def write_documents(self, documents: Iterable[dict[str, object]]) -> None:
        for document in documents:
            self._buffer.append(document)
            if len(self._buffer) >= self.chunk_size:
                self._flush_buffer()

    def finalize(self) -> tuple[int, tuple[ExportFileEntry, ...]]:
        if self._buffer:
            self._flush_buffer()
        return self._total_documents, tuple(self._files)

    def _flush_buffer(self) -> None:
        if not self._buffer:
            return

        self._current_file_index += 1
        filename = f"{self.file_prefix}-{self._current_file_index:05d}.jsonl"
        output_path = self.output_directory / filename

        with output_path.open("w", encoding="utf-8") as handle:
            for document in self._buffer:
                handle.write(json.dumps(document, separators=(",", ":"), ensure_ascii=False))
                handle.write("\n")

        document_count = len(self._buffer)
        self._total_documents += document_count
        self._files.append(
            ExportFileEntry(
                filename=filename,
                document_count=document_count,
                size_bytes=output_path.stat().st_size,
            )
        )
        self._buffer.clear()


def write_export_manifest(output_directory: Path, payload: dict[str, object]) -> None:
    """Write export manifest metadata alongside chunked export files."""
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def export_file_dicts(files: Iterable[ExportFileEntry]) -> list[dict[str, int | str]]:
    """Serialize export file entries for manifest JSON payloads."""
    return [entry.as_dict() for entry in files]
