# Polestar 4 DoIP

Read-only mapping of a Polestar 4's diagnostic data over DoIP (ISO 13400) through the OBD port: which modules answer, which DIDs they hold, and what the DIDs mean. Mapped on one 2026 UK car; other markets and software versions may differ.

**The data:**

- [`catalogue/signals.yaml`](catalogue/signals.yaml): decoded signals (module, DID, encoding, real examples), each marked C (confirmed) or P (provisional)
- [`catalogue/modules.yaml`](catalogue/modules.yaml): every module address that answers, with a label and status confirmed / unverified / unknown
- [`docs/did-map.csv`](docs/did-map.csv): every DID that answered on each module (or exists but refused), with status and response length; most are not decoded yet
- [`docs/modules.md`](docs/modules.md): what each module is and the evidence
- [`DISCOVERIES.md`](DISCOVERIES.md): what each release (a batch of sessions at the car) found

> [!WARNING]
> **Never read DID `EE13` on module `1301`** (the Mobileye driver assistance ECU). On this car it knocked that ECU off the network for about a minute, twice, while parked. A broadcast to `1FFF` or a range sweep that includes `EE13` also reaches `1301`. The tool refuses this read (`BLOCKED_READS` in `tool/p4doip/client.py`). `1635:EE13` (HV discharge counter) is a different module and is safe.
>
> Read-only does not mean risk-free. Use this parked, with the car's 12 V battery in good health, and never while driving except for a passive `watch` of known DIDs. You use it at your own risk.

## What's here

| Path | What |
|---|---|
| `catalogue/signals.yaml` | Decoded signals with their encoding and real examples the tests check. Confidence C = the same change seen at least twice in both directions; P = anything less |
| `catalogue/modules.yaml` | The 43 modules that answer, with a label and status confirmed / unverified / unknown |
| `docs/modules.md` | Module map: what each module is and the evidence |
| `docs/did-map.csv` | Every DID that answered, per module, with its response length (no values). Regenerate with `scripts/export-did-map.sh` |
| `tool/` | The `p4` tool, a simulated gateway and the tests |
| `web/` | Optional status site and live DID view (`docker` container, http://localhost:8088) |
| `scripts/drive-watch.sh` | Fast watch list for a drive (power, speed, gear, lamps, steering, chassis mode, matrix headlamps) |
| `scripts/pcap_uds.py` | Offline decoder for DoIP/UDS in pcap files |
| `scripts/prepublish-check.sh` | Fails if anything identifying (VIN, SIM or modem IDs, phone numbers, raw runs, pcaps) is tracked |
| `DISCOVERIES.md` | Discovery log: what each release (session) found |
| `PLAN.md` | Discovery method |

Not in the repository (git-ignored): `runs/` (tool output, which can contain the VIN), `captures/` (pcaps), `local/` (working notes) and `external/` (OBDb signal files, CC BY-SA 4.0; get them from [OBDb](https://github.com/OBDb)).

## Connecting

DoIP gateway logical address `1001`, tester `0E80`, routing activation type `00`, TCP 13400, DoIP protocol version 2, no TLS. Functional address `1FFF` reaches every module (`E400` is rejected). All reads are `22 xxxx` in the default session; no session change or security access is used. The gateway accepts one tester at a time.

## Tool

`./p4 <command>` runs in Docker (image `p4doip:local`, built on first use; `./p4 build` rebuilds). Nothing is installed on the host. The gateway address defaults to `169.254.19.1` (`--host` or `P4_HOST` to change).

| Command | Does |
|---|---|
| `./p4 test` | Offline tests against a simulated gateway |
| `./p4 discover` | TesterPresent to every address 1000–1FFE; lists modules, new ones and missing ones |
| `./p4 identify 1316 1317` | Part numbers and serials (`all` = every catalogue module) |
| `./p4 dtc 1316` | Stored and supported fault codes (`all` works here too) |
| `./p4 scan 1316` | Which DIDs answer (default ranges ~6 min; `--ranges 0000-FFFF` ~45 min). Skips DIDs already answered in any earlier run and blocked reads; `--rescan` overrides the first |
| `./p4 scan 1317 --like 1316` | Try a sibling's answering DIDs |
| `./p4 known 1316 --list` | What has been found on a module, including DIDs that exist but refused |
| `./p4 watch 1316` | Poll all known DIDs and print changes. Leave the car alone for the first 20 s: whatever changes then is hidden as background noise (`--baseline 0` to skip) |
| `./p4 watch 1601:E37B,2B1A --interval 0.1 --baseline 0` | Poll chosen DIDs fast (`--mute 5` hides a value that blinks) |
| `./p4 snapshot before 1316 1317`, do the action, `./p4 snapshot after 1316 1317`, then `./p4 diff before after` | Compare two moments |
| `./p4 mark "left front door"` | Timestamp an action in `local/session-log.md` and `runs/<date>/marks.jsonl` (works while a watch is running) |
| `./p4 signals` | List and validate the signal catalogue |
| `./p4 correlate 2026-11-11` | For each `mark` that day, the watch `CHANGE` lines from 2 s before to 15 s after (`--before`, `--after`; offline) |
| `./p4 strings 1316` | Readable text in the answered DIDs, with VIN, SIM and IMEI-like values masked (offline) |

The tool can only send UDS reads (0x22, 0x19, 0x3E); anything else, and any read on `BLOCKED_READS`, is refused in `tool/p4doip/client.py` before it reaches the socket, and the tests cover that. Every command except the offline ones (`diff`, `mark`, `known`, `signals`, `strings`, `correlate`) runs as container `p4-live`, so a second one fails instead of knocking the first off; `docker stop p4-live` frees the gateway. Disconnect any other diagnostic tool first.

To capture alongside, tcpdump needs capture rights on the adaptor (`CAP_NET_RAW`), e.g. `sudo tcpdump -i <adaptor> -s 0 -U -w captures/doip-%Y%m%d-%H%M%S.pcap -G 1800`. Pcaps contain the VIN.

## Releases

A release is a discovery log entry, not a software build: no assets, just notes. After a session at the car:

1. Add an entry at the top of `DISCOVERIES.md`, headed `## YYYY.MM.DD - <title>`, covering new signals (with C/P), modules identified, hazards, corrections and what was looked for but not found. Update `catalogue/` and `docs/` in the same change (`scripts/export-did-map.sh` regenerates the DID list).
2. Merge it to `main` with CI passing.
3. Run `scripts/release.sh YYYY.MM.DD` on an up-to-date, clean `main`. It runs the pre-publish check, tags the version and creates a GitHub release whose notes are that entry. A second release on the same day uses `YYYY.MM.DD.2`.

## Licence

MIT, see `LICENSE`.
