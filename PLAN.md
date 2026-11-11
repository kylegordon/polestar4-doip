# Discovery plan (drafted 2026-11-10; not yet run)

Goal: turn "a module answers at this address" into "this is what it is and these are its signals", using reads only. Commands are in `README.md`.

## How a module gets identified

Evidence, cheapest first. Stop as soon as the role is clear.

1. **Address.** Neighbours share a domain: 13xx driver assistance, 16xx chassis/propulsion, 1Axx body, 1Bxx lamps.
2. **Identity** (`identify`): hardware/software part numbers and serials. Same hardware part with adjacent serials = a left/right pair. Same software as a known module = a second unit of it.
3. **Fault codes** (`dtc`): the stored and supported DTC lists say what the module monitors, which usually names it.
4. **DID map** (`scan`): which DIDs answer, and which known module's map it resembles (`--like`).
5. **Behaviour** (`watch`, or `snapshot` + `diff`): change one thing on the car, see which values move. This is the only step that makes a signal "confirmed".

Signal confidence: **C** needs the same change seen at least twice, in both directions, with the action noted in `local/session-log.md`. Anything less is **P**.

## Session order

Starting point: 1316, 1317, 1656, 1675 and 1676 have so far answered identity DIDs only, so `watch` shows nothing on them until their scan has found live DIDs.

| Step | Command | Done when | Time |
|---|---|---|---|
| Before the car | `./p4 build` (needs internet); look up the unknown modules' hardware part numbers in public parts catalogues; compare the other diagnostic tool's own captures with `./p4 known all` | image built; any names found noted in `catalogue/modules.yaml` | 15 min |
| 0. Preflight | laptop on charger; other diagnostic tools disconnected; `./p4 test`; start tcpdump (README) in its own terminal; `./p4 mark "session start"` | tests pass, pcap growing | 2 min |
| 1. Census | `./p4 discover` | 43 answering incl. 1251; add anything "not in catalogue" to `catalogue/modules.yaml` as `unknown`; a WARNING line means the run is not reliable | ~3 min |
| 2. Identity and faults | `./p4 identify all` then `./p4 dtc all` | `runs/<date>/identify-*.json` and `dtc-*.jsonl` written; part numbers and fault lists for the unknowns noted in `local/references.md` | ~3 min |
| 3. Map 1316 | `./p4 scan 1316` | ends "N new OK" and `./p4 known 1316 --list` shows DIDs beyond the F1xx/EDxx/DDxx identity ones; if not, see below | ~6 min |
| 4. Map its pair | `./p4 scan 1317 --like 1316` | same DIDs answer on 1317, or the difference is noted | seconds |
| 5. Radar walk | terminal 1: `./p4 watch 1316 1317` and wait for "baseline over" (20 s, nobody near the car). Terminal 2: `./p4 mark "left front door"` at each corner; walk clockwise from the left front door, twice | a CHANGE lines up with the same corner on both laps (signal is C), or two laps with none (radar guess dropped; say so in the module's `note`) | 5 min |
| 6. Other unknowns | `./p4 scan 1656`, `./p4 scan 1675`, `./p4 scan 1670`, `./p4 scan 1676`, `./p4 scan 1251`, then `./p4 watch <addr>` with that module's stimuli (below) | each has one C signal or a note of what was tried | ~8 min each |
| 7. Record | add signals to `catalogue/signals.yaml` with a real example; set the module's `label`, `role`, `status: confirmed`; `./p4 test` | tests pass | as you go |

If a scan finds nothing beyond identity DIDs, run `./p4 scan <addr> --ranges 0000-FFFF` (~45 min; it holds the connection, so nothing else can run) or drop the module. Scans skip DIDs that got a definite answer in any earlier run, so an interrupted one carries on where it stopped, on any day.

## Stimuli per hypothesis

| Module | Guess | Why | Try |
|---|---|---|---|
| 1316 / 1317 | corner radars or other left/right sensor pair | same hardware part, serials 7 apart, next to front radar 1344 | walk round the car; stand at each corner 10 s; select reverse; open a door on each side |
| 1676 | second steering unit | same software part numbers and placeholder serial as PSCM 1670 | scan 1670 first (only 2 DIDs recorded), then `./p4 scan 1676 --like 1670`; `./p4 watch 1670 1676` and turn the wheel lock to lock |
| 1675 | chassis, unknown | sits between steering addresses | steering, gear selector, brake pedal, drive mode |
| 1656 | charging/power related | sits beside charger 1650 | plug in and charge; switch on heavy 12 V loads; climate on/off |
| 1251 | head-up display | usual label for that address; answers a physical address scan only | HUD on/off, brightness, height |

For a module with a large DID map, or slow effects, use `snapshot before` → action → `snapshot after` → `diff` instead of `watch`.

## Ideas not yet tried

- Multi-DID reads to speed up scans: a `22` with several DIDs should answer if any exists, so blocks of 8–16 could be bisected (a full scan in minutes, not 45). The tool refuses multi-DID requests today because it can't split the answer; needs a tool change and a 10-second test at the car first.
- A report that lines up `watch` logs with `marks.jsonl` (value of each DID at each mark).
- `known --names` (labels from `local/` extracts) and a `similar <addr>` command ranking known modules by DID overlap.

- Watch the battery contactor values through the car going to sleep and waking (the tester may keep it awake; test by disconnecting for 10 min and comparing snapshots).
- Find the displayed range and 59 % figure: `snapshot` every module, change the range (climate on/off in dynamic mode), `diff`.
- Check whether IEM 1637 answers the same DIDs on CAN; those could go to OBDb as a normal pull request.

## Backlog from 2026-11-10

Seats (other axes, driver seat 1A27, rear 1A29); lights fully off and matrix dimming (daylight / torch); exact steering scale; left headlamp 43D7 flicker; driver door handle reading `ff` after lock.

## Limits

- One tester at a time. Stop a `watch` with Ctrl-C. If a live command says the name `p4-live` is in use, run `docker stop p4-live`. Do this before another diagnostic tool connects, and disconnect that tool before any live `p4` command.
- A pass over a whole module takes seconds, so fast events (blinks, short presses) need `./p4 watch ADDR:DID,DID --interval 0.1 --baseline 0`.
- `watch` hides whatever changes during its baseline for the rest of the run (still in the log). If the thing you are testing moves during the baseline, restart the watch.
- A scan that found nothing in the default ranges has not proved the module empty: the ranges come from where other modules answered.
- pcaps and identity reads contain the VIN.

## Idea: voice channel for drives (parked 2026-11-11)

Driver calls out events and gets spoken instructions, hands-free. Page on the p4-web container: open mic with voice-activity detection (optional wake word, since it transcribes all car conversation) -> local Whisper container -> utterances appended to a file -> Claude follows the file live (Monitor), marks and checks the log -> replies written to a second file -> page speaks them with browser speechSynthesis (works offline). Few seconds per round trip. Estimate 2-3 h incl. a parked test. Simpler fallback: mark buttons + note box on the page.
