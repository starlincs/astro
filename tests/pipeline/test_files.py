"""AstroFile container tests."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.working.manifest import IngestedFileRecord


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"
    marker = "configured"


@pytest.fixture
def ingest_record(tmp_path: Path) -> IngestedFileRecord:
    parquet_path = tmp_path / "ingested" / "establishments.parquet"
    parquet_path.parent.mkdir(parents=True)
    pl.DataFrame({"URN": ["1"], "EstablishmentName": ["School"]}).write_parquet(parquet_path)
    return IngestedFileRecord(
        name="establishments",
        source_path=str(tmp_path / "source.csv"),
        parquet_path=str(parquet_path),
        row_count=1,
        column_count=2,
        source_size_bytes=10,
    )


@pytest.fixture
def astro_file(tmp_path: Path, ingest_record: IngestedFileRecord) -> AstroFile:
    return AstroFile.hydrate(
        spec=EstablishmentsFile(),
        ingest_record=ingest_record,
        run_directory=tmp_path,
    )


def test_load_reads_active_parquet(astro_file: AstroFile) -> None:
    dataframe = astro_file.load()

    assert dataframe["URN"][0] == "1"


def test_save_in_place_overwrites_ingested_parquet(astro_file: AstroFile) -> None:
    updated = pl.DataFrame({"URN": ["2"], "EstablishmentName": ["Updated"]})

    astro_file.save_in_place(updated)

    assert astro_file.active_path == Path(astro_file.ingest_record.parquet_path)
    assert pl.read_parquet(astro_file.active_path)["URN"][0] == "2"


def test_save_to_writes_under_explicit_subfolder(astro_file: AstroFile, tmp_path: Path) -> None:
    updated = pl.DataFrame({"URN": ["3"], "EstablishmentName": ["Custom"]})

    output_path = astro_file.save_to("processed", "establishments.parquet", updated)

    assert output_path == tmp_path / "processed" / "establishments.parquet"
    assert astro_file.active_path == output_path
    assert pl.read_parquet(output_path)["URN"][0] == "3"


def test_save_to_rejects_empty_subfolder(astro_file: AstroFile) -> None:
    with pytest.raises(ValueError, match="subfolder"):
        astro_file.save_to("", "out.parquet", pl.DataFrame({"URN": ["1"]}))


def test_spec_exposes_custom_configuration(astro_file: AstroFile) -> None:
    assert astro_file.spec.marker == "configured"
