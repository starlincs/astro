# Astro documentation

Astro is a small CLI written in Python that helps you create simple pipelines for processing CSV data into other formats (basically a really simple ETL).

> Astro is primarily generated via AI, so please do your own validation before using in production or critical contexts

You can use Astro to quickly take CSV files, filter and transfor them and create any output you want. Pipelines are defined as "steps" which are just pure Python!

```{toctree}
:maxdepth: 2
:hidden:
:caption: Getting started

getting-started/introduction
getting-started/installation
getting-started/quickstart
```

```{toctree}
:maxdepth: 2
:hidden:
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
:hidden:
:caption: API reference

api/index
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Contributing

contributing/index
contributing/development-setup
contributing/testing
contributing/code-style
contributing/documentation
contributing/release
```

## Quick links

- {doc}`getting-started/installation` — install Astro from PyPI or source
- {doc}`getting-started/quickstart` — ingest and run your first pipeline
- {doc}`user-guide/pipelines` — define a `pipeline.py`
- {doc}`user-guide/cli` — CLI command reference
- {doc}`contributing/index` — contribute to Astro
