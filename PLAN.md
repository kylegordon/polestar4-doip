# Discovery method (drafted 2026-11-10)

**Status:** historical method, kept because it still describes how a module earns a label. Current
candidate work is in [`docs/did.md`](docs/did.md) (ledger, sessions, entries, leads). Session runbooks are
in [`docs/did-sessions.md`](docs/did-sessions.md). Commands are in `README.md`.

Goal: turn "a module answers at this address" into "this is what it is and these are its signals",
using reads only.

## How a module gets identified

Evidence, cheapest first. Stop as soon as the role is clear.

1. **Address.** Neighbours share a domain: 13xx driver assistance, 16xx chassis/propulsion, 1Axx body, 1Bxx lamps.
2. **Identity** (`identify`): hardware/software part numbers and serials. Same hardware part with adjacent serials = a left/right pair. Same software as a known module = a second unit of it.
3. **Fault codes** (`dtc`): the stored and supported DTC lists say what the module monitors, which usually names it.
4. **DID map** (`scan`): which DIDs answer, and which known module's map it resembles (`--like`, `similar`).
5. **Behaviour** (`watch`, `read --repeat`, or `snapshot` + `diff`): change one thing on the car, see which values move. This is the only step that makes a signal "confirmed".

Signal confidence: **C** needs the same change seen at least twice, in both directions, with the action
noted in `local/session-log.md`. Anything less is **P**.

## Stimuli per hypothesis

| Module | Guess | Why | Try |
|---|---|---|---|
| 1316 / 1317 | corner radars or other left/right sensor pair | same hardware part, serials 7 apart, next to front radar 1344 | walk round the car; stand at each corner 10 s; select reverse; open a door on each side |
| 1676 | second steering unit | same software part numbers and placeholder serial as PSCM 1670 | scan 1670 first, then `./p4 scan 1676 --like 1670`; `./p4 watch 1670 1676` and turn the wheel lock to lock |
| 1675 | chassis, unknown | sits between steering addresses | steering, gear selector, brake pedal, drive mode; it answers OBD PID 0D (`F40D`) |
| 1656 | charging/power related | sits beside charger 1650 | plug in and charge; switch on heavy 12 V loads; climate on/off |
| 1251 | head-up display | usual label for that address; answers a physical address scan only | HUD on/off, brightness, height |

For a module with a large DID map, or slow effects, use `snapshot before` → action → `snapshot after` → `diff` instead of `watch`.

## Limits

- One tester at a time. Stop a `watch` with Ctrl-C. If a live command says the name `p4-live` is in use, run `docker stop p4-live`. Do this before another diagnostic tool connects, and disconnect that tool before any live `p4` command.
- A pass over a whole module takes seconds, so fast events (blinks, short presses) need `./p4 watch ADDR:DID,DID --interval 0.1 --baseline 0`.
- `watch` hides whatever changes during its baseline for the rest of the run (still in the log). If the thing you are testing moves during the baseline, restart the watch.
- A scan that found nothing in the default ranges has not proved the module empty: the ranges come from where other modules answered.
- Hazards live in `catalogue/hazards.yaml` (blocked or cautioned), not in prose only. Read it before a broad scan.
- pcaps and identity reads contain the VIN.

## Parked idea

A voice channel for drives (hands-free marks and spoken replies) is described in the 2026-11-11 session
notes. It is not implemented; `mark` plus the status site's timeline covers the same need more simply.
