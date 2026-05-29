# Statistics

Pipeline runs record numeric statistics scoped to a **run**, **file**, or **step**, keyed by an **action** name.

Each update:

1. Logs an INFO line to `astro.stats` (visible in console, dashboard, and `astro.log`)
2. Upserts the value in SQLite (later calls replace the prior value for the same scope/subject/action)

Log format:

```text
STAT run=abc12 scope=step subject=validate action=rows_quarantined value=3
```

Run-scoped statistics use `subject=-` in log output.

## Step API

Each `StepContext` exposes a `stats` recorder:

```python
def step_transform(ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    dataframe = file.load()
    ctx.stats.record_file(file.spec.__class__.ingest_name, "rows_read", dataframe.height)
    ctx.stats.record_run("custom_counter", 1)
    ctx.stats.record_step("rows_written", dataframe.height)
    file.save_in_place(dataframe)
```

| Method | Scope |
|--------|-------|
| `ctx.stats.record_run(action, value)` | Run |
| `ctx.stats.record_file(file_name, action, value)` | File (ingest name) |
| `ctx.stats.record_step(action, value)` | Current step |

`StatisticsRecorder` and `StatScope` are also exported from `astro` for use outside step functions.

## Built-in statistics

| Phase | Scope | Action | When recorded |
|-------|-------|--------|---------------|
| Ingest | file | `row_count`, `column_count`, `source_size_bytes` | After each file materializes |
| Ingest | run | `files_ingested` | After successful ingest |
| Run | step | `duration_ms` | After each step executes |
| Run | step | `rows_quarantined` | When a step quarantines rows |
| Run | file | `rows_filtered`, `rows_kept` | After a filter step processes a file |
| Run | step | `rows_filtered` | After a filter step (total removed) |
| Run | run | `steps_completed` | When run finishes |
| Run | run | `duration_ms` | When run finishes |
| Run | run | `steps_quarantined` | When run finishes with quarantined steps |

## SQLite storage

Statistics are stored in `{pipeline_dir}/.astro/stats.db`:

- **`runs`**: `run_id`, `pipeline_name`, `status`, `source_directory`, `created_at`, `ingested_at`
- **`ingest_files`**: per-file row/column counts, source path, parquet path, source size
- **`statistics`**: generic metrics with `run_id`, `scope`, `subject`, `action`, `value`, `recorded_at`

See {doc}`working-directory` for the full directory layout.
