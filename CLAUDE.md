# Polestar 4 DoIP: working notes for Claude

Read `README.md` (tool, hazards, commands), `docs/did.md` (DID backlog) and `CHANGELOG.md` first.

- Only `./p4` talks to the car. No raw sockets, no ad hoc scripts against the gateway. The read-only guard
  (`ALLOWED_SIDS` in `tool/p4doip/client.py`, hazards in `catalogue/hazards.yaml`) runs from the working
  tree, so treat any edit under `tool/` or `catalogue/hazards.yaml` as a change to what reaches the car.
- Hazards: never read `1301:EE13` or `1301:EE14` (blocked); `1601:D928`-`D92C` are caution (needs `--allow-caution` or
  `--paced`). Add new hazards to `catalogue/hazards.yaml` with the evidence, not to code.
- The gateway takes one tester. Car-facing commands share the `p4-live` container name; `docker stop p4-live`
  frees it (and ends any running watch).
- Split of work: the main session runs `./p4`, decodes signals, sets C/P confidence and edits `catalogue/`,
  `docs/`, `DISCOVERIES.md` and `CHANGELOG.md`. The `p4-analyst` subagent (Haiku, `.claude/agents/`) does
  offline work only: web research on `./p4 strings` output, summaries of `./p4 correlate`, module note
  drafts. Check its claims against the raw `runs/` records before anything lands in `catalogue/`.
- Evidence: `runs/` is the source of truth; `docs/did-map.csv` is generated with `./p4 didmap`. Do not
  hand-edit either. A C signal needs the same change twice, both directions, with the action in
  `local/session-log.md`; one pass is P.
- DISCOVERIES.md is the project's purpose: any commit that adds or changes what we know about the car
  (catalogue signals or confidence, hazards, findings, corrections) adds or updates the matching
  DISCOVERIES.md entry in the same commit. One entry per session or release; update today's entry
  rather than starting a second one.
- Before every push: `scripts/prepublish-check.sh` (run it after `git add`: it checks the index and
  history, not the working tree), the tests (`./p4 test`, or `pytest tool/tests` on a
  host) and, after code changes, `ruff check tool/p4doip web scripts`, `mypy tool/p4doip`,
  `shellcheck p4 scripts/*.sh web/start.sh`. CI runs all of them plus the image build.
- Never commit `local/`, `runs/`, `captures/`, `external/` or `NEXT.md`, the VIN, or the name of any
  third-party diagnostic tool.
- Commit straight to `main`, one coherent change at a time; stage the whole tree (`git add -A`) so a docs
  migration cannot leave replacements untracked.
- Two sites. `web/` is the PRIVATE status site (raw `runs/`/`local/` data, GPS, VIN-bearing records): trusted
  local network only, never published or port-forwarded. The PUBLIC GitHub Pages site (builder under
  `tool/p4doip/site/`, design in `docs/site-design.md`) is anonymised:
  - it reads only git-tracked files, through one gated reader; never `runs/`, `local/`, `captures/`,
    `external/` or `NEXT.md`, and no live data;
  - never publish GPS (`1011:FD50` or anything position-like), VIN or serials (`MASKED_DIDS` or embedded
    in other DIDs, plain, UTF-16 or hex-wrapped), ICCID/IMEI, TPMS sensor IDs (`1A01:281F`), home or
    destination, number plates, names, or exact session dates (month and year only on the site);
  - the build fails if any rendered string would be changed by `privacy.mask`, or matches the shared
    pattern file used by `scripts/prepublish-check.sh`;
  - plain English for owners: Confirmed / Provisional / Unconfirmed labels, hazards with recovery steps,
    an honest scan guide (Linux, Docker, terminal) with stop-if lines;
  - the owner reads the rendered site before the first deploy and before any new data type is published
    (demo data needs a strict per-DID schema: fixed length, numeric range, bounded window, relative time);
  - the Pages workflow: build job `contents: read` (tests, prepublish, build, output scan, upload), deploy
    job alone has `pages: write`; every action SHA-pinned; Python deps pinned.
- Hands-on car sessions: before proposing a test, check `local/session-log.md` and `runs/*/snap-*` and say
  when it last ran and what it found; a test that found nothing is a retest, not new. One simple step at a
  time; if the car cuts a test short (auto-P, sleep), offer to redo it at once. When a candidate is one or
  two passes from C, go straight into the extra passes. Never suggest ending the session.
