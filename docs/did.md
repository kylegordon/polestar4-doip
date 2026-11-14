# DID analysis: state, method, candidate index

Start here for the DID-decoding work. The transfer workflow is three files keyed by stable candidate ids
(T01-T36): this index (state, method, traps, candidate table), [did-ledger.md](did-ledger.md) (one section
per candidate: verdict, evidence, procedure pointer, entry pointer), [did-sessions.md](did-sessions.md)
(runbooks A-D and the offline settling procedures), [did-entries.md](did-entries.md) (paste-ready
`signals.yaml` drafts). Siblings: [did-leads.md](did-leads.md), [did-identity.md](did-identity.md).

## State

- `docs/did-map.csv`: 4,401 answering module:DID pairs (status ok) across 43 modules — 1,805 distinct DIDs.
- `catalogue/signals.yaml`: 113 decoded signals (105 + the eight catalogue-ready §1 rows landed 2026-11-14).
- Transfer candidates ([did-ledger.md](did-ledger.md) T01-T36): 36 — 0 confirmable-now, 7 settle-from-data
  (T04, T24, T27, T28, T30, T31, T32), 17 needs-session, 5 ruled-out (T23, T25, T26, T29, T33), 7 integrated
  (T02, T08-T11, T35/T36).
- Most candidate rows have paste-ready entry drafts ([did-entries.md](did-entries.md)); the length-ruled-out
  rows have none. T02 was integrated as `front_drive_engaged` on 2026-11-13.
- Next action: run the 7 settle-from-data rows on the capture machine (Session D in
  [did-sessions.md](did-sessions.md)), then the parked Session B.

## Reading order — what do I do next

1. **Ledger**: pick a candidate from [did-ledger.md](did-ledger.md) by verdict — settle-from-data rows need
   no car time; needs-session rows go into the session run order.
2. **Sessions**: [did-sessions.md](did-sessions.md) — run Session D first (0 min car time, highest rate),
   then the car sessions in its run order (D → B → A → C, cheapest candidates per car-minute first).
3. **Entries**: after a candidate's test passes, take its paste-ready draft from
   [did-entries.md](did-entries.md), fill the TODO example raws from the run records, `./p4 test`, and log
   the outcome in `DISCOVERIES.md` / `docs/findings.md` per the session's Follow-up.
4. Outside the transfer workflow: [did-leads.md](did-leads.md) (decodes awaiting publication),
   [did-identity.md](did-identity.md) (identification DIDs).

## Transfer method

Several DIDs answer on more than one module. Where one of those modules already has a decoded signal
([`catalogue/signals.yaml`](../catalogue/signals.yaml)), the same decode can plausibly be transferred to the
others — but only within the same module family, and only ever as a hypothesis until it is confirmed on that
module by its own test. No raw values are invented — every claim cites a line in `findings.md`,
`signals.yaml`, `did-map.csv`, `DISCOVERIES.md`, `modules.md` or `README.md`.

A transfer is presumed valid **within a module family** and presumed invalid across unrelated modules:

- door ↔ door (`1A12`/`1A13`/`1A21`/`1A22`), seat ↔ seat (`1A27`/`1A28`/`1A29`), lamp ↔ lamp (`1BB3`/`1BB4`);
- the steering set `1670`/`1672`/`1676` (same 44-DID set on `1670`/`1676`, `docs/modules.md:33`);
- the drive-unit set `1631`/`1637`/`1601`;
- the brake pair `1601`/`1701` (share 29 DIDs, `docs/modules.md:34`) — but see the traps: shared DIDs between
  these two are not automatically the same signal.

One exception is sanctioned: **per-module housekeeping quantities** transfer across unrelated modules,
because every module reports them about itself — own supply voltage (`D112`, and the `D904` lead,
`docs/findings.md:12`) and the car-wide block (`DD01` odometer, `DD0A` power mode, `docs/findings.md:12`).

Rules for every candidate (each T-section in [did-ledger.md](did-ledger.md)):

- A transfer entry is a **hypothesis**. Until its own test passes on that module, its confidence is at most
  **P**, and it must not be added to `catalogue/signals.yaml` for that module. C still requires the same
  change seen twice in both directions with the action noted (`catalogue/signals.yaml:5`); one pass is not
  confirmation (`docs/findings.md:91`, the confounded parked pedal pass).
- The candidate's answer length in `docs/did-map.csv` must be able to hold the decoded span. A 1-byte answer
  cannot hold a u16/u32 decode: those candidates are listed but marked implausible, and their test is a cheap
  diff expected to rule them out. Where the answer is a longer block, only the first bytes may be compared.
- Worked example of a completed transfer: the mirror DIDs `4051`/`4052`/`4053` were decoded on `1A12` and
  transferred to `1A13`, confirmed by the 2026-11-12 parked fold/unfold test on both sides
  (`catalogue/signals.yaml:61-73`). Every candidate in the ledger needs the equivalent of that one session.
- Hazards apply as everywhere: never read `EE13` on `1301` (`README.md:15`, `docs/findings.md:65`); while
  driving, only passive watches of known DIDs (`README.md:17`).

## Divergence traps: never transfer across these

These are proven cases of the same DID meaning something else per module. They are why the family rule
exists; cite them when rejecting a cross-family transfer.

- `D906` = brake pedal sensor b on `1701` (`catalogue/signals.yaml:195-196`, `docs/findings.md:180`) vs
  tailgate position on `1A15` (`catalogue/signals.yaml:125-126`, `docs/findings.md:219`). It also answers,
  undecoded, on `1601`, `1633`, `1316`/`1317`, `1001`, `1011` and the doors (`docs/did-map.csv:1153`, `:1979`,
  `:983`/`:1019`, `:31`, `:128`, `:3332`/`:3530`/`:3745`/`:3900`).
- `D938` = park-selected flag on `1201` (`catalogue/signals.yaml:180-181`, `docs/findings.md:43`) vs a rolling
  log of window runs on `1A12` (`docs/findings.md:208`; also answers on `1A13`/`1A21`/`1A22`/`1A11`/`1301`/`1601`,
  `docs/did-map.csv:3557`, `:3770`, `:3925`, `:3159`, `:857`, `:1182`).
- `FE08` = four brake-pressure channels on `1701` (`catalogue/signals.yaml:185-192`, `docs/findings.md:180`) vs
  unrelated content on `1023` and `1675` and all four door modules (`docs/did-map.csv:577`, `:2600`, `:3441`,
  `:3625`, `:3829`, `:3984`).
- `D93A` = per-corner damper commands on `1614` (`catalogue/signals.yaml:208-215`, `docs/findings.md:104`) vs
  unrelated content on `1201`, `1675`, `1701`, `1A11` and the doors (`docs/did-map.csv:635`, `:2558`, `:2690`,
  `:3161`, `:3361`).
- `D902` = per-corner ride-height/motion on `1614` (`catalogue/signals.yaml:217-224`, `docs/findings.md:104`)
  vs unrelated content on `1001`, `1011`, `1201`, `1316`/`1317`, `1633` (`docs/did-map.csv:28`, `:124`, `:605`,
  `:982`/`:1018`, `:1977`).
- `D905` = brake pedal sensor a on `1701` (`catalogue/signals.yaml:193-194`, `docs/findings.md:180`) vs
  unrelated content on the doors, `1A15`, `1011`, `1251`, `1670`/`1676`, `1614` (`docs/did-map.csv:3331`,
  `:3657`, `:127`, `:790`, `:2469`, `:1801`).
- `D927`/`D929` = temperature-flap positions on `1A11` (`catalogue/signals.yaml:137-140`,
  `docs/findings.md:200`) vs unrelated content on `1201` and the doors (`docs/did-map.csv:621`, `:623`,
  `:3350`, `:3761`); `D927` is additionally a camera entry on `1301` (`docs/findings.md:64`,
  `docs/did-map.csv:845`).
- Hard rule, not a divergence: `EE13` on `1301` knocks the Mobileye ECU off the network — never read it there,
  and no watch or sweep may reach it (`docs/findings.md:65`, `README.md:15`).

## Candidate table

Verdicts are the audit's ([did-ledger.md](did-ledger.md)); status is the next action. Procedures: Session
D §0-§11 and Sessions A/B/C are in [did-sessions.md](did-sessions.md); drafts in
[did-entries.md](did-entries.md).

| T-id | Candidate | Verdict | Status | Ledger |
|---|---|---|---|---|
| T01 | `D003` -> `1637` rear drive speed | needs-session | Session A (pre-check D10) | [T01](did-ledger.md) |
| T02 | `E307` -> `1631` front drive | integrated | done (P, as `front_drive_engaged`); Session A can make it C | [T02](did-ledger.md) |
| T03 | `E307` -> `1601` brake-side drive flag | needs-session | Session A | [T03](did-ledger.md) |
| T04 | `E319` -> `1631` front drive torque direction | settle-from-data | D10, then land; else Session A | [T04](did-ledger.md) |
| T05 | `E319` -> `1601` brake-side torque direction | needs-session | Session A | [T05](did-ledger.md) |
| T06 | `3019` -> `1670` steering angle | needs-session | Session A (pre-check D10) | [T06](did-ledger.md) |
| T07 | `3019` -> `1676` steering angle | needs-session | Session A (pre-check D10) | [T07](did-ledger.md) |
| T08 | `D112` -> `1316` supply | integrated | done | [T08](did-ledger.md) |
| T09 | `D112` -> `1317` supply | integrated | done | [T09](did-ledger.md) |
| T10 | `D112` -> `1344` supply | integrated | done | [T10](did-ledger.md) |
| T11 | `D112` -> `1672` supply | integrated | done | [T11](did-ledger.md) |
| T12 | `D112` -> `1301` supply | needs-session | Session B3 (pre-check D8) | [T12](did-ledger.md) |
| T13 | `40A3` -> `1A27` seat slide | needs-session | Session B2 (nothing recorded) | [T13](did-ledger.md) |
| T14 | `40A3` -> `1A29` seat slide | needs-session | Session B2 (nothing recorded) | [T14](did-ledger.md) |
| T15 | `40A8` -> `1A27` seat switches | needs-session | Session B2 (nothing recorded) | [T15](did-ledger.md) |
| T16 | `40A8` -> `1A29` seat switches | needs-session | Session B2 (nothing recorded) | [T16](did-ledger.md) |
| T17 | `2B1A` -> `1701` EPB position | needs-session | Session B1 (nothing recorded) | [T17](did-ledger.md) |
| T18 | `2B15` -> `1701` EPB lamp | needs-session | Session B1 (nothing recorded) | [T18](did-ledger.md) |
| T19 | `2B20` -> `1701` EPB counter | needs-session | Session B1 (pre-check D9) | [T19](did-ledger.md) |
| T20 | `EE02` -> `1650` 12 V rail | needs-session | D5 first, else rail-swing pair | [T20](did-ledger.md) |
| T21 | `EE02` -> `1C01` 12 V rail | needs-session | D5 first, else rail-swing pair | [T21](did-ledger.md) |
| T22 | `EE02` -> `1301` 12 V rail | needs-session | D5 first, else rail-swing pair | [T22](did-ledger.md) |
| T23 | `EE02` -> `1601` 12 V rail | ruled-out | closed | [T23](did-ledger.md) |
| T24 | `EE07` -> `1301` outside temp | settle-from-data | D6; else Session C2 | [T24](did-ledger.md) |
| T25 | `EE07` -> `1601` outside temp | ruled-out | closed | [T25](did-ledger.md) |
| T26 | `EE07` -> `1650` outside temp | ruled-out | closed | [T26](did-ledger.md) |
| T27 | `EE71` -> `1635` charge energy | settle-from-data | D4; else Session C1 | [T27](did-ledger.md) |
| T28 | `EE71` -> `1A01` charge energy | settle-from-data | D4; else Session C1 | [T28](did-ledger.md) |
| T29 | `EE72` -> `1635` last-charge power | ruled-out | closed | [T29](did-ledger.md) |
| T30 | `EE72` -> `1A01` last-charge power | settle-from-data | D7; else Session C1 | [T30](did-ledger.md) |
| T31 | `EE13` -> `1650` discharge counter | settle-from-data | D3 | [T31](did-ledger.md) |
| T32 | `EE13` -> `1656` discharge counter | settle-from-data | D3 | [T32](did-ledger.md) |
| T33 | `EE13` -> `1601` discharge counter | ruled-out | closed | [T33](did-ledger.md) |
| T34 | `FE0D` -> `1A13` left mirror fold current | needs-session | Session B2 (pre-check D10) | [T34](did-ledger.md) |
| T35 | `DD0A` power mode -> all 40 modules | integrated | done (widening) | [T35](did-ledger.md) |
| T36 | `DD01` odometer -> all 40 modules | integrated | done (widening) | [T36](did-ledger.md) |
