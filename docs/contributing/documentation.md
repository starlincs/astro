# Documentation

User-facing documentation lives in `docs/` and is built with Sphinx and MyST (Markdown).

## Build locally

```bash
pip install -e ".[docs]"
make docs
```

Output is written to `docs/_build/html/`. Open `docs/_build/html/index.html` in a browser.

## Live reload

```bash
make docs-serve
```

Uses `sphinx-autobuild` to rebuild on file changes.

## Documentation structure

| Section | Location |
|---------|----------|
| Getting started | `docs/getting-started/` |
| User guide | `docs/user-guide/` |
| API reference | `docs/api/` (autodoc from Python modules) |
| Contributing | `docs/contributing/` |

Configuration: `docs/conf.py`

## Writing guidelines

- Use task-oriented prose for user guides
- Include copy-paste examples where helpful
- Keep CLI option tables accurate with `src/astro/cli/main.py`
- When behaviour changes, update both `SPEC.md` and the relevant `docs/` page

## API docstrings

Public API symbols should have docstrings so autodoc renders useful pages. Focus on symbols exported from `astro.__all__` and key pipeline/resolver classes.

## Read the Docs

The repository includes `.readthedocs.yaml` for automated builds.

### Publish to Read the Docs

1. Sign in at [readthedocs.org](https://readthedocs.org)
2. Import the Git repository
3. Confirm the config file is `.readthedocs.yaml`
4. Enable builds on `main`
5. Update `[project.urls] Documentation` in `pyproject.toml` with the final URL

RTD installs the package and docs dependencies so autodoc can import Polars and Pandera-dependent modules.

## Relationship to SPEC.md

- **`docs/`** — user-facing documentation (installation, guides, API reference)
- **`SPEC.md`** — behavioural specification for implementers and agents

When adding or changing features, update both. The contributing guide in `docs/contributing/index.md` explains this relationship.
