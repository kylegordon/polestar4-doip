#!/bin/sh
# p4: run the read-only DoIP tool in Docker. `./p4 test` runs the offline test suite.
set -eu
ROOT=$(cd "$(dirname "$0")" && pwd)
IMG=p4doip:local

if [ "${1:-}" = "build" ]; then
  exec docker build -t "$IMG" "$ROOT/tool"
fi
docker image inspect "$IMG" >/dev/null 2>&1 || docker build -q -t "$IMG" "$ROOT/tool" >/dev/null
if [ "${1:-}" = "test" ]; then
  shift
  exec docker run --rm --init -v "$ROOT":/w:ro --entrypoint python "$IMG" -m pytest -p no:cacheprovider /w/tool/tests "$@"
fi

# Find the subcommand (first argument that is not a global option or its value).
SUB=""
skip=0
for a in "$@"; do
  if [ "$skip" = 1 ]; then skip=0; continue; fi
  case "$a" in
    --host|--port|--retries|--retry-wait) skip=1 ;;
    -*) ;;
    *) SUB=$a; break ;;
  esac
done

# --init: Ctrl-C, a closed terminal or `docker stop` ends the run at once and frees the gateway.
# /etc/localtime: run dates and timestamps match the laptop clock and the pcap file names.
set -- --rm --init --user "$(id -u):$(id -g)" --network host -e P4_HOST -e P4_PORT \
  -e P4_COMMIT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || true)" \
  -v /etc/localtime:/etc/localtime:ro -v "$ROOT":/w "$IMG" "$@"
# One tester at a time: commands that talk to the car share a container name, so a second one fails fast.
# Listed the other way round (offline commands are exempt) so anything unrecognised takes the lock.
case "$SUB" in
  ""|diff|mark|known|signals|strings|correlate|import-legacy|didmap|similar|scandiff|dtcdiff|ranges|hazards|did|runs|tree|export|report) ;;  # "" = no subcommand (--help)
  *) set -- --name p4-live "$@" ;;
esac
exec docker run "$@"
