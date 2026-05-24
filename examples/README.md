# Example pipeline

This directory contains a minimal Astro pipeline you can run locally.

## Prerequisites

```bash
pip install -e ".[dev]"
```

## Run the example

From the repository root:

```bash
# Create sample source data
mkdir -p /tmp/astro-example-source
echo 'URN,EstablishmentName' > /tmp/astro-example-source/edubase20260522.csv
echo '100001,Example School' >> /tmp/astro-example-source/edubase20260522.csv

# Run ingest and pipeline steps from the example directory
astro ingest /tmp/astro-example-source -C examples/
astro run -C examples/
astro describe -C examples/
astro list -C examples/
```

Working files are written under `examples/.working/` and statistics under `examples/.astro/`.

Remove completed runs with:

```bash
astro cleanup -C examples/ --yes
```

See [docs/getting-started/quickstart.md](../docs/getting-started/quickstart.md) for a guided walkthrough.
