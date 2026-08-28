# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `astro.io` chunked export helpers — `CsvChunkWriter`, `JsonlChunkWriter`, `write_export_manifest`, and `ExportFileEntry` for pipeline steps that write SQLite-importable CSV or Typesense JSONL artifacts in fixed-size chunks
- Data environment resolution for `astro run` — `StepContext.data_environment` resolves `data/environments/<name>/` from `DATA_ENV`, `environment.local`, or `PAF_ENV`, and loads the environment `.env` file without overriding existing process variables
- `IngestFileSpec.preprocess` — optional per-file loader (`Callable[[Path], pl.DataFrame]`) invoked before Pandera validation; replaces default CSV reading
- `IngestFileSpec.optional` — skip ingest specs when no source file matches; at least one file must still match overall
- Run steps that reference only absent optional ingests are skipped during `astro run`; steps mixing present and absent optional ingests fail the run

### Changed

- Failed ingest now removes the run directory under `.working/` (and SQLite rows for that run) instead of leaving a `failed` run that blocks serial pipelines

## [1.0.0](https://github.com/starlincs/astro/releases/tag/v1.0.0) - 2026-05-24

### Added

- First stable release (version 1.0.0)
