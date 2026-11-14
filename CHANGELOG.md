# Changelog

Owned by the project; newest first. This file records tool, catalogue and documentation changes —
observations about the car belong in docs/findings.md and DISCOVERIES.md, not here.

## 2026-11-14 — public site, phase 1

- `tool/p4doip/site/`: builder for the public GitHub Pages site (Start here, Hazards, Signals, Findings,
  Contribute, Glossary). Inputs only through `Inputs.read_input` (git-tracked, never `runs/`, `local/`,
  `captures/`, `external/` or `NEXT.md`); free text has exact dates reduced to month and year and
  identifiers masked; every output file is scanned (`python -m p4doip.site scan`) and the build fails on a hit.
- `scripts/patterns.txt`: the prepublish patterns, now shared by `prepublish-check.sh` and the site scan.
- `tool/p4doip/render.py`: `CSS`, `TOKENS`, `coverage_bar` and `e`, shared by `web/gen.py` and the site.
- `.github/workflows/pages.yml` (SHA-pinned; build job read-only, deploy job alone writes Pages),
  `.github/dependabot.yml`, issue forms under `.github/ISSUE_TEMPLATE/`; `ci.yml` also builds the site.
- `tool/requirements.txt`: `markdown==3.7` (rebuild the image with `./p4 build`).
- `docs/site-design.md`: the design and the owner's decisions.

## 2026-11-14 — parked session: new signals, EE14 block, discovery bars

- `catalogue/hazards.yaml` + built-in `BUILTIN_BLOCKED`: `1301:EE14` blocked alongside `EE13` (it knocked the
  Mobileye ECU off and the gateway refused DoIP until the adaptor was replugged).
- `catalogue/signals.yaml`: about 35 signals added or upgraded from a parked hands-on session (drive mode,
  creep, door locks, seat heating and recline, steering wheel heat, rear fog, window motor and switch codes,
  rear climate flaps, cable present, 10 parking sensor distances, Mobileye uptime); `980E` removed.
- `catalogue/modules.yaml`: 1A27 and 1A29 confirmed; 1015 role notes the parking distances.
- `web/gen.py`: discovery progress bars (share of the 65,536 DIDs tried, per module and whole car);
  `web/live.html` nav matches the other pages; `web/matrix.html` layout wording.

## 2026-11-14 — audit backlog: safety, robustness, CLI, packaging

Implements a full review of the tool, tests, docs and data pipeline: safety, robustness, CLI, decoder,
privacy, web, packaging and CI. Suite: 691 tests, 90 % line coverage on tool/p4doip; ruff, mypy and
shellcheck clean; prepublish OK.

### Safety

- `catalogue/hazards.yaml` + `tool/p4doip/hazards.py`: blocked and cautioned reads with evidence. The
  built-in block on 1301:EE13 cannot be downgraded; 1601:D928-D92C are caution (start-up race). Loaded by
  the client on every read, applied to physical and functional targets. `p4 hazards` lists them.
- `--allow-caution` (global) is required for caution reads; a `--paced` scan allows them implicitly because
  it checks the module and gateway after every single read. Ordinary scans/watch/plans skip caution rows.
- `DoIP.request` caps ResponsePending replies at 8 (`MAX_PENDING`) and reports the cap as a timeout note:
  a broken ECU can no longer hold an unattended sweep forever.
- Transient NRCs (`0x21`, `0x24`) are retried in-process (3 attempts) and, if still refusing, stored with
  `retryable: true`; they never settle a DID and never enter docs/did-map.csv.
- A truncated JSONL record no longer breaks every reader: `read_jsonl` tolerates the last broken line and
  append_jsonl writes a repair marker so a new record cannot be swallowed by a half-written one.

### Tool

- `p4 read MODULE:DID[,DID]`: guarded one-off reads, `--repeat`, `--interval`, `--json`, and an
  experimental `--multi` (one 0x22 with several DIDs; splits only with known lengths from did-map.csv).
- `p4 did` looks up a DID by hex or name across the registry, signals and did-map; `known`/`strings`/`scan`
  gain `--names`; `scan --dids-file` scans a candidate list.
- `p4 hazards`, `p4 runs`, `p4 tree` (coverage bars), `p4 doctor` (preflight/self-check, `--offline`),
  `p4 export` (JSON/CSV, masked values stay zero), `p4 report DAY` (markdown summary).
- `--json` on hazards, did, read, known, strings, signals, whois, dtc, diff, similar, ranges, scandiff,
  dtcdiff, runs, tree, doctor, export.
- `scan --skip-silent-after DAYS` resumes a full-range scan without re-probing every silent DID; the
  policy is recorded in the run header. Run headers now carry `v: 2`, tool version, git commit, timeout,
  paced/rescan/adaptive flags and the skip policy.
- Sweep: `--rescan`, `--adaptive-timeout`, `--skip-silent-after`, `--dry-run` (validated plan + ETAs, no
  connection or writes), per-slot `rescan`/`adaptive_timeout`/`timeout`, strict unknown-key errors, a
  `sweep.log`, and progress written as `failed:`/`stopped` on errors and interrupts instead of leaving a
  stale slot. SIGTERM now ends a sweep watch promptly.
- Scan/sweep/watch input errors (bad hex, two modules in one watch spec) are clear `SystemExit` messages,
  not tracebacks. `--paced` hazards print a ready-to-paste hazards.yaml proposal.
- `p4 dtc`: status-bit legend, `--names` from catalogue/dtc.yaml, `--freeze DTC` (19 04), `--json`; the
  simulator can serve supported DTCs and freeze frames.
- Watch logs now start with a full ISO timestamp (old logs still parse), so `correlate`/web need no
  midnight heuristic; `watch --keepalive SECS` keeps the session alive through long intervals.
- `p4 strings` finds printable runs anywhere in a payload (after a binary header, UTF-16LE/BE, hex-wrapped),
  not only whole-payload text.

### Decoder and catalogue

- decode.py: `encoding: ascii`, `utf-16le`, `utf-16be`, `utf-8` (in addition to ascii-hex/raw), `endian:
  little` for integers/bits, and array counts from a sibling DID (`repeat.count_from`). `describe()` takes
  a sibling payload context; watch/sweep pass it in.
- signals.yaml: 105 -> 113. The eight docs/did-leads.md §1 rows landed as P with their full 1-byte
  payloads: `window_direction` (1A12/1A13 D008), `stalk_push_d914`/`_d915`/`_d919`/`_d920`,
  `stalk_hold_da02`/`_da03`, `obd_speed_1675` (1675 F40D).
- catalogue/dids.yaml now includes F196/F198; `IDENTITY_DIDS` probes both (F198 masked). F190 (VIN) is
  deliberately not probed (`IDENTITY_SKIP`) and documented.
- catalogue/dtc.yaml (new): optional DTC names; empty until a code is established.

### Privacy

- `tool/p4doip/privacy.py`: one masking/text implementation for the CLI, web and tests. `stored_value`,
  `MASKED_DIDS`, VIN/email/phone/long-number masking and printable-run extraction live there. `p4 read`
  now stores/prints masked DIDs as zeros (it briefly printed the raw VIN; a test caught it).
- The status site uses the same function, skips every `MASKED_DIDS` value and no longer prints emails or
  phone numbers. `web/server.py` binds 127.0.0.1 by default.

### Web

- `web/gen.py` reads `runs/*/sweep.progress.json` (and the older `unattended.progress.json`), and
  `latest_scan_results` reads the new `sweep.log`. Paths are configurable (`P4_WEB_W`, `P4_WEB_OUT`,
  `P4_WEB_SCANLOG`); the server takes `P4_WEB_HOST`/`P4_WEB_PORT`.
- `web/Dockerfile` + `web/start.sh` build the advertised container; README has the run recipe and publishes
  it on 127.0.0.1 only. `web/tests` (tool/tests/test_web.py) cover progress, scans, watch_last, masking and
  the server defaults.

### Packaging, CI, scripts

- `pyproject.toml` (package metadata, console script, pytest pythonpath, ruff/mypy config) and
  `tool/requirements{,-dev}.txt`; the Dockerfile installs from the requirements file.
- CI: prepublish, ruff, mypy, shellcheck, image build and pytest with 87 % coverage floor (actual 90).
- `scripts/export-did-map.sh` is now a wrapper around `p4 didmap` (one implementation, no jq/awk copy).
- `scripts/prepublish-check.sh`: the did-map freshness gate used bash-only `compgen` in a `#!/bin/sh`
  script and silently skipped under dash; it is POSIX now, with a test and shellcheck in CI.
- `scripts/pcap_uds.py` import style fixed for ruff.

### Documentation

- README: hazards section, car-facing/offline command tables, new commands and flags, status-site recipe,
  Linux/Docker networking note, development commands, doc links.
- CLAUDE.md, PLAN.md (now a method note pointing to did.md/audit), docs/did.md (T02 and counts corrected,
  113 signals), docs/did-sessions.md (hazard and watch-syntax notes), docs/did-leads.md (landed rows),
  docs/findings.md (catalogue/hazard status).
- Remaining work, deliberately not in this change: the web UI rewrite, native (non-Docker) transport, the
  voice channel, analyst note generation, and the did-leads §2 catalogue rows that still need a full-payload
  raw.

### Verification

- 691 tests, 98.9 s; coverage 90 % (all modules 87–100 % except `__main__`).
- `ruff check tool/p4doip web scripts`, `mypy tool/p4doip`, `shellcheck p4 scripts/*.sh web/start.sh`,
  `scripts/prepublish-check.sh`: clean.
- No car-facing command was run; every behaviour above is exercised against the simulated gateway.

## 2026-11-13/14 — DID deep dive, offline decoding push, sweep/identify tooling

### Tool (tool/)

- decode.py: new signal value modes — `encoding: ascii-hex` (ASCII hex digits stored as ASCII text,
  e.g. the release string in 1001 D0D0), `encoding: raw`, and arrays via `repeat: {count, len, ...}`
  (per-element spec reuses the existing keys; returns a list). Needed for the documented-but-uncatalogued
  cell/temperature/segment/log arrays. 8 new tests; catalogue/signals.yaml format block documents them.
- cli.py: `IDENTITY_DIDS` extended with the DIDs docs/did-identity.md proved answer on this car
  (F180, F181, F184, F196, F198, E103, D0B5) plus probes F182/F183/F18E/F18F — `identify` was
  incomplete before this.
- cli.py: `MASKED_DIDS` = {F190, F18C, F192, F198} — per-car identifiers (VIN, ECU serial per the ISO
  reading, supplier HW number, tester serial) are stored as zeros by `stored_value` and never printed;
  `identify` now stores/prints through it too (it wrote raw values before). Two tests updated to the
  new masked expectations.
- client.py: `NRC_NAMES` + `nrc_name()` (ISO 14229-1 negative response codes) for readable output;
  `p4 known --list` now prints "NRC 33 (securityAccessDenied)" style lines. Stored records keep the
  raw codes (wire/log format unchanged).
- cli.py: new offline command `p4 didmap` — regenerates docs/did-map.csv from runs/ (parity with
  scripts/export-did-map.sh: ok rows + NRC 22/33 rows, values never exported); `--check` exits 1 when
  the file on disk is stale. Added to the p4 wrapper's offline list.
- scripts/prepublish-check.sh: did-map freshness check — where runs/ exists, a stale docs/did-map.csv
  fails prepublish; elsewhere (CI, fresh clones) it is skipped or a note.

### Catalogue

- signals.yaml: 100 -> 105 signals. New (all P, raws quoted in docs/findings.md): `headlamp_scene`
  (1BB3/1BB4 4368 home-safe/approach), `welcome_lamp` (1A01 4222), `ambient_light_state` +
  `ambient_light_level` (1A01 410B), `front_drive_engaged` (1631 E307 — per-motor engagement, drops
  out in Range cruising; deliberately separate from 1637's C-grade `drive_engaged`).
- signals.yaml: module-list widenings from docs evidence — `power_mode`/`odometer` to all 40 answering
  modules (78 labels), `low_volt_rail` +1656, `srs_supply_v` +1316/1317/1344/1672 (the sanctioned
  per-module-housekeeping exception in docs/did.md / docs/did-ledger.md).
- catalogue/dids.yaml (new): DID registry — names/families for the identity and common blocks
  (sources: docs/did-identity.md, docs/findings.md); masked entries are the machine-readable twin of
  MASKED_DIDS (test-enforced). Loader: decode.load_dids().

### Documentation (docs/)

- DID analysis set, restructured from seven process-shaped files into six purpose-shaped ones:
  - did.md — index: state summary, reading order, transfer method + divergence traps, T01–T36 table.
  - did-ledger.md — single source of truth: one section per candidate (T-ids) with verdict, verbatim
    evidence, procedure pointer, entry pointer. Verdicts: 1 confirmable-now (landed as
    `front_drive_engaged`), 7 settle-from-recorded-data, 17 need a session, 5 ruled out on length,
    4 D112 transfers integrated, DD0A/DD01 widening done.
  - did-entries.md — paste-ready signals.yaml drafts per candidate with TODO example slots.
  - did-sessions.md — four confirming-session runbooks (~84 min car time), ordered candidates-per-minute
    (D no-car, B parked, A drive, C charge), with the capture-machine snapshot-diff procedures folded in.
  - did-leads.md: inventory of decodes established in findings/DISCOVERIES but missing from the
    catalogue — catalogue-ready rows, decoder-blocked rows (now unblocked), needs-a-capture rows,
    and the divergence warnings.
  - did-identity.md: ISO 14229-1:2020 names + length verdicts for the 39 identity DIDs; finds F12E/F1AE
    are one structure (lengths coupled on every module) and flags F18C/F192/F198 as per-car identifiers.
  - Watch-syntax note: two-colon watch specs (e.g. `1631:D003,1637:D003`) crash parse_watch_specs —
    the runbooks use one-module-per-spec form throughout.

### Tool — sweep & identification push (all read-only services; the guard is untouched)

- cli.py: `p4 scan --adaptive-timeout` (opt-in) — after 20 consecutive timeouts the per-DID timeout
  drops to max(0.2, 0.4 x normal), the 50th DID probes at full timeout, any answer restores it; paced
  scans never adapt. Cuts silent-range sweeps ~2.5x.
- cli.py: `p4 whois <addr>` — one-shot unknown-module identification: TesterPresent, usage mode, the
  full (extended) identity set with dids.yaml names and masked values, DTC counts, top-3 similar
  matches, and a scan-fingerprint hint. Car-facing (takes the p4-live lock).
- cli.py: `p4 sweep --plan <file>` — unattended scan plans: slots (module, optional ranges/paced/watch),
  reuses the extracted `scan_core` (cmd_scan delegates), bounded watch passes, progress file in the
  shape web/gen.py already reads, --max-minutes budget and SIGTERM stop between slots.
- cli.py: `p4 similar` — DID-set + length fingerprint matching (Jaccard over did-map.csv);
  `--families` prints look-alike module clusters (union-find over a score threshold), `--refused`
  scores the exists-but-refused NRC 31 sets too (they are family fingerprints). Verified on the real
  map: 1316's best match is 1317 at 1.00, and 1316/1317 + 1670/1676 cluster.
- cli.py: `p4 scandiff` — per-day DID status transitions for a module (newly OK, was-OK-now-refused
  with NRC names, was-OK-now-silent); store.load_scans gained an optional day filter (default
  behaviour unchanged).
- cli.py: `p4 dtcdiff` — stored-DTC sets between run days per module (new/gone/unchanged).
- cli.py: `p4 ranges` — suggested --ranges specs from answered DIDs, with DEFAULT_RANGES coverage per
  module and a --all union with a --min-modules threshold; lossless (singletons included).
- cli.py: `strings` upgrades — identity DIDs included under masking (only masked DIDs skipped),
  UTF-16LE detection (lanes tested on raw and stripped payloads so padding cannot shift them), and
  ASCII-hex-wrapped text unwrapping. Existing thresholds and masking unchanged.
- store.py: load_scans results cached against scan-file mtimes (root/target/day-scoped; appends
  invalidate) — strings/known/similar/scandiff no longer re-read every run file per call.
- p4 wrapper: offline list gained didmap, similar, scandiff, dtcdiff, ranges (whois/sweep take the
  lock); README command table updated.

### Verification

- Test suite grew 541 -> 587 through the session; every catalogue example decodes (the tests caught
  a YAML no/yes-as-boolean bug in the first front_drive_engaged draft, and an over-eager UTF-16
  lane strip during the review round); prepublish-check OK; sim-asserted read-only invariant holds
  for every new car-facing command.
