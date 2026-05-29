# Running pipelines

`astro run` executes registered pipeline steps on an ingested run.

## Basic usage

```bash
astro run
astro run --run-id abc12
astro run --mode cli
```

## Run resolution

When `--run-id` is omitted, Astro selects a run in this order:

1. Latest quarantined run
2. Latest failed run with quarantined steps
3. Latest ingested run

## Display modes

| Mode | Description |
|------|-------------|
| `dashboard` (default) | Rich three-panel UI: steps (left), live log (right), status bar (bottom) |
| `cli` | Plain console log output (still written to the run log file) |

## Step execution

By default, run steps execute **serially** in registration order, respecting `depends_on`.

When `step_execution_mode = StepExecutionMode.PARALLEL`, Astro dispatches ready steps to a thread pool. A step runs when all dependencies are `complete` or `skipped`, up to `max_parallel_workers` at a time.

## Optional ingest files

When an optional ingest file was not supplied at ingest time:

| Step references | Action |
|-----------------|--------|
| Only absent optional ingests | Step is **skipped** (`skipped` in `manifest.json`) |
| Present ingests only | Step runs normally |
| Both present ingests and absent optional ingests | Run **fails** with an error |

Skipped steps satisfy `depends_on`, so downstream steps that do not reference the missing optional file can still run. Keep optional-only processing in steps that reference that ingest alone; do not combine optional and required/present ingests in one step.

## Run outcomes

| Outcome | Meaning |
|---------|---------|
| `completed` | All steps finished with no quarantined rows (skipped steps count as done) |
| `quarantined` | Some steps quarantined rows; run is retryable |
| `failed` | Hard error or dependency block stopped the run |

`astro run` appends logs to `.working/{run_id}/astro.log` with session separators between invocations.

## View pipeline flow

```bash
astro describe
```

Prints a terminal flow diagram of ingest and run steps.

## Retry quarantined runs

Re-run `astro run` against a `quarantined` run (or a `failed` run with quarantined steps). See {doc}`quarantine` for retry behaviour.

## Next steps

- {doc}`steps-and-files` — implement step functions
- {doc}`cli` — full CLI reference
