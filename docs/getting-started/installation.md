# Installation

Astro requires **Python 3.11 or later**.

## Install from PyPI

```bash
pip install astro-pipeline
```

The distribution name is `astro-pipeline` (the name `astro` is already taken on PyPI). After install, use the `astro` CLI and `import astro` as usual.

## Install from source

Clone the Astro repository and install in editable mode with development dependencies:

```bash
git clone https://github.com/starlincs/astro.git
cd astro
pip install -e ".[dev]"
```

Verify the CLI is available:

```bash
astro --help
```

## Install for documentation builds

To build the documentation locally:

```bash
pip install -e ".[docs]"
make docs
```

Open `docs/_build/html/index.html` in a browser, or use live reload:

```bash
make docs-serve
```

## Use Astro in a pipeline repository

Pipeline repositories depend on Astro as a library. Install Astro into the same Python environment where you run your pipeline:

```bash
pip install astro-pipeline
```

Or from a local checkout:

```bash
pip install -e /path/to/astro
```

Your pipeline repository needs a `pipeline.py` at its root (or pass `-C` to point Astro at the directory containing it).

## Optional tooling

```bash
pre-commit install          # run lint/format hooks on commit
pre-commit install --hook-type pre-push  # optional: run tests before push
```

## Next steps

- {doc}`quickstart` — run your first ingest and pipeline run
- {doc}`../contributing/development-setup` — set up a development environment
