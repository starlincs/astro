"""Rich dashboard for astro run."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable

from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.text import Text

from astro.cli.display.steps import StepStatus, StepTracker
from astro.cli.logging import InMemoryLogBuffer

_STATUS_ICONS = {
    StepStatus.PENDING: ("○", "dim"),
    StepStatus.RUNNING: ("◉", "cyan"),
    StepStatus.COMPLETE: ("✓", "green"),
    StepStatus.FAILED: ("✗", "red"),
    StepStatus.WARNING: ("!", "yellow"),
    StepStatus.QUARANTINED: ("!", "yellow"),
}


class RunDashboard:
    """Three-panel Rich layout: steps, live log, and status bar."""

    def __init__(
        self,
        tracker: StepTracker,
        buffer: InMemoryLogBuffer,
        *,
        console: Console | None = None,
    ) -> None:
        self.tracker = tracker
        self.buffer = buffer
        self.console = console or Console()

    def render_once(self) -> None:
        self.console.print(self.build_layout())

    def run(
        self,
        *,
        refresh_callback: Callable[[], None] | None = None,
        refresh_per_second: float = 4.0,
        minimum_display_seconds: float = 0.25,
    ) -> None:
        if not sys.stdout.isatty():
            self.render_once()
            return

        with Live(
            self.build_layout(),
            console=self.console,
            refresh_per_second=refresh_per_second,
            screen=False,
        ) as live:
            end_time = time.monotonic() + minimum_display_seconds
            while time.monotonic() < end_time:
                if refresh_callback is not None:
                    refresh_callback()
                live.update(self.build_layout())
                time.sleep(1 / refresh_per_second)

    def build_layout(self) -> Group:
        return Group(
            Columns(
                [self._build_steps_panel(), self._build_log_panel()],
                expand=True,
                equal=False,
                column_first=True,
            ),
            self._build_status_panel(),
        )

    def _build_steps_panel(self) -> Panel:
        step_lines: list[Text] = []
        for step in self.tracker.steps:
            icon, style = _STATUS_ICONS[step.status]
            label = step.label if step.detail is None else f"{step.label} ({step.detail})"
            step_lines.append(Text.assemble((f"{icon} ", style), (label, style)))
        if not step_lines:
            step_lines = [Text("No steps defined", style="dim")]
        return Panel(Group(*step_lines), title="Steps", border_style="blue")

    def _build_log_panel(self) -> Panel:
        lines = [self._format_log_record(record) for record in self.buffer.records]
        if not lines:
            lines = [Text("Waiting for log output...", style="dim")]
        return Panel(Group(*lines), title="Live log", border_style="blue", expand=True)

    def _format_log_record(self, record: logging.LogRecord) -> Text:
        message = record.getMessage()
        if record.levelno >= logging.ERROR:
            style = "red"
        elif record.levelno >= logging.WARNING:
            style = "yellow"
        else:
            style = "white"
        formatter = self.buffer.formatter
        timestamp = (
            formatter.formatTime(record, "%H:%M:%S") if formatter is not None else "--:--:--"
        )
        level = record.levelname
        return Text(f"{timestamp} {level:<8} {message}", style=style)

    def _build_status_panel(self) -> Panel:
        message = self.tracker.status_message or "Ready"
        style = "white"
        lower_message = message.lower()
        if "error" in lower_message or "failed" in lower_message:
            style = "red"
        elif "warning" in lower_message or "not implemented" in lower_message:
            style = "yellow"

        renderables: list[RenderableType] = [Text(message, style=style)]
        if self.tracker.progress_percent is not None:
            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                expand=True,
            )
            task_id = progress.add_task("Processing", total=100)
            progress.update(task_id, completed=self.tracker.progress_percent)
            renderables.append(progress)

        return Panel(Group(*renderables), title="Status", border_style="blue")
