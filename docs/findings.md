# Findings so far: Polestar 4 Coupe (UK)

What has been learned about one car, module by module, including leads that are not yet confirmed. Shared so other owners can check them on their own cars.

- **Car**: Polestar 4 Coupe (no rear window; camera rear-view mirror), UK, right-hand drive, customer software release 4.2.11 (EMEA).
- **Method**: read-only UDS `0x22` ReadDataByIdentifier over DoIP in the default session, through the OBD port, with the `./p4` tool. No session change, no security access, no writes. Meanings come from watching values change while doing something to the car (opening a door, pressing the brake, driving), not from names on other cars.
- **Confidence**: as in [`catalogue/signals.yaml`](../catalogue/signals.yaml). **C** = the same change seen at least twice in both directions; **P** = anything less. Signals are referred to by their catalogue `id`.
- **Lead** = an observation that is not in the catalogue: something moved once, or moved at a plausible time, or fits a plausible encoding. Each lead says how strong it is.
- Every answering DID, per module, is in [`docs/did-map.csv`](did-map.csv); module evidence in [`docs/modules.md`](modules.md); the dated history in [`DISCOVERIES.md`](../DISCOVERIES.md). Counts below are answering DIDs as of 2026-11-13: the default scan ranges on every module, and the full `0000`-`FFFF` range on `1A01`, `1015`, `1011`, `1201`, `1601`, `1701`, `1316`, `1317`, `1344` and `1650`.
- Most modules have never been watched while something happens to them. "Nothing seen" usually means "not looked at in the right moment", not "absent".

**Common to every module**: `DD01` odometer in km (`odometer`, P), `DD0A` power mode (`power_mode`, P: `01` parked, `02` awake, `0d` on, which includes sitting in P, so it does not mean driving), `DD00` a clock in 0.1 s steps, the same on every module to within a few counts. Against the laptop clock its reads from 2026-11-11 to 2026-11-15 (1,165 on `1316`) lie on one straight line (0.4 s scatter) across the overnight sleeps, so it keeps counting while the car sleeps; extrapolated back, zero falls in 2025. Module event logs stamp their entries with it (2026-11-16). `D904` on several modules moves `0x96`/`0x97` with load: probably supply voltage in 0.1 V (lead, weak).

**OBD-on-UDS info blocks** (`F400`-`F4FF`, `F800`-`F8FF`, VIN skipped) were read on 42 modules. Unlike a US car (issue #2), almost nothing answers here: only `1701`, `1675`, `1601` (`F800` only) and `1670`/`1676` (`F804`, all zero). So `F80A` module names are not available for most modules on this car.

## 1001 Gateway

- **What it is**: the DoIP entity (logical address `1001`); tester `0E80`, functional address `1FFF`. 88 DIDs. Gateway firmware build string dated December 2025.
- **Leads**: `D0D0` holds the customer software release "4.2.11", stored as ASCII hex digits written in ASCII (P; the decoder supports `encoding: ascii-hex`, but no full-payload raw is quoted here yet, so it is not catalogued). The same release appears as text in a telematics update record (`1011`).
- **Not found**: no range or distance-to-empty value; values that happened to match the displayed range were configuration or hash bytes.

## 1011 Telematics

- **What it is**: the car's mobile connection (TEM label, unverified). 119 DIDs. Holds SIM and modem identifiers, two assistance phone numbers, a current date-time, a release string (`P417_4.2.11_…`) and server names. Identifiers are masked by `./p4 strings` and not published.
- **Leads**: `FD50` (10 bytes) holds the car's position: two signed 32-bit big-endian values in milliarcseconds (degrees x 3,600,000), longitude then latitude. One parked read matched where the car stood within about 100 m (P; values never published). A configured GB/T 32960 (Chinese national EV remote-monitoring standard) server entry, on a UK car. Whether it ever sends anything is not known. The phone app shows tyre pressures; none found here after a full-range scan.

## 1012 Driver monitoring

- **What it is**: label guess (DMM) from related cars; not checked. 53 DIDs; a full `0000`-`FFFF` scan on 2026-11-15 found no more.
- **Not found**: driver attention. A 10-minute watch of its 34 non-identity DIDs while driving (2026-11-15) saw no change at a yawn, hands off the wheel (the car warned), mirror checks, a head turn or an eye rub; only `D963`-`D966` and `DD02` flicker by one step all the time (temperatures or supplies, guess). The hands-off warning probably comes from steering torque, not this module.

## 1015 Wireless access / digital key

- **What it is**: keyless entry and phone-as-key. 162 DIDs. Software names include `PAS_VE` (passive entry?) and `…CCA…`/`…CCR…` strings, perhaps Car Connectivity Consortium digital-key components (guess). Polestar documents UWB, BLE and NFC key-card for this car.

- **Signals (2026-11-14)**: the parking sensor distances live here, `B112`-`B121`, in cm (511 = nothing seen), matching the screen to within about 3 cm. Even DIDs are left, odd are right: rear corners `B112`/`B113`, rear inner `B114`/`B115`, front corners `B116`/`B117`, front inner `B118`/`B119`; `B120`/`B121` are the two extra rear sensors (the car has 4 front, 6 rear) and have not triggered yet. Active only in R or D (P).
## 1023 Key system control module (BNCM)

- **What it is**: the key system's BNCM, made by Marquardt. It reports `F197` = `BNCM` and `F18A` = `MARQUARDT`, and the owner's manual's [key system certification](https://www.polestar.com/uk/manual/polestar-4/2026/article/0a500a085a173960c0a8b09771bff25e-f19ebb76fc2e9629ac1b7acc5528389d-8664b2fa77a7e089c0a8296870d1a409/) lists a Marquardt BNCM (model GE1, FCC ID IYZGE1) with a UWB anchor (GU1), NFC reader (GR3) and key fob (GK2). 142 DIDs. The phone charger is a separate part: the manual's [wireless charger and NFC approval](https://www.polestar.com/uk/manual/polestar-4/2026/article/d8eb41f1d4b91c11c0a8cc3748b783e2-dfdd3d233eb7acaec0a8b0c176da1984-8664b2fa77a7e089c0a8296870d1a409/) names Changzhou Tenglong Auto Parts as its maker. `F1BB` lists part `6608017285`, which a parts shop sells as "control unit for wireless charging", perhaps the charger pad as a sub-unit (inference). This replaces the earlier "wireless phone charger" reading (2026-11-15).
- **Leads**: none yet. Not yet watched: a key fob or phone key approaching, and a phone on/off the charging pad (in case the pad is its sub-unit).

## 1201 Infotainment

- **What it is**: IHU. 133 DIDs.
- **Signals**: `park_selected` (`D938`: `00` P, `01` not P, `02` changing; C). `01` is "not in P" even when stopped in D, R or N.
- **Not found**: the displayed SoC and range (no value matching 59 % or 161 mi when shown); three distance-to-empty-like DIDs read `00`. `D931` reads `02` at each new connection then `00` (connection artefact).

## 1202 Camera / vision

- **What it is**: label guess; not checked. 22 DIDs. A second diagnostic address on the infotainment unit (`1201`): same core and delivery part numbers and the same ECU serial, with its own seven-entry software list (2026-11-15, from the 2026-11-10/11 scans).

## 1212 Audio amplifier

- **What it is**: label guess; not checked. 21 DIDs.
- **Signals** (2026-11-19): `supply_v_1212` (`DD02`, 12 V in 0.25 V steps; follows the 12 V rail `1635:4947` over 1,180 paired readings; P).
- **Not found**: none of the 21 DIDs changed for audio on, volume up and down, play/pause or an EQ change (2026-11-19, parked, noted). The amplifier label is still unchecked.

## 1213 Rear-seat entertainment

- **What it is**: label guess; not checked. 29 DIDs.

## 1251 Head-up display

- **What it is**: label guess. 22 DIDs. Answers physical addressing only, not the `1FFF` broadcast.
- **Hazards**: continuous polling of `D110`, `D904`, `D905`, `D992`, `D993`, `D995`-`D998` while driving makes the car show Pilot Assist as unavailable, again and again until the reads stop (2026-11-15, three passes; the owner judged it not unsafe). Single reads, five quick reads of `D110` and one pass of all nine did nothing; a 10-second continuous loop was enough. Not yet tried parked. The nine are **caution** in `catalogue/hazards.yaml`.
- **Not found**: the speed limit shown in the car (40 and 50 mph called out during a watch): none of the nine follows it.

## 1301 Mobileye SuperVision ECU

- **What it is**: driver-assistance computer. Firmware string names `P417_EU` (P417 = Polestar 4 model code) and `GAS52`, built January 2026. `D921`-`D927` hold seven camera entries, but only four distinct type codes (`CAM000022`-`25`), so they are variant codes rather than per-camera IDs. 111 DIDs; the scan stops before `EE13` on purpose.
- **Hazards**: **never read `EE13` on `1301`.** Twice (once parked and unattended) it knocked this ECU off the network (gateway NACK), the second time for about a minute, with no dash warning. A `1FFF` broadcast or a range sweep through `EE13` reaches it too. The tool refuses the read. `1635:EE13` is a different module and is safe. `1301` is kept out of watches while driving.
- **Leads (2026-11-14)**: `EE04` = uptime in ms (catalogued, P); the unit is unreachable for about 30 s after the car wakes while it boots. `EE00` (and `D018`, same values big-endian) looks like 45 supply rails in mV (14.0, 12.1, 5.0, 3.3, 1.8, 1.5, 1.1, 0.9, 0.85, 0.75 V); `EE01`/`D017` like 10 temperatures; `EE10` lists 11 slots, the same as SuperVision's 11 cameras; `EE11` names the release `SV52_P417_25.11.RC1`. `DB00`-`DBD2` answer "not supported".
- **Hazards (2026-11-14)**: `EE14` does the same. A paced read of it (parked, the first DID after `EE13`) stopped `1301` answering; the passenger airbag lamp blinked off and on, and the gateway refused new diagnostic connections until the adaptor was unplugged and replugged. No dash warning; afterwards `1301` held two confirmed fault codes (there is no earlier fault read to compare with). `EE14` is blocked like `EE13`.

## 1314 Dash camera

- **What it is**: label guess (DVR); not checked. 51 DIDs.

## 1316 Unknown (left of a pair)

- **What it is**: unknown. Same hardware and delivery part numbers as `1317` but different software parts (`F1AE` part numbers ending `39` rev D vs `37` rev C), serials 7 apart (a few other part-number DIDs differ), same 36 DIDs. Sits next to the front radar in the driver-assistance address range. Guesses: a left/right sensor pair (the manual certifies only one radar).
- **Leads**: very few live values (fewer than `1317`). `2000`-`2D2B` is empty. `D112` is module supply voltage (x 0.08 V), as on `1C01`.

## 1317 Unknown (right of a pair)

- **What it is**: pair of `1316` (see above). 36 DIDs.
- **Leads**: `D237` (on both `1316` and `1317`) is a 10-entry log of 5-byte records: a type byte, then the `DD00` clock little-endian. Types `05` and `06` come every 305 s, 5 s apart, all day: a heartbeat, not sensor events (2026-11-16, 366 and 333 entries decoded). Types `07`, `02`, `04` cluster at stops and wake-ups: power-state changes. So its changes on drives say nothing about traffic. `D005` and `E103` also change. `D112` is module supply voltage. A move-closer-to-a-wall test on 2026-11-13 showed no distance values on either side.

## 1344 Front radar

- **What it is**: label guess (FLR); not checked. 45 DIDs. The manual's [radar type approvals](https://www.polestar.com/uk/manual/polestar-4/2026/article/d8eb41f1d4b91c11c0a8cc3748b783e2-9bc02397d4b9ca5fc0a8cc37097af9c5-8664b2fa77a7e089c0a8296870d1a409/) list one radar, the front-centre unit F5CP12 (FCC ID NF3-F5CP12; NF3 is Bosch's FCC grantee code), 76-77 GHz. That this address is that radar rests on the label.
- **Leads**: being watched with `1316`/`1317` while the cluster draws surrounding cars; nothing correlated yet. `D923` byte 0 rises one step every 30-60 s after the car wakes and falls after use: behaves like a temperature, not traffic. `D112` is module supply voltage (x 0.08 V), as on `1C01`, and reads within 1-2 counts of `1C01`, `1316`, `1317` and `1672` in every snapshot that has them.

## 1601 Vehicle dynamics / parking brake

- **What it is**: brake and stability controller with the electric parking brake (VDDM label; our label rests on the parking-brake behaviour). 702 DIDs, the largest map on the car. A US owner's `F80A` reads a hybrid-powertrain-controller name for `1601` (issue #2); here `1601` answers `F800` only, so the name cannot be read.
- **Signals**: `epb_state` (`E37B`), `epb_position` (`2B1A`), `epb_lamp` (`2B15`), `epb_operations` (`2B20`, counts on each release) (all C; also the automatic release/apply on shifting out of and into P, five cycles). `vddm_speed` (`E36E`, km/h x 1/256, C: median ratio to `1631:D003` 0.994-1.002 over 943 paired reads on five drives). `wheel_speed_1`-`_4` (`E3E4`-`E3E7`, same scale as `D003`; all four within about 1 km/h of each other and 0 at rest; corners from 2026-11-15 turns in both directions: `E3E4` left front, `E3E5` right front, `E3E6` left rear, `E3E7` right rear; outer front fastest and inner rear slowest, e.g. right lock 1.17/0.94/1.08/0.81 of the mean; C). `motor_speed_front`/`_rear` (`E3E8`/`E3E9`, raw `0x4E20` at rest (decoded as 0), about 83 counts per km/h; `E3E8` drops to `0x4E20` when cruising and matches `E3E9` when pulling away, and on 2026-11-15 (two switches each way while cruising) the front motor turned on every read in Performance and stopped about 9 s after switching to Range, staying stopped while cruising: Range drives on the rear motor alone; `motor_speed_front` C, both motors about 82.8 counts per km/h). The counts look like motor rpm (P): at the published 200 km/h top speed they would reach about 16,570, within 0.5 % of the 16,500 rpm maximum that the [Smart #1 manual](https://my.smart.com/wp-content/uploads/2024/06/HX11-Digital-User-Manual-Malaysia-20240607.pdf) (Technical data) gives for motors TZ220XSA01/02 (200 kW peak, 343 Nm); the [Polestar 4 UK manual](https://www.polestar.com/uk/manual/polestar-4/2025/article/0ed816eed33d98cac0a8cc377bc12bc7-241d345d2bf41f36c0a8b0973d024aff-8664b2fa77a7e089c0a8296870d1a409) names the rear motor TZ220XSA02. With 255/50 R20 tyres that makes the overall reduction about 11.6-11.9:1 (inference; no published ratio). Polestar's own pages describe a clutch that disconnects the front motor, matching the spin-down. `long_accel_vddm` (`2B11`, signed, about 1/128 m/s² per count, + = speeding up (sign corrected 2026-11-15: it was published as + = slowing; the correlation with the change in speed is positive on three days); parked it reads an offset that changes with the slope: P). `brake_pressure_vddm` (`E3C7`, `0x4000` with the brake released; = 7.2 x `1701:FE08` ch1 + 40, r 0.998 on one drive; over all drives 7.06 x ch1 + 95, r 0.964; P).
- **Signals (2026-11-14)**: `drive_mode` (`E450`: `01` Range, `04` Performance; C, switched twice each way in P; mirrored in `E425` byte 0, and `E42D` sets a byte in Performance). Setting ESC to Sport also selects Performance, and the front motor then reads engaged (`1631:E307`) even when stationary. `creep` (`E3B5`: `02` off, `01` on in P, `03` seen in D; P).
- **Leads**:
  - The parked pedal pass (off / light / hard, 2026-11-12) is confounded with time: it ran in one order over about 2 minutes. `E4AF` "rising" was a free-running 10 Hz counter, and `E391`/`E392` (published as falling with pedal force) also drift by themselves near wake-up and ramp while driving, so they are withdrawn. `E39D`, `E362`, `D925`, `EE2B`/`EE2C`, `D922`/`D939`, `E340`, `E455`/`E457` are unproven for the same reason.
  - `E46A` (`0x4000` = none) rises on lift-off regen with the pedal released as well as under the pedal: a total deceleration demand? The stop lamps were on whenever it was at or above about `0x4380` on one drive (P).
  - `E406` reads speed in whole km/h; `E467`/`E468` are a pair at `0x7F80` at rest moving with speed (about 128 counts per km/h; axle speeds?). More speed copies (2026-11-16, r above 0.99 against `1631:D003`): `EF10` and the four bytes of `EF11` in whole m/s (per wheel?), `E47C` (about 1/256 km/h), `E4CA`-`E4CE` (8-byte records, two words at about 1/128 km/h). `E3CF`/`E3D1`-`E3D3` (also in `E496`-`E49D`) form mirrored pairs under the pedal: per-wheel brake torque? (one pass).
  - `D9AC` (toggles `5280`/`51e0`), `D921`/`D935` (step together), `D989` (four monotonic steps) and `D901` (ramp then reset) changed while driving: wheel-speed or yaw candidates (weak; ~12-20 s sampling).
  - A byte at `E3A7` changes at each automatic parking-brake apply and `E3A6` at each release (seen over several cycles; meaning unknown).
  - `D905`/`D907`/`D914`/`D91A` changed together 45 s after the cluster showed two cars to the left (timing only).
  - The long `EExx`/`EFxx` blocks change on almost every read while parked: rolling logs or history buffers (guess).
- **Not found**: tyre pressures (`D282` holds several unequal words, about 455-560, when the app showed 2.3 bar on all four: ruled out; `D911`-`D913`: three values in steps of 5 around 2,600 that sometimes shift along and sometimes flicker: ruled out). The Polestar 2 wheel-speed DIDs `2B06`-`2B09` and other `2Bxx`/`20xx` dynamics DIDs return NRC 31 (not supported). `2B34` flips on its own when parked. Gear does not show here.
- **Hazards**: possible, not repeated: one silence of about 10 s while reading `D928`-`D92C` (earlier releases said `D927`-`D92B`; `D927` answered normally), 3 s after the car had woken. Silences mid-scan have also happened on other modules with no special DID, so start-up is a likely cause. The tool records `D928`-`D92C` as **caution** in `catalogue/hazards.yaml`: ordinary scans skip them, and `--allow-caution` or a paced scan is needed to test one. `D92C` has since been read without trouble. On 2026-11-14 a paced read (one DID at a time, module checked after each, car awake in P) got NRC 31 (not supported) on `D928`-`D92B` with `1601` answering after every read: no repeat. They stay caution for now.

## 1614 Suspension

- **What it is**: suspension/chassis control (SUM label). 52 DIDs.
- **Signals**: `chassis_mode` (`D90F`: `00` Standard, `40` Firm, `30` Nimble; C). `damper_cmd_c1`-`c4` (`D93A`, four per-corner bytes in equal pairs, ~`0x28` in Standard, `0x30`-`0x57` in one Firm interval, spikes on road inputs, Standard also spiking to `0x55`; P). `corner_motion_c1`-`c4` (`D902`, four signed per-corner values, move constantly while driving; ride height or body motion, + = corner extends; P). Both run front left, front right, rear left, rear right, as found on a US car (issue #2) and checked here on the 2026-11-11 drives (94 reads): `D902` front minus rear follows `2B11` at r 0.87 and left minus right follows yaw x speed at r 0.59, with left turns extending channels 1 and 3; `D93A` reads in front and rear pairs. `speed_ms_sum` (`D92D` byte 0, whole m/s, r 0.99 with `D003`; P) and `yaw_rate_sum` (`D92D` byte 2, signed deg/s, + = turning left; slope 1.05 against the yaw from the rear wheel speeds and the 1,713 mm rear track above 8 m/s; P, one drive). Rechecked 2026-11-16 over all drives: heading change summed over 10 s and 20 s windows gives a median ratio of 1.02 and 0.97 to the rear-wheel figure (24 and 15 windows), so about 1 deg/s per count holds; single reads scatter widely (slope 0.6-1.6 by speed band) because the two DIDs are read at different moments. The other yaw leads (`1601:EF06`, `EFA5`, `EFA6`) are not rates.
- **Leads**: `D901` behaves like `D93A`; `D903` moves constantly like `D902`.
- **Not found here**: drive mode is on `1601` (`E450`, see `1601`); one-pedal level not found anywhere yet.

## 1615 Steering column lock

- **What it is**: label guess (SCL); not checked. 25 DIDs. No wiper or washer DIDs answer here.

## 1631 Front drive motor controller (probable)

- **What it is**: probably the front drive motor controller, as issue #2's `F80A` name says: `E307` goes `01` -> `02` only in short bursts when pulling away or accelerating (about 1.5-2.2 m/s²), `E303` then reads `0x4000` + front motor speed (same ~83 counts per km/h as `1601:E3E8`), and `E319` reads `00` in those bursts like `1637:E319`. Labelled brake control (BCM) before; brake pedal and parking-brake DIDs return NRC 31 and no steering DIDs answer. A US owner's `F80A` reads "drive motor controller 2" (issue #2); not readable here. 103 DIDs. Traceability string with a production date and the model code P417. Shares 29 DIDs with `1701`.
- **Signals**: `vehicle_speed` (`D003`, km/h x 0.0140625; C). The dash reads about 5 % above it.
- **Leads**: `E312` is speed with a `0x4000` offset (r 0.97-0.99 over two drives; P, not catalogued), about 70 counts per km/h: not the 83 counts per km/h of the motor speeds, so not simply the front motor speed. `E335`-`E338` are four near-equal values (~`0x332c` parked), per-wheel guess; weak correlation with braking.

## 1633 Gear selector stalk

- **What it is**: the column gear stalk (EGSM label). 51 DIDs. One physical unit with `1672` (see there). Reports stalk movement only, not the selected gear.
- **Leads**: `D914`, `D915`, `D919`, `D920` go `01` -> `04` while the stalk is pushed (back within ~2 s); `DA02`/`DA03` go `01` -> `03` while held down (the N gesture); `DA00`/`DA01` jitter by a count or two (raw positions?). P, one test. The push and hold channels are in the catalogue as `stalk_push_*` / `stalk_hold_*`.
- **Not found**: the wiper button on the stalk (single wipe, washer) moved nothing here.

## 1635 HV battery (BECM)

- **What it is**: the battery management module. 209 DIDs.
- **Signals**: `hv_soc` (`4801`, C), `cell_soc_avg`/`max`/`min` (`DA19`/`DA17`/`DA18`, C), `charge_counter` (`EE14`, C; counts plug charging, not regen; mAh: a 54 % DC charge on 2026-11-15 added 130,836 while the integrated `4802` current gave 130.8 Ah), `discharge_counter` (`EE13`, C; mAh per issue #2 and our parked current; on 19 drive segments it rose 0.94-1.02 x the integral of the positive (discharge) current, so regen is not netted off), `charging_flag` (`49EF`), `charge_request_flag` (`49E5`), `charge_power_limit` (`49DD`, unit unknown), `pack_current` (`4802`, 0.1 A, `0x4000` = 0, + = discharge; regen to about -95 A seen), `pack_voltage` (`497C`), `cell_v_mean` (`DA1D`), `cell_max_index`/`cell_max_v` and `cell_min_index`/`cell_min_v` (`4907`/`4908`), `low_volt_rail_bms` (`EE02`), `low_volt_rail` (`4947`), `charge_power_limit_kw`/`discharge_power_limit_kw` (`489C`/`489E`), `outside_temp_becm` (`EE07`, 0.01 °C with a -50 offset) (all P).
- **Leads**:
  - `DA31`: 130 x u16 cell-group voltages in mV, 110 valid (`EE19` = 110); their sum matches `497C` within 0.05 V in nine snapshots. `EE83`: 30 pack temperatures, 28 valid (`EE20` = 28), 0.01 °C with -50 (gives 6.5-7 °C on a November night). `EE06` ambient, same encoding. Agree with issue #2; catalogued as `cell_group_voltages` and `pack_temperatures` (P, 2026-11-14) now that the decoder reads arrays.
  - Displayed SoC sits below `4801`: 59 % shown at 61.3 % raw; 65 % at 66.6 %; the dash ticked 68 -> 67 % at 68.9 % raw. Issue #2's formula `(raw - 9.5) / (97.1 - 9.5) x 100` fits the 66.6 % point. On 2026-11-14 the dash showed 86 % at 87.2 % raw, where that formula gives 88.7 %: it does not hold near full; the gap shrinks as the pack fills (2.3, 1.6, about 1.4, 1.2 points).
  - Capacity (2026-11-15 DC charge, 26.8 -> 81.0 %): 241.4 Ah per 100 % of `4801`, against 242.73 Ah rated (`DA06`). This is the BMS's own view of capacity (its SoC may be counted against the same figure), not an independent health test.
  - Pack resistance from current steps (dV/dI, same read pass): about 52 mΩ below 10 °C, 35 mΩ at 10-20 °C and 31 mΩ at 20-30 °C mean pack temperature (2026-11-15); 65-68 mΩ on the colder 2026-11-12/13 drives. Compare only at matched temperature.
  - Preconditioning before a DC stop (2026-11-15): the pack's warmest sensor rose from about 21 to 31 °C over the last 45 minutes (from 41 % SoC); 25-31 °C at plug-in, 36.5-42 °C after 28 minutes at up to 394 A (`489C` 215 kW limit). Cell-group spread (`4907`-`4908`) stayed within about 40 mV all day.
  - Dash vs `4801` across the range: 100 % shown at 96.1 %, 52 % at 51.4 %, 15 % at about 17.4 %; the dash runs above `4801` near full and below it near empty, so it is a rescaled figure, not `4801` itself.
  - `49F6` + `49F7` always add up to about 4460: an energy used/remaining pair.
  - `49EC` rose from 0 to 46-54 during a 7 kW AC charge (scale unknown).
  - `489C` charge limit here is 55-65 % below the US car's at the same SoC; `489E` within about 5 %.
  - `496D` and `496B` read a constant 10000 (100.00 % with the Polestar 2 SOH scaling); nothing shows they track anything. `4898` = 100000 and `DA06` = 242,730,000 (nominal Wh and µAh per issue #2).
  - `4805` reads close to pack voltage (421 V at /100).
- **Not found**: `F45B` is a constant `FF` here (SoC on the US car); `F4B2` (battery health), `F49A` and `F80A` are not supported.

## 1637 Inverter / e-machine

- **What it is**: rear drive inverter/motor control (IEM label; issue #2's `F80A` reads "drive motor controller 1"). 93 DIDs. Traceability string with a production date and P417.
- **Signals**: `drive_engaged` (`E307`, `02` in R or D; C), `torque_direction` (`E319`, `00` traction, `01` regen or no forward drive; C). `E319` was published as "forward gear" from parked tests; on the 2026-11-13 drive it was `00` under traction for 146 of 146 s and flipped 25 times, 22 of them with the sign of the pack current, as issue #2 said.
- **Leads**: `EEC4` rose `0x3a` -> `0x3e` over the first drive (temperature guess, one drive).
- An earlier release gave a gear decode from `D938`/`E319`/`E307`. It only holds parked: while regenerating in D it would give R. Use `1201:D938` for P and the reversing lamp `1A01:4224` for R.

## 1650 Charger / charge inlet

- **What it is**: on-board charger and inlet (CDD label; issue #2 reads a charger-controller name). 103 DIDs.
- **Signals**: `inlet_leds` (`EE32`, C: `01010100` lid open, `00010000` pulses every ~3 s while charging, off after a timeout), `ac_plug_status` (`EE24`, P; charge state only: it does not change when the cable goes in), `charge_cable_present` (`EE31`, `01` cable in, P, 2026-11-14), `charge_energy_counter` (`EE71`, lifetime AC energy in 0.1 kWh, 4.5 MWh; P), `last_charge_avg_power` (`EE72`), `last_charge_energy` (`EE74`) (P).
- **Leads**: `EE71` rose one count every ~55 s on a 7 kW AC charge (about 6.5 kW). `EE72`/`EE74` do not form a consistent pair across two reads, so their meaning is weak. `EEE1` went up by one during a charge (a counter). DC charging not yet observed. `EE12` reads 235-238 while a cable is in (`ffff` without): mains voltage or the plug's proximity resistance (220 ohm = 32 A cable), not settled (2026-11-14).

## 1656 Unknown, 12 V power path

- **What it is**: unknown. Hardware string `HX1100` (`HX11` is the Smart #1 project code, so this part is probably shared with it). 27 DIDs. `4947` and `D110` read 14.0-14.2 V with the car awake: the 12 V rail in mV (another owner reports the same pair). Also answers `EE13`, `4AF5` and `EE30`, DIDs from the battery module's ranges. Guess: DC-DC converter. Issue #2's `F80A` reads a charger-controller name for this address; not readable here.
- **Leads**: `1635` also answers `4947`, so the 12 V reading alone does not single out this module.

## 1670 Power steering

- **What it is**: PSCM label. 44 DIDs, the same set as `1676`. Answers `F804` (all zero).
- **Leads**: `3019` tracks the steering angle while driving: `1670:3019` = `0x3853` - 0.5614 x `1672:3019` (r -0.997 on 0.5 s resampled reads; about 230 changes of `1670:3019` and 480 of `1672:3019` on the 2026-11-11 drives). The opposite sign and that ratio fit 0.1 ° per count with right positive (inference), which would make `1672`'s scale 0.0561 °/count, within 1.3 % of the 0.0554 estimated by eye. `D900` = `0x707F` - `3019` on both `1670` and `1676`.

## 1672 Steering angle

- **What it is**: SAS label; a US owner's `F80A` reads "chassis controller" (issue #2). 41 DIDs. Same physical unit as the gear stalk module `1633`: same core and delivery part numbers and the same ECU serial, different software (2026-11-15, from the 2026-11-11 scans). So the steering angle sensor and the stalk probably share one column unit (inference: the SAS role rests on the label). The steering test does not single it out, since `1670` and `1676` also answer `3019`.
- **Signals**: `steering_angle` (`3019`, signed, left positive, ~0.0554 °/unit by eye, locks about ±430 °, ~2.4 turns; P). `1670:3019` suggests 0.0561 °/unit (see `1670`). Against yaw on the 2026-11-15 turns watch: r 0.77, peak at zero lag.
- **Leads**: `301A` moves while steering (meaning not established). `D112` is module supply voltage (x 0.08 V), as on `1C01`.

## 1675 Unknown chassis module (second brake unit?)

- **What it is**: unknown, between the steering units. Configuration string `GE60_P03_M10_…`. 56 DIDs. Perhaps a second brake unit (inference, weak, 2026-11-16): like `1701` it answers OBD speed `F40D`, and its `FE08` is a pair of close words like `1701:FE08` channels 1-2. Whether it is a redundant brake unit or a booster is not known; the platform's brake layout is not published.
- **Signals**: `obd_speed_1675` (`F40D`, km/h): it does move; r 0.999 with `1631:D003`, ratio 0.998 (1,178 changes, 2026-11-12 to 2026-11-15), the same as `1701:F40D` (P).
- **Leads**: `FE08` holds two signed words 5-8 counts apart: about zero (`fff5`/`fffc`) parked with the brake off (2026-11-11), `0x113`-`0x1a9` while the car stood in R or D on 2026-11-14 (four snapshots; no brake reading in them), of similar size and spacing to `1701:FE08` channels 1-2 with the pedal held in other snapshots (`0x1c1`-`0x208`, 6-8 apart). The two modules were not read at the same moment before 2026-11-19. The 2026-11-14 session notes took them for parking distances; the distances did not follow (the parking sensors are on `1015`). At times `1675` switches to a second state: `FE08` `7fff`/`7fff`, `D941`-`D944` `ffff` (else `0000`), `D952` and `DD0C` change too; it stayed there from about 15:45 that day even in R on the brake. What sets it is not known. On a 2026-11-19 drive both `FE08` words tracked `1701:FE08` channel 1 while braking (r 0.988, ratio 0.97; P), which supports the brake-unit idea.
- **Leads** (2026-11-19): `D941` is vehicle speed, 256 counts per m/s (the scale of `1631:D003`; r 0.9995 with `1601:E36E` on one drive, 0.966 on another; P). Not in the catalogue yet: in the second state it reads `ffff` (and `FE08` `7fff`), which the decoder would show as a real value; it needs a not-available marker first.

## 1676 Second steering controller

- **What it is**: probably the second channel of a dual-channel power steering: same DID set (44) as `1670`, and part numbers one step apart from `1670`'s (e.g. software part numbers ending `05`-`07` vs `08`-`10`), so related but not identical.
- **Leads**: in 11 snapshots (2026-11-11 and 2026-11-14) `3019` and `D900` read within 1 count of `1670`'s across the wheel travel seen; on both modules `D900` + `3019` = `0x707F`, a second, mirrored angle track. Not yet watched lock to lock, or while driving.

## 1701 Brake system (BSCM)

- **What it is**: the brake system; `F80A` reads `BSCM-BrakeSystem` (the only module name readable on this car). Configuration string `BRP417EA`. 132 DIDs.
- **Signals**: `brake_pressure_ch1`-`ch4` (`FE08`, four signed channels; off ~0, light 118/128/-10/-3, hard 462/469/252/259: per-wheel or per-circuit pressure? the first two channels read higher, perhaps the front axle. 2026-11-16 over all drives: while braking channels 3-4 read only 3-6 % of channel 1 and go slightly negative while moving, so they are not a plain rear-axle pressure; perhaps regen on the rear motor does the rear braking, not settled), `brake_pedal_sensor_a`/`_b` (`D905`/`D906`, two sensors in step, ~0 -> 300 -> 1030: pedal travel or master-cylinder pressure), `obd_speed_bscm` (`F40D`), `bscm_supply_v` (`F442`, 14.26 V) (all P, one parked pass).
- **Signals** (added 2026-11-13): `brake_pedal_switch` (`2B00`, `00` released, `42` pressed; C since 2026-11-19), `long_accel_bscm` (`2B11`, signed 16-bit, about 1/128 m/s² per count with an offset of about -32 parked, + = speeding up; P).
- **Leads**: `D945`, `D946`, `D948` rise with pedal force and step with `2B00` on drives. `F449` (OBD PID 49, accelerator pedal position): `00` at rest, during regen and with the brake pressed, `06`-`6A` while pulling away. `2B33` changes several times a second (a live value, not a flag). `F400` = `00080011` and `F440` = `40800001`, identical to the US car; PIDs `1C`, `30`, `31`, `49` also answer.
- **Not found**: one-pedal level (`2B33` looked like it at first; it is noise).

## 1A01 Central electronics (CEM)

- **What it is**: body control. 332 DIDs (40 before 2026-11-12).
- **Signals**: `ajar` (`42F2`: `01` tailgate, `04` left rear, `08` right rear, `10` left front, `20` right front; C), `bonnet_ajar` (`42F2` bit `80`; P), `charge_lid` (`EFF5`, C since 2026-11-14), `turn_lamps` (`421B`, C), `hazard_button` (`4300`, momentary, active low; C), `stop_lamps` (`4223`, on with the pedal and also on regen deceleration from about 0.6 m/s², with the pedal released; stays on about 2 s after the pedal is released while slowing; C), `reverse_lamp` (`4224`, C), `brake_pedal_cem` (`42F6`, `01` with the pedal pressed; unlike the stop lamps it stays off on regen; C, 2026-11-19), `beam` (`42E7`, `00` off, `40` dipped, `50` main or flash, also auto main beam; C). `power_mode`, `odometer` (P). Added 2026-11-13 (P): `driver_occupied` (`20A8`, `00` seated, `80` empty; 11 snapshots, standby and car on; the last byte of `42F9` follows it), wipers `420A`/`41E9` (toggle out of phase once per wipe). `4218` reads `00`/`20`/`40` and changed with the wiper button: a wiper switch or mode state, not a momentary button.
- **Leads**: 2026-11-14: `421C` = rear fog lamps (`0000ffff` on; C); one byte of `4222` follows the rear fog too, so `4222` carries more than the welcome lamp. `EE71` byte 1 = steering wheel heating (`02` on; C); other bytes of `EE71` set for a few seconds when the wheel is bumped. On lock, all four door modules also flip `D921` (`80`/`40`), `FE11` (`48`/`0a`) and the handles (`D90C`/`D90D`).
  - `42F2` bits `40` and `02` are set with everything shut (unknown). A door not fully latched keeps its bit and its frameless window dropped. `4443` and `45A3` gain the same door/tailgate bits.
  - `4222` `000000` -> `ffff01` on walking up with the key, off a minute later: approach/welcome lamp (once). `411D` `90` -> `00` and `4222` changes after locking: home-safe lighting (weak).
  - `281F` holds the four TPMS sensor IDs (one per wheel), so TPMS lives here; no pressure found yet. Values are per-car identifiers and are not published.
  - `410B` looks like an ambient light sensor: byte 0 `02` with a 16-bit level (about 2,800-10,000) in daylight, `01 0000` in the evening (one day).
  - `42ED`, `42EE` answer only while driving (NRC 22 parked, sometimes moving) and sit at about 4985 ± 30 all day with no rise as the tyres warm (2026-11-15, 09:00-18:00): not tyre pressure. `45B2`, `45C9` refused all day.
- **Not found here**: lock state is on the door modules (`4054`/`4056`, 2026-11-14), not the CEM; brake pedal position (`42D9`, `42FC` do not move); the wiper and washer in the 40 DIDs known before the full scan; tyre pressures in any of the 332 DIDs (searched for 2.3 bar in common encodings).

## 1A11 Climate

- **What it is**: climate control (CCM). 138 DIDs.
- **Signals**: `temp_flap_fl` (`D927`, passenger) and `temp_flap_fr` (`D929`, driver) (C since 2026-11-14: four setpoint changes each side). `980E`, earlier called the front-left flap target, did not move in eight front setpoint changes on 2026-11-14 and is no longer catalogued. Earlier note: a 2 °C setpoint drop stepped the target at once, then the flap positions crept cooler over ~15 s.
- **Leads**: `D910` stepped down with the setpoint at the same moment. `9800`/`9801` and `9802`-`9804` drift at rest. The 29 DIDs added on 2026-11-12 are mostly zero-filled; `FDE1` is a 100-byte structured block.
- **Not found**: the setpoint itself (e.g. 20.0 °C); probably held elsewhere.

## 1A12 Driver door (right front)

- **What it is**: driver door module (DDM); right front on this right-hand-drive car. 200 DIDs.
- **Signals**: `front_window` (`4047`), `front_window_stops` (`42C5`, end-stop counter), `door_handle` (`D90C`, P: one lock/unlock cycle; `ff` after locking and `03` on later days on this door, unexplained), `mirror_fold_right` (`4053`), `mirror_fold_motor_right` (`4052`), `mirror_heat_right` (`4051`) (C); `mirror_fold_current_right` (`FE0D`, P).
- **Leads**: `D938` is a rolling log of window runs, newest first, 10-byte entries: a byte, start position, end position, a byte, then the `DD00` clock big-endian in bytes 6-9 (positions ~1000 closed, ~5900 open). Decoded, the latest entries fall within six seconds of each other on 2026-11-14, inside the logged window-switch test, so each run can be dated. `D008` = window motor request (`00` stopped, `01` manual up, `02` manual down, `03` auto up, `04` auto down; `window_direction`, C since 2026-11-14). `4054` = lock (`02` unlocked, `01` locked; P). `4035` carries the driver-door window switches as bits (raw, P); the passenger-window switch on that panel does not show in it. Blind-spot lights: `1A13:4003` left and `1A12:4003` right (`00` off, `32` lit after dark, `64` in daylight; C, 2026-11-15, matched to cars alongside on each side). `1316`/`1317` (identity unknown; the manual certifies only one radar) show no target data in their known DIDs while cars pass (only clocks, counters and a history record change). `4096` changes with the window drive command, not position. `D909` moves with every door event. `480C` read 33 when the car was at about 33 km/h (speed copy, once).

## 1A13 Passenger door (left front)

- **What it is**: passenger door module (PDM). 184 DIDs. Issue #2's `F80A` gives a gateway name for this address on the US car; the door behaviour here does not fit that.
- **Signals**: `front_window`, `front_window_stops`, `door_handle` (P), `mirror_fold_left`, `mirror_fold_motor_left` (directions mirrored from the right side), `mirror_heat_left` (C).
- **Leads**: as `1A12` (`D008`, `4096`, `D909`). `400E` `07` -> `08` while the window switch is held.

## 1A15 Tailgate

- **What it is**: powered tailgate (POT). 45 DIDs.
- **Signals**: `tailgate_position` (`D906`, 0 closed, ~3198 open; P: one open/close cycle).
- **Leads**: `D907` reads about `0x0877` while moving and near 0 at rest: it moves only while the tailgate moves.

## 1A21 Left rear door

- **What it is**: rear door module (RLDM). 155 DIDs; the same set as `1A22` apart from `4240`/`4241`.
- **Signals**: `rear_window` (`4048`; C since 2026-11-14: full cycles on both rear doors, `1f00` fully open), `rear_window_stops` (`42C6`), `door_handle` (`D90C`) (P). `4056` = lock (`02` unlocked, `01` locked; P). `403B` = own-door window switch (`01` first step up, `03` second step up; C).
- **Leads**: 51 DIDs answer on both rear doors and return NRC 31 on both front doors (rear-only functions). None watched yet.

## 1A22 Right rear door

- **What it is**: rear door module (RRDM). 155 DIDs.
- **Signals**: `rear_window`, `rear_window_stops`, `door_handle` (P).

## 1A27 Driver seat

- **What it is**: driver seat module (confirmed 2026-11-14: its heating DIDs follow the driver seat switch). 81 DIDs.
- **Signals**: `seat_heat_level` (`983E`: `00`/`20`/`40`/`60` = off/1/2/3), `seat_heating_on` (`FD03`), `seat_heater_output` (`F1F4`) (P; same DIDs on `1A28`).
- **Leads**: none. `9007` (a clock), `FD02`, `FD32` change all the time in all three seat modules.

## 1A28 Passenger seat

- **What it is**: passenger seat module (SMP; confirmed by one move). 81 DIDs.
- **Signals**: `pass_seat_slide` (`40A3`, rises moving forward), `pass_seat_switches` (`40A8` bit `40` = forward switch) (P, one move).
- **Leads**: `FD00`-`FD04` and `FD32` dip during motor runs. `41F4` stepped `82` -> `83` once, unexplained (weak occupancy guess).

## 1A29 Rear seat

- **What it is**: rear seat module (confirmed 2026-11-14: rear seat heating and recline). 66 DIDs.
- **Signals**: `rear_seat_heat_levels` (`983E`: bits 5-6 left level, bits 2-3 right level), `seat_heating_on` (`FD03`), `rear_recline_left`/`rear_recline_right` (`40A3` bytes 2-3 and 8-9: `0x0013` upright, about `0x0213` fully back) (P).
- **Leads**: `41F4` flipped by one count three times, unexplained.

## 1A30 Interior lighting

- **What it is**: label guess (ILCM); not checked. 30 DIDs.

## 1BB3 Left headlamp

- **What it is**: left matrix headlamp module (HCML). 63 DIDs.
- **Signals**: `headlamp_status` (`4368` byte 0, a bitfield: `01` lamp active, `04` indicating, `10` dipped, `40` main or flash), `main_beam_ch3_duty`, `main_beam_ch4_duty` (`435C`/`435D`), `indicator_ch11_duty`, `indicator_ch12_duty` (`4364`/`4367`) (C). Flash and main beam look the same.
- **Leads**:
  - `7022`: 32 bytes of matrix main-beam segment brightness (2 rows of 16?): dipped beam lights only the nearside (low-numbered) end of the bottom row and main beam both rows, peaking toward the car centre (confirmed parked 2026-11-14, C), `0x0f`-`0x50` per segment on main beam, with runs of `00` where a car ahead or oncoming was shaded (P, one drive). 2026-11-15 (10-minute watch, owner calling cars): main beam stayed on 90 % of the time through streams of oncoming traffic, with one shaded block per lamp that moved with the traffic; the full dips were at roundabouts. Polestar quotes 32 pixel LEDs per lamp, matching the 32 bytes. No published limit on how many vehicles it shades. Segment order (2026-11-14): left to right on both lamps, no flips; main beam peaks at segments 9-10 on the left lamp and 7-8 on the right (numbered from 1), toward the car centre.
  - `4368` = `11000000` for ~90 s after locking (home-safe), `00000020` on approach with the key.
  - Channels 6-9 (`435F`-`4362`) sit at 15 % and drop to 0 on the indicating side (DRL/position dimming, guess).
  - `43D7` on this side toggles `0800`/`0000` every few seconds at rest; the right lamp stays `0000` (meaning unknown).
  - `43CE`-`43D2` moved with the lamps on a drive.

## 1BB4 Right headlamp

- **What it is**: right matrix headlamp module (HCMR). 63 DIDs.
- **Signals**: as `1BB3` (C); the indicator channels mirror the left side.
- **Leads**: as `1BB3` (`7022`, `4368` home-safe/approach).

## 1C01 Airbags

- **What it is**: label guess (SRS). 57 DIDs. Issue #2's `F80A` gives a gateway name for this address on the US car; nothing here settles it.
- **Signals**: `srs_supply_v` (`D112`, x 0.08 V; tracks `1701:F442` at r 0.98-1.00 when the 12 V rail swings; P). **Correction**: 2026.11.12.2 published `D112` bit `02` as the driver belt. It is not: the low bits move with supply voltage several times a second with nothing touched.
- **Not found**: belt buckle or seat occupancy, watched on 2026-11-13 with the car in standby and on (only `D910`, a counter, changed).

## Open questions

- **Tyre pressure**: no DID found among those searched. The TPMS sensor IDs are on the CEM (`1A01:281F`); `2800`-`28FF` holds nothing else, and none of the 332 CEM values matches. `1A01` `42ED`/`42EE` answer while driving but stay flat at about 4985 all day (not pressure); `45B2`/`45C9` refuse even while driving (2026-11-15). Earlier: the app showed 2.3 bar on all four; the 2,856 DIDs read by 2026-11-11 and the first 269 of the 273 new CEM DIDs were searched for that value in common encodings (bar x10, x100, kPa gauge and absolute, kPa/2.5, kPa/4, psi, psi x10, mbar; four values in one DID or four nearby DIDs): no real match. `1601:D282` and `D911`-`D913` ruled out. The full-range scans of `1A01`, `1601`, `1011` and `1015` found nothing either. A deflate test (let 0.3 bar out of one tyre, diff) is planned but not done.
- **Wheel speeds**: found and placed (`1601:E3E4`-`E3E7`: left front, right front, left rear, right rear; C, 2026-11-15).
- **Yaw rate / lateral acceleration**: yaw rate found (`1614:D92D` byte 2, P, one drive). Lateral acceleration not found (`D92D` byte 1 did not follow anything). Longitudinal acceleration is `2B11` on `1601` and `1701` (P). `1601:EF06`, `EFA5`, `EFA6` are not rates; `EFA7`-`EFAA` untested.
- **Wipers / rain sensor**: wipers found on the CEM (`420A`/`41E9`, `4218`). Rain sensor not found: one natural-rain snapshot was confounded (standby, seat occupancy changed); candidates `40E2`, `4104` unproven, and `402A` copies the module temperature.
- **Seat occupancy and belts**: driver occupancy found (`1A01:20A8`, P). No passenger occupancy and no belt buckle found, with the car in standby or on. Rear occupancy and the rear left buckle were not found either (2026-11-14). The car does know: the dash shows which seats are unbuckled. The airbag module `1C01` is the likely home, but only its default ranges (about 8,700 of 65,536 DIDs) have been read; a full scan of it has not been done. The driver belt published earlier (`1C01:D112`) was wrong (see `1C01`).
- **Surround-view objects**: the cluster draws cars around the car, so the data exists somewhere (radar or sensor fusion). Watching `1316`, `1317` and `1344` alongside marks has not shown anything yet; `1301` is kept out of driving watches.
- **Charge port cover**: the lid state (`1A01:EFF5`) and inlet LEDs (`1650:EE32`) are known; both seen at least twice (C, 2026-11-14), from the screen and the door button. Cable insertion shows in `1650:EE31` (`01` cable in; P), not in `EE24`.
- **Also not found**: one-pedal level, Steering Feel and Hill Descent (the test in D was cut short); the climate setpoint (front and rear); the displayed range. Drive mode (`1601:E450`) and door locks (`4054`/`4056`) were found on 2026-11-14.
