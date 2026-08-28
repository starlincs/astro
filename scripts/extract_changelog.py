"""Extract GitHub release notes for one version from CHANGELOG.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"


def extract_release_notes(version: str, *, changelog_path: Path = CHANGELOG_PATH) -> str:
    """Return the body for one released version (sections under the version heading)."""
    normalized = version.removeprefix("v")
    text = changelog_path.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(normalized)}\].*?\n(.*?)(?=^## \[|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        msg = f"No changelog section found for version {normalized!r} in {changelog_path}"
        raise ValueError(msg)
    return match.group(1).strip() + "\n"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} VERSION")

    print(extract_release_notes(sys.argv[1]), end="")


if __name__ == "__main__":
    main()
