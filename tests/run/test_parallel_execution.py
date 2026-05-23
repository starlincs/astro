"""Parallel run step execution tests."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from astro.ingest.service import IngestService
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec, StepExecutionMode
from astro.pipeline.steps import StepContext
from astro.run.service import RunService
from astro.working.manifest import RunStatus, StepRunStatus
from astro.working.run_manager import RunManager


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


class EstablishmentsAFile(AstroFileSpec):
    ingest_name = "establishments_a"


class EstablishmentsBFile(AstroFileSpec):
    ingest_name = "establishments_b"


_overlap_detected = threading.Event()
_active_step_count = 0
_active_step_lock = threading.Lock()
_execution_log: list[tuple[str, str]] = []
_execution_log_lock = threading.Lock()
_merge_ran = threading.Event()
_parent_a_done = threading.Event()
_parent_b_done = threading.Event()
_after_failure_ran = threading.Event()


def _track_parallel_entry(step_id: str) -> None:
    global _active_step_count
    with _active_step_lock:
        _active_step_count += 1
        if _active_step_count >= 2:
            _overlap_detected.set()
    time.sleep(0.2)
    with _active_step_lock:
        _active_step_count -= 1


def step_branch_a(_ctx: StepContext, _files: list[AstroFile]) -> None:
    _track_parallel_entry("branch-a")


def step_branch_b(_ctx: StepContext, _files: list[AstroFile]) -> None:
    _track_parallel_entry("branch-b")


def step_parent_a(_ctx: StepContext, _files: list[AstroFile]) -> None:
    time.sleep(0.1)
    _parent_a_done.set()


def step_parent_b(_ctx: StepContext, _files: list[AstroFile]) -> None:
    time.sleep(0.1)
    _parent_b_done.set()


def step_merge(_ctx: StepContext, _files: list[AstroFile]) -> None:
    if not _parent_a_done.is_set() or not _parent_b_done.is_set():
        raise AssertionError("Merge ran before both parent steps completed")
    _merge_ran.set()


def step_touch_shared_file(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    step_id = _ctx.step_id
    with _execution_log_lock:
        _execution_log.append((step_id, "start"))
    time.sleep(0.15)
    file.save_in_place(file.load())
    with _execution_log_lock:
        _execution_log.append((step_id, "end"))


def step_fail(_ctx: StepContext, _files: list[AstroFile]) -> None:
    raise RuntimeError("parallel step failed")


def step_slow(_ctx: StepContext, _files: list[AstroFile]) -> None:
    time.sleep(0.3)


def step_after_failure(_ctx: StepContext, _files: list[AstroFile]) -> None:
    _after_failure_ran.set()


class ParallelIngestSpec(Pipeline):
    name = "parallel-ingest-spec"
    execution_mode = ExecutionMode.PARALLEL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema(
                {
                    "URN": pa.Column(str),
                    "EstablishmentName": pa.Column(str),
                },
                strict="filter",
            ),
        ),
    ]


class ParallelRootPipeline(ParallelIngestSpec):
    name = "parallel-root"
    step_execution_mode = StepExecutionMode.PARALLEL
    max_parallel_workers = 2
    ingest_files = [
        IngestFileSpec(
            name="establishments_a",
            source_pattern="edubase_a*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
        IngestFileSpec(
            name="establishments_b",
            source_pattern="edubase_b*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("Branch A", step_branch_a, [EstablishmentsAFile()])
        self.add_step("Branch B", step_branch_b, [EstablishmentsBFile()])


class SerialRootPipeline(ParallelRootPipeline):
    name = "serial-root"
    step_execution_mode = StepExecutionMode.SERIAL


class ParallelMergePipeline(ParallelIngestSpec):
    name = "parallel-merge"
    step_execution_mode = StepExecutionMode.PARALLEL
    max_parallel_workers = 2

    def configure_steps(self) -> None:
        self.add_step("Parent A", step_parent_a, [EstablishmentsFile()])
        self.add_step("Parent B", step_parent_b, [EstablishmentsFile()])
        self.add_step(
            "Merge",
            step_merge,
            [EstablishmentsFile()],
            depends_on=["parent-a", "parent-b"],
        )


class ParallelSharedFilePipeline(ParallelIngestSpec):
    name = "parallel-shared-file"
    step_execution_mode = StepExecutionMode.PARALLEL
    max_parallel_workers = 2

    def configure_steps(self) -> None:
        self.add_step("Touch A", step_touch_shared_file, [EstablishmentsFile()])
        self.add_step("Touch B", step_touch_shared_file, [EstablishmentsFile()])


class ParallelFailurePipeline(ParallelIngestSpec):
    name = "parallel-failure"
    step_execution_mode = StepExecutionMode.PARALLEL
    max_parallel_workers = 2

    def configure_steps(self) -> None:
        self.add_step("Fail", step_fail, [EstablishmentsFile()])
        self.add_step("Slow", step_slow, [EstablishmentsFile()])
        self.add_step(
            "After failure",
            step_after_failure,
            [EstablishmentsFile()],
            depends_on=["fail"],
        )


class ParallelQuarantinePipeline(ParallelIngestSpec):
    name = "parallel-quarantine"
    step_execution_mode = StepExecutionMode.PARALLEL
    max_parallel_workers = 2

    def configure_steps(self) -> None:
        self.add_step("Quarantine bad rows", _step_quarantine_one_row, [EstablishmentsFile()])
        self.add_step(
            "Validate processed",
            _step_validate_processed,
            [EstablishmentsFile()],
            depends_on=["quarantine-bad-rows"],
        )


def _step_quarantine_one_row(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load()
    bad_rows = dataframe.filter(pl.col("URN") == "999")
    good_rows = dataframe.filter(pl.col("URN") != "999")
    if bad_rows.height:
        ctx.quarantine.quarantine_rows(file, bad_rows, reason="invalid urn")
    file.save_to("processed", "establishments.parquet", good_rows)


def _step_validate_processed(_ctx: StepContext, files: list[AstroFile]) -> None:
    files[0].load()


@pytest.fixture
def run_source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase20260522.csv").write_text(
        "URN,EstablishmentName\n100001,Example School\n999,Bad School\n",
        encoding="utf-8",
    )
    return source_dir


@pytest.fixture
def parallel_root_source_directory(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "edubase_a20260522.csv").write_text("URN\n100001\n", encoding="utf-8")
    (source_dir / "edubase_b20260522.csv").write_text("URN\n200002\n", encoding="utf-8")
    return source_dir


@pytest.fixture(autouse=True)
def reset_parallel_test_state() -> None:
    global _active_step_count
    _overlap_detected.clear()
    _merge_ran.clear()
    _parent_a_done.clear()
    _parent_b_done.clear()
    _after_failure_ran.clear()
    _active_step_count = 0
    _execution_log.clear()


def _ingest(pipeline_dir: Path, pipeline: Pipeline, source_directory: Path):
    ingest_result = IngestService(pipeline_dir, pipeline).ingest(source_directory)
    manifest = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    return ingest_result, manifest


def test_parallel_run_executes_independent_steps_concurrently(
    tmp_path: Path,
    parallel_root_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = ParallelRootPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, parallel_root_source_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    assert _overlap_detected.is_set()
    completed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert completed.status == RunStatus.COMPLETED


def test_serial_run_does_not_execute_root_steps_concurrently(
    tmp_path: Path,
    parallel_root_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = SerialRootPipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, parallel_root_source_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    assert not _overlap_detected.is_set()


def test_parallel_run_waits_for_dependencies(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = ParallelMergePipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    assert _merge_ran.is_set()


def test_parallel_run_serializes_shared_ingest_file_access(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = ParallelSharedFilePipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    starts = [index for index, (_, event) in enumerate(_execution_log) if event == "start"]
    ends = [index for index, (_, event) in enumerate(_execution_log) if event == "end"]
    assert len(starts) == 2
    assert len(ends) == 2
    for index in range(len(_execution_log) - 1):
        if _execution_log[index][1] == "start" and _execution_log[index + 1][1] == "start":
            pytest.fail("shared ingest file steps overlapped")


def test_parallel_run_stops_on_hard_failure(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = ParallelFailurePipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    with pytest.raises(RuntimeError, match="parallel step failed"):
        RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    assert not _after_failure_ran.is_set()
    failed = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert failed.status == RunStatus.FAILED


def test_parallel_run_blocks_dependent_after_quarantine(
    tmp_path: Path,
    run_source_directory: Path,
) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    pipeline = ParallelQuarantinePipeline()
    ingest_result, manifest = _ingest(pipeline_dir, pipeline, run_source_directory)

    RunService().run(pipeline_dir, pipeline, ingest_result.run_directory, manifest)

    result = RunManager(pipeline_dir).load_manifest(ingest_result.run_directory)
    assert result.status == RunStatus.FAILED
    statuses = result.step_status_map()
    assert statuses["quarantine-bad-rows"] == StepRunStatus.QUARANTINED
    assert statuses["validate-processed"] == StepRunStatus.BLOCKED
