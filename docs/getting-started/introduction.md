# Introduction

Astro helps you build reliable CSV import pipelines in Python. You define a pipeline in an external repository, ingest source files from the command line, and run ordered processing steps with built-in validation, statistics, filtering, and quarantine support.

## What Astro provides

- **CLI control** — run and manage pipelines from the command line
- **Library** — define pipelines by importing Astro in your own repository
- **External pipelines** — each pipeline lives in its own repo with a `pipeline.py` file
- **Folder ingestion** — ingest a directory of CSV files with heterogeneous schemas
- **Persistent statistics** — store pipeline run statistics locally in SQLite

## Typical workflow

1. Create a `pipeline.py` that declares ingest files, Pandera schemas, and run steps.
2. Run `astro ingest path/to/source/` to validate CSVs and write Parquet snapshots.
3. Run `astro run` to execute registered pipeline steps.
4. Inspect logs, statistics, and quarantine files under `.working/{run_id}/`.

## Tech stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.11+ |
| DataFrame | Polars |
| Schema validation | Pydantic |
| Data validation | Pandera |
| CLI | Typer |
| Local storage | SQLite (`.astro/stats.db`) |

## Next steps

- {doc}`installation` — set up Astro locally
- {doc}`quickstart` — walk through a complete ingest and run
- {doc}`../user-guide/pipelines` — learn the pipeline contract

## Security model

Astro discovers and executes `pipeline.py` from the directory you pass to `-C` / `--pipeline-dir` (default: current directory). That module runs as your user and can read and write files under the pipeline working tree. **Only run Astro against pipeline repositories you trust.**
