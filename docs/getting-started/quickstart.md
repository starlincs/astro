# Quickstart

This walkthrough uses the example pipeline from the Astro repository. Adapt it for your own pipeline repository.

## 1. Create a pipeline

Create `pipeline.py` in your project directory:

```python
import pandera.polars as pa
import polars as pl

from astro import AstroFileSpec, Pipeline
from astro.pipeline import ExecutionMode, IngestFileSpec
from astro.pipeline.files import AstroFile
from astro.pipeline.steps import StepContext


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def remove_closed(dataframe: pl.DataFrame) -> pl.DataFrame:
    return dataframe.filter(pl.col("EstablishmentName").str.contains("Closed"))


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
                {
                    "URN": pa.Column(str),
                    "EstablishmentName": pa.Column(str),
                },
                strict="filter",
            ),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_filter("Remove closed establishments", remove_closed, [EstablishmentsFile()])
        self.add_step(
            "Copy establishments to processed",
            step_copy_establishments,
            [EstablishmentsFile()],
            depends_on=["remove-closed-establishments"],
        )


pipeline = ExamplePipeline()
```

The module **must** export a `pipeline` object.

## 2. Prepare source data

Create a directory with a CSV matching your ingest pattern:

```text
source/
  edubase_sample.csv
```

The CSV must match the Pandera schema declared in `ingest_files`.

## 3. Ingest source files

From the directory containing `pipeline.py`:

```bash
astro ingest path/to/source/
```

Astro will:

1. Validate the source directory contains exactly the expected files
2. Validate each CSV against its Pandera schema
3. Write Parquet files to `.working/{run_id}/ingested/`
4. Record statistics in `.astro/stats.db`

Large files show a progress bar during materialization.

## 4. Run the pipeline

```bash
astro run
```

By default, Astro shows a Rich dashboard with step progress and live logs. Use plain log output instead:

```bash
astro run --mode cli
```

## 5. Inspect the result

```text
.working/{run_id}/
  manifest.json
  ingested/
    establishments.parquet
  processed/
    establishments.parquet
  filtered/
    remove-closed-establishments/
      establishments.parquet
  astro.log
```

View the pipeline flow diagram:

```bash
astro describe
```

List stored runs:

```bash
astro list
```

## Next steps

- {doc}`../user-guide/pipelines` — pipeline configuration in depth
- {doc}`../user-guide/quarantine` — handle invalid rows without aborting
- {doc}`../user-guide/cli` — full CLI reference
