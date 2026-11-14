# Same-DID transfer entries: ready-to-apply drafts

Entry drafts for every transfer candidate in [`docs/did-ledger.md`](did-ledger.md) not ruled out by answer
length. Built 2026-11-13. Integration after a confirming session: paste the entry text over the existing
`catalogue/signals.yaml` entry (or append the new one), fill the TODO examples from the run records, then
`./p4 test`. Nothing here is in `signals.yaml` yet; no raw is invented.

Markers:

- **READY-NOW** — entry text complete, examples already quoted in the docs. Nothing left to collect.
  The hard rule below (own test before it lands) still applies.
- **AFTER-SESSION** — entry text complete except the example raws; the named session fills the TODO slots.

Module lists in amended entries assume every listed candidate's test has passed; if applying one candidate
at a time, paste with only the modules whose tests have passed. Order is known module first, then
candidates in `did-ledger.md` order (the `srs_supply_v` precedent).

## Hard rules any integration must satisfy

Checked by `tool/tests/test_catalogue.py`; run `./p4 test` after every paste.

1. Never invent a raw. Every `examples:` raw comes from a run record or is already quoted in the docs.
   A TODO slot stays TODO until the session fills it (`test_example_decodes_to_recorded_value` decodes
   every example; a wrong one fails the suite).
2. Every signal has at least one example (`test_every_signal_has_an_example`).
3. Signal ids are unique (`test_signal_ids_are_unique`). The two new ids below
   (`epb_position_bscm`, `mirror_fold_current_left`) were checked against all existing ids: no collision.
4. `module` and `did` are quoted hex; every module must exist in `catalogue/modules.yaml`
   (`test_signal_modules_exist_in_module_catalogue`).
5. A C signal's module list may only contain `status: confirmed` modules
   (`test_modules_with_confirmed_signals_are_marked_confirmed`). Blocked today: `discharge_counter` +
   `1656` (unknown); and do not raise `steering_angle` to C while `1670`/`1676` are unverified.
6. A transfer lands only after its own test passes on that module; one pass is not confirmation; C needs
   the same change twice, both directions, action noted (the transfer method rules in `docs/did.md`,
   `catalogue/signals.yaml` header, `docs/findings.md:91`).
7. Amended entries must keep every existing example decoding: the `len:` additions below were checked —
   `36ab`, `1644`, `00b083`, `196a`, `00d3cf44` all re-decode unchanged.
8. Hazards: never read `EE13` on `1301` (`README.md:15`, `findings.md:65`) — no watch, sweep or snapshot
   may reach it (the default scan already stops before it, `findings.md:64`); while driving, only passive
   watches of known DIDs (`README.md:17`).

## Already applied — no draft needed

The old transfers doc said "nothing here is in the catalogue yet"; these have since landed (ledger status
integrated/done):

- `D112` on `1316,1317,1344,1672` — inside `srs_supply_v` (`signals.yaml`, 2026-11-13; `DISCOVERIES.md:24`).
  [T08-T11]
- `DD0A` `power_mode` and `DD01` `odometer` — module lists already cover all 40 scanned modules
  (`DISCOVERIES.md:139`). The zero-risk widening is done. [T35/T36]

Only `D112` on `1301` is still open (T12, below).

## Drive unit (`1631`/`1637`/`1601`)

### T01 — vehicle_speed gains 1637 — AFTER-SESSION

Comment for `signals.yaml`:

    # D003 is the reference speed of the drive-unit set (findings.md:115); 1637 answers it, 2 B, same span
    # (did-map.csv:2234) — transfer within the drive-unit set, confirmed on one drive both directions (docs/did-ledger.md T01).

Replace the existing `vehicle_speed` entry with:

```yaml
- {id: vehicle_speed, module: "1631,1637", did: "D003", name: Vehicle speed, type: u, scale: 0.0140625, unit: " km/h", confidence: C,
   examples: [{raw: "1544", value: 76.55625}, {raw: "0000", value: 0}]}
```

Examples the confirming session must supply (`./p4 watch 1631:D003,1637:D003 --interval 0.2 --baseline 0`):

- TODO raw from the drive-unit drive watch: `1637:D003` at a steady cruise, expected = the `1631:D003`
  raw at the same instant (same count, x 0.0140625 km/h), at more than one speed up and back.
- TODO raw from the same watch at rest, expected `0000`.

### T02/T03 — drive_engaged gains 1631 (READY-NOW) and 1601 (AFTER-SESSION)

Comment for `signals.yaml`:

    # E307 on 1631 goes 01 -> 02 only in pull-away bursts (findings.md:114): per-motor engagement, active
    # only when the front motor drives (modules.md:24); 1601 has no behaviour seen yet (docs/did-ledger.md T02/T03).

Replace the existing `drive_engaged` entry with:

```yaml
- {id: drive_engaged, module: "1637,1631,1601", did: "E307", name: Inverter drive engaged (R or D), values: {"01": "no (P/N)", "02": "yes (R/D)"}, confidence: C,
   examples: [{raw: "02", value: "yes (R/D)"}, {raw: "01", value: "no (P/N)"}]}
```

- 1631 part **READY-NOW**: the `01`/`02` byte values are quoted in `findings.md:114` (payload 1 B per
  `did-map.csv:1887`, so the byte values are full payload raws). Apply after its confirming drive
  (Range cruising must return to `01`, each pull-away to `02`, Session A).
- 1601 part **AFTER-SESSION**, same watch with `1601:E307` added:
  - TODO raw from the drive watch: `1601:E307` held parked through P<->R<->D cycles, expected one
    consistent value through all holds (the watch decides which of `01`/`02` it maps to; it must track
    one meaning twice each way).
  - TODO raw from the same watch during a pull-away and during cruising, expected to follow the same
    pattern as whichever drive unit it mirrors.

### T04/T05 — torque_direction gains 1631 (AFTER-SESSION, settle-from-data) and 1601 (AFTER-SESSION)

Comment for `signals.yaml`:

    # E319 on 1631 reads 00 in the pull-away bursts like 1637:E319 (findings.md:114); on 1637 the flips
    # follow the pack current sign (findings.md:141); 1601 untested (docs/did-ledger.md T04/T05).

Replace the existing `torque_direction` entry with:

```yaml
- {id: torque_direction, module: "1637,1631,1601", did: "E319", name: Drive torque direction, values: {"00": traction, "01": "regen, or no forward drive (P/N/R)"}, confidence: C,
   examples: [{raw: "00", value: traction}, {raw: "01", value: "regen, or no forward drive (P/N/R)"}]}
```

- 1631 part **AFTER-SESSION** (settle-from-data per the audit: the regen `01` is not on record for
  `1631`): `00` on `1631:E319` is quoted in `findings.md:114` (1 B, `did-map.csv:1896`). Confirm from the
  recorded 2026-11-13 drive watch (flip to `01` on lift-off regen with the pack current sign, twice each
  way, the `findings.md:141` standard — Session D §10) or the same confirming drive before pasting.
- 1601 part **AFTER-SESSION**, same watch with `1601:E319` added:
  - TODO raw from the drive watch: `1601:E319` under traction (pull-away), expected `00` if it matches
    `1637:E319`.
  - TODO raw from the same watch on lift-off regen, expected `01`; the flips must match `1637:E319`
    twice each way.

## Steering set (`1670`/`1672`/`1676`)

### T06/T07 — steering_angle gains 1670 and 1676 — AFTER-SESSION (both)

Comment for `signals.yaml`:

    # 3019 answers 2 B on 1670 and 1676 (did-map.csv:2458, :2602); 1670 tracks the angle with a slightly
    # different encoding (findings.md:159); 1676 matched 1670 minutes apart (findings.md:175); same 44-DID
    # set (modules.md:33). Verified lock to lock on one drive.

Replace the existing `steering_angle` entry with:

```yaml
- {id: steering_angle, module: "1672,1670,1676", did: "3019", name: "Steering wheel angle (left positive, scale approximate)", type: s, scale: 0.0554, unit: deg, confidence: P,
   examples: [{raw: "e1b5", value: -429.627}, {raw: "1e6e", value: 431.566}]}
```

Examples the confirming session must supply (`./p4 watch 1670:3019,1672:3019,1676:3019 --interval 0.2 --baseline 0`, full lock-to-lock sweep both ways):

- TODO raw from the steering drive: `1670:3019` at full left lock and at full right lock, expected within
  the small encoding offset of `1672:3019` at the same moment, through the whole sweep both directions.
- TODO raw from the same watch: `1676:3019` at both locks, same expectation.
- Caveat: the draft assumes the `1672` decode (scale 0.0554) holds on `1670`/`1676`; if the sweep shows
  its own fixed offset or scale, amend `scale`/`add` before pasting and re-derive the values.
- Keep P: the scale is approximate, and a later C would first need `1670`/`1676` marked confirmed in
  `catalogue/modules.yaml` (hard rule 5).

## Module supply voltage (`D112`)

### T12 — srs_supply_v gains 1301 — AFTER-SESSION

Comment for `signals.yaml`:

    # D112 behaves as supply x 0.08 V on 1316, 1317, 1344 and 1672 (findings.md:74, :79, :84, :165;
    # DISCOVERIES.md:24); 1301 answers, 1 B (did-map.csv:821), behaviour not yet noted — safe there,
    # only EE13 is refused (findings.md:65). Confirmed on the parked rail-swing pass.

Replace the existing `srs_supply_v` entry with:

```yaml
- {id: srs_supply_v, module: "1C01,1316,1317,1344,1672,1301", did: "D112", name: "Module supply voltage", type: u, scale: 0.08, unit: " V", confidence: P,
   examples: [{raw: "b2", value: 14.24}]}
```

Examples the confirming session must supply (`./p4 watch 1701:F442,1C01:D112,1301:D112 --baseline 0`
with loads (headlamps, rear demister, blower) toggled on then off, twice, `./p4 mark` at each toggle):

- TODO raw from the rail-swing pass: `1301:D112` with the loads on, expected = the `1C01:D112` raw
  (same x 0.08 V scale) within a count or two at that mark.
- TODO raw from the same pass with the loads off, same expectation — twice each way.

## Seats (`1A27`/`1A28`/`1A29`)

### T13/T14 — pass_seat_slide gains 1A27 and 1A29 — AFTER-SESSION

Comment for `signals.yaml`:

    # 40A3 answers 14 B on 1A27 (did-map.csv:3998) and 16 B on 1A29 — the offset may sit elsewhere
    # (did-map.csv:4166); no behaviour seen yet (findings.md:236). Same offset 6 len 2 as on 1A28,
    # confirmed by moving the seat.

Replace the existing `pass_seat_slide` entry with (name generalised; the id stays):

```yaml
- {id: pass_seat_slide, module: "1A28,1A27,1A29", did: "40A3", name: Seat slide position (rises moving forward), offset: 6, len: 2, type: u, confidence: P,
   examples: [{raw: "00110000ffff02470670ffffffff", value: 583}]}
```

Examples the confirming session must supply (`./p4 watch 1A27:40A3,1A28:40A3 --baseline 0`,
`./p4 mark` at each end of the driver-seat travel):

- TODO raw from the seat session: `1A27:40A3` with the driver seat fully aft, expected a lower count at
  offset 6 len 2.
- TODO raw from the same session with the seat fully forward, expected a higher count (rising moving
  forward, as on `1A28`).
- 1A29 (weaker; 16 B): TODO raw from a snapshot diff while someone shifts on the rear bench
  (`./p4 snapshot s1 1A29`, action, `./p4 snapshot s2 1A29`, `./p4 diff s1 s2`), expected to step with
  the movement; if offset 6 len 2 does not hold, relocate the offset before labelling. If nothing moves
  it, leave `1A29` out.

### T15/T16 — pass_seat_switches gains 1A27 and 1A29 — AFTER-SESSION

Comment for `signals.yaml`:

    # 40A8 answers 3 B on 1A27 and 1A29 (did-map.csv:3999, :4167); on 1A28 bit 40 of byte 1 sets only
    # while the forward switch is held (signals.yaml pass_seat_switches). Same session as 40A3.

Replace the existing `pass_seat_switches` entry with:

```yaml
- {id: pass_seat_switches, module: "1A28,1A27,1A29", did: "40A8", name: Seat switches (bit 40 = forward), offset: 1, len: 1, bits: {"40": forward}, confidence: P,
   examples: [{raw: "c043fc", value: [forward]}, {raw: "c003fc", value: []}]}
```

Examples the confirming session must supply (same session as `40A3`):

- TODO raw from the seat session: `1A27:40A8` while the driver forward switch is held, expected byte 1
  with bit `40` set (decodes `[forward]`).
- TODO raw from the same session with the switch released, expected `[]`.
- 1A29: TODO raw while a rear switch (if any) is held, expected the same bit; if no rear switch sets it,
  leave `1A29` unlabelled.

## Parking brake (`1601` -> `1701`)

One parked session confirms all three: `./p4 watch 1601:2B1A,1701:2B1A,1601:2B15,1701:2B15,1601:2B20,1701:2B20 --interval 0.2 --baseline 0`
through five P<->D shifts (the automatic EPB release/apply, `findings.md:89`).

### T18 — epb_lamp gains 1701 — AFTER-SESSION

Comment for `signals.yaml`:

    # 2B15 answers 1 B on 1701 like 1601 (did-map.csv:2649); shared DIDs between 1601/1701 are proven to
    # diverge (docs/modules.md:34), so this was a real test, confirmed in step with 1601 (docs/did-ledger.md T18).

Replace the existing `epb_lamp` entry with:

```yaml
- {id: epb_lamp, module: "1601,1701", did: "2B15", name: Parking brake lamp, values: {"00": applied, "03": moving, "01": released}, confidence: C,
   examples: [{raw: "03", value: moving}]}
```

Examples the confirming session must supply:

- TODO raw from the EPB session: `1701:2B15` with the EPB applied, expected `00`, in step with
  `1601:2B15` (the `1601` value for that state).
- TODO raw while releasing/applying, expected `03`.
- TODO raw released, expected `01`.

### T19 — epb_operations gains 1701 — AFTER-SESSION

Comment for `signals.yaml`:

    # 2B20 answers 4 B on 1701 like 1601 (did-map.csv:2651); the counter gains one on each EPB release
    # (signals.yaml epb_operations), confirmed in step with 1601 (docs/did-ledger.md T19).

Replace the existing `epb_operations` entry with:

```yaml
- {id: epb_operations, module: "1601,1701", did: "2B20", name: Parking brake operation counter, type: u, confidence: C,
   examples: [{raw: "0000056b", value: 1387}]}
```

Examples the confirming session must supply:

- TODO raw from the EPB session: `1701:2B20` before the first release, expected = its own value minus
  the number of releases by the end.
- TODO raw after the fifth release, expected +1 per release, in step with `1601:2B20`.

### T17 — epb_position -> 1701 — AFTER-SESSION, new id `epb_position_bscm`

`1701:2B1A` answers 2 B vs `1601`'s 4 B value map (`did-map.csv:2650` vs `:1095`) — plausibility weak,
not length-ruled-out. A 2 B payload cannot share the `len`-less 4-byte map, so it gets its own id
(`epb_position` on `1601` stays untouched).

Comment for `signals.yaml`:

    # 2B1A answers 2 B on 1701 vs 1601's 4 B map (did-map.csv:2650 vs :1095) — plausibility weak; kept as
    # its own entry so the 1601 decode is untouched. Keys below are the expected 2-byte truncation of the
    # 1601 map; replace with whatever the confirming watch shows (docs/did-ledger.md T17).

Append to `signals.yaml` (chassis section):

```yaml
- {id: epb_position_bscm, module: "1701", did: "2B1A", name: Parking brake position (BSCM),
   values: {"0100": applied, "0800": releasing, "0200": applying, "0400": released}, confidence: C,
   examples: []}
```

The value keys are a hypothesis, not a confirmed decode — the session must confirm or replace them
together with the examples. Hard rule 2 (every signal has an example) means the entry cannot be pasted
before the session fills them. Examples it must supply:

- TODO raw from the EPB session: `1701:2B1A` applied, expected the 2-byte analogue of `1601`'s
  `00000100`.
- TODO raw releasing, applying and released, expected `0800`/`0200`/`0400` on the same assumption —
  `1701` must step through the same four states as `1601:2B1A` through all five P<->D shifts; any other
  behaviour means a different signal: do not paste.

## Battery / charger range DIDs (`EE02`, `EE07`, `EE71`, `EE72`, `EE13`)

Family membership is weak; every test is a diff against the known module, and a diverging candidate is
just another trap (the battery-family preamble in `docs/did-ledger.md`). Length-ruled-out, no drafts: `EE02`->`1601` (1 B, T23),
`EE07`->`1601` (1 B, T25), `EE07`->`1650` (1 B, T26), `EE72`->`1635` (1 B, T29), `EE13`->`1601` (2 B,
T33) — none can hold the u16/u24/u32 decode.

### T20/T21/T22 — low_volt_rail_bms gains 1650, 1C01, 1301 — AFTER-SESSION (all three; one rail-swing pair)

Comment for `signals.yaml`:

    # EE02 answers 2 B on 1650 (did-map.csv:2348) and as blocks on 1C01 (35 B, :4412) and 1301 (64 B,
    # :895) — bytes 0-1 only. Family membership weak; confirmed by snapshot diff against 1635
    # (docs/did-ledger.md T20/T21/T22).

Replace the existing `low_volt_rail_bms` entry with (`len: 2` added; existing example re-decodes
unchanged):

```yaml
- {id: low_volt_rail_bms, module: "1635,1650,1C01,1301", did: "EE02", name: 12 V rail (BMS), len: 2, type: u, scale: 0.001, unit: " V", confidence: P,
   examples: [{raw: "36ab", value: 13.995}]}
```

Examples the confirming session must supply (parked rail-swing pair: `./p4 snapshot a 1635 1650 1C01 1301`,
loads on, `./p4 snapshot b ...`, `./p4 diff a b`; loads on/off twice):

- TODO raw from the rail-swing pair: `1650:EE02` (2 B) with loads on and off, expected in step with
  `1635:EE02` (x 0.001 V), twice each way.
- TODO first two bytes of `1C01:EE02` (35 B block) at both moments, same expectation.
- TODO first two bytes of `1301:EE02` (64 B block) at both moments, same expectation. Safe: only `EE13`
  is refused on `1301` (`findings.md:65`).

### T24 — outside_temp_becm gains 1301 — AFTER-SESSION

Comment for `signals.yaml`:

    # EE07 answers 33 B on 1301; bytes 0-1 could hold the u16 x 0.01 - 50 decode (did-map.csv:900).
    # Outside temperature is car-wide, so two snapshots hours apart decide; a value that drifts away is
    # a module-local temperature (docs/did-ledger.md T24).

Replace the existing `outside_temp_becm` entry with:

```yaml
- {id: outside_temp_becm, module: "1635,1301", did: "EE07", name: "Outside air temperature (offset per issue 2; not yet checked against the dash)", len: 2, type: u, scale: 0.01, add: -50, unit: " C", confidence: P,
   examples: [{raw: "1644", value: 7.0}]}
```

Examples the confirming session must supply (two snapshots hours apart, engine bay warm vs cold-soaked,
`./p4 diff`):

- TODO bytes 0-1 of `1301:EE07` from the warm snapshot, expected within a few counts of `1635:EE07` at
  the same moment.
- TODO bytes 0-1 from the cold-soaked snapshot, same expectation at both moments.

### T27/T28 — charge_energy_counter gains 1635 and 1A01 — AFTER-SESSION (both; one AC charge)

Comment for `signals.yaml`:

    # EE71 answers 24 B on 1635 (did-map.csv:2179) and 200 B on 1A01 (:3056) — first 3 bytes could hold
    # the u24 x 0.1 kWh counter; 1650 rose one count per ~55 s on a 7 kW charge (findings.md:149).

Replace the existing `charge_energy_counter` entry with (`len: 3` added; existing example re-decodes
unchanged):

```yaml
- {id: charge_energy_counter, module: "1650,1635,1A01", did: "EE71", name: Lifetime AC charge energy (4.5 MWh here; not per charge), len: 3, type: u, scale: 0.1, unit: kWh, confidence: P,
   examples: [{raw: "00b083", value: 4518.7}]}
```

Examples the confirming session must supply (`./p4 watch 1650:EE71,1635:EE71,1A01:EE71 --interval 5`
during one AC charge):

- TODO bytes 0-2 of `1635:EE71` early and late in the charge, expected rising count-for-count with
  `1650:EE71` (one count ~ 0.1 kWh per ~55 s).
- TODO bytes 0-2 of `1A01:EE71`, same expectation.
- Caveat: the first-3-bytes assumption is unverified — if the rising u24 sits deeper in the block, move
  `offset` before pasting and take the raws from the same bytes.

### T30 — last_charge_avg_power gains 1A01 — AFTER-SESSION

Comment for `signals.yaml`:

    # EE72 answers 50 B on 1A01; first two bytes could hold the u16 W decode (did-map.csv:3057).
    # EE72/EE74 are themselves weak (findings.md:149).

Replace the existing `last_charge_avg_power` entry with (`len: 2` added):

```yaml
- {id: last_charge_avg_power, module: "1650,1A01", did: "EE72", name: Average power of last charge, len: 2, type: u, unit: W, confidence: P,
   examples: [{raw: "196a", value: 6506}]}
```

Examples the confirming session must supply (read once after a charge):

- TODO bytes 0-1 of `1A01:EE72`, expected = the `1650:EE72` value from the same post-charge read.

### T31/T32 — discharge_counter gains 1650 and 1656 — AFTER-SESSION (snapshot pair around a drive)

Comment for `signals.yaml`:

    # EE13 answers 4 B on 1650 (did-map.csv:2361) and 5 B on 1656 (:2439, first 4 bytes; among the
    # battery-range DIDs it answers, findings.md:153); the counter only moves with discharge
    # (signals.yaml discharge_counter). Never read EE13 on 1301 (findings.md:65).

Replace the existing `discharge_counter` entry with (`len: 4` added; existing example re-decodes
unchanged):

```yaml
- {id: discharge_counter, module: "1635,1650,1656", did: "EE13", name: Accumulated discharge counter (mAh; per a US owner, issue 2, and our parked current), len: 4, type: u, unit: " mAh", confidence: C,
   examples: [{raw: "00d3cf44", value: 13881156}]}
```

- 1650 part: `1650` is `status: confirmed`, no blocker.
- 1656 part: **blocked by hard rule 5** — `1656` is `status: unknown` in `catalogue/modules.yaml`. The
  confirming session's behaviour evidence is what would support marking it confirmed; that is a main
  session decision. Until then paste with `module: "1635,1650"` only.

Examples the confirming session must supply (`./p4 snapshot d0 1635 1650 1656`, drive,
`./p4 snapshot d1 ...`, `./p4 diff d0 d1`):

- TODO raw from d1: `1650:EE13` (4 B), expected = its d0 value + exactly the `1635:EE13` rise (mAh).
- TODO first 4 bytes of `1656:EE13` from d1, same expectation.

## Mirrors (the remaining per-side gap)

### T34 — mirror_fold_current_left, new id on 1A13 — AFTER-SESSION

The right-side entry's name says "right"; `1A13` is the left mirror, so this is a new id on the
`mirror_fold_*` pattern (checked: no collision).

Comment for `signals.yaml` (mirror section):

    # Left-side counterpart of mirror_fold_current_right; FE0D answers 2 B on 1A13 (did-map.csv:3630);
    # the per-side mirror set is otherwise fully catalogued both sides (4051/4052/4053). 2026-MM-DD
    # parked fold test on the left (docs/did-ledger.md T34).

Append to `signals.yaml` (after `mirror_fold_current_right`):

```yaml
- {id: mirror_fold_current_left, module: "1A13", did: "FE0D", name: Left mirror fold motor current (raw; 1-2 at rest, about 0x40-0x4b moving), type: u, confidence: P,
   examples: []}
```

Hard rule 2 applies: the entry cannot be pasted before the session fills the examples. Examples it must
supply (`./p4 watch 1A13:FE0D,1A12:4052 --baseline 0`, fold/unfold twice):

- TODO raw from the left mirror session: `1A13:FE0D` at rest, expected `0001`-`0002` (decodes 1-2).
- TODO raw while folding or unfolding, expected `0x0040`-`0x4b` (decodes 64-75), with `1A12:4052`
  showing the movement.

## Session index: what unlocks what

| Session | Entries unlocked |
|---|---|
| Drive-unit drive watch (`1631`/`1637`/`1601`, `D003`+`E307`+`E319`) — Session A | **5** — T01 vehicle_speed+1637; T02 drive_engaged+1631 (confirm); T04 torque_direction+1631 (settle-from-data first, Session D §10; confirm); T03 drive_engaged+1601; T05 torque_direction+1601. The most of any single session. |
| Seat parked session (move driver seat, hold switches; rear-bench diff) — Session B2 | 4 — T13 pass_seat_slide+1A27, T14 +1A29; T15 pass_seat_switches+1A27, T16 +1A29 |
| Parked rail-swing pass, combined (`1301:D112` + `EE02` snapshots) — Session B3 (+ offline D5/D8 first) | 4 — T12 srs_supply_v+1301; T20 low_volt_rail_bms+1650, T21 +1C01, T22 +1301 |
| EPB parked session (five P<->D shifts) — Session B1 | 3 — T17 epb_position_bscm; T18 epb_lamp+1701; T19 epb_operations+1701 |
| AC charge watch (+ post-charge read) — Session C1 | 3 — T27 charge_energy_counter+1635, T28 +1A01; T30 last_charge_avg_power+1A01 |
| Snapshot pair around a drive (`EE13`) — Session D §3 | 2 — T31 discharge_counter+1650, T32 +1656 |
| Steering lock-to-lock drive — Session A | 2 — T06 steering_angle+1670, T07 +1676 |
| Two-snapshot temperature diff — Session C2 | 1 — T24 outside_temp_becm+1301 |
| Left mirror fold session — Session B2 | 1 — T34 mirror_fold_current_left |

Total: 25 candidates drafted — 1 READY-NOW (T02), 24 AFTER-SESSION (T04 settle-from-data per the audit),
5 length-ruled-out, 6 already applied (ledger T08-T11, T35/T36).
