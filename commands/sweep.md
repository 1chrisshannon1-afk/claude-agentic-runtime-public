---
description: Manual oversight sweep — the degraded-mode fallback when scheduled jobs are down. Runs the daily pre-steps + one chosen dimension, or "all" for the full rotation.
argument-hint: "[health|logs|cost|consistency|all]"
model: sonnet
---

Run an oversight sweep in this repo, exactly as the scheduled daily job would (this command exists
so the wheel still turns by hand when schedules are down — see
`~/.claude/knowledge/oversight_install.md`).

Argument: `$ARGUMENTS` — one of `health | logs | cost | consistency | all`. Default when omitted:
`health` (the manual run does NOT try to reconstruct the down job's rotation state — it records
which dimension it ran in its own heartbeat's `summary`, and the daily job resumes its own
rotation from its own state when it recovers).

Procedure:
1. Kill-switch check: if `~/.claude/schedules/DISABLED` exists, say so and stop.
2. Budget pre-flight (advisory, not a gate — AA-0002, rationale re-derived 2026-09-01): `python3
   ~/.claude/hooks/agent_budget.py status` — note its `live_leases`/`ceiling`/
   `recommended_additional_slots` fields in the report (there is no `status` key); there is no
   saturation skip here, because the real limit (the account's weekly Anthropic quota) is not
   observable from this script — a lease-based skip gates on the wrong signal regardless of pacer
   state.
3. Fixed pre-steps, always: dispatch the `sentinel` agent for the heartbeat audit + deploy-drift
   poll (it reads the repo dossier at `.claude/oversight/sentinel.md`); then, in THIS session
   (never delegated), run the daily job's pre-step C's eight runtime self-checks, plus the
   mirror-sync status check unique to this manual fallback, plus pre-step D's spend rollup,
   pre-step E's review-attribution audit, and pre-step G's social-queue reload due-check
   (pre-step F, the delivery-speed report, is pre-existing-absent from this manual fallback and
   stays that way — not part of this leg) — any violation line or non-zero exit from any of them is a finding, filed the
   same way as step 5:
   - `python3 ~/.claude/hooks/model_pin_parity.py`
   - `python3 ~/.claude/hooks/bundle_parity.py` — REPORT-ONLY drift guard for
     `runtime_bundle_repo_agnostic_plan.md` (mirrors `schedules/prompts/daily_sweep.txt`'s own
     self-check leg): does everything a bundle agent/primer/skill/command reads or names actually
     ship (primer-shipped, template-present, doc-present, referenced-paths-shipped,
     twin-collision, mirror-readme-count, knowledge-referenced-ships)? Cluster by RULE NAME, not
     by finding line, when filing (see `daily_sweep.txt`'s own bundle_parity leg for the full
     discipline — one issue per rule name, every current line pasted as evidence, `create`'s
     overlap search decides new-vs-comment) — never one issue per finding line. Findings during
     the bundle-plan rollout are expected, not a reason to skip filing.
   - `python3 ~/.claude/hooks/check_safety_core_parity.py < /dev/null` — no exemption remains on
     record as of 2026-09-03 (`block_prod_mutations.py`, `model_pin_gate.py`, and
     `pretooluse_task.py` are all now wired into settings.json's PreToolUse dispatcher closure);
     any violation line here is a finding.
   - `python3 ~/.claude/hooks/heartbeat_audit.py`
   - `python3 ~/.claude/hooks/runtime_mirror_sync.py --status` — the runtime GitHub mirror's
     health. Strictly read-only (no push, no network, not a log line) and safe on any cadence;
     **NEVER run `--sync` here** — that performs a real push. Branch on the leading state token
     (line 1) or the exit code: `OK` (0) silent · `INERT` (5) is a **P1 finding** — a rejected
     config disables the subsystem silently, so it never runs, never blocks, and never logs a
     block; this check is the only thing that can see it · `BLOCKED` (3) — relay `Source HEAD:`
     and every `` - `path` matched `pattern` `` line from `.mirror/BLOCKED.md` verbatim, and
     adjudicate rather than assume: a block is NOT proof of a leak (the first real one was a false
     positive: an unanchored vendor token matching inside an unrelated public domain name), and
     equally the sweep never clears the gate · `DRIFTED` (4) — a watch item, not an alert;
     mirroring rides an ask-gated push, so being behind is often just an unpushed runtime commit.
     Baseline to re-derive, never recite (as of 2026-08-31):
     `grep -c BLOCKED ~/.claude/.mirror/sync.log` vs `grep -c 'sync: pushed' ~/.claude/.mirror/sync.log`.
     Same leg as `sentinel`'s `health` dimension — this is the manual fallback, not a second
     owner; full contract in `~/.claude/docs/subsystems/mirror-sync.md`.
   - `python3 ~/.claude/hooks/validate_agentarch_ledger.py ~/.claude/knowledge/agentarch_recommendations.jsonl` — validates the ledger (field schema, id sequence, status/date/value domains, metric_command guard-legality, live re-score, never-scored grace). A `metric_command` may reference a repo via the symbolic `${REPO:<slug>}` form, resolved at run time against `~/.claude/knowledge/repo_registry.json`; every registered repo's root is automatically an allowed bounds-check root, so no trailing CLI argument is needed for a repo that is already registered — add a new app by editing that registry file, not by passing a root here. A root passed as a trailing CLI argument is only for a genuine one-off root not yet worth registering (mirrors `schedules/prompts/daily_sweep.txt:13`). Such a root (or a registry entry) that is overbroad, nonexistent, or not a real repo checkout (no `.git` entry) is dropped and reported as its own `extra-repo-root-rejected` violation, never silently accepted — a registry entry (never a CLI-passed root) may also be rejected for a fourth reason, checked separately before the other three: a root containing whitespace, which would silently mis-tokenize once substituted into a command string. Non-zero exit is a finding; relay its violation lines verbatim.
   - `python3 ~/.claude/hooks/validate_research_ledger.py ~/.claude/knowledge/research_ledger.jsonl` — validates the research-scout/market-analyst findings ledger (field order/set, RS-#### sequence, target/verdict domains, length caps, and the license-ceiling invariant: no AGPL*/GPL*/LGPL*/SSPL*/NOASSERTION/unknown row may carry `verdict: COPY`). Staleness lines are report-only, never the exit code; non-zero exit is a finding — relay violation lines verbatim (mirrors `schedules/prompts/daily_sweep.txt`; wired 2026-08-31, #4731).
   - `python3 ~/.claude/hooks/agentarch_metric_check.py ~/.claude/knowledge/agentarch_recommendations.jsonl` — the repo-agnosticism regression guard for the same ledger (hardcoded-repo-path / unknown-repo-slug); takes no repo-root arguments (it resolves `${REPO:<slug>}` placeholders itself via `knowledge/repo_registry.json`). Non-zero exit is a finding; relay its violation lines verbatim.
   - `python3 ~/.claude/hooks/doc_citation_check.py` — the file:line citation drift sensor
     (#5843). REPORT-ONLY, always exits 0 here (no `--strict`), so a non-zero exit is a
     broken-check finding, never a citation finding. Cluster findings by rule name like
     `bundle_parity` — at most ONE issue per distinct rule name (`missing-file`,
     `out-of-range`, `empty-target`) per run, never one issue per line.
   - `python3 ~/.claude/hooks/daily_spend_rollup.py` — the daily job's separate pre-step D (mirrors
     `schedules/prompts/daily_sweep.txt:16`), run here too so the manual fallback path also
     contributes to the append-only spend series: aggregates yesterday's (UTC) `spend.jsonl` rows
     by `(agent_type, model)` and appends one line to `daily_rollup.jsonl`; idempotent (a rerun for
     an already-recorded date is a clean no-op). Non-zero exit is a finding (a genuine read/write
     failure only — an absent `spend.jsonl` exits 0, not a finding). This same invocation also runs
     an attribution-compaction pass (F1, 2026-09-01 agentic-systems-architect audit):
     `spend_attribution.py`'s own `enrich --out` recovery, writing recovered agent_type/model
     identities for the CURRENT spend.jsonl window to the sidecar
     `~/.claude/.agent_budget/spend_enriched.jsonl` (never mutating `spend.jsonl` itself) and
     refreshing its shared identity-index cache — best-effort, never affects the exit code above.
   - `python3 ~/.claude/hooks/audit_review_attribution.py` — the daily job's separate pre-step E
     (mirrors `schedules/prompts/daily_sweep.txt`'s own pre-step E), run here too: joins the review
     ledger (`last_reviewed`) against the dispatch-lease ledger (`spend.jsonl`) to flag `clean`
     review entries whose claimed reviewer dispatch cannot be corroborated (`unmatched`), carries no
     identity (`no-identity`), or is cited by more than one `clean` entry (`reused`). Same ~5-6 day
     `spend.jsonl` retention ceiling as `daily_spend_rollup.py` above — run it inside that window.
     REPORT-ONLY (same posture as `churn_report.py`/`model_pin_parity.py`): relay any flagged
     `unmatched`/`reused` entries as a finding (`--only unmatched`/`--only reused` narrows past
     legacy `no-identity` noise); never blocks, and closes the audit gap only against
     casual/accidental mismatches, never a deliberate forger with ordinary read access to
     `spend.jsonl` — see the module docstring's LIMITATIONS section. WARM-CHAIN CAVEAT
     (CLAUDE.md §10, 2026-08-30): a legitimate warm re-review chain re-cites round 1's reviewer
     identity by construction — until the #4686 auditor exemption lands: Exempt ONLY (i) a
     `reused` or `unmatched` verdict on an entry that is a successive `round=` value on a
     `prev=`-linked chain, where — for `unmatched` — the cited (agent_id, tool_use_id) pair
     EXISTS somewhere in `~/.claude/.agent_budget/spend.jsonl` (window-ignored; a pair that
     appears NOWHERE is a real mismatch and is always relayed); and (ii) a `reused` or `unmatched` verdict on a warm-shaped entry
     whose ledger `ts=` predates 2026-08-31 (the field mandate's landing date) — a hard date,
     never "before the mandate existed". Everything else in the verdict classes STANDS and is
     relayed — a `no-identity` entry is NEVER exempt on this ground alone — warm-chain shape is never a reason to suppress one; the existing `--only unmatched`/`--only reused` filter for legacy `no-identity` noise is unchanged
     (`round=`/`prev=` are not in the table output — read them via `--json`'s raw field, or the
     tokens in `~/.claude/.review_state/last_reviewed` directly, and cross-check a cited
     `unmatched` pair against `spend.jsonl` directly before relaying it). REKEY-CHAIN CAVEAT
     (AA-0064 Item 8 / 2026-09-01 fix rounds 2-3 — unlike the warm-chain caveat above, this one IS
     mechanically exempted in code already, `audit_review_attribution.py`'s own `rekey-exempt`
     verdict, so a legitimate `record_review.py --rekey` carry-forward normally never even reaches
     `reused`/`unmatched`): TWO shapes are still expected to show up flagged, NEITHER automatically
     a forgery signal — (i) a BROKEN chain: `rekey=` names a prior key that turned out missing or
     non-clean, which the exemption deliberately never covers — cross-check the cited `rekey=` key
     against `last_reviewed` directly (present in `--json`'s raw field); and (ii) a LEGACY
     MULTI-HOP chain predating the root-resolution fix (fix round 3, Finding 1: `--rekey` used to
     let a cited entry itself be a rekey entry, producing a chain longer than one hop) — the
     exemption's one-hop, true-root-only boundary NEVER groups such a chain into a star (a
     deliberate, safe-direction over-flag, not a bug) — verify the `rekey=` links by hand before
     relaying it the way an ordinary, unexplained `unmatched`/`reused` would be.
   - SOCIAL-QUEUE RELOAD DUE-CHECK (#5430) — the daily job's separate pre-step G (mirrors `schedules/prompts/daily_sweep.txt`'s own pre-step G): resolve the repo root as `$OVERSIGHT_REPO` if it is set in your process environment and resolves to a real git repository, else this session's own cwd (NEVER a display-name string — this repo's actual working directory); if `repo_tooling/scripts/social_reload_due.py` exists under that root, run `.venv/bin/python3 repo_tooling/scripts/social_reload_due.py --append-card ; RC=$? ; if [ "$RC" -eq 0 ] || [ "$RC" -eq 1 ]; then .venv/bin/python3 repo_tooling/scripts/gen_operator_hub.py ; fi` exactly per `marketing/social/RELOAD_RUNBOOK.md`'s own "Recurring trigger" section (repo-relative) — exit-code contract: 0 means the check ran fine regardless of DUE/OK; 1 means the state file was unreadable (still worth a hub card, still regenerate); only 2 (bad args) is skipped; treat non-zero-and-not-1 as a broken-check finding, never as DUE — DUE is reported via stdout/`--json`/the appended card, never the exit code; an absent/unbuilt `.venv` (exit 127) is an environment gap to note, not a broken check; when a platform reports DUE, this command never performs the reload itself (it needs the headed social browser) — file or update the tracked issue via `gh_issue.sh create` (or `--related <num>`) per board-steward rules naming the due platform(s) and pointing at `marketing/social/RELOAD_RUNBOOK.md` as the procedure; if the resolved repo has no `repo_tooling/scripts/social_reload_due.py` (a non-CSA product), skip this leg — never a failure.
4. The chosen dimension: `health`/`logs`/`cost` → dispatch `sentinel` with that dimension;
   `consistency` → dispatch `consistency-auditor` with the dossier's next audit slice; `all` →
   each of the above sequentially (budget permitting).
5. Relay each agent's digest VERBATIM in structure; file findings through the board steward's
   rules (one issue per root-cause cluster). Read `github.project_owner` / `github.project_number`
   from the resolved repo's manifest first (`python3 ~/.claude/scripts/repo_manifest.py get
   github.project_owner --repo <resolved repo root>` / `... get github.project_number --repo
   <resolved repo root>`), then file via `~/.claude/scripts/gh_issue.sh create --priority
   P0|P1|P2|P3 --project <that number> --owner <that owner> --label <type> --label "area: <x>"
   --label "difficulty: <x>"` — #5827: `--project`/`--owner` are what actually
   let `--priority` write the board field (without them the write is skipped with a warning and the
   create still exits 0, fix-round 1 finding A2; with them, a board-write failure is a PARTIAL exit
   3 — the issue WAS filed and its number is on stdout as `PARTIAL #<num> — Priority NOT set:
   <reason>` — never retry the create, record the reason and set Priority by hand or via
   `gh_issue.sh transition`; exit 1 means the create was refused before anything was filed, full
   stop — every post-create failure exits PARTIAL 3 naming the issue on stdout (`PARTIAL #<num> —
   Priority NOT set: …`, `… — Status NOT set: …`, or `PARTIAL #<unknown> — issue filed, number
   unparseable: …`), with ONE exception: the Backlog status the helper auto-fills when `--project`
   is given and `--triage` is not is SOFT, so a failed Backlog write exits 0 with a stderr warning
   that the issue was filed with NO Status set — exit 0 means filed, not necessarily parked), so
   never omit them; during the observer-first window a create missing `--priority` or a label class
   still files, it only logs `create-missing-triage`, so passing them is expected practice, not yet
   a hard requirement; destructive dispositions are proposed to the operator, never executed.
6. Write the heartbeat for the manual run: `~/.claude/schedules/heartbeats/manual-sweep.json`
   (`{job, started_at, finished_at, exit, cadence, summary}` — the summary names the dimension
   run). All timestamps UTC ISO-8601 with a literal `Z` suffix, matching `_preamble.txt`'s
   TIMESTAMP FORMAT rule — never a local offset. `cadence` is always the literal string
   `"manual"`: that is what tells the daily job's own heartbeat audit (and `heartbeat_audit.py`)
   to exempt this file from cadence-staleness checking entirely, since a manual sweep is never
   "due" on any schedule. In an interactive session either the Write tool (approve the prompt) or
   a Bash heredoc works; the heredoc form
   is the one proven in headless runs (the spike observed a Write-tool permission gate on one
   schedules/ path).

Session/model discipline: dispatched agents use their own pinned models; do not override upward.
This command never pushes, merges, deploys, or touches production.
