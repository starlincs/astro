"""Pipeline working directory and run lifecycle management."""

from __future__ import annotations

import json
import secrets
import shutil
import string
from datetime import UTC, datetime
from pathlib import Path

from astro.pipeline.models import ExecutionMode
from astro.working.manifest import RunManifest, RunStatus

WORKING_DIRNAME = ".working"
MANIFEST_FILENAME = "manifest.json"
INGESTED_DIRNAME = "ingested"
_RUN_ID_LENGTH = 5


class SerialIngestConflictError(RuntimeError):
    """Raised when serial mode blocks a new ingest."""

    def __init__(self, blocking_run_ids: list[str]) -> None:
        self.blocking_run_ids = blocking_run_ids
        joined = ", ".join(blocking_run_ids)
        super().__init__(f"Ingest blocked: incomplete run(s) exist: {joined}")


class RunManager:
    """Manage run directories and manifests under a pipeline working root."""

    def __init__(self, pipeline_dir: Path) -> None:
        self.pipeline_dir = pipeline_dir
        self.working_root = pipeline_dir / WORKING_DIRNAME

    def working_root_for(self, pipeline_dir: Path | None = None) -> Path:
        root = pipeline_dir or self.pipeline_dir
        return root / WORKING_DIRNAME

    def find_incomplete_runs(self) -> list[RunManifest]:
        incomplete_runs: list[RunManifest] = []
        working_root = self.working_root
        if not working_root.is_dir():
            return incomplete_runs

        for run_directory in sorted(working_root.iterdir()):
            if not run_directory.is_dir():
                continue
            manifest_path = run_directory / MANIFEST_FILENAME
            if not manifest_path.is_file():
                incomplete_runs.append(
                    RunManifest(
                        run_id=run_directory.name,
                        pipeline_name="unknown",
                        status=RunStatus.CREATED,
                        execution_mode=ExecutionMode.SERIAL.value,
                        source_directory="",
                        created_at=datetime.now(UTC),
                    )
                )
                continue
            manifest = self.load_manifest(run_directory)
            if manifest.is_incomplete():
                incomplete_runs.append(manifest)
        return incomplete_runs

    def assert_serial_ingest_allowed(self, execution_mode: ExecutionMode) -> None:
        if execution_mode != ExecutionMode.SERIAL:
            return
        blocking = [manifest.run_id for manifest in self.find_incomplete_runs()]
        if blocking:
            raise SerialIngestConflictError(blocking)

    def create_run(
        self,
        *,
        pipeline_name: str,
        execution_mode: ExecutionMode,
        source_directory: Path,
    ) -> tuple[Path, RunManifest]:
        self.working_root.mkdir(parents=True, exist_ok=True)
        run_id = self._generate_run_id()
        run_directory = self.working_root / run_id
        ingest_directory = run_directory / INGESTED_DIRNAME

        try:
            run_directory.mkdir(parents=False, exist_ok=False)
            ingest_directory.mkdir(parents=False, exist_ok=False)
            manifest = RunManifest(
                run_id=run_id,
                pipeline_name=pipeline_name,
                status=RunStatus.CREATED,
                execution_mode=execution_mode.value,
                source_directory=str(source_directory.resolve()),
                created_at=datetime.now(UTC),
            )
            self.save_manifest(run_directory, manifest)
        except Exception:
            shutil.rmtree(run_directory, ignore_errors=True)
            raise
        return run_directory, manifest

    def load_manifest(self, run_directory: Path) -> RunManifest:
        manifest_path = run_directory / MANIFEST_FILENAME
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return RunManifest.model_validate(manifest_data)

    def save_manifest(self, run_directory: Path, manifest: RunManifest) -> None:
        manifest_path = run_directory / MANIFEST_FILENAME
        manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def ingest_directory_for(self, run_directory: Path) -> Path:
        return run_directory / INGESTED_DIRNAME

    def _generate_run_id(self) -> str:
        valid_characters = string.ascii_lowercase + string.digits
        for _ in range(100):
            candidate = "".join(secrets.choice(valid_characters) for _ in range(_RUN_ID_LENGTH))
            if not (self.working_root / candidate).exists():
                return candidate
        raise RuntimeError("Unable to allocate a unique run identifier.")
