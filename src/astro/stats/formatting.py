"""Format statistics for logs and CLI display."""

from __future__ import annotations

from astro.stats.models import StatScope


def format_stat_log_message(
    *,
    run_id: str,
    scope: StatScope,
    subject: str | None,
    action: str,
    value: int | float,
) -> str:
    subject_label = subject or "-"
    return (
        f"STAT run={run_id} scope={scope.value} subject={subject_label} "
        f"action={action} value={value}"
    )


def format_stat_display_message(
    *,
    scope: StatScope,
    subject: str | None,
    action: str,
    value: int | float,
) -> str:
    parts = ["Stat"]
    if scope in {StatScope.FILE, StatScope.STEP} and subject:
        parts.append(subject)
    parts.append(_humanize_action(action))
    parts.append(_format_stat_value(action, value))
    return " · ".join(parts)


def log_record_display_message(record: object) -> str | None:
    return getattr(record, "astro_display_message", None)


def _humanize_action(action: str) -> str:
    if action.endswith("_ms"):
        return action[:-3].replace("_", " ") or "duration"
    return action.replace("_", " ")


def _format_stat_value(action: str, value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    if action.endswith("_ms"):
        return f"{value} ms"

    if isinstance(value, int) and abs(value) >= 1000:
        return f"{value:,}"

    if isinstance(value, float):
        return f"{value:g}"

    return str(value)
