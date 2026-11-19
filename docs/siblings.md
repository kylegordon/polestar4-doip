# Sibling cars and shared parts

The Polestar 4 is built on Geely's SEA platform (Sustainable Experience Architecture), and several other
Geely-group cars use the same parts. Their parts listings, manuals, radio filings and owners' findings can
help name or check modules on this car, and our findings may help their owners in turn. This page lists the
sibling cars and every shared part found so far, with how strong each link is.

**Same part** means a matching part number. **Hint** means a weaker link, such as a shared manual page or a
supplier filing for another brand; it is a lead to check, not a finding. Nothing here changes a module's
status in [`catalogue/modules.yaml`](../catalogue/modules.yaml) on its own.

## Sibling cars

All on SEA. Sources disagree on the variant names (SEA1, SEA2, and SEA-P/SEA-S/EPA/EMA for the Lotus cars),
so treat those labels as unchecked.

| Car | Notes |
|---|---|
| Zeekr 001 | the first SEA car; same rear motor and the same `1675` part as this car |
| Zeekr 007, Zeekr X | SEA |
| smart #1, smart #3 | SEA, the compact variant; same motor family (TZ220XSA01/02) |
| Lotus Eletre, Lotus Emeya | SEA, the high-performance variant; phone key with Bluetooth, UWB and NFC, NFC card key |
| Volvo EX30 | SEA |

## Shared parts

| Part on this car | Shared with | Link | Evidence |
|---|---|---|---|
| Rear motor TZ220XSA02 | Zeekr 001 (same part), smart #1 (same family) | same part / hint | Polestar 4 UK manual; a Zeekr 001 RWD dismantler listing gives the same motor code; the smart #1 manual lists TZ220XSA01/02 |
| `1675` (`D901` part 8889074832) | Zeekr 001 | same part | sold used from a Polestar 4 AWD ([autoparts-24](https://www.autoparts-24.com/item/N_0917_198542/)) and a Zeekr 001 ([japoto.nl](https://www.japoto.nl/nl/onderdeel/zeekr/001/snelheid-sensor/25935506/)); see below |
| Key system control module `1023`, Marquardt GE1 | Lotus | hint | the GE1 FCC label drawing is headed "Lotus" and names it "communication module - BLE and NFC key" ([FCC ID IYZGE1](https://fccid.io/IYZGE1)) |
| NFC reader, Marquardt GR3 | Lotus | hint | filed with the FCC as "Lotus NFC Reader" ([IYZGR3](https://fccid.io/IYZGR3)) |
| UWB anchors, Marquardt GU1 | Geely | hint | filed as "Geely UWB module" ([IYZGU1](https://fccid.io/IYZGU1)) |
| Key system as a whole | Volvo EX30 | hint | the EX30 manual's key-system certification page has the same article ID as the Polestar 4 one (`0a500a085a173960c0a8b09771bff25e-f19ebb76fc2e9629ac1b7acc5528389d`); its content was not readable, so the parts it lists are unchecked |

### `1675`: a Bosch sensor part

The part number in `1675:D901` is sold used as a Bosch sensor: the label in the listing photos reads Bosch
`0 265 011 171`, with a two-hole mount, an orientation arrow and a four-pin plug. Dismantlers call it an
acceleration sensor or a speed sensor. Bosch's `0 265 0…` numbers cover chassis sensors such as yaw-rate
and acceleration sensors; this exact number was not found in a Bosch catalogue. So `1675` is probably
Bosch's inertial sensor (inference).

That does not fit the readings decoded so far: `1675:FE08` follows the brake pressure on `1701` (r 0.988 on a
drive), not the car's deceleration (r -0.26 against `1601:2B11`), and stays high while the car is held on
the brake. So `FE08` and `D941` look like signals `1675` receives from other modules, not its own
measurements, and their "not available" values (`7fff`, `ffff`) would then mean the input is missing
(inference). See [`findings.md`](findings.md#1675-unknown-chassis-module-bosch-sensor).

### `1316`/`1317`: a Polestar-branded radio unit

A Norwegian dismantler sells a part from a Polestar 4 whose label carries the same hardware and delivery
part numbers as `1316`/`1317` (6608445312, 6608445525). The label says Polestar (not a supplier), with
CE, RCM and FCC marks but no FCC ID, and the unit has a wire antenna. The dismantler lists it as an electric
tailgate control unit; that may only be where it was fitted, since this car's tailgate controller is `1A15`
with different parts. What it does is still open.

## Radio filings

The FCC and ISED filings named in the Polestar 4 manual, with what each filing adds. None of the diagnostic
reads recorded from this car holds an FCC ID.

| FCC ID | Part | From the filing |
|---|---|---|
| [IYZGE1](https://fccid.io/IYZGE1) | Marquardt GE1, the BNCM (`1023`) | Bluetooth LE 2402-2480 MHz; label "communication module - BLE and NFC key", drawing headed Lotus |
| [IYZGU1](https://fccid.io/IYZGU1) | Marquardt GU1, UWB anchor | "Geely UWB module", 6489.6 and 7987.2 MHz. The technical description says six per car, on CAN with a daisy chain to the body controller; the key measures its distance to each by time of flight. 72.8 x 39.5 x 18.7 mm, white cover, antenna on the board |
| [IYZGR3](https://fccid.io/IYZGR3) | Marquardt GR3, NFC reader | "Lotus NFC Reader", 13.56 MHz |
| [IYZGK2](https://fccid.io/IYZGK2) | Marquardt GK2, key fob | "V216 keyfob", UWB and Bluetooth LE |
| [NF3-F5CP12](https://fccid.io/NF3-F5CP12) | Bosch front radar F5CP12 | "Front Radar Gen5 Car Plus", 76.06-76.955 GHz; the label reads "BOSCH ACC" |

Other Marquardt filings of the same family, not yet linked to a car: [GR4](https://fccid.io/IYZGR4) (NFC
reader), [GC1](https://fccid.io/IYZGC1) (Bluetooth key fob), [GK2A](https://fccid.io/IYZGK2A) (key with UWB
and Bluetooth).

## Help wanted

- Owners of the cars above: a module list, part numbers (`F1AA`, `F1AB`) or a DID scan from your car would
  show which of our modules you share. Open an issue; leave out your VIN and serials.
- Dismantler listings or labels for any part number in [`catalogue/hardware.yaml`](../catalogue/hardware.yaml),
  from any of these cars.
- Manual pages from the sibling cars that share article IDs with the Polestar 4 manual.

Sources: the links above; [Lotus Connect](https://www.lotuscars.com/en-GB/lotus-connect) (Eletre phone key);
[Electrek on the Emeya car key](https://electrek.co/2024/02/05/lotus-confirms-2024-emeya-car-key-support-control-from-iphone-apple-watch/);
[Wikipedia: Sustainable Experience Architecture](https://en.wikipedia.org/wiki/Sustainable_Experience_Architecture_platform);
[just-auto: Geely group, the future models](https://www.just-auto.com/features/geely-group-the-future-models).
