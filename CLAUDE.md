# Polestar 4 DoIP: working notes for Claude

Read README.md (tool, hazards) and PLAN.md (method) first.

- Only `./p4` talks to the car. No raw sockets, no ad hoc scripts against the gateway. The read-only guard (`ALLOWED_SIDS`, `BLOCKED_READS` in `tool/p4doip/client.py`) runs from the working tree, so treat any edit under `tool/` as a change to what reaches the car.
- The gateway takes one tester. Car-facing commands share the `p4-live` container name; `docker stop p4-live` frees it (and ends any running watch).
- Split of work: the main session runs `./p4`, decodes signals, sets C/P confidence and edits `catalogue/`, `docs/` and `DISCOVERIES.md`. The `p4-analyst` subagent (Haiku, `.claude/agents/`) does offline work only: web research on `./p4 strings` output, summaries of `./p4 correlate`, module note drafts. Check its claims against the raw `runs/` records before anything lands in `catalogue/`.
- Commit straight to `main`. Run `scripts/prepublish-check.sh` and `./p4 test` before every push.
- Never commit `local/`, `runs/`, `captures/`, `external/` or `NEXT.md`, the VIN, or the name of any third-party diagnostic tool.
