# Discovery log

One entry per release. A release marks the end of a session at the car (or a batch of sessions) and records what was learned: new signals, modules identified, corrections, and what was looked for but not found. Releases are notes only; there are no assets. See "Releases" in `README.md` for the process.

Confidence follows `catalogue/signals.yaml`: **C** = the same change seen at least twice in both directions; **P** = anything less.

<!-- New entries go directly below this line, newest first. The heading must be "## <version> - <title>". -->

## 2026.11.22.2 - 360 cameras on 1015, remote climate and seat heat, Mobileye versions

Unattended in park: climate and seat heat driven from the Polestar app (through Home Assistant) with nobody in the car, a sweep of every readable string the modules return, and a comparison of two whole-car snapshots taken two days apart on the same software (4.2.11).

**New**
- `1015` is most likely the 360 camera and park assist module (from its own strings; not yet tested with the camera view): it lists four surround-view cameras (OmniVision `OX03C10` sensors), holds the parking sensor distances, and runs park-assist software (`PAS_V2.8.2`). Its label WAM is Volvo's abbreviation for Wide Angle vision Module, the 360 side-camera unit in a Volvo technical bulletin ([NHTSA copy](https://static.nhtsa.gov/odi/tsbs/2019/MC-10170176-9999.pdf)).
- Remote climate: `1A11:9804` byte 3 shows climate running (C); `1A11:D214` is a log that gains an entry at each climate start (P); `980E` byte 0 may be the blower level (P).
- The app's target temperature is applied only when climate starts (C): started at 28 °C both temperature flaps go straight to full hot, at 16 °C they start near cold. Changing it while climate runs does nothing.
- Seat heat from the app is also applied at climate start and dropped when it stops. The app's front-left seat is `1A28` (the passenger seat on this right-hand-drive car), front-right `1A27` (driver), rear-left and rear-right the two halves of `1A29` (twice each).
- Reclassified from earlier sessions (2026-11-20 and 11-21): both steering controllers (`1670`, `1676`) are now catalogued as the two channels of the power steering (same steering angle, same assist load at full lock).
- `1301` (Mobileye SuperVision) version strings: the software package name, the main build `SV52_P417` (SV52 = Mobileye SuperVision) and the boot build. The package name gained a suffix between two days with no car update; it is now read daily.
- `1011` names the downloaded 4.3.0 update package and keeps an update campaign log.

**Corrections**
- `1015` was described as wireless access / digital key (2026.11.11 onwards). Its own strings point to the 360 camera / park assist module; "PAS" most likely means park assist, not passive entry.

**Also from manufacturer bulletins (published by NHTSA, linked in [modules](docs/modules.md#label-sources-manufacturer-bulletins))**
- Polestar's own bulletins call the Polestar 4 gateway VGM, so the VCM label on `1001` may be wrong (correction to the label, not to any signal).
- The CDD label on `1650` means Charger and DCDC Module: per the bulletin it also holds the DC-DC converter.
- A WAM (`1015`) fault can make a full software update fail until the WAM gets its own fix (Polestar 4 TJ 37940).

**Looked for, not found**
- The climate setpoint itself in any `1A11` DID (only its effect on the flaps).
- Steering wheel heat requested from the app: no change on `1A01:EE71` in two attempts.

## 2026.11.22 - Full scans finished, washer and key card, and the app's battery level

Parked sessions on 2026-11-20 and 2026-11-21, one short drive, an unattended overnight scan with an AC charge, and a comparison against ten days of the Polestar app's own readings (battery level, charging, tyres).

**New**
- Every answering module has now been read across its whole `0000`-`FFFF` range (`16A1` never answers), including the driver-assistance computer `1301`, read slowly while parked with no drop-outs (132 DIDs; 5 skipped as possible hazards). Its `EF11` names the boot software for an Infineon AURIX TC39x chip in that unit (`GAS52EVO_BOOT_P417`, August 2025).
- `1A01:420A`/`41E9` are the washer request, not a wiper state (C): one ~1 s pulse per washer press, none on plain wipes.
- `1A01:4222` drives the welcome lights (C): the front badge on one walk-up with the key, the rear lights on the other, about 30 s each, in step with it.
- `1A01:D214` (and `D218`) is a key card reader log (C): one entry pair each time the card is put on the phone pad or taken off.
- `1601:E4A1` / 10 is the battery level the app shows (P, 45 readings, r 0.9994); `1601:E37A` shows the same in finer steps (P).
- `1650:EE12` is the AC supply voltage while charging, in volts (P).
- Over the overnight charge (62-80% shown) the app's battery level was a straight line of the battery pack's own state of charge (`1635:4801`), about 1.16 shown points per pack point (lead; one charge, so the ends of the scale are not known).
- Both steering controllers (`1670`, `1676`) show the assist load (`D901`) peak at full lock: both share the work. `1675:FE08` again followed brake pressure on a drive (r 0.95).
- `1A15:2000`/`2100` hold a small fault-snapshot-style header (clock, odometer, power mode).

**Corrections**
- `1A01:420A`/`41E9`: "wiper state" (2026.11.13) was the washer request.

**Looked for, not found**
- Belts and seat occupancy on `1C01`: its full range is now read (114 DIDs, twice as many), but not yet tested against buckling up.
- Tyre pressures: nothing read so far follows the app's four pressures (229-261 kPa over ten days). Candidates go into the next drive.
- Steering Feel Firm (two rounds each way, 2026-11-20), Hill Descent Control (2026-11-14, partly repeated 2026-11-20) and One Pedal levels (2026-11-14): no DID changed for them in the modules watched.
- Brake pedal position on the CEM (`42D9`, `42FC`): no change with light or firm presses.
- A key distance or UWB range reading: none found on a walk round the car.

**Also seen**
- The car shifted itself to P after about 10 minutes standing in D, in the 2026-11-14 and 2026-11-20 parked sessions.

## 2026.11.19.2 - Sibling cars, radio filings and two module leads

Offline: dismantler listings, FCC filings and Geely-group sources, checked against the recorded runs. A new page, [`docs/siblings.md`](docs/siblings.md), lists the cars that share parts with the Polestar 4 and asks their owners to compare notes.

**New**
- Sibling cars on the same SEA platform: Zeekr 001/007/X, smart #1/#3, Lotus Eletre/Emeya, Volvo EX30. Same part so far: the rear motor (Zeekr 001; the same motor family on the smart #1) and the `1675` part (Zeekr 001).
- `1675` is probably a Bosch chassis sensor, not a brake unit (inference): the part number it reports in `D901` is sold used from a Polestar 4 and a Zeekr 001 as a Bosch sensor, called an acceleration or speed sensor. Its `FE08` follows brake pressure (r 0.988), not deceleration (r -0.26), so `FE08` and `D941` look like signals it receives.
- `1316`/`1317`: a used part with the same part numbers is a Polestar-branded box with a wire antenna and CE, RCM and FCC marks but no FCC ID. A dismantler calls it a tailgate control unit; what it does is still open.
- Key system (FCC filings): the GE1 module in `1023` is Bluetooth LE and its label drawing is headed Lotus; the NFC reader is filed as "Lotus NFC Reader"; the car has six UWB anchors on CAN. The front radar is Bosch's "Front Radar Gen5 Car Plus".

**Corrections**
- `1675` is no longer described as a second brake unit (2026.11.16 and 2026.11.19 entries); the `FE08` brake-pressure match stands, but as a received signal.

**Looked for, not found**
- FCC or other radio IDs in the car's own diagnostic data: none in any recorded read.

## 2026.11.19 - Brake pedal on the CEM, and 1675 reads like a brake unit

Parked: three noted brake press/release rounds and an audio test. Then a 10-minute drive, not narrated. Checked against all earlier watch logs and the 108 snapshots.

**New**
- `1A01:42F6` is the brake pedal (C): `01` while pressed, in step with `1701:2B00` in all three rounds and six presses on the drive. The stop lamps `4223` lit 21 more times on regen with the pedal released; `42F6` stayed `00` every time.
- `1701:2B00` brake pedal switch: now C.
- `1675:D941` is vehicle speed (P), 256 counts per m/s like `1631:D003`. Both `1675:FE08` words track `1701:FE08` channel 1 while braking (r 0.988, P): more support for `1675` being a second brake unit.
- `1212:DD02` is a 12 V supply reading in 0.25 V steps (P).
- The stop lamps stay on about 2 s after the pedal is released while the car is slowing.

**Looked for, not found**
- `1212` (labelled audio amplifier): none of its 21 DIDs changed for audio on, volume, play/pause or an EQ change. The label is still unchecked.

## 2026.11.16 - Reanalysis of every run

Offline: all watch logs (212 files, 2026-11-11 to 11-15) and 108 snapshots re-read together, each published claim checked against the other modules' readings.

**Held up**
- Speed sources agree within 0.3 % (`1631:D003`, `1601:E36E`, the four wheel speeds, `1701`/`1675` `F40D`). Both motors run at 82.8 counts (rpm, P) per km/h of their own axle's wheel speed. Wheel corners hold in both turn directions. `2B11` (+ = speeding up), `E319` (traction never draws negative current), the stop lamps on regen from about 0.6 m/s², `EE13`/`EE14` against the integrated current (`EE13` gross discharge, `EE14` charging only, not regen), `D112` at about 0.08 V on five modules, and the yaw rate in `1614:D92D` (median ratio 1.02 and 0.97 against the rear wheels over 24 10-s and 15 20-s windows; single reads scatter 0.6-1.6).
- The one-unit pairs `1201`/`1202` and `1633`/`1672` share a real serial. `1631`/`1637` and `1670`/`1676` share only a placeholder, which says nothing.

**New**
- `DD00` is a clock in 0.1 s steps, shared by every module; its reads over five days fall on one line against the laptop clock, overnight sleeps included. Module logs stamp entries with it: the door window logs (`1A12`/`1A13:D938` bytes 6-9) and `1316`/`1317:D237`, so their entries can be dated.
- `1670:3019` = `0x3853` - 0.5614 x `1672:3019` (r -0.997, about 230 changes): opposite sign; if `1670` counts 0.1 ° (inference), `1672` is 0.0561 °/count (by eye: 0.0554).
- `1675` may be a second brake unit (weak): its `F40D` speed moves with the car (published as never seen moving), and its `FE08` is a pair of close words like `1701:FE08` channels 1-2, about zero parked with the brake off and `0x113`-`0x1a9` in R or D on one day (four snapshots).

**From issue #2** (thanks to the US owner who worked these out on their own car and shared them)
- Suspension corners, `1614:D902` and `D93A` (P): front left, front right, rear left, rear right. Checked on this car's 2026-11-11 drives: `D902` front minus rear follows the longitudinal acceleration (`2B11`, r 0.87) and left minus right follows yaw x speed (r 0.59), left turns extending the left pair; `D93A` reads in front and rear pairs, the front a count above the rear in Firm.

**Corrections**
- `1316`/`1317:D237` is a heartbeat log (types `05`/`06` every 305 s, `07`/`02`/`04` at power changes), not traffic events. `1316`/`1317` have different software parts (the 2026.11.13 wording said shared). `1A12` no longer calls them side radars.
- `1701:FE08` channels 3-4 read only 3-6 % of channel 1 while braking on drives (the one parked hard press read about 55 %): not a plain rear-axle pressure.
- `1631:E312` runs at about 70 counts per km/h, not the motors' 83, so it is not simply the front motor speed.
- `1676`: the serial it shares with `1670` is a placeholder, so it no longer counts as evidence.

## 2026.11.15.3 - Hardware catalogue

Offline, from the identification reads in the 2026-11-10 to 2026-11-12 full scans.

- New `catalogue/hardware.yaml`: hardware and delivery part numbers for all 43 modules, and the physical components known so far with sources.
- Two pairs of addresses are each one physical unit (same part numbers and the same ECU serial, different software): `1201` infotainment with `1202` camera/vision, and `1633` gear stalk with `1672` steering angle.
- Shared parts: the two seats (`1A27`/`1A28`), the two headlamps, and the `1316`/`1317` pair. Seven door and seat units carry the same F18A code (`100057`), probably one supplier.
- Makers from the owner's manual's radio certification pages: `1023` is the key system's BNCM by Marquardt (model GE1), not the phone charger as we had it; the phone charger is by Changzhou Tenglong; the one certified radar is the F5CP12 front-centre unit, FCC ID NF3-F5CP12 (NF3 is Bosch's FCC grantee code). With only one radar certified, the corner-radar guess for `1316`/`1317` looks weaker.

## 2026.11.15.2 - Motor speed in rpm and the gear ratio

Offline, from the 2026-11-15 drive data and two owner's manuals.

**Signals**
- `1601:E3E8`/`E3E9` read motor speed in rpm (P for the unit). Both motors run at about 82.8 rpm per km/h, so at the published 200 km/h top speed they would reach about 16,570 rpm. The [Polestar 4 UK manual](https://www.polestar.com/uk/manual/polestar-4/2025/article/0ed816eed33d98cac0a8cc377bc12bc7-241d345d2bf41f36c0a8b0973d024aff-8664b2fa77a7e089c0a8296870d1a409) names the rear motor TZ220XSA02; the [Smart #1 manual](https://my.smart.com/wp-content/uploads/2024/06/HX11-Digital-User-Manual-Malaysia-20240607.pdf) (Technical data) gives TZ220XSA01/02 a 16,500 rpm maximum, 200 kW peak and 343 Nm. The two agree within 0.5 %, which fits a top speed set by the motor's limit (inference).

**Leads**
- Overall reduction about 11.6-11.9:1 on 255/50 R20 tyres (no published figure; depends on the loaded tyre radius).
- Polestar describes a clutch that disconnects the front motor for efficiency, which matches the front motor winding down in Range.
- Module `1656` reports `HX1100`; `HX11` is the Smart #1 project code (a shared part, probably).

## 2026.11.15 - Long drive: wheel corners, yaw, drive modes, blind spot, battery capacity, a HUD hazard

A day-long drive (about 600 km, one DC charge) on 2026-11-15 with the scanner running throughout, a passenger calling out events, and short targeted watches.

**New signals**
- Wheel corners, `1601:E3E4`-`E3E7` (C): left front, right front, left rear, right rear. In tight turns both ways the outer front wheel was fastest and the inner rear slowest.
- Range vs Performance (C): in Performance the front motor (`1601:E3E8`) turns all the time; about 9 s after switching to Range it stops and stays stopped while cruising. Two switches each way while driving.
- Blind-spot lights (C): `1A13:4003` left and `1A12:4003` right, matched to cars alongside on each side; `32` lit after dark, `64` in daylight.
- Yaw rate, `1614:D92D` byte 2 (P): signed degrees per second, + = turning left; it matches the yaw worked out from the rear wheel speeds and the 1,713 mm rear track to within about 5 % above 30 km/h. Byte 0 of the same DID is road speed in whole m/s (P).
- `1635:EE14` counts mAh: over a 54 % DC charge it rose by as much as the integrated pack current (130.8 Ah).

**Battery**
- Capacity: 241.4 Ah per 100 % of `4801`, against 242.73 Ah rated: the BMS's own view, not an independent health test.
- DC charge: up to 394 A at 27 %, about 300 A at 50 %, 166 A at 80 % when stopped by hand; the pack warmed from about 21 to 31 °C over the last 45 minutes before the charger (preconditioning), and reached 42 °C.
- Pack resistance falls as it warms: about 52 mΩ below 10 °C, 35 mΩ at 10-20 °C, 31 mΩ at 20-30 °C.
- Dash charge vs `4801`: 100 % shown at 96.1 %, 52 % at 51.4 %, 15 % at about 17.4 %. The dash is a rescaled figure.

**Leads (not in the catalogue)**
- Matrix headlamps in traffic: main beam stays on with one moving shaded block per lamp; full dips came at roundabouts, not with streams of oncoming cars. Polestar quotes 32 pixels per lamp, matching the 32 bytes of `7022`.
- Phantom braking: three moments of brake pressure (`1701:FE08`) with the pedal at rest at motorway speed, each followed by a return to cruising speed; candidates for the system braking by itself, which the owner felt once or twice.
- Pilot Assist on/off was not found; it needs a dedicated test.

**Hazards**
- **Continuous polling of the head-up display (`1251`) while driving makes Pilot Assist show as unavailable** until the reads stop. Three passes; the first also polled `1601:EE27`, the third polled only the HUD and still did it, and `EE27` is read in every drive watch without trouble. Single reads and one pass of all nine DIDs were harmless, a 10-second loop was enough. The nine DIDs are now caution in `catalogue/hazards.yaml`. Not yet tried parked.

**Looked for, not found**
- Tyre pressure: `1A01:42ED`/`42EE` answer while driving but stay flat all day as the tyres warm; `45B2`/`45C9` refuse even while driving.
- Driver attention on `1012` (full scan, no new DIDs; nothing reacted to a yawn, hands off, mirror checks or a head turn). The speed limit shown in the car (not on the HUD DIDs). Live target data on the side radars `1316`/`1317`.

**Corrections**
- `2B11` on `1601` and `1701` is + = speeding up, not + = slowing (positive correlation with the change in speed on three drive days).

## 2026.11.14 - Parking sensors, drive mode, locks, seats, a second Mobileye hazard

A long parked session on 2026-11-14 (P and stationary D, owner at the car), plus offline analysis of earlier Mobileye reads.

**New signals**
- Parking sensor distances, `1015:B112`-`B121` (P): centimetres, matching the screen to within about 3 cm; 511 = nothing seen. Even DIDs are left, odd right: rear corners `B112`/`B113`, rear inner `B114`/`B115`, front corners `B116`/`B117`, front inner `B118`/`B119`; `B120`/`B121` are probably the two extra rear sensors (4 front, 6 rear on this car); they did not trigger, so their side is not yet known. They only report in R or D. They sit on `1015`, probably the keyless module, not a separate parking module.
- Drive mode, `1601:E450` (C): `01` Range, `04` Performance, switched twice each way in P. Setting ESC to Sport also selects Performance, and the front motor then reads engaged (`1631:E307`) even when stationary.
- Creep, `1601:E3B5` (P): `02` off, `01` on in P; `03` seen in D.
- Door locks (P): `4054` on the front doors, `4056` on the rear doors, `02` unlocked, `01` locked; door handles and `D921`/`FE11` follow the lock too.
- Window motor request, `D008` on the front doors (C): `00` stopped, `01` manual up, `02` manual down, `03` auto up, `04` auto down. Own-door window switches: `1A13:4036` (passenger door) and `1A21`/`1A22:403B` (rear doors): `01` first step up, `03` second step up; `02` first step down seen on `4036`. The driver-door panel switches are bits in `1A12:4035`; the passenger-window switch there does not show in it.
- Rear window position `4048` upgraded to C (both rear doors, full cycles).
- Seat heating (P): level `983E` (`00`/`20`/`40`/`60` = off/1/2/3 on the front seats; the rear module packs left and right levels into one byte), on/off `FD03`, heater output `F1F4` (cycles while heating). Module identities: `1A27` is the driver seat and `1A29` the rear seats (both modules now marked confirmed).
- Rear backrest recline, `1A29:40A3` bytes 2-3 (left) and 8-9 (right): `0x0013` upright, about `0x0213` fully back (P).
- Steering wheel heating, `1A01:EE71` byte 1 (C): `02` on. Other bytes of the same DID set for a few seconds when the wheel is bumped.
- Climate flaps: front left (passenger) `1A11:D927` and front right (driver) `D929` upgraded to C; rear temperature blend `D92D` and rear air distribution `D92F` (floor vs B-pillar vents) are C, with their targets in `9809`/`980A` (P).
- Rear fog lamps, `1A01:421C` (C): `0000ffff` on (the two short segments low in the rear light bar).
- Left blind-spot light, `1A13:4003` (P): `00` off, `32` lit, matched to what the driver saw.
- Charge cable present, `1650:EE31` (P): `01` with the cable in. `EE24` only follows charging, not the cable.
- Mobileye uptime, `1301:EE04` (P): milliseconds since boot. The unit takes about 30 s to boot after the car wakes and is unreachable until then.

**Leads (not in the catalogue)**
- Matrix headlamps confirmed parked: dipped beam lights only the nearside (low-numbered) end of the bottom row; main beam lights both rows, brightest toward the car's centre (left lamp segments 9-10, right lamp 7-8); left to right on both lamps, no flips.
- `1301:EE00` (and `D018`, the same values big-endian) looks like 45 internal supply rails in millivolts (14.0, 12.1, 5.0, 3.3, 1.8, 1.5, 1.1, 0.9, 0.85, 0.75 V). `EE01`/`D017` look like 10 temperatures. `EE10` lists 11 slots, the same number as SuperVision's 11 cameras. `EE11` names the release `SV52_P417_25.11.RC1`.
- `1650:EE12` reads 235-238 while a cable is in (`ffff` without). Mains voltage or the plug's proximity resistance (220 ohm = 32 A cable); not settled.
- Dash charge reading: 86 % on the dash at 87.2 % in the pack (`1635:4801`). The formula from issue #2 predicts 88.7 % here, so it does not hold near full; the gap shrinks as the pack fills.

**Hazards**
- **`1301:EE14` is blocked**, like `EE13`. A slow, one-at-a-time read of it (parked) stopped the Mobileye ECU answering; the passenger airbag lamp blinked off and on, and the gateway refused new diagnostic connections until the adaptor was unplugged and replugged. No dash warning; afterwards the ECU held two confirmed fault codes (no earlier fault read to compare). The tool now refuses `EE14` even if `catalogue/hazards.yaml` is missing.
- **`1601:D928`-`D92C`: no repeat of the silence.** Read one at a time with the module checked after each, `D928`-`D92B` answered "not supported" (NRC 31) and the module kept answering; `D92C` had already answered. The earlier silence was probably the car still waking. They stay recorded as caution for now.

**Looked for, not found**
- The climate temperature setpoint (front and rear), the steering wheel heating level, the glovebox, the rear reading light, rear seat occupancy and rear belts (the airbag module has only been read in its default ranges), key fob presence or UWB range, the vehicles drawn on the dash. One-pedal level, Steering Feel and Hill Descent could not be tested (greyed out in P; the test in D was cut short).

**Corrections**
- `1A11:980E` is not the front-left flap target (it did not move in eight setpoint changes); removed from the catalogue.
- `1A01:4222` carries more than the welcome lamp: one byte follows the rear fog lamps.
- The earlier reading of the matrix bottom row as a "matrix base pattern" while driving was the dipped beam.

## 2026.11.13 - Wheel speeds, motor speeds, corrections from an audit

Two drives and parked tests on 2026-11-13, unattended full-range scans, then a re-check of every catalogue signal and published claim against all recorded data. Several earlier claims were wrong; they are corrected here.

**Coverage**
- 4,401 DIDs now answer (`docs/did-map.csv`), up from 4,297. The full `0000`-`FFFF` range was read on `1A01`, `1015`, `1011`, `1201`, `1601`, `1701`, `1316`, `1317`, `1344` and `1650` (`1015` +25, `1A01` +19, `1201` +13, `1601` +13, `1635` +11, `1701` +8, `1001` +6, `1011` +3, `1316`/`1317`/`1344` +2 each).

**New signals**
- `1601:E36E` vehicle speed upgraded to C: median ratio 0.994-1.002 against `1631:D003` over 943 paired reads on five drives.
- Wheel speeds, `1601:E3E4`-`E3E7` (P): the same scale as `D003` (x 0.0140625 km/h), all four within about 1 km/h of each other, 0 at rest. Corner order unknown; `E3E4`/`E3E6` move together against `E3E5`/`E3E7` in turns.
- Motor speeds, `1601:E3E8`/`E3E9` (P): `0x4E20` (20000) at rest, about 83 counts per km/h. `E3E8` drops back to `0x4E20` when cruising and matches `E3E9` when pulling away, which fits the front motor disconnect Polestar describes for Range power delivery. A drive in each mode is needed to confirm.
- Longitudinal acceleration, `2B11` on `1601` and `1701` (P): about 128 counts per m/s², + = slowing; parked it reads an offset that changes with the slope.
- Brake: `1601:E3C7` (`0x4000` = none) tracks `1701:FE08` channel 1 (r 0.998, one drive); `1701:2B00` is the pedal switch (`00`/`42`) (P).
- Wipers on the CEM: `1A01:420A`/`41E9` toggle out of phase once per wipe (P). `4218` (`00`/`20`/`40`) changed with the wiper button but reads `40` through the day: a switch or mode state.
- Driver seat occupancy, `1A01:20A8`: `00` seated, `80` empty (P, 11 snapshots, standby and car on).
- `1C01:D112` is module supply voltage, x 0.08 V (P; tracks `1701:F442` at r 0.98-1.00). The same DID behaves the same way on `1316`, `1317`, `1344` and `1672`.

**Leads (not in the catalogue)**
- `1631` is probably the front drive motor controller (issue #2's name for it): `E307` goes to `02` and `E303` carries a motor speed only in short bursts when pulling away. `1637` is then the rear.
- `1011:FD50` holds the car's position: longitude and latitude as signed 32-bit big-endian milliarcseconds. One parked read matched where the car stood within about 100 m. Values are not published.
- `1A01:281F` holds the four TPMS sensor IDs, so TPMS lives on the CEM; no pressure found yet (values not published).
- `1701:F449` accelerator pedal position (OBD PID 49): 0 at rest, in regen and with the brake pressed.
- `1601:E46A` rises on lift-off regen as well as under the pedal (a deceleration demand?); the stop lamps were on whenever it was at or above about `0x4380` on one drive.
- `1A01:410B` looks like an ambient light sensor (a 16-bit level in daylight, `01 0000` in the evening; one day).
- `1344:D923` byte 0 behaves like a temperature, not traffic.
- Matrix headlamps `1BB3`/`1BB4:7022`: 84 bytes, 32 data bytes as two rows of 16 plus `ff` padding.
- Stop lamps light on regen with the pedal released: 10 of 11 lamp episodes on one drive were regen-only, at 0.6-1.0 m/s² (UNECE R13-H allows this below 1.3 m/s² and requires it above).

**Corrections**
- **Driver belt retracted.** 2026.11.12.2 gave `1C01:D112` bit `0x02` as the driver belt from one parked pass. The value moves with supply voltage several times a second with nothing touched; no belt DID has been found, with the car in standby or on.
- **`1637:E319` is torque direction, not forward gear** (as issue #2 said): `00` traction, `01` regen or no forward drive. It flipped 25 times in 3 minutes of driving in D, 22 times with the sign of the pack current. The gear decode in 2026.11.12 and `docs/findings.md` only works parked; while regenerating in D it would give R.
- **`1601:E391`/`E392` withdrawn** (published P as falling with pedal force). They drift by themselves near wake-up and ramp while driving; the parked pedal pass ran in one order over two minutes, so time and force can't be separated. `E4AF` ("rises with force") is a free-running 10 Hz counter. The other `1601` steppers from that pass are unproven.
- **`1601` hazard DIDs**: the silent reads were `D928`-`D92C`, not `D927`-`D92B` (`D927` answered normally). It happened 3 s after the car woke; silences mid-scan have also happened elsewhere with no special DID, so start-up is a likely cause.
- **Stop lamps `1A01:4223`** mean pedal or regen deceleration, not the pedal alone.
- **Down from C to P** (seen fewer than twice each way): charge lid `EFF5` (closing seen once), tailgate `D906`, rear windows `4048`, rear window end-stops `42C6`, door handles `D90C`.
- **Catalogue decodes**: headlamp status `4368` is now byte 0 as a bitfield (many values were unmapped); beam `42E7` adds `00` = off; door handle adds `03` (unknown); two example values replaced with real readings.
- **Wording**: `1301` `D921`-`D927` are seven camera entries with four type codes, not seven camera IDs; 51 DIDs (not 24) are rear-door only; `1670`/`1676` have 44 DIDs; `1316`/`1317` share software part numbers; `1614:D93A` Firm range is `0x30`-`0x57` and `D902` only weakly follows deceleration; `1635:EE07`'s -50 offset has not been checked against the dash; `1015`, `1656` and `1676` are candidate identities.

**Not found**
- Belt buckle (driver or passenger) and passenger occupancy, with the car in standby and on.
- Rain sensor (one confounded snapshot in rain).
- Tyre pressure, after full-range scans of `1A01`, `1601`, `1011` and `1015`.
- Distance or object values on `1316`/`1317` in a move-closer-to-a-wall test.

## 2026.11.12.3 - Findings write-up and suspension signals

No new car session: this publishes what was already known but only in working notes.

**New document**
- [`docs/findings.md`](docs/findings.md): every module with what it is, its signals, leads (unconfirmed observations, with how strong each is), what was looked for and not found, hazards, and the open questions (tyre pressure, wheel speeds, yaw, wipers, seat occupancy, surround view, charge port cover).

**New signals (P)**
- Suspension `1614` (drives on 2026-11-11): `D93A` four per-corner bytes, about `0x28` in Standard and `0x3c`-`0x55` in Firm with spikes on road inputs (damper command?); `D902` four signed per-corner values moving constantly and dipping under braking (ride height or body motion?). Corner order unknown.
- Outside air temperature `1635 EE07`, u16 x 0.01 - 50 C (offset from issue #2's follow-up; 7.0 C on a November night here, where -40 would give 17 C).

## 2026.11.12.2 - Brakes, mirrors, CEM and module names (first pass)

Evening of 2026-11-12, parked, plus an unattended session rotating scans and watches. Car: Polestar 4 **Coupe** (no rear window), customer software release 4.2.11 (EMEA). Much of this is single-pass and speculative, marked P: shared so others can test it on their cars.

**Coverage**
- 4,297 DIDs now answer (`docs/did-map.csv`), up from 3,270. Full default-range scans finished on the brake controller `1601` (689), CEM `1A01` (313, from 40), climate `1A11` (138), rear doors `1A21`/`1A22` (155 each, mirror images apart from `4240`/`4241`), all three seat modules and most of the left headlamp.
- Standard OBD-on-UDS info blocks (`F400`-`F4FF`, `F800`-`F8FF`) read on 42 modules (`F802`, the VIN, skipped). Unlike the US car in issue #2, almost nothing answers here: only `1701` (`F80A` = `BSCM-BrakeSystem`, plus PIDs `0D`, `1C`, `30`, `31`, `42`, `49`; `F400` = `00080011` and `F440` = `40800001`, identical to the US car), `1675` (`F40D` speed), `1601` (`F800` info-type mask only) and `1670`/`1676` (`F804`, an all-zero calibration ID). So there are no `F80A` module names on this car for most modules, and no `F4B2` battery-health PID.

**New signals (C)**
- Door mirrors, both sides (`1A12` right, `1A13` left): fold state `4053` (02 unfolded, 00 moving, 01 folded), fold motor `4052` (03/04 = direction, mirrored between sides, 00 stopped), heating `4051` (01 off, 02 on). Folded/unfolded and heating on/off twice each.

**New signals (P, single pass)**
- Bonnet: bit `0x80` of the ajar byte `1A01 42F2` (seen once each way; catalogued as its own P signal).
- Brake system `1701`: `FE08` = four signed channels that rise with pedal force, two higher than the other two (off ~0; light 118/128/-10/-3; hard 462/469/252/259): looks like per-wheel or per-circuit brake pressure, front-biased. `D905`/`D906` = two sensors in step (about 0 -> 300 -> 1030): pedal travel or force. `D945`, `D946`, `D948` also step with force. `2B00` 00 -> 42 with the pedal pressed.
- Brake controller `1601`: `E391`/`E392` fall together with pedal force; `E39D`, `E4AF`, `E362`, `EE2B`/`EE2C` also step; `E340`, `E455`/`E457` switch-like.
- Driver seat belt buckled: bit `0x02` of `1C01 D112`.
- `1701 F40D` speed (OBD PID 0D) and `F442` supply voltage (PID 42, 14.26 V).
- Customer software release: `1001 D0D0` holds "4.2.11" as ASCII hex digits written in ASCII (also as text in a telematics update record, `1011 FD4A`). Not in the catalogue (the decoder has no encoding for it).

**From issue #2 (a US owner's findings), checked against this car's recorded values**
- Agree: `1635 DA31` cell-group voltages (sum = `497C` within 0.05 V), `4907`/`4908` highest/lowest cell index + mV, `EE83` pack temperatures, `EE02` 12 V in mV, `489C`/`489E` charge/discharge power limits (u32 x 0.001 W; this car's charge limit is lower than theirs at the same SoC), `EE13` in mAh (unit provisional: one parked window), `1650 EE71` = lifetime AC energy. In the catalogue at P: `4907`/`4908`, `EE02`, `489C`/`489E`; `EE13` stays C with the unit noted, and `EE71` has corrected text (the array DIDs `DA31` and `EE83` are not, as the decoder handles scalars only).
- Differ: `DD0A` `0d` is "on" (also in P, R and N), not "driving"; `1201 D938` `01` = not in P (also when stopped), not "moving"; `1635 F45B` reads a constant `FF` here.
- Module labels: `1631` and `1672` may be the drive motor controller 2 and chassis controller (their `F80A` names); not readable here, so ours stay with a note.

**Leads (not in the catalogue)**
- Displayed SoC is about 1.9 points below `1635 4801` (dash ticked 68% -> 67% at a raw 68.9%). One point so far.
- CEM `4000`-`45FF`: 177 DIDs answered for the first time; the wiper, washer and rain/light-sensor state may be among them. None of the CEM DIDs known before moved in a first wiper/washer test, and that test ran before the CEM scan. To retest.
- `1601 D9AC`, `D921`/`D935`, `D989` and `D901` moved while driving (wheel speed / yaw candidates); `E3C7`/`E46A` sit at `4000` at rest (offset-binary). The Polestar 2 wheel-speed DIDs `2B06`-`2B09` are not supported here.
- `1601 D282` and `D911`-`D913` are not tyre pressures; no DID read so far matches the 2.3 bar the app shows. `2800`-`28FF` on `1A01`/`1601` still to read.

**Hazards**
- Still possible, not repeated: `1601` `D927`-`D92B` (see 2026.11.12.1). Scans here keep skipping them.

**Corrections**
- `1701` is the brake system (BSCM), not "brake control 2".
- The bonnet bit, `EE13` units and `EE71` meaning above replace earlier catalogue text.

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
