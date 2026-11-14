#!/bin/sh
# Fail if anything that must never be published is in the git index or the history.
# Run before every push: scripts/prepublish-check.sh   (also runs in CI)
set -eu
cd "$(dirname "$0")/.."
git rev-parse --git-dir >/dev/null
fail=0

bad_paths=$(git ls-files | grep -i -E '(^|/)(local|runs|captures|external)/|(^|/)NEXT\.md$|\.(pcap|pcapng|cap)$' || true)
if [ -n "$bad_paths" ]; then
  echo "FAIL: tracked paths that must stay local:"; echo "$bad_paths"; fail=1
fi

# Binary files can't be searched for identifiers, so none may be tracked.
binaries=$(git ls-files --eol | awk '$1 == "i/-text" {print $NF}')
if [ -n "$binaries" ]; then
  echo "FAIL: binary files are tracked (this check cannot read them):"; echo "$binaries"; fail=1
fi

# Content patterns: a third-party tool's name (patterns use character classes so this file never matches itself),
# full VINs (Polestar/Volvo/Geely WMIs, as text or hex), SIM ICCIDs, 15-16 digit IMEI/IMEISV, USB adaptor names
# derived from a MAC, international phone numbers and home paths.
patterns='h[a]nterill|enx[0-9a-f]{12}|(YSM|LPS|LRW|YV1)[A-HJ-NPR-Z0-9]{14}|(59534d|4c5053|4c5257|595631)[0-9a-f]{28}|89[0-9]{16,18}|(^|[^0-9a-fA-F])[0-9]{15,16}([^0-9a-fA-F]|$)|\+[1-9][0-9]{1,2}[ -]?[0-9]{2,4}[ -]?[0-9]{3,4}[ -]?[0-9]{3,4}|/hom[e]/[a-z]|/User[s]/|/roo[t]/'

# Index, not working tree: this is what a commit will contain. Exit 1 = no match; anything else is an error.
set +e
hits=$(git grep --cached -n -I -i -E "$patterns")
rc=$?
set -e
if [ "$rc" -gt 1 ]; then echo "ERROR: git grep failed ($rc)"; exit 2; fi
if [ -n "$hits" ]; then
  echo "FAIL: identifying or private content in the index:"; echo "$hits"; fail=1
fi

if [ -n "$(git rev-list -n1 --all)" ]; then
  # Added lines in every commit on every ref, with the leading + stripped so ^ anchors work.
  log=$(git log -p --cc --all --format=)
  # Known false positive, already pushed in ea12ced: two 8-byte DID readings (1A01:EE71) made only of decimal
  # digits, which look like an IMEI to the 15-16 digit pattern. History only, and only that exact whole line.
  # (built from halves so this file does not match the pattern itself)
  a='00020000'; b='00000000'; c='00000100'
  fp="   examples: [{raw: \"$a$c\", value: \"on\"}, {raw: \"$b$c\", value: \"off\"}]}  # first 8 of 200 bytes"
  hist=$(printf '%s\n' "$log" | grep -E '^\+' | grep -v -E '^\+\+\+ ' | cut -c2- | grep -v -x -F "$fp" | grep -n -i -E "$patterns" || true)
  if [ -n "$hist" ]; then
    echo "FAIL: identifying or private content in git history:"; echo "$hist" | head -20; fail=1
  fi
  oldbin=$(git log --all --full-history --numstat --format= | awk -F'\t' '$1 == "-" && $2 == "-" {print $3}' | sort -u)
  if [ -n "$oldbin" ]; then
    echo "FAIL: binary files in git history (cannot be checked):"; echo "$oldbin"; fail=1
  fi
  meta=$(git log --all --format='%an %ae %cn %ce%n%B' | grep -n -i -E "$patterns" || true)
  if [ -n "$meta" ]; then
    echo "FAIL: identifying or private content in commit messages or authors:"; echo "$meta" | head -20; fail=1
  fi
fi

# docs/did-map.csv freshness: only meaningful where runs/ exists (the capture machine); skipped elsewhere.
# Exit 1 from didmap --check = stale map; any other failure (no python3/yaml) is a note, not a gate.
have_scans=""
for f in runs/*/scan-*.jsonl; do
  if [ -e "$f" ]; then have_scans=1; break; fi
done
if [ -n "$have_scans" ] && [ -d tool ] && command -v python3 >/dev/null; then
  didmap_root=$(pwd)
  rc=0
  # The `|| rc=$?` keeps `set -e` from aborting the whole check with a status (2 under dash) when the
  # helper cannot run; a missing tool/ or did-map is reported as a note, not as this script's error.
  (cd tool && P4_ROOT="$didmap_root" python3 -B -c "from p4doip.cli import main; main(['didmap', '--check'])") 2>/dev/null || rc=$?
  if [ "$rc" -eq 1 ]; then
    echo "FAIL: docs/did-map.csv is stale; run ./p4 didmap and commit the result"; fail=1
  elif [ "$rc" -ne 0 ]; then
    echo "NOTE: did-map freshness check did not run (exit $rc)"
  fi
fi

[ "$fail" = 0 ] && echo "prepublish-check: OK"
exit "$fail"
