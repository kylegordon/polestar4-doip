#!/bin/sh
# Regenerate the static pages every 20 s and serve them. Mount the project read-only at /w and a
# writable volume at /srv (see README). P4_WEB_HOST=0.0.0.0 inside the container; publish it on
# 127.0.0.1 only unless you intend the LAN to see the car data.
set -eu
out=${P4_WEB_OUT:-/srv}
mkdir -p "$out"
cp /web/live.html "$out/live.html"
python /web/gen.py &
exec python /web/server.py
