# Large files

Astro uses batched I/O for files at or above `large_file_threshold_bytes` (default **100MB**). This applies to ingest, filter steps, and quarantine appends.

## Pipeline tuning

Configure on your pipeline class:

```python
class ExamplePipeline(Pipeline):
    large_file_threshold_bytes = 100 * 1024 * 1024  # 100MB
    ingest_batch_size = 100_000   # CSV rows per ingest batch
    run_batch_size = 100_000      # Parquet rows per filter/batch iteration
```

| Setting | Default | Purpose |
|---------|---------|---------|
| `large_file_threshold_bytes` | 100MB | Trigger batched paths |
| `ingest_batch_size` | 100,000 | CSV rows validated and written per batch during ingest |
| `run_batch_size` | 100,000 | Parquet rows processed per batch during filter and `iter_batches()` |

## Ingest

Large-file ingest reads CSVs in a single pass, validates each batch with Pandera, and appends to a single Parquet file via PyArrow. Small files use the eager path.

- UTF-8 files: `scan_csv` + `collect_batches`
- Non-UTF-8 encodings (e.g. cp1252): PyArrow streaming CSV reader

The CLI shows a progress bar during large-file ingest, with row counts estimated from a file-size sample.

## Filter and quarantine

Filter steps and quarantine appends use batched Parquet I/O above the threshold, avoiding full in-memory loads.

## Step authors

For large files in custom steps, prefer lazy I/O:

```python
def step_transform(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    if file.is_large_file():
        lazy_frame = file.scan().with_columns(pl.lit("processed").alias("stage"))
        file.save_in_place_lazy(lazy_frame)
        return
    file.save_in_place(file.load().with_columns(pl.lit("processed").alias("stage")))
```

Or iterate batches:

```python
for batch in file.iter_batches():
    # process batch
    ...
```

## Bypass batched ingest temporarily

To force the eager path for a one-off run (fast but memory-heavy), raise the threshold above your file size:

```python
large_file_threshold_bytes = 10 * 1024 * 1024 * 1024  # 10GB
```

## Next steps

- {doc}`ingest` — ingest behaviour
- {doc}`steps-and-files` — `scan()`, `sink()`, and `iter_batches()`
