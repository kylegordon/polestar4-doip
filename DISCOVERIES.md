# Discovery log

One entry per release. A release marks the end of a session at the car (or a batch of sessions) and records what was learned: new signals, modules identified, corrections, and what was looked for but not found. Releases are notes only; there are no assets. See "Releases" in `README.md` for the process.

Confidence follows `catalogue/signals.yaml`: **C** = the same change seen at least twice in both directions; **P** = anything less.

<!-- New entries go directly below this line, newest first. The heading must be "## <version> - <title>". -->

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
