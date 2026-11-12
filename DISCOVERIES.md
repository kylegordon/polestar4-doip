# Discovery log

One entry per release. A release marks the end of a session at the car (or a batch of sessions) and records what was learned: new signals, modules identified, corrections, and what was looked for but not found. Releases are notes only; there are no assets. See "Releases" in `README.md` for the process.

Confidence follows `catalogue/signals.yaml`: **C** = the same change seen at least twice in both directions; **P** = anything less.

<!-- New entries go directly below this line, newest first. The heading must be "## <version> - <title>". -->

## 2026.11.12.1 - Doors and brake controller, first pass

One drive on 2026-11-12 with an unattended session rotating default-range scans and drive watches.

**Coverage**
- 3,270 DIDs now answer (`docs/did-map.csv`), up from 2,856: driver door `1A12` +143, passenger door `1A13` +126, brake controller `1601` +133 (126 in D9xx, 1 in EDxx, 6 in F1xx; the rest of `1601` is still to scan), passenger seat `1A28` +12 (`FD11`-`FD1C`, 42 bytes each; scan cut short when the adaptor was unplugged).
- `1A27` (driver seat, unverified label): nothing beyond the DIDs already known in the default ranges.

**New signals**
- Vehicle speed per the brake controller, `1601 E36E`, km/h x 1/256 (P).

**Leads (not in the catalogue)**
- `1601`: `D9AC`, `D921`/`D935`, `D989` and `D901` change while driving; candidates for wheel speeds, yaw or braking, to be tested with a fast watch.
- `1601 D911`-`D913` move together, each taking its neighbour's old value: looks like a rolling history rather than tyre pressures.
- Door modules: new DIDs that look like mirror fold, heat and position state; to be tested with a parked fold/unfold.

**Hazards**
- Possible: after reading `1601` `D927`-`D92B` (parked), the brake controller failed to answer a TesterPresent (the scan stopped) and answered normally to the next connection a second later. Not repeated yet. Scans here skip those DIDs until it is tested one DID at a time.

**Corrections**
- The 2026.11.12 entry's "full default-range sweep of every module" covered 28 of the 43 modules. Not yet swept: `1001`, `1201`, `1601` (part), `1A01`, `1A11`, `1A21`, `1A22`, `1A28` (part), `1A29`, `1BB3`, `1BB4`; `1301` is left at `EE13` on purpose.

**Not found**
- Tyre pressure: none of the 2,856 DIDs read before this session matches the 2.3 bar the app showed (the new DIDs are not checked yet).

## 2026.11.12 - First full map

Sessions on 2026-11-10 and 2026-11-11: parked mapping, two drives, a full default-range sweep of every module, and parked tests of gear, chassis mode, drive mode and one-pedal settings.

**Coverage**
- 43 modules answer on this car; 2,856 DIDs answer in the default sweep ranges (`docs/did-map.csv`).
- Module map with evidence for each module: `docs/modules.md`.

**New signals**
- Vehicle speed, `1631 D003` (C); speed with a `4000` offset, `1631 E312` (P, not yet in the catalogue).
- Gear, decoded from four values (C): `1201 D938` P, `1637 E319` D, `1637 E307` drive engaged (R or D), reversing lamp `1A01 4224`.
- Gear stalk `1633` reports only stalk movement, not the selected gear (P).
- Chassis mode, `1614 D90F`: Standard, Firm, Nimble (C). Per-corner damper level `1614 D93A` (P, not yet in the catalogue).
- Power mode `DD0A` and odometer `DD01`, the same on every module (P).
- HV pack current `1635 4802`, pack voltage `497C`, mean cell voltage `DA1D`, 12 V rail `4947` (P; agree with another owner's US car).
- Matrix headlamp segment brightness, `1BB3`/`1BB4` `7022` (P); headlamp status values for home-safe and approach lighting (P). Neither is in the catalogue yet.
- Earlier parked mapping (2026-11-10): SOC, charge state, doors, lamps, windows, door handles, tailgate, parking brake, steering angle, climate flaps, seat position.

**Modules identified**
- `1301` Mobileye SuperVision ECU (firmware names the Polestar 4 code `P417`; seven driver-assistance camera IDs).
- `1023` wireless phone charger (from its part number), `1015` digital key, `1676` redundant steering controller, `1701` second brake controller, `1656` probably on the 12 V / DC-DC path.
- `1316`/`1317` remain an unidentified left/right pair.

**Hazards**
- Reading `1301 EE13` knocks the Mobileye ECU off the network for about a minute. The tool refuses it on `1301` and on any functional address.

**Not found**
- One-pedal level and drive mode (Range/Performance): no DID changes with them, parked.

**Corrections**
- `1701 2B33` is a fast-changing live value, not a gear or one-pedal flag.
