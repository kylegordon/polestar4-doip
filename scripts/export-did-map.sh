#!/bin/sh
# Regenerate docs/did-map.csv from runs/. Thin wrapper: `p4 didmap` is the single implementation, so the
# script and the freshness gate in scripts/prepublish-check.sh always agree (no jq/awk copy to drift).
# Usage: scripts/export-did-map.sh [--check]
set -eu
cd "$(dirname "$0")/.."
exec env PYTHONPATH=tool P4_ROOT="$PWD" python3 -B -m p4doip didmap "$@"
