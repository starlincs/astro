"""SQLite-backed store for pipeline run statistics."""

from pathlib import Path


class PipelineStore:
    """Local persistent store for pipeline statistics."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path.cwd() / ".astro" / "stats.db"

    def initialize(self) -> None:
        """Create the database schema if it does not exist."""
        ...

    def record_run(self, pipeline_name: str, **stats: object) -> None:
        """Record statistics for a pipeline run."""
        ...

    def list_runs(self, pipeline_name: str | None = None) -> list[dict[str, object]]:
        """Return stored run statistics, optionally filtered by pipeline name."""
        return []

    def cleanup(self, pipeline_name: str | None = None) -> None:
        """Remove stored statistics for one or all pipelines."""
        ...
