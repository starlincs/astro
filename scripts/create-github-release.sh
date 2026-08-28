#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: create-github-release.sh VERSION

Create or update a GitHub release for an existing tag using CHANGELOG.md.

Examples:
  ./scripts/create-github-release.sh 1.1.0
  ./scripts/create-github-release.sh v1.0.0
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -ne 1 ]]; then
  usage
  exit "${1:+0}" 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1#v}"
TAG="v${VERSION}"
NOTES="$(python "${ROOT}/scripts/extract_changelog.py" "${VERSION}")"

if gh release view "${TAG}" >/dev/null 2>&1; then
  gh release edit "${TAG}" --title "${VERSION}" --notes "${NOTES}"
  echo "Updated GitHub release ${TAG}"
else
  gh release create "${TAG}" --title "${VERSION}" --notes "${NOTES}"
  echo "Created GitHub release ${TAG}"
fi
