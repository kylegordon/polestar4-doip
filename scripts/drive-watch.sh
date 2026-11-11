#!/bin/bash
# Next drive: fast watch of power, speed and controls (~1 s per pass). Live view: http://localhost:8088/live.html
# Mark events from a second terminal: ./p4 mark "one-pedal 2"
cd "$(dirname "$0")/.." || exit 1
exec ./p4 watch \
  1635:4802,497C,4801,4947 \
  1631:D003,E312 \
  1A01:4223,4224,42E7,DD0A \
  1672:3019,301A \
  1614:D90F,D93A \
  1637:EEC4 \
  1BB3:7022 1BB4:7022 \
  --baseline 0 --show-first --interval 0 --name drive-fast "$@"
