"""cycle_budget — mechanical, in-cycle spend guard for any unattended agent loop.

WHY THIS EXISTS (see the loop's first real cycle, #4498, 2026-08-27/28):
a cost TREND across cycles is an oversight AGENT's job (a periodic sweep can
notice "spend is climbing" tomorrow); stopping a RUNAWAY cycle before it burns
the budget cannot be an agent's job, because an agent that learns about the
overrun on tomorrow's sweep cannot undo today's spend. That needs a
synchronous, mechanical check a dispatcher calls BEFORE every additional
spawn, in the same process, right now. This module is that check.

It is a PURE CONSUMER of ~/.claude/.agent_budget/spend.jsonl (the real-spend
ledger `agent_budget.py`'s release_hook already writes) -- this module never
writes to that ledger, never takes a lease, and owns no lock. It adds no new
mutable state of its own, by design: the fewer moving parts a budget GUARD
introduces, the fewer ways the guard itself can be wrong.

INTEGRATION STATUS (round 16, 2026-08-28 review finding #4): as of this
writing, no dispatcher, schedule, or job in this runtime actually CALLS
`check`/`decide_cycle_budget()` before a real spawn -- this module exists,
is tested, and is correct, but is not yet wired into anything live; treat
it as built-but-not-integrated, not as an active gate, until a caller is
confirmed.

REPO-AGNOSTIC BY CONSTRUCTION: every identifying fact (which system is
asking, which orchestrating session, which time window, which agent types it
is allowed to have dispatched) is a caller-supplied parameter, never a
hardcoded path, product name, or loop. `spend.jsonl` rows carry NO
system/repo field at all (verified against the live ledger schema,
2026-08-28) -- session id + timestamp + agent_type are the only correlators
that exist -- so a caller's `system` label is pure bookkeeping/logging; it is
never used to filter or branch, because the data to do that doesn't exist.

THE CENTRAL DESIGN CHOICE -- fail OPEN vs fail CLOSED, and why they differ
here from `agent_budget.py`'s own conventions:

  * `agent_budget.py`'s pacer/gate is a CONCURRENCY throttle: worst case on
    failure is a few extra parallel agents for a few seconds, so it is
    correct for it to fail OPEN (never wedge a session over an advisory
    accounting hiccup) -- see its own module docstring.
  * This guard is a SPEND ceiling. Worst case on failure is an unattended
    loop burning real, unbounded dollars overnight with nobody watching --
    which is the exact failure this module was commissioned to prevent
    (evidence #4 above: a reported cost that was ~26x too small produced one
    already-wrong conclusion). So the actual gating surface --
    `attribute_cycle_spend()` / `decide_cycle_budget()` -- fails CLOSED:
    any state it cannot confidently price or attribute to the calling cycle
    (ledger unreadable, dispatches missing from the ledger entirely, an
    unpriced/unrecognized model, a caller/ledger mismatch) comes back with
    `status="unknown"`, and `decide_cycle_budget()` treats unknown exactly
    like "over budget" (`allowed=False`) -- NEVER as "$0 spent, keep going".
  * The read-only introspection surfaces (`status`/`doctor` CLI subcommands)
    stay fail-open in the narrow sense that a read error never raises or
    crashes the calling process -- they degrade to a clearly-labeled
    `status="unknown"` (or a `doctor` health report saying the ledger is
    unreadable) rather than throwing. That is NOT the same as fail-open
    authorizing spend: nothing in this module ever turns "I could not read
    the ledger" into "so assume zero was spent". The only two outcomes a
    caller can ever see are a confidently-priced `known` figure, or an
    honest `unknown` -- there is no third, silent "probably fine" path.
  * Bad CALLER input (empty session id, unparsable timestamp, an empty
    `known_agent_types` set, a bare string/bytes passed as `known_agent_types`
    instead of a real collection -- iterated character-by-character, which
    silently empties the ambiguous-row check, see BLOCKER 1 2026-08-28 --
    a non-positive ceiling) is different again: that is a programming error
    at the call site, not ledger ambiguity, so it raises `ValueError`
    immediately rather than being laundered into `unknown` -- the two
    failure classes must stay distinguishable so a dispatcher can tell "I
    called this wrong" apart from "the ledger would not confirm my spend".

LEDGER SCHEMA (as written by `agent_budget.py`'s release_hook; verified
against the live file 2026-08-28): one JSON object per line --
  {"ts": "<UTC %Y-%m-%dT%H:%M:%SZ>", "session": <str|None>,
   "agent_type": <str|None>, "model": <str|None>,
   "tokens": {"input": int, "output": int, "cache_read": int,
              "cache_creation": int}, "tokens_total": int, ...}
`session` is the TOP-LEVEL Claude Code session id that dispatched the
sub-agent (verified: every row sharing one `session` value traces back to one
orchestrating session), which is why it is the primary attribution key here.
A large fraction of real rows carry `session: null` -- an unjoined
claim/stop pair (see `agent_budget.py`'s `join_state`) -- and that is
precisely the population this guard refuses to silently drop or silently
include; see `attribute_cycle_spend()`'s "ambiguous" bucket below.

IDENTITY RECOVERY (added 2026-08-28, `spend_attribution.py`) -- an OPTIONAL,
purely-additive `identity_index` parameter on `attribute_cycle_spend()`/
`decide_cycle_budget()`. Measured live: ~47% of ledger tokens carry
`model: null` (unpriceable) and, for a real sub-population, `agent_type`
is only the client's generic "workflow-subagent" placeholder rather than a
real dispatched type -- `spend_attribution.py` recovers both from Claude
Code's own workflow-dispatch metadata (never fabricated) and marks every
recovered value with an explicit `attribution` provenance block. When
`identity_index` is supplied, ledger rows are enriched via
`spend_attribution.enrich_rows()` BEFORE classification -- but this can only
ever WIDEN what this module already knows how to do with a row, never
weaken it, because recovery only ever moves a row in the SAME safe
direction the existing algorithm already treats as more cautious:
  * A previously-EXCLUDED row (a placeholder/no agent_type, assumed
    unrelated background noise -- see EXCLUDED below) whose TRUE recovered
    agent_type turns out to be one this cycle declared becomes AMBIGUOUS
    instead -- correctly forcing `unknown` for real spend that was
    previously silently ignored, never the reverse.
  * A MATCHED row (session already exactly equals this cycle's own --
    the highest-confidence signal this ledger offers) whose placeholder
    agent_type recovers to a real, known type is now correctly validated
    against `known_agent_types` instead of failing that check on a generic
    label; its recovered `model` (if the original was null) can now be
    priced instead of forcing `unpriced-model-in-window`.
  * Recovery NEVER fabricates a `session` match, and never turns AMBIGUOUS
    into MATCHED or EXCLUDED into MATCHED -- only EXCLUDED into AMBIGUOUS,
    or resolves a placeholder/missing field on an ALREADY-matched row. A
    slice that is genuinely still ambiguous or unpriceable after recovery
    returns `status="unknown"`/`allowed=False` exactly as before -- this
    integration is enrichment, never a relaxation, of the fail-closed
    contract above.
`identity_index` defaults to `None` (no recovery attempted -- identical,
byte-for-byte, to this module's pre-recovery behavior) at the LIBRARY level,
preserving this module's existing "every ledger path/parameter is explicit,
no hidden global state" testability contract. Only the CLI (`run()`) opts
into loading a default index automatically, via
`spend_attribution.load_cached_index()` -- which ONLY reads whatever
identity cache already exists on disk and NEVER triggers a live filesystem
scan (round 18, 2026-08-28: no fixed duration is safe to quote here --
see `spend_attribution.py`'s own CACHING section for why; the right
mental model is "scales with temp-root size," not a fixed number of
seconds -- far too slow either way for a per-dispatch gate) -- so a
`check`/`status` CLI call still degrades to `identity_index=
{}` (i.e. no recovery, but never an error) if the cache is missing, stale,
or `spend_attribution` cannot be imported at all. `--no-recovery` disables
this explicitly for debugging/auditing raw, unrecovered attribution.

PROVENANCE VISIBILITY (added 2026-08-28). Recovery can flip a real denial
into a real allowance -- e.g. a MATCHED row's placeholder `agent_type`
recovers to a declared type with a priced model, turning
`unexpected-agent-type-for-session` into `status="known", allowed=True`.
A caller must be able to tell that such a verdict rests partly on an
INFERRED, not measured, identity. `attribute_cycle_spend()` therefore
actually reads each MATCHED row's `row["attribution"]` block (populated by
`spend_attribution.enrich_rows()`, never the bare, already-overwritten
`agent_type`/`model` fields) via `_count_recovered_fields()`, and reports
`recovered_agent_type_rows`/`recovered_model_rows` on every
`CycleAttribution` it returns (both `known` and `unknown` results). This is
PURELY informational -- it never changes the allow/deny decision itself,
only makes an already-decided verdict's reliance on inference visible to
the caller.

DUPLICATE-AGENT_ID SPEND (added 2026-08-28). The same `agent_id` can
appear as two independent MATCHED ledger lines sharing this cycle's own
session -- a normal claim/release plus a LATER, LARGER cumulative
`stopped-unjoined` reap of the SAME agent's still-running spend (see
`spend_attribution.py`'s module docstring for the measured real example).
Naively pricing every matched row would double-count that spend.
`_collapse_duplicate_agent_id_rows()` collapses each duplicate-agent_id
group to only its single largest reading before pricing.

ROUND 4 CORRECTION (2026-08-28) -- round 3's fix here was itself wrong on
two counts, both now fixed:
  * BLOCKER 1: the winner used to be picked by summing raw TOKEN COUNTS
    across the group -- but `price_tokens_usd()` weights token fields very
    differently by rate (e.g. on sonnet, output tokens are ~50x the $/token
    of cache_read tokens), so "most tokens" and "most dollars" can name
    DIFFERENT rows, and picking the token-count winner could under-report
    real spend by >20x. Round 3's own docstring claim that keying both
    quantities on the same raw field "makes that disagreement structurally
    impossible" solved the wrong disagreement (field-vs-field, measurably
    0/1203 rows on the live ledger) while leaving the real one
    (quantity-vs-price) live. The winner is now selected by each candidate
    row's actual computed dollar value (`price_tokens_usd()` itself, the
    exact function that later prices the survivor) -- never by a token
    count of any kind.
  * BLOCKER 2: a row DROPPED by the collapse was never price-checked at
    all, so a malformed/unpriceable row sharing an agent_id with a clean
    row could silently vanish from the pricing sum instead of forcing
    `unknown` -- invisible to the unpriced-model-in-window safety net that
    correctly catches a LONE unpriceable row. Every candidate in a
    duplicate-agent_id group (winner AND every dropped row) is now
    price-checked; if ANY of them cannot be priced, the group contributes
    to `unpriced_rows` and the whole attribution returns `unknown` with
    reason `unpriced-model-in-window`, exactly as if that row had matched
    alone with no duplicate to hide behind.

`matched_rows` on the returned `CycleAttribution` still reports every row
that matched this cycle by session OR by agent_id correlation (round 8;
see the module docstring's ROUND 8 CORRECTION section -- unaffected by
this collapse), while `collapsed_duplicate_rows` discloses how many of
those rows were excluded from the PRICING sum specifically.

ROUND 6 CORRECTION (2026-08-28) -- BLOCKER 3: the collapse above keyed
SOLELY on `agent_id`, diverging from `churn_report.py`'s OWN
`dedup_spend_lines()` (cited by name as authoritative just above and in
spend_attribution.py's own docstring), which dedups by `tool_use_id` and
deliberately never collapses two rows carrying DISTINCT non-null
`tool_use_id`s. Two rows sharing an `agent_id` but each carrying its OWN,
different, non-null `tool_use_id` are two real, independent dispatches --
not two readings of one -- and collapsing them reported half the real
spend ($3.00 instead of $6.00 for two independent $3.00 dispatches, in the
reviewer's exact repro). `_collapse_duplicate_agent_id_rows()` now checks,
per agent_id group, how many DISTINCT non-null `tool_use_id`s are present:
2 or more means the group is left completely uncollapsed (every row priced
and summed independently -- the same answer churn_report.py's own
dedup_spend_lines() already gives for identical input bytes); 0 or exactly
1 (the case this collapse was actually designed for -- a claim/release
plus a later `tool_use_id: null` reap of the SAME dispatch) is collapsed
exactly as before. Summing, rather than forcing `unknown`, was the chosen
answer for the 2+-distinct-id case: a non-null, distinct `tool_use_id` on
each side is itself direct, strong evidence of two real dispatches, so
treating that evidence as spend rather than refusing to price it keeps
this module answering the question it exists to answer, and keeps it from
silently diverging from churn_report.py's own cited answer for the
identical bytes.

BLOCKER 2 (round 3, 2026-08-28): this collapse now also runs BEFORE
`attribute_cycle_spend()` compares `expected_dispatch_count` against the
matched-row count -- and that comparison is against the POST-collapse
distinct-dispatch count, never the raw pre-collapse row count. The two
double-counting mitigations (declare-your-count vs. collapse-duplicates)
previously defeated each other: an honestly-declared count of 1 was
rejected as a "count mismatch" the instant its one real agent legitimately
produced 2 ledger lines, while a cycle that simply omitted or over-declared
its count sailed the identical rows through with the collapse silently
applied underneath it. Comparing post-collapse closes that gap.

ROUND 8 CORRECTION (2026-08-28) -- BLOCKER 4, the ROOT CAUSE underlying 3
straight rounds (3, 4, 6) of duplicate-agent_id patches: every one of those
rounds hardened `_collapse_duplicate_agent_id_rows()` -- the function that
runs on the `matched` list -- without ever asking how a row GETS into
`matched` in the first place. The answer, unchanged since round 1, was:
independently, by that row's OWN `session`/`agent_type`/window, with zero
awareness of `agent_id` at all. `agent_id` correlation was therefore pure
background noise to the classification pass and only ever mattered
AFTERWARD, to rows that had ALREADY both independently qualified as
MATCHED. Measured against the live ledger (1245 rows, 2026-08-28): 44
duplicate-agent_id groups exist, ALL 44 split across one session-matched
row and one session:null row, and in ALL 44 the null row carries the
LARGER cumulative reading -- including the exact example this module's own
and spend_attribution.py's docstrings quote by name as the motivating case
(agent_id "a0c1c8e46f867986d"). Because the null row's own session/
agent_type were evaluated in isolation, it was independently classified as
EXCLUDED (or, if its own agent_type happened to be independently declared,
AMBIGUOUS) and never once reached the collapse step this module had spent
3 rounds hardening -- that machinery was correctly built, for a shape that
does not occur even once in the live ledger, while the shape that occurs
44/44 times flowed straight through as if it were unrelated background
noise.

THE FIX is a genuine pipeline reordering, not another special case:
`_session_matched_agent_ids()` runs FIRST, over every row, and answers one
question -- which `agent_id`s does THIS cycle's `session_id` already prove
it dispatched. The main per-row classification loop then checks agent_id
correlation ALONGSIDE the session check, not after it: a `session: null`
row whose `agent_id` is in that proven set is treated exactly like a direct
session match for bucketing purposes -- fed into the SAME `matched` list,
regardless of its own `agent_type`/window -- so `_collapse_duplicate_
agent_id_rows()` finally receives the actual live shape it was built for,
and prices/collapses/force-unknowns it using machinery that already
existed and was already correct. This closes the specific symptoms BLOCKER
1 (round 8) and BLOCKER 2 (round 8) independently also needed fixing --
their own repros involve no agent_id correlation at all (a lone undated
row, and a lone row with no session-matched sibling, respectively) -- so
this reordering does not subsume either of them; both needed their own
targeted fix alongside this one. See `attribute_cycle_spend()`'s own
ATTRIBUTION ALGORITHM docstring section for the corrected bucket
definitions this reordering produces.

ROUND 10 CORRECTION (2026-08-28) -- round 8's agent_id correlation, once
combined with two dimensions it was never tested against, had two real
gaps (both now fixed) plus one over-broad claim (now scoped):

  * BLOCKER 1: the window exemption for a correlated row (see ROUND 8's
    "outside the window is still included" text above) applied in BOTH
    directions, but the "its own timestamp records when a LATER reap
    process ran" rationale only ever justifies exempting a row dated
    AFTER `cycle_end`. A correlated row dated BEFORE `cycle_start` is
    genuinely PRIOR-CYCLE spend -- charging it to the current cycle
    over-counts, and on a long-lived session id this can accumulate into
    a permanent denial. The exemption is now one-directional: only
    `row_dt > end_dt` is exempted for a correlated row; `row_dt <
    start_dt` is dropped exactly like any other out-of-window row,
    correlated or not.
  * BLOCKER 3: the duplicate-agent_id collapse (`_collapse_duplicate_
    agent_id_rows()`) can silently DISCARD a genuinely ambiguous row --
    one that reached `matched` only via agent_id correlation (never
    proven to be this cycle's own session) -- the instant it loses the
    dollar-value comparison to another row in its group. Before this
    round, that row's dropped/collapsed fate never asked whether its own
    (pre-collapse) `agent_type` was itself one this cycle declared; if it
    was, the module was SILENTLY GUESSING "duplicate reading" over
    "genuine additional spend" -- exactly the guess round 7's IDENTITY
    RECOVERY contract ("never turns AMBIGUOUS into MATCHED") exists to
    refuse. DECISION (round 10): preserve the promise. A dropped row that
    is agent_id-correlated (not a direct session match) AND whose
    original-or-effective agent_type (the same union
    `_ambiguous_agent_type_candidates()` already uses) is in
    `known_agent_types` now forces `status="unknown"` (reason
    `ambiguous-duplicate-agent-id-declared-type`) instead of being
    silently discarded -- the module still refuses to guess which of the
    two readings is real. A dropped row that arrived via a DIRECT session
    match is unaffected: both readings are already proven to be this
    session's own, so collapsing them remains the safe, intentional
    behavior round 3/4 built. `_collapse_duplicate_agent_id_rows()` now
    accepts the per-row correlation flags and `known_agent_types` needed
    to make this check; it is purely additive when either is omitted.
  * Doc-only (#5): `matched_rows` counts a row matched by session OR by
    agent_id correlation since round 8 -- two stale docstring locations
    still said "matched this cycle's SESSION" only; corrected in both
    places.

ROUND 16 CORRECTION (2026-08-28) -- BLOCKER 1, a genuine 5x UNDER-report,
the dangerous direction this module exists to prevent: the after-window
exemption (`row_dt > end_dt` check) used to be hard-gated on
`not is_agent_id_correlated`, which is trivially true for a DIRECT session
match (the two predicates are mutually exclusive) -- so that guard was
ALSO, silently, the entire fate of a direct-session-match row dated after
cycle_end: an unconditional drop with ZERO bookkeeping (not matched,
ambiguous, excluded, unpriced, or undated), even when that row shared an
`agent_id` with an anchor this cycle had already proven dispatched
in-window. Reproduced: an identical agent/timestamp/spend reap reported
the full, correct spend when its `session` field was null (the pre-
existing agent_id-correlated path) and a 5x under-report the instant that
same field was instead populated with a real session value -- strictly
MORE evidence (a populated session field) must never yield strictly LESS
inclusion than strictly LESS evidence (a null one), which directly
contradicts this module's own stated axiom that `agent_id` is unique PER
DISPATCH: a row sharing an agent_id with an already-proven-this-cycle
anchor is, by definition, that SAME dispatch's own spend, regardless of
what value happens to be stamped in that row's own `session` field --
PROVIDED the window has already closed on it (see below for the crucial
scoping this fix does NOT extend). FIX: the after-window exemption
(`is_after_window_exempt`) is now keyed on a single check -- does this
row's `agent_id` appear in `this_cycle_anchor_agent_ids` -- applied
uniformly whether the row reached the branch via `is_agent_id_correlated`
(null session), a NEW, separate `is_after_window_agent_id_match` channel
(a real, non-null, non-matching session, but ONLY when `row_dt > end_dt`),
or a literal (possibly stale) match of this cycle's own session id dated
after cycle_end. All three routes are, once exempted, EXEMPT from the
unexpected-agent-type safety net -- each is, by the axiom above, a REAP of
an already-proven in-window dispatch, not a fresh declaration of this
session's own, so none needs its OWN (possibly placeholder/undeclared)
agent_type to be one this cycle declared.

CORRECTED (round 20, 2026-08-28): this paragraph originally also claimed
all three routes are "flagged as agent_id-correlated for the
duplicate-collapse ambiguity check" once exempted -- FALSE for the third
route (a literal, possibly-stale match of this cycle's own session id):
round 10's own carve-out already rules a direct session match's duplicates
are NEVER ambiguous for that SEPARATE check, regardless of window
position (see ROUND 18 CORRECTIONS' Blocker 2 below, and ROUND 20
CORRECTION below for the two-consumer split this required). Only the two
genuinely agent_id-only correlation channels (`is_agent_id_correlated`,
`is_after_window_agent_id_match`) are flagged correlated for the
duplicate-collapse ambiguity check; the safety-net exemption above,
governed by a DIFFERENT predicate, still covers all three routes.

SCOPING (round 16, load-bearing, mutation-tested): the axiom-based
inclusion above applies ONLY to a row dated STRICTLY AFTER cycle_end --
`is_agent_id_correlated` itself (governing IN-WINDOW correlation) still
requires `row_session is None`, UNCHANGED from round 10. An IN-WINDOW row
carrying a real, non-null, DIFFERENT session is a live, contemporaneous
declaration by that OTHER session, not evidence of a reap, and merging it
purely on a shared `agent_id` would let a genuinely independent
dispatch's real spend get attributed to this cycle merely for an
agent_id collision -- exactly the failure mode
`test_falsify_correlation_requires_null_session_never_pulls_in_other_
concrete_session` (round 10) exists to prevent, and it must keep passing
UNCHANGED. The distinguishing fact that makes the after-window case safe
to widen but the in-window case unsafe: by the time a background reap
process runs (after cycle_end, potentially long after), whatever value
happens to be stamped in ITS OWN `session` field is an artifact of
WHEN/HOW the reap ran, not a live ownership claim the way an in-window
row's own populated session is. See `attribute_cycle_spend()`'s main loop
and `test_cycle_budget.py`'s reap-own-session-classification grid test
(reap position x reap's own session classification: null / this cycle's
own session / some other session, against an anchor proven in-window).

ROUND 18 CORRECTIONS (2026-08-28) -- three defects found reviewing rounds
14-16's own fixes above:

  * BLOCKER 1: the restricted-anchor rejection just above (`is_agent_id_
    correlated and row_agent_id not in this_cycle_anchor_agent_ids`) used
    to `continue` unconditionally -- denying the CORRELATION correctly,
    but also consuming the row ENTIRELY, skipping the normal ambiguous/
    excluded classification tail it would have received had
    `is_agent_id_correlated` never been true at all, with ZERO
    bookkeeping. Confirmed live-reachable against the real
    ~/.claude/.agent_budget/spend.jsonl (3 real rows affected). FIX: mark
    a `correlation_rejected` flag instead of `continue`ing, and fall
    through to the same ambiguous/excluded tail an uncorrelated row gets
    -- see `attribute_cycle_spend()`'s main loop for why this must be
    layered AFTER the `row_dt is None`/`row_dt < start_dt` handling
    rather than folded into `is_agent_id_correlated` itself (that
    alternative loosens an UNDATED correlated row from a forced `unknown`
    to a silent drop -- a real trap, verified against this module's own
    `test_falsify_correlated_row_anchor_position_grid_4x4[before-undated]`/
    `[after-undated]`).
  * BLOCKER 2: the "All three routes are bookkept identically downstream"
    claim in the ROUND 16 CORRECTION paragraph above is now WRONG for one
    of the three -- `is_correlated_for_bookkeeping`'s bare `row_dt >
    end_dt` disjunct incorrectly flagged a genuine after-window DIRECT
    SESSION MATCH (`is_session_match`) as agent_id-correlated for round
    10's own duplicate-collapse ambiguity check, reversing round 10's own
    explicit carve-out (`_collapse_duplicate_agent_id_rows()`'s own
    docstring: "a direct-session-match row is never subject to this check
    regardless -- both readings are already proven to be this session's
    own"). FIX: `is_session_match` is now excluded from
    `is_correlated_for_bookkeeping` outright, unconditionally, regardless
    of window position -- a genuine direct match's own duplicates are
    NEVER ambiguous, dated after cycle_end or not.
  * BLOCKER 3: `is_after_window_agent_id_match`'s "agent_id is unique per
    dispatch" axiom (round 16) could pull in a row belonging to a
    genuinely DIFFERENT, non-null session, disagreeing with
    `_collapse_duplicate_agent_id_rows()`'s own, authoritative rule (2+
    DISTINCT non-null `tool_use_id`s on one `agent_id` proves 2+
    INDEPENDENT dispatches). A candidate admitted via agent_id alone but
    carrying a `tool_use_id` the collapse would treat as proof of a
    SEPARATE dispatch got summed in anyway, since the collapse never
    merges rows it treats as independent. FIX: `is_after_window_agent_id_
    match` now defers to the SAME tool_use_id-compatibility rule via
    `_this_cycle_anchor_tool_use_ids()` -- a candidate is only pulled in
    when its own `tool_use_id` is null (reap-shaped) or genuinely matches
    an already-proven anchor value for that `agent_id`.

    CORRECTED (round 20, 2026-08-28): "so the two rules can never
    disagree" was true only of THIS one channel considered in isolation --
    round 19's review found the identical axiom-conflict still fully
    reachable through the OTHER two after-window admission routes this
    fix never touched: a null-session candidate reaching the shared
    after-window exemption via `is_agent_id_correlated`, and a literal
    (possibly stale) direct session match reaching it via `is_session_
    match`. Neither channel's own predicate ever consulted the
    compatibility gate above -- it lived solely inside `is_after_window_
    agent_id_match`'s own definition -- so a conflicting-tool_use_id
    candidate on either of those two routes still got silently summed in.
    See ROUND 20 CORRECTION below for the actual fix: the gate now lives
    on the SHARED `is_after_window_exempt` check every route passes
    through, not on one route's own predicate.

ROUND 20 CORRECTION (2026-08-28) -- round 19's own review of rounds 18's
fixes found both of them had the identical failure shape this module keeps
hitting: a targeted patch closed the ONE repro tested, leaving an untested
SIBLING path through the SAME shared decision surface wide open.

  * BLOCKER 1: the after-window admission surface has THREE distinct
    routes into `matched` -- (a) `is_after_window_agent_id_match` (a real,
    non-null, non-matching/foreign session), (b) `is_agent_id_correlated`
    (a null session), (c) a literal, possibly-stale match of this cycle's
    own session id (`is_session_match`) -- and all three converge on the
    SAME shared gate, `is_after_window_exempt` (the `row_dt > end_dt`
    check). Round 18's tool_use_id-compatibility fix was wired into route
    (a)'s OWN predicate instead of that shared gate, so it only ever
    protected route (a); a conflicting-tool_use_id candidate reaching the
    identical after-window admission via route (b) or (c) was still summed
    in whole -- measured: a null-session candidate (route b) or a literal
    direct-session-match candidate (route c) sharing an anchor's agent_id
    but carrying a DIFFERENT, non-null `tool_use_id` reported known/$33.00
    (wrongly including the conflicting $30.00 reading) while the
    byte-identical foreign-session shape (route a) correctly reported
    known/$3.00. FIX: `is_tool_use_id_compatible` (unchanged, still
    computed once per row from `_this_cycle_anchor_tool_use_ids()`) is now
    ANDed directly into the shared `is_after_window_exempt` check itself --
    `is_after_window_exempt = row_agent_id-is-a-str and row_agent_id in
    this_cycle_anchor_agent_ids and is_tool_use_id_compatible` -- so every
    route that reaches this check is governed by it uniformly, and route
    (a)'s own predicate no longer needs (or carries) its own private copy
    of the same gate.

  * BLOCKER 2: `is_correlated_for_bookkeeping` (round 18's fix, which
    excluded `is_session_match` unconditionally) fed TWO genuinely
    different downstream consumers with ONE flag, and round 18's fix was
    correct for only one of them. Consumer #1, the duplicate-collapse
    ambiguity check (`_collapse_duplicate_agent_id_rows()`'s
    `correlated_flags`), correctly wants `is_session_match` EXCLUDED
    unconditionally -- round 10's own carve-out that a direct match's
    duplicates are never ambiguous, regardless of window position, is
    unaffected by this round and stays correct. Consumer #2, the
    unexpected-agent-type safety net a few lines below, wants something
    narrower: round 16's own documented intent was that the safety net
    still applies to a genuine, IN-WINDOW direct session match (only an
    AFTER-WINDOW-exempted direct match, or either agent_id-only
    correlation route, is exempt from it). Round 18's single shared flag
    silently reinstated the safety net for an after-window-exempted direct
    match too -- reproduced: a reap-shaped row with `session` literally
    equal to this cycle's own `session_id` (a stale copy of an in-window
    anchor's own session), `agent_type` undeclared, `tool_use_id` null,
    dated after `cycle_end`, correctly reported known/$33.00 before round
    18 and incorrectly denied as `unexpected-agent-type-for-session` after
    it. FIX: the one flag is now two, each computed and named for its own
    consumer -- `is_correlated_for_collapse_ambiguity` (unchanged from
    round 18: `(not is_session_match) and (is_agent_id_correlated or
    is_after_window_agent_id_match)`) feeds `matched_is_correlated`/the
    collapse check exactly as before; `is_exempt_from_unexpected_type_
    check` (`(not is_session_match) or (row_dt > end_dt)` -- true for
    either agent_id-only correlation route, OR a direct match that only
    survived the window check via the after-window exemption above) gates
    the safety net. The two are equal for every row EXCEPT an
    AFTER-WINDOW direct session match: there, the collapse-ambiguity flag
    is always `False` (never ambiguous) while the safety-net-exemption
    flag depends on window position (exempt only after cycle_end) --
    restoring round 16's
    original, narrower intent for consumer #2 without reopening round 18's
    fix to consumer #1.

  Both fixes live on the SAME shared surface (the `if is_session_match or
  is_agent_id_correlated or is_after_window_agent_id_match:` block and its
  post-window-check tail in `attribute_cycle_spend()`'s main loop) --
  intentionally: every prior round's failure in this area was a fix
  applied to one named channel's own predicate instead of the shared gate
  or shared flag all channels actually pass through. See
  `test_cycle_budget.py`'s route (a)/(b)/(c) tool_use_id-conflict trio and
  the after-window undeclared-type direct-match test for the regression
  coverage this round adds.

PRICING is a single editable data table (`PRICING_USD_PER_MTOK`), not
literals scattered through the pricing logic. Rates are USD per million
tokens, published Anthropic list pricing re-verified 2026-09-05 against
platform.claude.com's pricing page, at FAMILY granularity (haiku/sonnet/opus).
NOTE: every family in this table was found STALE on 2026-09-05 -- opus by 3.0x
in both directions (it carried the retired Opus 4.1 rates) -- so this table had
been overstating opus spend threefold since authoring. `ccdash/pricing.py` keys
on exact model id and is the finer, authoritative instrument; when the two
disagree, ccdash wins and this table is the one to correct. Update
this table (or pass `--pricing-file` / the `pricing=` kwarg with the same
shape) when Anthropic's pricing changes; nothing else in this module needs to
change. A model string that does not normalize to a known family (including
`None` and any unrecognized code-name model tag) is priced as `unknown` on
purpose -- see `normalize_model()` -- which forces the CONSERVATIVE outcome
(`status="unknown"`, never a silent $0) rather than guessing a family.
Known limitation, intentionally not modeled: Anthropic's 1M-context long-
context premium tier (models tagged `[1m]`) can bill above 200K context at a
higher per-token rate than the base family; this table prices `[1m]`-tagged
models at their base family's rate, which is an UNDER-estimate for very long
prompts. Flagged here rather than silently absorbed into "sonnet"/"opus";
tighten by adding a `sonnet-1m`/`opus-1m` family if this bites in practice.

CLI subcommands (`status` / `check` / `doctor`) -- see `build_arg_parser()`
for the full flag surface. `check` is the gate a dispatcher shells out to
before spawning more work; its exit code is deliberately three-valued:
  0  allowed        (status == known, spend below ceiling)
  2  denied         (status == known, spend at/over ceiling)
  3  unknown        (attribution could not be confirmed -- stop and ask)
  2  argument error (bad CLI usage; argparse's own convention)
`status`/`doctor` always exit 0 -- they report, they never gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# ---------------------------------------------------------------------------
# Pricing data -- USD per MILLION tokens, by normalized model family. Edit
# this table (or supply an equivalent-shaped --pricing-file) when Anthropic's
# published pricing changes. See the module docstring for the "why family
# granularity, why unknown models are never guessed" rationale.
# ---------------------------------------------------------------------------
# CORRECTED 2026-09-05 against platform.claude.com/docs/en/about-claude/pricing.
# Every family in this table was STALE, and opus was stale by 3.0x in both
# directions:
#   opus   15/75 -> 5/25   -- 15/75 are the RETIRED Opus 4.1/4.0 rates. Opus 4.5
#                             through Opus 5 are all $5/$25. Every opus dollar
#                             this module reported before today was 3x too high.
#   sonnet 3/15  -> 2/10   -- Sonnet 5's launch "introductory" pricing became the
#                             standard price; the scheduled 2026-09-01 increase
#                             back to 3/15 was cancelled (see the pricing page's
#                             claude-sonnet-5-introductory-pricing note). Sonnet
#                             4.6/4.5 remain 3/15, which family granularity
#                             cannot express -- see the caveat below.
#   haiku  0.80/4 -> 1/5   -- 0.80/4 are the RETIRED Haiku 3.5 rates; Haiku 4.5
#                             is $1/$5.
# cache_read = 0.1x input; cache_creation = 1.25x input (the 5-minute write
# multiplier). The 1-hour write is 2.0x and is NOT modeled at this granularity
# -- a 1h-cached call is therefore UNDER-priced here. `ccdash/pricing.py` keys
# on exact model id and models both TTLs; it is the finer instrument and the
# tie-breaker whenever the two disagree.
# FAMILY-GRANULARITY CAVEAT (why these can drift again): one rate per family
# cannot represent a generation split that is live RIGHT NOW -- Sonnet 5 at 2/10
# vs Sonnet 4.6/4.5 at 3/15. This table prices all sonnet at the CURRENT
# generation's rate, which under-prices any residual 4.6/4.5 traffic by 1.5x.
PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "opus": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_creation": 6.25},
    "sonnet": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_creation": 2.50},
    "haiku": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_creation": 1.25},
    # Fable 5 / Mythos 5, $10/$50 (added 2026-09-05 -- see the family-pattern
    # note; these rows were previously unpriced and invisible in every chart).
    "fable": {"input": 10.00, "output": 50.00, "cache_read": 1.00, "cache_creation": 12.50},
}

# RESOLVED 2026-09-05 -- the note below is kept only as a record of the
# decision it reversed. BLOCKER 4 (2026-08-28) excluded "claude-fable-5" on
# the grounds that it "is not a published Anthropic model name/family this
# table's authoring conventions can source a real per-MTok rate from," and
# said to "revisit if/when its real billing family is confirmed." It is now
# confirmed: Fable 5 is published at $10/$50 per MTok (and Mythos 5 at the
# same rate), verified 2026-09-05 against platform.claude.com's pricing
# page. Both are priced above.
#
# The original refusal-to-guess was CORRECT reasoning and is unchanged as a
# principle. What it lacked was a way to notice when the missing fact became
# available: the exclusion held for a week while 15 live rows carrying 268M
# tokens dropped out of every by-model chart, and it surfaced only because
# the operator noticed the dashboard never showed a model they run
# constantly. A refusal to guess must come with a re-check trigger, or it
# silently becomes a permanent blind spot -- that lesson is the point of
# keeping this note.

# Checked in order; first substring match (case-insensitive) wins. A model
# string matching none of these (including None/"" and an unrecognized
# internal code name like "claude-fable-5") normalizes to "unknown", which is
# never present in PRICING_USD_PER_MTOK -- so it can never be silently priced.
# FABLE ADDED 2026-09-05 (operator report: "it only shows Opus, Sonnet and
# Haiku but I run Fable almost nonstop"). Fable was deliberately omitted on
# 2026-08-28 as "not a published Anthropic model name this table's authoring
# conventions can source a real rate for" -- see the BLOCKER 4 note below,
# which is now STALE. Fable 5 IS published, at $10/$50 per MTok (verified
# 2026-09-05 against platform.claude.com/docs/en/about-claude/pricing), and
# 15 live ledger rows carrying 268M tokens were being silently dropped from
# every by-model chart and priced at nothing. Mythos 5 shares Fable's rate
# and is added with it; both use the standard 0.1x cache-read / 1.25x
# 5-minute-cache-write multipliers.
#
# ORDER MATTERS: matching is first-needle-wins by substring, so a more
# specific needle must precede any needle that is a substring of it. These
# four are mutually non-overlapping today; keep it that way when adding.
_MODEL_FAMILY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("opus", "opus"),
    ("sonnet", "sonnet"),
    ("haiku", "haiku"),
    ("fable", "fable"),
    ("mythos", "fable"),
)

_TOKEN_FIELDS: tuple[str, ...] = ("input", "output", "cache_read", "cache_creation")


def normalize_model(model: object) -> str:
    """Map a raw ledger `model` value to a pricing family, or "unknown".

    Pure. Never raises -- any non-string or unmatched string is "unknown" by
    design (see module docstring): guessing a family for an unrecognized
    model string is exactly the kind of guess this module refuses to make.
    """
    if not isinstance(model, str) or not model:
        return "unknown"
    lowered = model.lower()
    for needle, family in _MODEL_FAMILY_PATTERNS:
        if needle in lowered:
            return family
    return "unknown"



# BLOCKER 2 (round 6, 2026-08-28): tolerance for the `tokens_total`
# cross-check below. Every ledger-writer-produced field is an integer token
# count, so an honest row's `tokens_total` should equal
# `sum(_TOKEN_FIELDS)` EXACTLY -- this tolerance exists only to absorb float
# round-trip noise (e.g. a `tokens_total` that arrived via JSON as a float),
# never to paper over a real, material mismatch. Any gap this small can
# never hide a real billable field (those are always many thousands of
# tokens at minimum) -- it exists purely so a float-vs-int representation
# difference of the identical value can never itself trigger a false
# "unknown".
_TOKENS_TOTAL_TOLERANCE = 1e-6

# BLOCKER 2 (round 11 review finding, round 12 fix, 2026-08-28): a sentinel
# distinct from a real value (including the real, meaningful value `None`)
# so `price_tokens_usd()` can tell apart two different callers that both
# end up passing "nothing": (a) a caller that genuinely never supplies a
# `tokens_total` argument at all -- e.g. a low-level unit test exercising
# pricing logic in isolation -- which must keep skipping the cross-check
# exactly as before this round (purely additive, no behavior change); and
# (b) `attribute_cycle_spend()`'s own two call sites, which always pass
# `row.get("tokens_total")` for a REAL ledger row -- where a missing key or
# an explicit JSON `null` both evaluate to Python `None`, and BOTH mean the
# row's own `tokens_total` field is absent/malformed, not "the caller
# declined the check". Defaulting the parameter to this sentinel (never to
# `None`) lets an explicitly-passed `tokens_total=None` mean the latter --
# UNPRICEABLE -- while an omitted argument still means the former.
_TOKENS_TOTAL_NOT_SUPPLIED = object()


def price_tokens_usd(
    tokens: object,
    model_family: str,
    price_table: dict[str, dict[str, float]],
    tokens_total: object = _TOKENS_TOTAL_NOT_SUPPLIED,
) -> float | None:
    """USD cost of one ledger row's `tokens` dict for `model_family`.

    Returns None (never 0.0) when the cost cannot be confidently computed:
    the family is not in `price_table` (includes "unknown"), `tokens` is not
    a dict, a required field is MISSING (BLOCKER 2, round 6, 2026-08-28--
    `field not in tokens`, distinct from a field present with value `0`) or
    present but non-numeric/negative, the price table lacks a rate for a
    field actually present, or (when `tokens_total` is supplied and itself
    looks like a real number) it disagrees with `sum(_TOKEN_FIELDS)` by more
    than `_TOKENS_TOTAL_TOLERANCE`.

    Two independent defenses catch a future billable token field this
    table's `_TOKEN_FIELDS` tuple does not yet enumerate (a long-context
    tier, `cache_creation_1h`, reasoning tokens, etc.):

      * an UNKNOWN KEY present in `tokens` at all (round 8, 2026-08-28,
        finding #6) -- checked unconditionally, independent of whether the
        writer folded that field's value into `tokens_total`. The
        `tokens_total` cross-check below is opt-in on the WRITER: it only
        catches an extra field if the writer's own `tokens_total` also
        reflects it, so a writer that adds a new billable key but forgets
        (or has not yet been updated) to fold it into `tokens_total` sails
        straight through the cross-check alone. A key this function does
        not recognize is never assumed to be free.
      * the `tokens_total` cross-check itself: the ledger already writes
        `tokens_total` as the row's own true total, so a MATERIAL gap
        between that and the sum of the fields this function actually
        knows about means a real, unpriced field is silently present --
        exactly the case this function must never treat as "no cost for
        that field" ($0). Omitting the `tokens_total` argument entirely
        (the default, and every pre-round-6 call site) skips this SECOND
        check only -- purely additive, never a behavior change for a
        caller that cannot supply it. The unknown-key check above still
        runs regardless of `tokens_total`. BLOCKER 2 (round 11 review
        finding, round 12 fix, 2026-08-28): an EXPLICITLY passed
        `tokens_total=None` is a DIFFERENT thing from omitting the
        argument -- it means a real ledger row's own `tokens_total` field
        is missing or JSON `null`, which this function now treats as
        UNPRICEABLE (returns `None`), never as "skip the check". A caller
        priceing a real ledger row (both of `attribute_cycle_spend()`'s
        own call sites) always passes `row.get("tokens_total")`, so a row
        that never wrote this field is now correctly refused rather than
        silently passing cross-check-free.

    A None return is a signal to the caller to treat the WHOLE attribution
    as unknown, never to treat this one row as free.
    """
    if model_family not in price_table:
        return None
    rates = price_table[model_family]
    if not isinstance(tokens, dict):
        return None
    # BLOCKER #6 (round 8, 2026-08-28): an UNKNOWN key present in `tokens`
    # at all -- regardless of whether the writer also folded its value into
    # `tokens_total` -- means a real billable field this function does not
    # know how to price may be silently present. See the docstring above.
    if set(tokens.keys()) - set(_TOKEN_FIELDS):
        return None
    total = 0.0
    token_sum = 0.0
    for field in _TOKEN_FIELDS:
        if field not in tokens:
            return None
        raw = tokens[field]
        if raw is None:
            raw = 0
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        if raw < 0:
            return None
        rate = rates.get(field)
        if rate is None:
            return None
        token_sum += float(raw)
        total += (float(raw) / 1_000_000.0) * float(rate)
    if tokens_total is not _TOKENS_TOTAL_NOT_SUPPLIED:
        # BLOCKER 2 (round 12, 2026-08-28): an explicitly-passed value --
        # including `None` -- is a real assertion about a real ledger
        # row's own `tokens_total` field, not an opt-out. `None` here means
        # the field is missing/JSON-null on that row: unpriceable, exactly
        # like any other malformed required field this function refuses.
        if tokens_total is None:
            return None
        if isinstance(tokens_total, bool) or not isinstance(tokens_total, (int, float)):
            return None
        if abs(float(tokens_total) - token_sum) > _TOKENS_TOTAL_TOLERANCE:
            return None
    return total


# BLOCKER 3 (round 8, 2026-08-28): the real, known pricing-family names
# `normalize_model()` can ever produce (excluding its own "unknown"
# sentinel, which is never a key any real model normalizes to something
# priceable under). `_validate_pricing_table()` uses this as an allowlist
# rather than merely rejecting the literal string "unknown" -- an
# override table naming any OTHER invented/misspelled family is just as
# unpriceable in practice (normalize_model() can never route a real model
# string to it either) and just as capable of silently masking a real
# validation gap.
_KNOWN_MODEL_FAMILIES: frozenset[str] = frozenset(family for _, family in _MODEL_FAMILY_PATTERNS)


def _validate_pricing_table(table: object) -> bool:
    """True iff `table` has the shape PRICING_USD_PER_MTOK requires.

    BLOCKER 3 (round 8, 2026-08-28): a prior version of this check accepted
    ANY dict key at all -- including the literal "unknown" sentinel
    `normalize_model()` returns for every unrecognized/null model -- and
    any non-negative rate, including exactly `0.0`. A `--pricing-file`
    override of the shape `{"unknown": {...all rates 0.0...}}` therefore
    passed validation and then PRICED every row this module is specifically
    designed to REFUSE to price (see `normalize_model()`'s own docstring:
    an unrecognized model normalizing to "unknown" must never be silently
    priced) -- turning the entire unpriced-model safety gate off via a
    confident $0.00 verdict. A real pricing family with an all-zero rate
    table is the identical failure by a different route (it silently zeros
    out real spend for a family this module WOULD otherwise price
    correctly), so both are rejected the same way here: (a) every key must
    be one of the real, known pricing families `normalize_model()` can
    actually produce (`_KNOWN_MODEL_FAMILIES`, built from `_MODEL_FAMILY_
    PATTERNS`'s own family names) -- "unknown" is never a member of that
    set BY CONSTRUCTION, so it is rejected without needing its own special
    case, and so is any other invented/misspelled family name; (b) every
    rate must be STRICTLY POSITIVE, not merely non-negative -- a `0.0` rate
    for a real, known family is just as capable of silently zeroing out
    real spend as an "unknown" entry is.
    """
    if not isinstance(table, dict) or not table:
        return False
    for family, rates in table.items():
        if family not in _KNOWN_MODEL_FAMILIES:
            return False
        if not isinstance(rates, dict):
            return False
        for field in _TOKEN_FIELDS:
            value = rates.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            if value <= 0:
                return False
    return True


def _load_pricing_file(path: str) -> dict[str, dict[str, float]] | None:
    """Load and validate a pricing-table override file. None on any failure."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if _validate_pricing_table(data) else None


# ---------------------------------------------------------------------------
# Timestamp helpers -- ledger rows use the runtime's standard UTC stamp
# (`_lib._now()`'s format); caller-supplied boundaries accept that same
# format or a general ISO-8601 string, always normalized to UTC.
# ---------------------------------------------------------------------------


def _parse_ts(ts: str) -> datetime:
    """Parse a timestamp string to an aware UTC datetime. Raises ValueError."""
    if not isinstance(ts, str) or not ts:
        raise ValueError(f"timestamp must be a non-empty string, got {ts!r}")
    try:
        return datetime.strptime(ts, TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"unparsable timestamp: {ts!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def _validate_expected_dispatch_count(value: int | None) -> None:
    """BLOCKER 7 (round 4, 2026-08-28): `expected_dispatch_count`'s TYPE was
    previously unvalidated -- `False`/`0.0` both alias to a valid-looking 0
    (`bool` is an `int` subclass in Python; `0.0 < 0` is a legal comparison
    that just happens to pass), and a `str` raised a raw, uncaught
    `TypeError` at the `< 0` comparison instead of the module's documented
    "raises ValueError for caller misuse" contract. `None` (the caller
    explicitly declining to assert a count) is always valid. Called at the
    top of both `attribute_cycle_spend()` and `decide_cycle_budget()` so
    neither function can be reached with a malformed count, regardless of
    which one a caller calls directly."""
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            "expected_dispatch_count must be an int or None, got "
            f"{value!r} ({type(value).__name__})"
        )
    if value < 0:
        raise ValueError("expected_dispatch_count must be >= 0")


def _row_ts(row: dict[str, object]) -> datetime | None:
    """The row's own timestamp, or None if missing/unparsable (never raises)."""
    ts = row.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        return _parse_ts(ts)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ledger I/O -- the ONLY place this module touches disk for the spend
# ledger. Read-only, always; this module never writes spend.jsonl.
# ---------------------------------------------------------------------------


def _safe_load_ledger_rows(
    ledger_path: str,
) -> tuple[list[dict[str, object]] | None, int]:
    """Read every JSON object line of `ledger_path`.

    Returns (rows, malformed_line_count). `rows` is None ONLY when the
    ledger could not be opened/read at all (missing file, permission error,
    OS-level failure) -- the fail-CLOSED signal callers turn into an
    explicit `unknown` attribution. A ledger that opens fine but contains
    some unparsable/non-object lines returns whatever DID parse plus a
    non-zero `malformed_line_count`, mirroring agent_budget.py's own
    established convention: one bad line (e.g. a writer crashed mid-line)
    is data noise, not proof the whole ledger is unusable.
    """
    if not ledger_path or not os.path.isfile(ledger_path):
        return None, 0
    rows: list[dict[str, object]] = []
    malformed = 0
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    malformed += 1
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
                else:
                    malformed += 1
    except OSError:
        return None, 0
    return rows, malformed


def _apply_identity_recovery(
    rows: list[dict[str, object]], identity_index: Mapping[str, object] | None
) -> list[dict[str, object]]:
    """Best-effort `spend_attribution.enrich_rows()` pass. See module
    docstring's IDENTITY RECOVERY section.

    Never raises and never changes row COUNT/ORDER -- on ANY problem
    (`identity_index` falsy, `spend_attribution` unimportable, or the call
    itself raising) this returns `rows` completely unchanged, which is
    byte-for-byte this module's behavior before recovery existed. Recovery
    failing is therefore always safe: the classification loop below simply
    sees the same raw rows it always has.
    """
    if not identity_index:
        return rows
    try:
        import spend_attribution
    except Exception:
        return rows
    try:
        return spend_attribution.enrich_rows(rows, identity_index)
    except Exception:
        return rows


def _default_ledger_path(environ: dict[str, str]) -> str:
    """Default spend ledger path: $CSA_CYCLE_LEDGER, else ~/.claude/.agent_budget/spend.jsonl.

    Computed at CALL time from the supplied environ mapping (never at import
    time) so tests can point this at a sandboxed ledger without monkeypatching
    module globals.
    """
    override = environ.get("CSA_CYCLE_LEDGER")
    if override:
        return override
    home = environ.get("HOME") or os.path.expanduser("~")
    return os.path.join(home, ".claude", ".agent_budget", "spend.jsonl")


# ---------------------------------------------------------------------------
# Result types.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CycleAttribution:
    """The result of attempting to attribute ledger spend to one cycle."""

    status: str  # "known" | "unknown"
    spent_usd: float | None
    reason: str | None
    system: str
    session_id: str
    window_start: str
    window_end: str
    matched_rows: int
    ambiguous_rows: int
    excluded_rows: int
    unpriced_rows: int
    malformed_lines: int
    collapsed_duplicate_rows: int = 0
    recovered_agent_type_rows: int = 0
    recovered_model_rows: int = 0
    undated_matched_rows: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "spent_usd": self.spent_usd,
            "reason": self.reason,
            "system": self.system,
            "session_id": self.session_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "matched_rows": self.matched_rows,
            "ambiguous_rows": self.ambiguous_rows,
            "excluded_rows": self.excluded_rows,
            "unpriced_rows": self.unpriced_rows,
            "malformed_lines": self.malformed_lines,
            "collapsed_duplicate_rows": self.collapsed_duplicate_rows,
            "recovered_agent_type_rows": self.recovered_agent_type_rows,
            "recovered_model_rows": self.recovered_model_rows,
            "undated_matched_rows": self.undated_matched_rows,
        }


@dataclass(frozen=True)
class CycleBudgetDecision:
    """The result of `decide_cycle_budget()` -- what a dispatcher gates on."""

    allowed: bool
    status: str  # "known" | "unknown"
    spent_usd: float | None
    ceiling_usd: float
    remaining_usd: float | None
    reason: str
    attribution: CycleAttribution

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "spent_usd": self.spent_usd,
            "ceiling_usd": self.ceiling_usd,
            "remaining_usd": self.remaining_usd,
            "reason": self.reason,
            "attribution": self.attribution.to_dict(),
        }


def _unknown_attribution(
    *,
    reason: str,
    system: str,
    session_id: str,
    window_start: str,
    window_end: str,
    matched_rows: int = 0,
    ambiguous_rows: int = 0,
    excluded_rows: int = 0,
    unpriced_rows: int = 0,
    malformed_lines: int = 0,
    collapsed_duplicate_rows: int = 0,
    recovered_agent_type_rows: int = 0,
    recovered_model_rows: int = 0,
    undated_matched_rows: int = 0,
) -> CycleAttribution:
    return CycleAttribution(
        status="unknown",
        spent_usd=None,
        reason=reason,
        system=system,
        session_id=session_id,
        window_start=window_start,
        window_end=window_end,
        matched_rows=matched_rows,
        ambiguous_rows=ambiguous_rows,
        excluded_rows=excluded_rows,
        unpriced_rows=unpriced_rows,
        malformed_lines=malformed_lines,
        collapsed_duplicate_rows=collapsed_duplicate_rows,
        recovered_agent_type_rows=recovered_agent_type_rows,
        recovered_model_rows=recovered_model_rows,
        undated_matched_rows=undated_matched_rows,
    )


def _collapse_duplicate_agent_id_rows(
    rows: list[dict[str, object]],
    price_table: dict[str, dict[str, float]],
    *,
    correlated_flags: list[bool] | None = None,
    known_agent_types: frozenset[str] | None = None,
) -> tuple[list[dict[str, object]], int, int, int]:
    """Collapse same-`agent_id` duplicate rows to a single reading before
    summing spend. BLOCKER 3 (2026-08-28): the SAME agent_id can appear as
    two independent ledger lines -- a normal claim/release plus a LATER,
    LARGER cumulative 'stopped-unjoined' reap of the SAME agent's still-
    running spend (see spend_attribution.py's module docstring for the
    measured real example) -- and naively summing every MATCHED row would
    double-count that one agent's real spend. Only the row with the largest
    reading per duplicate-agent_id group is priced; every other same-
    agent_id row is dropped from the PRICING sum only (never from
    `matched_rows`'s own count, which still reflects every row that matched
    this cycle by session OR by agent_id correlation -- round 8). A row
    with no/blank `agent_id` is never grouped.

    ROUND 4 (2026-08-28), replacing round 3's own (wrong) BLOCKER 4 fix:

      BLOCKER 1: the winner is now selected by each candidate's actual
      computed DOLLAR value -- `price_tokens_usd()` itself, the identical
      function that later prices the survivor -- never by a raw token
      count of any kind. A raw-token-count winner can be wrong by >20x
      because token fields are priced at very different rates (e.g. sonnet
      output tokens are ~50x the $/token of cache_read tokens): a row with
      fewer, more-expensive tokens can be the real larger spend. An
      unpriceable candidate (`price_tokens_usd()` returns None) always
      sorts strictly BELOW every priceable one, so it can never be crowned
      winner merely by looking numerically large.

      BLOCKER 2: every candidate in a duplicate-agent_id group is now
      price-checked, not just the winner -- `unpriceable_dropped_count`
      (the 3rd return value) counts how many DROPPED (non-winner) rows in
      any group could not be priced at all. Without this, a malformed/
      unpriceable row sharing an agent_id with a clean sibling would simply
      vanish from the pricing sum when it lost the winner comparison,
      invisible to the unpriced-model-in-window safety net that correctly
      catches the identical row if it had no duplicate to hide behind. The
      caller folds this count into the same `unpriced_rows` total that
      already forces `unknown` for a lone unpriceable row.

    KNOWN, ACCEPTED TRADEOFF (round 8, 2026-08-28, finding #7): the 2+-
    distinct-`tool_use_id` rule below can OVER-count when a group also
    contains an embedded, null-`tool_use_id` REAP of one of the group's own
    real rows (verified: a group of one real $3 row, one real $3 row with a
    distinct tool_use_id, plus a null-tool_use_id reap of the first row's
    same underlying dispatch reports $9 for $6 of genuine spend). This is
    the fail-CLOSED direction for a spend-ceiling guard (over-counting
    spend denies slightly early; under-counting would allow slightly late
    -- the actual dangerous direction) and is genuine parity with
    `churn_report.py`'s own `dedup_spend_lines()` for the identical input
    bytes -- but it means this rule is not presented here as always
    producing the exactly-right dollar figure, only as never producing an
    UNDER-count.

    KNOWN, ACCEPTED TRADEOFF #2 (round 14, 2026-08-28, review finding #3):
    two cycle windows on the SAME session that genuinely OVERLAP (e.g.
    cycle A `[09:00, 12:00]` and cycle B `[11:00, 14:00]` sharing a session
    id) can each independently, and CORRECTLY per their own window math,
    count the identical real dollar amount -- an agent anchored at 11:30
    (inside BOTH windows) with a reap at 15:00 reports known/$30.00 for
    cycle A AND known/$30.00 for cycle B, the same $30.00 counted twice
    across the two reports. This module's own window semantics operate
    entirely per-call, on ONE `[start_dt, end_dt]` pair at a time -- it has
    no way to see a SIBLING cycle's own window and would need one to
    de-duplicate this case. This is accepted, not a bug to fix here, for
    the same fail-CLOSED reasoning as tradeoff #1 above: double-counting
    overlapping-window spend denies slightly early (safe); the module's
    documented OPERATING PRECONDITION is that a caller's own cycle windows
    for a given session are non-overlapping -- a caller that schedules
    genuinely overlapping cycles against the same session id is outside
    that precondition and should expect exactly this double-count, not a
    silent split of the real spend between the two reports (which would
    require this module to guess which cycle a shared row "really"
    belongs to -- precisely the kind of guess this module exists to
    refuse).

    ROUND 6 (2026-08-28), BLOCKER 3 -- this collapse used to key SOLELY on
    `agent_id`, diverging from `churn_report.py`'s OWN `dedup_spend_lines()`
    (cited by name as authoritative in both this module's and
    spend_attribution.py's docstrings), which dedups by `tool_use_id` and
    correctly never collapses two rows carrying DISTINCT non-null
    `tool_use_id`s -- those are, by construction, two independent real Task
    dispatches, never two readings of the same one. Collapsing them into a
    single winner silently discarded real, independent spend (a 2x
    under-report in the reviewer's repro: two `tool_use_id`-distinct $3.00
    rows collapsed to one, reporting $3.00 instead of the real $6.00).

    FIX (round 6): within each agent_id group, first collect every DISTINCT
    non-null, str `tool_use_id` present. If 2 or more distinct values are
    present, this group is definitively NOT "one dispatch read twice" --
    it is provably 2+ INDEPENDENT dispatches that merely happen to share an
    agent_id -- so the group is left COMPLETELY UNCOLLAPSED: every row in
    it is priced and SUMMED independently, exactly as churn_report.py's own
    dedup_spend_lines() already treats the identical bytes (chosen over
    forcing `unknown` for the group, because a distinct, non-null
    `tool_use_id` on each side is itself strong, direct evidence of two
    real dispatches -- refusing to sum genuinely-known, separately-
    identified spend would be a worse failure mode than the double-counting
    this function exists to prevent, and would also silently diverge from
    churn_report.py's own established, cited-as-authoritative answer for
    the identical input). A group with 0 or exactly 1 distinct non-null
    `tool_use_id` (the case this collapse was actually designed for -- a
    normal claim/release plus a later `tool_use_id: null` 'stopped-
    unjoined' reap of the SAME dispatch) is collapsed exactly as before,
    by largest computed dollar value.

    BLOCKER 3 (round 10, 2026-08-28): a row this collapse DROPS can be one
    that only reached the caller's `matched` population via agent_id
    correlation (round 8) -- i.e. its own `session` was never proven to be
    this cycle's own. Dropping such a row is safe when it looks like a
    genuine duplicate reading of an ALREADY-attributed dispatch, but if its
    original (pre-collapse) `agent_type` is itself one this cycle
    declared, the module cannot actually tell "duplicate reading of known
    spend" apart from "independent, additional spend from a same-agent_id
    but different dispatch" -- exactly the ambiguity round 7's IDENTITY
    RECOVERY contract ("never turns AMBIGUOUS into MATCHED") exists to
    refuse to guess. `correlated_flags` (parallel to `rows`, `True` where
    that row reached `matched` via agent_id correlation rather than a
    direct session match) and `known_agent_types` are OPTIONAL: omitting
    either preserves this function's pre-round-10 behavior exactly (a
    direct-session-match row is never subject to this check regardless --
    both readings are already proven to be this session's own, so
    collapsing them remains the intentional, safe behavior rounds 3/4
    built). When both are supplied, the 4th return value counts how many
    DROPPED rows meet this exact ambiguous condition; the caller forces
    `unknown` when it is non-zero rather than silently accepting the
    collapse's chosen winner.

    Returns (rows-to-actually-price, collapsed_row_count,
    unpriceable_dropped_count, ambiguous_dropped_declared_count)."""
    groups: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        agent_id = row.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            groups.setdefault(agent_id, []).append(i)

    def _priced_value(i: int) -> float | None:
        family = normalize_model(rows[i].get("model"))
        return price_tokens_usd(rows[i].get("tokens"), family, price_table, rows[i].get("tokens_total"))

    def _distinct_tool_use_ids(idxs: list[int]) -> set[str]:
        ids: set[str] = set()
        for i in idxs:
            tid = rows[i].get("tool_use_id")
            if isinstance(tid, str) and tid:
                ids.add(tid)
        return ids

    drop: set[int] = set()
    unpriceable_dropped = 0
    ambiguous_dropped_declared = 0
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        if len(_distinct_tool_use_ids(idxs)) >= 2:
            # BLOCKER 3 (round 6): 2+ distinct non-null tool_use_ids proves
            # these are independent dispatches, never a duplicate reading
            # of the same one -- do not collapse any row in this group.
            continue
        prices = {i: _priced_value(i) for i in idxs}
        winner = max(
            idxs,
            key=lambda i: (prices[i] is not None, prices[i] if prices[i] is not None else 0.0, -i),
        )
        for i in idxs:
            if i == winner:
                continue
            drop.add(i)
            if prices[i] is None:
                unpriceable_dropped += 1
            # BLOCKER 3 (round 10, 2026-08-28): see this function's own
            # docstring section by the same name. A dropped row is only
            # ambiguous (not a safe duplicate-of-known-spend collapse) when
            # it (a) reached `matched` via agent_id correlation, never a
            # direct session match, AND (b) its original-or-effective
            # agent_type is itself one this cycle declared.
            if (
                correlated_flags is not None
                and known_agent_types is not None
                and i < len(correlated_flags)
                and correlated_flags[i]
                and _ambiguous_agent_type_candidates(rows[i]) & known_agent_types
            ):
                ambiguous_dropped_declared += 1
    kept = [row for i, row in enumerate(rows) if i not in drop]
    return kept, len(drop), unpriceable_dropped, ambiguous_dropped_declared


def _count_recovered_fields(rows: list[dict[str, object]]) -> tuple[int, int]:
    """How many of `rows` had `agent_type`/`model` RECOVERED (not
    first-party) per spend_attribution's own provenance block. BLOCKER 5
    (2026-08-28): this module's classification/pricing logic reads only the
    bare, already-overwritten `row["agent_type"]`/`row["model"]` fields --
    it must ALSO actually read `row["attribution"]` so a caller can tell
    that a 'known' verdict rests partly on an INFERRED, not measured,
    identity (the exact scenario that can flip a real denial into a real
    allowance). A row with no `attribution` block at all (no identity_index
    was supplied, or spend_attribution enrichment never ran) contributes to
    neither count -- there is nothing to read."""
    agent_type_count = 0
    model_count = 0
    for row in rows:
        attribution = row.get("attribution")
        if not isinstance(attribution, dict):
            continue
        agent_type_block = attribution.get("agent_type")
        if isinstance(agent_type_block, dict) and agent_type_block.get("provenance") == "recovered":
            agent_type_count += 1
        model_block = attribution.get("model")
        if isinstance(model_block, dict) and model_block.get("provenance") == "recovered":
            model_count += 1
    return agent_type_count, model_count


def _session_matched_agent_ids(
    rows: list[dict[str, object]], session_id: str
) -> frozenset[str]:
    """Every real `agent_id` present on a row whose `session` already
    equals this cycle's own `session_id` -- built from EVERY such row,
    regardless of that row's own timestamp/window (BLOCKER 4, round 8,
    2026-08-28; see module docstring's ROUND 8 CORRECTION section).

    This is a pure identity fact -- "session `session_id` dispatched
    `agent_id` X" -- and, like `spend_attribution.py`'s own same-ledger
    sibling join (`_build_ledger_sibling_facts()`), it does not expire at a
    window boundary: a session match established outside this cycle's own
    start/end still proves the identical thing about that `agent_id` that
    an in-window match would. The set this returns is consulted by the main
    classification loop to decide whether an otherwise-unjoined row is
    actually a same-agent reading of a row already proven to be this
    cycle's own.
    """
    ids: set[str] = set()
    for row in rows:
        if row.get("session") != session_id:
            continue
        agent_id = row.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            ids.add(agent_id)
    return frozenset(ids)


def _session_matched_agent_ids_this_window(
    rows: list[dict[str, object]],
    session_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> frozenset[str]:
    """A NARROWER sibling of `_session_matched_agent_ids()` -- BLOCKER 1
    (round 12, 2026-08-28). Used ONLY to gate the after-window correlation
    exemption inside `attribute_cycle_spend()`'s main loop; NEVER to decide
    `is_agent_id_correlated` itself, which must stay window-independent
    (round 10's own mutant-2 test, `test_falsify_session_matched_agent_ids_
    includes_undated_anchor_rows`, depends on that and must keep passing).

    The general, window-independent anchor set answers "does agent_id X
    belong to THIS session, ever" -- true, but insufficient to justify the
    after-window exemption at the `row_dt > end_dt` check below. That
    exemption's entire rationale is "this correlated row is a LATER reap of
    work THIS CYCLE already proved happened" (see module docstring). That
    rationale only holds when the row that PROVED it -- the anchor -- itself
    genuinely belongs to THIS cycle's own [start_dt, end_dt] window, not
    some OTHER cycle sharing the same long-lived session id. A cycle's
    session id is not unique to that one cycle: the same orchestrating
    session can run many bounded cycles back to back, each with its own
    start/end. A session-matched row dated AFTER this cycle's own end is
    definitionally a LATER cycle's own direct dispatch, not evidence for
    this one; a session-matched row dated BEFORE this cycle's own start is
    likewise some EARLIER cycle's own spend. Either way, excluding that
    row's agent_id from this restricted set is what stops that OTHER
    cycle's own after-window reap from being charged backwards (or
    forwards) onto THIS cycle.

    An anchor row whose own `ts` is unparsable is never excluded here --
    mirrors `_session_matched_agent_ids()`'s own undated handling: there is
    no basis to say an undated row belongs to some OTHER cycle rather than
    this one, so it stays a valid anchor for this restricted set too.
    """
    ids: set[str] = set()
    for row in rows:
        if row.get("session") != session_id:
            continue
        agent_id = row.get("agent_id")
        if not (isinstance(agent_id, str) and agent_id):
            continue
        row_dt = _row_ts(row)
        if row_dt is not None and (row_dt < start_dt or row_dt > end_dt):
            continue
        ids.add(agent_id)
    return frozenset(ids)


def _this_cycle_anchor_tool_use_ids(
    rows: list[dict[str, object]],
    session_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, frozenset[str]]:
    """Per-`agent_id` set of non-null, non-empty `tool_use_id`s seen on THIS
    cycle's own session-matched, in-window anchor rows -- BLOCKER 3 (round
    18, 2026-08-28).

    `is_after_window_agent_id_match()`'s own agent_id-only channel and
    `_collapse_duplicate_agent_id_rows()`'s own tool_use_id-based rule
    (module docstring's DUPLICATE-AGENT_ID SPEND / ROUND 6 sections: 2+
    DISTINCT non-null `tool_use_id`s on one `agent_id` proves 2+
    INDEPENDENT dispatches, never one dispatch read twice) were two
    DIFFERENT axioms about what proves "the same dispatch" -- an
    after-window row could be PULLED IN on the strength of a shared
    `agent_id` alone, then the collapse's own, stricter rule would refuse
    to treat it as the same dispatch as its anchor, silently SUMMING a
    genuinely independent dispatch's spend into this cycle's own total
    rather than ever excluding it as the "not evidence for this cycle"
    row it actually is.

    CORRECTED (round 20, 2026-08-28): round 18 wired this compatibility
    check into `is_after_window_agent_id_match()`'s OWN predicate, which
    only ever governs ONE of the three routes that reach the shared
    after-window admission gate (`is_after_window_exempt` in
    `attribute_cycle_spend()`'s main loop) -- a null-session candidate
    (`is_agent_id_correlated`) or a literal, possibly-stale direct session
    match (`is_session_match`) reaching that SAME gate never consulted
    this helper at all, so either could still disagree with the collapse's
    own rule exactly as described above. As of round 20 this helper is
    consulted directly by the SHARED `is_after_window_exempt` check
    itself, governing every route uniformly: a candidate is admitted only
    when its own `tool_use_id` is null (matches what a real
    `stopped-unjoined` reap row actually looks like) or is genuinely one
    of the tool_use_ids returned here for that `agent_id` -- a candidate
    with a DIFFERENT, non-null `tool_use_id` than every one already
    established for that `agent_id` this cycle is, by the collapse's own
    rule, proof of a second, independent dispatch, not a reap of the
    anchor's own, regardless of which of the three routes it arrived by.

    An `agent_id` with zero non-null anchor `tool_use_id`s (every anchor
    row for it happened to carry a null `tool_use_id` too) maps to an
    empty `frozenset` -- there is nothing yet PROVEN to conflict with, so
    a single non-null candidate stays compatible (the collapse's own rule
    only fires at 2+ DISTINCT non-null values; one is never enough). This
    is intentional (see `test_falsify_after_window_empty_anchor_tool_use_
    ids_admits_arbitrary_candidate` in `test_cycle_budget.py`)."""
    ids: dict[str, set[str]] = {}
    for row in rows:
        if row.get("session") != session_id:
            continue
        agent_id = row.get("agent_id")
        if not (isinstance(agent_id, str) and agent_id):
            continue
        row_dt = _row_ts(row)
        if row_dt is not None and (row_dt < start_dt or row_dt > end_dt):
            continue
        tool_use_id = row.get("tool_use_id")
        if isinstance(tool_use_id, str) and tool_use_id:
            ids.setdefault(agent_id, set()).add(tool_use_id)
    return {agent_id: frozenset(values) for agent_id, values in ids.items()}


def _ambiguous_agent_type_candidates(row: dict[str, object]) -> frozenset[str]:
    """The set of agent_type values a null-session row's AMBIGUITY test
    must check membership against -- BLOCKER 2 (round 8, 2026-08-28).

    Returns the UNION of the row's EFFECTIVE `agent_type` (which, after
    `spend_attribution.enrich_rows()` has run, may already be a RECOVERED
    value that has overwritten the original) and its ORIGINAL, pre-recovery
    value (read from `row["attribution"]["agent_type"]["original_value"]`,
    when spend_attribution populated one). Module docstring's IDENTITY
    RECOVERY section states recovery may only ever WIDEN this module's
    fail-closed contract, never narrow it -- but the effective-value-only
    check this replaces was a REPLACEMENT, not a union: a row whose
    ORIGINAL agent_type this cycle explicitly declared (a real ambiguity
    candidate on the raw ledger, before any recovery ran at all) could
    resolve, via recovery, to a real but UNDECLARED type and silently
    become EXCLUDED instead -- directly contradicting the module's own
    written guarantee that recovery never turns AMBIGUOUS into EXCLUDED.
    Checking both values as a union closes that regardless of which
    direction recovery moves a row's apparent type.
    """
    candidates: set[str] = set()
    effective = row.get("agent_type")
    if isinstance(effective, str) and effective:
        candidates.add(effective)
    attribution = row.get("attribution")
    if isinstance(attribution, dict):
        agent_type_block = attribution.get("agent_type")
        if isinstance(agent_type_block, dict):
            original = agent_type_block.get("original_value")
            if isinstance(original, str) and original:
                candidates.add(original)
    return frozenset(candidates)


# ---------------------------------------------------------------------------
# The core gating surface.
# ---------------------------------------------------------------------------


def attribute_cycle_spend(
    ledger_path: str,
    *,
    system: str,
    session_id: str,
    cycle_start_ts: str,
    known_agent_types: Iterable[str],
    cycle_end_ts: str | None = None,
    expected_dispatch_count: int | None,
    pricing: dict[str, dict[str, float]] | None = None,
    identity_index: Mapping[str, object] | None = None,
) -> CycleAttribution:
    """Attribute this cycle's real USD spend from the ledger, or refuse to guess.

    Parameters (ALL required except `cycle_end_ts`/`pricing` -- this module
    never infers cycle identity from environment or convention, per the
    repo-agnostic requirement):
      ledger_path            path to the spend.jsonl-shaped ledger.
      system                 caller's own label for the calling system/loop.
                              Bookkeeping ONLY -- spend.jsonl carries no such
                              field, so this is never a filter.
      session_id             the orchestrating Claude Code session id whose
                              dispatches this cycle wants credited. Ledger
                              rows carry a `session` field written at dispatch
                              time; an exact match is the ONLY confident
                              attribution signal this ledger schema offers.
      cycle_start_ts          UTC boundary; rows before this are out of window.
      known_agent_types       the non-empty set of agent_types this cycle
                              may have dispatched. Required (not optional):
                              without it, a `session: null` unjoined row (a
                              large, real fraction of this ledger -- see
                              module docstring) can never be told apart from
                              unrelated background noise from concurrent,
                              unrelated work on the same machine.
      cycle_end_ts            UTC boundary, default now(). Must be >= start.
      expected_dispatch_count REQUIRED (BLOCKER 1, 2026-08-28 round 3 -- no
                              default, every caller must pass something).
                              The caller's own count of dispatches made so
                              far this cycle, or `None` if the caller
                              declines to assert a count at all. A mismatch
                              against the ledger's POST-COLLAPSE distinct
                              dispatch count (see BLOCKER 2 below) is itself
                              grounds for `unknown` (see reasons below).
                              CRITICAL: zero rows matching this cycle's
                              session is EXACTLY the state this module can
                              never, on its own, tell apart from "my
                              session id/window is wrong and my real spend
                              is invisible to this query" -- the real
                              failure mode this module exists to catch (an
                              earlier B0 pilot run's spend went genuinely
                              unattributable this way). A `known`/$0 verdict
                              for zero matched rows therefore requires the
                              caller to have EXPLICITLY passed
                              `expected_dispatch_count=0` -- passing `None`
                              (declining to assert) or any positive int both
                              force `unknown` when nothing matched. This
                              parameter being required (not optional-with-a-
                              None-default) exists precisely so a caller
                              cannot silently opt into the unsafe path by
                              omission -- it must consciously choose `0`,
                              a real count, or `None`.
      pricing                 override for PRICING_USD_PER_MTOK (same shape).
      identity_index          OPTIONAL: a `spend_attribution.RecoveredIdentity`
                              map (agent_id -> identity), applied to every
                              loaded row via `spend_attribution.enrich_rows()`
                              BEFORE classification -- see module docstring's
                              IDENTITY RECOVERY section for why this can only
                              ever widen, never weaken, this function's
                              fail-closed contract. Defaults to `None` (no
                              recovery attempted -- identical to this
                              function's pre-recovery behavior).

    Raises ValueError for CALLER misuse (empty system/session_id, empty
    known_agent_types, unparsable/inverted timestamps, negative
    expected_dispatch_count) -- these are programming errors, never ledger
    ambiguity, and must stay distinguishable from an `unknown` result.

    Never raises for ledger I/O problems -- those come back as a `status=
    "unknown"` CycleAttribution (see `_safe_load_ledger_rows`), which is the
    fail-CLOSED contract this whole module exists to provide.

    ATTRIBUTION ALGORITHM (round 8, 2026-08-28 -- CORRECTS an earlier,
    unsafe version of this whole section; see module docstring's ROUND 8
    CORRECTION for why the ordering itself, not just this text, changed).
    The classifier now runs an AGENT_ID CORRELATION pass BEFORE bucketing
    any row by session, because a row's own `session`/`agent_type` is not
    the only evidence this ledger offers about whose spend it is: a real,
    non-null `agent_id` shared with a row ALREADY proven to be this cycle's
    own (a direct session match, dated or undated) is itself proof the two
    rows are readings of the SAME underlying agent, regardless of what that
    second row's own `session`/`agent_type`/timestamp happen to say (see
    `_session_matched_agent_ids()`). A row outside the time window with no
    such correlation is still dropped from every bucket -- it is simply not
    evidence either way for THIS cycle. A row whose own `ts` is missing/
    unparsable is handled specially in every case below: it is NEVER simply
    "dropped" the way an out-of-window, uncorrelated row is.

      MATCHED    row["session"] == session_id, OR row["agent_id"] is
                 shared with a row that is (regardless of the correlated
                 row's own session/agent_type/window -- BLOCKER 4, round 8:
                 the prior version of this algorithm classified every row
                 independently by its OWN session/type FIRST and only ever
                 collapsed same-agent_id MATCHED rows together AFTERWARD,
                 so a same-agent_id sibling that itself looked unjoined/
                 undeclared was classified as EXCLUDED or AMBIGUOUS in
                 total isolation and could never reach the collapse step at
                 all -- measured live: 44/44 real duplicate-agent_id groups
                 have exactly this shape, a matched row plus an unjoined
                 same-agent_id reap holding the LARGER reading, and every
                 one of them was silently excluded). A dated, in-window
                 correlated row and a dated, in-window direct match are
                 treated identically from here on (both feed
                 `_collapse_duplicate_agent_id_rows()`); a correlated row
                 dated AFTER cycle_end is still included -- unlike a
                 non-correlated row, its own timestamp records when a LATER
                 reap process ran, not when the underlying work happened,
                 so window filtering does not meaningfully apply to it in
                 that direction (BLOCKER 1, round 10, 2026-08-28: narrowed
                 from "either direction" -- a correlated row dated BEFORE
                 cycle_start is genuinely prior-cycle spend, not a later
                 reap, and is dropped like any other out-of-window row) --
                 BUT ONLY when the session-matched row that made it
                 "correlated" (its anchor) is itself genuinely inside THIS
                 cycle's own [start_dt, end_dt] window (BLOCKER 1, round
                 12, 2026-08-28: a session id is not unique to one cycle --
                 the same long-lived session can run many bounded cycles
                 back to back, each with its own window -- so an anchor
                 dated outside THIS cycle's window is some OTHER cycle's
                 own direct dispatch, and that other cycle's own
                 after-window reap must never be charged backwards onto
                 this one; see `_session_matched_agent_ids_this_window()`).
                 A correlated (or directly matched) row whose `ts` cannot be
                 parsed lands in the dedicated `undated_matched_rows`
                 bucket -- exact spend, unknown timing, never silently
                 dropped. A row dropped by the duplicate-agent_id collapse
                 below that is agent_id-correlated AND whose declared
                 agent_type this cycle recognizes is never silently
                 discarded either -- see BLOCKER 3 (round 10) below and
                 `_collapse_duplicate_agent_id_rows()`'s own docstring: it
                 forces the AMBIGUOUS outcome instead.
      AMBIGUOUS  every OTHER row whose `session` is `None`/`""` (an
                 unjoined ledger row -- see module docstring) whose EFFECTIVE
                 agent_type, OR whose ORIGINAL pre-recovery agent_type
                 (BLOCKER 2, round 8 -- a UNION, never a replacement: see
                 module docstring's IDENTITY RECOVERY section), IS one this
                 cycle declared it might dispatch -- a real candidate for
                 "this cycle's spend that failed to join its session id",
                 precisely the failure mode that produced the ~26x
                 under-report this module was built to prevent. This now
                 applies whether or not the row's own `ts` parses (BLOCKER
                 1, round 8 -- corrects round 6's fix, which only handled
                 the SESSION-MATCH half of an unparsable-ts row and left an
                 unjoined, undated, declared-type row silently dropped: a
                 null-session row is NOT known to be someone else's just
                 because its timestamp happens to be unparsable). ANY
                 ambiguous row forces `unknown` -- see below.
      EXCLUDED   everything else: a different, non-null, non-correlated
                 session (definitely someone else's dispatch), or an
                 unjoined row whose agent_type (both effective AND
                 original) this cycle never declared and which shares no
                 agent_id with anything already matched (assumed unrelated
                 background noise -- the one place this module accepts a
                 bounded, documented risk rather than refusing every
                 possible byte of a busy shared ledger; the
                 `expected_dispatch_count` check below is the safety net for
                 a cycle that under-declared its own agent types). An
                 unparsable-ts row belonging to some OTHER, concrete,
                 non-null, non-correlated session is still correctly
                 dropped with no further bookkeeping here -- ambiguous
                 evidence about someone ELSE's spend genuinely isn't
                 evidence about this cycle's own.

    A `status="unknown"` result is returned, in priority order, when:
      1. the ledger cannot be opened/read at all;
      2. any MATCHED row's agent_type is not in `known_agent_types` (session
         matched exactly, yet the type is one this cycle never declared --
         "agent types the cycle never dispatched", called out explicitly);
      3. the `undated_matched_rows` bucket is non-empty (BLOCKER 1, round 6:
         a row genuinely matches this cycle's own session but its `ts`
         could not be parsed -- real spend of unknown timing, never
         silently invisible);
      4. the AMBIGUOUS bucket is non-empty (an unjoined row could belong to
         this cycle and there is no way to confirm or deny it);
      5. zero rows matched this cycle's session AND `expected_dispatch_count`
         is anything other than exactly `0` -- including `None` (BLOCKER 1,
         round 3: no assertion was made at all) or any positive int ("the
         cycle's dispatches do not appear in the ledger AT ALL" -- this
         really happens, per the evidence that motivated this module). The
         ONE way to get a `known`/$0 verdict for zero matched rows is to
         explicitly pass `expected_dispatch_count=0`;
      6. `expected_dispatch_count` is given (not `None`) and disagrees with
         the matched, POST-COLLAPSE (BLOCKER 2, round 3) distinct dispatch
         count -- collapsing same-agent_id duplicate rows to one BEFORE this
         comparison, so an honest cycle that declares "I dispatched N
         agents" is never rejected merely because one of those agents
         legitimately produced two ledger lines (a normal claim/release plus
         a later reap -- see BLOCKER 3 below);
      7. any MATCHED row cannot be priced (`price_tokens_usd` returns None
         -- an unrecognized model family, or a malformed `tokens` field).
    Otherwise `status="known"` and `spent_usd` is the confident USD sum over
    the MATCHED rows only.
    """
    if not isinstance(system, str) or not system:
        raise ValueError("system must be a non-empty string")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session_id must be a non-empty string")
    if isinstance(known_agent_types, (str, bytes)):
        # BLOCKER 1 (2026-08-28): a bare string/bytes value is iterated
        # CHARACTER BY CHARACTER by the frozenset() comprehension below --
        # exactly the natural CLI-parsing mistake (passing the raw
        # `--agent-types` value straight through instead of splitting it).
        # No single character ever matches a real agent_type, so the
        # AMBIGUOUS bucket silently empties and real spend becomes invisible
        # -- the exact laundering this module's own docstring promises never
        # happens. Reject it outright as caller misuse, never as ledger
        # ambiguity.
        raise ValueError(
            "known_agent_types must be a collection of strings, not a bare "
            f"string/bytes ({known_agent_types!r}) -- a bare string is "
            "iterated character-by-character, silently emptying the "
            "ambiguous-row check"
        )
    agent_types = frozenset(t for t in known_agent_types if isinstance(t, str) and t)
    if not agent_types:
        raise ValueError(
            "known_agent_types must declare at least one agent type this cycle may dispatch"
        )
    _validate_expected_dispatch_count(expected_dispatch_count)

    start_dt = _parse_ts(cycle_start_ts)
    end_dt = _parse_ts(cycle_end_ts) if cycle_end_ts is not None else datetime.now(timezone.utc)
    if end_dt < start_dt:
        raise ValueError("cycle_end_ts precedes cycle_start_ts")
    window_start = _fmt_ts(start_dt)
    window_end = _fmt_ts(end_dt)

    price_table = pricing if pricing is not None else PRICING_USD_PER_MTOK

    rows, malformed = _safe_load_ledger_rows(ledger_path)
    if rows is None:
        return _unknown_attribution(
            reason="ledger-unreadable",
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
        )
    rows = _apply_identity_recovery(rows, identity_index)

    # BLOCKER 4 (round 8, 2026-08-28): the identity-correlation pass runs
    # BEFORE any row is bucketed by session -- see module docstring's ROUND
    # 8 CORRECTION and `attribute_cycle_spend()`'s own ATTRIBUTION
    # ALGORITHM section above for the full rationale. `anchor_agent_ids` is
    # the set of `agent_id`s already PROVEN to belong to this cycle via a
    # direct session match, computed once, up front, over every row
    # (window-independent -- see `_session_matched_agent_ids()`).
    anchor_agent_ids = _session_matched_agent_ids(rows, session_id)
    # BLOCKER 1 (round 12, 2026-08-28): a NARROWER anchor set, scoped to
    # THIS cycle's own [start_dt, end_dt] window, with three real
    # consumers below: `is_after_window_agent_id_match` (~line 1834),
    # `is_after_window_exempt` (~line 1938), and the `correlation_rejected`
    # check (~line 1857, which fires at any window position, not just
    # after-window) -- see `_session_matched_agent_ids_this_window()`'s own
    # docstring for why the general `anchor_agent_ids` above is
    # deliberately insufficient for any of them.
    this_cycle_anchor_agent_ids = _session_matched_agent_ids_this_window(
        rows, session_id, start_dt, end_dt
    )
    # BLOCKER 3 (round 18, 2026-08-28): consulted by
    # `is_tool_use_id_compatible` below, which the SHARED
    # `is_after_window_exempt` gate applies uniformly to all three
    # after-window routes.
    this_cycle_anchor_tool_use_ids = _this_cycle_anchor_tool_use_ids(
        rows, session_id, start_dt, end_dt
    )

    matched: list[dict[str, object]] = []
    # Parallel to `matched` (same length, same order): True where that row
    # reached `matched` via agent_id correlation rather than a direct
    # session match. BLOCKER 3 (round 10, 2026-08-28): needed so the
    # duplicate-agent_id collapse below can tell a genuinely-ambiguous
    # dropped row apart from a safe, already-proven-same-session one.
    matched_is_correlated: list[bool] = []
    ambiguous_count = 0
    excluded_count = 0
    unexpected_type_count = 0
    undated_matched_count = 0

    for row in rows:
        row_dt = _row_ts(row)
        row_session = row.get("session") or None
        row_agent_id = row.get("agent_id")
        is_session_match = row_session == session_id
        # BLOCKER 4: an unjoined row (`session` is None) sharing a real
        # `agent_id` with a row already proven to belong to this cycle is
        # identity-correlated -- fold it into the SAME population a direct
        # session match uses, regardless of its OWN agent_type/window. A
        # row belonging to some OTHER, concrete, non-null session dated
        # INSIDE this cycle's own window is never pulled in this way even
        # if it happens to share an agent_id: an IN-WINDOW row with its own
        # populated, DIFFERENT session is a live, contemporaneous
        # declaration by that OTHER session, not evidence of a reap, and
        # merging it would let a genuinely independent dispatch's real
        # spend get attributed to this cycle merely for an agent_id
        # collision (mutation-tested guard --
        # `test_falsify_correlation_requires_null_session_never_pulls_in_
        # other_concrete_session`). BLOCKER 1 (round 16, 2026-08-28): a row
        # dated AFTER cycle_end is a different story -- see
        # `is_after_window_agent_id_match` below, and the module docstring's
        # ROUND 16 CORRECTION section.
        is_agent_id_correlated = bool(
            not is_session_match
            and row_session is None
            and isinstance(row_agent_id, str)
            # The `row_agent_id` truthiness check is PROVABLY DEAD:
            # `_session_matched_agent_ids()` already guards `and agent_id`,
            # so `anchor_agent_ids` can never contain `""`, which makes
            # `row_agent_id in anchor_agent_ids` alone sufficient. Kept for
            # defensive redundancy -- BLOCKER 4 (round 12, 2026-08-28): the
            # module is a HIGH-risk spend-authorization guard, so the bar
            # for deleting a redundant safety check here is higher than
            # normal.
            and row_agent_id
            and row_agent_id in anchor_agent_ids
        )
        # BLOCKER 1 (round 16, 2026-08-28): a SEPARATE, narrower
        # correlation channel from `is_agent_id_correlated` above -- this
        # one is NOT restricted to a null `session`, but IS restricted to a
        # row dated STRICTLY AFTER `end_dt` sharing an `agent_id` with an
        # anchor THIS CYCLE has already proven dispatched INSIDE its own
        # window (`this_cycle_anchor_agent_ids` -- window-scoped, never the
        # window-independent `anchor_agent_ids`, for the same reason
        # `_session_matched_agent_ids_this_window()`'s own docstring gives).
        # RATIONALE: by the time a background reap process runs (after
        # cycle_end, potentially long after), whatever value happens to be
        # stamped in ITS OWN `session` field -- null, a stale copy of this
        # cycle's own session id, or some genuinely different session id --
        # is an artifact of WHEN/HOW the reap ran, not a live,
        # contemporaneous ownership claim the way an IN-WINDOW row's own
        # populated session is. Per this module's own agent_id-uniqueness
        # axiom, a reap sharing an agent_id with an in-window anchor is that
        # anchor's own spend regardless of that particular reap row's own
        # session value -- but ONLY once the window has closed; an
        # IN-WINDOW row with a genuinely different session stays governed
        # by the stricter, null-session-only rule above. Reproduced (round
        # 16 review): an identical agent/timestamp/spend reap row reported
        # the correct, full spend when its `session` was null and a 5x
        # UNDER-report when its `session` happened to be populated --
        # strictly MORE evidence (a populated session field) must never
        # yield strictly LESS inclusion than strictly LESS evidence (a null
        # one), for a row dated after this cycle's own window has closed.
        # BLOCKER 3 (round 18, 2026-08-28), RELOCATED round 20: a
        # tool_use_id-compatibility gate -- see
        # `_this_cycle_anchor_tool_use_ids()`'s own docstring for the full
        # axiom-conflict rationale. A candidate is compatible with a
        # same-agent_id in-window anchor when its own `tool_use_id` is null
        # (matches the shape a real `stopped-unjoined` reap row actually
        # has), OR when this cycle has PROVEN zero non-null anchor
        # tool_use_ids for this `agent_id` yet (nothing to conflict with --
        # see `test_falsify_after_window_empty_anchor_tool_use_ids_admits_
        # arbitrary_candidate`), OR when its `tool_use_id` genuinely IS one
        # of those already-proven anchor values. A candidate carrying a
        # DIFFERENT, non-null `tool_use_id` is, by
        # `_collapse_duplicate_agent_id_rows()`'s own 2+-distinct rule,
        # proof of a second, independent dispatch. CORRECTED (round 20,
        # 2026-08-28, BLOCKER 1): round 18 folded this gate into
        # `is_after_window_agent_id_match`'s OWN predicate below, which
        # governs only ONE of the THREE routes that reach the shared
        # after-window admission gate (`is_after_window_exempt` further
        # below) -- a null-session candidate (`is_agent_id_correlated`) or
        # a literal, possibly-stale direct session match
        # (`is_session_match`) reaching that SAME shared gate never
        # consulted this check at all, leaking the identical axiom
        # conflict through either sibling route. `is_tool_use_id_
        # compatible` is now computed here (unchanged) but consulted by
        # `is_after_window_exempt` itself, so it governs every route
        # uniformly -- see that check below.
        row_tool_use_id = row.get("tool_use_id")
        anchor_tool_use_ids = (
            this_cycle_anchor_tool_use_ids.get(row_agent_id, frozenset())
            if isinstance(row_agent_id, str)
            else frozenset()
        )
        is_tool_use_id_compatible = (
            not (isinstance(row_tool_use_id, str) and row_tool_use_id)
            or not anchor_tool_use_ids
            or row_tool_use_id in anchor_tool_use_ids
        )
        is_after_window_agent_id_match = bool(
            not is_session_match
            and row_dt is not None
            and row_dt > end_dt
            and isinstance(row_agent_id, str)
            and row_agent_id
            and row_agent_id in this_cycle_anchor_agent_ids
        )

        if is_session_match or is_agent_id_correlated or is_after_window_agent_id_match:
            if row_dt is None:
                # BLOCKER 1 (round 6, extended round 8 to the correlated
                # case): genuine spend of unknown timing -- never silently
                # dropped, whether proven by a direct session match or by
                # agent_id correlation.
                undated_matched_count += 1
                continue
            if row_dt < start_dt:
                # BLOCKER 1 (round 10, 2026-08-28): a row dated BEFORE
                # cycle_start is genuinely PRIOR-CYCLE spend, never a later
                # reap -- the "later reap" rationale below applies ONLY to
                # rows dated AFTER cycle_end. The exemption used to apply
                # in BOTH directions, which could charge a prior cycle's
                # real spend to this one (and, on a long-lived session id,
                # accumulate into a permanent denial). Dropped exactly like
                # any other out-of-window row, correlated or not -- it is
                # not evidence either way for THIS cycle.
                continue
            correlation_rejected = False
            if is_agent_id_correlated and row_agent_id not in this_cycle_anchor_agent_ids:
                # BLOCKER 1 (round 18, 2026-08-28): CORRECTS round 14's own
                # fix, which used an unconditional `continue` here. That
                # `continue` did not merely deny the CORRELATION -- it
                # consumed the row ENTIRELY, skipping the normal
                # ambiguous/excluded classification tail below (the exact
                # treatment this row would get had `is_agent_id_correlated`
                # never been true at all) with ZERO bookkeeping. Confirmed
                # live-reachable against the real
                # ~/.claude/.agent_budget/spend.jsonl (3 real rows
                # affected): a row correlated by agent_id whose anchor
                # belongs to a DIFFERENT cycle is not PROVEN to be someone
                # else's -- it is exactly the unjoined, null-session
                # population (`is_agent_id_correlated` requires
                # `row_session is None`) the AMBIGUOUS bucket exists for,
                # and silently dropping it reopens the exact class of
                # under-report this module exists to prevent. Marking the
                # rejection here, rather than `continue`ing, and falling
                # through to the classification tail below is the fix.
                #
                # Do NOT fold this restriction into `is_agent_id_correlated`
                # itself instead of gating it here, post-hoc, after the
                # predicate has already been used above: that alternative
                # was checked against this test file's own
                # `test_falsify_correlated_row_anchor_position_grid_4x4
                # [before-undated]`/`[after-undated]` and BREAKS it -- those
                # cells depend on an UNDATED correlated row still reaching
                # the `row_dt is None` branch above (which requires
                # `is_agent_id_correlated` to be `True`) so it forces
                # `unknown`/`matched-row-with-unparsable-ts` rather than
                # silently vanishing; folding this restriction into the
                # predicate itself would make `is_agent_id_correlated`
                # `False` for such a row before it ever reaches that
                # check, LOOSENING an undated row from a forced `unknown`
                # to a silent drop -- exactly the trap this module keeps
                # finding. Rejecting here, AFTER the `row_dt is None`/
                # `row_dt < start_dt` handling above has already run,
                # keeps that undated-row protection completely intact.
                correlation_rejected = True
            if not correlation_rejected:
                # BLOCKER 1 (round 16, 2026-08-28): a row dated AFTER cycle_end
                # is exempted from the window check -- whether it reached this
                # branch via `is_agent_id_correlated` (null-session), via
                # `is_after_window_agent_id_match` (populated-but-non-null
                # session, only reachable here because THAT predicate already
                # requires `row_dt > end_dt`), OR via a literal (possibly
                # stale) match of THIS cycle's own session id -- ONLY when its
                # `agent_id` is one this cycle has ALREADY proven, via
                # `this_cycle_anchor_agent_ids`, to have dispatched INSIDE its
                # own window. CORRECTION: before this round, the exemption for
                # a DIRECT session match dated after cycle_end was hard-gated
                # on `not is_agent_id_correlated` -- harmless in isolation, but
                # the two predicates are mutually exclusive
                # (`is_agent_id_correlated` requires `not is_session_match`),
                # so that guard was ALSO, silently, the ENTIRE fate of a
                # direct-session-match row dated after cycle_end: an
                # unconditional drop with ZERO bookkeeping (not matched,
                # ambiguous, excluded, unpriced, or undated), even when that
                # row shared an `agent_id` with an anchor this cycle had
                # already proven dispatched in-window. Per this module's own
                # agent_id-uniqueness axiom (see the predicates above), that IS
                # exactly this cycle's own reap and must not vanish.
                #
                # CORRECTED (round 20, 2026-08-28, BLOCKER 1): this shared
                # gate is the SINGLE point all three after-window routes
                # converge on -- it must carry the tool_use_id-compatibility
                # check itself (`is_tool_use_id_compatible`, computed above),
                # not just route (a)'s own predicate. Round 18 wired that
                # check into `is_after_window_agent_id_match` alone, leaving
                # routes (b) (`is_agent_id_correlated`, a null session) and
                # (c) (a literal, possibly-stale `is_session_match`) able to
                # admit a candidate whose `tool_use_id` conflicts with an
                # already-proven anchor value -- exactly the independent-
                # dispatch-summed-in leak `is_tool_use_id_compatible` exists
                # to prevent, just reachable through the two sibling routes
                # instead. See `test_falsify_after_window_null_session_
                # independent_dispatch_never_summed_via_tool_use_id_conflict`
                # and `test_falsify_after_window_direct_match_independent_
                # dispatch_never_summed_via_tool_use_id_conflict`.
                is_after_window_exempt = (
                    isinstance(row_agent_id, str)
                    and row_agent_id in this_cycle_anchor_agent_ids
                    and is_tool_use_id_compatible
                )
                if row_dt > end_dt and not is_after_window_exempt:
                    # A row genuinely outside the window and not exempted is
                    # still not evidence either way for THIS cycle.
                    continue
                # A row only reaches `matched` here on the strength of its
                # `agent_id` rather than a fresh, in-window declaration of this
                # session's own -- true whenever it is agent_id-correlated via
                # either channel (`is_agent_id_correlated` or
                # `is_after_window_agent_id_match`), OR whenever it is a direct
                # session match that only survived the check immediately above
                # because of the after-window agent_id exemption (in which case
                # `row_dt > end_dt` here, since an IN-WINDOW direct match never
                # needed that exemption to survive).
                #
                # BLOCKER 2 (round 18, 2026-08-28), SPLIT round 20: this flag
                # used to feed BOTH downstream consumers below, but they need
                # DIFFERENT predicates. `is_correlated_for_collapse_ambiguity`
                # (consumer #1, `_collapse_duplicate_agent_id_rows()`'s own
                # ambiguity check) correctly excludes `is_session_match`
                # unconditionally -- round 10's own explicit carve-out (that
                # function's own docstring, BLOCKER 3 section: "a
                # direct-session-match row is never subject to this check
                # regardless -- both readings are already proven to be this
                # session's own") -- regardless of window position; this is
                # UNCHANGED from round 18. `is_exempt_from_unexpected_type_
                # check` (consumer #2, immediately below) is narrower:
                # round 16's own documented intent was that the safety net
                # still applies to a genuine, IN-WINDOW direct session match
                # -- only an AFTER-WINDOW-exempted direct match (necessarily
                # `row_dt > end_dt` here, since an in-window one never needed
                # the exemption above to survive), or either agent_id-only
                # correlation route, is exempt from it. Round 18's single
                # shared flag silently reinstated the safety net for an
                # after-window-exempted direct match too (an undeclared
                # `agent_type` on a stale-session-copy reap row dated after
                # cycle_end forced a spurious `unknown`, reversing round 16's
                # own fix) -- see `test_falsify_after_window_direct_match_
                # undeclared_type_not_denied_round16_restored`. The two
                # predicates agree for every row EXCEPT an AFTER-WINDOW
                # direct session match, where the collapse-ambiguity flag
                # is always `False` while the safety-net-exemption flag
                # depends on window position.
                is_correlated_for_collapse_ambiguity = (not is_session_match) and (
                    is_agent_id_correlated or is_after_window_agent_id_match
                )
                is_exempt_from_unexpected_type_check = (not is_session_match) or (row_dt > end_dt)
                matched.append(row)
                matched_is_correlated.append(is_correlated_for_collapse_ambiguity)
                if not is_exempt_from_unexpected_type_check:
                    # The unexpected-agent-type safety net still applies to a
                    # DIRECT, IN-WINDOW session match (unchanged). It
                    # deliberately never applies to a row that only reached
                    # `matched` via agent_id correlation, nor to the
                    # after-window direct-match exemption above (round 16):
                    # requiring ITS OWN (possibly placeholder or undeclared)
                    # agent_type to be in `known_agent_types` would reinstate
                    # exactly the class of bug this module keeps finding --
                    # an undeclared type on a reap-like row is precisely why it
                    # was being silently dropped/excluded before.
                    row_type = row.get("agent_type")
                    if row_type not in agent_types:
                        unexpected_type_count += 1
                continue
            # correlation_rejected: fall through (no `continue`) to the SAME
            # ambiguous/excluded classification tail below that an
            # uncorrelated row gets -- BLOCKER 1 (round 18). NOTE (round 20,
            # lower-severity finding, review round 19): this reaches the
            # in-window ambiguous/excluded classification lines specifically
            # only when the row is dated INSIDE this cycle's own window; a
            # rejected row dated AFTER `end_dt` still hits the tail's own
            # `row_dt < start_dt or row_dt > end_dt: continue` window filter
            # first and is silently dropped with ZERO bookkeeping (excluded_
            # rows/ambiguous_rows both untouched), exactly like any other
            # out-of-window, uncorrelated row -- "the same tail" describes
            # the CODE PATH a rejected row falls into, not a guarantee that
            # every rejected row lands in the ambiguous or excluded bucket.
            # At this point `row_dt` is guaranteed not `None` and `>= start_dt` (both
            # handled above), and `row_session` is `None` (a precondition of
            # `is_agent_id_correlated`), so the tail's own `row_session is
            # None` branch is exactly the one this row lands in below.

        if row_dt is None:
            # BLOCKER 1 (round 8, 2026-08-28): corrects round 6's own fix,
            # which handled only the SESSION-MATCH half of an unparsable-ts
            # row and left the null-session half silently dropped
            # unconditionally. A null-session row is NOT known to be
            # someone else's; it is exactly the unjoined population the
            # AMBIGUOUS bucket exists for, whether or not its timestamp
            # parses. Only a row belonging to some OTHER, concrete,
            # non-null session stays genuinely dropped here.
            if row_session is None and _ambiguous_agent_type_candidates(row) & agent_types:
                ambiguous_count += 1
            continue

        if row_dt < start_dt or row_dt > end_dt:
            continue

        if row_session is None and _ambiguous_agent_type_candidates(row) & agent_types:
            # BLOCKER 2 (round 8, 2026-08-28): checks the UNION of the
            # row's effective (possibly recovered) agent_type and its
            # ORIGINAL pre-recovery value -- never the effective value
            # alone, which let recovery silently downgrade an originally-
            # declared-placeholder row to EXCLUDED the instant its true
            # type resolved to something this cycle never declared. See
            # `_ambiguous_agent_type_candidates()`.
            ambiguous_count += 1
        else:
            excluded_count += 1

    # BLOCKER 5: computed once, up front, from every row that matched this
    # cycle's session -- threaded into every return path below so a caller
    # can ALWAYS tell whether a verdict (known OR unknown) rests partly on
    # spend_attribution's inferred (not measured) identity, never only on
    # inspecting the bare, already-overwritten agent_type/model fields.
    recovered_agent_type_rows, recovered_model_rows = _count_recovered_fields(matched)

    if unexpected_type_count:
        return _unknown_attribution(
            reason="unexpected-agent-type-for-session",
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            matched_rows=len(matched),
            ambiguous_rows=ambiguous_count,
            excluded_rows=excluded_count,
            malformed_lines=malformed,
            recovered_agent_type_rows=recovered_agent_type_rows,
            recovered_model_rows=recovered_model_rows,
        )

    if undated_matched_count:
        # BLOCKER 1 (round 6, 2026-08-28): at least one row genuinely
        # matches this cycle's own session but its `ts` could not be
        # parsed -- real spend of unknown timing, never silently dropped.
        # `matched_rows` intentionally does NOT include these rows (they
        # never entered `matched` at all); `undated_matched_rows` is the
        # dedicated, visible counter for exactly this population.
        return _unknown_attribution(
            reason="matched-row-with-unparsable-ts",
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            matched_rows=len(matched),
            ambiguous_rows=ambiguous_count,
            excluded_rows=excluded_count,
            malformed_lines=malformed,
            recovered_agent_type_rows=recovered_agent_type_rows,
            recovered_model_rows=recovered_model_rows,
            undated_matched_rows=undated_matched_count,
        )

    if ambiguous_count:
        return _unknown_attribution(
            reason="ambiguous-unjoined-rows-in-window",
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            matched_rows=len(matched),
            ambiguous_rows=ambiguous_count,
            excluded_rows=excluded_count,
            malformed_lines=malformed,
            recovered_agent_type_rows=recovered_agent_type_rows,
            recovered_model_rows=recovered_model_rows,
        )

    # BLOCKER 3 (defense in depth): collapse same-agent_id duplicate MATCHED
    # rows to their single largest reading before summing spend -- see
    # `_collapse_duplicate_agent_id_rows()`. `matched_rows` below still
    # reports every row that matched this cycle's session; only the PRICING
    # sum is deduplicated. BLOCKER 2 (round 3, 2026-08-28): this collapse now
    # runs BEFORE the `expected_dispatch_count` comparison below, and that
    # comparison reads the POST-collapse distinct-dispatch count
    # (`len(priced_rows)`), never the raw pre-collapse `len(matched)` -- see
    # module docstring's DUPLICATE-AGENT_ID SPEND / BLOCKER 2 section for why
    # comparing pre-collapse defeated the two mitigations against each other.
    # ROUND 4: the winner is now selected by actual dollar value, and
    # `unpriceable_dropped_count` folds every DROPPED-but-unpriceable
    # candidate into the `unpriced` total below, so a malformed/unpriceable
    # row can never vanish just because it shared an agent_id with a clean
    # sibling -- see module docstring's ROUND 4 CORRECTION section.
    (
        priced_rows,
        collapsed_duplicate_rows,
        unpriceable_dropped_count,
        ambiguous_dropped_declared_count,
    ) = _collapse_duplicate_agent_id_rows(
        matched, price_table, correlated_flags=matched_is_correlated, known_agent_types=agent_types
    )

    if ambiguous_dropped_declared_count:
        # BLOCKER 3 (round 10, 2026-08-28): at least one row the collapse
        # above DROPPED reached `matched` only via agent_id correlation
        # (never proven to be this cycle's own session) and its own
        # declared agent_type is one this cycle recognizes -- the module
        # cannot tell "a duplicate reading of already-attributed spend"
        # apart from "genuine additional spend from a different dispatch
        # sharing the same agent_id". Round 7's promise ("never turns
        # AMBIGUOUS into MATCHED") is preserved by refusing to guess here,
        # exactly like any other ambiguous unjoined row.
        return _unknown_attribution(
            reason="ambiguous-duplicate-agent-id-declared-type",
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            matched_rows=len(matched),
            ambiguous_rows=ambiguous_dropped_declared_count,
            excluded_rows=excluded_count,
            malformed_lines=malformed,
            collapsed_duplicate_rows=collapsed_duplicate_rows,
            recovered_agent_type_rows=recovered_agent_type_rows,
            recovered_model_rows=recovered_model_rows,
        )

    if not priced_rows:
        # BLOCKER 1 (round 3, 2026-08-28): zero matched rows is EXACTLY the
        # state this module can never, on its own, distinguish between
        # "this cycle genuinely dispatched nothing" and "my session id/
        # window is wrong and every one of my real dispatches is invisible
        # to this query" -- the precise real-world failure mode this module
        # exists to catch. A `known`/$0 verdict is refused unless the
        # caller has EXPLICITLY asserted `expected_dispatch_count=0`; any
        # other value -- INCLUDING `None` (no assertion made at all) --
        # forces `unknown`.
        if expected_dispatch_count != 0:
            reason = (
                "no-matched-rows-and-no-dispatch-count-asserted"
                if expected_dispatch_count is None
                else f"dispatches-not-in-ledger:expected={expected_dispatch_count}"
            )
            return _unknown_attribution(
                reason=reason,
                system=system,
                session_id=session_id,
                window_start=window_start,
                window_end=window_end,
                excluded_rows=excluded_count,
                malformed_lines=malformed,
                collapsed_duplicate_rows=collapsed_duplicate_rows,
                recovered_agent_type_rows=recovered_agent_type_rows,
                recovered_model_rows=recovered_model_rows,
            )
    elif expected_dispatch_count is not None and len(priced_rows) != expected_dispatch_count:
        return _unknown_attribution(
            reason=(
                f"count-mismatch:expected={expected_dispatch_count}:found={len(priced_rows)}"
            ),
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            matched_rows=len(matched),
            excluded_rows=excluded_count,
            malformed_lines=malformed,
            collapsed_duplicate_rows=collapsed_duplicate_rows,
            recovered_agent_type_rows=recovered_agent_type_rows,
            recovered_model_rows=recovered_model_rows,
        )

    total = 0.0
    # BLOCKER 2 (round 4): seed `unpriced` with every duplicate-group row the
    # collapse dropped because it could not be priced -- never let a
    # malformed/unpriceable row disappear from this count just because a
    # priceable sibling won the collapse in its place.
    unpriced = unpriceable_dropped_count
    for row in priced_rows:
        family = normalize_model(row.get("model"))
        cost = price_tokens_usd(row.get("tokens"), family, price_table, row.get("tokens_total"))
        if cost is None:
            unpriced += 1
            continue
        total += cost

    if unpriced:
        return _unknown_attribution(
            reason="unpriced-model-in-window",
            system=system,
            session_id=session_id,
            window_start=window_start,
            window_end=window_end,
            matched_rows=len(matched),
            excluded_rows=excluded_count,
            unpriced_rows=unpriced,
            malformed_lines=malformed,
            collapsed_duplicate_rows=collapsed_duplicate_rows,
            recovered_agent_type_rows=recovered_agent_type_rows,
            recovered_model_rows=recovered_model_rows,
        )

    return CycleAttribution(
        status="known",
        spent_usd=round(total, 6),
        reason=None,
        system=system,
        session_id=session_id,
        window_start=window_start,
        window_end=window_end,
        matched_rows=len(matched),
        ambiguous_rows=0,
        excluded_rows=excluded_count,
        unpriced_rows=0,
        malformed_lines=malformed,
        collapsed_duplicate_rows=collapsed_duplicate_rows,
        recovered_agent_type_rows=recovered_agent_type_rows,
        recovered_model_rows=recovered_model_rows,
    )


def decide_cycle_budget(
    ledger_path: str,
    *,
    system: str,
    session_id: str,
    cycle_start_ts: str,
    known_agent_types: Iterable[str],
    ceiling_usd: float,
    expected_dispatch_count: int | None,
    cycle_end_ts: str | None = None,
    pricing: dict[str, dict[str, float]] | None = None,
    identity_index: Mapping[str, object] | None = None,
) -> CycleBudgetDecision:
    """The gate: call BEFORE spawning more work in a cycle.

    `identity_index` is passed straight through to `attribute_cycle_spend()`
    -- see that function's own docstring and this module's IDENTITY
    RECOVERY section for the (purely additive) contract.

    `expected_dispatch_count` is REQUIRED here too (BLOCKER 3, round 4,
    2026-08-28) -- round 3 made this a required keyword on
    `attribute_cycle_spend()` (the callee), but left THIS function, the
    actual gate a real dispatcher calls, defaulting it to `None` and merely
    forwarding whatever it received. That is the identical failure class
    one frame up the call stack: a caller of `decide_cycle_budget()` could
    silently opt into the unsafe "no count asserted" path by simply never
    passing the keyword, exactly what making it required on the callee was
    supposed to close. `None` is still a legal explicit value (the caller
    consciously declining to assert a count); only OMITTING the keyword
    entirely is now impossible (Python raises `TypeError` before the
    function body runs, same as it always has for the callee).

    Raises ValueError for the same caller-misuse cases as
    `attribute_cycle_spend()` (including a malformed `expected_dispatch_count`
    type -- BLOCKER 7, checked here directly so the error surfaces before any
    other computation), plus a non-positive `ceiling_usd`.

    Never raises for ledger/data problems: any unexpected exception while
    attributing spend is caught here and turned into `allowed=False,
    status="unknown"` -- a second, defense-in-depth fail-CLOSED backstop
    behind `attribute_cycle_spend()`'s own never-raise-for-ledger-issues
    contract, matching this module's stated policy that a budget guard must
    never translate "something went wrong" into "so authorize more spend".
    """
    if not isinstance(ceiling_usd, (int, float)) or isinstance(ceiling_usd, bool):
        raise ValueError("ceiling_usd must be a number")
    if ceiling_usd <= 0:
        raise ValueError("ceiling_usd must be > 0")
    _validate_expected_dispatch_count(expected_dispatch_count)

    try:
        attribution = attribute_cycle_spend(
            ledger_path,
            system=system,
            session_id=session_id,
            cycle_start_ts=cycle_start_ts,
            known_agent_types=known_agent_types,
            cycle_end_ts=cycle_end_ts,
            expected_dispatch_count=expected_dispatch_count,
            pricing=pricing,
            identity_index=identity_index,
        )
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - defense in depth, see docstring
        attribution = _unknown_attribution(
            reason=f"internal-error:{type(exc).__name__}",
            system=system,
            session_id=session_id,
            window_start=cycle_start_ts,
            window_end=cycle_end_ts or "",
        )

    if attribution.status != "known" or attribution.spent_usd is None:
        return CycleBudgetDecision(
            allowed=False,
            status="unknown",
            spent_usd=None,
            ceiling_usd=float(ceiling_usd),
            remaining_usd=None,
            reason=attribution.reason or "unknown",
            attribution=attribution,
        )

    remaining = float(ceiling_usd) - attribution.spent_usd
    allowed = remaining > 0
    return CycleBudgetDecision(
        allowed=allowed,
        status="known",
        spent_usd=attribution.spent_usd,
        ceiling_usd=float(ceiling_usd),
        remaining_usd=round(remaining, 6),
        reason="under-ceiling" if allowed else "ceiling-reached",
        attribution=attribution,
    )


# ---------------------------------------------------------------------------
# doctor -- read-only ledger/pricing health report. Never gates, never raises.
# ---------------------------------------------------------------------------


def _doctor_payload(ledger_path: str) -> dict[str, object]:
    exists = os.path.isfile(ledger_path)
    raw_rows, malformed = _safe_load_ledger_rows(ledger_path)
    # BLOCKER 4 (round 6, 2026-08-28): `readable` MUST be captured from
    # `_safe_load_ledger_rows()`'s own return value BEFORE the `rows or []`
    # fallback below -- that fallback makes `rows` a list unconditionally,
    # so a check written AFTER it (`rows is not None`) is always True and
    # always was, silently lying "readable" for a missing or genuinely
    # unreadable (permission error, OS failure) ledger -- exactly the health
    # signal an operator/oversight job depends on to know this guard is
    # actually functioning.
    readable = raw_rows is not None
    rows = raw_rows or []
    sessions = {r.get("session") for r in rows if r.get("session")}
    unjoined = sum(1 for r in rows if not r.get("session"))
    families_seen = sorted({normalize_model(r.get("model")) for r in rows})
    # #8 (round 10, 2026-08-28): `rows[0]`/`rows[-1]` assumed the ledger's
    # own file order is chronological -- it is an append-only log written
    # by potentially-concurrent writers, so that is never guaranteed. Use
    # a real min/max over every row whose `ts` actually parses instead; a
    # row with a missing/unparsable `ts` is simply not a candidate for
    # either boundary (never crashes, never silently picks the wrong one).
    dated_ts = sorted(dt for dt in (_row_ts(r) for r in rows) if dt is not None)
    oldest_row_ts = _fmt_ts(dated_ts[0]) if dated_ts else None
    newest_row_ts = _fmt_ts(dated_ts[-1]) if dated_ts else None
    return {
        "ledger_path": ledger_path,
        "ledger_exists": exists,
        "ledger_readable": readable,
        "row_count": len(rows),
        "malformed_lines": malformed,
        "distinct_sessions": len(sessions),
        "unjoined_session_rows": unjoined,
        "model_families_seen": families_seen,
        "unpriced_families_seen": sorted(f for f in families_seen if f not in PRICING_USD_PER_MTOK),
        "pricing_table_valid": _validate_pricing_table(PRICING_USD_PER_MTOK),
        "pricing_families": sorted(PRICING_USD_PER_MTOK),
        "oldest_row_ts": oldest_row_ts,
        "newest_row_ts": newest_row_ts,
    }


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _add_identity_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--system",
        required=True,
        help="Arbitrary label for the calling system/loop (e.g. a repo or job "
        "name). Bookkeeping only -- never filters the ledger.",
    )
    sp.add_argument(
        "--session",
        required=True,
        dest="session_id",
        help="Orchestrating Claude Code session id (matches spend.jsonl's "
        "'session' field).",
    )
    sp.add_argument(
        "--cycle-start",
        required=True,
        dest="cycle_start_ts",
        help=f"Cycle start, UTC, format {TS_FORMAT.replace('%', '%%')!r} (or general ISO-8601).",
    )
    sp.add_argument(
        "--cycle-end",
        default=None,
        dest="cycle_end_ts",
        help="Cycle end, same format as --cycle-start (default: now).",
    )
    sp.add_argument(
        "--agent-types",
        required=True,
        dest="agent_types",
        help="Comma-separated agent_types this cycle may dispatch.",
    )
    sp.add_argument(
        "--ledger",
        default=None,
        dest="ledger_path",
        help="Override the spend ledger path (default: $CSA_CYCLE_LEDGER or "
        "~/.claude/.agent_budget/spend.jsonl).",
    )
    sp.add_argument(
        "--pricing-file",
        default=None,
        dest="pricing_file",
        help="Override PRICING_USD_PER_MTOK with a JSON file of the same shape.",
    )
    sp.add_argument(
        "--no-recovery",
        dest="no_recovery",
        action="store_true",
        help="Disable spend_attribution.py identity recovery -- attribute "
        "strictly from the raw ledger, exactly as before that module existed.",
    )


def _add_expected_dispatches_arg(sp: argparse.ArgumentParser, *, required: bool) -> None:
    """`--expected-dispatches` -- REQUIRED on `check` (round 3, BLOCKER 1,
    2026-08-28): `check` is the gate a dispatcher actually spawns/denies
    work on, so it can never be allowed to silently default into the unsafe
    "zero matched rows, no assertion made" path this flag exists to close --
    the caller MUST either name a real count or explicitly pass `0`. `status`
    stays OPTIONAL: it is a pure report (never gates), and
    `attribute_cycle_spend()`'s own required-keyword contract still forces
    this CLI to pass SOMETHING through explicitly (`None` when the flag is
    omitted here) -- `status` reporting `unknown` for an un-asserted zero-
    matched-rows slice is the correct, safe behavior, not a gap."""
    sp.add_argument(
        "--expected-dispatches",
        type=int,
        default=None,
        required=required,
        dest="expected_dispatch_count",
        help="How many Task dispatches this cycle believes it has made so "
        "far this cycle. Required on `check` -- zero matched ledger rows "
        "with no count asserted is refused as unknown, never read as '$0 "
        "spent' (pass 0 explicitly for a cycle that genuinely expected zero "
        "dispatches).",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cycle_budget.py",
        description="Mechanical in-cycle spend guard, reading the real "
        "~/.claude/.agent_budget/spend.jsonl ledger.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Report this cycle's attributed spend so far.")
    _add_identity_args(p_status)
    _add_expected_dispatches_arg(p_status, required=False)
    p_status.add_argument(
        "--ceiling-usd",
        type=float,
        default=None,
        dest="ceiling_usd",
        help="Optional: also compute remaining budget against this ceiling.",
    )

    p_check = sub.add_parser("check", help="Gate: may this cycle spawn more work?")
    _add_identity_args(p_check)
    _add_expected_dispatches_arg(p_check, required=True)
    p_check.add_argument(
        "--ceiling-usd",
        type=float,
        required=True,
        dest="ceiling_usd",
        help="Per-cycle USD ceiling.",
    )

    p_doctor = sub.add_parser("doctor", help="Ledger + pricing-table health report.")
    p_doctor.add_argument(
        "--ledger",
        default=None,
        dest="ledger_path",
        help="Override the spend ledger path.",
    )

    return parser


def _parse_agent_types(raw: str) -> frozenset[str]:
    return frozenset(t.strip() for t in raw.split(",") if t.strip())


def _load_default_identity_index(environ: dict[str, str]) -> Mapping[str, object]:
    """CLI-only default: `spend_attribution.load_cached_index()`, which ONLY
    reads whatever identity cache already exists on disk (never a live
    filesystem scan -- see module docstring's IDENTITY RECOVERY section for
    why the gate path must never pay that cost inline). Degrades to `{}`
    (no recovery, never an error) if `spend_attribution` cannot be imported
    or the cache is missing/corrupt -- identical to this module's
    pre-recovery behavior in either case.
    """
    try:
        import spend_attribution
    except Exception:
        return {}
    try:
        return spend_attribution.load_cached_index(environ=environ)
    except Exception:
        return {}


def run(argv: list[str], environ: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    """Pure-ish core: parse argv, compute, return (exit_code, json_payload).

    Never prints; `main()` is the thin I/O wrapper around this so tests can
    drive the whole CLI surface with in-memory arguments/environ, matching
    this codebase's established split (cf. agent_budget.py's decide() /
    apply_decision()).
    """
    environ = environ if environ is not None else dict(os.environ)
    parser = build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 2)
        return code, ({} if code == 0 else {"error": "argument-error"})

    ledger_path = args.ledger_path or _default_ledger_path(environ)

    if args.command == "doctor":
        return 0, _doctor_payload(ledger_path)

    pricing = PRICING_USD_PER_MTOK
    pricing_file_error: str | None = None
    if getattr(args, "pricing_file", None):
        loaded = _load_pricing_file(args.pricing_file)
        if loaded is None:
            pricing_file_error = f"unreadable-or-invalid-pricing-file:{args.pricing_file}"
        else:
            pricing = loaded

    agent_types = _parse_agent_types(args.agent_types)
    identity_index: Mapping[str, object] = (
        {} if getattr(args, "no_recovery", False) else _load_default_identity_index(environ)
    )

    # `check` goes through decide_cycle_budget() directly -- the SAME gate
    # function a library caller uses -- rather than re-deriving the
    # allow/deny math here. Two independent implementations of "does spend
    # exceed the ceiling" is exactly the kind of divergence a budget guard
    # cannot afford (one could silently drift to a weaker check than the
    # other); a single source of truth means the CLI's exit code and a
    # direct `decide_cycle_budget()` call can never disagree.
    if args.command == "check":
        try:
            if pricing_file_error:
                raise ValueError(pricing_file_error)
            decision = decide_cycle_budget(
                ledger_path,
                system=args.system,
                session_id=args.session_id,
                cycle_start_ts=args.cycle_start_ts,
                known_agent_types=agent_types,
                ceiling_usd=args.ceiling_usd,
                cycle_end_ts=args.cycle_end_ts,
                expected_dispatch_count=args.expected_dispatch_count,
                pricing=pricing,
                identity_index=identity_index,
            )
        except ValueError as exc:
            return 2, {"error": f"invalid-arguments:{exc}"}
        exit_code = 0 if decision.allowed else (3 if decision.status == "unknown" else 2)
        return exit_code, decision.to_dict()

    # command == "status"
    try:
        if pricing_file_error:
            raise ValueError(pricing_file_error)
        attribution = attribute_cycle_spend(
            ledger_path,
            system=args.system,
            session_id=args.session_id,
            cycle_start_ts=args.cycle_start_ts,
            known_agent_types=agent_types,
            cycle_end_ts=args.cycle_end_ts,
            expected_dispatch_count=args.expected_dispatch_count,
            pricing=pricing,
            identity_index=identity_index,
        )
    except ValueError as exc:
        return 2, {"error": f"invalid-arguments:{exc}"}

    payload = attribution.to_dict()
    ceiling_usd = getattr(args, "ceiling_usd", None)
    if ceiling_usd is not None:
        payload["ceiling_usd"] = ceiling_usd
        if attribution.status == "known" and attribution.spent_usd is not None:
            payload["remaining_usd"] = round(ceiling_usd - attribution.spent_usd, 6)
        else:
            payload["remaining_usd"] = None
    return 0, payload


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    exit_code, payload = run(argv)
    if payload:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
