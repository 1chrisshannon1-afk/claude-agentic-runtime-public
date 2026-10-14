# Board Steward Primer

Runtime-level oversight primer. Product-agnostic: contains no app-specific paths, account
names, or counts belonging to any one repository. Distilled from external research on
issue-tracker/backlog hygiene; every claim below carries its source. `gh_issue.sh` referenced in
the closing section is this runtime's own generic issue-filing helper (`~/.claude/scripts/`), not
a product-repo artifact.

## 1. Icebox decay and auto-expiry

The "icebox" model — items you won't work soon but won't delete — was popularized by Pivotal
Tracker. Its named failure mode: "the icebox is where stories go to die," accumulating hundreds
of unreadable, undifferentiated stories that add cognitive overhead and obscure the real roadmap
rather than preserving optionality.
(Source: "The Icebox Is Where Stories Go to Die" — thoughtbot,
https://thoughtbot.com/blog/the-icebox-is-where-stories-go-to-die)

Auto-expiry patterns that keep an icebox from becoming a graveyard, observed in practice:
- Mark a stale item a cleanup candidate with an explanatory comment; auto-close after 14 days of
  no response. One documented application: applied to icebox items untouched for over 2 years.
  (Source: GitLab triage-ops merge request, https://gitlab.com/gitlab-org/quality/triage-ops/-/merge_requests/586
  [unverified — confirm at the source before citing outward])
- A stale-bot flags items with no discussion for 6+ months, prompting a relevance check rather
  than an automatic close.
- A manual opt-out label (e.g. an explicit "excluded from cleanup" marker) lets someone
  intentionally park an item without the aging rule silently killing it — auto-expiry needs an
  escape hatch or it will eventually delete something deliberate.
(Sources: Supportbench "Manage Backlog Aging & Prevent Zombie Tickets," InvGate "10 Ways to
Overcome Aged Tickets")

## 2. Linear's zero-bug policy — mechanics, not slogan

No backlog option exists for bugs at all — an engineer must either commit to fixing an assigned
bug or explicitly mark it "won't fix"; there is no third, passive state. High-priority bugs are
fixed within 48 hours, low-priority within 7 days [unverified — confirm at the source before
citing outward]. A per-engineer open-bug count crossing roughly 4–5 items is caught on a
dashboard review and triggers reassignment or relief [unverified — confirm at the source before
citing outward] — the count itself is the trigger, not a subjective sense that someone seems
overloaded. Before the ongoing policy began, the team cleared a pre-existing debt of roughly 175
bugs in one dedicated 3-week sprint [unverified — confirm at the source before citing outward];
the team norm since is that the bug inbox is the first thing opened each morning.
(Source: "Zero Bugs Policy" — Linear, https://linear.app/now/zero-bugs-policy)

The transferable mechanism, independent of the exact numbers: remove the passive "sits in
backlog forever" state for defects entirely. Every bug is either actively owned toward a fix or
explicitly, visibly dispositioned as won't-fix. A dashboard-visible per-owner load threshold
converts "someone seems overloaded" from a feeling into a trigger.

## 3. Honest won't-fix discipline

Use "won't fix" aggressively, not reluctantly — for deprecated-feature bugs, extreme edge cases,
or cases where fix cost is far greater than impact. But two conditions are non-negotiable every
time:
1. **Always a stated reason.** The disposition comment names *why*, not just the label.
2. **Capacity math stated transparently.** ("N open items, bandwidth for M per period, here is
   the prioritization that produced this call.") The reporter can see the actual constraint, not
   a bare rejection.

Closing this way is not permanent — a won't-fix item can be reopened if someone later picks it
up. The discipline's own framing: leaving an issue open indefinitely with no real intent to fix
it is dishonest to the reporter, not a kindness — an honest, reasoned close is more respectful of
their time than an indefinite, silent non-answer.
(Source: Scrum.org, "Zero Bug Policy: A Fast Way of Paying Back Technical Debt"; The Quality
Duck, "The Quality Duck's Approach to a Zero Bug Policy")

## 4. Duplicate-detection practice

The core difficulty is that the same underlying defect gets reported in different vocabulary by
different reporters — matching requires meaning, not string equality. Current AI/embedding-based
semantic-similarity matching against a full issue database is reported at 70–85% accuracy
[unverified — confirm at the source before citing outward] — the method behind that number:
comparing new-report embeddings against the existing corpus and scoring match precision/recall
against a labeled duplicate set.
(Sources: arXiv 2504.14797, https://arxiv.org/html/2504.14797v1)

Practical implication: automated duplicate suggestion is good enough to *propose* a merge, not
good enough to *auto-close* on its own — the accuracy band (70–85%) leaves enough of a false-
positive/false-negative tail that a human or a downstream approval step should confirm before an
issue is actually merged or closed as a duplicate.

## 5. WIP limits

Capping concurrent in-progress items forces a pull system. The purpose is not primarily a
throughput trick — it is preventing multitasking/context-switch overload, surfacing bottlenecks
as soon as they form (a queue backs up visibly instead of hiding inside everyone's "in progress"
column), and improving completion rate and quality of what does ship.
(Sources: Atlassian, "WIP Limits" — https://www.atlassian.com/agile/kanban/wip-limits;
Planview, "WIP Limits"; Miro, "WIP Limits in Kanban")

## 6. Label/field hygiene — fields over labels

Recommended structure: three label families — status / type / priority — each prefixed by its
family so they sort and scan together. Priority and phase belong in single-select **custom
fields**, not free-text labels, because a field is structured and queryable where a label is a
flat, unenforced string. Assignee + label (or field) are treated as the stated minimum required
metadata; an issue only counts as "accepted" once it carries a priority designation, not merely
a title. A weekly pass re-checks that labels — especially priority — are still current, since a
label set once and never revisited drifts out of truth as circumstances change.
(Sources: GitHub Docs, "Best Practices for Projects,"
https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/best-practices-for-projects;
Medium, "Sane GitHub Labels")

## 7. Refinement cadence

Weekly is the most common cadence for teams on 2-week sprints (biweekly for longer cycles),
typically a 30–60 minute session. The pre-2020 Scrum Guide caps total refinement time at roughly
10% of team capacity ("usually consumes no more than 10% of the capacity of the Development Team"
— removed in the 2020 rewrite; guidance, never a cap) — refinement is a bounded cost, not an
open-ended standing meeting. Cross-
functional participation (not PO-only) surfaces risks and simpler approaches earlier than a
solo-owner pass would. The health signal to watch is *friction removed from planning* — items
arrive at planning already sized and understood — not meeting attendance or a raw item-count
processed.
(Sources: Mountain Goat Software, "Backlog Refinement"; Plane, "Backlog Grooming Best Practices
for Agile Teams")

## 8. One-issue-per-root-cause-cluster

When a single review or audit pass surfaces multiple findings that share a root cause or problem
area, file **one** issue carrying a checklist of the individual findings — not one issue per
finding. The anti-pattern this guards against: an audit pass that produces many top-level tickets
which are really the same underlying defect surfacing in different symptoms, inflating the
backlog with sprawl that looks like coverage but is actually noise. No single named external
doctrine was found for this specific anti-pattern in the source research (flagged there as thin
coverage — the closest available guidance is generic "use a checklist for one person working a
linear list; use separate linked issues only when work needs independent assignment, time-
tracking, or board visibility"). Treat the exception, not the rule, narrowly: a finding that is
independently launch-blocking on its own severity still gets its own issue regardless of what
else the same pass turned up.
(Sources: Zenhub, "When to Use Checklists, Issues, and Epics"; GitLab forum thread on
epic-vs-issue distinction — both general guidance, not a named anti-pattern doctrine)

---

## How this agent applies it

- **Non-destructive mutations are autonomous** — labeling, field updates, linking duplicates,
  adding a checklist item to an existing root-cause-cluster issue, flagging staleness, and
  filing a new issue for a genuinely new finding all proceed without waiting for approval.
- **Dispositions are PROPOSED for approval, never executed unilaterally** — any won't-fix,
  auto-expiry close, or duplicate-merge is written up with its stated reason and (for won't-fix)
  its capacity math, then held for approval before it takes effect. This mirrors the discipline in
  §3: an honest disposition is still a disposition someone should be able to see and contest
  before it's final.
- **Closes only via `gh_issue.sh resolve` (a real fix) or `gh_issue.sh dispose` (a not-planned
  close — duplicate-of/stale-superseded/wont-fix), never a bare `gh issue close`.** Both helpers
  enforce the reasoned-close discipline this primer describes; bypassing either re-opens exactly
  the "silent non-answer" failure mode in §3. `dispose` exists and is this agent's own execution
  mechanism for a not-planned close — it is never the approval itself: run it only on an
  operator-approved batch, after every disposition in that batch has been proposed with its stated
  reason (and, for won't-fix, its capacity math) and the operator has signed off on the batch as a
  whole — and NEVER in a scheduled/unattended sweep, which always proposes and stops (the runtime
  contract's §13 roster table: "destructive dispositions ALWAYS operator-approved"; the install
  doc's steward row says the same in its own words: "disposition batch PROPOSED to the tracking
  issue, never executed"); a prior session's issue
  comment is a proposal record, not the sign-off itself.
- **Never git-history scans for triage.** Backlog grooming reasons about issue state (labels,
  fields, comments, linked items) and the disposition rules above — not by mining commit history,
  which is slow, unbounded, and not what any of the cited practices above are actually keyed to.
