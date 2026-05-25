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

1. Validate `SOURCE_DIR` contains exactly the expected CSV files (no extras, no subdirectories)
2. Validate each CSV against its Pandera schema
3. Write Parquet files to `.working/{run_id}/ingested/`
4. Record run and file statistics in `.astro/stats.db`
5. Update `manifest.json` with status `ingested`

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
)
```

CSV dtypes are derived from the Pandera schema to avoid loading all columns as strings.

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
