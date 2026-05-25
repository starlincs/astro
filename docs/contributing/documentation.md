# Documentation

User-facing documentation lives in `docs/` and is built with Sphinx and MyST (Markdown).

## Root markdown vs `docs/`

Keep a single source of truth for each audience:

| Content | Write it here | Not here |
|---------|---------------|----------|
| Install, guides, API reference | `docs/` | `README.md` (link only) |
| GitHub landing summary | `README.md` | `docs/` |
| Contributing workflow | `docs/contributing/` | `CONTRIBUTING.md` (pointer only) |
| Behavioural contract | `SPEC.md` | User guide pages |
| Vulnerability reporting | `SECURITY.md` | — |
| Release notes | `CHANGELOG.md` | — |

`README.md` and `CONTRIBUTING.md` stay short and link into the docs site. Avoid copying CLI tables, workflow steps, or guide prose into root files.

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

## Relationship to other docs

- **`docs/`** — user-facing documentation (installation, guides, API reference)
- **`SPEC.md`** — behavioural specification for implementers and agents
- **`README.md` / `CONTRIBUTING.md`** — short GitHub entry points that link here

When adding or changing features, update the relevant `docs/` page and `SPEC.md`. See {doc}`index` for the full file layout.
