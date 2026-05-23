"""ASCII flow diagrams for pipeline step dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from astro.pipeline.base import Pipeline
from astro.pipeline.models import StepExecutionMode
from astro.pipeline.steps import StepDefinition

INGEST_NODE_ID = "ingest"
BOX_GAP = 4
RANK_GAP = 3


@dataclass(frozen=True)
class FlowNode:
    node_id: str
    title: str
    subtitle: str


@dataclass(frozen=True)
class FlowGraph:
    layers: tuple[tuple[FlowNode, ...], ...]
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class NodePlacement:
    node_id: str
    box_lines: tuple[str, ...]
    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def bottom_y(self) -> int:
        return self.y + self.height - 1

    @property
    def top_y(self) -> int:
        return self.y


def build_flow_graph(pipeline: Pipeline) -> FlowGraph:
    """Build a layered flow graph from a pipeline definition."""
    ingest_names = ", ".join(spec.name for spec in pipeline.ingest_files)
    ingest_node = FlowNode(
        node_id=INGEST_NODE_ID,
        title="Ingest",
        subtitle=ingest_names,
    )

    step_nodes = {step.step_id: _step_to_flow_node(step) for step in pipeline.steps}
    node_depths: dict[str, int] = {INGEST_NODE_ID: 0}
    edges: list[tuple[str, str]] = []

    for step in pipeline.steps:
        if step.depends_on:
            depth = 1 + max(node_depths[dependency_id] for dependency_id in step.depends_on)
            for dependency_id in step.depends_on:
                edges.append((dependency_id, step.step_id))
        else:
            depth = 1
            edges.append((INGEST_NODE_ID, step.step_id))
        node_depths[step.step_id] = depth

    max_depth = max(node_depths.values())
    layers: list[list[FlowNode]] = [[] for _ in range(max_depth + 1)]
    layers[0] = [ingest_node]
    for step in pipeline.steps:
        layers[node_depths[step.step_id]].append(step_nodes[step.step_id])

    return FlowGraph(
        layers=tuple(tuple(layer) for layer in layers),
        edges=tuple(edges),
    )


def render_flow_diagram(pipeline: Pipeline) -> str:
    """Render the pipeline workflow with dependency connections."""
    graph = build_flow_graph(pipeline)
    header = _pipeline_flow_header(pipeline)
    if _is_linear_chain(graph.layers):
        body = _render_linear_chain(graph.layers)
    else:
        body = _render_branching_workflow(graph)
    return "\n".join([header, "", *body])


def _pipeline_flow_header(pipeline: Pipeline) -> str:
    parts = [pipeline.execution_mode.value]
    if pipeline.step_execution_mode != StepExecutionMode.SERIAL:
        parts.append(f"{pipeline.step_execution_mode.value} steps")
    return f"{pipeline.name} ({', '.join(parts)})"


def _is_linear_chain(layers: tuple[tuple[FlowNode, ...], ...]) -> bool:
    return all(len(layer) == 1 for layer in layers)


def _render_linear_chain(layers: tuple[tuple[FlowNode, ...], ...]) -> list[str]:
    boxes = [_render_box(node.title, node.subtitle) for layer in layers for node in layer]
    if not boxes:
        return []

    height = max(len(box) for box in boxes)
    padded_boxes = [box + [""] * (height - len(box)) for box in boxes]
    title_row = 1

    lines: list[str] = []
    for row_index in range(height):
        separator = " ──► " if row_index == title_row else " " * 5
        lines.append(separator.join(box[row_index] for box in padded_boxes))
    return lines


def _render_branching_workflow(graph: FlowGraph) -> list[str]:
    placements: dict[str, NodePlacement] = {}
    y_cursor = 0
    rank_bounds: list[tuple[int, int]] = []

    for layer in graph.layers:
        x_cursor = 0
        row_height = 0
        layer_placements: list[NodePlacement] = []
        for node in layer:
            box = _render_box(node.title, node.subtitle)
            placement = NodePlacement(
                node_id=node.node_id,
                box_lines=tuple(box),
                x=x_cursor,
                y=y_cursor,
                width=len(box[0]),
                height=len(box),
            )
            layer_placements.append(placement)
            placements[node.node_id] = placement
            x_cursor += placement.width + BOX_GAP
            row_height = max(row_height, placement.height)

        rank_bounds.append((y_cursor, y_cursor + row_height - 1))
        y_cursor += row_height + RANK_GAP

    canvas_width = max(placement.x + placement.width for placement in placements.values())
    canvas_height = y_cursor - RANK_GAP
    canvas = _Canvas(canvas_width, canvas_height)

    for placement in placements.values():
        canvas.blit(placement.x, placement.y, list(placement.box_lines))

    for rank_index in range(len(graph.layers) - 1):
        _route_between_ranks(canvas, graph, placements, rank_index, rank_bounds)

    return canvas.lines()


def _route_between_ranks(
    canvas: _Canvas,
    graph: FlowGraph,
    placements: dict[str, NodePlacement],
    rank_index: int,
    rank_bounds: list[tuple[int, int]],
) -> None:
    current_layer = graph.layers[rank_index]
    next_layer = graph.layers[rank_index + 1]
    current_ids = {node.node_id for node in current_layer}
    next_ids = {node.node_id for node in next_layer}

    rank_bottom = rank_bounds[rank_index][1]
    next_rank_top = rank_bounds[rank_index + 1][0]
    routing_top = rank_bottom + 1
    routing_bottom = max(routing_top, next_rank_top - 1)
    routing_row = (routing_top + routing_bottom) // 2

    transition_edges = [
        (source_id, target_id)
        for source_id, target_id in graph.edges
        if source_id in current_ids and target_id in next_ids
    ]
    if not transition_edges:
        return

    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    for source_id, target_id in transition_edges:
        outgoing.setdefault(source_id, []).append(target_id)
        incoming.setdefault(target_id, []).append(source_id)

    handled_pairs: set[tuple[str, str]] = set()

    for source_id, target_ids in outgoing.items():
        if len(target_ids) <= 1:
            continue
        source = placements[source_id]
        targets = [placements[target_id] for target_id in target_ids]
        _draw_vertical(canvas, source.center_x, source.bottom_y + 1, routing_row)

        span_left = min(target.center_x for target in targets)
        span_right = max(target.center_x for target in targets)
        if source.center_x < span_left:
            _draw_horizontal(canvas, source.center_x, span_left, routing_row)
        elif source.center_x > span_right:
            _draw_horizontal(canvas, span_right, source.center_x, routing_row)

        _draw_horizontal(canvas, span_left, span_right, routing_row)
        for target in targets:
            _draw_vertical(canvas, target.center_x, routing_row, target.top_y - 1)
            canvas.set_char(target.center_x, target.top_y - 1, "▼")
            handled_pairs.add((source_id, target.node_id))

    for target_id, source_ids in incoming.items():
        if len(source_ids) <= 1:
            continue
        target = placements[target_id]
        sources = [placements[source_id] for source_id in source_ids]

        for source in sources:
            _draw_vertical(canvas, source.center_x, source.bottom_y + 1, routing_row)

        span_left = min(source.center_x for source in sources)
        span_right = max(source.center_x for source in sources)
        _draw_horizontal(canvas, span_left, span_right, routing_row)

        if target.center_x < span_left:
            _draw_horizontal(canvas, target.center_x, span_left, routing_row)
        elif target.center_x > span_right:
            _draw_horizontal(canvas, span_right, target.center_x, routing_row)

        _draw_vertical(canvas, target.center_x, routing_row, target.top_y - 1)
        canvas.set_char(target.center_x, target.top_y - 1, "▼")
        for source_id in source_ids:
            handled_pairs.add((source_id, target_id))

    for source_id, target_id in transition_edges:
        if (source_id, target_id) in handled_pairs:
            continue
        source = placements[source_id]
        target = placements[target_id]
        if source.center_x == target.center_x:
            _draw_vertical(canvas, source.center_x, source.bottom_y + 1, target.top_y - 1)
            canvas.set_char(source.center_x, target.top_y - 1, "▼")
            continue

        _draw_vertical(canvas, source.center_x, source.bottom_y + 1, routing_row)
        _draw_horizontal(canvas, source.center_x, target.center_x, routing_row)
        _draw_vertical(canvas, target.center_x, routing_row, target.top_y - 1)
        canvas.set_char(target.center_x, target.top_y - 1, "▼")


def _draw_vertical(canvas: _Canvas, x: int, y_start: int, y_end: int) -> None:
    for y in range(y_start, y_end + 1):
        canvas.set_char(x, y, "│")


def _draw_horizontal(canvas: _Canvas, x_start: int, x_end: int, y: int) -> None:
    for x in range(min(x_start, x_end), max(x_start, x_end) + 1):
        canvas.set_char(x, y, "─")


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self._grid = [[" "] * width for _ in range(height)]

    def blit(self, x: int, y: int, lines: list[str]) -> None:
        for row_offset, line in enumerate(lines):
            for column_offset, character in enumerate(line):
                self.set_char(x + column_offset, y + row_offset, character)

    def get_char(self, x: int, y: int) -> str:
        if 0 <= y < len(self._grid) and 0 <= x < len(self._grid[0]):
            return self._grid[y][x]
        return " "

    def set_char(self, x: int, y: int, character: str) -> None:
        if not (0 <= y < len(self._grid) and 0 <= x < len(self._grid[0])):
            return
        current = self._grid[y][x]
        if current in {" ", character, "│", "─", "┼"} and character == "▼":
            self._grid[y][x] = "▼"
            return
        if current in {" ", character}:
            self._grid[y][x] = character
            return
        if {current, character} == {"│", "─"}:
            self._grid[y][x] = "┼"

    def lines(self) -> list[str]:
        return ["".join(row).rstrip() for row in self._grid]


def _step_to_flow_node(step: StepDefinition) -> FlowNode:
    ingest_names = ", ".join(
        sorted({file_spec.__class__.ingest_name for file_spec in step.file_specs})
    )
    return FlowNode(
        node_id=step.step_id,
        title=step.label,
        subtitle=f"{step.kind.value} · {ingest_names}",
    )


def _render_box(title: str, subtitle: str) -> list[str]:
    content_lines = [title]
    if subtitle:
        content_lines.append(subtitle)
    inner_width = max(len(line) for line in content_lines)
    top = f"┌{'─' * (inner_width + 2)}┐"
    middle = [f"│ {line.ljust(inner_width)} │" for line in content_lines]
    bottom = f"└{'─' * (inner_width + 2)}┘"
    return [top, *middle, bottom]
