# Module map

All 43 modules that answer on this car, with the answering DIDs listed in `did-map.csv` across them (default-session `22` reads only). "Guess" means a label used on related Volvo/Geely cars, not checked on this car.

| Address | Module | Basis |
|---|---|---|
| `1001` | Gateway (DoIP entity) | addressing |
| `1011` | Telematics | SIM and modem IDs, assistance phone numbers in DIDs |
| `1012` | Driver monitoring | guess |
| `1015` | Wireless access / digital key (UWB, BLE, NFC)? | software names (`PAS_VE`, `…CCA…`, `…CCR…`) |
| `1023` | Wireless phone charger | part `6608017285` is sold as "control unit for wireless charging" (the usual label for this address is BNCM, which looks wrong here) |
| `1201` | Infotainment | park signal `D938` |
| `1202` | Camera / vision | guess |
| `1212` | Audio amplifier | guess |
| `1213` | Rear-seat entertainment | guess |
| `1251` | Head-up display | guess; answers physical addressing only, not `1FFF` |
| `1301` | Mobileye SuperVision ECU | firmware string names `P417_EU` and `GAS52`; 7 camera entries (`D921`–`D927`) with 4 type codes |
| `1314` | Dash camera | guess |
| `1316` / `1317` | Unknown left/right pair | same hardware part, serials 7 apart, same DID set, very few live values; corner sensors? |
| `1344` | Front radar | guess |
| `1601` | Vehicle dynamics / parking brake | EPB signals |
| `1614` | Suspension | chassis mode `D90F` |
| `1615` | Steering column lock | guess |
| `1631` | Front drive motor controller (probable) | speed `D003`; `E307`/`E303` active only when the front motor drives (pull-aways); a US owner reads F80A `DMC2` (drive motor controller 2) |
| `1633` | Gear stalk | stalk movement only |
| `1635` | HV battery | SOC, pack V/I, cells |
| `1637` | Rear inverter / e-machine | drive engaged `E307`, torque direction `E319`; `EEC4` rose 0x3A → 0x3E on a drive (temperature?) |
| `1650` | Charger / inlet | charge signals |
| `1656` | Unknown, HV/12 V power path | `4947`/`D110` read 14.0–14.2 V (12 V rail, as on `1635`); hardware `HX1100`; DC-DC converter? |
| `1670` | Power steering | steering angle `3019` |
| `1672` | Steering angle sensor? | `3019` (also answers on `1670`/`1676`); a US owner reads F80A `CHCM` (chassis controller): unverified here |
| `1675` | Unknown chassis module | config string `GE60_P03_M10_…`; answers OBD speed `F40D` (2026-11-12) |
| `1676` | Second (redundant) steering controller? | same 44 DIDs and software part numbers as `1670` |
| `1701` | Brake system (BSCM) | `F80A` reads `BSCM-BrakeSystem` (2026-11-12); config `BRP417EA`; shares 29 DIDs with `1631`; brake pressure/pedal candidates `FE08`, `D905`/`D906` |
| `1A01` | Body / central electronics | lamps, doors |
| `1A11` | Climate | flap positions |
| `1A12` / `1A13` | Driver / passenger door | windows, handles |
| `1A15` | Tailgate | position |
| `1A21` / `1A22` | Rear doors | windows |
| `1A27` / `1A28` / `1A29` | Seats: driver / passenger / rear | seat position |
| `1A30` | Interior lighting | guess |
| `1BB3` / `1BB4` | Headlamps L/R | matrix segments |
| `1C01` | Airbags | guess |

Other notes:
- `D904` on several modules moves 0x96/0x97 with load: probably supply voltage in 0.1 V steps.
- `1635` `49F6` + `49F7` always add up to the same total (~4460): an energy used/remaining pair.
- On this UK car the telematics unit holds a configured GB/T 32960 (Chinese EV remote-monitoring standard) server address pointing at a test host. Whether it ever sends anything isn't known.
