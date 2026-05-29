# Ingest

`astro ingest SOURCE_DIR` creates a new pipeline run under `.working/{run_id}/`. `SOURCE_DIR` must be a directory containing one or more CSV source files.

## Run directory after ingest

```text
.working/
  abcde/
    manifest.json
    ingested/
      establishments.parquet
    astro.log
```

## Ingest behaviour

1. Validate `SOURCE_DIR` is a flat directory of files (no subdirectories)
2. Match source files to declared `ingest_files` specs (required specs must match exactly one file; optional specs may be absent; at least one file must match overall; no unmatched extras)
3. Load each matched file via default CSV reading or an optional `preprocess` hook, then validate against its Pandera schema
4. Write Parquet files to `.working/{run_id}/ingested/` (batched validation + append for large CSV files ≥ `large_file_threshold_bytes`; preprocess always uses the eager path)
5. Record run and file statistics in `.astro/stats.db`
6. Update `manifest.json` with status `ingested`

If ingest fails for any reason, Astro removes the run directory under `.working/` (and any SQLite rows for that run) so serial pipelines can ingest again immediately. No `failed` ingest run is left behind.

Large-file ingest reads CSVs in batches, validates each batch with Pandera, and appends to a single Parquet file via PyArrow. Small files use the eager path. CSV dtypes are derived from the Pandera schema to avoid loading all columns as strings.

## IngestFileSpec

Declare expected source files in `ingest_files`:

```python
IngestFileSpec(
    name="establishments",
    source_pattern="edubase*.csv",
    schema=pa.DataFrameSchema(
        {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
        strict="filter",
    ),
    encoding="utf-8",       # optional, default utf-8
    has_header=True,        # optional, default True
    column_names=None,      # required when has_header=False
    preprocess=None,        # optional Callable[[Path], pl.DataFrame]; replaces CSV loading
    optional=False,         # optional, default False; skip when no file matches
)
```

CSV dtypes are derived from the Pandera schema to avoid loading all columns as strings. When `preprocess` is set, it is called with the matched source path and must return a `pl.DataFrame` that is then Pandera-validated and written to Parquet; `encoding`, `has_header`, and `column_names` are ignored. Preprocess always uses the eager materialization path regardless of file size.

When `optional=True`, a missing source file is skipped rather than failing ingest. At least one ingest file (required or optional) must still match. During `astro run`, steps that reference only absent optional ingests are skipped automatically. Steps that mix present ingests with absent optional ingests fail the run — keep optional-only work in dedicated steps.

`name` values must be unique across the pipeline. Names must start with an alphanumeric character and may contain letters, numbers, `.`, `_`, and `-`. Set `column_names` when `has_header=False`; Astro uses those names with the Pandera schema when reading headerless CSVs.

## Execution modes

| Mode | Behaviour |
|------|-----------|
| `serial` | Fail ingest if any run under `.working/` is not `completed` |
| `parallel` | Allow multiple incomplete runs concurrently |

Set on your pipeline class:

```python
class ExamplePipeline(Pipeline):
    execution_mode = ExecutionMode.SERIAL
```

Run IDs are 5-character lowercase alphanumeric strings.

## Large-file ingest

Files at or above `large_file_threshold_bytes` (default 100MB) use batched validation and append to Parquet via PyArrow. Small files use the eager path. See {doc}`large-files` for tuning batch sizes and streaming behaviour.

During large-file ingest, the CLI shows a progress bar with estimated row counts.

## Logging

`astro ingest` prints logs to the console and writes them to `.working/{run_id}/astro.log`. Each session starts with a timestamp separator:

```text
================================================================================
Astro session started: 2026-05-22T14:30:00.123456+00:00  command=ingest  run_id=abc12
================================================================================
```

## Next steps

- {doc}`running` — execute pipeline steps after ingest
- {doc}`../getting-started/quickstart` — end-to-end walkthrough
