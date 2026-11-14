# DID-transfer ledger (T01-T36): verdicts, evidence, procedures

The single source of truth for same-DID transfer work. One section per candidate; ids are stable. T01-T34
are the candidate rows of the old `did-transfers.md` in its table order, family by family; T35-T36 are the
`DD0A`/`DD01` widenings proposed in the same document. Method rules and the divergence traps live in
[did.md](did.md); runbooks and offline procedures in [did-sessions.md](did-sessions.md); paste-ready entry
drafts in [did-entries.md](did-entries.md), keyed by the same T-ids.

Verdicts follow the 2026-11-13 audit of every candidate row against repo evidence only (`findings.md`,
`DISCOVERIES.md`, `modules.md`, `did-leads.md`, `catalogue/signals.yaml` (comments included) and
`did-map.csv`); nothing has been tested at the car since. Verdict vocabulary (audit term in parentheses):

- **integrated** — CONFIRMABLE-NOW (integrated): already in `catalogue/signals.yaml` on documented
  per-module behaviour; nothing to do.
- **confirmable-now** — CONFIRMABLE-NOW: per-module behaviour in the repo in both directions of the decode
  (or counter movement) and raws quotable for examples. Can be labelled in `catalogue/signals.yaml` today.
- **settle-from-data** — CONFIRMABLE-FROM-EXISTING-DATA: no car time needed; confirmation is the stated
  diff over already-recorded sessions, run where the captures live. This checkout has no `runs/`, `local/`
  or `captures/`; every such row names its comparison and pass criteria.
- **needs-session** — NEEDS-SESSION: the confirming watch/snapshot needs new car actions; the session named
  in [did-sessions.md](did-sessions.md) is still the test.
- **ruled-out** — RULED-OUT: the answer length in `did-map.csv` cannot hold the decode span.

Bar applied: "the DID answers and the family matches" is not evidence; a documented per-module observation
is (the `1631:E307` pull-away bursts count). Catalogue rules hold throughout: C needs the same change twice
in both directions (`catalogue/signals.yaml:8`), a C module must be status confirmed in
`catalogue/modules.yaml` (`tool/tests/test_catalogue.py:48-53`), and every example must be a real quoted raw
that decodes to the stated value (`tool/tests/test_catalogue.py:21-27`).

Note the tension with the method rules in [did.md](did.md) (a transfer must not enter `signals.yaml` until
its own test passes on that module): the confirmable-now verdicts override that where the recorded
per-module evidence already shows what the test would check — the main session decides with eyes open.

Where things stand — 34 candidate rows audited: **5 CONFIRMABLE-NOW** (4 already integrated = T08-T11,
1 ready to land = T02), **7 CONFIRMABLE-FROM-EXISTING-DATA** (T04, T24, T27, T28, T30, T31, T32), **17
NEEDS-SESSION**, **5 RULED-OUT** (T23, T25, T26, T29, T33); the `DD0A`/`DD01` widening (T35/T36) is done.

No car time needed, but not yet done (run on the capture machine; comparisons and pass criteria per row
below): `E319` -> `1631` (T04), `EE07` -> `1301` (T24), `EE71` -> `1635` (T27), `EE71` -> `1A01` (T28),
`EE72` -> `1A01` (T30), `EE13` -> `1650` (T31), `EE13` -> `1656` (T32).

Car sessions still required (17 rows): the drive dual-watch (`D003` -> `1637`, T01), `E307`/`E319` ->
`1601` (T03/T05), both steering sweeps (`3019` -> `1670`/`1676`, T06/T07), the rail-swing pass with `1301`
added (`D112`, T12), the seat sessions (`40A3`/`40A8` -> `1A27`/`1A29`, T13-T16), the EPB shift session
(`2B1A`/`2B15`/`2B20` -> `1701`, T17-T19), the `EE02` rail-swing pairs (`1650`/`1C01`/`1301`, T20-T22), and
the left-mirror repeat (`FE0D` -> `1A13`, T34).

## Drive unit (`1631`/`1637`/`1601`) — T01-T05

`1631` is probably the front drive motor controller, `1637` the rear (`docs/findings.md:114`). `E307`/`E303`
on `1631` are active only when the front motor drives (`docs/modules.md:24`), so the transferred label there
is per-motor engagement, not gear engagement.

### T01 — `D003` -> `1637` (vehicle_speed, C on `1631`)

Family: drive unit. Verdict: **needs-session**.
Evidence: decode `signals.yaml:146-147`; answers, 2 B, holds the u16 (`did-map.csv:2234`); no `1637:D003`
behaviour anywhere (`findings.md:140-142` covers only `E307`/`E319`/`EEC4`).
Procedure: Session A (the drive-transfer watch, step 2; pass criteria there) — the dual watch; pass =
`1637` raw equals `1631` raw (x 0.0140625) at all speeds, up and back. Offline pre-check: Session D §10
(a whole drive both ways = the C bar; a mismatch = ruled out).
Entry: [did-entries.md](did-entries.md) T01 (AFTER-SESSION).

### T02 — `E307` -> `1631` (front_drive_engaged, P)

Family: drive unit. Verdict: **integrated** 2026-11-13 as `front_drive_engaged` (P, separate entry — on
1631 the meaning is per-motor engagement, dropping out in Range cruising, not 1637's gear engagement;
the C-extension draft in did-entries.md is superseded).
Evidence: decode `signals.yaml:178-179`; `findings.md:114`: goes `01` -> `02` only in pull-away bursts on
the 2026-11-13 drives (`DISCOVERIES.md:11`, `:27`) — `01` is the rest state, so both directions are on
record; 1 B (`did-map.csv:1887`); amendment pending `did-leads.md:26`. Raws: `01` = no (P/N), `02` = yes
(R/D) — complete 1-byte payloads quoted at `findings.md:114`.
Procedure: label at **P** (not enumerated twice each way; the Range-cruise watch makes C — `1631` must
return to `01` while cruising in Range (front motor disconnect, `DISCOVERIES.md:19`) and go `02` on each
pull-away, while `1637` stays `02` through R/D: Session A). Per the family preamble, the `1631` meaning is
front-motor engagement, not R/D: a `1631`-specific entry is the honest form; the `did-leads.md:26` extension
would carry the entry's C on `1637`'s evidence. `1631` is confirmed (`modules.yaml:23`), so either form
passes the module test.
Entry: [did-entries.md](did-entries.md) T02/T03 (READY-NOW part).

### T03 — `E307` -> `1601`

Family: drive unit. Verdict: **needs-session**.
Evidence: answers, 1 B (`did-map.csv:1289`); no behaviour in `findings.md:86-99`.
Procedure: Session A (parked P<->R<->D cycles, step 3, plus the drive watch) — the T03 watch; must hold a
consistent value through parked P<->R<->D and track one meaning twice each way; anything else is not the
same signal.
Entry: [did-entries.md](did-entries.md) T02/T03 (AFTER-SESSION part).

### T04 — `E319` -> `1631` (torque_direction, C on `1637`)

Family: drive unit. Verdict: **settle-from-data** (audit).
Disagreement note: the entry draft was marked READY-NOW; the audit verdict wins — the regen `01` is not on
record for `1631`, so settle from data before landing (the draft is AFTER-SESSION).
Evidence: decode `signals.yaml:181-182`; `findings.md:114`: reads `00` in the bursts — the traction side
only; the regen `01` is not on record for `1631`; 1 B (`did-map.csv:1896`); amendment pending
`did-leads.md:27`.
Procedure: Session D §10 — the 2026-11-13 drive watch that sampled `1631:E319` (source of the bursts,
`runs/` on the capture machine) against `1637:E319` / pack-current sign in the same log; pass =
`1631:E319` flips `00`<->`01` with the current sign at least twice each way, the `findings.md:141` standard
for `1637` (22 of 25). If the log lacks regen windows: the T04 drive watch (Session A). Landing
`did-leads.md:27` today would rest on one direction only.
Entry: [did-entries.md](did-entries.md) T04/T05 (AFTER-SESSION).

### T05 — `E319` -> `1601`

Family: drive unit. Verdict: **needs-session**.
Evidence: answers, 1 B (`did-map.csv:1304`); no behaviour in `findings.md:86-99`.
Procedure: Session A (pass criteria there) — must match `1637:E319` flips twice each way. Offline:
Session D §10 (only parked-cycle consistency can come from logs; expect no hit).
Entry: [did-entries.md](did-entries.md) T04/T05 (AFTER-SESSION).

## Steering set (`1670`/`1672`/`1676`) — T06-T07

### T06 — `3019` -> `1670` (steering_angle, P on `1672`)

Family: steering set. Verdict: **needs-session**.
Evidence: `findings.md:159`: tracks the angle while driving, encoding differs slightly — the `1670` scale
is not established; no raw quoted anywhere; 2 B, holds the s16 (`did-map.csv:2458`); source decode P, scale
approximate (`signals.yaml:95-96`).
Procedure: Session A — the lock-to-lock watch (full lock-to-lock sweep both ways). Cheaper pre-check on the
capture machine: the paired `1670`/`1672` drive log behind `findings.md:159`; a constant offset through
left and right steering would pre-verify, full-lock extremes still need the session. Offline: Session D §10
(grep plus the steering snapshot fallback).
Entry: [did-entries.md](did-entries.md) T06/T07 (AFTER-SESSION).

### T07 — `3019` -> `1676`

Family: steering set. Verdict: **needs-session**.
Evidence: `findings.md:175`: equal to `1670:3019` minutes apart, parked, once; 2 B (`did-map.csv:2602`);
`did-leads.md:70`.
Procedure: Session A — the same sweep watch; must track the full sweep alongside `1670`/`1672`, both
directions. Offline: Session D §10.
Entry: [did-entries.md](did-entries.md) T06/T07 (AFTER-SESSION).

## Module supply voltage (`D112`) — T08-T12

The one cross-family class: each module's own 12 V reading. Known decode is `x 0.08 V` on `1C01`, tracking
`1701:F442` at r 0.98-1.00 when the rail swings (`catalogue/signals.yaml:264-267`).

T08-T11 are integrated into `srs_supply_v` (`catalogue/signals.yaml:269`) on the
`findings.md:74`/`:79`/`:84`/`:165` + `DISCOVERIES.md:24` notes (`did-leads.md:29`) — the project precedent
for integrating a transfer on documented per-module behaviour without a dedicated session. Nothing to do;
the entry's example raw `b2` -> 14.24 V is the `1C01` reading (`signals.yaml:270`); examples are per-entry —
no per-module raw for the four is quoted anywhere in the repo.

### T08 — `D112` -> `1316` (srs_supply_v)

Family: module supply voltage. Verdict: **integrated**.
Evidence: answers, 1 B (`did-map.csv:978`); `findings.md:74` (supply x 0.08 V, as on `1C01`);
`DISCOVERIES.md:24`; `signals.yaml:269`; `did-leads.md:29`.

### T09 — `D112` -> `1317`

Family: module supply voltage. Verdict: **integrated**.
Evidence: answers, 1 B (`did-map.csv:1014`); `findings.md:79`; `DISCOVERIES.md:24`; `signals.yaml:269`;
`did-leads.md:29`.

### T10 — `D112` -> `1344`

Family: module supply voltage. Verdict: **integrated**.
Evidence: answers, 1 B (`did-map.csv:1057`); `findings.md:84`; `DISCOVERIES.md:24`; `signals.yaml:269`;
`did-leads.md:29`.

### T11 — `D112` -> `1672`

Family: module supply voltage. Verdict: **integrated**.
Evidence: answers, 1 B (`did-map.csv:2512`); `findings.md:165`; `DISCOVERIES.md:24`; `signals.yaml:269`;
`did-leads.md:29`.

### T12 — `D112` -> `1301`

Family: module supply voltage. Verdict: **needs-session**.
Evidence: answers, 1 B (`did-map.csv:821`); `findings.md:62-65` (§1301) notes no `D112` behaviour.
Procedure: Session B3 — the rail-swing pass with `1301` added (safe: only `EE13` is refused there,
`findings.md:65`); pass = tracks `1701:F442` x 0.08 twice each way, loads on then off. Offline pre-check:
Session D §8 (BOTH*).
Entry: [did-entries.md](did-entries.md) T12 (AFTER-SESSION).

## Seats (`1A27`/`1A28`/`1A29`) — T13-T16

### T13 — `40A3` -> `1A27` (pass_seat_slide, P on `1A28`)

Family: seats. Verdict: **needs-session**.
Evidence: answers, 14 B like `1A28` (`did-map.csv:3998` vs `:4082`) — offset 6 len 2 fits
(`signals.yaml:132-133`); `findings.md:236`: "Leads: none".
Procedure: Session B2 — parked fore/aft move with marks; pass = steps and rises moving forward. Recorded
data: Session D §11 (no recorded stimulus).
Entry: [did-entries.md](did-entries.md) T13/T14 (AFTER-SESSION).

### T14 — `40A3` -> `1A29`

Family: seats. Verdict: **needs-session**.
Evidence: answers, 16 B vs `1A28`'s 14 B (`did-map.csv:4166`) — the offset may sit elsewhere;
`findings.md:247`: only `41F4` noted.
Procedure: Session B2 — whatever rear-seat adjustment exists; if none moves it, the bench shift + snapshot
diff is the only mover. Recorded data: Session D §11.
Entry: [did-entries.md](did-entries.md) T13/T14 (AFTER-SESSION).

### T15 — `40A8` -> `1A27` (pass_seat_switches, P on `1A28`)

Family: seats. Verdict: **needs-session**.
Evidence: answers, 3 B (`did-map.csv:3999`); `findings.md:236`.
Procedure: same session as `40A3` (Session B2); pass = bit `40` of byte 1 sets only while the forward
switch is held (`signals.yaml:134-135`). Recorded data: Session D §11.
Entry: [did-entries.md](did-entries.md) T15/T16 (AFTER-SESSION).

### T16 — `40A8` -> `1A29`

Family: seats. Verdict: **needs-session**.
Evidence: answers, 3 B (`did-map.csv:4167`); `findings.md:247`.
Procedure: Session B2; a rear switch press (if any) must set the same bit, else leave unlabelled. Recorded
data: Session D §11.
Entry: [did-entries.md](did-entries.md) T15/T16 (AFTER-SESSION).

## Parking brake (`1601` -> `1701`) — T17-T19

Both are brake-side controllers sharing 29 DIDs (`docs/modules.md:34`), but the divergence traps
([did.md](did.md)) show a shared DID can still differ, so these are real tests, not formalities.

### T17 — `2B1A` -> `1701` (epb_position, C on `1601`)

Family: parking brake. Verdict: **needs-session** (plausibility weak).
Evidence: answers, 2 B (`did-map.csv:2650`) vs `1601`'s 4 B (`did-map.csv:1095`) — the 4-byte value map
(`signals.yaml:86-88`) cannot be read off a 2-byte answer as written; an offset/len variant would be needed.
Procedure: Session B1 — the five P<->D shift watch (the automatic EPB release/apply, `findings.md:89`);
pass = `1701` steps through the same applied/releasing/applying/released values in step with `1601`.
Recorded data: Session D §11.
Entry: [did-entries.md](did-entries.md) T17 (AFTER-SESSION; new signal id `epb_position_bscm`).

### T18 — `2B15` -> `1701` (epb_lamp, C on `1601`)

Family: parking brake. Verdict: **needs-session**.
Evidence: answers, 1 B like `1601` (`did-map.csv:2649` vs `:1094`); decode `signals.yaml:89-90`.
Procedure: same session (Session B1); pass = `00`/`03`/`01` in step with `1601`. Recorded data: Session D §11.
Entry: [did-entries.md](did-entries.md) T18 (AFTER-SESSION).

### T19 — `2B20` -> `1701` (epb_operations, C on `1601`)

Family: parking brake. Verdict: **needs-session**.
Evidence: answers, 4 B like `1601` (`did-map.csv:2651` vs `:1096`); decode `signals.yaml:91-92`.
Procedure: same session (Session B1); pass = the counter gains one on each release, in step with `1601`.
Offline pre-check: Session D §9 (BOTH*).
Entry: [did-entries.md](did-entries.md) T19 (AFTER-SESSION).

## Battery/charger-range DIDs (`EE02`, `EE07`, `EE71`, `EE72`, `EE13`) — T20-T33

Decoded on `1635` (`EE02`, `EE07`, `EE13`) and `1650` (`EE71`, `EE72`). These answer on unrelated modules
too, so family membership is weak; the tests are snapshot diffs against the known module, and a candidate
that diverges is just another trap. `1656` is noted to answer battery-range DIDs (`docs/findings.md:153`).

### T20 — `EE02` -> `1650` (low_volt_rail_bms, P on `1635`)

Family: battery/charger-range. Verdict: **needs-session**.
Evidence: decode `signals.yaml:170-171`; answers, 2 B, holds the u16 x 0.001 (`did-map.csv:2348`); no
`1650:EE02` behaviour in `findings.md:145-149`.
Procedure: audit session: the parked rail-swing pair, twice each way (car commands in the T20 draft);
cheaper pre-check on the capture machine: paired `1635`/`1650` `EE02` in the 2026-11-12 charge-window
captures (`findings.md:132`, `:148`), if sampled — the full offline procedure is Session D §5 (the recorded
snapshots span standby and car-on states, so the rail-swing pair may come free).
Entry: [did-entries.md](did-entries.md) T20/T21/T22 (AFTER-SESSION).

### T21 — `EE02` -> `1C01`

Family: battery/charger-range. Verdict: **needs-session**.
Evidence: answers, 35 B block — bytes 0-1 only (`did-map.csv:4412`).
Procedure: same pair with `1C01` added (Session D §5; car commands in the T20 draft).
Entry: [did-entries.md](did-entries.md) T20/T21/T22 (AFTER-SESSION).

### T22 — `EE02` -> `1301`

Family: battery/charger-range. Verdict: **needs-session**.
Evidence: answers, 64 B block — bytes 0-1 only (`did-map.csv:895`).
Procedure: same pair with `1301` added (Session D §5); safe, `findings.md:65`.
Entry: [did-entries.md](did-entries.md) T20/T21/T22 (AFTER-SESSION).

### T23 — `EE02` -> `1601`

Family: battery/charger-range. Verdict: **ruled-out**.
Evidence: answers, 1 B (`did-map.csv:1645`) — cannot hold the u16 x 0.001 V decode (needs 2 B).
Note: expected: different content — at best a 0.1 V-step supply like the `D904` lead (`findings.md:12`), not
the decode. Length-settled (Session D §2): the single byte could still be a coarser encoding — a different
hypothesis, not this transfer.
Entry: no draft (length-ruled-out).

### T24 — `EE07` -> `1301` (outside_temp_becm, P on `1635`)

Family: battery/charger-range. Verdict: **settle-from-data**.
Evidence: answers, 33 B block — bytes 0-1 can hold the u16 x 0.01 - 50 (`did-map.csv:900`); decode
`signals.yaml:228-229`; `1301` was swept to just below `EE13` on 2026-11-10/11 and read again since
(`DISCOVERIES.md:121`, `:128`).
Procedure: Session D §6 — every recorded `1301:EE07` payload in `runs/` against `1635:EE07` from the same
sessions; pass = bytes 0-1 within a few counts of `1635:EE07` at every compared moment, warm and
cold-soaked; fail = drifts away from the `1635` value (module-local temperature, the trap pattern). If
`runs/` holds only one `1301:EE07` moment, needs the two-snapshot session (Session C2).
Entry: [did-entries.md](did-entries.md) T24 (AFTER-SESSION).

### T25 — `EE07` -> `1601`

Family: battery/charger-range. Verdict: **ruled-out**.
Evidence: answers, 1 B (`did-map.csv:1650`) — cannot hold the u16.
Note: expected: ruled out. Length-settled (Session D §2); Session C2 expects the same.
Entry: no draft (length-ruled-out).

### T26 — `EE07` -> `1650`

Family: battery/charger-range. Verdict: **ruled-out**.
Evidence: answers, 1 B (`did-map.csv:2351`) — cannot hold the u16.
Note: expected: ruled out. Length-settled (Session D §2); Session C2 expects the same.
Entry: no draft (length-ruled-out).

### T27 — `EE71` -> `1635` (charge_energy_counter, P on `1650`)

Family: battery/charger-range. Verdict: **settle-from-data**.
Evidence: decode `signals.yaml:38-39`; answers, 24 B block — bytes 0-2 could hold the u24 x 0.1 kWh counter
(`did-map.csv:2179`); both modules read on 2026-11-12 and 2026-11-13 (`findings.md:132`, `:148-149`; full
`1650` sweep `DISCOVERIES.md:14`).
Procedure: Session D §4 — paired `1635:EE71` (bytes 0-2) and `1650:EE71` across the recorded sessions in
`runs/`; pass = equal counts at each paired moment and equal rise across the 2026-11-12 charge (one count
per ~55 s at 7 kW, `findings.md:149`); fail = any divergence. Car fallback: Session C1 (one AC charge
watch).
Entry: [did-entries.md](did-entries.md) T27/T28 (AFTER-SESSION).

### T28 — `EE71` -> `1A01`

Family: battery/charger-range. Verdict: **settle-from-data**.
Evidence: answers, 200 B block — bytes 0-2 only (`did-map.csv:3056`); `1A01` scanned 11-12 and 11-13
(`DISCOVERIES.md:69`, `:14`).
Procedure: same comparison and pass criteria (Session D §4). Car fallback: Session C1.
Entry: [did-entries.md](did-entries.md) T27/T28 (AFTER-SESSION).

### T29 — `EE72` -> `1635` (last_charge_avg_power, P on `1650`)

Family: battery/charger-range. Verdict: **ruled-out**.
Evidence: decode `signals.yaml:34-35`; answers, 1 B (`did-map.csv:2180`) — cannot hold the u16 W decode.
Note: expected: ruled out; the source decode is itself weak (`findings.md:149`). Length-settled
(Session D §2).
Entry: no draft (length-ruled-out).

### T30 — `EE72` -> `1A01`

Family: battery/charger-range. Verdict: **settle-from-data**.
Evidence: answers, 50 B block — bytes 0-1 only (`did-map.csv:3057`).
Procedure: Session D §7 — paired recorded reads of `1650:EE72` and `1A01:EE72` bytes 0-1; pass = equal at
every paired moment (the post-charge read). Equality alone labels at most P: the source decode is weak
(`findings.md:149`). Car fallback: Session C1 post-charge read.
Entry: [did-entries.md](did-entries.md) T30 (AFTER-SESSION).

### T31 — `EE13` -> `1650` (discharge_counter, C mAh on `1635`)

Family: battery/charger-range. Verdict: **settle-from-data**.
Evidence: decode `signals.yaml:30-31`; answers, 4 B, holds the u32 (`did-map.csv:2361`); `1650` read 11-12
(charge) and 11-13 (sweep).
Procedure: Session D §3 — paired `1650:EE13` vs `1635:EE13` across the recorded days in `runs/`; pass =
equal u32 mAh at each paired moment and equal rise across the drives between them (the counter only moves
with discharge); fail = divergence (another trap).
Entry: [did-entries.md](did-entries.md) T31/T32 (AFTER-SESSION).

### T32 — `EE13` -> `1656`

Family: battery/charger-range. Verdict: **settle-from-data**.
Evidence: answers, 5 B — first 4 bytes only (`did-map.csv:2439`); noted among the battery-range DIDs `1656`
answers (`findings.md:153`); content on `1656` otherwise unknown (`did-leads.md:89` warns `EE13` diverges
per module).
Procedure: same comparison and pass criteria (Session D §3); divergence = another trap, not a transfer.
Landing note: `1656` is `status: unknown` in `catalogue/modules.yaml` — blocked by hard rule 5 until marked
confirmed; that is a main-session decision (see the T31/T32 draft).
Entry: [did-entries.md](did-entries.md) T31/T32 (AFTER-SESSION).

### T33 — `EE13` -> `1601`

Family: battery/charger-range. Verdict: **ruled-out**.
Evidence: answers, 2 B (`did-map.csv:1662`) — cannot hold the u32 mAh.
Note: expected: ruled out. Length-settled (Session D §2). Hard rule stands: never `EE13` on `1301`
(`findings.md:65`).
Entry: no draft (length-ruled-out).

## Mirrors (the remaining per-side gap) — T34

### T34 — `FE0D` -> `1A13` (mirror_fold_current_right, P on `1A12`)

Family: mirrors. Verdict: **needs-session**.
Evidence: answers, 2 B, holds the u16 (`did-map.csv:3630`); the left mirror set is otherwise fully
catalogued (`signals.yaml:67-76`) but `FE0D` is not mentioned in `findings.md:211-214` (§1A13); the
2026-11-12 watch log covered the right side only (`signals.yaml:64`, raw `0049` at `signals.yaml:78`).
Procedure: Session B2 — repeat the 2026-11-12 fold/unfold test on the left; pass = raw sits at 1-2 at rest
and about `0x40`-`0x4b` while moving (`signals.yaml:77`). Offline: Session D §10 (grep the mirror watch
log; no hit = NOTHING).
Entry: [did-entries.md](did-entries.md) T34 (AFTER-SESSION; new signal id `mirror_fold_current_left`).

## Widening with essentially zero risk (`DD0A`, `DD01`) — T35/T36, done

Two catalogue signals state "same DID on every module" in their own names
(`catalogue/signals.yaml:147-150`) and are recorded as common to every module (`docs/findings.md:12`,
`DISCOVERIES.md:139`). Both answer on all 40 scanned modules (`docs/did-map.csv`, 40 rows each, `1001` at
`:47`/`:45` through `1C01` at `:4406`/`:4404`):

- `DD0A` `power_mode` — catalogued on `1A01` only; could list all 40.
- `DD01` `odometer` — catalogued on `1A01` only; could list all 40.

Widening their `module` field from `1A01` to the full list is zero-risk: both are car-wide quantities
already read in every default scan, and no per-module test is needed beyond the trivial check — any
snapshot in which each module's `DD01` equals the odometer and `DD0A` equals the power mode read on `1A01`.
(`DD00`, a free-running clock, sits in the same common block, `docs/findings.md:12`, but has no catalogue
decode, so there is nothing to widen.) Widening these two would add 39 module labels each — more than all
the tested candidates above combined — without a single new car session.

The widening is already in place: `signals.yaml:150-153` list all 40 addresses (evidence
`DISCOVERIES.md:139`, `findings.md:12`). Nothing left to do there. Same batch, not a transfer row:
`4947` -> `1656` (`low_volt_rail`, `signals.yaml:176`) (`did-leads.md:28`).

### T35 — `DD0A` `power_mode` -> all 40 scanned modules

Verdict: **integrated** (done). Evidence: `signals.yaml:150-153` list all 40 addresses
(`DISCOVERIES.md:139`, `findings.md:12`); answers on all 40 scanned modules (`docs/did-map.csv`).
Procedure: none left — the settling check is kept for the record as Session D §1.
Entry: not an entries draft — the `module` field edit in `catalogue/signals.yaml` (already applied).

### T36 — `DD01` `odometer` -> all 40 scanned modules

Verdict: **integrated** (done). Evidence: `signals.yaml:150-153` list all 40 addresses
(`DISCOVERIES.md:139`, `findings.md:12`); answers on all 40 scanned modules (`docs/did-map.csv`).
Procedure: none left — the settling check is kept for the record as Session D §1.
Entry: not an entries draft — the `module` field edit in `catalogue/signals.yaml` (already applied).
