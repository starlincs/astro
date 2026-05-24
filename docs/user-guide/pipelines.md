# Defining pipelines

Pipelines declare ingest configuration and register ordered run steps in a `pipeline.py` module.

## Pipeline contract

When Astro runs in a directory containing `pipeline.py`, it discovers and loads that module. The module must export a `pipeline` object implementing the `Pipeline` interface.

### Configuration attributes

| Attribute | Purpose |
|-----------|---------|
| `ingest_files` | Expected source file patterns and Pandera schemas for CLI ingest |
| `execution_mode` | `serial` or `parallel` ingest concurrency rules |
| `step_execution_mode` | `serial` (default) or `parallel` run-step scheduling |
| `max_parallel_workers` | Cap on concurrent run steps when parallel (defaults to `min(32, cpu_count + 4)`) |
| `large_file_threshold_bytes` | Size above which batched ingest/filter/quarantine paths are used (default 100MB) |
| `ingest_batch_size` | CSV rows per batch during large-file ingest (default 100,000) |
| `run_batch_size` | Parquet rows per batch during filter steps and `iter_batches()` (default 100,000) |

### Step registration

Register steps in `configure_steps()`:

- `add_step(label, fn, files, depends_on=[...])` — custom run step
- `add_filter(label, fn, files, depends_on=[...])` — declarative row filter

Each step references one or more `AstroFileSpec` subclasses. Each source file may have a different schema.

## Example pipeline

```python
from astro import AstroFileSpec, Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext
import pandera.polars as pa


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_copy_establishments(_ctx: StepContext, files: list[AstroFile]) -> None:
    file = files[0]
    file.save_to("processed", "establishments.parquet", file.load())


class ExamplePipeline(Pipeline):
    name = "example"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema(
                {"URN": pa.Column(str), "EstablishmentName": pa.Column(str)},
                strict="filter",
            ),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step(
            "Copy establishments to processed",
            step_copy_establishments,
            [EstablishmentsFile()],
        )


pipeline = ExamplePipeline()
```

## AstroFileSpec

`AstroFileSpec` is a declarative per-file configuration container. Subclass it and set `ingest_name` to match an entry in `ingest_files`:

```python
class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"
```

You can add custom attributes for use in step functions:

```python
class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"
    marker = "configured"
```

## Step dependencies

Use `depends_on` to declare step ordering. Step IDs are derived from labels (slugified) unless you pass an explicit `step_id`:

```python
self.add_filter("Remove closed", remove_closed, [EstablishmentsFile()])
self.add_step(
    "Transform open schools",
    step_transform,
    [EstablishmentsFile()],
    depends_on=["remove-closed"],
)
```

## Parallel step execution

Set `step_execution_mode = StepExecutionMode.PARALLEL` to dispatch independent steps concurrently. Steps that touch the same ingested file name are serialized with per-file locks. Parallel scheduling works best for I/O-bound and Polars work; pure-Python CPU-bound steps will not scale due to the GIL.

## Next steps

- {doc}`ingest` — ingest behaviour and execution modes
- {doc}`steps-and-files` — read and write data in steps
- {doc}`filtering` — declarative row filters
