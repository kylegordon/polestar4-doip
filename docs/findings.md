# Findings so far: Polestar 4 Coupe (UK)

What has been learned about one car, module by module, including leads that are not yet confirmed. Shared so other owners can check them on their own cars.

- **Car**: Polestar 4 Coupe (no rear window; camera rear-view mirror), UK, right-hand drive, customer software release 4.2.11 (EMEA).
- **Method**: read-only UDS `0x22` ReadDataByIdentifier over DoIP in the default session, through the OBD port, with the `./p4` tool. No session change, no security access, no writes. Meanings come from watching values change while doing something to the car (opening a door, pressing the brake, driving), not from names on other cars.
- **Confidence**: as in [`catalogue/signals.yaml`](../catalogue/signals.yaml). **C** = the same change seen at least twice in both directions; **P** = anything less. Signals are referred to by their catalogue `id`.
- **Lead** = an observation that is not in the catalogue: something moved once, or moved at a plausible time, or fits a plausible encoding. Each lead says how strong it is.
- Every answering DID, per module, is in [`docs/did-map.csv`](did-map.csv); module evidence in [`docs/modules.md`](modules.md); the dated history in [`DISCOVERIES.md`](../DISCOVERIES.md). Counts below are answering DIDs as of 2026-11-13: the default scan ranges on every module, and the full `0000`-`FFFF` range on `1A01`, `1015`, `1011`, `1201`, `1601`, `1701`, `1316`, `1317`, `1344` and `1650`.
- Most modules have never been watched while something happens to them. "Nothing seen" usually means "not looked at in the right moment", not "absent".

**Common to every module**: `DD01` odometer in km (`odometer`, P), `DD0A` power mode (`power_mode`, P: `01` parked, `02` awake, `0d` on, which includes sitting in P, so it does not mean driving), `DD00` a free-running clock. `D904` on several modules moves `0x96`/`0x97` with load: probably supply voltage in 0.1 V (lead, weak).

**OBD-on-UDS info blocks** (`F400`-`F4FF`, `F800`-`F8FF`, VIN skipped) were read on 42 modules. Unlike a US car (issue #2), almost nothing answers here: only `1701`, `1675`, `1601` (`F800` only) and `1670`/`1676` (`F804`, all zero). So `F80A` module names are not available for most modules on this car.

## 1001 Gateway

- **What it is**: the DoIP entity (logical address `1001`); tester `0E80`, functional address `1FFF`. 88 DIDs. Gateway firmware build string dated December 2025.
- **Leads**: `D0D0` holds the customer software release "4.2.11", stored as ASCII hex digits written in ASCII (P; the decoder has no encoding for it, so it is not in the catalogue). The same release appears as text in a telematics update record (`1011`).
- **Not found**: no range or distance-to-empty value; values that happened to match the displayed range were configuration or hash bytes.

## 1011 Telematics

- **What it is**: the car's mobile connection (TEM label, unverified). 119 DIDs. Holds SIM and modem identifiers, two assistance phone numbers, a current date-time, a release string (`P417_4.2.11_…`) and server names. Identifiers are masked by `./p4 strings` and not published.
- **Leads**: `FD50` (10 bytes) holds the car's position: two signed 32-bit big-endian values in milliarcseconds (degrees x 3,600,000), longitude then latitude. One parked read matched where the car stood within about 100 m (P; values never published). A configured GB/T 32960 (Chinese national EV remote-monitoring standard) server entry, on a UK car. Whether it ever sends anything is not known. The phone app shows tyre pressures; none found here after a full-range scan.

## 1012 Driver monitoring

- **What it is**: label guess (DMM) from related cars; not checked. 53 DIDs.

## 1015 Wireless access / digital key

- **What it is**: keyless entry and phone-as-key. 162 DIDs. Software names include `PAS_VE` (passive entry?) and `…CCA…`/`…CCR…` strings, perhaps Car Connectivity Consortium digital-key components (guess). Polestar documents UWB, BLE and NFC key-card for this car.

## 1023 Wireless phone charger

- **What it is**: part `6608017285` is sold as "control unit for wireless charging". 142 DIDs, a lot for a phone charger, so it may be a combined unit.
- **Leads**: none yet; a phone on/off the pad has not been watched.

## 1201 Infotainment

- **What it is**: IHU. 133 DIDs.
- **Signals**: `park_selected` (`D938`: `00` P, `01` not P, `02` changing; C). `01` is "not in P" even when stopped in D, R or N.
- **Not found**: the displayed SoC and range (no value matching 59 % or 161 mi when shown); three distance-to-empty-like DIDs read `00`. `D931` reads `02` at each new connection then `00` (connection artefact).

## 1202 Camera / vision

- **What it is**: label guess; not checked. 21 DIDs.

## 1212 Audio amplifier

- **What it is**: label guess; not checked. 21 DIDs.

## 1213 Rear-seat entertainment

- **What it is**: label guess; not checked. 29 DIDs.

## 1251 Head-up display

- **What it is**: label guess. 22 DIDs. Answers physical addressing only, not the `1FFF` broadcast.

## 1301 Mobileye SuperVision ECU

- **What it is**: driver-assistance computer. Firmware string names `P417_EU` (P417 = Polestar 4 model code) and `GAS52`, built January 2026. `D921`-`D927` hold seven camera entries, but only four distinct type codes (`CAM000022`-`25`), so they are variant codes rather than per-camera IDs. 111 DIDs; the scan stops before `EE13` on purpose.
- **Hazards**: **never read `EE13` on `1301`.** Twice (once parked and unattended) it knocked this ECU off the network (gateway NACK), the second time for about a minute, with no dash warning. A `1FFF` broadcast or a range sweep through `EE13` reaches it too. The tool refuses the read. `1635:EE13` is a different module and is safe. `1301` is kept out of watches while driving.

## 1314 Dash camera

- **What it is**: label guess (DVR); not checked. 51 DIDs.

## 1316 Unknown (left of a pair)

- **What it is**: unknown. Same hardware and software part numbers as `1317`, serials 7 apart (a few other part-number DIDs differ), same 36 DIDs. Sits next to the front radar in the driver-assistance address range. Guesses: corner radars or side obstacle detection.
- **Leads**: very few live values (fewer than `1317`). `2000`-`2D2B` is empty. `D112` is module supply voltage (x 0.08 V), as on `1C01`.

## 1317 Unknown (right of a pair)

- **What it is**: pair of `1316` (see above). 36 DIDs.
- **Leads**: `D237` is an event list with timestamps; it changed at 16:01-16:02 on the 2026-11-12 drive, cause not known (weak). `D005` and `E103` also change. `D112` is module supply voltage. A move-closer-to-a-wall test on 2026-11-13 showed no distance values on either side.

## 1344 Front radar

- **What it is**: label guess (FLR); not checked. 45 DIDs.
- **Leads**: being watched with `1316`/`1317` while the cluster draws surrounding cars; nothing correlated yet. `D923` byte 0 rises one step every 30-60 s after the car wakes and falls after use: behaves like a temperature, not traffic. `D112` is module supply voltage (x 0.08 V), as on `1C01`.

## 1601 Vehicle dynamics / parking brake

- **What it is**: brake and stability controller with the electric parking brake (VDDM label; our label rests on the parking-brake behaviour). 702 DIDs, the largest map on the car. A US owner's `F80A` reads a hybrid-powertrain-controller name for `1601` (issue #2); here `1601` answers `F800` only, so the name cannot be read.
- **Signals**: `epb_state` (`E37B`), `epb_position` (`2B1A`), `epb_lamp` (`2B15`), `epb_operations` (`2B20`, counts on each release) (all C; also the automatic release/apply on shifting out of and into P, five cycles). `vddm_speed` (`E36E`, km/h x 1/256, C: median ratio to `1631:D003` 0.994-1.002 over 943 paired reads on five drives). `wheel_speed_1`-`_4` (`E3E4`-`E3E7`, same scale as `D003`; all four within about 1 km/h of each other and 0 at rest; corner order unknown, `E3E4`/`E3E6` move together against `E3E5`/`E3E7` in turns; P). `motor_speed_front`/`_rear` (`E3E8`/`E3E9`, raw `0x4E20` at rest (decoded as 0), about 83 counts per km/h; `E3E8` drops to `0x4E20` when cruising and matches `E3E9` when pulling away, which fits the front motor disconnect in Range power delivery; P). `long_accel_vddm` (`2B11`, signed, about 1/128 m/s² per count, + = slowing; parked it reads an offset that changes with the slope: P). `brake_pressure_vddm` (`E3C7`, `0x4000` with the brake released; = 7.2 x `1701:FE08` ch1 + 40, r 0.998 on one drive; P).
- **Leads**:
  - The parked pedal pass (off / light / hard, 2026-11-12) is confounded with time: it ran in one order over about 2 minutes. `E4AF` "rising" was a free-running 10 Hz counter, and `E391`/`E392` (published as falling with pedal force) also drift by themselves near wake-up and ramp while driving, so they are withdrawn. `E39D`, `E362`, `D925`, `EE2B`/`EE2C`, `D922`/`D939`, `E340`, `E455`/`E457` are unproven for the same reason.
  - `E46A` (`0x4000` = none) rises on lift-off regen with the pedal released as well as under the pedal: a total deceleration demand? The stop lamps were on whenever it was at or above about `0x4380` on one drive (P).
  - `E406` reads speed in whole km/h; `E467`/`E468` are a pair at `0x7F80` at rest moving with speed (about 128 counts per km/h; axle speeds?). `E3CF`/`E3D1`-`E3D3` (also in `E496`-`E49D`) form mirrored pairs under the pedal: per-wheel brake torque? (one pass).
  - `D9AC` (toggles `5280`/`51e0`), `D921`/`D935` (step together), `D989` (four monotonic steps) and `D901` (ramp then reset) changed while driving: wheel-speed or yaw candidates (weak; ~12-20 s sampling).
  - A byte at `E3A7` changes at each automatic parking-brake apply and `E3A6` at each release (seen over several cycles; meaning unknown).
  - `D905`/`D907`/`D914`/`D91A` changed together 45 s after the cluster showed two cars to the left (timing only).
  - The long `EExx`/`EFxx` blocks change on almost every read while parked: rolling logs or history buffers (guess).
- **Not found**: tyre pressures (`D282` holds several unequal words, about 455-560, when the app showed 2.3 bar on all four: ruled out; `D911`-`D913`: three values in steps of 5 around 2,600 that sometimes shift along and sometimes flicker: ruled out). The Polestar 2 wheel-speed DIDs `2B06`-`2B09` and other `2Bxx`/`20xx` dynamics DIDs return NRC 31 (not supported). `2B34` flips on its own when parked. Gear does not show here.
- **Hazards**: possible, not repeated: one silence of about 10 s while reading `D928`-`D92C` (earlier releases said `D927`-`D92B`; `D927` answered normally), 3 s after the car had woken. Silences mid-scan have also happened on other modules with no special DID, so start-up is a likely cause. Scans skip `D927`-`D92B` until they are tested one at a time; `D92C` has since been read without trouble.

## 1614 Suspension

- **What it is**: suspension/chassis control (SUM label). 52 DIDs.
- **Signals**: `chassis_mode` (`D90F`: `00` Standard, `40` Firm, `30` Nimble; C). `damper_cmd_c1`-`c4` (`D93A`, four per-corner bytes in equal pairs, ~`0x28` in Standard, `0x30`-`0x57` in one Firm interval, spikes on road inputs, Standard also spiking to `0x55`; P, corner order unknown). `corner_motion_c1`-`c4` (`D902`, four signed per-corner values, move constantly while driving, weak negative link to deceleration; ride height or body motion; P). Lead: `D92D` byte 0 reads speed in m/s.
- **Leads**: `D901` behaves like `D93A`; `D903` moves constantly like `D902`.
- **Not found**: drive mode (Range/Performance) and one-pedal level: no DID changes with them, parked.

## 1615 Steering column lock

- **What it is**: label guess (SCL); not checked. 25 DIDs. No wiper or washer DIDs answer here.

## 1631 Front drive motor controller (probable)

- **What it is**: probably the front drive motor controller, as issue #2's `F80A` name says: `E307` goes `01` -> `02` only in short bursts when pulling away or accelerating (about 1.5-2.2 m/s²), `E303` then reads `0x4000` + front motor speed (same ~83 counts per km/h as `1601:E3E8`), and `E319` reads `00` in those bursts like `1637:E319`. Labelled brake control (BCM) before; brake pedal and parking-brake DIDs return NRC 31 and no steering DIDs answer. A US owner's `F80A` reads "drive motor controller 2" (issue #2); not readable here. 103 DIDs. Traceability string with a production date and the model code P417. Shares 29 DIDs with `1701`.
- **Signals**: `vehicle_speed` (`D003`, km/h x 0.0140625; C). The dash reads about 5 % above it.
- **Leads**: `E312` is the same speed with a `0x4000` offset (r 0.98 over two drives; P, not catalogued). `E335`-`E338` are four near-equal values (~`0x332c` parked), per-wheel guess; weak correlation with braking.

## 1633 Gear selector stalk

- **What it is**: the column gear stalk (EGSM label). 51 DIDs. Reports stalk movement only, not the selected gear.
- **Leads**: `D914`, `D915`, `D919`, `D920` go `01` -> `04` while the stalk is pushed (back within ~2 s); `DA02`/`DA03` go `01` -> `03` while held down (the N gesture); `DA00`/`DA01` jitter by a count or two (raw positions?). P, one test.
- **Not found**: the wiper button on the stalk (single wipe, washer) moved nothing here.

## 1635 HV battery (BECM)

- **What it is**: the battery management module. 209 DIDs.
- **Signals**: `hv_soc` (`4801`, C), `cell_soc_avg`/`max`/`min` (`DA19`/`DA17`/`DA18`, C), `charge_counter` (`EE14`, C; counts plug charging, not regen), `discharge_counter` (`EE13`, C; mAh per issue #2 and our parked current), `charging_flag` (`49EF`), `charge_request_flag` (`49E5`), `charge_power_limit` (`49DD`, unit unknown), `pack_current` (`4802`, 0.1 A, `0x4000` = 0, + = discharge; regen to about -95 A seen), `pack_voltage` (`497C`), `cell_v_mean` (`DA1D`), `cell_max_index`/`cell_max_v` and `cell_min_index`/`cell_min_v` (`4907`/`4908`), `low_volt_rail_bms` (`EE02`), `low_volt_rail` (`4947`), `charge_power_limit_kw`/`discharge_power_limit_kw` (`489C`/`489E`), `outside_temp_becm` (`EE07`, 0.01 °C with a -50 offset) (all P).
- **Leads**:
  - `DA31`: 130 x u16 cell-group voltages in mV, 110 valid (`EE19` = 110); their sum matches `497C` within 0.05 V in nine snapshots. `EE83`: 30 pack temperatures, 28 valid (`EE20` = 28), 0.01 °C with -50 (gives 6.5-7 °C on a November night). `EE06` ambient, same encoding. Agree with issue #2; not catalogued (arrays, or not yet seen to change).
  - Displayed SoC sits below `4801`: 59 % shown at 61.3 % raw; 65 % at 66.6 %; the dash ticked 68 -> 67 % at 68.9 % raw. Issue #2's formula `(raw - 9.5) / (97.1 - 9.5) x 100` fits the 66.6 % point.
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
- **Signals**: `inlet_leds` (`EE32`, C: `01010100` lid open, `00010000` pulses every ~3 s while charging, off after a timeout), `ac_plug_status` (`EE24`, P), `charge_energy_counter` (`EE71`, lifetime AC energy in 0.1 kWh, 4.5 MWh; P), `last_charge_avg_power` (`EE72`), `last_charge_energy` (`EE74`) (P).
- **Leads**: `EE71` rose one count every ~55 s on a 7 kW AC charge (about 6.5 kW). `EE72`/`EE74` do not form a consistent pair across two reads, so their meaning is weak. `EEE1` went up by one during a charge (a counter). DC charging not yet observed.

## 1656 Unknown, 12 V power path

- **What it is**: unknown. Hardware string `HX1100`. 27 DIDs. `4947` and `D110` read 14.0-14.2 V with the car awake: the 12 V rail in mV (another owner reports the same pair). Also answers `EE13`, `4AF5` and `EE30`, DIDs from the battery module's ranges. Guess: DC-DC converter. Issue #2's `F80A` reads a charger-controller name for this address; not readable here.
- **Leads**: `1635` also answers `4947`, so the 12 V reading alone does not single out this module.

## 1670 Power steering

- **What it is**: PSCM label. 44 DIDs, the same set as `1676`. Answers `F804` (all zero).
- **Leads**: `3019` tracks the steering angle while driving (encoding differs slightly from `1672`).

## 1672 Steering angle

- **What it is**: SAS label; a US owner's `F80A` reads "chassis controller" (issue #2). 41 DIDs. The steering test does not single it out, since `1670` and `1676` also answer `3019`.
- **Signals**: `steering_angle` (`3019`, signed, left positive, ~0.0554 °/unit by eye, locks about ±430 °, ~2.4 turns; P).
- **Leads**: `301A` moves while steering (meaning not established). `D112` is module supply voltage (x 0.08 V), as on `1C01`.

## 1675 Unknown chassis module

- **What it is**: unknown, between the steering units. Configuration string `GE60_P03_M10_…`. 56 DIDs.
- **Leads**: answers `F40D` (OBD PID 0D vehicle speed), `00` parked; not yet seen moving.

## 1676 Second steering controller

- **What it is**: probably the redundant half of the power steering: same software part numbers and placeholder serial as `1670`, same DID set. 44 DIDs.
- **Leads**: its `3019` read the same value as `1670:3019` minutes apart. Not yet watched lock to lock alongside `1670`.

## 1701 Brake system (BSCM)

- **What it is**: the brake system; `F80A` reads `BSCM-BrakeSystem` (the only module name readable on this car). Configuration string `BRP417EA`. 132 DIDs.
- **Signals**: `brake_pressure_ch1`-`ch4` (`FE08`, four signed channels; off ~0, light 118/128/-10/-3, hard 462/469/252/259: per-wheel or per-circuit pressure? the first two channels read higher, perhaps the front axle), `brake_pedal_sensor_a`/`_b` (`D905`/`D906`, two sensors in step, ~0 -> 300 -> 1030: pedal travel or master-cylinder pressure), `obd_speed_bscm` (`F40D`), `bscm_supply_v` (`F442`, 14.26 V) (all P, one parked pass).
- **Signals** (added 2026-11-13): `brake_pedal_switch` (`2B00`, `00` released, `42` pressed; P), `long_accel_bscm` (`2B11`, signed 16-bit, about 1/128 m/s² per count with an offset of about -32 parked; P).
- **Leads**: `D945`, `D946`, `D948` rise with pedal force and step with `2B00` on drives. `F449` (OBD PID 49, accelerator pedal position): `00` at rest, during regen and with the brake pressed, `06`-`6A` while pulling away. `2B33` changes several times a second (a live value, not a flag). `F400` = `00080011` and `F440` = `40800001`, identical to the US car; PIDs `1C`, `30`, `31`, `49` also answer.
- **Not found**: one-pedal level (`2B33` looked like it at first; it is noise).

## 1A01 Central electronics (CEM)

- **What it is**: body control. 332 DIDs (40 before 2026-11-12).
- **Signals**: `ajar` (`42F2`: `01` tailgate, `04` left rear, `08` right rear, `10` left front, `20` right front; C), `bonnet_ajar` (`42F2` bit `80`; P), `charge_lid` (`EFF5`, P: closing seen once), `turn_lamps` (`421B`, C), `hazard_button` (`4300`, momentary, active low; C), `stop_lamps` (`4223`, on with the pedal and also on regen deceleration from about 0.6 m/s², with the pedal released; C), `reverse_lamp` (`4224`, C), `beam` (`42E7`, `00` off, `40` dipped, `50` main or flash, also auto main beam; C). `power_mode`, `odometer` (P). Added 2026-11-13 (P): `driver_occupied` (`20A8`, `00` seated, `80` empty; 11 snapshots, standby and car on; the last byte of `42F9` follows it), wipers `420A`/`41E9` (toggle out of phase once per wipe). `4218` reads `00`/`20`/`40` and changed with the wiper button: a wiper switch or mode state, not a momentary button.
- **Leads**:
  - `42F2` bits `40` and `02` are set with everything shut (unknown). A door not fully latched keeps its bit and its frameless window dropped. `4443` and `45A3` gain the same door/tailgate bits.
  - `4222` `000000` -> `ffff01` on walking up with the key, off a minute later: approach/welcome lamp (once). `411D` `90` -> `00` and `4222` changes after locking: home-safe lighting (weak).
  - `281F` holds the four TPMS sensor IDs (one per wheel), so TPMS lives here; no pressure found yet. Values are per-car identifiers and are not published.
  - `410B` looks like an ambient light sensor: byte 0 `02` with a 16-bit level (about 2,800-10,000) in daylight, `01 0000` in the evening (one day).
  - `42ED`, `42EE`, `45B2`, `45C9` refuse with NRC 22 (conditions not correct): worth a read in another car state.
- **Not found**: lock state (no change in 243 door/boot/window DIDs on lock/unlock); brake pedal position (`42D9`, `42FC` do not move); the wiper and washer in the 40 DIDs known before the full scan; tyre pressures in any of the 332 DIDs (searched for 2.3 bar in common encodings).

## 1A11 Climate

- **What it is**: climate control (CCM). 138 DIDs.
- **Signals**: `temp_flap_fl_target` (`980E`), `temp_flap_fl` (`D927`), `temp_flap_fr` (`D929`) (P): a 2 °C setpoint drop stepped the target at once, then the flap positions crept cooler over ~15 s.
- **Leads**: `D910` stepped down with the setpoint at the same moment. `9800`/`9801` and `9802`-`9804` drift at rest. The 29 DIDs added on 2026-11-12 are mostly zero-filled; `FDE1` is a 100-byte structured block.
- **Not found**: the setpoint itself (e.g. 20.0 °C); probably held elsewhere.

## 1A12 Driver door (right front)

- **What it is**: driver door module (DDM); right front on this right-hand-drive car. 200 DIDs.
- **Signals**: `front_window` (`4047`), `front_window_stops` (`42C5`, end-stop counter), `door_handle` (`D90C`, P: one lock/unlock cycle; `ff` after locking and `03` on later days on this door, unexplained), `mirror_fold_right` (`4053`), `mirror_fold_motor_right` (`4052`), `mirror_heat_right` (`4051`) (C); `mirror_fold_current_right` (`FE0D`, P).
- **Leads**: `D938` is a rolling log of window runs, newest first, 10-byte entries: start position, end position, a byte, timestamp (positions ~1000 closed, ~5900 open). `D008` = window direction (`04` down, `03` up). `4096` changes with the window drive command, not position. `D909` moves with every door event. `480C` read 33 when the car was at about 33 km/h (speed copy, once).

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
- **Signals**: `rear_window` (`4048`), `rear_window_stops` (`42C6`), `door_handle` (`D90C`) (P: one cycle per door; "fully open" never read on a rear door).
- **Leads**: 51 DIDs answer on both rear doors and return NRC 31 on both front doors (rear-only functions). None watched yet.

## 1A22 Right rear door

- **What it is**: rear door module (RRDM). 155 DIDs.
- **Signals**: `rear_window`, `rear_window_stops`, `door_handle` (P).

## 1A27 Driver seat

- **What it is**: seat module; driver side by elimination (label unverified). 81 DIDs.
- **Leads**: none. `9007` (a clock), `FD02`, `FD32` change all the time in all three seat modules.

## 1A28 Passenger seat

- **What it is**: passenger seat module (SMP; confirmed by one move). 81 DIDs.
- **Signals**: `pass_seat_slide` (`40A3`, rises moving forward), `pass_seat_switches` (`40A8` bit `40` = forward switch) (P, one move).
- **Leads**: `FD00`-`FD04` and `FD32` dip during motor runs. `41F4` stepped `82` -> `83` once, unexplained (weak occupancy guess).

## 1A29 Rear seat

- **What it is**: rear seat module (label unverified). 66 DIDs.
- **Leads**: `41F4` flipped by one count three times, unexplained.

## 1A30 Interior lighting

- **What it is**: label guess (ILCM); not checked. 30 DIDs.

## 1BB3 Left headlamp

- **What it is**: left matrix headlamp module (HCML). 63 DIDs.
- **Signals**: `headlamp_status` (`4368` byte 0, a bitfield: `01` lamp active, `04` indicating, `10` dipped, `40` main or flash), `main_beam_ch3_duty`, `main_beam_ch4_duty` (`435C`/`435D`), `indicator_ch11_duty`, `indicator_ch12_duty` (`4364`/`4367`) (C). Flash and main beam look the same.
- **Leads**:
  - `7022`: 32 bytes of matrix main-beam segment brightness (2 rows of 16?): all `00` dipped, `0x0f`-`0x50` per segment on main beam, with runs of `00` where a car ahead or oncoming was shaded (P, one drive).
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

- **Tyre pressure**: no DID found among those searched. The TPMS sensor IDs are on the CEM (`1A01:281F`); `2800`-`28FF` holds nothing else, and none of the 332 CEM values matches. `1A01` `42ED`/`42EE`/`45B2`/`45C9` refuse with NRC 22 when parked and are now watched while driving. Earlier: the app showed 2.3 bar on all four; the 2,856 DIDs read by 2026-11-11 and the first 269 of the 273 new CEM DIDs were searched for that value in common encodings (bar x10, x100, kPa gauge and absolute, kPa/2.5, kPa/4, psi, psi x10, mbar; four values in one DID or four nearby DIDs): no real match. `1601:D282` and `D911`-`D913` ruled out. The full-range scans of `1A01`, `1601`, `1011` and `1015` found nothing either. A deflate test (let 0.3 bar out of one tyre, diff) is planned but not done.
- **Wheel speeds**: found (`1601:E3E4`-`E3E7`, P). Corner order still unknown: next is a fast watch through tight low-speed turns with steering angle.
- **Yaw rate / lateral acceleration**: not found. Longitudinal acceleration is `2B11` on `1601` and `1701` (P). Weak leads: `1601:EF06`, `EFA5`-`EFAA`, `1614:D92D` bytes 1-2.
- **Wipers / rain sensor**: wipers found on the CEM (`420A`/`41E9`, `4218`). Rain sensor not found: one natural-rain snapshot was confounded (standby, seat occupancy changed); candidates `40E2`, `4104` unproven, and `402A` copies the module temperature.
- **Seat occupancy and belts**: driver occupancy found (`1A01:20A8`, P). No passenger occupancy and no belt buckle found, with the car in standby or on. The driver belt published earlier (`1C01:D112`) was wrong (see `1C01`).
- **Surround-view objects**: the cluster draws cars around the car, so the data exists somewhere (radar or sensor fusion). Watching `1316`, `1317` and `1344` alongside marks has not shown anything yet; `1301` is kept out of driving watches.
- **Charge port cover**: the lid state (`1A01:EFF5`) and inlet LEDs (`1650:EE32`) are known; opening has been seen three times, closing once. A parked test of the motorised cover opening and closing from the screen, diffing `1650` and `1A01`, is planned to find the cover motor or position.
- **Also not found**: drive mode (Range/Performance) and one-pedal level, parked (Range should show as the front motor `1601:E3E8` dropping out when cruising; a drive in each mode is needed); door lock state; the climate setpoint; the displayed range.
