# Module map

All 45 modules that answer on this car, with the answering DIDs listed in `did-map.csv` across them (default-session `22` reads only). "Guess" means a label used on related Volvo/Geely cars, not checked on this car.

| Address | Module | Basis |
|---|---|---|
| `1001` | Gateway (DoIP entity) | addressing |
| `1011` | Telematics | SIM and modem IDs, assistance phone numbers in DIDs |
| `1012` | Driver monitoring | guess |
| `1015` | 360 camera / park assist, most likely (label WAM: Volvo's Wide Angle vision Module) | four surround-view camera entries (`E30D`-`E310`, OmniVision `OX03C10`); parking sensor distances `B112`-`B121`; software `PAS_V2.8.2` |
| `1023` | Key system control module (BNCM), Marquardt | reports `BNCM` and `MARQUARDT`, matching the manual's key system certification (BNCM model GE1; the FCC label drawing is headed Lotus, see [siblings](siblings.md)); the phone charger is a separate Changzhou Tenglong part |
| `1201` | Infotainment | park signal `D938` |
| `1202` | Camera / vision | guess; a second address on the infotainment unit (same core part and serial as `1201`) |
| `1212` | Audio amplifier | guess |
| `1213` | Rear-seat entertainment | guess |
| `1251` | Head-up display | guess; answers physical addressing only, not `1FFF` |
| `1301` | Mobileye SuperVision ECU | firmware string names `P417_EU` and `GAS52`; 7 camera entries (`D921`–`D927`) with 4 type codes |
| `1314` | Dash camera | guess |
| `1316` / `1317` | Unknown left/right pair | same hardware and delivery parts, different software parts, serials 7 apart, same DID set, very few live values (`D237` is a heartbeat log); corner sensors? (the manual certifies only one radar, so probably not radars). A used part with the same part numbers is a Polestar-branded box with a wire antenna ([siblings](siblings.md)) |
| `1344` | Front radar | label guess; the manual certifies one radar, the F5CP12 front-centre unit (FCC grantee NF3 = Bosch) |
| `1601` | Vehicle dynamics / parking brake | EPB signals |
| `1614` | Suspension | chassis mode `D90F` |
| `1615` | Steering column lock | guess |
| `1631` | Front drive motor controller (probable) | speed `D003`; `E307`/`E303` active only when the front motor drives (pull-aways); a US owner reads F80A `DMC2` (drive motor controller 2) |
| `1633` | Gear stalk | stalk movement only |
| `1635` | HV battery | SOC, pack V/I, cells |
| `1637` | Rear inverter / e-machine | drive engaged `E307`, torque direction `E319`; `EEC4` rose 0x3A → 0x3E on a drive (temperature?) |
| `1650` | Charger / inlet | charge signals |
| `1656` | Unknown, charging-related (the bulletins put the DC-DC converter in the CDD, see `1650`) | since 4.3.0 `F80A` reads `BCC1-B+ChargerCtrl1`; `4947`/`D110` read 14.0–14.2 V (12 V rail, as on `1635`); hardware `HX1100` |
| `1670` | Power steering, first channel | steering angle `3019` (= `0x3853` - 0.5614 x `1672:3019`: 0.1 °/count, right positive?) |
| `1672` | Steering angle sensor? | `3019` (also answers on `1670`/`1676`); a US owner reads F80A `CHCM` (chassis controller): unverified here; one unit with the gear stalk `1633` (same core part and serial) |
| `1675` | Bosch chassis sensor? | its part number is sold used as a Bosch sensor from a Polestar 4 and a Zeekr 001 ([siblings](siblings.md)); config string `GE60_P03_M10_…`; OBD speed `F40D` tracks `D003`; `FE08` follows `1701:FE08` channel 1 (brake pressure), so it looks like a received signal |
| `1676` | Power steering, second channel | same 50 DIDs as `1670`, sibling (not identical) part numbers; `3019`/`D900` read the same angle as `1670` within 0-2 counts (up to 4 while turning); `D901` assist load peaks at full lock on both |
| `1691` | Second address for `1601` | answers 701 of `1601`'s 702 DIDs (`F13F` refuses here, response too long), same parts and software; first seen after the 4.3.0 update |
| `1701` | Brake system (BSCM) | `F80A` reads `BSCM-BrakeSystem` (2026-11-12); config `BRP417EA`; shares 29 DIDs with `1631`; brake pressure/pedal candidates `FE08`, `D905`/`D906` |
| `1A01` | Body / central electronics | lamps, doors |
| `1A11` | Climate | flap positions |
| `1A12` / `1A13` | Driver / passenger door | windows, handles |
| `1A15` | Tailgate | position |
| `1A21` / `1A22` | Rear doors | windows |
| `1A27` / `1A28` / `1A29` | Seats: driver / passenger / rear | seat position |
| `1A30` | Interior lighting | guess |
| `1B61` | Unknown | 29 DIDs, its own part numbers, `F120` = `14TR AA`; first seen after the 4.3.0 update |
| `1BB3` / `1BB4` | Headlamps L/R | matrix segments |
| `1C01` | Airbags | guess |

Other notes:
- `D904` on several modules moves 0x96/0x97 with load: probably supply voltage in 0.1 V steps.
- `1635` `49F6` + `49F7` always add up to the same total (~4460): an energy used/remaining pair.
- On this UK car the telematics unit holds a configured GB/T 32960 (Chinese EV remote-monitoring standard) server address pointing at a test host. Whether it ever sends anything isn't known.

## Label sources (manufacturer bulletins)

The short names in the table above are the usual Volvo/Geely labels for these addresses on related cars. These manufacturer technical journals (service bulletins), published by NHTSA, spell out what the labels mean. They describe related cars as well as the Polestar 4; nothing here was tested on this car beyond what the module sections say.

| Label | Meaning (per the bulletin) | Bulletin | Link |
|---|---|---|---|
| VGM | Vehicle Gateway Module (the Polestar 4 gateway; the bulletin gives no address, so our `1001` label VCM may be wrong) | Polestar TJ 37280, Polestar 4 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11021908-0001.pdf) |
| VCM | Vehicle Connectivity Module (connectivity certificates) | Polestar TJ 36628, Polestar 2/3 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11031084-0001.pdf) |
| WAM | Wide-Angle Vision Module (driver support, parking assistance) (`1015`) | Polestar TJ 37493, Polestar 4 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11029161-0001.pdf) |
| WAM | a WAM fault can make a full software download fail; it gets its own fix first | Polestar TJ 37940, Polestar 4 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11037952-0001.pdf) |
| CDD | Charger and DCDC Module (`1650`) | Polestar TJ 37772, Polestar 4 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11032615-0001.pdf) |
| CDD | Charger and DC-DC Module; charge-inlet faults traced under it | Volvo TJ 37436, EX30 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11037960-0001.pdf) |
| CEM | Central Electronic Module (`1A01`); can stay in "OTA mode" after a failed update (no start) | Polestar TJ 37431, Polestar 4 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11023525-0001.pdf) |
| BECM | Battery Energy Control Module (`1635`) | Polestar TJ 37385, Polestar 2 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11020562-0001.pdf) |
| AUD | Audio Unit Device (`1212`) | Polestar TJ 36569, Polestar 2 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11035014-0001.pdf) |
| IEM | Inverter Electric(al) Rear Axle Drive (Module) (`1637`) | Polestar TJs 37102 and 37523, Polestar 2 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11025983-0001.pdf) |
| HUD | Heads up display (`1251`) | Polestar TJ 37455, Polestar 3 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11022802-0001.pdf) |
| TEM | Telematics Electronic Module (`1011`) | Volvo TJ 31938 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2016/MC-10167812-9999.pdf) |
| SUM | suspension module (`1614`) | Volvo TJ 31236 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2016/MC-10110152-9999.pdf) |
| POT | Power Operated Tailgate (`1A15`) | Volvo TJ 37159, EX90 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11016903-0001.pdf) |
| DDM, PDM | Driver Door Module, Passenger Door Module (`1A12`, `1A13`) | Volvo TJ 37294, EX30 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11016910-0001.pdf) |
| HCML, HCMR | Headlamp Control Module Left/Right (`1BB3`, `1BB4`) | Volvo TJ 37571, EX90 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2026/MC-11028393-0001.pdf) |
| SRS | Supplement Restraint System (`1C01`) | Volvo TJ 36048 | [NHTSA](https://static.nhtsa.gov/odi/tsbs/2025/MC-11016886-0001.pdf) |
