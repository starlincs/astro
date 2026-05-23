"""Ingest validation helpers."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from astro.pipeline.models import IngestFileSpec


@dataclass(frozen=True)
class MatchedIngestFile:
    spec: IngestFileSpec
    source_path: Path


class IngestValidationError(ValueError):
    """Raised when source directory contents do not match pipeline ingest config."""


def match_ingest_files(
    source_directory: Path,
    ingest_files: list[IngestFileSpec],
) -> list[MatchedIngestFile]:
    if not source_directory.is_dir():
        raise IngestValidationError(f"Source path is not a directory: {source_directory}")

    entries = list(source_directory.iterdir())
    if any(entry.is_dir() for entry in entries):
        raise IngestValidationError("Source directory must contain files only.")

    source_files = [entry for entry in entries if entry.is_file()]
    matched_paths: set[Path] = set()
    matches: list[MatchedIngestFile] = []

    for spec in ingest_files:
        pattern_matches = [
            path
            for path in source_files
            if fnmatch.fnmatch(path.name, spec.source_pattern) and path not in matched_paths
        ]
        if not pattern_matches:
            raise IngestValidationError(
                f"No source file matched pattern {spec.source_pattern!r} for {spec.name!r}."
            )
        if len(pattern_matches) > 1:
            matched_names = ", ".join(path.name for path in pattern_matches)
            raise IngestValidationError(
                f"Expected exactly one source file for {spec.name!r}, "
                f"found multiple matches: {matched_names}."
            )
        matched_path = pattern_matches[0]
        matched_paths.add(matched_path)
        matches.append(MatchedIngestFile(spec=spec, source_path=matched_path))

    unmatched_files = [path for path in source_files if path not in matched_paths]
    if unmatched_files:
        unmatched_names = ", ".join(path.name for path in unmatched_files)
        raise IngestValidationError(
            f"Unexpected files found in source directory: {unmatched_names}."
        )

    return matches
