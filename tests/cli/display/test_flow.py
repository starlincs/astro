"""Pipeline flow diagram tests."""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from astro.cli.display.flow import build_flow_graph, render_flow_diagram
from astro.pipeline.base import Pipeline
from astro.pipeline.files import AstroFile, AstroFileSpec
from astro.pipeline.models import ExecutionMode, IngestFileSpec
from astro.pipeline.steps import StepContext, StepKind


class EstablishmentsFile(AstroFileSpec):
    ingest_name = "establishments"


def step_one(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


def step_two(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


class SteppedPipeline(Pipeline):
    name = "stepped"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("First step", step_one, [EstablishmentsFile()])
        self.add_step(
            "Second step",
            step_two,
            [EstablishmentsFile()],
            depends_on=["first-step"],
        )


def remove_closed(_dataframe: pl.DataFrame) -> pl.DataFrame:
    return _dataframe.filter(pl.col("EstablishmentName").str.contains("Closed"))


def step_copy(_ctx: StepContext, _files: list[AstroFile]) -> None:
    return None


class FilterPipeline(Pipeline):
    name = "example"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_filter("Remove closed establishments", remove_closed, [EstablishmentsFile()])
        self.add_step(
            "Copy establishments to processed",
            step_copy,
            [EstablishmentsFile()],
            depends_on=["remove-closed-establishments"],
        )


class BranchingPipeline(Pipeline):
    name = "branching"
    execution_mode = ExecutionMode.SERIAL
    ingest_files = [
        IngestFileSpec(
            name="establishments",
            source_pattern="edubase*.csv",
            schema=pa.DataFrameSchema({"URN": pa.Column(str)}, strict="filter"),
        ),
    ]

    def configure_steps(self) -> None:
        self.add_step("Branch A", step_one, [EstablishmentsFile()])
        self.add_step("Branch B", step_two, [EstablishmentsFile()])
        self.add_step(
            "Merge branches",
            step_copy,
            [EstablishmentsFile()],
            depends_on=["branch-a", "branch-b"],
        )


def test_build_flow_graph_includes_ingest_and_dependencies() -> None:
    pipeline = SteppedPipeline()
    graph = build_flow_graph(pipeline)

    assert graph.layers[0][0].node_id == "ingest"
    assert graph.layers[1][0].node_id == "first-step"
    assert graph.layers[2][0].node_id == "second-step"
    assert ("ingest", "first-step") in graph.edges
    assert ("first-step", "second-step") in graph.edges


def test_build_flow_graph_marks_filter_steps() -> None:
    pipeline = FilterPipeline()
    graph = build_flow_graph(pipeline)

    filter_node = next(
        node
        for layer in graph.layers
        for node in layer
        if node.node_id == "remove-closed-establishments"
    )

    assert "filter · establishments" in filter_node.subtitle
    assert pipeline.steps[0].kind is StepKind.FILTER


def test_render_flow_diagram_shows_boxes_and_arrows() -> None:
    diagram = render_flow_diagram(FilterPipeline())

    assert "example (serial)" in diagram
    assert "Ingest" in diagram
    assert "Remove closed establishments" in diagram
    assert "Copy establishments to processed" in diagram
    assert "──►" in diagram
    assert "filter · establishments" in diagram
    assert "step · establishments" in diagram
    assert "┌" in diagram
    assert "└" in diagram


def test_render_flow_diagram_places_parallel_steps_side_by_side() -> None:
    diagram = render_flow_diagram(BranchingPipeline())

    assert "branching (serial)" in diagram
    assert "Branch A" in diagram
    assert "Branch B" in diagram
    assert "Merge branches" in diagram
    branch_a_index = diagram.index("Branch A")
    branch_b_index = diagram.index("Branch B")
    merge_index = diagram.index("Merge branches")
    assert branch_a_index < branch_b_index
    assert branch_a_index < merge_index
    assert branch_b_index < merge_index
    assert "│" in diagram


def test_render_flow_diagram_lists_ingest_file_names() -> None:
    diagram = render_flow_diagram(FilterPipeline())

    assert "establishments" in diagram
