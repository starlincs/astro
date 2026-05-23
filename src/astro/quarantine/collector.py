"""Step-scoped quarantine collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from astro.pipeline.files import AstroFile
from astro.quarantine.store import QuarantineStore


@dataclass
class StepQuarantine:
    """Collect quarantined rows for the current pipeline step."""

    run_directory: Path
    step_id: str
    _store: QuarantineStore = field(init=False)
    _touched_paths: set[Path] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._store = QuarantineStore(self.run_directory)

    def quarantine_rows(self, file: AstroFile, rows: pl.DataFrame, *, reason: str) -> None:
        path = self._store.quarantine_path(self.step_id, file.spec.__class__.ingest_name)
        self._store.append_rows(path, rows, reason=reason)
        self._touched_paths.add(path)

    def quarantine_row(self, file: AstroFile, row: dict[str, object], *, reason: str) -> None:
        self.quarantine_rows(file, pl.DataFrame([row]), reason=reason)

    @property
    def has_quarantined_rows(self) -> bool:
        return any(self._store.has_rows(path) for path in self._touched_paths)
