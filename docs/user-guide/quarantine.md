# Row quarantine

Steps may quarantine individual rows that fail business rules without aborting the whole step. Quarantined rows are persisted under the run directory and recorded in `manifest.json` step state.

## Step API

Each `StepContext` exposes a `quarantine` collector:

```python
def step_validate(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    df = file.load()
    bad = df.filter(pl.col("score") < 0)
    good = df.filter(pl.col("score") >= 0)
    if not bad.is_empty():
        _ctx.quarantine.quarantine_rows(file, bad, reason="negative score")
    file.save_in_place(good)
```

| Method | Purpose |
|--------|---------|
| `ctx.quarantine.quarantine_rows(file, rows, reason=...)` | Append rows to a new quarantine part file |
| `ctx.quarantine.quarantine_row(file, row, reason=...)` | Convenience for a single row |

- `reason` must be non-empty
- `rows` must not be empty
- Step authors must exclude quarantined rows from saved output

Quarantine Parquet rows use the source file schema plus `_astro_quarantine_reason: str`.

## Run directory layout

```text
.working/{run_id}/
  ingested/
  processed/ …
  snapshots/{step_id}/{ingest_name}.parquet
  quarantine/{step_id}/{ingest_name}.part-00001.parquet
  manifest.json
```

`snapshots/` captures the input `active_path` at step start. Quarantine uses part files (no read-merge-rewrite on append).

## Step and run status

| Event | Step status | Run status | Pipeline action |
|-------|-------------|------------|-----------------|
| Step finishes with quarantined rows | `quarantined` | (unchanged until end) | Continue to next step |
| Step depends on a quarantined step | `blocked` | `failed` | Stop run |
| All runnable steps done, some quarantined | mixed | `quarantined` | Stop run (retryable) |
| All steps complete, no quarantine | `complete` | `completed` | Done |
| Hard exception in step | `failed` | `failed` | Stop run |

`manifest.json` stores per-step records in `step_states`: `step_id`, `status`, and optional `detail`.

## Retry

Re-run `astro run` against a `quarantined` run, or a `failed` run that has quarantined steps. For each quarantined step only:

1. Truncate the step quarantine file(s)
2. Merge snapshot input with quarantined rows back into the file's `active_path`
3. Re-run that step

Previously completed steps are skipped. Previously blocked or pending dependent steps run once their dependencies are `complete`.

## Next steps

- {doc}`running` — run resolution and display modes
- {doc}`statistics` — `rows_quarantined` metric
