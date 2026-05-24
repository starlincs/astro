# Row filtering

Filter steps remove rows from one or more files using author-defined logic. Astro applies the filter boilerplate: split input rows, save kept rows in place, persist removed rows for audit, and record statistics.

Filter steps always complete normally (unlike quarantine).

## Register a filter

The author function receives the input `pl.DataFrame` and returns **removed rows only**:

```python
def remove_closed(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("EstablishmentName").str.contains("Closed"))


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

You can also pass a Polars expression predicate:

```python
self.add_filter("Remove closed", pl.col("status") == "closed", [EstablishmentsFile()])
```

## What Astro does for each file

1. Loads the current active parquet (or uses batched path for large files)
2. Calls the filter function to obtain removed rows
3. Validates removed rows are a subset of the input (matching columns; semi-join check)
4. Writes kept rows back with `save_in_place()`
5. Writes removed rows to `filtered/{step_id}/{ingest_name}.parquet`
6. Records `rows_filtered` and `rows_kept` statistics

## Run directory layout

```text
.working/{run_id}/
  ingested/
  filtered/{step_id}/{ingest_name}.parquet
  manifest.json
```

Filtered Parquet rows use the same schema as the source file (no extra framework columns).

## Duplicate rows

Splitting uses joins on all columns, so identical duplicate rows may not partition cleanly if the filter returns fewer copies than exist in the input.

## Large files

Filter steps automatically use a batched path when the file exceeds `large_file_threshold_bytes`. See {doc}`large-files`.

## Next steps

- {doc}`quarantine` — isolate invalid rows with retry support
- {doc}`statistics` — built-in filter statistics
