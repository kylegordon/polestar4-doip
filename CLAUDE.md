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
