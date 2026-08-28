# Release and PyPI publishing

Astro is published to PyPI as **`astro-pipeline`**. The import name and CLI remain `astro`.

## Versioning

- Single source of truth: `__version__` in `src/astro/__init__.py`
- Hatch reads it via `[tool.hatch.version]` in `pyproject.toml`
- Record user-visible changes in `CHANGELOG.md`

## GitHub release notes

Release notes are generated from `CHANGELOG.md` so PyPI, GitHub, and the changelog stay aligned.

1. Move `[Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md`.
2. Bump `__version__` in `src/astro/__init__.py` and update `tests/test_import.py`.
3. Run `make check`, commit, tag, and push:

```bash
git tag v1.2.0
git push origin main v1.2.0
```

4. Create or update the GitHub release from the changelog:

```bash
./scripts/create-github-release.sh 1.2.0
```

The script reads the matching changelog section and runs `gh release create` (or `gh release edit` if the release already exists). Preview notes only:

```bash
python scripts/extract_changelog.py 1.2.0
```

Requires the [`gh`](https://cli.github.com/) CLI authenticated against the repository.

## Build locally

```bash
pip install -e ".[dev]"
make build
```

Artifacts are written to `dist/`. Verify locally with:

```bash
twine check dist/*
```

For manual uploads, run `twine check dist/*` if your Twine version supports Metadata 2.4 (PEP 639). PyPI accepts the wheel regardless.

## Publish manually

Use this only when not publishing via GitHub Actions.

1. Create a PyPI account and register the `astro-pipeline` project.
2. Create an API token scoped to that project.
3. Build and upload:

```bash
make build
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-... twine upload dist/*
```

## Publish via GitHub Actions (recommended)

The workflow in `.github/workflows/publish.yml` publishes on:

- Git push of a tag matching `v*` (for example `v1.0.0`)
- GitHub Release publish
- Manual `workflow_dispatch`

### One-time PyPI trusted publishing setup

1. On [pypi.org](https://pypi.org), register the **`astro-pipeline`** project (the name `astro` is already taken).
2. Open **Publishing** → **Add a new pending publisher**.
3. Configure:
   - **PyPI project name:** `astro-pipeline`
   - **Owner:** `starlincs`
   - **Repository:** `astro`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
4. In GitHub, create an environment named **`pypi`** on the repository (Settings → Environments). No secrets are required for trusted publishing.
5. Tag and push a release:

```bash
git tag v1.0.0
git push origin main v1.0.0
./scripts/create-github-release.sh 1.0.0
```

Pushing a `v*` tag triggers the publish workflow. The GitHub release step is separate and uses notes from `CHANGELOG.md`.

## After publishing

Users install with:

```bash
pip install astro-pipeline
```

Update `README.md` and `docs/getting-started/installation.md` if install instructions change.
