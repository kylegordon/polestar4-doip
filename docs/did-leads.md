# DID leads: interpretation done, publication pending

**Status 2026-11-14:** the eight §1 rows are in `catalogue/signals.yaml` (P): `window_direction`, four
`stalk_push_*`, two `stalk_hold_*` and `obd_speed_1675` — their DIDs answer with exactly one byte, so the
quoted values are complete payloads. The §2 decoder features exist (`ascii`, `utf-16le/be`, `utf-8`,
`endian`, `count_from`), but the entries still need a full-payload raw (none is quoted in the docs). §3 is
unchanged and waiting for a capture-machine read.

Decodes already established in `docs/findings.md`, `DISCOVERIES.md` or `docs/modules.md` but missing from `catalogue/signals.yaml`, with what each still needs. Built 2026-11-13. Raws are copied exactly from the docs and never invented: a row without a quoted raw cannot get a `signals.yaml` `examples:` entry yet (the tests verify every example decodes). Identity DIDs (`IDENTITY_DIDS` in `tool/p4doip/cli.py`) and every entry already in `signals.yaml` are excluded. Decoder: `values`/`bits`/`type u|s` with `scale`/`add` and `offset`/`len` (`tool/p4doip/decode.py`), plus `encoding: ascii`, `utf-16le/be`, `utf-8`, `ascii-hex`, `raw`, `endian` and array support (`repeat`, including `count_from`). Leads with no decode at all (e.g. `1601 E3CF`-`E3D3`, `1701 D945`-`D948`, `1637 EEC4`, `1344 D923`) stay in `findings.md`.

Citations: `findings.md:N` = `docs/findings.md`; otherwise the file is named.

## 1. Catalogue-ready now

Decode established; what may be missing is only an example raw. "Raw" = quoted in the docs.

| Module | DID | Proposed entry | Decode | Raw in docs | Source |
|---|---|---|---|---|---|
| `1A12,1A13` | `D008` | `window_direction` | values: `03` up, `04` down | `04`/`03` (byte values; payload width unstated) | findings.md:208, 214 |
| `1A01` | `410B` | `ambient_light_state` | byte 0: values `01` dark, `02` daylight | `01 0000` (evening; full payload) | findings.md:193; DISCOVERIES.md:32 |
| `1A01` | `410B` | `ambient_light_level` | offset 1, len 2, type u (counts, no scale yet) | same payload (level 0); daylight ~2,800-10,000 given only as decimal | findings.md:193 |
| `1BB3,1BB4` | `4368` | `headlamp_scene` | whole-payload values: `11000000` home-safe (~90 s after locking), `00000020` approach | `11000000`, `00000020` | findings.md:259, 268; DISCOVERIES.md:141 |
| `1A01` | `4222` | `welcome_lamp` | values: `000000` off, `ffff01` approach/welcome on | `000000`, `ffff01` | findings.md:191 |
| `1675` | `F40D` | `obd_speed_1675` | type u, km/h (OBD PID 0D) | `00` (parked; not yet seen moving) | findings.md:170; modules.md:32 |
| `1633` | `D914`,`D915`,`D919`,`D920` | `stalk_push_*` (one entry per DID) | values: `01` idle, `04` pushed (self-releases ~2 s) | `01`/`04` (byte values; width unstated) | findings.md:121 |
| `1633` | `DA02`,`DA03` | `stalk_hold_*` (one entry per DID) | values: `01` idle, `03` held (the N gesture) | `01`/`03` (byte values; width unstated) | findings.md:121 |

All P. The `1633` rows and `4222` rest on a single test each. Where only byte values are quoted, confirm the payload width from a capture before writing the example.

Amendments (module-list extensions of existing `signals.yaml` entries; no new examples needed):

- `drive_engaged` (1637, signals.yaml:175): add `1631` — `E307` goes `01` -> `02` only in pull-away bursts there (findings.md:114; `1631` identity probable).
- `torque_direction` (1637, signals.yaml:178): add `1631` — `E319` reads `00` in those bursts, like `1637:E319` (findings.md:114).
- `low_volt_rail` (1635, signals.yaml:173): add `1656` — `4947` reads 14.0-14.2 V awake there (findings.md:153; modules.md:29).
- `srs_supply_v` (1C01, signals.yaml:266): add `1316,1317,1344,1672` — `D112` x 0.08 V behaves the same on all four (DISCOVERIES.md:24; findings.md:74, 79, 84, 165).

## 2. Blocked on decoder features

| Module | DID | Established decode | Feature | Entry shape | Source |
|---|---|---|---|---|---|
| `1001` | `D0D0` | customer software release "4.2.11", ASCII digits stored as ASCII (P) | `encoding: ascii-hex` | `{id: software_release, module: "1001", did: "D0D0", encoding: ascii-hex}`; no payload hex quoted — capture an example | findings.md:19; DISCOVERIES.md:81 |
| `1011` | `FD4A` | release text `P417_4.2.11_…` | `encoding: ascii-hex` | same shape | findings.md:24; DISCOVERIES.md:81 |
| `1635` | `DA31` | 130 x u16 cell-group voltages in mV, 110 valid (`EE19` = 110); sum matches `497C` within 0.05 V in nine snapshots | array | count 130, type u, scale 0.001 V, valid count from `EE19`; no raw quoted | findings.md:129; DISCOVERIES.md:84 |
| `1635` | `EE83` | 30 pack temperatures, 28 valid (`EE20` = 28), x 0.01 °C - 50 (6.5-7 °C on a November night) | array | count 30, type u, scale 0.01, add -50, valid count from `EE20` | findings.md:129 |
| `1635` | `EE06` | ambient temperature, same encoding as `EE83`; not yet seen to change | array (or scalar) | if scalar: type u, scale 0.01, add -50, as `outside_temp_becm` (signals.yaml:225) | findings.md:129 |
| `1BB3,1BB4` | `7022` | matrix main-beam segment brightness: 84 bytes = 32 data bytes (two rows of 16) + `ff` padding; all `00` dipped, `0x0f`-`0x50` per segment on main beam | array + padding skip | 32 x u8 brightness as 2x16 | findings.md:258; DISCOVERIES.md:34 |
| `1A12` | `D938` | window-run log, newest first: 10-byte entries = start, end, a byte, timestamp; positions ~1000 closed, ~5900 open | array of fixed records | 10-byte structs, u16 positions; same DID as `1201` `park_selected` (section 4) | findings.md:208 |
| `1601` | `EExx`/`EFxx` blocks | rolling logs or history buffers (change on almost every read parked; guess) | array / log | per-DID records; structures not yet established | findings.md:97 |

Also needing the same support once their structure is known: `1317` `D237` event list with timestamps (weak; findings.md:79), `1A11` `FDE1` 100-byte structured block (findings.md:201). DISCOVERIES.md:84 records why `DA31`/`EE83` were left uncatalogued: "the decoder handles scalars only".

## 3. Interpreted but needs a capture-machine read

Decode rests on values seen on the car; no full payload hex in the docs (or labels/scale still missing), so nothing here may become an `examples:` entry yet.

| Module | DID | Proposed decode | Evidence |
|---|---|---|---|
| `1011` | `FD50` | position: two s32 BE, longitude then latitude, deg = raw / 3,600,000; one parked read matched within ~100 m. Decoder-ready as two scalar entries; blocked only on a raw ("values never published") | findings.md:25; DISCOVERIES.md:28 |
| `1001` + several | `D904` byte 0 | supply voltage x 0.1 V (moves `0x96`/`0x97` with load; weak) | findings.md:12; modules.md:46 |
| `1631` | `E312` | vehicle speed, offset-binary: raw - `0x4000` at the `D003` scale (r 0.98 over two drives) | findings.md:116; DISCOVERIES.md:135 |
| `1631` | `E303` | front motor speed: raw - `0x4000`, ~83 counts/km/h, non-zero only in pull-away bursts | findings.md:114 |
| `1631` | `E335`-`E338` | four near-equal per-wheel values (~`0x332c` parked); weak braking link | findings.md:116 |
| `1601` | `E406` | vehicle speed in whole km/h | findings.md:93 |
| `1601` | `E467`,`E468` | axle speeds?: pair at `0x7F80` at rest, ~128 counts/km/h | findings.md:93 |
| `1601` | `E46A` | total deceleration demand?: `0x4000` = none; stop lamps on at/above ~`0x4380` | findings.md:92; DISCOVERIES.md:31 |
| `1614` | `D92D` | byte 0 speed in m/s; bytes 1-2 weak yaw/lateral candidates | findings.md:104, 280 |
| `1635` | `4801` (second entry) | display SoC = (raw - 9.5) / (97.1 - 9.5) x 100; fits the point where 65 % was shown at 66.6 % raw, dash ticked 68 -> 67 at 68.9 raw | findings.md:130; DISCOVERIES.md:89 |
| `1635` | `49F6`,`49F7` | energy used/remaining pair; sum always ~4460; unit unknown | findings.md:131; modules.md:47 |
| `1635` | `496D`,`496B` | SOH? constant 10000 = 100.00 % (Polestar 2 scaling); tracking unproven | findings.md:134 |
| `1635` | `4898` | nominal pack energy, 100000 Wh | findings.md:134 |
| `1635` | `DA06` | nominal capacity, 242,730,000 uAh | findings.md:134 |
| `1635` | `4805` | ~pack voltage x 0.01 (421 V); role not settled | findings.md:135 |
| `1635` | `49EC` | charge counter: 0 -> 46-54 in a 7 kW AC charge; scale unknown | findings.md:132 |
| `1701` | `F449` | accelerator pedal (OBD PID 49): `00` at rest/regen/brake, `06`-`6A` pulling away; scale not established | findings.md:182; DISCOVERIES.md:30 |
| `1656` | `D110` | 12 V rail in mV (14.0-14.2 V awake), pairs with `4947` | findings.md:153; modules.md:29 |
| `1670`,`1676` | `3019` | steering angle; encoding differs slightly from `1672` and `1676:3019` matched `1670:3019` minutes apart — verify the scale before extending `steering_angle` | findings.md:159, 175 |
| `1BB3,1BB4` | `435F`-`4362` | four duty channels (same shape as `435C`/`435D`): sit at 15 %, drop to 0 on the indicating side — DRL/position dimming (guess) | findings.md:260 |
| `1A01` | `4218` | wiper switch/mode state: `00`/`20`/`40`, changed with the button, reads `40` through the day; labels unknown | findings.md:188; DISCOVERIES.md:22 |
| `1A01` | `4443`,`45A3` | gain the same door/tailgate ajar bits as `42F2` | findings.md:190 |
| `1A01` | `42F9` last byte | follows `driver_occupied` (`20A8`) | findings.md:188 |
| `1A01` | `411D` | `90` -> `00` after locking, alongside `4222`: home-safe lighting (weak) | findings.md:191 |
| `1A12,1A13` | `4096` | changes with the window drive command, not position | findings.md:208, 214 |
| `1A12` | `480C` | speed copy: read 33 at ~33 km/h (once) | findings.md:208 |
| `1A13` | `400E` | `07` -> `08` while the window switch is held | findings.md:214 |
| `1A15` | `D907` | tailgate motion: ~`0x0877` while moving, near 0 at rest | findings.md:220 |
| `1650` | `EEE1` | counter, +1 during a charge | findings.md:149 |

## 4. Divergence warnings

Same DID, different meaning — proven on this car; never carry a decode across modules:

- `D906`: brake pedal sensor B on `1701` (findings.md:180; signals.yaml:195) vs tailgate position 0..~3198 on `1A15` (findings.md:219; signals.yaml:125).
- `D938`: park_selected `00`/`01`/`02` on `1201` (findings.md:43; signals.yaml:180) vs a rolling window-run log of 10-byte records on `1A12` (findings.md:208).
- `D927`: front-left flap position on `1A11` (findings.md:200; signals.yaml:137) vs a camera variant entry on `1301` (`D921`-`D927`; findings.md:64).
- `EE13`: discharge counter (mAh) on `1635` (findings.md:127; signals.yaml:27) vs unknown on `1656` (findings.md:153) and hazardous on `1301`, where a read can knock the ECU off the network (findings.md:65). Never broadcast-read it.

Withdrawn or non-portable decodes — do not republish:

- `1637:E319` was published as "forward gear"; it is torque direction, and the parked gear decode from `D938`/`E319`/`E307` would read R while regenerating in D (findings.md:143; DISCOVERIES.md:39).
- `1C01:D112` bit `02` was published as the driver belt; the low bits track supply voltage (findings.md:273; DISCOVERIES.md:38).
- Single-pass decodes withdrawn as time-confounded: `1601 E391`/`E392`/`E4AF` (findings.md:91; DISCOVERIES.md:40); `1701 2B33` is noise, not one-pedal (findings.md:183; DISCOVERIES.md:156).
- US-car meanings that do not hold here: `DD0A 0d` = "on", not driving (findings.md:12); `1201 D938 01` = "not in P", not moving (findings.md:43; DISCOVERIES.md:85).
