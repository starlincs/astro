# Astro documentation

Astro is a Python CLI tool and library for importing and processing CSV files through user-defined pipelines.

Use Astro to validate source CSVs, materialize Parquet snapshots, run ordered pipeline steps, filter and quarantine rows, and record run statistics locally.

```{toctree}
:maxdepth: 2
:caption: Getting started

getting-started/introduction
getting-started/installation
getting-started/quickstart
```

```{toctree}
:maxdepth: 2
:caption: User guide

user-guide/pipelines
user-guide/ingest
user-guide/running
user-guide/steps-and-files
user-guide/filtering
user-guide/quarantine
user-guide/statistics
user-guide/large-files
user-guide/resolver
user-guide/working-directory
user-guide/cli
```

```{toctree}
:maxdepth: 2
:caption: API reference

api/index
```

```{toctree}
:maxdepth: 2
:caption: Contributing

contributing/index
contributing/development-setup
contributing/testing
contributing/code-style
contributing/documentation
```

## Quick links

- {doc}`getting-started/installation` — install Astro from source
- {doc}`getting-started/quickstart` — ingest and run your first pipeline
- {doc}`user-guide/pipelines` — define a `pipeline.py`
- {doc}`user-guide/cli` — CLI command reference
- {doc}`contributing/index` — contribute to Astro

## Architecture

```text
External repo                    Astro package
─────────────                    ─────────────
pipeline.py  ──imports──►  astro.Pipeline
     │                     astro.cli (ingest, run, list, cleanup)
     │                     astro.storage (PipelineStore)
     │                     astro.resolver (CanonicalIdResolver)
     │                     astro.ingest (IngestService)
     │                     astro.working (RunManager)
     └── run via ──►  astro ingest|run|list|cleanup
```

Each pipeline lives in its own repository with a `pipeline.py` file. Astro discovers and loads that module when you run commands from the pipeline directory (or pass `-C`).
