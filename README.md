<p align="center">
  <img src="docs/banner.png" alt="Astro pipeline" width="100%">
</p>

# Astro

CLI tool and library for CSV import pipelines.

## Documentation

Full guides, API reference, and contributing docs are at **[https://astro-pipeline.readthedocs.io](https://astro-pipeline.readthedocs.io)**.

Build locally: `pip install -e ".[docs]"` and `make docs`.

| Topic | Where to read |
|-------|---------------|
| Install and quickstart | [docs/getting-started/](docs/getting-started/) |
| Pipeline authoring | [docs/user-guide/pipelines.md](docs/user-guide/pipelines.md) |
| CLI reference | [docs/user-guide/cli.md](docs/user-guide/cli.md) |
| Contributing | [docs/contributing/](docs/contributing/) |
| Behavioural spec (implementers) | [SPEC.md](SPEC.md) |

## Install

```bash
pip install astro-pipeline
```

PyPI name is `astro-pipeline` because `astro` is already taken. The CLI and import name remain `astro`.

From source:

```bash
git clone https://github.com/starlincs/astro.git
cd astro
pip install -e ".[dev]"
```

## What Astro does

Astro ingests CSV directories into validated Parquet snapshots, then runs ordered pipeline steps with statistics, filtering, and row quarantine. Each pipeline lives in an external repository as a `pipeline.py` file.

```bash
astro ingest path/to/data/
astro run
astro describe
astro list
```

See the [quickstart](docs/getting-started/quickstart.md) and [CLI reference](docs/user-guide/cli.md) for full usage, including cleanup, quarantine retry, and large-file behaviour.

## Security

Astro loads and executes `pipeline.py` from the directory you point it at. Only run Astro against pipeline repositories you trust. See the [security model](docs/getting-started/introduction.md#security-model) in the docs.

## Development

```bash
make check    # lint + format + typecheck + tests
make cov      # include large-file integration tests
```

See [docs/contributing/](docs/contributing/) for the test-first workflow and release process.

## License

MIT — see [LICENSE](LICENSE).
