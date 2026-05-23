"""SQLite-backed store for pipeline run statistics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from astro.working.manifest import IngestedFileRecord


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    pipeline_name: str
    status: str
    source_directory: str
    created_at: str
    ingested_at: str | None


class PipelineStore:
    """Local persistent store for pipeline statistics."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path.cwd() / ".astro" / "stats.db"

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_directory TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ingested_at TEXT
                );

                CREATE TABLE IF NOT EXISTS ingest_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    parquet_path TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    source_size_bytes INTEGER NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    def record_run(
        self,
        *,
        run_id: str,
        pipeline_name: str,
        status: str,
        source_directory: str,
        created_at: datetime,
        ingested_at: datetime | None = None,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, pipeline_name, status, source_directory, created_at, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    pipeline_name = excluded.pipeline_name,
                    status = excluded.status,
                    source_directory = excluded.source_directory,
                    created_at = excluded.created_at,
                    ingested_at = excluded.ingested_at
                """,
                (
                    run_id,
                    pipeline_name,
                    status,
                    source_directory,
                    created_at.isoformat(),
                    ingested_at.isoformat() if ingested_at else None,
                ),
            )

    def record_ingest_files(
        self,
        run_id: str,
        files: list[IngestedFileRecord],
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("DELETE FROM ingest_files WHERE run_id = ?", (run_id,))
            connection.executemany(
                """
                INSERT INTO ingest_files (
                    run_id,
                    file_name,
                    source_path,
                    parquet_path,
                    row_count,
                    column_count,
                    source_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        file_record.name,
                        file_record.source_path,
                        file_record.parquet_path,
                        file_record.row_count,
                        file_record.column_count,
                        file_record.source_size_bytes,
                    )
                    for file_record in files
                ],
            )

    def list_runs(self, pipeline_name: str | None = None) -> list[dict[str, object]]:
        self.initialize()
        with self._connect() as connection:
            if pipeline_name is None:
                rows = connection.execute(
                    "SELECT run_id, pipeline_name, status, source_directory, "
                    "created_at, ingested_at FROM runs ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT run_id, pipeline_name, status, source_directory, "
                    "created_at, ingested_at FROM runs "
                    "WHERE pipeline_name = ? ORDER BY created_at DESC",
                    (pipeline_name,),
                ).fetchall()
        return [
            {
                "run_id": row[0],
                "pipeline_name": row[1],
                "status": row[2],
                "source_directory": row[3],
                "created_at": row[4],
                "ingested_at": row[5],
            }
            for row in rows
        ]

    def cleanup(self, pipeline_name: str | None = None) -> None:
        self.initialize()
        with self._connect() as connection:
            if pipeline_name is None:
                connection.execute("DELETE FROM ingest_files")
                connection.execute("DELETE FROM runs")
            else:
                run_ids = connection.execute(
                    "SELECT run_id FROM runs WHERE pipeline_name = ?",
                    (pipeline_name,),
                ).fetchall()
                for (run_id,) in run_ids:
                    connection.execute("DELETE FROM ingest_files WHERE run_id = ?", (run_id,))
                connection.execute("DELETE FROM runs WHERE pipeline_name = ?", (pipeline_name,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
