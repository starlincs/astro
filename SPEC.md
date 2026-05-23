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

Pipelines declare ingest configuration and implement transform/validate:

- **`ingest_files`** — expected source file patterns and Pandera schemas for CLI ingest
- **`execution_mode`** — `serial` or `parallel` ingest concurrency rules
- **`transform(data, source)`** — transform one ingested source file
- **`validate(data, source)`** — validate one ingested source file

Each source file may have a different schema. `Pipeline.run()` is reserved for a future `astro run` command.

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
from astro.pipeline import ExecutionMode, IngestFileSpec, Pipeline
import pandera.polars as pa

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
| `astro run` | Run the pipeline (not implemented) |
| `astro list` | List registered pipelines and their statistics (not implemented) |
| `astro cleanup [--all]` | Remove stored pipeline data (not implemented) |

All commands accept `-C / --pipeline-dir` to point at the directory containing `pipeline.py` (defaults to the current directory).

## Quality bar

Before merging or completing work:

1. `make check` must pass (lint, format, typecheck, tests)
2. Test coverage must remain at or above 80%
3. New behaviour requires tests written first (see `AGENTS.md`)

## Current status

`astro ingest` is implemented with run creation, Pandera validation, Parquet materialization, SQLite statistics, and serial/parallel gating. The canonical ID resolver library is implemented. `astro run`, `astro list`, and `astro cleanup` remain stubs.
