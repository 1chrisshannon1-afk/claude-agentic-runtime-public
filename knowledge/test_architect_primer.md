# Test Architect Primer

Product-agnostic reference for an agent performing test-suite and observability oversight — is the
suite shaped right, does it prove anything, is it stable, does it run in budget, and can a human or
an AI agent debug a production incident from the logs alone. This primer has no app-specific facts,
paths, tenant names, or numbers; a given product's actual suite composition, flaky-test history, and
logging surfaces belong in that product's own dossier, not here.

## 1. Test-pyramid economics

The shape is an economic argument, not an aesthetic preference (Ham Vocke, "The Practical Test
Pyramid," published on martinfowler.com): write *lots* of small, fast unit tests; write *some* more coarse-grained integration
tests; write *very few* high-level end-to-end tests. Cost and speed both degrade climbing the
pyramid — unit tests run in milliseconds and can execute in the thousands; integration tests
exercise one integration point at a time (a database, an external service) and are correspondingly
slower and more expensive to set up; UI/E2E tests are the slowest and most fragile tier (real
browser automation, a full running system with all its dependencies) and should be reserved for
covering critical user journeys only, not every code path.

Martin Fowler's own framing (from his separate "TestPyramid" bliki entry) of what a high-level-test
failure actually means: "If you get a failure in a high-level test, not just do you have a bug in
your functional code, you also have a missing or incorrect unit test." A bug caught only at the
E2E layer is itself a finding — it means unit coverage has a gap, not merely that the E2E suite
did its job.

The named anti-pattern is the **"ice-cream cone"** — an inverted pyramid with too much high-level
testing relative to unit testing — called out explicitly as a maintenance nightmare: slow feedback,
expensive-to-diagnose failures, and a suite that discourages running tests often because each run
is slow. The corrective instinct is always to "push tests as far down the pyramid as you can" —
before adding a new E2E case, ask whether the same defect class could be caught by a unit or
integration test instead.

(Ham Vocke — "The Practical Test Pyramid" (published on martinfowler.com), https://martinfowler.com/articles/practical-test-pyramid.html;
quote above from Martin Fowler — "TestPyramid," https://martinfowler.com/bliki/TestPyramid.html)

## 2. Mutation testing as net-quality proof

Coverage answers "was this line executed by some test." It does not answer "would a test have
caught it if this line were wrong" — a test that executes a line but asserts nothing on it still
shows 100% line coverage and would not fail if that line's logic were broken. Mutation testing
answers the second question directly.

Mechanism: a mutation-testing tool injects small, mechanical changes into the production code
(flip a boundary condition, swap an operator, remove a line) and reruns the — previously fully
green — test suite against each mutant. A mutant is **killed** if some test now fails; it
**survives** if the suite stays green. A surviving mutant is proof, not a guess, that the suite
would not have caught that specific class of defect. Tooling requires a genuinely green baseline
before it will even run (PIT, the Java tool, explicitly errors "tests did not pass without
mutation" if the pre-mutation suite isn't clean).

What mutation testing catches that coverage alone misses: wrong boundary conditions, wrong
operators, missing error-handling branches, and — critically — weak or absent assertions.

Score interpretation is not backed by a single primary academic threshold, but converges across
multiple secondary sources: a mutation score above roughly 80% is treated as a strong quality
signal; below roughly 70% is treated as weak. Representative tooling: Stryker (JavaScript/
TypeScript/C#/Scala), PIT/PITest (Java), and first-party Microsoft Learn coverage of the technique
for .NET.

(nexocode — "Mutation testing," https://nexocode.com/blog/posts/mutation-testing/;
getautonoma — "Mutation testing vs. code coverage," https://getautonoma.com/blog/mutation-testing-vs-code-coverage/;
PITest issue tracker (baseline-must-be-green behavior), https://github.com/hcoles/pitest/issues/1272)

## 3. Characterization vs. intent tests — the lock-in-test disease

Michael Feathers coined **characterization test** in *Working Effectively with Legacy Code* (2004),
where he also defines legacy code itself as "code without tests." A characterization test (also
called a Golden Master test) records the code's *actual, currently observed* behavior and asserts
against that going forward — it is a change-detector, not a correctness-validator. It "checks that
no properties have been changed," in contrast to an intent/spec-based test, which asserts that
specific properties hold a *specified* correct value regardless of what the code currently happens
to do.

Characterization testing is a legitimate, deliberate technique when wrapping legacy code that has
no tests and no clear spec — it creates a safety net before refactoring. The disease — call it a
**lock-in test** — is applying the same technique to code that *does* have an intended behavior:
writing a test by running the code once and asserting whatever it happened to output, rather than
reading the spec (contract, schema, docstring, user story) and asserting what it is *supposed* to
output. A lock-in test passes trivially against a bug, because it was written by observing the bug.
It then actively defends the bug against a future fix, since the fix will make the "test" fail.

There is no single external term of art matching "lock-in test" exactly — the nearest documented
equivalents in the literature are Feathers' characterization test when misapplied to new code, and
the general "assert-current-behavior-as-correct" anti-pattern described in unit-testing
anti-pattern literature as tests coupled to implementation rather than to intended behavior. The
operational rule either way is the same: before writing or fixing a test, read the spec, not the
just-written code; if the code doesn't match the spec, fix the code, not the test.

(Wikipedia — "Characterization test," https://en.wikipedia.org/wiki/Characterization_test)

## 4. Flaky-test management

A flaky test is one that gives different results (pass/fail) on identical reruns of identical code
— it erodes trust in the suite and, left unmanaged, trains engineers to re-run-until-green instead
of investigating failures. The general industry pattern, converging across multiple sources:

- **Detect** by comparing results of the same commit run multiple times, or by tracking a test's
  pass/fail history over time and flagging inconsistency above a threshold.
- **Quarantine**, don't delete: a flagged test is removed from the CI-*blocking* critical path (it
  no longer fails a merge) but keeps executing so failure data keeps accumulating.
- **Ticket + owner + expiry**: quarantine comes with a filed ticket, an assigned owner, and a
  bounded maximum stay — commonly cited as 2–4 weeks — after which the test must be fixed or
  formally retired. An indefinitely quarantined test is a silent coverage hole, not a fixed
  problem.

(Google Testing Blog — "Flaky Tests at Google and How We Mitigate Them,"
https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html;
Mergify — "Test quarantine," https://mergify.com/learn/test-quarantine)

## 5. Test-suite runtime budgets

A **test budget** is a fixed CI time allowance the suite must fit inside; when a suite risks
exceeding it, execution order is reprioritized to fail fast (run the tests most likely to catch a
regression, or most recently broken, earlier) rather than simply accepting a slower pipeline.
Commonly cited targets (no single primary standard, but multiple overlapping secondary sources
converge): a fast-feedback/commit-stage loop under roughly 10 minutes, a full pre-merge suite under
roughly 30 minutes, and per-test targets in the sub-2-second range at the unit-test tier.
**Test-impact analysis** — running only the subset of tests actually touched by a given diff's
dependency graph — is the named lever for keeping a large suite inside budget without cutting
coverage outright; the alternative of simply deleting slow tests trades signal for speed instead of
buying both.

(Shopify Engineering — "Test budget: a time-constrained approach to CI feedback,"
https://shopify.engineering/test-budget-time-constrained-ci-feedback;
thoughtbot — "Introducing test budget," https://thoughtbot.com/blog/introducing-test-budget)

## 6. Falsifiability discipline

A test's value is proven only by demonstrating that it *can* fail. Formalized directly in mutation
testing: "if nothing fails [when a mutation/defect is injected], a test is missing or needs to be
rewritten." This is structurally the same claim as the single-fix version of falsifiability: revert
the production change, keep the new test, confirm the test goes **red**; reapply the fix, confirm
**green**. A test that has never been observed to fail against the un-fixed code is not evidence
that the fix works — it may simply never execute the changed lines, or it may pass identically
whether the fix is present or not. Mutation testing is this same discipline automated and applied
across the entire codebase's defect space, rather than to one fix's specific lines at a time.

Practical application for an oversight agent: when asked to verify a "fix," do not accept a green
run as evidence on its own — ask whether the test was seen to fail without the fix. If that check
was never performed, the fix is unverified regardless of the suite's current color.

(getautonoma — "Mutation testing vs. code coverage," https://getautonoma.com/blog/mutation-testing-vs-code-coverage/)

## 7. Observability: structured logging, correlation, and the "stranger can troubleshoot" bar

**Three pillars of observability**, definitions stable and convergent across many independent
sources:

- **Logs** — discrete, timestamped event records (structured or plain text); the forensic/
  historical record, best for root-cause analysis and anomaly detection after the fact.
- **Metrics** — numerical, time-series measurements (latency, error rate, resource utilization);
  cheap to store at scale, best for trend and threshold-based alerting.
- **Traces** — the per-request or per-transaction flow across services; best for latency
  attribution and localizing a bottleneck in a distributed call chain.

**Structured-logging practice:**

- **Levels**, from least to most severe: DEBUG (dev-only detail, off in production except during
  active incident investigation) → INFO (normal events, the typical production default) → WARN
  (risk or degraded condition, not yet a failure) → ERROR (a failure) → FATAL (process-ending).
  Logging at the wrong level in either direction defeats the purpose — DEBUG noise buried in
  production INFO logs drowns the signal; a real failure logged at INFO gets missed by
  alerting tuned to WARN/ERROR.
- **Correlation/request IDs.** Generate one ID at the entry point (the first service or gateway
  that sees a request), propagate it through every downstream call (commonly a header such as
  `X-Correlation-ID` or equivalent), and stamp it into every log line emitted anywhere in that
  request's chain. This one mechanism is what lets a person — or an agent — reconstruct a single
  request's full path across services from logs alone, without reproducing the issue locally.
- **Cardinality discipline.** High-cardinality fields (user ID, tenant ID, request ID) are
  explicitly *good* to include as log fields, for searchability and correlation. They must not be
  promoted into metrics-label dimensions — tagging a metric with a per-user or per-request label is
  the specific mechanism that blows up time-series cardinality and cost. The rule: log it as a
  field; never tag it as a metric dimension.

**The bar for "a stranger, or an AI agent, can troubleshoot from the logs without reproducing the
issue"** (synthesized, convergent across sources): a timestamped, correlation-ID-tagged log line at
every meaningful state transition and every external-call boundary (request sent, response
received, with status and duration); enough context in that trail to reconstruct the timeline of an
incident purely from logs, with no need to run the code locally; and explicit, systematic exclusion
of secrets and PII from every log line — never log a password, a token, or a full card number, even
at DEBUG level.

**Error-tracking triage** (Sentry-flavored pattern, generalizes to any error-tracking tool): issues
are fingerprinted primarily off stack trace plus error type, so grouping quality depends on stack
traces being meaningful (not swallowed/wrapped into a generic exception). Alert rules should fire on
severity or frequency *spikes*, not on every new event — "notify on all new issues" as a default is
explicitly a noise problem to configure away from. When triaging, weight the call stack highest,
then breadcrumbs/context (browser, device, release, environment tags) as secondary signal.

(sematext — "Three pillars of observability," https://sematext.com/glossary/three-pillars-of-observability/;
dash0 — "Structured logging for modern applications," https://www.dash0.com/guides/structured-logging-for-modern-applications;
Broadlume Product — "Sentry: three best practices for error management," https://medium.com/broadlume-product/sentry-three-best-practices-for-error-management-afc07bade57;
makandra — "Controlling issue grouping (Sentry)," https://makandracards.com/makandra/484983-controlling-issue-grouping-sentry)

## 8. What a test + logging audit measures

A converging set across multiple QA-dashboard sources (no single primary standard, but consistent
across sources) for the test-quality half:

1. **Pass rate** — percentage of test runs succeeding.
2. **Flake rate** — percentage of tests giving inconsistent results on identical reruns (a commonly
   cited concrete example: 5% flake rate, i.e. roughly 1-in-20 runs noisy, treated as worth
   investigating).
3. **Coverage** — percentage of code exercised. Flagged everywhere as necessary but insufficient on
   its own; must be paired with mutation score, since 100% coverage with zero assertions still
   passes trivially.
4. **Mutation score** — the assertion-strength complement to coverage (§2 above).
5. **MTTR (test)** — time from a build going red to going green again; a low MTTR signals failures
   are treated as real signals and acted on, not re-run-until-green or ignored.
6. **Escaped defects** — bugs that reached production despite the suite.
7. **Suite runtime** — wall-clock time for a full run, checked against the runtime budget (§5).

The observability/logging half of an audit is less standardized in the literature — no equivalent
named metric set surfaced as a single accepted standard. The closest parallel measures, by analogy
to the test-quality set above: coverage of the three pillars for each request path (does every
external-call boundary produce a log line, a metric, and — where distributed — a trace),
completeness of correlation-ID propagation (does every downstream hop actually carry and log the
ID, or does it silently drop partway through), and MTTR-to-diagnose (distinct from MTTR-to-green
above — time from an incident being noticed to root cause being identified from logs/traces alone,
without local reproduction). Treat this half as needing an explicit, bespoke definition per product
rather than assuming an off-the-shelf standard exists.

(getautonoma — "QA metrics dashboard," https://getautonoma.com/blog/qa-metrics-dashboard;
Better Stack — "Logging best practices," https://betterstack.com/community/guides/logging/logging-best-practices/)

## 9. Metamorphic testing and the oracle problem

The **oracle problem** is the condition where a system's correct output for a given input is
difficult or impossible to state in advance — not because the system can't be run, but because no
independent mechanism exists to check any single execution's result against a known-correct value
(Tsong Yueh Chen, Fei-Ching Kuo, Huai Liu, Pak-Lok Poon, Dave Towey, T. H. Tse, Zhi Quan Zhou —
"Metamorphic Testing: A Review of Challenges and Opportunities," ACM Computing Surveys 51(1),
Article 4, 2018). Most testing assumes an oracle exists: run the input, compare the output to a
known-correct value, pass or fail. Metamorphic testing (MT) is the technique for when that
comparison is unavailable. It does not attempt to state what one output should be; it states a
relationship that must hold between the outputs of two or more *related* executions, and checks
that relationship instead of any absolute value.

The unit of the technique is the **metamorphic relation (MR)**: a necessary property of the target
function over a sequence of two or more inputs and their corresponding outputs, formalized as
R ⊆ Xⁿ × Yⁿ for n ≥ 2 (Chen et al. 2018, Definition 1). Given a **source test case** and its
output, an MR specifies how to derive a **follow-up test case** — by transforming the source input
in some defined way — plus the relationship the follow-up output must bear to the source output.
Neither output has to be independently verified; only the relationship between the two does. A
violation is a *necessary*, not merely probable, sign of a fault, because the relation is a
property the correct implementation is logically required to satisfy (Sergio Segura, Gordon
Fraser, Ana B. Sanchez, Antonio Ruiz-Cortés — "A Survey on Metamorphic Testing," IEEE Transactions
on Software Engineering 42(9), pp. 805–824, 2016). The canonical illustration in both surveys:
nobody can state sin(12°) from memory, but sin(x) = sin(π − x) is a property of the sine function
itself, checkable without knowing either value. Metamorphic testing traces to a 1998 technical
report by T. Y. Chen, S. C. Cheung, and S. M. Yiu, "Metamorphic Testing: A New Approach for
Generating Next Test Cases" (HKUST-CS98-01, Department of Computer Science, Hong Kong University
of Science and Technology) — cited directly by both surveys above; this primer could not reach the
original document itself this session (a DNS failure on the HKUST host), so the citation rests on
the two secondary sources that were read in full, not on the primary text.

Identifying good MRs is explicitly not mechanical — both surveys describe it as requiring
creativity and domain knowledge about the function under test, with known patterns serving as a
starting aid rather than a derivation procedure. One recurring taxonomy, originally proposed for
numerical and machine-learning functions by Murphy et al. (2008) and tabulated by Upulee Kanewala
and James M. Bieman ("Using Machine Learning Techniques to Detect Metamorphic Relations for
Programs without Test Oracles," IEEE ISSRE 2013 — Murphy et al.'s own paper was not itself fetched
this session), names MR classes by the shape of the input transformation: **additive** (add or
subtract a constant), **multiplicative** (scale by a constant), **permutative** (reorder the
input's elements), **invertive** (invert each element), **inclusive** (add a new element), and
**exclusive** (remove an element) — plus a **compositional** class that merges two or more source
inputs into one follow-up input. These are patterns for *generating* candidate MRs from a
function's structure, not a checklist every system must satisfy against; which classes are
meaningful depends entirely on the domain.

Determinism (repeatability) testing sits at the boundary of this framework rather than squarely
inside it, and the honesty this primer applies elsewhere holds here too: Chen et al.'s 2018 survey
explicitly excludes a closely related family — N-version programming and differential testing,
which compare multiple executions against one *shared* input — from the formal MR definition by
name, stating that such a property "does not involve multiple different inputs... it is not
regarded as an MR" even though it spans multiple executions. That same stated reasoning applies
with equal force to a pure determinism check (same program, same input, run twice): no clause in
the source names determinism testing directly, but it is exactly this same-input,
multiple-execution shape, so strictly it sits outside formal MR scope as well. Structurally it is
still the design's degenerate case — a follow-up input equal to the source input (the identity
transformation) paired with an equality output relation — and it shares MT's central move of
substituting a relationship across executions for an absolute per-output oracle. Treat it as MT's
nearest relative and the cheapest member of the same family to automate, not as a citable instance
of Chen's own MR definition.

Grounded for a system that turns an AI-interpreted scope of work into a cost estimate: no primary
source states what a given remodel *should* cost, so no oracle exists for any single estimate's
absolute dollar figure — the oracle problem in its purest form. Relational properties survive that
absence. A multiplicative-class MR holds regardless: doubling a room's area in the source scope,
with every other input fixed, must produce a strictly higher total in the follow-up estimate — the
exact multiplier is unspecified and unenforceable, but the direction is a necessary property of
any correctly implemented pricing function, checkable with no reference price at all. An
inclusive-class MR holds similarly: adding a fixture to an otherwise-identical scope must never
lower the total. And the identity/determinism check — same scope in, same estimate out, on every
run — is the cheapest MR-adjacent test available and the one most worth automating first,
precisely because an AI-interpretation step in the pipeline is exactly the kind of component most
likely to violate it silently.

(Tsong Yueh Chen, Fei-Ching Kuo, Huai Liu, Pak-Lok Poon, Dave Towey, T. H. Tse, Zhi Quan Zhou —
"Metamorphic Testing: A Review of Challenges and Opportunities," ACM Computing Surveys 51(1),
Article 4, 2018 (read via technical-report mirror), https://www.cs.hku.hk/data/techreps/document/TR-2017-04.pdf;
Sergio Segura, Gordon Fraser, Ana B. Sanchez, Antonio Ruiz-Cortés — "A Survey on Metamorphic
Testing," IEEE Transactions on Software Engineering 42(9), pp. 805–824, 2016 (read via open-access
author copy), https://eprints.whiterose.ac.uk/id/eprint/110335/1/segura16-tse.pdf;
Upulee Kanewala, James M. Bieman — "Using Machine Learning Techniques to Detect Metamorphic
Relations for Programs without Test Oracles," IEEE ISSRE 2013 preprint,
https://www.cs.colostate.edu/~bieman/Pubs/KanewalaBiemanISSRE2013preprint.pdf;
Sergio Segura, Amador Durán, Javier Troya, Antonio Ruiz-Cortés — "Metamorphic Relation Patterns
for Query-Based Systems" (attributes the additive/multiplicative/permutative/invertive/
inclusive/exclusive taxonomy to Murphy et al., 2008), https://personal.us.es/sergiosegura/files/papers/segura19-met.pdf;
Wikipedia — "Metamorphic testing," https://en.wikipedia.org/wiki/Metamorphic_testing. The original
1998 T. Y. Chen, S. C. Cheung, and S. M. Yiu technical report, HKUST-CS98-01, was not
independently reachable this session — a DNS failure on the HKUST host — and is cited above only
via the two surveys that quote it directly.)

## 10. Property-based testing

An example-based test picks one input, runs the code, and asserts one expected output — it proves
the code is correct for that single point. A property-based test instead asserts a
**universally-quantified property**: a statement that must hold for *every* input in some
described space, then hands a framework the job of generating many inputs from that space and
checking the property against each one. The technique originates with QuickCheck, introduced by
Koen Claessen and John Hughes in "QuickCheck: A Lightweight Tool for Random Testing of Haskell
Programs" (ICFP 2000): the programmer supplies a specification as properties functions should
satisfy, and the tool tests that the properties hold across a large number of randomly generated
cases rather than a hand-picked few. Hypothesis, the dominant Python implementation, frames the
same idea for a mainstream audience: "you write tests which should pass for all inputs in whatever
range you describe, and let Hypothesis randomly choose which of those inputs to check — including
edge cases you might not have thought about." Both sources are explicit that this is additive, not
a replacement — Hypothesis's own tutorial states plainly, "Property-based testing is a powerful
addition to unit testing. It is not always a replacement."

**Generators** (QuickCheck calls them `Arbitrary` instances; Hypothesis calls them strategies)
describe the space of valid inputs — not a fixed list of values but a distribution the framework
samples from, including boundary and pathological cases a human author would not think to write by
hand (empty collections, negative numbers, `NaN`, deeply nested structures). This is the core
value proposition over example-based tests: the space searched is far larger than any
hand-authored example set, and it is searched by the machine rather than the author's imagination.

**Shrinking** is what makes a found counterexample usable. A property that fails on some large,
framework-generated input is not itself a good bug report — a five-hundred-element list with one
bad value buried inside it tells a developer little. QuickCheck's original paper describes the fix
directly: "once such a test case is found, QuickCheck tries to reduce it to a minimal failing
subset by removing or simplifying input data that are unneeded to make the test fail." Hypothesis
performs the same reduction automatically and reports the *simplest* falsifying example it can
find — its own introductory tutorial shows a float-list property collapsing a large generated
failure down to a minimal case like `[1.0, nan, 0]`. The framework — not the test author — owns
the search for both the counterexample and its simplest form.

For pricing and quantity logic specifically, several property classes recur. **Wlaschin's
"Choosing properties for property-based testing"** (F# for Fun and Profit) names the ones most
directly useful here, though — as with several patterns catalogued elsewhere in this primer — this
is a practitioner taxonomy converging across the property-based-testing community rather than a
single formal academic standard: **invariants** ("some things never change" — a transformation
preserves some measured quantity, e.g. a line-item list's computed subtotal equals the sum of its
parts regardless of the order items were added); **round-trips** ("there and back again" —
combining an operation with its inverse returns the original state, e.g. serializing a priced
estimate to a wire format and back yields an equivalent object); **idempotence** ("the more things
change, the more they stay the same" — applying an operation twice equals applying it once, e.g.
re-running a rounding or markup pass on an already-rounded total must not change it further); and
**oracle-comparison** (checking a fast or optimized implementation's output against a reference
implementation — a brute-force quantity calculation, or a prior engine version, standing in for a
known-correct answer where no closed-form expected value exists). **Monotonicity** — an ordering
relation preserved under transformation, e.g. increasing a quantity input never decreases total
price — is a common and directly relevant property in pricing logic but does not map onto one of
Wlaschin's seven named categories cleanly; it is best read as a specialization of the invariant
class rather than a separately sourced pattern.

Property-based testing and **metamorphic testing** are close relatives, not separate disciplines.
Metamorphic testing, introduced in a 1998 technical report by Chen, Cheung and Yiu (§9 above), is
itself described as "a property-based software testing technique," and its **metamorphic relations
(MRs)** are "necessary properties of the intended functionality of the software, and must involve
multiple executions of the software" — the canonical example being sin(x) = sin(π − x): running
the same function twice on related inputs and checking the outputs stay related, rather than checking
either output against a known value. This is precisely the answer to the test-oracle problem in
domains — like AI-interpreted pricing — where no ground-truth expected value exists for an
arbitrary input: an MR that "doubling every quantity in a scope must not more than double the
total price" (a monotonicity/scaling property checked across two related executions) is a
metamorphic relation, and the mechanism is the same generate-and-check loop as any other property
test, just applied across a pair or sequence of executions instead of one.

(Koen Claessen and John Hughes — "QuickCheck: A Lightweight Tool for Random Testing of Haskell
Programs," ICFP 2000, https://www.cse.chalmers.se/~rjmh/QuickCheck/ and
https://en.wikipedia.org/wiki/QuickCheck;
Hypothesis documentation — https://hypothesis.readthedocs.io/en/latest/ and
https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html;
Scott Wlaschin — "Choosing properties for property-based testing," F# for Fun and Profit,
https://fsharpforfunandprofit.com/posts/property-based-testing-2/;
Wikipedia — "Metamorphic testing," https://en.wikipedia.org/wiki/Metamorphic_testing)

## 11. Test-double taxonomy

Gerard Meszaros's *xUnit Test Patterns* (2007) named five distinct kinds of stand-in object under
the umbrella term **test double** (an analogy to a film stunt double), specifically to end the
practice of calling every substitute object "a mock" regardless of what it actually does. Martin
Fowler adopted Meszaros's vocabulary directly in both his bliki entry on the term and in "Mocks
Aren't Stubs," and the definitions below are Meszaros's as Fowler quotes them — Meszaros's own
companion site to the book, xunitpatterns.com, could not be reached this session (a connection
failure on both a direct fetch and an archive.org retry), so the taxonomy here is sourced via
Fowler's direct citation of Meszaros's terminology, not independently cross-checked against the
original book or site itself. A **dummy** is an object "passed around but never actually used,"
existing only to satisfy a constructor or parameter list — it proves nothing and asserts nothing.
A **stub** "provides canned answers to calls made during the test, usually not responding at all
to anything outside what's programmed in for the test" — it exists to put the subject under test
(SUT) into a controlled state or feed it a controlled input, and a passing test using one proves
only that the SUT produced the right *state or output given that input*. A **spy** is "a stub that
also records some information based on how it was called" (Fowler's example: an email-sending
double that counts messages sent) — it lets a test assert on calls made *after the fact*, from
data the double happened to capture, rather than from a pre-declared expectation. A **mock** is
"pre-programmed with expectations which form a specification of the calls they are expected to
receive," and it self-verifies: it fails the test itself, via an exception on an unexpected call
or a `verify()` step that checks every expected call arrived. A mock proves that the SUT *called
its collaborators in the specified way* — a claim about interaction, not about resulting state. A
**fake** is different in kind from the other four: it "has a working implementation, but usually
takes some shortcut which makes it not suitable for production" (an in-memory database standing in
for a real one). A fake proves the SUT behaves correctly against realistic collaborator behavior
at unit-test speed — but only as faithfully as the fake's shortcut implementation actually tracks
the real dependency's behavior, which is itself an unverified assumption unless the fake is
separately contract-tested against the real thing (§14).

These five are not interchangeable, and substituting one for another silently changes what a
passing test can and cannot demonstrate. Swapping a stub for a mock in the same slot turns a test
from asserting "given this input, the SUT produces the right output" into asserting "the SUT
emitted this exact call" — a fundamentally different claim, and one that fails for a different
reason when it breaks. Reading a test's double type is therefore not a naming nicety; it is how a
reviewer knows what the test is actually proving, and confusing a spy's after-the-fact recording
with a mock's pre-declared expectation, or a stub's "any input in, canned output out" with a
fake's "real logic, lightweight implementation," misreads the test's evidentiary claim in exactly
the way loose terminology invites (§3's characterization-test discipline is the same failure mode
one layer down — what a test actually proves versus what it is assumed to prove).

Fowler's "Mocks Aren't Stubs" frames the deeper fork this taxonomy sits on top of: **classical**
(sometimes "Detroit school") testing uses real collaborator objects wherever feasible and reaches
for a double only when the real one is awkward — slow, non-deterministic, external — and verifies
by inspecting the resulting *state* of the SUT and its collaborators. **Mockist** ("London school")
testing substitutes a mock for any collaborator with interesting behavior and verifies by checking
that the SUT made the *correct calls*, using this discipline to drive outside-in, interaction-first
design. This is a genuine design-philosophy fork, not a tooling preference: a mockist test is
coupled to the SUT's internal call pattern in a way a classical, state-verifying test is not, so a
refactor that changes *how* the SUT collaborates internally while leaving its observable output
identical breaks the mockist test and leaves the classical one green.

Mocking the SUT itself — rather than its collaborators — is always a defect, and it is defect by
definition rather than by degree: the entire premise of a test double is that it substitutes for
something *around* the code being exercised so the real code can run and be observed (Vladimir
Khorikov, enterprisecraftsmanship.com, states the premise flatly: "you obviously don't want to
mock the system under test itself"). Replace the SUT with a double and no production code executes
at all — the test can only ever validate the double's own scripted or recorded behavior, so it
cannot fail against a real defect in the thing it claims to test, violating the falsifiability bar
this primer already applies to any test (§6).

Over-mocking — reaching for a mock or stub against internal collaborators rather than true external
boundaries — produces the implementation-coupling problem for a related but distinct reason.
Khorikov's distinction is useful here: calls between classes *inside* one application are
implementation detail, while calls the application makes *out* to another system are its
observable behavior; only the latter (and, more narrowly, only the *unmanaged* out-of-process
dependencies the team doesn't fully control — a third-party API, an SMTP server — rather than a
managed one like the application's own database) are legitimate candidates for a double at all.
Mocking an internal collaborator turns a test's assertion into a claim about the SUT's internal
call graph rather than its externally observable result, so any refactor that reshapes that
internal collaboration — even one that leaves behavior completely unchanged — breaks the test. The
team then either fixes tests on every refactor or stops refactoring; either way the suite has
stopped protecting behavior and started pinning implementation, the same structural failure §3
names for lock-in tests, expressed at the level of *how objects talk to each other* instead of
*what a function returns*.

(Gerard Meszaros's test-double taxonomy as quoted and applied by Martin Fowler — "Mocks Aren't
Stubs," https://martinfowler.com/articles/mocksArentStubs.html;
Martin Fowler — "TestDouble" (bliki), https://martinfowler.com/bliki/TestDouble.html;
Vladimir Khorikov, enterprisecraftsmanship.com — "When to Mock,"
https://enterprisecraftsmanship.com/posts/when-to-mock/)

## 12. Test-smell taxonomy

Where §§1–11 treat test quality as measurable percentages (coverage, mutation score, flake rate), a
**test smell** names a specific structural symptom in the test code itself — the test-code
analogue of Fowler's production-code smells. The term was coined by van Deursen, Moonen, van den
Bergh, and Kok in "Refactoring Test Code" (2nd International Conference on Extreme Programming and
Flexible Processes in Software Engineering, University of Cagliari, pp. 92–95, 2001), which
catalogued eleven test smells and paired each with a specific refactoring; Meszaros later broadened
the catalog in *xUnit Test Patterns: Refactoring Test Code* (2007), adding further smells and
distinguishing test smells proper from behavior smells and project smells. The original 2001 paper
itself was not independently fetchable this run (paywalled, no open mirror found); the definitions
and refactorings below are drawn from Bavota, Qusef, Oliveto, De Lucia, and Binkley's empirical
study (ICSM 2012), which reproduces van Deursen et al.'s smell-definition table directly with page
citations.

**Assertion roulette** is several assertions inside one test method with no explanation of what
each one checks; when one fails, the stack trace alone does not say which assertion broke or why.
The fix is to attach an explanatory message to every assertion, or split the method into one test
per logical check. The measured cost is severe and specific: in Bavota et al.'s controlled
experiment, subjects asked to identify which line of a failing test generated a given error trace
scored 0% correctness in the presence of Assertion Roulette against 90% correctness on the same
class without it — and Assertion Roulette was also the single most common smell across the 18
systems studied, present in 62% of JUnit classes analyzed.

**Eager test** is a test method that checks several methods of the object under test in one go, so
a failure doesn't localize which behavior broke and the method's name and body no longer describe
one thing. The fix is Extract Method: split the eager test into one test per method under test,
each exercising and asserting on a single behavior.

**Mystery guest** is a test whose fixture data lives outside the test method — an external file, a
database row — so a reader cannot see the cause-and-effect relationship between setup and
assertion inside the test itself, and the test becomes fragile against changes to that external
state. The fix is an Inline Resource refactoring: pull the needed data into the test as a literal
or an in-memory fixture, removing the hidden external dependency. In the same experiment, Mystery
Guest dropped subject correctness from 83% to 22% — the largest single swing of any smell measured.

**General fixture** is a shared `setUp()` that builds more state than any one test method needs, so
tests carry dependencies they never exercise and an unrelated change to the fixture can break a
test that doesn't touch the field that changed. The fix is to split the fixture into smaller,
per-test setups — extracting only the state each test actually uses rather than one shared
superset built for the union of all tests in the class.

**Indirect testing** is a test for object A that asserts on behavior it reaches through some other
object B, rather than testing A directly; a defect in B then surfaces as a failure in A's tests,
misdirecting debugging effort toward the wrong class. The fix, per secondary literature
summarizing van Deursen et al. (not independently verified against the original text), is Extract
Method followed by Move Method: pull the indirect assertions out and relocate them into a test
class for the object they actually exercise.

**Test code duplication** is the same setup or assertion logic copied across multiple test methods
or classes instead of factored into a shared helper — the same Extract Method discipline used for
duplication in production code, applied to test code, so a change to the behavior under test
doesn't require updating N separate copies.

**Sensitive equality** is an assertion that compares objects via their `toString()` output rather
than a real equality or property check, so the test breaks whenever the string representation
changes even though the underlying behavior didn't. The fix is to replace the `toString()`
comparison with a dedicated `equals` or field-level check.

**For testers only** is the one smell of the eight that lives in production code rather than test
code: a production class exposes a method used only by test code, with no real caller anywhere in
the running system. The fix, again via secondary characterization rather than the original text,
is Extract Subclass — move the test-only method out of the production interface and into the test
code, rather than letting test convenience widen the shipped API surface.

A scanner that implements these as named, syntactic detection rules — an assert with no message
string, a `setUp()` field a given test method never touches, a `toString()` call inside an assert,
a test class invoking methods outside the class it targets — routes each finding to exactly one of
these structural causes and, through the cause, to exactly one refactoring. That is the practical
payoff over an undifferentiated "this test file is bad": Bavota et al.'s detector, built on rules
this simple (e.g. "at least one method that uses more than one method of the tested class" for
Eager Test), still achieved high per-smell precision once manually validated, and their
co-occurrence data shows multiple smells regularly compound in the same class — Lazy Test co-occurs
with Eager Test 78% of the time in their sample — which argues for naming each one separately
rather than collapsing them into one opaque debt score: a single test class can carry several
independent, separately-fixable defects at once, and only a named taxonomy lets a fix target the
one actually present.

(Brent van Bladel & Serge Demeyer — "Test Refactoring: a Research Agenda," SATToSE 2017,
https://ceur-ws.org/Vol-2070/paper-02.pdf (quotes and summarizes A. Van Deursen, L. Moonen, A. van
den Bergh, G. Kok — "Refactoring Test Code," XP2001, University of Cagliari, pp. 92–95, 2001,
itself unreachable this session — paywalled, no open mirror found);
Gabriele Bavota, Abdallah Qusef, Rocco Oliveto, Andrea De Lucia, David Binkley — "An Empirical
Analysis of the Distribution of Unit Test Smells and Their Impact on Software Maintenance," ICSM
2012, https://www.cs.loyola.edu/~binkley/papers/icsm-12-smells.pdf;
testsmells.org — "Software Unit Test Smells," https://testsmells.org/pages/testsmells.html;
testsmells.org — "Software Unit Test Smells — examples," https://testsmells.org/pages/testsmellexamples.html;
thoughtbot — "Mystery Guest," https://thoughtbot.com/blog/mystery-guest)

## 13. Coverage-criteria hierarchy

Coverage criteria form a subsumption hierarchy: criterion C1 subsumes C2 if and only if every test
suite satisfying C1 also satisfies C2 (Ammann & Offutt — *Introduction to Software Testing*, 2nd
edition, Chapter 8, "Logic Coverage" course slides). A stronger criterion is not vaguely "more
testing" — its guarantee includes the weaker criterion's obligations for free. That is what makes
the hierarchy useful for an oversight judgment: naming where a suite's structural coverage actually
sits says precisely what class of defect it has *not* been shown to catch, not merely how much code
ran.

**Statement coverage**, the floor, requires only that every executable line run at least once
somewhere in the suite. It says nothing about a decision's outcome: an `if` with no `else` can
reach 100% statement coverage while the condition is only ever true, and a compound condition
inside it can hold any clause distribution that happens to make the whole thing true. This is also
where the primer's §2 caution bites hardest: a "covered" line is an *executed* line, not a
*checked* one — a test that runs the line and asserts nothing about its result still counts as full
coverage on it.

**Branch (decision) coverage** requires each decision to take both outcomes — equivalent, on a
control-flow graph, to edge coverage, and to Ammann & Offutt's "Predicate Coverage," which they
note is "equivalent to edge coverage" when predicates sit on graph edges. Reaching both outcomes of
every decision necessarily executes every statement reachable from at least one of them, so branch
coverage subsumes statement coverage. It still treats each decision as an opaque true/false value:
`(A or B)` observed both true and false says nothing about whether A specifically, or B
specifically, was ever the deciding clause.

**Condition coverage** ("Clause Coverage") opens the decision up: each atomic clause must
independently evaluate both true and false. It looks like a fix for branch coverage's blind spot,
but Ammann & Offutt's own worked example shows it is not: the first clause-coverage test for
`((5 < 10) ∨ true) ∧ (1 >= 1*1)` sets every clause true, yet, as their slides put it, "only the
last clause counts" — the other two are satisfied without ever determining the result. Condition
coverage does not even guarantee branch coverage: for `a ∨ b`, the pair (T,F)/(F,T) covers both
truth values of both clauses while never once driving the whole predicate false.

**Condition/decision coverage** patches that specific hole by requiring decision coverage and
condition coverage together, a minimum of two test cases per decision. But union is not synthesis:
for `A or B`, the tests (TT) and (FF) satisfy condition/decision coverage without distinguishing
that expression from `A` alone, from `B` alone, or from `A and B` — an operator-substitution fault
survives untouched (NASA/TM-2001-210876, Hayhurst, Veerhusen, Chilenski & Rierson, "A Practical
Tutorial on Modified Condition/Decision Coverage," May 2001, §2.3.4).

**MC/DC** closes that gap with an independence requirement layered on condition/decision coverage:
every entry/exit point is invoked, every condition and decision takes both outcomes, and — the
distinguishing clause — "each condition in a decision has been shown to independently affect that
decision's outcome[, by] varying just that condition while holding fixed all other possible
conditions" (NASA/TM-2001-210876, §2.6, quoting the DO-178B definition). This needs a minimum of
n+1 test cases for n conditions, against the 2^n needed for full combinatorial coverage — the same
tutorial cites real avionics Boolean expressions running past 36 conditions in a single decision,
where 2^n testing is not expensive but physically impossible, which is exactly the case MC/DC was
built to make tractable (NASA/TM-2001-210876, §2.5). MC/DC is mandated by DO-178C, Table A-7, for
Software Level A — code whose failure could contribute to a catastrophic aircraft-level failure
condition. DO-178C's own text is an RTCA-controlled standard this primer could not fetch directly,
so that claim rests on the freely available NASA tutorial's identical DO-178B-era definition plus
converging industry sources describing DO-178C's Level A table as unchanged on this point (LDRA —
"Modified Condition/Decision Coverage," https://ldra.com/capabilities/mc-dc/; Wikipedia —
"Modified condition/decision coverage"; quality.arc42.org — "DO-178C" standards reference page,
https://quality.arc42.org/standards/do-178c).

**Multiple-condition (combinatorial) coverage** sits above MC/DC within one decision: every
combination of clause truth values, 2^n tests — exhaustive, and explicitly "impractical for
predicates with more than 3 or 4 clauses" even outside avionics-scale expressions (Ammann &
Offutt, Ch. 8 slides).

**Path coverage**, the top of the hierarchy across the whole control-flow graph rather than one
decision, requires every distinct route through the program — including every distinct
loop-iteration count — to execute at least once; an unbounded loop makes this not expensive but
infinite. No source treats it as achievable at scale; it functions as the theoretical ceiling the
other criteria are measured against, not a criterion a real suite satisfies in full.

The throughline for an oversight judgment: none of these criteria, MC/DC included, says anything
about whether the test that achieved them asserted the right thing. Coverage strength answers "was
this structure exercised, and how thoroughly"; it never answers "would a wrong result have been
caught" — that is §2's question, and the two axes are orthogonal. A suite reporting high statement
or branch coverage with weak or absent assertions — the common case in, say, a system that prices
work from an AI-interpreted scope, where a line computing a markup multiplier is "covered" by a
test that only checks the estimate object didn't throw — is not evidence of correctness anywhere in
this hierarchy; only a mutation score or an equivalent assertion-strength check is.

(Ammann & Offutt — *Introduction to Software Testing*, 2nd edition, Chapter 8, "Logic Coverage"
course slides — read via Owolabi Legunsen's Cornell CS 5154 deck, which states on its title slide
that it is a modified version of the authors' own publicly available Chapter 8 slides, so the
quotations below are the slides' wording rather than the book's text,
https://www.cs.cornell.edu/courses/cs5154/2021sp/resources/LogicCoverage.pdf;
Hayhurst, Veerhusen, Chilenski & Rierson — "A Practical Tutorial on Modified Condition/Decision
Coverage," NASA/TM-2001-210876, May 2001,
https://shemesh.larc.nasa.gov/fm/papers/Hayhurst-2001-tm210876-MCDC.pdf;
LDRA — "Modified Condition/Decision Coverage (MC/DC)," https://ldra.com/capabilities/mc-dc/;
Wikipedia — "Modified condition/decision coverage," https://en.wikipedia.org/wiki/Modified_condition/decision_coverage;
quality.arc42.org — "DO-178C" standards reference page, https://quality.arc42.org/standards/do-178c)

## 14. Contract testing

A contract, in this discipline's specific sense, is a machine-checkable record of the messages one
component sends or expects to receive from another at an integration boundary — for an HTTP API,
the request shapes a consumer actually issues and the response shapes it actually depends on; for a
queue-based system, the message schemas exchanged. Pact's documentation frames the technique as
"testing an integration point by checking each application in isolation to ensure the messages it
sends or receives conform to a shared understanding that is documented in a 'contract'" (Pact
documentation, https://docs.pact.io/). Each side is tested *alone*, against the contract, never by
spinning up both services together and driving a real call between them — that isolation is what
keeps a contract test fast and stable in a way a full integration test structurally cannot be.

Pact's vocabulary splits the two sides as **consumer** (the application that needs data — a
client, or a downstream service calling an API) and **provider** (the application that supplies
it), chosen deliberately generically because "client/server" doesn't map cleanly onto asynchronous
or queue-based integrations (Pact documentation, https://docs.pact.io/). The discipline is
consumer-*driven* by design, tracing to Ian Robinson's original Consumer-Driven Contracts pattern:
rather than a provider unilaterally publishing a contract that every consumer must adapt to, each
consumer expresses only the subset of the provider's behavior it actually depends on, and the
provider's obligation is to keep those consumer-authored expectations passing — not to preserve
every theoretically possible interaction it exposes (Martin Fowler / Ian Robinson, "Consumer-Driven
Contracts," https://martinfowler.com/articles/consumerDrivenContracts.html). This inverts the usual
coupling: a provider is free to change anything no real consumer depends on, and a change is unsafe
only when some consumer's stated expectation would actually break.

Mechanically, Pact generates the contract from running the consumer's own tests against a mock of
the provider — the resulting pact file is not hand-written or maintained as prose spec, it is a
generated artifact of concrete request/response pairs actually exercised, "contract by example"
rather than a spec authored ahead of implementation (Pact documentation, https://docs.pact.io/).
That file is published to a **Pact Broker**, a shared service that stores every pact keyed by
consumer name, provider name, and consumer application version. Provider-side CI pulls the
relevant pacts and replays each recorded interaction against the real provider, publishing
pass/fail verification results back to the broker keyed to the pact's content. The broker
assembles every published pact against every recorded verification into a compatibility matrix,
and the **can-i-deploy** check queries that matrix before a release to confirm the version about
to ship is verified-compatible with whatever consumer or provider versions are already live in the
target environment (Pact documentation — Pact Broker overview, https://docs.pact.io/pact_broker/overview).
This is what lets two services deploy independently and asynchronously while still carrying a real,
machine-checked compatibility guarantee before either one ships; Pact's own framing of the
alternative — standing both systems up together for an end-to-end check — is that you don't set
the house on fire to test the smoke alarm, you use the test button (Pact documentation,
https://docs.pact.io/).

What this proves that neither neighboring tier proves alone: a unit test against a hand-written
stub only proves the consumer's own code behaves correctly against what the *author believed* the
provider does — it says nothing about whether that belief is still true. A full integration or E2E
test proves the two systems work together *in that one environment, at that one moment*, at the
cost of standing up both, and re-verifies the whole call chain on every run rather than isolating
which side actually broke. A contract test sits in the gap: cheap and fast like a unit test, each
side run alone with no shared environment, but backed by a continuously re-verified,
machine-checked guarantee that both sides still agree — a guarantee only a genuine cross-service
check can supply.

Martin Fowler's own bliki entry on this is worth separating from Pact's consumer-driven mechanism,
rather than treated as the same claim: his **Contract Test** (reachable also at the entry's earlier
name, **IntegrationContractTest**) is a narrower, older idea — a suite that checks a test double
against an external service's *actual* behavior, run on the external service's own change cadence
rather than the codebase's deploy pipeline, so that testing against a double stops being a standing
leap of faith (Martin Fowler, "ContractTest," https://martinfowler.com/bliki/ContractTest.html; the
same content is also reachable at the older "IntegrationContractTest" URL,
https://martinfowler.com/bliki/IntegrationContractTest.html). Pact-style consumer-driven contract
testing is best read as this same underlying concern, operationalized: it automates the
periodic-verification half Fowler describes, and adds the consumer-driven authorship plus
broker-mediated compatibility check that his bliki entry does not itself specify a mechanism for.

The tool-selection rule follows from the mechanism. Reach for a contract test at a boundary between
independently deployable services or teams, where the real risk is *drift* — one side changing a
request or response shape without the other side finding out until a real call fails. Reach for a
full integration test when the thing under test is the behavior of the integration *itself* under
realistic conditions — real data volumes, real latency, real failure injection — not merely whether
the message shapes still match; contract tests deliberately do not exercise that. A single system's
internal function call needs neither. A system that prices work from an AI-interpreted scope and
calls out to an external pricing or catalog service, for instance, is a textbook case for a contract
at that boundary: the two sides change on independent schedules, and a shape mismatch there is
exactly what a contract test is built to catch before either side ships. The failure mode contract
testing exists to catch is **contract drift**: a provider ships a change — a renamed field, a
narrowed enum, a newly required parameter — invisible to every consumer's stubs and unit tests,
because those stubs still reflect the old shape; with no broker-verified contract in the loop, the
first signal is a runtime failure in production, discovered by an end user rather than by CI.
can-i-deploy is the direct structural answer: it refuses to let a version ship that has not been
verified against every consumer or provider version it will actually meet in the target
environment.

(Pact documentation, https://docs.pact.io/;
Pact documentation — Pact Broker overview, https://docs.pact.io/pact_broker/overview;
Martin Fowler / Ian Robinson — "Consumer-Driven Contracts," https://martinfowler.com/articles/consumerDrivenContracts.html;
Martin Fowler — "ContractTest," https://martinfowler.com/bliki/ContractTest.html;
Martin Fowler — "IntegrationContractTest" (same content, earlier URL), https://martinfowler.com/bliki/IntegrationContractTest.html)

## 15. Testing nondeterministic and LLM-backed systems

A unit test asserts one deterministic expected value for one deterministic input; that framing
breaks the moment the component under test is a language model, because the same prompt to the
same model can legitimately produce two different, both-correct outputs. Anthropic's own
evaluation vocabulary replaces "test" with four narrower concepts built for this: a *task*
(defined inputs and success criteria), a *trial* (one attempt at the task), a *grader* (the
scoring logic), and a *transcript* (the full record of one trial). Because "model outputs vary
between runs," a single trial is not evidence; an eval runs a task across many trials and reports
a rate rather than a pass/fail, expressed as pass@k (at least one success in k attempts) or pass^k
(all k attempts succeed) depending on which failure mode actually matters — a unit test's unit of
truth is one assertion, an eval's is a sample large enough to say something about a distribution.
Anthropic's own statistics research goes further, warning that a bare eval score is a point
estimate with sampling noise from two sources (which questions were included, and the model's own
stochastic behavior), so a score moving a few points between two runs is not on its own evidence
of a regression; detecting a real one needs a confidence interval, paired-difference testing
across the same question set, and a power analysis confirming the eval has enough questions to
detect a difference of the size that matters (Anthropic — "Demystifying evals for AI agents,"
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents; Anthropic — "A statistical
approach to model evaluations," https://www.anthropic.com/research/statistical-approach-to-model-evals).

Grading open-ended output at scale usually means using a second LLM as the grader — a
"model-based grader" in OpenAI's terminology, alongside code-based/deterministic graders and human
graders, since rubric-shaped output resists string-matching (OpenAI — API documentation, "Getting
started with evals," https://developers.openai.com/api/docs/guides/evaluation-getting-started).
The primary empirical study of this technique, Zheng et al., "Judging LLM-as-a-Judge with MT-Bench
and Chatbot Arena" (NeurIPS 2023), found a strong judge model reaching over 80% agreement with
human preference — the same level measured between two independent humans — which is the paper's
case for treating LLM-as-judge as a usable proxy at all. The same paper names the failure modes
that come with it: **position bias** (the judge favors whichever answer it sees first or second,
independent of quality — checked by running the comparison in both orders and crediting only a
preference that survives the swap, not eliminated by prompting alone), **verbosity bias** (longer
answers are rewarded even when the extra length adds no information), and limited reasoning
ability on questions that need actual computation rather than a quality judgment (Zheng et al.,
arXiv:2306.05685, https://arxiv.org/abs/2306.05685). A third bias from the same paper,
**self-enhancement**, is confirmed and extended by two later papers that are frequently — and
wrongly — merged into a single citation. The self-*recognition* finding is Panickssery, Bowman and
Feng, "LLM Evaluators Recognize and Favor Their Own Generations" (arXiv:2404.13076, 2024,
https://arxiv.org/abs/2404.13076): LLMs such as GPT-4 and Llama 2 distinguish their own outputs
from other models' and from human text at non-trivial accuracy out of the box, and fine-tuning
reveals a linear correlation between that self-recognition capability and the strength of
self-preference bias, with controlled experiments arguing the relationship survives the obvious
confounders. The *perplexity* explanation is a different paper by different authors — Wataoka,
Takahashi and Ri, "Self-Preference Bias in LLM-as-a-Judge" (arXiv:2410.21819, 2024,
https://arxiv.org/abs/2410.21819): it introduces a quantitative metric for the bias, measures a
significant degree of it in GPT-4, and finds that LLMs score low-perplexity — i.e. more familiar —
text far above where human evaluators score it *regardless of whether that text was
self-generated*, which locates the mechanism in familiarity rather than in self-recognition as
such. Both were read directly from their arXiv abstract pages for this entry. Note that these are
competing explanations of the same effect, not two halves of one finding, and this primer does not
adjudicate between them — cite whichever mechanism a given argument actually rests on, and do not
attribute either paper's claim to the other. The operational rule holds under either: never use the
same model, or one with shared lineage, to both generate and grade the candidate output under test,
and treat self-preference as a structural risk in any loop where a model iterates against its own
judgment.

Pinning temperature to 0 and pinning a seed narrows variance but does not deliver byte-for-byte
reproducibility, and treating it as if it does is a documented false assumption. Floating-point
arithmetic is not associative — (a+b)+c and a+(b+c) round differently — and GPU kernels for
matrix multiplication and attention accumulate in an order that depends on the batch a request
happens to execute in; because inference servers batch concurrent requests for throughput, and
batch composition varies with real-time load, the same prompt at temperature 0 with the same seed
can still diverge mid-generation. One documented test found 80 distinct completions out of 1,000
identical temperature-0 requests, matching for roughly the first hundred tokens before diverging —
a property of the serving stack's batch-dependent kernels, not a bug a caller configures away by
pinning parameters (Thinking Machines Lab — "Defeating Nondeterminism in LLM Inference,"
https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/). The consequence for
test design: pinning is still worth doing, since it narrows the variance an eval has to average
over, but a suite asserting exact-string equality against a pinned-temperature LLM call is still
asserting against a moving target, and an observed "regression" from one non-repeating run is
exactly the noise the statistical-evals framing above exists to filter out.

An eval or golden set is only as good as its resemblance to what the system sees in production,
and that resemblance decays silently — a set assembled against one month's traffic describes that
month, not the product six months later. This concern has no primary academic or vendor-neutral
standard behind it; the available guidance is a convergent set of eval-tooling vendor write-ups
rather than a peer-reviewed methodology, and should be weighted accordingly. The convergent
practical advice: append to the golden set rather than silently replace it, tag each case with when
and from what production slice it was added so a stale case is identifiable, and periodically
resample real production traffic to catch failure modes the static set was never built to see (no
single primary standard; this practice list is aggregated from search-engine snippets across
several vendor blogs — Langfuse, Braintrust, FutureAGI, and others — none independently fetched and
read as a full page this session).

The one structural move every source above agrees on, even without agreeing on thresholds: draw a
hard boundary between the code that wraps the model call and the model call itself, and test each
side with the tool suited to it. Input validation, prompt assembly, output parsing, schema
enforcement, retries, business-rule application, and persistence — for example, everything around
a system that prices work from an AI-interpreted scope except the interpretation step itself — are
ordinary deterministic code and belong in the ordinary unit/integration pyramid (§1), mocking the
model call so those tests stay fast and reliable. Only the model call, and anything that judges its
output, needs eval-set/statistical treatment. Collapsing the two — asserting exact output equality
across an LLM call, or exempting the deterministic wrapper code from ordinary testing discipline
because "the LLM makes it all nondeterministic anyway" — is the most common failure mode on both
sides. Stated plainly, because it is the load-bearing honesty this section owes: unlike coverage
thresholds or flaky-test quarantine windows, the field has **not** converged on a standard
eval-set size, an acceptable judge-agreement floor, or a standard drift-detection cadence — nor
even on a stable toolchain; OpenAI's own Evals platform, one of the sources this section draws on,
is scheduled for deprecation (read-only from October 31, 2026, shut down November 30, 2026) less
than three years after its 2023 introduction. Treat every figure in this section as a floor for
judgment, not a pass/fail gate to enforce mechanically.

(Anthropic — "Demystifying evals for AI agents," https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents;
Anthropic — "A statistical approach to model evaluations," https://www.anthropic.com/research/statistical-approach-to-model-evals;
Zheng et al. — "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," arXiv:2306.05685, https://arxiv.org/abs/2306.05685;
Panickssery, Bowman, Feng — "LLM Evaluators Recognize and Favor Their Own Generations," arXiv:2404.13076, 2024, https://arxiv.org/abs/2404.13076;
Wataoka, Takahashi, Ri — "Self-Preference Bias in LLM-as-a-Judge," arXiv:2410.21819, 2024, https://arxiv.org/abs/2410.21819;
OpenAI — API documentation, "Getting started with evals," https://developers.openai.com/api/docs/guides/evaluation-getting-started;
Thinking Machines Lab — "Defeating Nondeterminism in LLM Inference," https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)

## 16. Test-impact analysis and CI economics

Test-impact analysis (TIA) is the general term for running only the subset of a suite that a given
code change could plausibly break, rather than the full corpus, on every commit. The mechanism, as
documented for Microsoft's own Azure Pipelines TIA feature, is a dependency map recorded per test:
for each test method, the set of source files it actually exercised the last time it ran, captured
by instrumenting execution rather than by static analysis of imports alone. A new commit's changed
files are looked up against that map, and only the tests whose recorded dependency set intersects
the change are selected to run. Two details in Microsoft's own documentation matter more than the
headline speed-up: TIA explicitly falls back to running the full suite whenever it hits a change it
"can't reason about" — an unfamiliar file type, a multi-machine topology, a change outside managed
code — rather than silently narrowing the run; and the tool ships a configured-periodicity override
that forces a full run on a schedule regardless of what day-to-day selection concluded. Both are
load-bearing: a dependency map is only as good as its last capture, and running TIA with no
periodic full-suite backstop means trusting an increasingly stale graph indefinitely (Microsoft
Learn — "Use Test Impact Analysis - Azure Pipelines,"
https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis?view=azure-devops).

The literature is precise about three related but distinct techniques that get casually conflated
as "cutting down the suite." Test suite **minimization** permanently removes redundant or obsolete
test cases from the corpus — a one-way reduction in what could ever run again. Test case
**selection** chooses, per change, the subset of the existing corpus relevant to that change,
without deleting anything from the corpus itself — an excluded test remains available and can be
selected on a later commit. Test case **prioritization** discards nothing at all; it only reorders
execution so that tests more likely to reveal a fault run earlier, trading nothing but sequencing
for faster fault detection within a run that still executes everything eventually (S. Yoo and M.
Harman — "Regression Testing Minimisation, Selection and Prioritisation: A Survey," *Software
Testing, Verification and Reliability* 22(2), pp. 67–120, 2012, doi:10.1002/stv.430; first
published online 2010 — the year is verified against the dblp record, because the widely
circulated author-copy PDF carries no journal year of its own and this survey is often mis-cited
as 2007, a year in which no STVR publication of it exists). TIA, and the "run only the affected
tests" pattern generally, is a selection technique in this taxonomy, not minimization — the
distinction matters for an oversight agent because deleting a slow or flaky test (§5's named
alternative to be avoided) is minimization-shaped and destroys coverage permanently, while a
well-built selection system keeps the full corpus intact and only varies which slice of it runs on
a given commit.

Safety is a formally defined property in this literature, not a marketing word. Rothermel and
Harrold's foundational regression-test-selection technique — its own 1997 paper unreachable this
session (the PDF failed to parse), so read here via Graves, Harrold, Kim, Porter, and Rothermel,
"An Empirical Study of Regression Test Selection Techniques" (*ACM Transactions on Software
Engineering and Methodology* 10(2), pp. 184–208, April 2001, doi:10.1145/367008.367020), which
reviews and empirically evaluates the same technique
with two of its original authors, Harrold and Rothermel, as co-authors — defines a selection
algorithm as **safe** when, under an explicit set of conditions, the selected subset is guaranteed
to contain every test in the original suite capable of revealing a fault in the modified program:
built from control-flow-graph representations of the program before and after the change, plus
recorded execution profiles, so that any test whose profile touches a deleted, new, or modified
statement is retained. Most regression test-selection techniques in practical use —
minimization-based and dataflow-based alike — are explicitly not designed to meet this bar; an
unsafe technique can, and does, fail to select a test case that would have caught a real
regression. Evidence that safety and aggressive reduction are not in tension when the dependency
graph is precise comes from Rothermel and Harrold's own earlier results on their DejaVu tool —
reported in Graves et al.'s related-work survey rather than produced by that paper's own
experiments, a distinction worth preserving because the figures are widely requoted as if they
were Graves et al.'s findings: DejaVu "was able to discard an average of 45% of the test cases"
on 100–500 line programs while remaining safe, "while for a larger software system (50,000 lines)
it was able to discard an average of 95%" — the reduction gets *more* valuable, not less safe, as
the codebase grows, provided the graph stays accurate.

What breaks down at real CI scale is not the theory but the graph's precision and the cost of
sustaining it — dynamic dispatch, reflection, feature flags, and config-driven behavior all make a
fully accurate dependency map expensive or impossible to maintain, so most large-scale deployments
trade the formal safety guarantee for a measured, bounded risk instead. A large empirical study
spanning 285 million test results from Google Chrome, an internal Google project, and the JMRI
open-source project found that test selection can cut median feedback time by up to 96% using the
same machine count, but the same techniques can miss up to 55% of failures — a direct, measured
answer to "can TIA miss a real regression": yes, substantially, when the selection technique is
aggressive and not built to Rothermel-Harrold's safety conditions (Fallahzadeh, Rigby, and Adams —
"Contrasting Test Selection, Prioritization, and Batch Testing at Scale," *Empirical Software
Engineering* 30(1), article 33, 2025, doi:10.1007/s10664-024-10589-8 — accepted November 2024 and
cited here as a 2024 preprint until the journal record was checked; preprint at
https://mcislab.github.io/publications/2025/emse_scale.pdf).
Meta's predictive test selection is the deliberate, engineered version of that same tradeoff: rather
than claiming formal safety, it trains a model to rank each test's failure probability against a
proposed change, calibrated in production to run about a third of the tests a naive dependency
closure would have run, while still predicting outcomes correctly on over 95% of tests and catching
at least one failing test in over 99.9% of problematic changes — an explicit, measured risk floor
substituted for a proof, not the proof itself (Meta Engineering — "Predictive test selection to
ensure reliable code changes," https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/).

For a suite in the thousands of test files — an order of magnitude around 8,000-plus is a realistic
scale where retest-all genuinely stops fitting inside any usable CI budget — the practical posture
is layered rather than a single on/off choice: a fast per-commit pass runs a selected or
prioritized subset for quick feedback, and a slower, unconditional full run (nightly, or
Microsoft's "configured periodicity" override) acts as the backstop that catches whatever the day's
selection heuristic missed. This is what keeps a very large suite inside a runtime budget (§5)
without deleting coverage the way minimization or a slow-test cull would: the corpus stays whole,
only the per-commit slice varies. Auditing this system means checking the same things the sources
above flag: is the dependency map's last capture recent enough to trust; does the system fall back
to a full run, rather than silently narrowing, when it can't classify a change; is there in fact a
periodic full-suite run and not merely a selected subset running forever; and — applying §6's
falsifiability discipline directly — has the selection technique's actual miss rate ever been
measured against reality (for example, by diffing a periodic full run's failures against what the
day's selected subset would have caught) rather than assumed safe because nothing has visibly
escaped yet. A selection system whose safety has never been falsified sits in exactly the same
epistemic position as an unverified fix: green by construction, not by evidence.

(Microsoft Learn — "Use Test Impact Analysis - Azure Pipelines,"
https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis?view=azure-devops;
S. Yoo and M. Harman — "Regression Testing Minimisation, Selection and Prioritisation: A Survey,"
STVR 22(2), pp. 67–120, 2012, doi:10.1002/stv.430,
https://www.cse.chalmers.se/~feldt/advice/yoo_2010_regression_testing_survey.pdf;
Graves, Harrold, Kim, Porter, and Rothermel — "An Empirical Study of Regression Test Selection
Techniques," https://www.cs.umd.edu/users/aporter/Docs/p184-graves.pdf;
Fallahzadeh, Rigby, and Adams — "Contrasting Test Selection, Prioritization, and Batch Testing at
Scale," https://mcislab.github.io/publications/2025/emse_scale.pdf;
Meta Engineering — "Predictive test selection to ensure reliable code changes,"
https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/)

## 17. Falsifying an agent-definition change, not just its product's LLM calls

§15 is about evaluating an LLM call *inside a product* — a system that prices work from an
AI-interpreted scope, a classifier, a chatbot. This section is a narrower, structurally different
case: falsifying an edit to one of the runtime's own agent system prompts (`~/.claude/agents/*.md`
— the `high`-risk-tier class `review_risk_tier.py` actually gates on full review every time; a
primer or repo-local dossier edit is `trivial`-tier prose and is not this section's concern). The
ordinary falsifiability discipline (§6: revert the change, confirm the test goes red, reapply,
confirm green) has no direct target here — there is no test suite that exercises a prompt the way a
suite exercises a function. The artifact IS the behavior specification, and the only way to observe
whether it changed is to dispatch it.

**Why prose review cannot catch this on its own.** A code diff and a prompt diff both invite the
same reviewer error: reading the text and judging whether it *reads* correct, rather than
confirming it *behaves* differently. For ordinary code this is caught by "did a test go red without
the fix" (§6). For a prompt, the equivalent question is "did the OLD prompt actually mishandle the
case the edit claims to fix, and does the NEW one not." Nothing enumerates this automatically —
there is no ledger, no scan, no mutation battery for a system prompt — so it depends entirely on
whether the reviewer of that specific change performs the check. That is a real, load-bearing gap:
an editorially convincing prompt rewrite ships exactly as easily as a wrong one, because the
commit-gate review (`code-reviewer`, `~/.claude/agents/code-reviewer.md`, "Verify, don't assume")
can otherwise only assess prose quality, not behavior delta — and `code-reviewer` itself holds no
dispatch tool, so it cannot even run the probe unassisted (below).

**The mechanism, in outline** (the authoritative, enforced procedure lives in `code-reviewer.md`,
not here — this section is the doctrine): name the specific defect the edit claims to fix,
construct one small scenario that would plausibly expose it, then have the ORCHESTRATOR — never
`code-reviewer`, which holds `Read/Grep/Glob/Bash` only and, per `~/.claude/CLAUDE.md` §13's
confirmed-live nesting restriction, could not use a dispatch tool even if granted one — dispatch
the agent twice on that identical scenario, once under the pre-edit prompt and once under the
post-edit prompt, and hand both transcripts back for grading. `code-reviewer` treats a
required-but-missing pair of transcripts as a blocker, not an `UNVERIFIED` shrug: this is a known,
nameable dependency, not a genuinely unreachable fact. This is the single-fix, single-scenario
version of an eval (§15's vocabulary: one *task*, two *trials*, a pass/fail *grader* rather than a
rate) — deliberately not a full eval suite, because a standing eval battery re-run on every prompt
edit would be exactly the kind of gold-plated, high-standing-cost mechanism this runtime's design
philosophy argues against. It should stay cheap and targeted, not become a parallel CI system for
prompts.

**What this section does NOT claim.** It is not a mutation-testing battery for prompts, not a
standing regression suite, not a reason to build new tooling, and not a claim that
`~/.claude/.review_state/last_reviewed` records whether the probe ran — its schema is closed
(`ts`/`tier`/`tier_declared`/`reviewer`/`model`/`round`/`paths`/`paths_n`/`prev`/`vf`/`rekey`, `vf` already reserved for
`verify_fix.py`'s own code-falsifiability verdict token set) and adding a field for this would be
its own small piece of scope-creep this section declines to propose. The probe's outcome lives in
`code-reviewer`'s own findings report for that boundary — read by whoever files the resulting issue,
same as any other finding — not in a machine-greppable ledger row.

**This agent's role is doctrine, not enforcement or audit.** Test-architect does not run this probe,
does not gate the commit, and does not attempt to verify from the ledger that a given historical
`agents/*.md` commit was probed — the ledger cannot answer that question (above), and treating its
silence as a finding would produce a false positive against every prior entry. What belongs here is
the standing reference for why the check exists and what it can and cannot prove, so a future
monthly audit that DOES have a real signal (a `code-reviewer` report on hand, a filed issue
referencing a skipped probe) knows how to read it — not a manufactured audit against a signal that
was never recorded.

**Volume note, stated honestly rather than assumed.** An earlier draft of this section asserted
agent-definition edits are rare enough that a per-edit probe costs little; measured against the live
review ledger (2026-09-06), `agents/*.md` review entries ran roughly 7/day across August–September
— not rare. The design bias toward a cheap, targeted, one-scenario probe over a standing eval suite
still holds on its own terms (a heavier mechanism run 7×/day is a worse trade, not a better-justified
one), but the case for it is "this specific check is cheap," not "this class of edit is infrequent."

(No external source — this section is runtime-specific doctrine authored 2026-09-06, not a synthesis
of published literature the way §§1–16 are.)

## Sources

- Ham Vocke — "The Practical Test Pyramid" (published on martinfowler.com) — https://martinfowler.com/articles/practical-test-pyramid.html
- Martin Fowler — "TestPyramid" — https://martinfowler.com/bliki/TestPyramid.html
- Wikipedia — "Characterization test" — https://en.wikipedia.org/wiki/Characterization_test
- nexocode — "Mutation testing" — https://nexocode.com/blog/posts/mutation-testing/
- getautonoma — "Mutation testing vs. code coverage" — https://getautonoma.com/blog/mutation-testing-vs-code-coverage/
- PITest issue tracker (mutation baseline must be green) — https://github.com/hcoles/pitest/issues/1272
- Google Testing Blog — "Flaky Tests at Google and How We Mitigate Them" — https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html
- Mergify — "Test quarantine" — https://mergify.com/learn/test-quarantine
- Shopify Engineering — "Test budget: a time-constrained approach to CI feedback" — https://shopify.engineering/test-budget-time-constrained-ci-feedback
- thoughtbot — "Introducing test budget" — https://thoughtbot.com/blog/introducing-test-budget
- sematext — "Three pillars of observability" — https://sematext.com/glossary/three-pillars-of-observability/
- dash0 — "Structured logging for modern applications" — https://www.dash0.com/guides/structured-logging-for-modern-applications
- Broadlume Product — "Sentry: three best practices for error management" — https://medium.com/broadlume-product/sentry-three-best-practices-for-error-management-afc07bade57
- makandra — "Controlling issue grouping (Sentry)" — https://makandracards.com/makandra/484983-controlling-issue-grouping-sentry
- getautonoma — "QA metrics dashboard" — https://getautonoma.com/blog/qa-metrics-dashboard
- Better Stack — "Logging best practices" — https://betterstack.com/community/guides/logging/logging-best-practices/
- Tsong Yueh Chen, Fei-Ching Kuo, Huai Liu, Pak-Lok Poon, Dave Towey, T. H. Tse, Zhi Quan Zhou — "Metamorphic Testing: A Review of Challenges and Opportunities" (ACM Computing Surveys 51(1), 2018) — https://www.cs.hku.hk/data/techreps/document/TR-2017-04.pdf
- Sergio Segura, Gordon Fraser, Ana B. Sanchez, Antonio Ruiz-Cortés — "A Survey on Metamorphic Testing" (IEEE TSE 42(9), 2016) — https://eprints.whiterose.ac.uk/id/eprint/110335/1/segura16-tse.pdf
- Upulee Kanewala, James M. Bieman — "Using Machine Learning Techniques to Detect Metamorphic Relations for Programs without Test Oracles" (IEEE ISSRE 2013 preprint) — https://www.cs.colostate.edu/~bieman/Pubs/KanewalaBiemanISSRE2013preprint.pdf
- Sergio Segura, Amador Durán, Javier Troya, Antonio Ruiz-Cortés — "Metamorphic Relation Patterns for Query-Based Systems" — https://personal.us.es/sergiosegura/files/papers/segura19-met.pdf
- Wikipedia — "Metamorphic testing" — https://en.wikipedia.org/wiki/Metamorphic_testing
- Koen Claessen, John Hughes — "QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs" (ICFP 2000) — https://www.cse.chalmers.se/~rjmh/QuickCheck/
- Wikipedia — "QuickCheck" — https://en.wikipedia.org/wiki/QuickCheck
- Hypothesis documentation — https://hypothesis.readthedocs.io/en/latest/
- Hypothesis tutorial — "Introduction" — https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html
- Scott Wlaschin — "Choosing properties for property-based testing" (F# for Fun and Profit) — https://fsharpforfunandprofit.com/posts/property-based-testing-2/
- Martin Fowler — "Mocks Aren't Stubs" — https://martinfowler.com/articles/mocksArentStubs.html
- Martin Fowler — "TestDouble" (bliki) — https://martinfowler.com/bliki/TestDouble.html
- Vladimir Khorikov (enterprisecraftsmanship.com) — "When to Mock" — https://enterprisecraftsmanship.com/posts/when-to-mock/
- Brent van Bladel, Serge Demeyer — "Test Refactoring: a Research Agenda" (SATToSE 2017) — https://ceur-ws.org/Vol-2070/paper-02.pdf
- Gabriele Bavota, Abdallah Qusef, Rocco Oliveto, Andrea De Lucia, David Binkley — "An Empirical Analysis of the Distribution of Unit Test Smells and Their Impact on Software Maintenance" (ICSM 2012) — https://www.cs.loyola.edu/~binkley/papers/icsm-12-smells.pdf
- testsmells.org — "Software Unit Test Smells" — https://testsmells.org/pages/testsmells.html
- testsmells.org — "Software Unit Test Smells — examples" — https://testsmells.org/pages/testsmellexamples.html
- thoughtbot — "Mystery Guest" — https://thoughtbot.com/blog/mystery-guest
- Hayhurst, Veerhusen, Chilenski, Rierson — "A Practical Tutorial on Modified Condition/Decision Coverage" (NASA/TM-2001-210876, 2001) — https://shemesh.larc.nasa.gov/fm/papers/Hayhurst-2001-tm210876-MCDC.pdf
- Ammann & Offutt — *Introduction to Software Testing*, 2nd ed., Ch. 8 "Logic Coverage" course slides (read via Owolabi Legunsen's Cornell CS 5154 deck, a stated modified version of the authors' own slides) — https://www.cs.cornell.edu/courses/cs5154/2021sp/resources/LogicCoverage.pdf
- LDRA — "Modified Condition/Decision Coverage (MC/DC)" — https://ldra.com/capabilities/mc-dc/
- Wikipedia — "Modified condition/decision coverage" — https://en.wikipedia.org/wiki/Modified_condition/decision_coverage
- quality.arc42.org — "DO-178C" standards reference page — https://quality.arc42.org/standards/do-178c
- Pact documentation — https://docs.pact.io/
- Pact documentation — "Pact Broker" overview — https://docs.pact.io/pact_broker/overview
- Martin Fowler / Ian Robinson — "Consumer-Driven Contracts" — https://martinfowler.com/articles/consumerDrivenContracts.html
- Martin Fowler — "ContractTest" (bliki) — https://martinfowler.com/bliki/ContractTest.html
- Martin Fowler — "IntegrationContractTest" (bliki, earlier URL for the same entry) — https://martinfowler.com/bliki/IntegrationContractTest.html
- Anthropic — "Demystifying evals for AI agents" — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic — "A statistical approach to model evaluations" — https://www.anthropic.com/research/statistical-approach-to-model-evals
- Zheng et al. — "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (arXiv:2306.05685) — https://arxiv.org/abs/2306.05685
- Panickssery, Bowman, Feng — "LLM Evaluators Recognize and Favor Their Own Generations" (arXiv:2404.13076, 2024) — https://arxiv.org/abs/2404.13076
- Wataoka, Takahashi, Ri — "Self-Preference Bias in LLM-as-a-Judge" (arXiv:2410.21819, 2024) — https://arxiv.org/abs/2410.21819
- OpenAI — API documentation, "Getting started with evals" — https://developers.openai.com/api/docs/guides/evaluation-getting-started
- Thinking Machines Lab — "Defeating Nondeterminism in LLM Inference" — https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- Microsoft Learn — "Use Test Impact Analysis - Azure Pipelines" — https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis?view=azure-devops
- S. Yoo, M. Harman — "Regression Testing Minimisation, Selection and Prioritisation: A Survey" (*Software Testing, Verification and Reliability* 22(2), pp. 67–120, 2012; doi:10.1002/stv.430; online 2010) — https://www.cse.chalmers.se/~feldt/advice/yoo_2010_regression_testing_survey.pdf
- Graves, Harrold, Kim, Porter, Rothermel — "An Empirical Study of Regression Test Selection Techniques" (*ACM TOSEM* 10(2), pp. 184–208, April 2001; doi:10.1145/367008.367020) — https://www.cs.umd.edu/users/aporter/Docs/p184-graves.pdf
- Fallahzadeh, Rigby, Adams — "Contrasting Test Selection, Prioritization, and Batch Testing at Scale" (*Empirical Software Engineering* 30(1), article 33, 2025; doi:10.1007/s10664-024-10589-8; accepted November 2024) — preprint at https://mcislab.github.io/publications/2025/emse_scale.pdf
- Meta Engineering — "Predictive test selection to ensure reliable code changes" — https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/

---

## How this agent applies it

- **Audits the architecture of the suite, never individual tests in isolation** — pyramid shape
  (§1), mutation coverage (§2), and flake/runtime health (§4/§5) are evaluated as a system; a
  single slow or flaky test is a symptom to route to the right structural bucket, not a standalone
  finding.
- **Every finding names its axis** — pyramid-shape, mutation-strength, characterization-vs-intent
  (§3), flakiness, runtime-budget, or observability — so a fix targets the right structural cause
  rather than a vague "tests are bad."
- **Lock-in tests are named explicitly, per §3** — a test that only pins current output rather than
  asserting intended behavior is reported as a characterization-test finding by name, not folded
  into a generic coverage complaint.
- **Dead or silent telemetry is its own finding class** — a log line, metric, or trace that exists
  in code but never actually fires, or a correlation ID that drops partway through a request path,
  is reported the same way a missing assertion is: found, not assumed present because the code
  looks like it should emit it.
- **The stranger-debuggable bar (§7) is applied per critical flow named in the repo dossier**, not
  as a blanket suite-wide grade — each flow gets its own pass/fail against "could someone with no
  local context diagnose a production incident in this flow from logs/traces alone."
- **Severity is scored by what a missed regression in that area would actually cost** — a gap in a
  revenue- or safety-critical path outranks an equally-sized gap in a low-traffic corner, mirroring
  how §8's audit metrics are meant to be read against real product risk, not treated as uniform.
- **Metamorphic relations are the technique for a component with no test oracle (§9)** — a step
  whose absolute correct output can't be stated in advance (an AI-interpreted scope's dollar
  total, a vision-measurement read) is judged by relational properties across paired executions
  instead — doubling an input must not lower the output, adding a fixture must not lower the
  total — not waved off as untestable because "there's no way to know the right answer."
- **Property-based tests supplement the example-based suite, never substitute wholesale for it
  (§10)** — pricing and quantity logic get checked against universally-quantified properties
  (invariants, round-trips, idempotence, monotonicity) generated and shrunk to a minimal
  counterexample by the tool, not hand-picked by the test's author.
- **A test's double type is read before its assertion is trusted (§11)** — a mock proves an
  interaction happened, a stub proves an output given a canned input, a fake proves behavior
  against realistic (if lightweight) collaborator logic; mocking the SUT itself, or mocking an
  internal collaborator past the true external boundary, is flagged as a defect in its own right,
  not credited as isolation.
- **Scanner-flagged test smells are routed to a named structural cause and refactor, per §12** —
  Assertion Roulette, Mystery Guest, Eager Test, and the rest are reported by name with the
  specific fix each implies, not collapsed into an undifferentiated "this test file needs
  cleanup."
- **A reported coverage percentage is read against where it sits in the §13 hierarchy** — a bare
  line- or branch-coverage number is a weak claim on its own, since it proves a line ran, not that
  a wrong result there would have been caught; only a claim backed by condition/decision- or
  MC/DC-level criteria, or paired with a mutation score (§2), is treated as a strong one.
- **Cross-service boundaries are checked for contract drift, not credited on integration coverage
  alone (§14)** — an independently-deployable boundary with no consumer-driven contract in the
  loop is flagged as a drift risk even when both sides pass their own unit and integration suites,
  since neither proves the two sides still agree on message shape.
- **LLM-backed components are held to eval discipline, and the boundary around them is checked,
  not just the model call itself (§15)** — the deterministic code wrapping a model call (parsing,
  validation, business rules) stays inside the ordinary pyramid; only the model call and anything
  judging its output is graded by trial rate and judge-bias checks, and a suite that blurs the two
  — exact-match assertions on an LLM call, or exempting wrapper code from ordinary discipline
  because "the LLM makes it all nondeterministic" — is flagged either way.
- **A shrinking CI runtime is checked for how it shrank, per §16** — test selection (a subset run
  per change, full corpus intact) is distinguished from minimization (permanent deletion) and
  prioritization (reordering only); a suite that got faster by deleting slow or flaky tests is
  flagged as a coverage loss, not credited as budget discipline (§5).
- **§17 is read as doctrine, never run as a ledger audit** — the review ledger has no field
  recording whether an `agents/*.md` commit's falsifiability probe actually happened, so this agent
  never treats a normal-looking `last_reviewed` entry as evidence either way. If a `code-reviewer`
  report or a filed issue on hand for a specific commit shows the probe was skipped or its
  transcripts weren't graded, that is reported as a real finding (the same class as an unfalsified
  code "fix," §6) — but it is never inferred from ledger silence alone.
