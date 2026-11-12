#!/bin/sh
# Publish a discovery-log release: tag main and create a GitHub release whose notes are that version's
# entry in DISCOVERIES.md. No assets. Safe to rerun after a partial failure.
# Usage: scripts/release.sh 2026.11.12
set -eu
cd "$(dirname "$0")/.."
v=${1:?usage: scripts/release.sh <version>, e.g. $(date +%Y.%m.%d)}
echo "$v" | grep -qE '^[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$' || { echo "version must look like YYYY.MM.DD (or YYYY.MM.DD.N)"; exit 1; }

gh auth status >/dev/null 2>&1 || { echo "gh is not logged in"; exit 1; }
gh release view "$v" >/dev/null 2>&1 && { echo "release $v already exists"; exit 1; }
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || { echo "release from main"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
git fetch -q origin main
head=$(git rev-parse HEAD)
[ "$head" = "$(git rev-parse origin/main)" ] || { echo "main is not in step with origin/main"; exit 1; }

# Notes: the lines after "## <v> - <title>" up to the next "## " heading (literal match, no regex).
title=$(awk -v h="## $v - " 'index($0, h) == 1 {print substr($0, length(h) + 1); exit}' DISCOVERIES.md)
[ -n "$title" ] || { echo "DISCOVERIES.md has no '## $v - <title>' entry"; exit 1; }
notes=$(awk -v h="## $v - " 'index($0, h) == 1 {on=1; next} on && /^## / {exit} on' DISCOVERIES.md)
[ -n "$(printf '%s' "$notes" | tr -d '[:space:]')" ] || { echo "the $v entry is empty"; exit 1; }

scripts/prepublish-check.sh

# Tag: reuse one left by an earlier, interrupted run if it points at this commit; refuse otherwise.
remote_tag=$(git ls-remote -q --tags origin "refs/tags/$v^{}" | cut -f1)
[ -n "$remote_tag" ] || remote_tag=$(git ls-remote -q --tags origin "refs/tags/$v" | cut -f1)
if git rev-parse -q --verify "refs/tags/$v" >/dev/null; then
  [ "$(git rev-parse "$v^{commit}")" = "$head" ] || { echo "local tag $v points elsewhere"; exit 1; }
else
  git tag -a "$v" -m "$v - $title"
fi
if [ -n "$remote_tag" ]; then
  [ "$remote_tag" = "$head" ] || { echo "tag $v on origin points elsewhere"; exit 1; }
else
  git push -q origin "refs/tags/$v" || { git tag -d "$v" >/dev/null; echo "tag push failed; local tag removed"; exit 1; }
fi

printf '%s\n' "$notes" | gh release create "$v" --title "$v - $title" --notes-file - --verify-tag ||
  { echo "release create failed; the tag is pushed, so rerun scripts/release.sh $v"; exit 1; }
echo "released $v"
