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
- **`configure_steps()`** — register run steps via `add_step(label, fn, files, depends_on=[...])`
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

- `--run-id` — process a specific ingested run (defaults to the latest run with status `ingested`)
- `--mode dashboard` — Rich three-panel UI: steps (left), live log (right), status bar (bottom); default
- `--mode cli` — plain console log output (still written to the run log file)

`astro run` executes registered pipeline steps in order, updates the dashboard step list, marks the run `completed` on success, and appends logs to the run log file.

### Run statistics (SQLite)

Stored in `{pipeline_dir}/.astro/stats.db`:

- **`runs`**: `run_id`, `pipeline_name`, `status`, `source_directory`, `created_at`, `ingested_at`
- **`ingest_files`**: per-file row/column counts, source path, parquet path, source size

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
| `astro list` | List registered pipelines and their statistics (not implemented) |
| `astro cleanup [--all]` | Remove stored pipeline data (not implemented) |

All commands accept `-C / --pipeline-dir` to point at the directory containing `pipeline.py` (defaults to the current directory).

## Quality bar

Before merging or completing work:

1. `make check` must pass (lint, format, typecheck, tests)
2. Test coverage must remain at or above 80%
3. New behaviour requires tests written first (see `AGENTS.md`)

## Current status

`astro ingest` is implemented with run creation, Pandera validation, Parquet materialization, SQLite statistics, serial/parallel gating, and run-scoped logging. `astro run` executes registered pipeline steps with dashboard or CLI display and marks runs completed. The canonical ID resolver library is implemented as a separate importable module. `astro list` and `astro cleanup` remain stubs.
