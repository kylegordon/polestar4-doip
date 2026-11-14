# Identification DIDs (F18x/F19x, F120-F12E, F1A0+, DDxx, D134)

Names and length checks for the DIDs the tool treats as identification (`IDENTITY_DIDS` in `tool/p4doip/cli.py`), plus `F180`, `F181`, `F184`, `F18E`, `F190`, `F196`, `F198`: 39 DIDs. Intended as labels for the ~800 unlabelled DID rows in `did-map.csv`.

- **Method**: names from the ISO 14229-1:2020 Annex C DID definitions as reproduced by the [py-uds knowledge base](https://uds.readthedocs.io/en/latest/pages/knowledge_base/did.html); `F197`/`F19D` independently confirmed by [ISO 16844-7:2015 (tachograph parameters, which reuse UDS DIDs)](https://cdn.standards.iteh.ai/samples/57315/03df6fafca3442b3b5f0d150583195b4/ISO-16844-7-2015.pdf); `F186`/`F190` by [piembsystech](https://piembsystech.com/read-data-by-identifier-0x22/) and [CSSElectronics](https://www.csselectronics.com/pages/uds-protocol-tutorial-unified-diagnostic-services); `F180` by [icanhack.nl](https://icanhack.nl/knowledge-base/diagnostics/uds). Lengths from `docs/did-map.csv` (status `ok` rows, 43 modules, 2026-11-13).
- **ISO 14229-1 fixes almost no DID lengths** (content is "arbitrary length" per the standard); the notable fixed cases are `F186` (1 byte) and `F190` (17 bytes, ISO 3779 VIN). Most `F18x`/`F19x` DIDs are strings, so any non-zero length is compatible.
- **Verdicts**: CONFIRMED-FIT = standard length expectation met on every answering module; PLAUSIBLE = standard name exists and observed lengths do not contradict it; NOT OBSERVED = standard name exists but no module answers; MISMATCH = length contradicts the name. MISMATCH names must not be used as labels.
- **Masking rule**: this document carries names, module counts and lengths only. It must never contain the value of the VIN (`F190`), of serial-number-like DIDs (`F18C` if the ISO name applies, `F192`, `F198`), or of any IMEI, SIM, assistance-phone or other per-car identifier. The tool already stores `F190` as zeros of the same length (`stored_value` in `tool/p4doip/cli.py`) and `./p4 strings` masks telematics identifiers.

## Standard DIDs (ISO 14229-1:2020)

| DID | Standard name | Answers | Lengths (B) | Verdict | Evidence note |
|---|---|---|---|---|---|
| `F180` | bootSoftwareIdentification | 3 | 18 (`1023`), 25 (`1316`, `1317`) | PLAUSIBLE | Variable-length string by definition; any length fits |
| `F181` | applicationSoftwareIdentification | 1 | 18 (`1023`) | PLAUSIBLE | Variable-length string |
| `F184` | applicationSoftwareFingerprint | 1 | 31 (`1023`) | PLAUSIBLE | Variable-length string. NB: applicationDataIdentification is `F182`, not `F184` |
| `F186` | activeDiagnosticSession | 43 | 1 (all) | CONFIRMED-FIT | Standard fixed 1 byte (session number); 43/43 agree. Also refutes any "spare part number" label seen on other cars |
| `F187` | vehicleManufacturerSparePartNumber | 0 | - | NOT OBSERVED | Defined by ISO 14229-1:2020; no module answers |
| `F188` | vehicleManufacturerECUSoftwareNumber | 0 | - | NOT OBSERVED | Defined; no module answers |
| `F189` | vehicleManufacturerECUSoftwareVersionNumber | 0 | - | NOT OBSERVED | Defined; no module answers |
| `F18A` | systemSupplierIdentifier | 19 | 6 (18 modules), 24 (`1023`) | PLAUSIBLE | String-compatible. OEM usage on related cars reads `F18A` as hardware part number; both fit. The 6-byte answers match short part strings (e.g. `1656`'s `HX1100`) |
| `F18B` | ECUManufacturingDate | 0 | - | NOT OBSERVED | Defined; no module answers |
| `F18C` | ECUSerialNumber | 43 | 4 (all) | PLAUSIBLE | 4 bytes fit a 32-bit serial (ISO name) or a 4-char system code (OEM reading "system name/type"); lengths cannot separate the two. Values are per-car identifiers under the ISO reading - mask |
| `F18E` | vehicleManufacturerKitAssemblyPartNumber | 0 | - | NOT OBSERVED | Defined; no module answers |
| `F190` | vehicleVIN | 11 | 17 (all) | CONFIRMED-FIT | VIN is 17 chars; 11/11 answering modules (`1001`, `1011`, `1023`, `1201`, `1314`, `1601`, `1635`, `1675`, `1701`, `1A01`, `1C01`). Values never published |
| `F191` | vehicleManufacturerECUHardwareNumber | 1 | 17 (`1023`) | PLAUSIBLE | String-compatible |
| `F192` | systemSupplierECUHardwareNumber | 1 | 24 (`1023`) | PLAUSIBLE | String-compatible |
| `F193` | systemSupplierECUHardwareVersionNumber | 2 | 6 (`1015`), 8 (`1023`) | PLAUSIBLE | Version-string compatible |
| `F194` | systemSupplierECUSoftwareNumber | 0 | - | NOT OBSERVED | Defined; no module answers |
| `F195` | systemSupplierECUSoftwareVersionNumber | 4 | 7 (`1012`), 8 (`1023`), 16 (`1344`), 30 (`1015`) | PLAUSIBLE | Heterogeneous lengths fit version strings from different suppliers; contradicts only the pre-2020-style "ECUManufacturingDate" reading (a 30-byte date is impossible) |
| `F196` | exhaustRegulationOrTypeApprovalNumber | 1 | 16 (`1015`) | PLAUSIBLE | Type-approval strings are long; fits |
| `F197` | systemNameOrEngineType | 2 | 16 (`1015`), 24 (`1023`) | PLAUSIBLE | Name also confirmed by ISO 16844-7 (acronym SNOET) |
| `F198` | repairShopCodeOrTesterSerialNumber | 1 | 16 (`1015`) | PLAUSIBLE | Content may be a tester serial: treat values as sensitive |
| `F199` | programmingDate | 1 | 10 (`1015`) | PLAUSIBLE | 10 bytes fit an ASCII date |
| `F19D` | ECUInstallationDate | 1 | 10 (`1023`) | PLAUSIBLE | Name also confirmed by ISO 16844-7 (acronym EID); 10 bytes fit a date |

## Manufacturer-specific DIDs (no standard name)

ISO 14229-1:2020 allocates `F100`-`F17F` and `F1A0`-`F1EF` to "vehicle manufacturer ... identification" and `CF00`-`EFFF` to vehicle-manufacturer use, so nothing below has a standard name. No meanings are claimed here beyond the project-established ones in `docs/findings.md`.

| DID | Answers | Lengths (B) | Observed pattern |
|---|---|---|---|
| `F120` | 43 | 7 | Uniform 7 bytes on every module |
| `F121` | 32 | 7 | Uniform; absent on the same 11 modules as `F125`/`F1A1`/`F1A5` |
| `F125` | 32 | 7 | Uniform; same coverage as `F121` |
| `F12A` | 43 | 7 | Uniform |
| `F12B` | 43 | 7 | Uniform |
| `F12E` | 43 | 8-92 | Varies per module; always 8+7k (8, 15, 22, 29, 36, 43, 50, 92) - looks like a count plus k 7-byte entries |
| `F1A0` | 43 | 8 | Uniform |
| `F1A1` | 32 | 8 | Uniform; same coverage as `F121` |
| `F1A5` | 32 | 8 | Uniform; same coverage as `F121` |
| `F1AA` | 43 | 8 | Uniform |
| `F1AB` | 43 | 8 | Uniform |
| `F1AE` | 43 | 9-105 | Varies per module and is arithmetically tied to `F12E`: F1AE = F12E + 1 + (F12E-8)/7 on every module - one structure, not two independent values |
| `DD00` | 40 | 4 | Project-established: free-running clock (`findings.md`) |
| `DD01` | 40 | 3 | Project-established: odometer in km (`findings.md`) |
| `DD02` | 40 | 1 | Unknown |
| `DD0A` | 40 | 1 | Project-established: power mode (`findings.md`) |
| `D134` | 40 | 1 | Unknown |

Coverage facts: `F121`/`F125`/`F1A1`/`F1A5` are absent on the same 11 modules (`1212`, `1251`, `1344`, `1615`, `1A01`, `1A27`, `1A28`, `1A29`, `1BB3`, `1BB4`, `1C01`); the `DD00`-`DD0A`/`D134` block is absent on `1202`, `1251` and `1656`.

## Warnings

- **No MISMATCH against the ISO 14229-1:2020 names.** The only length contradictions found are against names imported from other cars' diagnostic files: `F186` = 1 byte on 43/43 proves activeDiagnosticSession, so a "spare part number" label for `F186` cannot apply here, and `F195` as a manufacturing date is impossible (30-byte answer on `1015`). Do not paste `F18x`/`F19x` names from other OEMs/editions onto this car without the length check.
- `F184` is applicationSoftwareFingerprint in ISO 14229-1:2020; applicationDataIdentification is `F182`. The project shorthand that says otherwise is wrong.
- `F18C` (4 bytes on 43/43): the ISO name is ECUSerialNumber. If that holds, its values are per-car serials - never publish them. The alternative OEM reading (4-char system code) cannot be excluded by length; a content check on one module would settle it.
- `F192` and `F198` may carry per-car hardware/tester identifiers by their ISO names; mask their values too.
- `1023` (wireless phone charger) answers the widest standard identification block on the car (`F180`, `F181`, `F184`, `F186`, `F18A`, `F18C`, `F190`-`F193`, `F195`, `F197`, `F19D`) and is the only module with `F18A` = 24 bytes instead of 6: a different supplier stack, and the best module to read for label values.
- Only 11 of 43 modules serve the VIN (`F190`); `F187`, `F188`, `F189`, `F18B`, `F18E` and `F194` answer nowhere, so their labels stay name-only in `did-map.csv` annotations.
- `F12E` and `F1AE` lengths are coupled on every module (see table). Any future decoding must treat them as one structure; lengths grow in steps of 7 (`F12E`) / 8 (`F1AE`).
