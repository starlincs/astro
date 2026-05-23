# Astro specification

## What this is

Astro is a Python CLI tool and library for importing and processing CSV files through user-defined pipelines.

The core product intent is:

- **CLI control** — run and manage pipelines from the command line
- **Library** — define pipelines in external repositories by importing Astro
- **External pipelines** — each pipeline lives in its own repo with a `pipeline.py` file
- **Folder ingestion** — ingest a single CSV file or a directory of files with heterogeneous schemas
- **Persistent statistics** — store pipeline run statistics locally in SQLite

## Tech stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.11+ |
| DataFrame | Polars |
| Schema validation | Pydantic |
| Data validation | Pandera |
| CLI | Typer |
| Local storage | SQLite (`.astro/stats.db`) |
| Lint + format | Ruff |
| Type checking | ty |
| Tests | pytest + pytest-cov |
| Quality gate | `make check` |

## Architecture

```text
External repo                    Astro package
─────────────                    ─────────────
pipeline.py  ──imports──►  astro.Pipeline
     │                     astro.cli (ingest, run, list, cleanup)
     │                     astro.storage (PipelineStore)
     │                     astro.resolver (CanonicalIdResolver)
     │                     astro.ingest (IngestService)
     │                     astro.working (RunManager)
     └── run via ──►  astro ingest|run|list|cleanup
```

When Astro runs in a directory containing `pipeline.py`, it discovers and loads that module. The module must export a `pipeline` object implementing the `Pipeline` interface.

## Pipeline contract

Pipelines declare ingest configuration and register ordered run steps:

- **`ingest_files`** — expected source file patterns and Pandera schemas for CLI ingest
- **`execution_mode`** — `serial` or `parallel` ingest concurrency rules
- **`step_execution_mode`** — `serial` (default) or `parallel` run-step scheduling within a single run
- **`max_parallel_workers`** — optional cap on concurrent run steps when `step_execution_mode=parallel` (defaults to `min(32, cpu_count + 4)`)
- **`configure_steps()`** — register run steps via `add_step(label, fn, files, depends_on=[...])` or filter steps via `add_filter(label, fn, files, depends_on=[...])`
- **`AstroFileSpec`** — per-file configuration container referenced by steps
- **`AstroFile`** — runtime wrapper hydrated during `astro run` with explicit I/O methods

Each source file may have a different schema. Run steps replace the previous `transform` / `validate` methods.

### AstroFile I/O

Steps must write outputs explicitly:

- `file.save_in_place(df)` — overwrite the ingested Parquet snapshot
- `file.save_to(subfolder, filename, df)` — write under `.working/{run_id}/{subfolder}/`
- `file.load()` — read from the file's current active path

Validation-only steps may call `load()` and raise without saving.

## Ingest step

`astro ingest SOURCE_DIR` creates a new pipeline run under `.working/{run_id}/`:

```text
.working/
  abcde/
    manifest.json
    ingested/
      establishments.parquet
```

### Pipeline author configuration

```python
from astro import AstroFileSpec, Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext
import pandera.polars as pa

class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"

def step_copy_establishments(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    file.save_to("processed", "establishments.parquet", file.load())

class ExamplePipeline(Pipeline):
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema(
                {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
                strict="filter",
            ),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step(
            "Copy establishments to processed",
            step_copy_establishments,
            [EstablishmentsFile()],
        )
```

### Ingest behaviour

1. Validate `SOURCE_DIR` contains exactly the expected files (no extras, no subdirectories)
2. Validate each CSV against its Pandera schema
3. Write Parquet files to `.working/{run_id}/ingested/`
4. Record run and file statistics in `.astro/stats.db`
5. Update `manifest.json` with status `ingested`

### Execution modes

| Mode | Behaviour |
|------|-----------|
| `serial` | Fail ingest if any run under `.working/` is not `completed` |
| `parallel` | Allow multiple incomplete runs concurrently |

Run IDs are 5-character lowercase alphanumeric strings.

### CLI logging

Each run directory may contain an `astro.log` file alongside `manifest.json`.

| Command | Console output | Run log file |
|---------|----------------|--------------|
| `astro ingest` | yes | `.working/{run_id}/astro.log` (created after run allocation) |
| `astro run` | dashboard (default) or plain logs (`--mode cli`) | same path; sessions append with a separator |
| `astro describe` | yes | no |
| `astro list`, `astro cleanup` | yes | no |

Each log-file session starts with a timestamp separator:

```text
================================================================================
Astro session started: 2026-05-22T14:30:00.123456+00:00  command=ingest  run_id=abc12
================================================================================
```

Log levels use standard semantics. WARNING lines render yellow and ERROR lines render red in console and dashboard views.

### Run display modes

`astro run` accepts:

- `--run-id` — process a specific runnable run (defaults to the latest quarantined run, else latest failed run with quarantined steps, else latest ingested run)
- `--mode dashboard` — Rich three-panel UI: steps (left), live log (right), status bar (bottom); default
- `--mode cli` — plain console log output (still written to the run log file)

`astro run` executes registered pipeline steps, updates the dashboard step list, marks the run `completed` on success, `quarantined` when steps quarantine rows without blocking dependents, or `failed` on hard errors or dependency blocks, and appends logs to the run log file.

By default, run steps execute **serially** in registration order (respecting `depends_on`). When a pipeline sets `step_execution_mode = StepExecutionMode.PARALLEL`, Astro dispatches ready steps to a thread pool: a step runs when all dependencies are `complete`, up to `max_parallel_workers` at a time. Steps that touch the same ingested file name are serialized with per-file locks to prevent corrupting shared Parquet snapshots. Parallel scheduling is intended for I/O-bound and Polars work; pure-Python CPU-bound steps will not scale due to the GIL.

### Row quarantine

Steps may quarantine individual rows that fail business rules without aborting the whole step. Quarantined rows are persisted under the run directory and recorded in `manifest.json` step state.

#### Run directory layout

```text
.working/{run_id}/
  ingested/
  processed/ …
  snapshots/{step_id}/{ingest_name}.parquet   # input active_path captured at step start
  quarantine/{step_id}/{ingest_name}.parquet  # rows quarantined during that step
  manifest.json                               # extended with step_states
```

Quarantine Parquet rows use the source file schema plus a framework column `_astro_quarantine_reason: str`.

#### Step API

Each `StepContext` exposes a `quarantine` collector:

```python
def step_validate(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    df = file.load()
    bad = df.filter(pl.col("score") < 0)
    good = df.filter(pl.col("score") >= 0)
    if not bad.is_empty():
        _ctx.quarantine.quarantine_rows(file, bad, reason="negative score")
    file.save_in_place(good)
```

- `ctx.quarantine.quarantine_rows(file, rows, reason=...)` — append rows to the step quarantine file
- `ctx.quarantine.quarantine_row(file, row, reason=...)` — convenience for a single row
- `reason` must be non-empty; `rows` must not be empty
- Step authors must exclude quarantined rows from saved output (the framework only collects and merges back on retry)

#### Step and run status

| Event | Step status | Run status | Pipeline action |
|-------|-------------|------------|-----------------|
| Step finishes with quarantined rows | `quarantined` | (unchanged until end) | Continue to next step |
| Step depends on a quarantined step | `blocked` (not started) | `failed` at that point | Stop run |
| All runnable steps done, some quarantined | mixed | `quarantined` | Stop run (retryable) |
| All steps complete, no quarantine | `complete` | `completed` | Done |
| Hard exception in step | `failed` | `failed` | Stop run |

`manifest.json` stores per-step records in `step_states`: `step_id`, `status` (`pending`, `complete`, `quarantined`, `failed`, `blocked`), and optional `detail`.

#### Retry

Re-run `astro run` against a `quarantined` run (or a `failed` run that has quarantined steps). Resolution prefers the latest quarantined run, then the latest failed run with quarantine, then the latest ingested run.

For each quarantined step only:

1. Truncate the step quarantine file(s)
2. Merge snapshot input with quarantined rows back into the file's `active_path`
3. Re-run that step

Previously completed steps are skipped. Previously blocked or pending dependent steps run once their dependencies are `complete`.

### Row filtering

Filter steps remove rows from one or more files using author-defined logic. Astro applies the filter boilerplate: split input rows, save kept rows in place, persist removed rows for audit, and record statistics. Filter steps always complete normally (unlike quarantine).

#### Run directory layout

```text
.working/{run_id}/
  ingested/
  filtered/{step_id}/{ingest_name}.parquet  # rows removed by that filter step
  manifest.json
```

Filtered Parquet rows use the same schema as the source file (no extra framework columns).

#### Pipeline API

Register a filter with `add_filter`. The author function receives the input `pl.DataFrame` and returns **removed rows only**:

```python
def remove_closed(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("status") == "closed")

class ExamplePipeline(Pipeline):
    def configure_steps(self) -> None:
        self.add_filter("Remove closed schools", remove_closed, [EstablishmentsFile()])
        self.add_step(
            "Transform open schools",
            step_transform,
            [EstablishmentsFile()],
            depends_on=["remove-closed-schools"],
        )
```

For each file in the step, Astro:

1. Loads the current active parquet
2. Calls the filter function to obtain removed rows
3. Validates removed rows are a subset of the input (matching columns; semi-join check)
4. Writes kept rows back with `save_in_place()`
5. Writes removed rows to `filtered/{step_id}/{ingest_name}.parquet`
6. Records `rows_filtered` and `rows_kept` statistics

**Duplicate rows:** splitting uses joins on all columns, so identical duplicate rows may not partition cleanly if the filter returns fewer copies than exist in the input.

Filter steps do not affect run quarantine/retry behaviour; removed rows remain in `filtered/` for reference only.

### Statistics

Pipeline runs record numeric statistics scoped to a **run**, **file**, or **step**, keyed by an **action** name. Each update:

1. Logs an INFO line to `astro.stats` (visible in console, dashboard, and `astro.log`)
2. Upserts the value in SQLite (later calls replace the prior value for the same scope/subject/action)

Log format:

```text
STAT run=abc12 scope=step subject=validate action=rows_quarantined value=3
```

Run-scoped statistics use `subject=-` in log output.

#### Step API

Each `StepContext` exposes a `stats` recorder:

```python
def step_transform(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load()
    ctx.stats.record_file(file.spec.__class__.ingest_name, "rows_read", dataframe.height)
    ctx.stats.record_run("custom_counter", 1)
    ctx.stats.record_step("rows_written", dataframe.height)
    file.save_in_place(dataframe)
```

- `ctx.stats.record_run(action, value)` — run-scoped metric
- `ctx.stats.record_file(file_name, action, value)` — file-scoped metric (ingest name)
- `ctx.stats.record_step(action, value)` — step-scoped metric for the current step

`StatisticsRecorder` and `StatScope` are also exported from `astro` for use outside step functions.

#### Built-in statistics

| Phase | Scope | Action | When recorded |
|-------|-------|--------|---------------|
| Ingest | file | `row_count`, `column_count`, `source_size_bytes` | After each file materializes |
| Ingest | run | `files_ingested` | After successful ingest |
| Ingest | run | `ingest_failed` | On ingest failure |
| Run | step | `duration_ms` | After each step executes |
| Run | step | `rows_quarantined` | When a step quarantines rows |
| Run | file | `rows_filtered`, `rows_kept` | After a filter step processes a file |
| Run | step | `rows_filtered` | After a filter step (total removed across files) |
| Run | run | `steps_completed` | When run finishes |
| Run | run | `duration_ms` | When run finishes |
| Run | run | `steps_quarantined` | When run finishes with quarantined steps |

### Run statistics (SQLite)

Stored in `{pipeline_dir}/.astro/stats.db`:

- **`runs`**: `run_id`, `pipeline_name`, `status`, `source_directory`, `created_at`, `ingested_at`
- **`ingest_files`**: per-file row/column counts, source path, parquet path, source size
- **`statistics`**: generic metrics with `run_id`, `scope` (`run` / `file` / `step`), `subject` (empty for run scope), `action`, `value`, `recorded_at`

## Storage

`PipelineStore` persists statistics at `.astro/stats.db` relative to the pipeline working directory unless overridden.

## Canonical ID resolver

Astro provides a Polars-native library for mapping source entries to stable canonical UUIDs and detecting grouped field changes.

### Storage

- Named stores live at `{pipeline_dir}/.persistent/{name}.parquet`
- Each store is scoped to a resolver instance (for example `establishments`, `links`)
- Writes use atomic temp-file rename

### Usage

```python
from datetime import date
from pathlib import Path

import polars as pl

from astro import CanonicalIdResolver

resolver = CanonicalIdResolver(
    pipeline_dir=Path("/path/to/pipeline"),
    name="establishments",
    hash_groups={
        "entry_changed": "*all",
        "address_changed": ["address1", "address2", "postcode"],
        "owner_changed": ["trust (code)"],
    },
)

result = resolver.resolve(
    data=df,
    source_key_column="source_key",
    namespace="establishments",
    run_date=date.today(),
)
```

### Inputs

- **`source_key_column`** — pipeline-provided identifier within a source file
- **`namespace`** — prefixes the stored key as `{namespace}:{source_key}`
- **`hash_groups`** — dict mapping group names to `"*all"` or a list of field names
- **`run_date`** — date-only value used for change tracking (no time component)

Hash groups use SHA-256 over canonicalized field values (null/blank normalized, `\x1f` separator).

### Outputs

Each row is augmented with:

| Column | Meaning |
|--------|---------|
| `canonical_id` | Stable UUID v4 string |
| `status` | `NEW`, `UNCHANGED`, or `CHANGED` |
| `{group}_changed` | Boolean flag per hash group (`True` when that group differs from stored state; all `True` for `NEW`) |

### Persistent record

Each stored entry retains:

- `source_key` — namespaced key
- `canonical_id`
- `{group}_hash` columns for each configured hash group
- `last_changed_date` — date of the most recent hash change
- `update_dates` — list of dates the entry was created or changed

### Performance

Resolution is vectorized with Polars joins and expressions. UUID assignment loops only over new keys. The design targets batches up to 75K rows against stores up to 250K entries.

## CLI commands

| Command | Purpose |
|---------|---------|
| `astro ingest SOURCE_DIR` | Create a run, validate source files, materialize Parquet |
| `astro run [--run-id ID] [--mode dashboard\|cli]` | Execute registered pipeline steps on an ingested run |
| `astro describe` | Display the pipeline steps as a terminal flow diagram |
| `astro list` | List registered pipelines and their statistics (not implemented) |
| `astro cleanup [--all]` | Remove stored pipeline data (not implemented) |

All commands accept `-C / --pipeline-dir` to point at the directory containing `pipeline.py` (defaults to the current directory).

## Quality bar

Before merging or completing work:

1. `make check` must pass (lint, format, typecheck, tests)
2. Test coverage must remain at or above 80%
3. New behaviour requires tests written first (see `AGENTS.md`)

## Current status

`astro ingest` is implemented with run creation, Pandera validation, Parquet materialization, SQLite statistics, serial/parallel gating, and run-scoped logging. `astro run` executes registered pipeline steps serially by default or in parallel when configured via `step_execution_mode`, with dashboard or CLI display, row quarantine, row filtering, retry for quarantined runs, and automatic statistics recording. `astro describe` prints a terminal flow diagram of ingest and run steps. The canonical ID resolver library is implemented as a separate importable module. `astro list` and `astro cleanup` remain stubs.
