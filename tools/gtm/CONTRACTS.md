# GTM Wave-2 interface contracts (index)

**Purpose.** These contracts are the one interface specification that every Wave-2 work package (WP)
builds from without talking to the others. If two WPs touch the same file, record, command or env
var, its exact shape is written here. Implementers code to the contracts, write their own tests
against the example records in them, and never invent a field, path, flag or exit code that is not
listed. The contracts fix shapes only and add no policy. Every choice the plan left open is marked
**DECIDED HERE** and indexed in `contracts/08_seats_wps.md` Appendix B. Every conflict between the
plan and itself or the committed code is listed in `contracts/08_seats_wps.md` Appendix C. The full
statement of purpose, source of truth and already-built modules is the preamble of
`contracts/00_global_paths.md`.

The contracts were split on 2026-09-27 from one 3,870-line document into the section files below.
The meaning is unchanged, and so is every section number. A reference into another file names that
file, e.g. `03_schemas.md §3.4.4`. A bare `§N` points either to the same file or, as in the original
document, to the plan: §10 and above always mean the plan, and so does any reference written
"plan §…".

## Precedence

When two sources conflict, the higher one wins:

1. **Plan §20**, the operator rulings of 2026-09-27, including §20.9 v15 and §20.13–§20.17, in
   `/Users/x/.claude/plans/gtm_autonomous_department_plan.md`.
2. **These contracts**: the section files in `contracts/`.
3. **Everything else**: other plan sections, primers, prompts, READMEs, code comments and notes.

## Files

| File | Sections | Lines |
|---|---|---|
| [`contracts/00_global_paths.md`](contracts/00_global_paths.md) | Preamble; §0 Global rules (every WP); §1 Paths, environment, test isolation | 341 |
| [`contracts/02_act.md`](contracts/02_act.md) | §2 The act package (WP-A1 core, WP-A2 execution) | 748 |
| [`contracts/03_schemas.md`](contracts/03_schemas.md) | §3 Data schemas | 1098 |
| [`contracts/04_hooks.md`](contracts/04_hooks.md) | §4 Hook contracts | 536 |
| [`contracts/05_approver.md`](contracts/05_approver.md) | §5 Approver protocol (WP-C ↔ WP-A2 ↔ WP-D) | 178 |
| [`contracts/06_connectors.md`](contracts/06_connectors.md) | §6 Connector interface (WP-L ↔ WP-A2) | 198 |
| [`contracts/07_notices_schedules.md`](contracts/07_notices_schedules.md) | §7 Notices, runners, schedules (WP-D ↔ WP-K; also A2, B2) | 332 |
| [`contracts/08_seats_wps.md`](contracts/08_seats_wps.md) | §8 Seat conventions; §9 WP dependency table; Appendix A minimal valid pack fixture; Appendix B every DECIDED HERE item; Appendix C conflicts found and coordinator follow-ups | 480 |
| [`contracts/OPEN_FINDINGS.md`](contracts/OPEN_FINDINGS.md) | Every finding from the last contracts review round (round 4), tagged by section file; CROSS marks a finding that spans files | 633 |

There is no `01_` file, because §0 and §1 share `00_global_paths.md`.
