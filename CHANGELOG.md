# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-24

### Added

- PyPI distribution as `astro-pipeline` with GitHub Actions publish workflow
- OSS scaffolding: LICENSE, contributing guides, CI, security policy, and changelog
- Implemented `astro list` and `astro cleanup` CLI commands
- Global `--debug` flag for verbose logging and tracebacks

### Changed

- First stable release (version 1.0.0)
- Removed legacy `Pipeline.run()` and unused `IngestedSource` API
- Hardened SQLite store (WAL, migrations), pipeline discovery, and path traversal guards

## [0.1.0] - 2026-05-24

### Added

- CLI commands: `astro ingest`, `astro run`, `astro describe`, `astro list`, `astro cleanup`
- Pipeline contract with `Pipeline`, `AstroFileSpec`, `AstroFile`, `add_step`, and `add_filter`
- CSV ingest with Pandera validation and Parquet materialization (eager and batched large-file paths)
- Run execution with serial and parallel step scheduling, row quarantine, retry, and filtering
- SQLite statistics store at `.astro/stats.db`
- `CanonicalIdResolver` for stable UUID mapping and change detection
- Rich dashboard for `astro run` and terminal flow diagram for `astro describe`
- Documentation site source under `docs/`

[1.0.0]: https://github.com/starlincs/astro/releases/tag/v1.0.0
[0.1.0]: https://github.com/starlincs/astro/releases/tag/v0.1.0
