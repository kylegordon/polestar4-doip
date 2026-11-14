# Public GitHub Pages site: design

Status: Phase 1 implemented (builder `tool/p4doip/site/`, workflow `.github/workflows/pages.yml`). Section 8 (panel review) overrides the earlier sections where they differ; paths such as `site/build.py` below are the pre-panel plan.

Owner decisions: session dates appear on the site as month and year only; Phase 1 = Start here, Hazards, Signals, Findings, Contribute (with issue templates) and a Glossary; Modules and Discoveries pages are Phase 2; URL `kylegordon.github.io/polestar4-doip`; the owner is named by GitHub handle only. Action pinning: full commit SHAs. Local build: from tracked files (`git ls-files`, or a `git archive` export with a manifest).

Open decisions were marked **[DECISION n]** and collected in section 7.

## 1. Goals and audience

**Audience**: other Polestar 4 owners (read, compare with their own car) and people who could run a scan and contribute (issues/PRs). Secondary: people researching UDS/DoIP on Geely/Volvo-platform cars.

**Goals**
- Make the discoveries readable without cloning the repo: what each module is, which signals are decoded and how sure we are, what not to read.
- Lower the barrier to contributing: how to scan safely, what to send back, how it is checked.
- Show, not just tell: two visual demos (headlamp matrix replay, battery cell view) built from a sanitised sample.

**Shows**

| Section | Source (already public) |
|---|---|
| Discovery log | `DISCOVERIES.md` |
| Signal catalogue (search, filter by module and C/P) | `catalogue/signals.yaml`, `catalogue/dids.yaml` |
| Module map with coverage bars | `catalogue/modules.yaml`, `docs/did-map.csv` |
| Hazards ("never read these") | `catalogue/hazards.yaml` |
| Findings per module | `docs/findings.md`, `docs/modules.md` |
| Scan your own car / contribute | `README.md`, hazard list, issue templates |
| Demos | committed sanitised demo dataset (section 2) |

Non-goals: live data, anything per-car, a replacement for the repo (every page links to the source file on GitHub).

## 2. Data sources and the anonymisation boundary

### 2.1 The rule

The public build reads **only files tracked in git**: `catalogue/`, `docs/`, `DISCOVERIES.md`, `README.md`, and a new committed `site/demo/` directory. It never opens `runs/`, `local/`, `captures/`, `external/` or `NEXT.md`. Those are git-ignored, so they do not exist in a CI checkout: a build that accidentally reached for them would fail rather than leak. A test also asserts the builder's code does not reference those paths (section 2.4).

Everything in the first release (no demos) is already public, so it adds no new disclosure. Only the demo dataset adds new data, and it is the only part needing an export script.

### 2.2 Demo dataset: allowlist export from `runs/`

Script: `scripts/export-demo.py`, run **by the owner on the capture machine** (Docker, like everything else), output committed under `site/demo/`. It is the only code that reads `runs/` for publication, and it is never run in CI.

Design principle: **allowlist, not blocklist.** The export emits only the DID/field combinations named in a committed spec, `site/demo-spec.yaml`. Anything not in the spec cannot appear, so a new sensitive DID cannot leak by default. The blocklist below is a second, independent gate.

Spec (initial): 
- Headlamp: `1BB3:7022` and `1BB4:7022` (32 brightness bytes each), `1A01:42E7` beam, `1631:D003` or `1601:E36E` speed.
- Battery: `1635:DA31` cell-group voltages, `1635:EE83` temperatures, `1635:4801` SoC, `1635:4802` current. **[DECISION 1]** whether to include pack current/SoC/pack voltage at all (they say little but are not needed for a cell-balance view; default: cell voltages and temperatures only).

Transformations, in order:
1. **Select** one short window per demo (e.g. 2-3 minutes) from a named watch log; the spec names the log and window by relative offsets, not by trusting arbitrary content.
2. **Drop** by rule (also enforced as a final check on output, see 2.3):
   - GPS and anything position-like: `1011:FD50` and all of module `1011` (telematics: SIM, modem, phone numbers, server names, date-time). No `1011` DID is ever allowlisted.
   - Any DID in `privacy.MASKED_DIDS` (`F190`, `F18C`, `F192`, `F198`) on any module.
   - Any record whose value contains a VIN-like string in plain, UTF-16LE/BE or hex-wrapped form (reuse `privacy.VIN_LIKE`, `readable_runs`), and any value matching `LONG_NUMBER`, `EMAIL`, `PHONE` (ICCID/IMEI/serials).
   - TPMS sensor IDs (`1A01:281F`) and any other tyre-sensor identity.
   - Odometer (`DD01`) and the free-running clock (`DD00`): odometer plus a date is a fingerprint. Not needed by any demo.
   - Home or destination, route, speed-trace-over-time that would reveal a recognisable route. The speed series is kept only for the matrix replay and is cropped to the window, no distance integral is exported.
   - Anything not in the allowlist.
3. **Relative clock**: timestamps become seconds from window start (`t: 0.0, 0.5, ...`). No absolute date or time of day, no timezone, no run-day name. Source log names (`2026-11-14/watch-x.log`) are not written; the output carries a generic id (`matrix-parked-1`).
4. **Coarsen where cheap**: round times to 0.1 s; battery temperatures keep 0.1 C; voltages stay in mV (needed for the demo). **[DECISION 2]** whether to also add small random jitter to the matrix/battery values. Recommendation: no jitter, it would misstate what the car reported; the allowlist already removes the identifying fields.
5. **Output**: one JSON file per demo (`site/demo/matrix-parked.json`, `matrix-drive.json`, `battery.json`), each with a header: `schema`, `source: "single UK Polestar 4, release 4.2.11"` (already public in `docs/findings.md`), `window_s`, `generated_by: export-demo.py`, **no** generation date. Total size target under 100 KB.

**Content judgement stays with the owner**: the export prints a one-screen summary (DIDs, counts, value ranges, window length) and writes to `site/demo/`; the owner reads the JSON diff before `git add`. The export script never commits.

### 2.3 Enforcement

1. **`scripts/prepublish-check.sh`** already scans the index and history for VINs, ICCIDs, IMEIs, phone numbers, home paths. `site/demo/*.json` is text and tracked, so it is covered automatically. Add: a path check that `site/demo/` contains only files named in `site/demo-spec.yaml`, and a check that no tracked file under `site/` contains an absolute ISO date or `HH:MM:SS` time (regex), except `site/content/` copied pages that already carry dates (the discovery log is dated by design; see 2.5).
2. **`tool/tests/test_demo_export.py`** (new, runs in the existing pytest CI step):
   - fixture `runs/` with planted VINs (plain, UTF-16, hex-wrapped), a masked DID, `1011:FD50`, `1A01:281F`, an ICCID-like number, odometer; the export must produce none of them, and must fail (non-zero exit, no output written) if any appears in output.
   - allowlist: a DID not in the spec never appears even if present in the fixture.
   - times: output has no absolute timestamps.
   - the committed `site/demo/*.json` passes the same validator (`export-demo.py --check-committed`), so a hand edit that adds a field fails CI.
3. **Output validator** is one function (`validate_demo(obj)`) used by both the export and the test: rejects unknown keys, DIDs outside the allowlist, any string matching `privacy.mask()` changes, any numeric key that looks like an epoch.
4. **Builder test** (`test_site_build.py`): builds the site from a fixture tree with `runs/` and `local/` present and poisoned with a canary string; asserts the canary is absent from output and that the builder opens no path under those directories (patched `open`/`glob` recording paths).
5. **Output scan in CI**: after build, run the prepublish patterns (`git grep` equivalent via `grep -rEn`) over `_site/` and fail the deploy on a hit. This catches content that arrives via a template or a transform rather than a tracked file.

### 2.4 Why nothing live or location-revealing is published

- No `runs/`, `local/` reads, no raw watch logs, no live endpoint: the site is static and built from committed files only.
- GPS, telematics, identity DIDs, TPMS IDs, odometer and absolute time are excluded by allowlist, then again by blocklist, then again by pattern scan of the output.
- The existing private status site (`web/`) keeps its "private" banner and is not part of the Pages build.

### 2.5 Existing published content

The committed docs already contain absolute dates (`DISCOVERIES.md` entries, "2026-11-14 parked test") and car facts (market, release, colour-free). The site republishes them as they are; it adds no new disclosure. Anything the owner now regards as too identifying in those files is a repo decision, not a site decision (fix the source file). **[DECISION 3]** whether the public site should strip or generalise session dates in the discovery log (default: keep, they are the project's history and are already public in the repo and releases).

## 3. Build and deploy

### 3.1 Generator

Recommendation: a **new, separate builder** `site/build.py` (Python, stdlib plus `PyYAML` and `markdown-it-py` or `markdown`; same deps style as existing tooling, run in Docker), plain HTML/CSS/JS output, **no framework, no bundler**. Justification: content is a few dozen pages, almost all generated from YAML and Markdown; JS is needed only for search/filter and the two demos, and fits in a couple of small hand-written files.

Not reusing `web/gen.py` as the base: it is 486 lines welded to `runs/`, `local/`, an auto-refresh loop and raw rendering, and its safety property is "private by default"; the public builder's property is "reads only committed inputs". A refactor of gen.py into a shared library would make every future gen.py edit a possible public-site change.

Shared code, by extraction not by import of `web/gen.py`:
- `tool/p4doip/privacy.py` is already shared; the public build uses `mask()` and `VIN_LIKE` as a last-line filter on every rendered string.
- New `site/render.py` module for pure helpers copied over from gen.py once and then diverged on purpose: the CSS tokens (light/dark), `coverage_bar()`, table rendering, page shell. If duplication hurts later, move the helpers into `tool/p4doip/render.py` and let both import it, **only pure functions with no filesystem access**. Do not do this in release 1.
- Matrix and battery JS: the demo pages take their drawing code from `web/matrix.html` (grid of 2x16 segments, colour scale) and `gen.py battery()` (cell box with bar), re-written to read `site/demo/*.json` instead of the live endpoint. The private pages are not modified.

The builder takes an explicit `--root` and an allowlist of input paths (`INPUTS = [...]` constants). It refuses to run if the root contains `runs/` or `local/` and the flag `--allow-private-dirs` is not given (a dev machine has them; CI does not). On a dev machine the builder still never reads them; the refusal is a tripwire. Simplest option for the owner: build in Docker with only tracked files mounted (`git archive HEAD | docker ...`). **[DECISION 4]** whether to document `git archive` as the supported local build (recommended, makes local == CI) or allow building from the working tree.

### 3.2 Where output lives

Built to `_site/` in CI, uploaded as a Pages artifact, **never committed**. `_site/` and `site/dist/` go in `.gitignore`. Source inputs live in `site/`:

```
site/
  build.py render.py
  templates/*.html       (page shell, partials)
  static/site.css site.js search.js matrix.js battery.js
  demo-spec.yaml
  demo/*.json            (committed, sanitised)
  README.md              (how to build, how the demo is made)
```

### 3.3 Workflow

New `.github/workflows/pages.yml`, separate from `ci.yml`:

- Trigger: `push` to `main` with `paths:` filtered to `catalogue/**`, `docs/**`, `DISCOVERIES.md`, `README.md`, `site/**`, `tool/p4doip/privacy.py`, and `workflow_dispatch`. No `pull_request` deploy; **[DECISION 5]** optionally build (no deploy) on PRs touching `site/**` to catch breakage (cheap, recommended).
- Permissions: `contents: read`, `pages: write`, `id-token: write`.
- Gate: `needs` a successful `ci.yml` on the same commit (use `workflow_run` on ci, or run `scripts/prepublish-check.sh` as the first step of the pages job, which is the simpler and self-contained option, recommended).
- Steps: checkout (`fetch-depth: 0` for the history check) -> `scripts/prepublish-check.sh` -> Python 3.12 + pip cache -> build -> output scan (2.3 #5) -> link check (3.4) -> `actions/upload-pages-artifact` -> `actions/deploy-pages` with environment `github-pages`.
- Pin actions to major versions as `ci.yml` does (or SHAs; **[DECISION 6]** pin to SHAs for the deploy job since it holds `pages: write`).
- Repo settings (owner, one-off, outside this design's scope to change): Pages source = "GitHub Actions". No branch to publish, no `gh-pages` branch.
- Concurrency group `pages`, `cancel-in-progress: false`.

### 3.4 Link checking

Internal links: the builder resolves every link it emits and fails on a miss (anchors, page names, GitHub source links are generated from known paths). External links: a weekly scheduled workflow with `lychee` or a small `urllib` check, non-blocking (opens a failing run, does not block deploys).

## 4. Pages and layout

Common shell: top bar with site name, nav (Home, Discoveries, Signals, Modules, Hazards, Findings, Demos, Contribute, Repo), light/dark via the same CSS-variable approach as `web/gen.py` (`prefers-color-scheme`, plus a small toggle stored in `localStorage` in a try/catch), single column up to ~1000 px, 16 px gutters, tables collapse to cards under 640 px, no horizontal page scroll, nav becomes a `<details>` menu on phones. Footer on every page: "Data from one UK 2026 Polestar 4; other markets and software versions may differ. Read-only diagnostic reads; see Hazards before scanning" plus the commit short SHA and build time (build time is the site's, not the car's).

Pages (all static HTML, generated):

1. **Home** `index.html`: one paragraph on what the project is, the headline numbers (signals decoded C/P, modules identified, DIDs answered, hazards), latest three discovery entries, two buttons (Scan your car, Browse signals), and the warning box about hazards.
2. **Discoveries** `discoveries/` and `discoveries/<yyyy-mm-dd>.html`: reverse-chronological list from `DISCOVERIES.md` (one page per entry, anchor links, entry headings preserved), summary line per entry (new signals, hazards, corrections).
3. **Signals** `signals.html`: searchable table, client-side JS over an inlined `signals.json` (id, module, DID, name, unit, confidence, example). Filters: module, confidence C/P, free text matching DID/name/id; URL hash keeps the filter so results are shareable. Row expands to encoding, values map, examples. Each signal also gets a static page or anchor so it is findable without JS (progressive enhancement: the table is in the HTML, JS only filters). Link "edit in repo" to the line in `signals.yaml`.
4. **Modules** `modules.html` and `modules/<addr>.html`: grid of cards per address: label, status (confirmed/unverified/unknown), DIDs answered, decoded signals count, and a **discovery coverage bar** with two segments: DIDs answering (from `did-map.csv`) and DIDs decoded (signals). Module page: description from `docs/findings.md` section, signals list, hazards on this module, answering DIDs table from `did-map.csv` (DID, status, length). Cards link to the findings section.
5. **Hazards** `hazards.html`: prominent, red-bordered. Table: DID, severity (block = never read, caution = needs flag), what happened (evidence from `hazards.yaml`), how the tool guards it. A copy-paste block of the exact rule so other tools can adopt it. Linked from Contribute and the footer.
6. **Findings** `findings.html`: `docs/findings.md` rendered with a table of contents by module, anchors per module, leads vs confirmed visually distinguished (taken from the document's own wording, no re-interpretation).
7. **Demos** `demos/` index plus:
   - **Headlamp matrix replay** (`demos/matrix.html`): two lamps, 2x16 segments each, play/pause/scrub over a relative clock, picker for the sample (parked dipped/main, drive), optional speed readout. Caption states what is confirmed (from catalogue) and that the data is a sanitised sample window.
   - **Battery cells** (`demos/battery.html`): cell-group grid with min/max/mean/spread, bars relative to lowest, temperature chips, from `battery.json`. Banner: "sample, relative clock, not live".
8. **Scan your own car** (`scan.html`) and **Contribute** (`contribute.html`): hardware and network setup (OBD DoIP adaptor, link-local address), `./p4 doctor`, read-only guarantee, the hazards box first, the order (`discover`, `identify` with masked output, `scan` with default ranges, `./p4 export`), exactly what to send back (`./p4 export --format json` masked output, never `runs/` raw, never pcaps, never VIN) and a checklist ("remove VIN, serial, SIM, position before posting"), links to issue templates and PR guide. **[DECISION 7]** whether to add issue templates ("my car scan results", "new signal observation", "correction") to `.github/ISSUE_TEMPLATE/` as part of the first release (recommended: yes, they are the contribution funnel).
9. **About** (`about.html`, short): scope (one UK car), method, confidence C/P definitions, licence (MIT), and a privacy statement for the site (static, no analytics, no cookies).

Search: the signal filter on `signals.html` plus a site-wide JSON index (`search-index.json`, titles and headings only) for a header search box in a later phase; no external search service.

## 5. Risks and handling

| Risk | Handling |
|---|---|
| Privacy regression in demo data (new field, new DID in a watch log) | Allowlist spec; blocklist; output validator; planted-identifier tests; prepublish patterns over `_site/`; owner reads the JSON diff before commit; exporter never commits |
| Builder reads `runs/` or `local/` by mistake | CI checkout does not contain them; builder tripwire; canary test; `git archive` local builds |
| Private pages or private notes republished through `docs/` (e.g. a doc that quotes `local/` content) | Pages renders only the named files; `prepublish-check.sh` already guards the index; output scan |
| Stale content (docs updated, site not) | Build is on every relevant push to `main`; site never has its own copy of content; footer shows commit SHA; counts are computed at build |
| Site and catalogue disagree (e.g. a signal removed) | Signal pages generated from YAML each build; unknown module/hazard references fail the build |
| Hazard information not prominent or out of date | Hazards page generated from `hazards.yaml`; red banner on Scan and Home; test that every hazard in the YAML appears in the built page |
| Someone follows the scan guide and damages something | Read-only tool guard already exists; guide leads with hazards, `doctor`, "stop if a module stops answering", no writes ever; disclaimer in footer and About |
| CI cost / minutes | Python build is seconds; paths-filtered trigger; pip cache; no image build in the pages job; `concurrency` prevents pile-up |
| Broken links | Internal check blocks deploy; weekly external check non-blocking |
| Pages deploy exposes something the repo did not (e.g. derived data) | Deploy only from `_site/` produced by the gated job; the same patterns as the commit gate |
| Accessibility and phone use | Semantic HTML, table-to-card layout, keyboard-operable filters and sliders, colour not the only signal (C/P labelled in text), contrast checked in both themes |
| Licence: `external/` content (OBDb, CC BY-SA 4.0) | Not in the repo and not referenced as content on the site; links to github.com/OBDb only |
| Over-claiming | Confidence labels on every signal; "one UK car" footer; leads are not shown as findings |

### Out of scope

- Any live or near-live data, telemetry upload, accounts, or a way to submit scans through the site (contributions go through GitHub issues/PRs).
- Publishing raw `runs/`, DID value dumps, `did-map.csv` values beyond what is already committed, or full watch logs.
- Per-car or per-VIN features, a car comparison database, a decoder that accepts pasted data.
- Analytics, cookies, comments, third-party scripts or fonts.
- Replacing or changing the private status site (`web/`).
- Writing to the car, anything beyond UDS reads, and any security-access or session-control guidance.
- A custom domain, a CMS or a JS framework (revisit only if the site grows past what plain files can manage).

## 6. Phased plan

**Phase 0 (30 min, owner)**: confirm decisions 1-7; set repo Pages source to "GitHub Actions".

**Phase 1: smallest useful release (no demo data, no new disclosure)**
- `site/build.py` with the shell and CSS (light/dark, responsive), Markdown rendering for `DISCOVERIES.md`, `docs/findings.md`.
- Pages: Home, Discoveries, Findings, Hazards, Contribute/Scan (from README), About.
- Signals page with client-side filter; Modules page with cards and coverage bars from `did-map.csv`.
- `pages.yml` with prepublish gate, build, output scan, internal link check, deploy.
- Tests: builder canary/tripwire test, hazards-on-page test, signals-count test.
- Update `CLAUDE.md`/README/`.gitignore` in the same PR (the instruction files are load-bearing).

**Phase 2: contribution funnel**
- Issue templates, a "what to send back" checklist, per-module pages with answering-DID tables.
- Weekly external link check. PR build-without-deploy.

**Phase 3: demos**
- `scripts/export-demo.py`, `site/demo-spec.yaml`, validator and tests, committed `site/demo/*.json`.
- Matrix replay page, then the battery page (one PR each, owner reviews each JSON diff).
- Extend `prepublish-check.sh` with the demo-dir and absolute-time checks.

**Phase 4: polish (only if wanted)**
- Site-wide search index, per-signal permalinks, a changelog feed (Atom) generated from `DISCOVERIES.md`, OpenGraph card, a "signals by confidence over time" chart from the release log.

Each phase is its own branch and PR. Each PR goes through the standard review (code-reviewer, silent-failure-hunter, pr-test-analyzer, Copilot CLI) before push.

## 7. Open decisions for the owner

1. **Battery demo scope**: cell voltages and temperatures only (recommended), or also SoC/current/pack voltage.
2. **Jitter on demo values**: no (recommended), or small random jitter.
3. **Session dates in the discovery log**: keep as in the repo (recommended), or strip/generalise on the site.
4. **Local build method**: `git archive HEAD` in Docker (recommended) or the working tree with the tripwire.
5. **PR builds**: build-only check on PRs touching `site/**` (recommended) or none.
6. **Action pinning**: major versions (matches `ci.yml`) or SHAs for the deploy job (recommended given `pages: write`).
7. **Issue templates** in Phase 1/2 (recommended) or leave contribution to free-form issues.
8. **Site name and URL**: default `kylegordon.github.io/polestar4-doip`; custom domain out of scope unless you want one.
9. **Branding/attribution**: how the site refers to you (GitHub handle only, recommended, no email or real name beyond what the repo already shows).
10. **Third-party tool names**: `CLAUDE.md` forbids naming any third-party diagnostic tool in commits; assumed to apply to the site too, so the builder's output scan includes that pattern from `prepublish-check.sh` (confirm).

## 8. Note on review

Panel run 2026-11-14 (architect, technical writer, tester, code reviewer). Agreed changes, to fold in before Phase 1:
- Build only from the git-tracked file list (git archive / ls-files, one read_input gate); drop the extra tripwire/canary layers except one test.
- Workflow: build job contents:read (prepublish, build, output scan, upload); deploy job pages:write only. SHA-pin every action, Dependabot for actions, pin Python deps. Deploy also gated on the test suite, not prepublish alone.
- One shared pattern file for prepublish-check.sh and the site output scan; plus privacy.mask over every rendered string as a fail gate.
- Builder code under tool/p4doip/site + tool/tests (lint, mypy, coverage apply); reuse decode/hazards loaders; extract pure helpers (e, coverage_bar, CSS) into tool/p4doip/render.py shared with gen.py.
- Plain-English first: Start here page, glossary, Confirmed/Provisional/Unconfirmed labels, hazards with recovery steps, scan guide with prerequisites (Linux, Docker, terminal) and stop-if lines, version/market banner, a no-scan route for owners.
- Owner reads the rendered site once before the first deploy (free-text docs are the real leak surface).
- Phase 3 demos: strict per-DID typed schema (length, range), bounded windows; defer the rest.
Differences: tester and code reviewer want workflow_run/CI gating; architect prefers running checks inside the pages job (chosen: run pytest + prepublish in the build job). Writer moves issue templates into Phase 1; code reviewer defers them (chosen: include, they are small and the funnel is the point).
