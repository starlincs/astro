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

List registered pipelines and their statistics.

```bash
astro list [-C PIPELINE_DIR]
```

**Status:** Not yet implemented.

## astro cleanup

Remove stored pipeline data and statistics.

```bash
astro cleanup [-C PIPELINE_DIR] [--all]
```

| Option | Description |
|--------|-------------|
| `--all` | Remove all stored pipeline statistics |

**Status:** Not yet implemented.

## Global options

```bash
astro --help
```

## Logging summary

| Command | Console | Run log file |
|---------|---------|--------------|
| `astro ingest` | yes | `.working/{run_id}/astro.log` |
| `astro run` | dashboard or CLI | same path; sessions append |
| `astro describe` | yes | no |
| `astro list`, `astro cleanup` | yes | no |

Log levels use standard semantics. WARNING lines render yellow and ERROR lines render red in console and dashboard views.
