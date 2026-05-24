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
