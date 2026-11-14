# Polestar 4 DoIP

Read-only mapping of a Polestar 4's diagnostic data over DoIP (ISO 13400) through the OBD port: which modules answer, which DIDs they hold, and what the DIDs mean. Mapped on one 2026 UK car; other markets and software versions may differ.

**The data:**

- [`catalogue/signals.yaml`](catalogue/signals.yaml): decoded signals (module, DID, encoding, real examples), each marked C (confirmed) or P (provisional)
- [`catalogue/modules.yaml`](catalogue/modules.yaml): every module address that answers, with a label and status confirmed / unverified / unknown
- [`catalogue/dids.yaml`](catalogue/dids.yaml): DID names and families (ISO 14229 identity names, common blocks)
- [`catalogue/hazards.yaml`](catalogue/hazards.yaml): reads that upset a module, as `block` or `caution`, with the evidence
- [`catalogue/dtc.yaml`](catalogue/dtc.yaml): named diagnostic trouble codes (empty until one is established)
- [`docs/did-map.csv`](docs/did-map.csv): every DID that answered on each module (or exists but refused), with status and response length; most are not decoded yet
- [`docs/modules.md`](docs/modules.md): what each module is and the evidence
- [`docs/findings.md`](docs/findings.md): everything learned so far, module by module, including unconfirmed leads and open questions
- [`docs/did.md`](docs/did.md): DID-decoding work: state, method, candidate index (with the ledger, sessions, entries and leads)
- [`DISCOVERIES.md`](DISCOVERIES.md): what each release (a batch of sessions at the car) found
- [`CHANGELOG.md`](CHANGELOG.md): tool, catalogue and documentation changes

> [!WARNING]
> **Never read DIDs `EE13` or `EE14` on module `1301`** (the Mobileye driver assistance ECU). On this car `EE13` knocked that ECU off the network for about a minute, twice, while parked; `EE14` did the same on 2026-11-14, the passenger airbag lamp blinked, and the gateway refused diagnostic connections until the adaptor was replugged. A broadcast to `1FFF` or a range sweep that includes them also reaches `1301`. The tool refuses these reads from [`catalogue/hazards.yaml`](catalogue/hazards.yaml), on `1301` and on any functional address. `1635:EE13` and `1635:EE14` (HV discharge and charge counters) are a different module and are safe on a physical read; only functional (broadcast) reads of those DIDs are refused.
>
> `1601:D928`-`D92C` are recorded as **caution**: the module stopped answering once after one of them, 3 s after the car woke (probably a start-up race). Ordinary scans skip them; `--allow-caution` or a `--paced` scan is needed to test one.
>
> Read-only does not mean risk-free. Use this parked, with the car's 12 V battery in good health, and never while driving except for a passive `watch` of known DIDs. You use it at your own risk.

## What's here

| Path | What |
|---|---|
| `catalogue/signals.yaml` | Decoded signals with their encoding and real examples the tests check. Confidence C = the same change seen at least twice in both directions; P = anything less |
| `catalogue/modules.yaml` | The 43 modules that answer, with a label and status confirmed / unverified / unknown |
| `catalogue/hazards.yaml` | Blocked and cautioned reads; the tool loads it before every car-facing command |
| `catalogue/dids.yaml` | DID registry: names, families, which values are per-car (masked) |
| `catalogue/dtc.yaml` | DTC code to name mappings (empty until established) |
| `docs/modules.md` | Module map: what each module is and the evidence |
| `docs/did-map.csv` | Every DID that answered, per module, with its response length (no values). Regenerate with `./p4 didmap` (or `scripts/export-did-map.sh`, a wrapper) |
| `docs/did.md` | Entry point for the DID-decoding backlog (ledger, sessions, entry drafts, leads) |
| `tool/` | The `p4` tool, a simulated gateway and the tests |
| `web/` | Optional status site and live DID view (Docker image, http://localhost:8088) |
| `scripts/drive-watch.sh` | Fast watch list for a drive (power, speed, gear, lamps, steering, chassis mode, matrix headlamps) |
| `scripts/pcap_uds.py` | Offline decoder for DoIP/UDS in pcap files |
| `scripts/patterns.txt` | The identifying-content patterns, shared by the prepublish check and the public site's output scan |
| `scripts/prepublish-check.sh` | Fails if anything identifying (VIN, SIM or modem IDs, phone numbers, raw runs, pcaps) is tracked, or if `docs/did-map.csv` is stale where `runs/` exists |
| `DISCOVERIES.md` | Discovery log: what each release (session) found |
| `CHANGELOG.md` | Tool/catalogue/documentation changes (not car observations) |
| `PLAN.md` | Historical discovery method; current work is in `docs/did.md` and the audit |

Not in the repository (git-ignored): `runs/` (tool output, which can contain the VIN), `captures/` (pcaps), `local/` (working notes) and `external/` (OBDb signal files, CC BY-SA 4.0; get them from [OBDb](https://github.com/OBDb)).

## Connecting

DoIP gateway logical address `1001`, tester `0E80`, routing activation type `00`, TCP 13400, DoIP protocol version 2, no TLS. Functional address `1FFF` reaches every module (`E400` is rejected). All reads are `22 xxxx` in the default session; no session change or security access is used. The gateway accepts one tester at a time.

## Tool

`./p4 <command>` runs in Docker (image `p4doip:local`, built on first use; `./p4 build` rebuilds). The gateway address defaults to `169.254.19.1` (`--host` or `P4_HOST` to change).

Car-facing commands need a host where Docker can use the car's network: `--network host` is native on **Linux**. On Docker Desktop for macOS the USB-Ethernet/link-local adaptor is not inside the VM, so use a Linux capture machine for sessions. Offline commands and `./p4 test` work anywhere. `./p4 doctor` checks the catalogue, hazards, did-map and (unless `--offline`) the gateway.

Global options go before the command: `--host`, `--port`, `--retries`, `--retry-wait`, `--allow-caution`, `--json` (on the commands that list it).

### Car-facing

| Command | Does |
|---|---|
| `./p4 test` | Offline tests against a simulated gateway (the whole suite: also run `pytest tool/tests` on the host) |
| `./p4 doctor` | Preflight self-check; `--offline` skips the gateway |
| `./p4 discover` | TesterPresent to every address 1000–1FFE; lists modules, new ones and missing ones |
| `./p4 identify 1316 1317` | Part numbers and serials (`all` = every catalogue module) |
| `./p4 whois 1316` | One-shot profile of an unknown module: usage mode, identity DIDs (masked ones as zeros, no text), stored/supported DTC counts and the closest cousins in `docs/did-map.csv` |
| `./p4 dtc 1316` | Stored and supported fault codes (`all` works too); `--names` labels from `catalogue/dtc.yaml`, `--freeze D12345` reads a freeze frame, `--json` |
| `./p4 read 1601:E37B,2B15` | Read chosen DIDs once; `--repeat N`, `--interval s`, `--json`. `--multi` sends one `0x22` with several DIDs (experimental: needs known lengths in `docs/did-map.csv`) |
| `./p4 scan 1316` | Which DIDs answer (default ranges ~6 min; `--ranges 0000-FFFF` ~45 min). Skips DIDs already answered in any earlier run, blocked/caution reads and hazards; `--rescan` overrides answered ones |
| `./p4 scan 1316 --dids-file candidates.txt` | Scan an explicit list (hex, spaces/commas, `#` comments, ranges allowed); `--names` labels the OK lines |
| `./p4 scan 1316 --adaptive-timeout` | Speeds up long silent ranges: after 20 DIDs with no answer in a row the per-DID timeout drops to 40% (min 0.2 s); every 50th DID is still probed at the full timeout and any answer restores it. Never applies to `--paced` |
| `./p4 scan 1316 --skip-silent-after 7` | Also skip DIDs that were silent within the last 7 days (resume a full-range scan without re-probing everything) |
| `./p4 scan 1317 --like 1316` | Try a sibling's answering DIDs |
| `./p4 scan 1316 --ranges D900-D9FF --paced 2` | Careful mode: one DID at a time, checks the module and the gateway still answer after each read, waits 2 s; stops at the first refusal, dropped connection or silence, records that DID as a hazard (scan never reads it again, even with `--rescan`; add it to `catalogue/hazards.yaml` to block it everywhere) and reports how long the module took to come back. `./p4 known 1301 --list` lists recorded hazards |
| `./p4 sweep --plan plan.yaml` | Run a scan plan unattended: slots in order, a bounded watch after each, progress after every slot in `runs/<date>/sweep.progress.json` and a `sweep.log` for the status site; `--dry-run` validates and prints ETAs, `--max-minutes` stops between slots, SIGTERM stops after the current slot. `--adaptive-timeout`/`--rescan`/`--skip-silent-after` apply to every slot; a slot may override `rescan`, `adaptive_timeout`, `timeout` |
| `./p4 known 1316 --list` | What has been found on a module, including DIDs that exist but refused, transient refusals and hazards (`--names` labels) |
| `./p4 watch 1316` | Poll all known DIDs and print changes. Leave the car alone for the first 20 s: whatever changes then is hidden as background noise (`--baseline 0` to skip) |
| `./p4 watch 1601:E37B,2B1A --interval 0.1 --baseline 0` | Poll chosen DIDs fast (`--mute 5` hides a value that blinks; `--keepalive 2` keeps the session alive through long intervals) |
| `./p4 snapshot before 1316 1317`, do the action, `./p4 snapshot after 1316 1317`, then `./p4 diff before after` | Compare two moments |
| `./p4 mark "left front door"` | Timestamp an action in `local/session-log.md` and `runs/<date>/marks.jsonl` (works while a watch is running) |

A sweep plan is YAML — a list of slots, or `{slots: [...], parked: true}` to record the car state for the status site:

```yaml
parked: true
slots:
  - {module: "1601", ranges: "E300-E4FF", watch: "E37B,2B1A", watch_secs: 240}
  - {module: "1635"}                        # ranges defaults to the scan defaults; add paced: 0.5 for careful mode
  - {module: "1251", ranges: "", watch: "F18C"}   # empty ranges = watch-only slot
```

Unknown plan keys are an error (a typo cannot silently become a default). `--dry-run` prints what each slot would try, how many DIDs are already settled and a rough ETA without connecting or writing anything.

### Offline

| Command | Does |
|---|---|
| `./p4 hazards` | List blocked/cautioned reads and their evidence |
| `./p4 did E37B` / `./p4 did speed` | Look up a DID: registry name, matching signals, modules that answer |
| `./p4 signals` | List and validate the signal catalogue |
| `./p4 correlate 2026-11-11` | For each `mark` that day, the watch `CHANGE` lines from 2 s before to 15 s after (`--before`, `--after`) |
| `./p4 strings 1316` | Readable text anywhere in the answered DIDs (plain, UTF-16, hex-wrapped), with VIN, SIM/IMEI, email and phone values masked (`--names` labels) |
| `./p4 similar 1316` | Modules whose answered DIDs look most like this one's (`--top N`, `--refused`); `--families` clusters look-alike modules |
| `./p4 scandiff 1601` | Which DIDs of a module changed status between two run days (`--day-a`, `--day-b`) |
| `./p4 dtcdiff 1601` | Which stored fault codes appeared or cleared between two run days |
| `./p4 ranges --module 1601` | Suggested `--ranges` specs from answered DIDs, per module or an `--all` union; reports how much `DEFAULT_RANGES` already covers |
| `./p4 tree` | DID coverage per module as a 0x1000-block bar |
| `./p4 runs` | Run days with scan/DTC/watch counts and size |
| `./p4 export --format json` | Export recorded DID facts (masked values stay zeros); `--format csv --out file` |
| `./p4 report 2026-11-13` | Markdown summary of a run day: scans, DTCs, watches, marks |
| `./p4 didmap` | Regenerate `docs/did-map.csv` from `runs/`; `--check` exits 1 when stale |
| `./p4 import-legacy` | Convert the 2026-11-10 text sweeps in `local/reads/` into `runs/` |

`--json` is available on `hazards`, `did`, `read`, `known`, `strings`, `signals`, `whois`, `dtc`, `diff`, `similar`, `ranges`, `scandiff`, `dtcdiff`, `runs`, `tree`, `doctor` and `export`.

The tool can only send UDS reads (0x22, 0x19, 0x3E). Anything else, and any blocked or (without `--allow-caution`) caution read, is refused in `tool/p4doip/client.py` before it reaches the socket, and the tests cover that. Every command except the offline ones shares the container name `p4-live`, so a second one fails instead of knocking the first off; `docker stop p4-live` frees the gateway. Disconnect any other diagnostic tool first.

## Status site

`web/` builds a small read-only page for a second screen during a session:

```sh
docker build -t p4-web web
docker run --rm --name p4-web -p 127.0.0.1:8088:8088 \
  -v "$PWD":/w:ro -v p4-web-srv:/srv -e P4_WEB_HOST=0.0.0.0 p4-web
# http://localhost:8088  (Live: /live.html)
```

**It shows raw car data unfiltered, including the GPS position, records that contain the VIN, and the TPMS sensor IDs. Run it only on a trusted private network; never publish it or forward its port to the internet.** It regenerates every 20 s from `runs/` (`sweep.progress.json`, `sweep.log`, scans, watches, marks) and serves the live DID view from the newest watch log. Inside the container it binds `0.0.0.0` so Docker can publish it; publish it on `127.0.0.1` only unless you intend the LAN to see the pages. The generator and server take `P4_WEB_W`, `P4_WEB_OUT`, `P4_WEB_SCANLOG`, `P4_WEB_HOST` and `P4_WEB_PORT` if you run them directly.

## Public site

[kylegordon.github.io/polestar4-doip](https://kylegordon.github.io/polestar4-doip/) is the plain-English, anonymised view of this repository for other owners: Start here, Hazards, Signals, Findings, Contribute and a Glossary. It is built by `.github/workflows/pages.yml` on every push to `main` from git-tracked files only (`tool/p4doip/site/`), shows session dates as month and year, and fails the build if any page matches `scripts/patterns.txt` or would be changed by the identifier masking. Design: [`docs/site-design.md`](docs/site-design.md). Build it locally:

```sh
git ls-files > .site-files && docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/w -w /w -e PYTHONPATH=tool --entrypoint python p4doip:local -m p4doip.site build --manifest .site-files --out _site
```

The image has no git, so the tracked-file list is passed in (`.site-files` and `_site/` are git-ignored). This reads the working-tree copies of tracked files; CI builds from `git archive HEAD`. After pulling this change, `./p4 build` once so the image has the Markdown package.

## Development

```sh
python3 -m pip install -r tool/requirements-dev.txt
pytest tool/tests                 # offline, simulated gateway (pyproject sets PYTHONPATH)
ruff check tool/p4doip web scripts
mypy tool/p4doip
shellcheck p4 scripts/*.sh web/start.sh
scripts/prepublish-check.sh
```

`./p4 test` runs the same suite in the image. Commit straight to `main`; run the prepublish check and the tests before every push. CI does all of the above, builds the image, and enforces 87 % line coverage on `tool/p4doip`.

To capture alongside, tcpdump needs capture rights on the adaptor (`CAP_NET_RAW`), e.g. `sudo tcpdump -i <adaptor> -s 0 -U -w captures/doip-%Y%m%d-%H%M%S.pcap -G 1800`. Pcaps contain the VIN.

## Releases

A release is a discovery log entry, not a software build: no assets, just notes. After a session at the car:

1. Add an entry at the top of `DISCOVERIES.md`, headed `## YYYY.MM.DD - <title>`, covering new signals (with C/P), modules identified, hazards, corrections and what was looked for but not found. Update `catalogue/` and `docs/` in the same change; add any new hazard to `catalogue/hazards.yaml` and regenerate the DID list with `./p4 didmap`.
2. Merge it to `main` with CI passing.
3. Run `scripts/release.sh YYYY.MM.DD` on an up-to-date, clean `main`. It runs the pre-publish check, tags the version and creates a GitHub release whose notes are that entry. A second release on the same day uses `YYYY.MM.DD.2`.

## Licence

MIT, see `LICENSE`.
