"""Statistics display formatting tests."""

from __future__ import annotations

from astro.stats.formatting import format_stat_display_message, format_stat_log_message
from astro.stats.models import StatScope


def test_format_stat_log_message_uses_machine_readable_format() -> None:
    message = format_stat_log_message(
        run_id="abcde",
        scope=StatScope.FILE,
        subject="establishments",
        action="row_count",
        value=10,
    )

    assert message == "STAT run=abcde scope=file subject=establishments action=row_count value=10"


def test_format_stat_display_message_for_run_scope() -> None:
    message = format_stat_display_message(
        scope=StatScope.RUN,
        subject=None,
        action="files_ingested",
        value=2,
    )

    assert message == "Stat · files ingested · 2"


def test_format_stat_display_message_for_file_scope() -> None:
    message = format_stat_display_message(
        scope=StatScope.FILE,
        subject="establishments",
        action="row_count",
        value=10,
    )

    assert message == "Stat · establishments · row count · 10"


def test_format_stat_display_message_for_step_scope() -> None:
    message = format_stat_display_message(
        scope=StatScope.STEP,
        subject="validate",
        action="duration_ms",
        value=42,
    )

    assert message == "Stat · validate · duration · 42 ms"
