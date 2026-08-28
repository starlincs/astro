# Steps and file I/O

During `astro run`, each step receives a `StepContext` and a list of `AstroFile` instances hydrated from the ingested run.

## Step function signature

```python
def step_copy(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    file.save_to("processed", "establishments.parquet", file.load())
```

Steps must write outputs explicitly. Validation-only steps may call `load()` and raise without saving.

## AstroFile I/O methods

| Method | Purpose |
|--------|---------|
| `file.load()` | Eager read from the active path (small files) |
| `file.scan()` | Lazy `scan_parquet` over the active path |
| `file.sink(lf)` | Streaming Parquet write to the active path |
| `file.save_in_place(df)` | Overwrite the ingested Parquet snapshot |
| `file.save_in_place_lazy(lf)` | Streaming overwrite of the ingested snapshot |
| `file.save_to(subfolder, filename, df)` | Write under `.working/{run_id}/{subfolder}/` |
| `file.save_to_lazy(subfolder, filename, lf)` | Streaming write under a subfolder |
| `file.row_count()` | Metadata-only row count |
| `file.iter_batches()` | Iterate Parquet row batches for large-file logic |
| `file.is_large_file()` | Whether the active path exceeds the large-file threshold |

For large files, prefer `scan()` + `sink()` or `save_in_place_lazy()` over `load()`. See {doc}`large-files`.

## Chunked export helpers

For export steps that materialize many rows or documents outside Parquet (for example SQLite CSV imports or Typesense JSONL dumps), use the helpers in `astro.io`:

| Symbol | Purpose |
|--------|---------|
| `CsvChunkWriter` | Write fixed-size CSV chunks with a stable column order |
| `JsonlChunkWriter` | Write fixed-size JSONL document chunks |
| `write_export_manifest` | Write a `manifest.json` beside exported chunk files |
| `export_file_dicts` | Serialize `ExportFileEntry` metadata for manifest payloads |

Each writer flushes when a chunk reaches `chunk_size`, names files `{prefix}-{index:05d}.{csv|jsonl}`, and returns totals plus per-file metadata from `finalize()`. Call `write_export_manifest` after export completes to record table or collection metadata alongside the chunk files.

## Optional ingest files

If an `IngestFileSpec` is declared with `optional=True` and no source file was ingested, run steps behave as follows:

- Steps whose `AstroFileSpec` list references **only** that absent optional ingest are skipped.
- Steps that reference both the absent optional ingest and a present ingest fail the run.
- Skipped steps count as satisfied dependencies for `depends_on`.

See {doc}`ingest` for ingest-time optional file rules and {doc}`running` for run outcomes.

## StepContext

Each step receives a context with:

| Attribute | Purpose |
|-----------|---------|
| `pipeline_dir` | Directory containing `pipeline.py` |
| `run_directory` | `.working/{run_id}/` path |
| `run_id` | Current run identifier |
| `run_date` | Date assigned to the run |
| `step_id` | Current step identifier |
| `logger` | Step-scoped logger |
| `quarantine` | Quarantine collector (see {doc}`quarantine`) |
| `stats` | Statistics recorder (see {doc}`statistics`) |
| `data_environment` | Resolved data environment paths and name (see below) |

## Data environment

At the start of `astro run`, Astro resolves a named data environment under `data/environments/<name>/` and exposes it on `StepContext.data_environment`. Use it in export or lookup steps for SQLite database paths (`sqlite_db("pipeline")`) and the Typesense data directory (`typesense_data_dir`).

Resolution order:

1. `DATA_ENV` process environment variable (absolute or relative to the pipeline directory)
2. `DATA_ENV` in `environment.local` beside `pipeline.py`
3. `PAF_ENV` process environment variable → `../../data/environments/<PAF_ENV>`
4. Default → `../../data/environments/dev`

When a data environment is resolved, Astro loads KEY=VALUE pairs from `<environment>/.env` into the process environment without overriding variables that are already set (for example Typesense connection settings).

## Example: validation step

```python
def step_validate(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load()
    if dataframe.is_empty():
        raise ValueError("establishments file is empty")
```

## Example: lazy transform

```python
def step_transform(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    lazy_frame = file.scan().with_columns(pl.lit("processed").alias("stage"))
    file.save_to_lazy("processed", "establishments.parquet", lazy_frame)
```

## Next steps

- {doc}`filtering` — declarative row filters
- {doc}`quarantine` — isolate invalid rows without aborting
