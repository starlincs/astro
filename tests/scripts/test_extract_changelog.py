"""Tests for changelog release-note extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.extract_changelog import extract_release_notes


def test_extract_release_notes_for_1_1_0() -> None:
    notes = extract_release_notes("1.1.0")

    assert "### Added" in notes
    assert "CsvChunkWriter" in notes
    assert "### Changed" in notes
    assert "Failed ingest now removes" in notes


def test_extract_release_notes_for_1_0_0() -> None:
    notes = extract_release_notes("1.0.0")

    assert "First stable release" in notes


def test_extract_release_notes_rejects_unknown_version(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [Unreleased]\n\n## [1.0.0] - date\n\n### Added\n\n- Initial\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No changelog section"):
        extract_release_notes("9.9.9", changelog_path=changelog)
