# DID-transfer confirming sessions (A-D) and offline settling

The per-candidate confirming tests (ledger T01-T34 in [did-ledger.md](did-ledger.md)), compiled into the
minimum set of car sessions plus the offline work over already-recorded `runs/` data: one section per
session, each a step-by-step runbook for one person, ordered by candidates unlocked per car-minute. Letters
are fixed labels; run in the table's order. Nothing here is in the catalogue yet — a transfer stays at most
P until its own test passes on that module, and C needs the same change seen twice in both directions with
the action noted (`catalogue/signals.yaml:5`; one pass is not confirmation, `docs/findings.md:91`), so every
session works each stimulus twice each way. After a session, finalise the drafts named in its Follow-up and
paste them into [did-entries.md](did-entries.md), then log the session in `DISCOVERIES.md`.

House rules, every session ([README.md:15-17](../README.md), [AGENTS.md](../AGENTS.md)):

- Read-only tool only; one tester at the gateway (`docker stop p4-live` frees it). Disconnect any other diagnostic tool first.
- **Never read `EE13` on `1301`** — it knocked the Mobileye ECU off the network twice. The tool refuses it
  (`BLOCKED_READS`, `tool/p4doip/client.py:20`), and no command below schedules it: every watch names its
  DIDs explicitly, and `snapshot 1301` is safe because `1301`'s scan stopped before `EE13` on purpose, so it
  is not in the known-OK set the snapshot reads. Watch specs must not include blocked DIDs; none below do.
- Parked sessions: car in P, ignition on as noted, 12 V battery in good health, laptop on charger. The drive
  session: a passive watch of known DIDs only; nothing is typed while moving — `./p4 mark` at a stop.
- Watch syntax: one module per spec — `1631:D003 1637:D003`, not `1631:D003,1637:D003`. The comma form across
  modules is rejected with a clear error by `parse_watch_specs`; the confirming commands in the old transfer
  tables (now folded into [did-ledger.md](did-ledger.md)) predate this correction and are corrected here.
- Hazards: `1301:EE13` is blocked; `1601:D928`-`D92C` are caution in `catalogue/hazards.yaml`. A normal scan
  skips caution rows; this runbook's paced/one-at-a-time steps may use `--allow-caution` when it needs them.
- `./p4 mark` is offline and works while a watch runs. `./p4 correlate <date>` afterwards prints each mark's
  watch CHANGE lines (-2/+15 s by default).

## Run order (candidates unlocked per car-minute)

| # | Session | Candidate rows | Car time | Rate |
|---|---|---|---|---|
| 1 | Session D — diffs over already-recorded `runs/` | 7 (T20-T23, T31-T33) + the DD01/DD0A widening (T35/T36, already applied); offline first-pass checks for T01-T07, T12, T19, T24, T27, T28, T30, T34; no-recorded-stimulus verdicts for T13-T18 | 0 min | highest by far |
| 2 | Session B — parked: EPB, seats, mirror, rail swing | 13 (T08-T19, T34; T08-T11 already integrated, re-verified) | ~28 min | ~0.46/min |
| 3 | Session A — drive: drive units + steering | 7 (T01-T07; T02 may already be landed at P, T04 may settle offline first) | ~26 min | ~0.27/min |
| 4 | Session C — charge + temperature | 7 (T24, T27-T30; T25/T26/T29 expected ruled out) | ~30 min (+5 min next morning) | ~0.23/min |

---

## Session D — offline diffs over recorded runs/ data (no car needed, capture machine)

7 rows, 0 min of car time, plus the zero-risk DD01/DD0A widening (T35/T36). Everything happens on the machine
holding `runs/`; `diff` and `grep` never touch the car. This session also carries the full per-candidate
settling procedures for the capture machine: first-pass checks for the car-session rows (T01-T07, T12, T19,
T24, T27, T28, T30, T34) and the no-recorded-stimulus verdicts (T13-T18).

**Every command here is offline and runs on the capture machine where `runs/` lives** (git-ignored; this
analysis repo cannot see it). `known`, `diff`, `mark`, `signals`, `strings` and `correlate` never talk to the
car (README: tool table); jq/python here only read `runs/`. No container, no gateway, no car time.

Markers (what the recorded data can do with a row): **CONFIRM** = recorded data confirms it; **RULE-OUT** =
recorded data kills it (length rows are already settled); **BOTH** = recorded data settles it either way;
**BOTH\*** = settles either way once the D0 precheck or grep shows the needed records exist; **NOTHING** = no
recorded stimulus, needs the session as written in the runbooks below.

House rules that apply here too: a snapshot-sourced pass is at most P unless the change is seen twice each
way with the action noted (`catalogue/signals.yaml:8`); for a monotonic counter, equal deltas on two
separate occasions are the equivalent; never read `EE13` on `1301` — nothing below does, and `snapshot`
only ever polls known-OK DIDs with blocked reads excluded (`tool/p4doip/store.py:76`). Do not paste
identity DIDs (part numbers, serials, VIN) into findings; the commands read value DIDs only.

### Records on the capture machine

- `runs/<date>/scan-<TGT>.jsonl` — one record per DID per scan run: `{t, tgt, did, status, data}` with the
  stored payload hex (`tool/p4doip/cli.py:317`). `./p4 known <addr> --list` prints the latest value per DID.
- `runs/<date>/snap-<name>.json` — `{t, values: {"TGT:DID": hex}}`; the VIN is stored as zeros
  (`cli.py:29`). Nine snapshots hold `1635` (the DA31 sums, `docs/findings.md:129`), eleven hold `1A01`
  on 2026-11-13 (`docs/findings.md:188`), across parked and other states and several days.
- `runs/<date>/watch-<name>.log` — `HH:MM:SS TGT:DID [CHANGE] old -> new` lines; drive watches exist for
  2026-11-12/13. The drive list (`scripts/drive-watch.sh:6-12`) polls `1631:D003` and `1672:3019` but none
  of the other candidate keys, so most drive rows below hinge on whether a custom watch covered them.
- `./p4 diff a b` resolves a bare name to its most recent day (`cli.py:377`); pass explicit paths when a
  name exists on several days: `./p4 diff runs/2026-11-13/snap-a.json runs/2026-11-13/snap-b.json`.

### D0 — inventory (run once, then work from its output)

List what is recorded: `ls runs/*/snap-*.json`. Pick, where they exist:

- the **EE13 pair** (D3): two snapshots of `1635 1650 1656 1601` that bracket a discharge (times span a
  drive; `1635:EE13` differs between them). Names `d0`/`d1` if they were recorded that way.
- the **EE02 pairs** (D5): two load-on/load-off pairs of `1635 1650 1C01 1301 1601` — four snapshots, on /
  off / on / off. Names `a`/`b` and a second pair, if recorded that way.

Then show which snapshots contain each candidate key:

```sh
for f in runs/*/snap-*.json; do
  echo "== $f $(jq -r .t "$f")"
  jq -r '.values | to_entries[]
        | select(.key | test("^(1635|1650|1656|1601|1701|1670|1672|1676|1637|1631|1301|1C01|1A01|1A13):(EE13|EE71|EE72|EE02|EE07|D112|2B20|3019|D003|E307|E319|F442|FE0D)$"))
        | "  \(.key)=\(.value)"' "$f"
done
```

A row below needs both sides present in at least two snapshots (or a snapshot plus a scan record on the
same non-charging day). Keys absent everywhere move their row to the grep tests in D10 or to NOTHING.

Diff with explicit paths. Bare names resolve per name to the most recent day (`find_snapshot`,
`tool/p4doip/cli.py:377`), which can mix days when a name was reused:

- `./p4 diff runs/<day>/snap-d0.json runs/<day>/snap-d1.json`
- `./p4 diff runs/<day>/snap-a.json runs/<day>/snap-b.json` (and the second pair)

### D1 — `DD01`/`DD0A` widening (T35/T36) — CONFIRM (2 items, minutes, up to 78 labels) — already applied

Any snapshot in which every module's `DD01` equals the odometer and every `DD0A` equals the power mode read
on `1A01` settles it (ledger T35/T36).

```sh
jq -r '.values as $v | .t as $t |
  [$v | to_entries[] | select(.key | test(":DD01$")) | .value] as $odo |
  [$v | to_entries[] | select(.key | test(":DD0A$")) | .value] as $pm |
  select(($odo | unique | length) > 1 or ($pm | unique | length) > 1) |
  "\($t): DD01 \($odo | join(",")) / DD0A \($pm | join(","))"' runs/*/snap-*.json
```

Quick check, one snapshot at a time: `grep -h ':DD01"' runs/<day>/snap-<name>.json | sort -u` (one line =
pass; repeat for `DD0A`; if `DD0A` shows several power states, try another snapshot). If it holds, widen
both signals' `module` field from `1A01` to all 40 modules — 78 labels, no car session.

Pass: no output across all snapshots — every module agreed at every recorded moment. Fail: each line names
the day and the odd values; exclude those modules. Record in `docs/findings.md` ("Common to every module"
paragraph) and widen the `module:` lists at `catalogue/signals.yaml:150-153`; `DD00` has no decode, nothing
to widen. No per-module test beyond this trivial check is claimed.

Status: already in place — `catalogue/signals.yaml:150-153` list all 40 addresses; kept for the record.

### D2 — length rule-outs (T23, T25, T26, T29, T33) — RULE-OUT (5 rows, already settled)

A 1- or 2-byte answer cannot hold the decode; the recorded length ends these permanently (the length rule
in [did.md](did.md)): `1601:EE13` 2 B vs the u32 mAh (T33), `1601:EE02` 1 B (T23) and `1650:EE07` 1 B (T26)
vs the u16, `1601:EE07` 1 B (T25) vs the u16 x 0.01 - 50, `1635:EE72` 1 B (T29) vs the u16 W
(`docs/did-map.csv` rows 1662, 1645, 2351, 1650, 2180; confirmed 2026-11-13). Belt-and-braces check of the
stored hex in any snapshot that has these modules (D0 shows which), or straight from the scan records —
length = half the hex characters:

```sh
jq -r '.values | to_entries[]
      | select(.key | test("^(1601:EE13|1650:EE07|1635:EE72|1601:EE02|1601:EE07)$"))
      | "\(.key)=\(.value)"' runs/<latest>/snap-<name>.json
./p4 known 1601 --list | grep -E "EE13|EE02|EE07"
```

Pass (ruled out): hex length shorter than the decoded span. The single bytes could still be coarser
encodings (a 0.1 V-step supply like the `D904` lead, a 1 °C temperature), but that is a different
hypothesis, not this transfer. Record: the rows are ruled out in the ledger (T23, T25, T26, T29, T33); also
note them in the module sections of `docs/findings.md`, citing the lengths.

### D3 — `EE13` discharge counter `1635` -> `1650`, `1656` (T31/T32), `1601` (T33) — BOTH (the flagship)

`1650:EE13` is 4 B, `1656:EE13` 5 B (first four bytes compared), same span as the u32 mAh (T31/T32). The
counter only moves with discharge, so between any two snapshots that straddle a drive, the candidate's u32
must rise by exactly what `1635:EE13` rose. Nine `1635` snapshots across days exist; 2026-11-13 had drives.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    out = []
    for k in ("1635:EE13", "1650:EE13", "1656:EE13"):
        try: out.append("%s=%d" % (k, int(v[k][:8], 16)))   # first 4 bytes
        except (KeyError, ValueError): pass
    if len(out) > 1: print(d["t"], " ".join(out))
'
grep -h "\"did\": \"EE13\"" runs/*/scan-1635.jsonl runs/*/scan-1650.jsonl runs/*/scan-1656.jsonl
```

Pass: oldest vs newest snapshot of the drive day — and every other straddling pair — equal deltas, in mAh,
on each candidate; two pairs spanning separate drives = the C bar for a counter. Fail: any pair where
`1635` rose and the candidate rose by a different amount or not at all — a trap, ruled out. A pair with
zero delta on both sides proves nothing (no discharge between them); skip it. Record: on pass, `EE13`
joins the catalogue on `1650` (4 B) and `1656` (offset 0, len 4 of 5 B), confidence per the rule above,
citing the snapshot names; `1656`'s DC-DC guess (`docs/findings.md:153`) gains its first shared quantity
with the BECM. The `grep` lines are extra points (1635/1650 data = 4 B, 1656 = 5 B).

### D4 — `EE71` lifetime AC charge energy `1650` -> `1635`, `1A01` (T27/T28) — BOTH

First three bytes of each block are the u24 x 0.1 kWh counter (T27/T28; `1635` 24 B, `1A01` 200 B). A
lifetime counter never falls, so two modules holding the same one must be equal at every recorded moment —
no charge watch needed.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    out = []
    for k in ("1650:EE71", "1635:EE71", "1A01:EE71"):
        try: out.append("%s=%d" % (k, int(v[k][:6], 16)))   # first 3 bytes
        except (KeyError, ValueError): pass
    if len(out) > 1: print(d["t"], " ".join(out))
'
```

Pass: equal at every line (across days; if a charge fell between two snapshots both sides must rise by the
same counts). Fail: any disagreement at a shared moment — ruled out. Scan-record fallback: same-day
`scan-1650.jsonl` / `scan-1635.jsonl` / `scan-1A01.jsonl` values are comparable only if no charge happened
between them (`grep -h "\"did\": \"EE71\"" runs/*/scan-*.jsonl` per module). Record: widen
`charge_energy_counter` to `1635` (offset 0, len 3 of 24 B) and `1A01` (offset 0, len 3 of 200 B), citing
snapshots.

### D5 — `EE02` 12 V rail `1635` -> `1650`, `1C01`, `1301` (T20/T21/T22), `1601` (T23) — BOTH

`1650:EE02` 2 B, `1C01:EE02` 35 B, `1301:EE02` 64 B; only the first two bytes are compared (T20-T22). The
recorded snapshots span standby and car-on states, so the rail-swing pair the ledger asks for comes free
from day-to-day variation.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    out = []
    for k in ("1635:EE02", "1650:EE02", "1C01:EE02", "1301:EE02"):
        try: out.append("%s=%.3f" % (k, int(v[k][:4], 16) / 1000))
        except (KeyError, ValueError): pass
    if len(out) > 1: print(d["t"], " ".join(out))
'
```

Pass: at every moment each candidate's u16 x 0.001 V sits within a few tens of mV of `1635:EE02` (the
catalogue already accepts 40 mV against `4947`, `catalogue/signals.yaml:161`), and the pair moves in step
across snapshots with different rails — a down and an up swing across the set is the "twice each way"
(dips with loads on, recovers off). Fail: static while the rail moves, or drifting away — different
content, ruled out. `EE02` -> `1601` (T23): 1 B — passes only if it tracks the rail in ~0.1 V steps (the
`D904` lead pattern, `docs/findings.md:12`); expected ruled out. Record: widen `low_volt_rail_bms` per
module citing snapshots; for `1C01`/`1301` say "first two bytes only".

### D6 — `EE07` outside temperature `1635` -> `1301` (T24) — BOTH

Bytes 0-1 of the 33 B block against the u16 x 0.01 - 50 decode (T24); snapshots hours or days apart span
engine-bay-warm vs cold-soaked. The test is relative, so the unchecked -50 offset does not matter.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    try: print(d["t"], "1635=%.2f" % (int(v["1635:EE07"][:4], 16) * 0.01 - 50),
                "1301=%.2f" % (int(v["1301:EE07"][:4], 16) * 0.01 - 50))
    except (KeyError, ValueError): pass
'
```

Pass: the same temperature at every moment (within a few raw counts), including a warm-vs-cold pair.
Fail: `1301` drifts away while `1635` tracks the weather — a module-local temperature, the trap pattern;
ruled out. If `runs/` holds only one `1301:EE07` moment, needs the two-snapshot session (Session C2).
Safety note: this reads `1301` only through recorded snapshots; never extend any command on `1301` to
`EE13`.

### D7 — `EE72` last-charge average power `1650` -> `1A01` (T30) — BOTH (weak source)

First two bytes of the 50 B block against the u16 W decode (T30). `EE72` only changes after a charge, so
equality across snapshots is expected content, not coincidence.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    try: print(d["t"], "1650=%d W" % int(v["1650:EE72"], 16),
                "1A01[:2]=%d" % int(v["1A01:EE72"][:4], 16))
    except (KeyError, ValueError): pass
'
```

Pass: equal at every recorded moment. Fail: differs — ruled out. On a pass the candidate is still only a
lead: `EE72`/`EE74` are themselves weak (`docs/findings.md:149`). Record accordingly.

### D8 — `D112` supply voltage `1C01` -> `1301` (T12) — BOTH\*

The four siblings were integrated from recorded data exactly this way (DISCOVERIES 2026.11.13); `1301` is
the last row (T12). Needs `1301` in snapshots (D0) or in a parked watch log.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    try:
        print(d["t"], "1301=%.2f" % (int(v["1301:D112"], 16) * 0.08),
              "1C01=%.2f" % (int(v["1C01:D112"], 16) * 0.08),
              "F442=%.2f" % (int(v["1701:F442"], 16) / 1000),
              "4947=%.2f" % (int(v["1635:4947"][:4], 16) / 1000))
    except (KeyError, ValueError): pass
'
grep -l "1301:D112" runs/*/watch-*.log
```

Pass: `1301:D112` x 0.08 agrees with `1701:F442` and `1C01:D112` within a few hundredths at every moment,
including lower-rail (standby) and higher-rail (car on) snapshots — a down and an up swing with the rail.
Fail: not the rail — ruled out. Record: on pass, add `1301` to `srs_supply_v` (`catalogue/signals.yaml:269`)
as P citing the snapshots; the watched loads-on/off pass (Session B3) remains the C route.

### D9 — `2B20` EPB operation counter `1601` -> `1701` (T19) — BOTH\*

4 B counters both sides (T19); each drive day adds automatic EPB releases on every P<->D shift, so
snapshots spanning drive days must show equal deltas. Needs `1701` in snapshots.

```sh
python3 -c '
import json, glob
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    try: print(d["t"], "1601=%d" % int(v["1601:2B20"][:8], 16),
                "1701=%d" % int(v["1701:2B20"][:8], 16))
    except (KeyError, ValueError): pass
'
```

Pass: over each pair straddling drive days, both counters rise by the same delta; equal deltas on two
separate day-pairs = the C bar for a counter. Static-equal pairs prove nothing. Fail: deltas differ —
ruled out (the shared-DID trap the ledger's parking-brake preamble warns about). Record: widen
`epb_operations` citing the snapshot pairs.

### D10 — drive and mirror rows that hinge on watch logs (T01-T07, T34) — BOTH\* or NOTHING

`scripts/drive-watch.sh` polls only `1631:D003` and `1672:3019` of these keys, so first find whether any
custom watch covered the candidate side:

```sh
grep -lE "1637:D003|1631:E307|1631:E319|1601:E307|1601:E319|1670:3019|1676:3019|1A13:FE0D" \
  runs/*/watch-*.log
```

No hit = NOTHING for that row (needs the session as written in the runbooks below). A hit: pull the paired
lines and score against the criteria — timestamps let both sides be lined up pass by pass.

| Candidate | Command on a hit | Pass / fail |
|---|---|---|
| `D003` -> `1637` (T01) | `grep -h -e 1631:D003 -e 1637:D003 runs/<date>/watch-<name>.log` | `1637` raw equals `1631` raw (x 0.0140625 km/h) at every speed, 0 parked, up and back; a whole drive both ways = C bar; a mismatch = ruled out |
| `E307` -> `1631` (T02) | `grep -h -e 1631:E307 -e 1637:E307 runs/<date>/watch-<name>.log` | `1631` `02` on each pull-away burst and `01` again while cruising (Range) while `1637` stays `02` through R/D (`docs/findings.md:114` already shows the pull-away half from recorded drives); cruise half missing = still P |
| `E319` -> `1631` (T04) | `grep -h -e 1631:E319 -e 1637:E319 -e 1635:4802 runs/<date>/watch-<name>.log` | `1631:E319` flips `00`/`01` in step with `1637`'s 25 flips and the pack-current sign (`docs/findings.md:141`); two mismatches = ruled out |
| `E307`, `E319` -> `1601` (T03/T05) | `grep -h -e 1601:E307 -e 1601:E319 runs/<date>/watch-<name>.log` | Only parked-cycle consistency can come from logs; drives decide — expect no hit, NOTHING |
| `3019` -> `1670`, `1676` (T06/T07) | `grep -h -e 1670:3019 -e 1672:3019 -e 1676:3019 runs/<date>/watch-<name>.log` | `1670` within the small encoding offset of `1672` and `1676` alongside, through a full lock-to-lock sweep both ways; without a sweep in the log, snapshot equality below can rule out but not confirm |
| `FE0D` -> `1A13` (T34) | `grep -h -e 1A12:FE0D -e 1A13:FE0D runs/2026-11-12/watch-mirrors.log` | Left raw 1-2 at rest, about `0x40`-`0x4b` while moving, on both fold and unfold — the same evidence the right side got (`catalogue/signals.yaml:77`); no hit = NOTHING (repeat the left fold test) |

Snapshot fallback for the steering rows (partial: equal raws at shared moments rule out; confirm still
needs the drive):

```sh
python3 -c '
import json, glob
sgn = lambda x: x - (1 << 16) if x >= (1 << 15) else x
for f in sorted(glob.glob("runs/*/snap-*.json")):
    d = json.load(open(f)); v = d["values"]
    out = []
    for k in ("1672:3019", "1670:3019", "1676:3019"):
        try: out.append("%s=%d" % (k, sgn(int(v[k], 16))))
        except (KeyError, ValueError): pass
    if len(out) > 1: print(d["t"], " ".join(out))
'
```

`1670` and `1676` decode equal at every moment (they did minutes apart once, `docs/findings.md:175`) and
near `1672`; any `1670` vs `1676` disagreement kills one of them as the angle. `1672`'s own decode is P
with an approximate scale (`catalogue/signals.yaml:95`), so a pass lands as P and names the offset.

### D11 — NOTHING from recorded data (T13-T16 seats, T17/T18 EPB — 6 rows)

`40A3`/`40A8` -> `1A27` and -> `1A29` (T13-T16): no recorded stimulus ever moved the driver or rear seats;
the only reads are parked scan records, and static equality proves nothing
(`grep -h "\"did\": \"40A3\"" runs/*/scan-1A27.jsonl` if you want the values anyway). `2B1A` and `2B15`
-> `1701` (T17/T18): the recorded EPB watches were of `1601` only, and parked snapshots would all show the
applied state — the Session B1 watch is unavoidable. `2B20` above (D9) is the one EPB row that recorded
data can move. Record: the rows stay pending in the ledger (T13-T18), noting "no recorded stimulus" so
nobody re-derives them.

### After each settled row

- `docs/findings.md`: move the claim into the module's Signals (with C/P per the rule that applied) or
  Not-found/trap note, citing the snapshot names or watch log used (e.g. "equal deltas with `1635:EE13`
  across `runs/2026-11-13/snap-d0.json`/`snap-d1.json`").
- `catalogue/signals.yaml`: add or widen only per the confidence actually earned; the tests check every
  example, so quote real raws from the snapshot output.
- The ledger ([did-ledger.md](did-ledger.md)): move the row's status per the outcome; add ruled-out
  content rows to the divergence-trap list in [did.md](did.md) only where content (not just length)
  disagreed.
- No `runs/` file is ever committed; nothing here produced car traffic, so no hazard note is needed.

### Missing pairs

A missing pair (e.g. nothing brackets a drive) is not doable offline: record it in one command each at the
next car session — `./p4 snapshot d0 1635 1650 1656 1601` before setting off, `./p4 snapshot d1 1635 1650 1656 1601`
after — then rerun the diff (D3).

Never attempt `EE13` on `1301` anywhere. No snapshot in this section reads `1301` for `EE13`; its `EE02` read is a different DID and safe.

**Follow-up**: finalise and paste into [did-entries.md](did-entries.md) the drafts for the EE13 rows
(`1635`->`1650` T31, `1635`->`1656` T32, `1635`->`1601` T33) and the EE02 rows (`1635`->`1650` T20,
`1635`->`1C01` T21, `1635`->`1301` T22, `1635`->`1601` T23); plus the DD01/DD0A widening edit in
`catalogue/signals.yaml` (not an entries draft; T35/T36 already applied).

---

## Session B — parked, car on: EPB trio, seats, mirror, rail swing

13 rows (T08-T19, T34), ~28 min. Car in P throughout except the gear shifts; ignition on.

### B1 EPB trio via five P<->D shifts (~5 min) — T17, T18, T19

1. `./p4 watch 1601:2B1A,2B15,2B20 1701:2B1A,2B15,2B20 --interval 0.2 --baseline 0 --name epb-transfer`
2. Foot on brake. Five full P<->D cycles, the automatic EPB release on shifting out of P and apply on
   returning to P (`docs/findings.md:89`). Mark each shift: `./p4 mark "P>D 1"`, `./p4 mark "D>P 1"`, ... through `5`.
3. Ctrl-C.

Pass criteria:

- T17 `1701:2B1A` steps through the same four states in step with `1601:2B1A` on all five shifts. `1601`'s
  value map: `00000100` applied, `00000800` releasing, `00000200` applying, `00000400` released
  (`catalogue/signals.yaml:83-85`). `1701` answers 2 B against `1601`'s 4 B: expect the low two bytes
  (`0100`/`0800`/`0200`/`0400`), but any constant-per-state 2 B that follows the same sequence passes. Five
  releases and five applies = both directions, five times.
- T18 `1701:2B15` reads `00` applied / `03` moving / `01` released in step with `1601:2B15` on every shift.
- T19 `1701:2B20` gains exactly one on each release, in step with `1601:2B20` (net +5 over the session).

### B2 seats `40A3`/`40A8` + mirror `FE0D` (~10 min) — T13, T14, T15, T16, T34

1. `./p4 watch 1A27:40A3,40A8 1A28:40A3,40A8 1A29:40A3,40A8 1A13:FE0D,4052 --interval 0.2 --baseline 0 --name seats-mirror`
2. Driver seat via the forward switch: full fore (switch held), `./p4 mark "seat fwd 1"`; full aft, `./p4 mark "seat aft 1"`; once more (`fwd 2`, `aft 2`).
3. Rear bench: a passenger shifts position a few times; `./p4 mark "bench shift 1"`, ... If the watch shows no
   `1A29` change: `./p4 snapshot s1 1A29`, passenger shifts, `./p4 snapshot s2 1A29`, `./p4 diff s1 s2`.
4. Left mirror: fold, `./p4 mark "mirror fold L 1"`; unfold, `./p4 mark "mirror unfold L 1"`; once more.
5. Ctrl-C.

Pass criteria:

- T13 `1A27:40A3` (offset 6, len 2): steps with seat movement and rises moving forward — fore above aft, twice
  each way, same decode as `1A28` (`catalogue/signals.yaml:129`).
- T15 `1A27:40A8` (offset 1, len 1): bit `40` of byte 1 set only while the forward switch is held — set on at
  least two presses, clear on each release (`catalogue/signals.yaml:131`).
- T14/T16 `1A29:40A3`/`40A8`: any step while the passenger moves counts (`40A3` is 16 B here against `1A28`'s
  14 B — the offset may sit elsewhere; look for a 2-byte field that steps, rising forward). If the snapshot
  diff shows nothing either, leave unlabelled.
- T34 `1A13:FE0D`: `0001`-`0002` at rest, `0040`-`004b` while `1A13:4052` reads `04` (folding) / `03` (unfolding)
  — fold, unfold, fold, unfold (`catalogue/signals.yaml:74-75`).

### B3 `D112` rail-swing pass (~6 min; 5 rows) — T12 (+ re-verified T08-T11)

1. `./p4 watch 1701:F442 1C01:D112 1316:D112 1317:D112 1344:D112 1672:D112 1301:D112 --baseline 0 --name rail-swing`
2. Loads = headlamps on + rear demister + blower high. On: `./p4 mark "loads on 1"`; off: `./p4 mark "loads off 1"`; on and off again (`2`).
3. Ctrl-C.

Pass criteria: every candidate (T08-T11 `1316`, `1317`, `1344`, `1672` re-verified, and T12 `1301`) tracks
`1701:F442` x 0.08 through both swings — dips with loads on, recovers off, twice each way
(`catalogue/signals.yaml:264-267`); `1C01:D112` (already P in the catalogue) is the cross-check. Safe on
`1301`: this watch reads `D112` only, and only `EE13` is refused there (`docs/findings.md:65`).

**Follow-up**: finalise and paste the drafts for `2B1A`/`2B15`/`2B20` -> `1701` (T17/T18/T19);
`40A3`/`40A8` -> `1A27` (T13/T15); `40A3`/`40A8` -> `1A29` (T14/T16, or the note that it stays unlabelled);
`FE0D` -> `1A13` (T34); `D112` -> `1301` (T12), plus the re-verified `D112` rows for
`1316`/`1317`/`1344`/`1672` (T08-T11) — into [did-entries.md](did-entries.md).

---

## Session A — drive: drive-unit and steering transfers

7 rows (T01-T07), ~26 min of car time. Passive watch only while driving; the only typing is `./p4 mark` at a stop.

1. Preflight, parked in P, ignition on: laptop on charger, other tools disconnected, `docker stop p4-live` if
   a stale container holds the tester.
2. One watch for the whole drive (12 DIDs; `--interval 0` because pass time, not the pause, is the limiter):
   `./p4 watch 1631:D003,E307,E319 1637:D003,E307,E319 1601:E307,E319 1635:4802 1670:3019 1672:3019 1676:3019 --interval 0 --baseline 0 --name drive-transfer`
   (`1635:4802` pack current is the traction/regen sign reference: `0x4000` = 0 A, + = discharge.)
3. Parked, before setting off — two P<->R<->D cycles, brake held, marking each shift:
   `./p4 mark "gear P>R 1"`, `"R>P 1"`, `"P>D 1"`, `"D>P 1"`, then the `2` set. (Dataset for T03 `1601:E307`.)
4. Drive, in order, marking each action at a stop or just after it:
   - two firm pull-aways (~2 m/s²), easing off each time: `./p4 mark "pull-away 1"`, `"pull-away 2"`;
   - two full lift-off regens from ~40-60 km/h, pedal released: `./p4 mark "lift-off regen 1"`, `"lift-off regen 2"`;
   - switch to Range and cruise steadily twice, long enough for the front motor to drop out (`1601:E3E8`
     flattens to `0x4E20`, `DISCOVERIES.md` 2026.11.13): `./p4 mark "range cruise 1"`, `"range cruise 2"`;
   - in a quiet low-speed area, two full lock-to-lock sweeps (full left, full right, twice):
     `./p4 mark "lock L 1"`, `"lock R 1"`, `"lock L 2"`, `"lock R 2"`.
   - The pull-aways and lift-offs already give T01 `D003` speed up and back; mark two longer runs if wanted
     (`"speed run 1"`, `"speed run 2"`).
5. Park, P, Ctrl-C. Log: `runs/<date>/watch-drive-transfer.log`.

Pass criteria (check the raw CHANGE lines; `./p4 correlate <date>` aligns marks and changes):

- T01 `1637:D003` raw equals `1631:D003` raw at every paired sample, from 0 up through acceleration and back down
  to 0 (x 0.0140625 km/h) — both directions of speed change at least twice.
- T02 `1631:E307`: `01` at rest in P/N; `02` on each pull-away; back to `01` in each Range cruise (front-motor
  disconnect): 01->02 twice and 02->01 twice. `1637:E307` stays `02` from R through D the whole drive.
- T03 `1601:E307`: one consistent meaning through the two parked P<->R<->D cycles (e.g. `02` exactly in R and D) —
  both directions twice — and the same logic through the drive; anything else is not the same signal.
- T04 `1631:E319`: `00` under traction; flips to `01` on each lift-off regen while `1635:4802` < `0x4000`
  (negative = regen current), back to `00` on each traction resume — twice each way, in step with `1637:E319`
  (which flipped with the current 22 of 25 times on the 2026-11-13 drive, `docs/findings.md:141`).
- T05 `1601:E319`: flips with `1637:E319` on the same events, twice each way.
- T06 `1670:3019`: stays within the small encoding offset of `1672:3019` through both lock-to-lock sweeps, left
  and right; sign of change matches throughout (`docs/findings.md:159`).
- T07 `1676:3019`: tracks the same sweeps alongside `1670`/`1672`, both directions (`docs/findings.md:175`).

**Follow-up**: finalise and paste the drafts for `D003` -> `1637` (T01); `E307` -> `1631` (T02);
`E307` -> `1601` (T03); `E319` -> `1631` (T04); `E319` -> `1601` (T05); `3019` -> `1670` (T06);
`3019` -> `1676` (T07) — into [did-entries.md](did-entries.md).

---

## Session C — charge + temperature

7 rows (T24, T27-T30; T25/T26/T29 expected ruled out), ~30 min of car time at the charger, plus ~5 min next
morning for the cold snapshot. Parked throughout; the charge is the wake-up.

### C1 `EE71`/`EE72` during one AC charge (~25 min) — T27, T28, T30 (+ T29 expected ruled out)

1. Plug in AC; when the charge starts, `./p4 mark "charge start"` and run:
   `./p4 watch 1650:EE71,EE72 1635:EE71,EE72 1A01:EE71,EE72 --interval 5 --baseline 0 --name charge-watch`
2. After at least 20 min (about 20+ counts on `1650:EE71` at 7 kW — one count per ~55 s,
   `docs/findings.md:149`), end the charge: unplug, `./p4 mark "charge end"`, keep the watch ~2 min more for
   the `EE72` updates.
3. Ctrl-C.

Pass criteria:

- T27 `1635:EE71` bytes 0-2 rise count-for-count with `1650:EE71` (u24 x 0.1 kWh) over the whole watch — at least
  20 shared increments, only while charging. (A counter only rises; the "twice" rule is met by the repeated
  in-step increments, not by both directions.)
- T28 `1A01:EE71` first 3 bytes: same count-for-count rise.
- At charge end `1650:EE72` (u16 W) updates once: T30 `1A01:EE72` first two bytes must equal it;
  T29 `1635:EE72` is 1 B and cannot hold the u16 — expected ruled out.

### C2 `EE07` warm vs cold-soaked snapshot pair (~5 min + ~5 min next morning) — T24 (+ T25/T26 expected ruled out)

1. With the bay still warm (end of the charge session), car on and parked, climate off:
   `./p4 snapshot t-warm 1635 1301 1601 1650` (about 5 min — it reads every known-OK DID of the four modules),
   then `./p4 mark "t-warm taken"`.
2. Next morning, cold-soaked, the same car state: `./p4 snapshot t-cold 1635 1301 1601 1650`, then
   `./p4 diff t-warm t-cold`.
3. Pass criteria:
   - T24 `1301:EE07` bytes 0-1 match `1635:EE07` (u16 x 0.01 - 50 °C) within a few counts **at both moments** —
     compare the raw values in both snap files, not only the diff. A value that drifts away from `1635`'s is a
     module-local temperature (trap pattern).
   - T25/T26 `1601:EE07` and `1650:EE07` (1 B each): cannot hold the u16 — expected ruled out.

`snapshot 1301` is safe: only `EE13` is refused on `1301`, and it is not in the known-OK set the snapshot reads.

**Follow-up**: finalise and paste the drafts for `EE71` -> `1635` (T27); `EE71` -> `1A01` (T28); `EE72` -> `1635`
(T29, expected ruled out); `EE72` -> `1A01` (T30); `EE07` -> `1301` (T24); `EE07` -> `1601` and `EE07` -> `1650`
(T25/T26, expected ruled out) — into [did-entries.md](did-entries.md).
