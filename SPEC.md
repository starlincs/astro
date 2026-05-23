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
     └── run via ──►  astro ingest|run|list|cleanup
```

When Astro runs in a directory containing `pipeline.py`, it discovers and loads that module. The module must export a `pipeline` object implementing the `Pipeline` interface.

## Pipeline contract

Pipelines implement `ingest`, `transform`, and `validate`:

- **`ingest(path)`** — load a file or directory; return `list[IngestedSource]`
- **`transform(data, source)`** — transform one source file's data
- **`validate(data, source)`** — validate one source file's data

Each source file may have a different schema. `Pipeline.run(path)` orchestrates ingest → transform → validate per source.

## CLI commands

| Command | Purpose |
|---------|---------|
| `astro ingest PATH` | Ingest a CSV file or directory of files |
| `astro run` | Run the pipeline |
| `astro list` | List pipelines and stored statistics |
| `astro cleanup [--all]` | Remove stored pipeline data |

All commands accept `-C / --pipeline-dir` to point at the directory containing `pipeline.py` (defaults to the current directory).

## Storage

`PipelineStore` persists statistics at `.astro/stats.db` relative to the pipeline working directory unless overridden.

## Quality bar

Before merging or completing work:

1. `make check` must pass (lint, format, typecheck, tests)
2. Test coverage must remain at or above 80%
3. New behaviour requires tests written first (see `AGENTS.md`)

## Current status

Commands and storage methods are stubbed. Discovery and the pipeline base class are implemented. Feature logic will be added incrementally with tests.
