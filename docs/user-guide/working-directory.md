# Working directory layout

Astro stores run data and statistics relative to your pipeline directory.

## Pipeline directory

```text
pipeline_dir/
  pipeline.py
  .astro/
    stats.db              # SQLite statistics
  .persistent/
    {name}.parquet        # Canonical ID resolver stores
  .working/
    {run_id}/             # One directory per run
```

## Run directory

```text
.working/{run_id}/
  manifest.json           # Run metadata and step states
  astro.log               # Run-scoped log file
  ingested/
    {ingest_name}.parquet
  processed/              # Step outputs (author-defined subfolders)
  filtered/
    {step_id}/
      {ingest_name}.parquet
  snapshots/
    {step_id}/
      {ingest_name}.parquet
  quarantine/
    {step_id}/
      {ingest_name}.part-00001.parquet
```

## manifest.json

Tracks run status (`ingested`, `completed`, `quarantined`, `failed`), ingested file records, and per-step state in `step_states`.

Each step record includes `step_id`, `status` (`pending`, `complete`, `quarantined`, `failed`, `blocked`), and optional `detail`.

## Run IDs

Run IDs are 5-character lowercase alphanumeric strings assigned at ingest time.

## Statistics database

`PipelineStore` persists statistics at `.astro/stats.db`:

- **`runs`** — run metadata
- **`ingest_files`** — per-file ingest records
- **`statistics`** — scoped metrics (run, file, step)

See {doc}`statistics` for the statistics API and built-in metrics.

## Cleanup

Use `astro cleanup` to remove completed or failed run directories under `.working/` and delete their statistics records. Pass `--all` to also clear `.astro/stats.db` and `.persistent/`. See {doc}`cli` for `--dry-run` and confirmation options.

## Next steps

- {doc}`ingest` — what happens during ingest
- {doc}`quarantine` — snapshot and quarantine paths
