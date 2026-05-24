# Canonical ID resolver

Astro provides a Polars-native library for mapping source entries to stable canonical UUIDs and detecting grouped field changes.

## Storage

- Named stores live at `{pipeline_dir}/.persistent/{name}.parquet`
- Each store is scoped to a resolver instance (for example `establishments`, `links`)
- Writes use atomic temp-file rename

## Usage

```python
from datetime import date
from pathlib import Path

import polars as pl

from astro import CanonicalIdResolver

resolver = CanonicalIdResolver(
    pipeline_dir=Path("/path/to/pipeline"),
    name="establishments",
    hash_groups={
        "entry_changed": "*all",
        "address_changed": ["address1", "address2", "postcode"],
        "owner_changed": ["trust (code)"],
    },
)

result = resolver.resolve(
    data=df,
    source_key_column="source_key",
    namespace="establishments",
    run_date=date.today(),
)
```

## Inputs

| Parameter | Purpose |
|-----------|---------|
| `source_key_column` | Pipeline-provided identifier within a source file |
| `namespace` | Prefixes the stored key as `{namespace}:{source_key}` |
| `hash_groups` | Dict mapping group names to `"*all"` or a list of field names |
| `run_date` | Date-only value used for change tracking (no time component) |

Hash groups use SHA-256 over canonicalized field values (null/blank normalized, `\x1f` separator).

## Outputs

Each row is augmented with:

| Column | Meaning |
|--------|---------|
| `canonical_id` | Stable UUID v4 string |
| `status` | `NEW`, `UNCHANGED`, or `CHANGED` |
| `{group}_changed` | Boolean flag per hash group |

## Persistent record

Each stored entry retains:

- `source_key` — namespaced key
- `canonical_id`
- `{group}_hash` columns for each configured hash group
- `last_changed_date` — date of the most recent hash change
- `update_dates` — list of dates the entry was created or changed

## Performance

Resolution is vectorized with Polars joins and expressions. UUID assignment loops only over new keys. The design targets batches up to 75K rows against stores up to 250K entries.

See {doc}`../api/index` for the full API reference.
