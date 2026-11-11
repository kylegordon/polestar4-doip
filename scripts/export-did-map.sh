#!/bin/bash
# Regenerate docs/did-map.csv from the scan results in runs/: every DID that answered (or exists but refused),
# per module, with its response length. No values are exported. Needs jq. Refuses to overwrite with nothing.
set -euo pipefail
cd "$(dirname "$0")/.."
shopt -s nullglob
files=(runs/*/scan-*.jsonl)
[ ${#files[@]} -gt 0 ] || { echo "no runs/*/scan-*.jsonl here; nothing exported" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is needed" >&2; exit 1; }
mkdir -p docs
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
{
  echo "module,did,status,length_bytes,nrc"
  cat "${files[@]}" | jq -r 'select(.did and .tgt) | [.tgt, .did, .status, ((.data // "") | length / 2 | floor), (.code // "")] | @tsv' |
    awk -F'\t' '{k=$1":"$2; r=($3=="ok")?2:(($3=="nrc")?1:0); if(!(k in best) || r>=rank[k]){best[k]=$0; rank[k]=r}}
               END{for(k in best) print best[k]}' |
    awk -F'\t' '$3=="ok" || ($3=="nrc" && ($5=="22" || $5=="33"))' |
    sort | awk -F'\t' 'BEGIN{OFS=","} {if($3=="ok") $5=""; else $4=""; print $1,$2,$3,$4,$5}'
} > "$tmp"
n=$(($(wc -l < "$tmp") - 1))
[ "$n" -gt 0 ] || { echo "export produced no DIDs; docs/did-map.csv left unchanged" >&2; exit 1; }
mv "$tmp" docs/did-map.csv
trap - EXIT
echo "docs/did-map.csv: $n DIDs"
