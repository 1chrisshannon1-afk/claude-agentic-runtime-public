# Product QA Primer

Product-agnostic reference for an agent performing UX/product-quality walkthroughs — inspection
methods that require no live users, scored consistently enough that findings can be triaged and
tracked. This primer has no app-specific facts, paths, tenant names, screens, or numbers; a given
product's actual task list, screens, and prior findings belong in that product's own dossier, not
here.

## 1. Nielsen's 10 usability heuristics, with severity scoring

Nielsen's 10 heuristics (published 1994, still the standard reference as of NN/g's most recent
review):

1. Visibility of system status
2. Match between the system and the real world
3. User control and freedom
4. Consistency and standards
5. Error prevention
6. Recognition rather than recall
7. Flexibility and efficiency of use
8. Aesthetic and minimalist design
9. Help users recognize, diagnose, and recover from errors
10. Help and documentation

**Process** (NN/g, "How to Conduct a Heuristic Evaluation"): 3–5 evaluators work *independently*,
not as a group, each doing a two-pass review — pass one to get familiar with the flow/interface,
pass two to score explicitly against the 10 heuristics. Roughly 1–2 hours per evaluator, with
findings pooled afterward (e.g. via affinity diagramming) rather than debated live during scoring.

**Severity scale (0–4)**, judged on frequency, impact, and persistence of the problem (plus an
optional "market impact" factor):

- 0 — not a usability problem at all
- 1 — cosmetic only; fix if time permits
- 2 — minor; low priority to fix
- 3 — major; high priority to fix
- 4 — catastrophe; must fix before release

A single evaluator's severity rating is, in Nielsen's own words, "too unreliable to be trusted"
[unverified — confirm at the source before citing outward as a verbatim quote; substance holds] —
use the **mean of at least 3 independent raters**, not one person's judgment call, whenever the
evaluation matters enough to gate a release decision.

The underlying math for "why 3–5 evaluators": the Nielsen–Landauer formula,
`N(1 − (1 − L)^n)`, with a typical per-evaluator find-rate `L` of 31%, shows that roughly 5
evaluators surface about 85% of findable problems, with sharply diminishing returns beyond that —
this is the empirical justification for "3–5 is enough," not an arbitrary convention.

(NN/g — "10 Usability Heuristics for User Interface Design," https://www.nngroup.com/articles/ten-usability-heuristics/;
"How to Rate the Severity of Usability Problems," https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/;
"How to Conduct a Heuristic Evaluation," https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/;
"Why You Only Need to Test with 5 Users," https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/)

## 2. Cognitive walkthrough — the four questions per step

A cognitive walkthrough is a task-based inspection method distinct from heuristic evaluation: a
solo evaluator simulates a *specific persona* attempting a *specific, defined task*, and at
**every step** of that task asks four fixed questions:

1. Will the user try to achieve the right effect at this step?
2. Will the user notice that the correct action is available?
3. Will the user associate the correct action with the effect they're trying to achieve?
4. After performing the action, will the user see progress toward their goal?

Any single "No" marks that step a **fail**. Preparation required before running a walkthrough:
defined top tasks, defined personas, a working prototype or interface, and a documented expected
task flow. Roles: a facilitator, one or more evaluators, and a recorder logging pass/fail per step
(and, when applicable, per evaluator — a walkthrough can also be run with multiple independent
evaluators the same way a heuristic evaluation is).

This is distinct from a **pluralistic walkthrough**, a group method where a mixed panel (real
users, developers, usability professionals) steps through a task scenario together, each
predicting their own action per step before the facilitator reveals the "correct" one, followed by
group discussion — a live, multi-stakeholder variant rather than a solo-expert simulation.

Both belong to the broader family Nielsen (1989, "Usability engineering at a discount") named
**"discount usability"** — inspection methods that require no recruited end users, are cheap and
fast, and need no lab: this includes heuristic evaluation, cognitive walkthrough, pluralistic
walkthrough, and informal expert review generally. (Nielsen & Molich (1990), "Heuristic evaluation
of user interfaces," is a distinct, separate paper — not the source of the "discount usability"
coinage.)

(NN/g — "Cognitive Walkthroughs: How-To," https://www.nngroup.com/articles/cognitive-walkthroughs/;
"Discount Usability: 20 Years," https://www.nngroup.com/articles/web-discount-usability/;
"Summary of Usability Inspection Methods," https://www.nngroup.com/articles/summary-of-usability-inspection-methods/;
Wikipedia — "Pluralistic walkthrough," https://en.wikipedia.org/wiki/Pluralistic_walkthrough)

## 3. Scripted task-based walkthrough protocol for an agent driving a real browser

The following combines the methods above into one repeatable protocol an agent can actually
execute against a real browser session and score mechanically. This exact combination is not any
single cited source's methodology — it is a synthesis across the pieces above, applied per defined
top task:

1. **Cognitive-walkthrough pass** — step through the task; at every step, answer the four
   questions from §2 and record pass/fail per step, with a one-line reason for any fail.
2. **Heuristic-evaluation pass** — while stepping through, scan each screen encountered against
   the 10 Nielsen heuristics (§1); log a hit with severity 0–4 whenever a heuristic is violated,
   regardless of whether that step passed the cognitive-walkthrough questions (a step can "work"
   and still violate a heuristic, e.g. succeed but with no visible system-status feedback).
3. **Form/error-state pass** — on any form encountered in the task, apply the checklist in §4
   below.
4. **Accessibility smoke pass** — on any screen encountered, apply the mechanical WCAG checks in
   §5 below.
5. **End-of-task ease score** — after completing (or abandoning) the task, record a single-item
   ease rating (a SEQ-style 1–7 "How difficult or easy was this task?" scale) as a coarse summary
   signal alongside the granular per-step findings above.

Academic precedent that agentic execution of something like this is an active, not yet settled,
research area: UXAgent simulates LLM personas driving a browser through a "Universal Browser
Connector" to generate usability findings at scale (arXiv 2504.09407); Avenir-UX combines standard
metrics (SUS, step-wise SEQ) with LLM-analyzed think-aloud reasoning into a UX report (arXiv
2604.09581 [verify URL resolves before citing]); a 2025 preprint directly compares AI-run versus
human-run Nielsen heuristic evaluation, "Synthetic Heuristic Evaluation" (arXiv 2507.02306). Treat
these as evidence the
approach is reasonable and being actively studied, not as a settled, citable standard to defer to
uncritically.

## 4. Form/error-state review

Baymard Institute's audits found that **92% of sites reuse one generic "invalid X" message
regardless of the actual cause** of the validation failure [unverified — confirm at the source
before citing outward] — the single most common form defect
found across audits, and the first thing to check on any form. The fix pattern is **adaptive error
messaging**: for a complex field (card number, password, phone, email), provide 4–7 distinct
messages, each naming the specific problem (e.g. "too short" vs. "contains an invalid character" vs.
"already in use" are different messages, not one generic "invalid" for all three).

Second check: **validation timing**. Live inline validation — checked as the user types or on
blur, before submit — consistently improves error-recovery outcomes over validation that only runs
at submit time, because the user learns about a problem while their attention and context are still
on that field.

Checklist to apply to any form encountered:

- Does every distinct failure cause produce a distinctly worded message, or does the form fall
  back to one generic "invalid" message for multiple different causes?
- Is validation inline (type-time/blur-time) for at least the higher-friction fields, or
  submit-only?
- Does the error message appear adjacent to the field it concerns, and does it remain visible
  (not just flash momentarily)?

(Baymard Institute — "Adaptive (Field-Specific) Error Messages," https://baymard.com/blog/adaptive-validation-error-messages;
"Inline Form Validation," https://baymard.com/blog/inline-form-validation)

## 5. WCAG accessibility smoke checks

WebAIM's WCAG 2 checklist spans four principles — Perceivable, Operable, Understandable, Robust —
across roughly 80+ success criteria at Levels A/AA/AAA, filterable by WCAG version (2.0/2.1/2.2).
A full audit against all of it is out of scope for a routine walkthrough; split the checks into two
tiers:

**Mechanical / DOM-inspectable (runnable without human judgment, e.g. via a browser-snapshot or
DOM-evaluate call):**

- `<html lang>` attribute present and correct
- `<title>` present and descriptive on every page/view
- Visible keyboard-focus indicator when tabbing through interactive elements
- Every `<input>` has an associated `<label>` (or equivalent accessible name)
- `alt` text present on every meaningful image

**Judgment-required (needs a human or an LLM-judgment pass, not pure DOM inspection):**

- Link text is meaningful out of context (not "click here" repeated everywhere)
- Color contrast meets the relevant WCAG level
- DOM reading order matches visual reading order
- Error messages are adequate on their own (ties back to §4)
- Content reflows at 400% zoom without introducing horizontal scrolling

Automated scanners (axe-core — which powers Lighthouse, and is optionally available as a Pa11y
runner, though Pa11y defaults to HTML_CodeSniffer — and WAVE) catch a meaningfully incomplete
slice of real issues; cited coverage estimates range from roughly 20% to 70% depending on source,
with one cross-tool analysis of 300k+ issues across 13k pages [unverified — confirm at the source
before citing outward] putting automated coverage at roughly 57% by volume [unverified — confirm
at the source before citing outward]. No single automated tool covers all of WCAG
2.2 — treat a clean automated scan as a floor, not a completion signal, and always still run the
judgment-required checks above by inspection.

(WebAIM — "WCAG 2 Checklist," https://webaim.org/standards/wcag/checklist;
a11yflow — "How accessibility scores are calculated," https://www.a11yflow.dev/blog/how-accessibility-scores-are-calculated;
a11yflow — "axe vs. Lighthouse vs. WAVE vs. Pa11y," https://www.a11yflow.dev/blog/axe-vs-lighthouse-vs-wave-vs-pa11y)

## 6. Walkthrough report shape

A completed walkthrough report should always be structured the same way, so findings are
comparable across tasks and across runs:

- **Per-task verdict** — for each defined top task: pass/fail (did the cognitive-walkthrough
  sequence complete with no failing step), plus the end-of-task ease score (§3.5).
- **Severity-scored findings list** — every heuristic-evaluation hit (§3.2), form/error-state
  issue (§4), and accessibility issue (§5), each with: the heuristic or checklist item violated,
  a severity score (0–4, per the §1 scale), the specific screen/step it occurred on, and a
  one-to-two-sentence description of the problem and why it matters (not just "violates heuristic
  #4" — state the actual user-facing consequence).
- **Screenshot references** — a captured screenshot (or DOM snapshot reference) for every
  reported finding, so a reviewer can verify the finding without re-running the walkthrough
  themselves. A finding with no visual evidence attached is materially harder to triage and should
  be the exception, not the norm.

This shape — per-task pass/fail plus a severity-ranked, screenshot-backed findings list — is what
makes a walkthrough's output usable as an input to triage (which findings are launch-blocking, per
the severity-4 threshold in §1) rather than a narrative summary that has to be re-interpreted by
whoever reads it.

## Sources

- NN/g — "10 Usability Heuristics for User Interface Design" — https://www.nngroup.com/articles/ten-usability-heuristics/
- NN/g — "How to Rate the Severity of Usability Problems" — https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/
- NN/g — "How to Conduct a Heuristic Evaluation" — https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/
- NN/g — "Cognitive Walkthroughs: How-To" — https://www.nngroup.com/articles/cognitive-walkthroughs/
- NN/g — "Why You Only Need to Test with 5 Users" — https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/
- NN/g — "Discount Usability: 20 Years" — https://www.nngroup.com/articles/web-discount-usability/
- NN/g — "Summary of Usability Inspection Methods" — https://www.nngroup.com/articles/summary-of-usability-inspection-methods/
- Wikipedia — "Pluralistic walkthrough" — https://en.wikipedia.org/wiki/Pluralistic_walkthrough
- UsabilityBOK — "Pluralistic Walkthrough" — https://www.usabilitybok.org/pluralistic-walkthrough/
- WebAIM — "WCAG 2 Checklist" — https://webaim.org/standards/wcag/checklist
- a11yflow — "How accessibility scores are calculated" — https://www.a11yflow.dev/blog/how-accessibility-scores-are-calculated
- a11yflow — "axe vs. Lighthouse vs. WAVE vs. Pa11y" — https://www.a11yflow.dev/blog/axe-vs-lighthouse-vs-wave-vs-pa11y
- Baymard Institute — "Adaptive (Field-Specific) Error Messages" — https://baymard.com/blog/adaptive-validation-error-messages
- Baymard Institute — "Inline Form Validation" — https://baymard.com/blog/inline-form-validation
- arXiv 2504.09407 — UXAgent — https://arxiv.org/abs/2504.09407
- arXiv 2604.09581 — Avenir-UX — https://arxiv.org/pdf/2604.09581 [verify URL resolves before citing]
- arXiv 2507.02306 — "Synthetic Heuristic Evaluation" — https://arxiv.org/pdf/2507.02306
