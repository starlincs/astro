# CLI reference

All commands accept `-C / --pipeline-dir` to point at the directory containing `pipeline.py` (defaults to the current directory).

## astro ingest

Create a run, validate source files, and materialize Parquet.

```bash
astro ingest SOURCE_DIR [-C PIPELINE_DIR]
```

| Argument / option | Description |
|-------------------|-------------|
| `SOURCE_DIR` | Path to a directory of source CSV files (required) |
| `-C`, `--pipeline-dir` | Directory containing `pipeline.py` |

**Behaviour:** Validates the source directory, applies Pandera schemas, writes Parquet to `.working/{run_id}/ingested/`, and records statistics. Shows a progress bar for large files.

**Logging:** Console output and `.working/{run_id}/astro.log`.

## astro run

Execute registered pipeline steps on an ingested run.

```bash
astro run [-C PIPELINE_DIR] [--run-id ID] [--mode dashboard|cli]
```

| Option | Description |
|--------|-------------|
| `-C`, `--pipeline-dir` | Directory containing `pipeline.py` |
| `--run-id` | Run identifier to process (defaults to latest runnable run) |
| `--mode` | `dashboard` (default) or `cli` for plain log output |

**Run resolution order** (when `--run-id` is omitted):

1. Latest quarantined run
2. Latest failed run with quarantined steps
3. Latest ingested run

## astro describe

Display the pipeline steps as a terminal flow diagram.

```bash
astro describe [-C PIPELINE_DIR]
```

## astro list

List stored pipeline runs from the statistics database.

```bash
astro list [-C PIPELINE_DIR]
```

Displays a table with run ID, pipeline name, status, source directory, and timestamps.

## astro cleanup

Remove completed or failed run directories and their statistics records.

```bash
astro cleanup [-C PIPELINE_DIR] [--all] [--dry-run] [--yes]
```

| Option | Description |
|--------|-------------|
| `--all` | Remove all runs, clear `.astro/stats.db`, and remove `.persistent/` resolver stores |
| `--dry-run` | Show planned deletions without removing anything |
| `--yes`, `-y` | Skip the confirmation prompt |

**Behaviour:** By default, removes run directories whose status is `completed` or `failed`, and deletes their rows from the statistics database. Runs that are `ingested` or `quarantined` are preserved. With `--all`, every run directory is removed along with all stored statistics and persistent resolver data. The command always prints a dry-run summary first; omit `--dry-run` and confirm (or pass `--yes`) to execute.

## Global options

```bash
astro [--debug] --help
```

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging and include tracebacks in error output |

## Logging summary

| Command | Console | Run log file |
|---------|---------|--------------|
| `astro ingest` | yes | `.working/{run_id}/astro.log` |
| `astro run` | dashboard or CLI | same path; sessions append |
| `astro describe` | yes | no |
| `astro list`, `astro cleanup` | yes | no |

Log levels use standard semantics. WARNING lines render yellow and ERROR lines render red in console and dashboard views.
