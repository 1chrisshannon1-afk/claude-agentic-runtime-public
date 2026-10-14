# GTM Wave-2 interface contracts — §7 Notices, runners, schedules

> Part of the split GTM Wave-2 contract set. Index, file list and precedence: [`../CONTRACTS.md`](../CONTRACTS.md).
> References into another contract file carry that file name (e.g. `03_schemas.md §3.4.4`). A bare `§N` is either
> a section of this file or, exactly as in the original single document, a section of the plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md`; always so for §10 and above, and wherever the text says "plan §…").
> Open review findings for this file: [`OPEN_FINDINGS.md`](OPEN_FINDINGS.md).

## 7. Notices, runners, schedules (WP-D ↔ WP-K; also A2, B2)

### 7.1 Notice record (`S/notices/<slug>/<notice_id>.json`)

```json
{"schema": "gtm.notice.v1", "notice_id": "ntc_other-company_20260927T150405Z_ab12cd", "company": "other-company",
 "kind": "hold", "severity": "info|warn|urgent", "created_at": "…", "title": "…", "body": "…",
 "action_id": "act_…", "request_id": null, "hold_until": "…", "status": "open|resolved",
 "resolved_at": null, "resolution": null, "resolved_by": null, "push": true, "dedupe_key": "hold:act_…",
 "created_by": "act", "system": null, "card_id": null, "origin_company": "other-company", "reason_code": null}
```
**Timestamps (r5; one form everywhere in this file).** `created_at`, `resolved_at` and `hold_until`
(and every `ts` this file writes: `pushed.jsonl`, `ST/inbox.jsonl`, `ST/runaway_stops.jsonl`, heartbeat
`started_at`/`finished_at`) are UTC `YYYY-MM-DDTHH:MM:SSZ` — exactly the form of the RUN CONTEXT
`start` (§7.5) — so `list`'s sort, `--since` and every comparison are plain string comparisons of one
fixed-width form; `write_notice` stamps `created_at` itself, and a reader that meets any other form
treats the record as malformed (skipped by `list`, counted in its stderr). D test: every timestamp a
fixture run writes matches `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$`.
`origin_company` = the GTM company whose context produced the notice: for a notice of a GTM company,
that company; for a `runtime` notice, the company the writer names (the CLI `--origin-company` flag
of the env-cleared shell writers, §7.2/§7.6; an in-process writer's own `company` argument), else
`null`. **Redaction keys on both:** every "pack has `regulated ∋ hipaa`" test of this file (the
`list` text redaction, the push rule, the page's *Notices* allowlist) is true when **either** the
`company` pack **or** the `origin_company` pack has `regulated ∋ hipaa`. `reason_code` = a refusal
code (`^[a-z0-9_]{1,40}$`, else stored `null`) set only on `isolation_hit` notices by act.py (E4,
below); the page and push render it only through `REFUSAL_REASON_TEXT` (below), never as free text.
`resolved_by` = who resolved it: the CLI records `cli:<CLAUDE_GTM_SESSION or "none">`; in-process
resolvers record their `NOTICE_CREATED_BY` name (e.g. `act`, `run-holds`). A reader treats a missing
key as null.
`system` = the tier system the notice is about (required, non-null, for `signin_missing`; null
otherwise). `card_id` = the operator-input card posted for this notice (set only by `notices.py
card-mark`, below; null until then) — the dedupe record for the two notice kinds that also get a
card (FID-10): `signin_missing` and `chain`.
`created_by` ∈ `NOTICE_CREATED_BY` = `act, run-holds, breaker, gate-gtm, G-A, notices, gtm_session,
run_gtm_job, approvals_verify, secret_sink, outside_actor, autonomy_ladder, perf_report, cycle,
session` (I16; the one enum — every writer named anywhere in this document is in it; `session` is
the one attribution of every notice a GTM session creates, only through `notices.py task`, below;
`notices.py write --created-by` refuses any value but `gtm_session`/`run_gtm_job`, exit 3, and the in-process `write_notice` raises
`NoticeError("bad_created_by")` for a non-member, writing nothing; there is **no** `hook` member:
every hook-side writer passes its own enum name — `G-A`, `gate-gtm`, `secret_sink`, … — with no
default, `requests/07_notices_schedules.md` R48 to 04_hooks.md's `write_notice_file`). `company` is a GTM slug or the reserved `runtime`
(runtime-wide notices: trust, unattributed spend; directory `S/notices/runtime/`; I12 — `runtime`
matches the slug grammar, so notice ids stay splittable on `_`, and `gtm_slugs()` never returns it).
`kind` ∈ `NOTICE_KINDS` = `hold, money_card, card, breaker, pause, signin_missing, agent_cancel, trust, budget, chain,
isolation_hit, runaway_spend, task, activity_log_failed, cancel_too_late, spool_dropped, info`
(seventeen; `cancel_too_late` is 03_schemas.md §3.11's late-cancel notice, `dedupe_key`
`cancel_late:<action_id>`, `created_by: act`; `spool_dropped` is 02_act.md §2.4's permanent pause-spool
failure, `dedupe_key` `spool_dropped:<file name>`, `created_by: act`). Holds are notices, never cards.
**Module constants (one owner, `notices.py`; everybody imports, nobody restates):**
`NOTICE_KINDS: tuple[str, ...]` (the kind enum, in the order above), `NOTICE_CREATED_BY:
tuple[str, ...]`, `NOTICE_KIND_LABEL: dict[str, str]` (below), `REFUSAL_REASON_TEXT: dict[str, str]`
(below) and `PAGE_TEXT_WRITERS: frozenset[str]` = {`notices`, `gtm_session`, `run_gtm_job`,
`approvals_verify`} (the page's writer allowlist, §7.1 "Page safety"). `approval_sig.write_urgent_notice`
(stdlib-only, cannot import `notices.py`) checks against its own literal copy of `NOTICE_KINDS`, and a
D test asserts the two tuples are equal.
`runaway_spend` is written by act.py for an urgent `$` request (02_act.md §2.6), by `act.py ingest-findings`
for every `runaway_spend` finding (02_act.md §2.4; dedupe key `runaway_spend:<agent_id>:<finding id>`)
and by `act.py read-run` for every `runaway_spend` finding of a `"findings": true` collector (§7.4;
dedupe key `runaway_spend:collector:<collector>:<finding id>`); `task` is an operator task
(e.g. the lease-held task, §7.6). Writers: act.py (via `notices.py`
API), hooks (direct file write per this schema, `gtm_hooklib.write_notice_file`), and the two
**sanctioned stdlib direct writers** of 05_approver.md, which run before the trust check lets
`notices.py` load: `approval_sig.write_trust_notice` (`kind: trust`, `created_by: approvals_verify`)
and the general `approval_sig.write_urgent_notice(S, slug, kind, title, body, dedupe_key, *,
created_by)` behind it (severity `urgent`, `push: true`; its callers are the step-0 fallback notices
of 02_act.md §2.3 — `created_by: act` — and the `lead_capture_stopped:<slug>:<UTC date>` `task`
notice of 05_approver.md §5.5 step 0, which it writes with `created_by: approvals_verify`, a fixed
template naming only the slug, so the page renders it; `requests/07_notices_schedules.md` R62). Both
write exactly this schema, id scheme and timestamp form, take the same two locks, and apply the same
`(company, dedupe_key, created_by)` dedupe (R44). Dedupe: a writer
skips creation when an `open` notice of the same company with the same `dedupe_key` **and the same
`created_by`** exists (so a notice planted under another writer's name can never absorb the real
one; §7.1 CLI rules; `requests/07_notices_schedules.md` R44 for the hook and trust-notice writers). **Locks (F-locks; both
writers use the same two):** the dedupe check and the create run inside one
`fcntl.flock(LOCK_EX)` on `S/notices/<slug>/.lock` (5 s timeout; a hook that times out skips the
notice and logs `gate-fault`, never blocks), so two concurrent writers cannot both create the same
`dedupe_key`; every append to `S/notices/pushed.jsonl` holds `S/notices/pushed.lock`. D test: two
processes writing the same `dedupe_key` concurrently produce one notice.

`notices.py` (WP-D) API and CLI:
```python
def write_notice(company, kind, severity, title, body, *, action_id=None, request_id=None, hold_until=None, push=False, dedupe_key=None, created_by="act", task=False, system=None, origin_company=None, reason_code=None) -> dict
    # push=True: immediately attempts the osascript push below (best effort, 5 s timeout)
    # and on success appends S/notices/pushed.jsonl (under S/notices/pushed.lock); push_pending() remains the retry path for failures.
    # task=True (kind "task"): also appends ST/inbox.jsonl {"ts","kind":"task","title","body","source":created_by,"status":"open","notice_id"}
    # when pack.inbox == "local_jsonl" (under ST/inbox.lock); other inbox kinds: the notice alone.
    # origin_company: for a non-runtime `company` it is forced to `company` (whatever was passed); for
    #   company == "runtime" it must be a gtm_slugs() member or None, else NoticeError("bad_company"), nothing written.
    # reason_code: accepted only with kind == "isolation_hit" (a non-None value with any other kind →
    #   NoticeError("bad_reason_code"), nothing written); a value failing ^[a-z0-9_]{1,40}$ is stored as null
    #   (the notice is still written — an isolation hit is never lost to a malformed code).
def resolve_notice(company, notice_id, resolution: str, *, resolved_by: str) -> None   # in-process API: any kind
    # resolving a `task` notice (by this function, resolve_by_dedupe_key or the CLI) of a local_jsonl pack also
    # appends {"ts", "kind": "task_status", "notice_id", "status": "resolved"} to ST/inbox.jsonl under
    # ST/inbox.lock, so the home's own task list never shows a resolved task as open
def resolve_by_dedupe_key(company, dedupe_key: str, resolution: str, *, created_by: str, resolved_by: str) -> list[str]
    # in-process: resolves every open notice of `company` whose dedupe_key equals the key AND whose created_by
    # equals `created_by` (the same (company, dedupe_key, created_by) rule as write dedupe and resolve-owned, so a
    # same-key notice planted under another writer's name is never closed by it); returns their ids
def list_notices(company=None, status="open", since=None) -> list[dict]   # sorted by created_at ascending; since: created_at >= since
def push_pending() -> tuple[int, int]   # (pushed, failed): the osascript push per unpushed push:true notice; records S/notices/pushed.jsonl {"notice_id","ts","channel":"osascript"|"failed"}
    # `pushed` = notices pushed on this call; `failed` = pushes attempted on this call that did not succeed
    # (including those recorded "failed" by the retry cap below)
    # retry cap: a notice whose created_at is more than 24 h old and still unpushed is recorded once with
    # channel "failed" and never retried again (so failed pushes cannot eat the holds job's 900 s deadline forever)
def prune(now=None) -> dict      # retention, holds job only (§7.2 step (3b)); returns {"deleted": n, "pushed_rows": n}
    # deletes every RESOLVED notice file whose resolved_at is more than 90 days old, and every pushed.jsonl row whose
    # notice file no longer exists (rewritten under pushed.lock); never touches an open notice
def push_text(notice: dict) -> tuple[str, str]   # (title, body) actually pushed — the ONE function osascript and E7 text come from (push rule below)
def render_operator_page(out: Path | None = None) -> Path   # default ~/Desktop/GTM_Operator.html (test seam below)
def card_draft(company, kind: str, out: Path) -> dict       # kind ∈ {"signin", "chain"}; the `card-draft` CLI below
def card_mark(company, card_id: str, notice_ids: list[str], *, replaces: str | None = None) -> None
class NoticeError(Exception):   # every in-process refusal raises NoticeError(code), code = the CLI's refusal code
    code: str                   # (e.g. "notice_not_open", "resolve_kind_not_cli", "card_not_posted", "bad_kind")
```
CLI: `notices.py render [--open] | push | prune | list [--company X] [--status open|resolved|all] [--since ISO] [--json] | resolve --company X --notice <id> --resolution "<text>" [--operator] |
write --company X --kind K --severity info|warn|urgent --title T --body B [--dedupe-key D] [--push] [--task] --created-by gtm_session|run_gtm_job [--origin-company S] |
task --company X --template lead_unanswered --lead-id <id> --received-at <UTC> | task --company X --template pending_commit --path <p> | task --company X --template restore_check --run <run_id> --exit-code <n> --error-code <code> | task --company X --template lead_capture_window |
resolve-owned --company X --dedupe-key D --resolution "<text>" --created-by gtm_session|run_gtm_job |
card-draft --company X --kind signin|chain --out <abs path under <home>/.claude/gtm/drafts/> | card-mark --company X --card-id <id> --notices <id,…> [--replaces <old card_id>]`

`origin_company` and `reason_code` are keyword parameters of `write_notice` itself (the one shared
in-process API; A2's act.py is a caller, WP-D the implementer), with the validation stated in the
signature comments; `gtm_hooklib.write_notice_file` and the two `approval_sig` writers apply the same
two rules (`requests/07_notices_schedules.md` R63). D tests (each falsified by removing its clause):
`write_notice("other-company", "hold", …, origin_company="othercompany")` stores `origin_company:
"other-company"`; `write_notice("runtime", "trust", …, origin_company="agency")` raises
`NoticeError("bad_company")` and writes nothing, and `origin_company=None` stores `null`;
`write_notice(…, kind="isolation_hit", reason_code="cross_company")` stores that code, `reason_code="Bad
Code!"` stores `null` and still writes the notice; `write_notice(…, kind="hold",
reason_code="cross_company")` raises `NoticeError("bad_reason_code")` and writes nothing.

**Output and state shapes.** `list --json` prints one JSON array of full notice records (§7.1
schema; missing keys as null) **plus one derived key on every record, `push_text: str`** = the two
parts of `push_text(notice)` joined as `<title> — <body>` (push rule below; present on every record,
whether or not the notice has `push: true`), sorted by `created_at` ascending; `--status` ∈ {`open`, `resolved`,
`all`}, default `open`; `--since ISO` keeps notices with `created_at >= since` (inclusive; a value
that does not match the `YYYY-MM-DDTHH:MM:SSZ` form above → exit 2 `usage`); without `--json` it prints one line per notice, `<created_at> <company>
<kind> <severity> <notice_id> <title>` (the title column follows the text-redaction rule below:
`-` wherever `title` is nulled). **Text redaction in `list` (every output form, CLI only):** a
record's `title` and `body` are replaced by `null` — and the line form's title column by `-` —
when the notice's company **or origin_company** pack has `regulated ∋ hipaa` **or** its `created_by` is not in
`PAGE_TEXT_WRITERS` (§7.1 "Page safety", *Notices*; `session` is deliberately not in it); every
other field is printed as stored, and `push_text` (already built by the push rule)
is always present. The record also carries two further derived keys: `label` =
`NOTICE_KIND_LABEL[kind]` (below), exactly that string and nothing appended, and `reason_text` =
`REFUSAL_REASON_TEXT[reason_code]` when `kind == "isolation_hit"` and `reason_code` is a key of that
dict, else `null` (every record carries both keys; the text line form prints neither). D test: an
`isolation_hit` notice with `reason_code: cross_company` lists `label: "Isolation hit"` and
`reason_text` = the fixed `cross_company` text; a `hold` notice lists `reason_text: null` (falsified
by joining the reason into `label`). So a session reads only allowlisted fields plus `push_text` — never an in-process
writer's title/body that may quote action, finding, recipient or customer text, and never a hipaa
pack's text (plan §20.4/§20.13; the §7.5 I8 "never Read a brief" rule). The in-process
`list_notices` returns full records; only `notices.py` itself and the page renderer call it.
`resolve` (and `resolve_notice`) of a notice that is already `resolved` refuses exit 3
`notice_not_open` and changes nothing (never an idempotent success, so a caller learns it acted on
stale state). There is no `--system` flag on the CLI: every CLI-writable kind has `system: null`
(§7.1 `system` rule), and `signin_missing` is written in-process only.

**No free text from a session (r5; supersedes the former `--title-file`/`--body-file` rule).** The
CLI `write` is for the env-cleared shell writers only (`gtm_session.sh`, `run_gtm_job.sh`, whose
titles and bodies are this file's fixed templates): it refuses exit 3 `write_in_session` whenever
`CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is set, and it has no `--title-file`/`--body-file`
flags (either → exit 2 `usage`, unknown flag). **`--company runtime` has no home**, so with it `--task`
exits 2 (`runtime_has_no_home`, nothing written). `--origin-company <slug>` is accepted only with
`--company runtime` (else exit 2 `usage`) and must be a `gtm_slugs()` member (else exit 3
`bad_company`); the shell writers of §7.2/§7.6 pass their own slug. **A GTM session creates notices
only through `notices.py task --template <name>`**, which takes **no text at all**: notices.py
composes the title, body, kind (`task`), severity, `dedupe_key`, `push: true`, `task: true` and
`created_by: session` itself from grammar-checked flag values, so no lead, review, DM, page or
finding text — and no injection-authored instruction — can reach a notice, the page or a push from a
session:

| template | flags (each grammar-checked; a failing value → exit 3 `bad_template_arg`, nothing written) | title (fixed) | body (fixed) | severity | `dedupe_key` |
|---|---|---|---|---|---|
| `lead_unanswered` | `--lead-id` (03_schemas.md §3.14 lead id grammar), `--received-at` (UTC form above) | `Lead unanswered: <lead_id>` | `Lead <lead_id> received <received_at> is unanswered past its response target; open the lead sink.` | `warn` | `lead_unanswered:<lead_id>` |
| `pending_commit` | `--path` (`^[A-Za-z0-9._/-]{1,200}$`, no `..` segment) | `Tracked change uncommitted >14 days: <path>` | `commit it from an interactive GTM session through gate 3b` | `warn` | `pending_commit:<path>` |
| `restore_check` | `--run` (`CYCLE_ID_RE`, slug = `--company`), `--exit-code` (integer 0–255), `--error-code` (`^[a-z0-9_]{1,40}$`) | `Backup restore check failed (<slug>)` | `backup_state.py --restore --latest exited <exit-code> (<error-code>); run <run_id>` | `urgent` | `restore_check:<slug>` |
| `lead_capture_window` | none | `GTM lead capture was stopped (<slug>)` | `Lead capture was stopped from <first ts> to <now>; check <inbox systems> for that window.` (`<first ts>` = the earliest `created_at` of the company's open `lead_capture_stopped:` notices, `<now>` = this task notice's own `created_at`, both in the pinned UTC form `YYYY-MM-DDTHH:MM:SSZ`; `<inbox systems>` = `", ".join(system_names.inbox_systems(pack))`, DECIDED (wave1c) and defined in §7.5 I2; all read by notices.py itself) | `urgent` | `lead_capture_window:<YYYY_MM_DD>` = the **UTC** date of `<first ts>` (its first ten characters with `-` replaced by `_`), never a company-local or machine-local date |

**Known limitation of `pending_commit` (stated).** Its `--path` grammar admits no space (nor any
character outside `[A-Za-z0-9._/-]`), so a stale tracked path containing one is never tasked: it
is refused `bad_template_arg` (W9's one-line note) and appears only in W10's *Pending commits*
section, which lists every `pending` path verbatim from `act.py pending-commits`. Widening the
grammar (e.g. percent-encoding) is not done here, because the path is copied into a pushed title
and a `dedupe_key`.

`lead_capture_window` (05_approver.md §5.5 step 0 item (3); `requests/05_approver.md` R54(c)) writes its
task only when the company has at least one open notice whose `dedupe_key` starts
`lead_capture_stopped:<slug>:` and `created_by` is `approvals_verify`, and then resolves every such
notice in-process (`resolve_by_dedupe_key(…, created_by="approvals_verify", resolved_by="notices")`);
with none it prints `{"ok": true, "created": false, "resolved": []}` and writes nothing. Every
template prints `{"ok": true, "notice_id": <id>|null, "created": bool, "resolved": [<ids>]}`; the
`(company, dedupe_key, created_by)` dedupe applies. `task` binds `--company` like every subcommand
(the company binding of "CLI rules" below: it must equal `CLAUDE_GTM_COMPANY` when that is set, and `runtime` is refused in session env). D tests
(each falsified by removing its clause): with `CLAUDE_GTM_COMPANY=other-company`, `write --company
other-company --kind info --severity info --title x --body y --created-by gtm_session` → exit 3
`write_in_session`; `task --company other-company --template lead_unanswered --lead-id <valid>
--received-at 2026-09-27T15:04:05Z` → one open `task` notice, `created_by: session`, whose title
contains no character outside the two values and the fixed text; `task --company other-company
--template lead_unanswered --lead-id 'x"; rm -rf' --received-at 2026-09-27T15:04:05Z` → exit 3
`bad_template_arg`; a `lead_capture_window` task whose earliest `lead_capture_stopped:` notice was
created at `2026-09-27T23:30:00Z` gets `dedupe_key: lead_capture_window:2026_09_27` whatever the
pack or machine timezone; `--title-file` → exit 2; `lead_capture_window` with two open
`lead_capture_stopped` notices → one task notice and both resolved, and with a same-key notice written
by `created_by: notices` → that one stays open.

**`resolve-owned` (the runner's and `gtm_session.sh`'s own resolver, for the notices they write).**
Resolves every open notice of `--company` whose `dedupe_key` equals `--dedupe-key` **and** whose
`created_by` equals `--created-by`, stamping `resolved_by: <created-by>`. It refuses exit 3
`resolve_owned_prefix` unless the key starts with one of `unsigned-caps:`, `tz_drift:`, `tcc:`,
`env_canary:`, `pacing_down:`, `purge_failed:`, and exit 3 `resolve_owned_in_session` when `CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is set in
its environment ("set", everywhere in this file's CLI rules, = **present in `os.environ`, even
with an empty value**; `env -u` removes it) — so no GTM session can call it (the §7.6 step 5 allowlist admits only commands
that start with the pinned interpreter `PY`, §7.2 "Interpreter pin", and G-B's scheduled-scope rule
denies every other command, so a session cannot unset those variables first). Prints
`{"ok": true, "resolved": [<ids>]}` (an empty list is exit 0). Its callers: §7.2 (runner, holds job
included) and §7.6 steps 3 and 4(d), each invoked through `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u
CLAUDE_GTM_RUN`. D tests: called with `CLAUDE_GTM_SESSION` set → exit 3 and the notice stays open;
a key `lease:…` → exit 3; a matching key written by `notices` (not the named `created_by`) is left
open.

**Fixed per-kind labels (`NOTICE_KIND_LABEL`, one dict owned by `notices.py`; the push rule, the
page renderer and `list`'s `label` key all import it, nobody restates it).** Exactly:

| `kind` | label |
|---|---|
| `hold` | `Held action` |
| `money_card` | `Approval needed` |
| `card` | `Card waiting` |
| `breaker` | `Breaker tripped` |
| `pause` | `Company paused` |
| `signin_missing` | `Sign-in missing` |
| `agent_cancel` | `Agent cancelled an action` |
| `trust` | `Trust check` |
| `budget` | `AI budget` |
| `chain` | `Action log integrity` |
| `isolation_hit` | `Isolation hit` |
| `runaway_spend` | `Runaway spend` |
| `task` | `Operator task` |
| `activity_log_failed` | `Activity log failed` |
| `cancel_too_late` | `Cancel came too late` |
| `spool_dropped` | `Queued command dropped` |
| `info` | `Info` |

D test: `set(NOTICE_KIND_LABEL) == set(NOTICE_KINDS)` (the kind enum above), and the page renderer
and `push_text` module objects reference the same dict (falsified by a local copy missing a key).

**Fixed refusal texts (`REFUSAL_REASON_TEXT`, owned by `notices.py`; rendered for an `isolation_hit`
notice whose `reason_code` is a key, whatever its writer, on the page, in `list`'s derived
`reason_text` key (never inside `label`) and in `push_text`'s body after the label; an unknown or
null code renders nothing extra):**

| `reason_code` | text |
|---|---|
| `cross_company` | `This would connect the company to another of your businesses. It must not be done by anyone, GTM or you.` |
| `unlisted_target` | `The target is not in the company's pack. If it really belongs to the company, add it to the pack's identity_allowlist through a reviewed pack change; otherwise do nothing.` |
| `phi_target` | `This is never done, by GTM or by hand through GTM.` |

These replace the former informational cards for those refusals (§7.5 E4, r5): an isolation refusal
already writes a pushed `isolation_hit` notice and trips the 02_act.md §2.9 breaker, so the page and
the push carry the fixed text and no card is posted (plan §20.11 names only three card types).

**Test seams for the two outward side effects (DECIDED (wave1c)).** `GTM_OPERATOR_PAGE` (an absolute
path) replaces the page default `~/Desktop/GTM_Operator.html`, and `GTM_OSASCRIPT` (an absolute path)
replaces `/usr/bin/osascript` as `argv[0]` of the push invocation below — each honoured **only when
`GTM_TEST=1`**, like `--machine-tz`. Either set without `GTM_TEST=1`: the notices.py CLI exits 2
`usage` before doing anything, and in-process callers (`write_notice`, `push_pending`,
`render_operator_page`) ignore it (production is never redirected). In test mode
(`gtm_env.test_mode(environ)` true) the real defaults are **never** used: with no `GTM_OPERATOR_PAGE`
the page is not rendered (the CLI `render` exits 2 `usage`; `write_notice`'s best-effort render is
skipped), and with no `GTM_OSASCRIPT` no push is attempted (the notice stays unpushed, `failed` not
incremented). Runner-level fixtures (§7.2; the runner refuses a test env) reach notices.py only
through the harness copy of the script whose `PY=` names a wrapper that exports `GTM_TEST=1`,
`GTM_OPERATOR_PAGE` and `GTM_OSASCRIPT` (a recording stub) before exec'ing the pinned interpreter.
K/D test (falsified by removing either gate): the real `~/Desktop/GTM_Operator.html`'s mtime (or
absence) is recorded before the full D suite and is unchanged after it, and the recording stub, never `/usr/bin/osascript`, receives every push; `GTM_OSASCRIPT` set without
`GTM_TEST=1` → CLI exit 2.

**Push rule (one function, `push_text`; every push channel uses it).**
- **Invocation.** The osascript push is exactly
  `subprocess.run(["/usr/bin/osascript", "-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run", title, body], timeout=5, shell=False)`
  where `(title, body) = push_text(notice)` (the one test seam for `/usr/bin/osascript`: below). Title and body travel **only** as argv items; no
  notice, action or finding text is ever spliced into AppleScript source text, and no shell is
  used. D test: a notice whose body is `" & (do shell script "touch /tmp/pwned_<nonce>") & "` is
  pushed and no such file appears (falsified by building the script with the body interpolated).
- **`<slug>` in every push title below = the notice's own `company` field** — so `runtime` for a
  runtime notice — **never** its `origin_company`: a hipaa-origin runtime notice pushes `GTM
  runtime`, and the origin slug (e.g. `othercompany`) never leaves the machine through a push.
- **Text.** For a notice whose `company` **or** `origin_company` pack has `regulated ∋ hipaa`,
  `push_text` returns the fixed pair
  (`"GTM <slug>"`, `"<kind> (<severity>) — open GTM_Operator.html"`) and nothing else — never the
  title, body, system, lead, target or recipient (macOS Notification Center persists pushed text
  on disk, outside every purge, and plan §20.4/§20.13 keep OtherCompany PHI out of logs and reports).
  Every other notice uses **the page's writer allowlist** (§7.1 "Page safety", *Notices*): when the
  notice's `created_by` ∈ `PAGE_TEXT_WRITERS` (the fixed templates of this file and the path-naming
  trust notices) → (`"GTM <slug>: <kind>"`, `<title>`), the title truncated to 200 characters; when
  it is `session` → (`"GTM <slug>: <kind>"`, `<NOTICE_KIND_LABEL[kind]> <dedupe_key>`) — the key
  notices.py composed from grammar-checked values only (`notices.py task`, above); for every other
  writer (`act`, `run-holds`, `breaker`, `G-A`, `secret_sink`, …, whose titles can quote action,
  finding, recipient or customer fields) → (`"GTM <slug>: <kind>"`, `<NOTICE_KIND_LABEL[kind]>
  <action_id or request_id or system or "">`), the same fixed label the page renders, followed for
  an `isolation_hit` notice by ` — <REFUSAL_REASON_TEXT[reason_code]>` when the code is a key. The
  body is never pushed for any company. So nothing leaves the machine through a push that the page
  itself would not render.
- E7's `PushNotification` (§7.5) sends exactly `push_text(notice)` joined as `<title> — <body>`,
  which `notices.py list --json` exposes per record as the key `push_text` so the prompt copies it
  verbatim and never composes text itself (a relay outside the machine, plan §20.5.6: no PHI to a
  vendor without a BAA). **A hipaa pack's scheduled session is never granted `PushNotification`
  at all** (§7.6 step 5; r5): that its message is `push_text` is only a prompt rule, and the
  orchestrator's context holds analyst `leads[]` and drafter/checker results, so for those packs the
  osascript fixed-pair push and the page are the only channels (the recorded probe-o fallback).
  **Recorded deviation from plan §20.8 (r6; pending ratification, `requests/07_notices_schedules.md`
  R63):** plan §20.8 says urgent runaway-spend cards "notify through every channel and wait"; for a
  hipaa pack this file withholds one channel (`PushNotification`). So that a hipaa pack's urgent `$`
  stop can never reach **no** push channel at all, **a recorded probe o PASS for an osascript
  notification delivered from a launchd-spawned process is a precondition for loading any hipaa
  pack's schedules and for loading `com.oversight.gtm.holds` while any hipaa pack is registered**
  (WP-K's `knowledge/oversight_install.md` §2 rows for those labels carry this precondition in their
  `does` text; the operator loads, §7.3). Until that PASS is recorded, a hipaa pack runs interactive
  sessions only, where the operator is present. Route (b) — granting `PushNotification` behind a
  hook that admits only an exact `push_text` — is not taken, because it adds a hook whose only
  benefit is a second channel for the fixed pair that osascript already carries.
- D tests (each falsified by removing its clause): a hipaa-pack notice whose title and body hold a
  marker string → the argv an osascript stub receives contains neither marker; a non-hipaa notice's
  body marker is not in the argv either; the `push_text` key of a hipaa notice in `list --json`
  contains no marker; **a non-hipaa `hold` notice written by `act` whose title holds a customer-name
  marker → neither the osascript argv nor its `push_text` key contains the marker, and both carry
  the fixed `Held action` label and its `action_id`** (falsified by pushing the title for every
  writer); a non-hipaa `task` notice written by `notices` pushes its title; a `session` task pushes
  exactly `Operator task <dedupe_key>`; a `runtime` notice with `origin_company: othercompany` (a
  hipaa fixture) pushes only the fixed pair (falsified by testing only `company`), and that pair's
  title is exactly `GTM runtime` — the argv contains no `othercompany` (falsified by taking `<slug>`
  from `origin_company`).

**CLI rules (the CLI is reachable from every GTM session, including unattended ones whose
orchestrator reads quoted untrusted data, so it is narrower than the in-process API).** "Session
env" below = `CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is set.
- **Company binding on every subcommand that takes or implies a company** (`list`, `write`, `task`,
  `resolve`, `card-draft`, `card-mark`; `resolve-owned` refuses any session env outright, below;
  `render`, `push` and `prune` take no company and print nothing but counts or a path): when
  `CLAUDE_GTM_COMPANY` is set, `--company` is **required** and must equal it — or, **for `list`
  only**, be `runtime` (E6/E7 read runtime notices) — an omitted `--company` or any other value →
  exit 3 `company_mismatch`, nothing read or written. **`list --company runtime` in session env
  returns only runtime records whose `origin_company` is `null` or equals `CLAUDE_GTM_COMPANY`**
  (every output form; the filter runs before `--status`/`--since`), so another company's
  runtime notices — its `tcc:`/`env_canary:` trust state, its slug in a `gtm_session`-written title,
  its `dedupe_key`s and `push_text` — never reach this session (plan §20.2 isolation). So a
  OtherCompanyB session (which has WebFetch/WebSearch egress) can never list OtherCompany's notices, its
  own or runtime ones, and `list` with no `--company` (every company), or of every runtime notice, is
  available only outside a GTM session (the page renderer, the operator's terminal). **No session writes a `runtime` notice (r5):** every mutating subcommand (`write`,
  `task`, `resolve`, `card-draft`, `card-mark`) given `--company runtime` in session env → exit 3
  `runtime_in_session`, nothing written — `runtime` has no pack, so the hipaa redaction could never
  key on it, and no E/I/D/W/M step needs a session to write one; runtime notices come only from the
  env-cleared shell writers (§7.2, §7.6, with `--origin-company`) and in-process writers. Checked
  before any other rule of the subcommand. D tests: with `CLAUDE_GTM_COMPANY=other-company`, `list
  --company othercompany --json` → exit 3 `company_mismatch` and no stdout array; `list --json` (no
  `--company`) → exit 3; `list --company runtime --json` and `list --company other-company --json` →
  exit 0, and with runtime notices whose `origin_company` is `exampleapp`, `null` and
  `other-company` present, the runtime list holds exactly the `null` and `other-company` ones (falsified by
  removing the filter), while the same command outside session env lists all three; `card-draft --company othercompany …` and `card-mark --company othercompany …` → exit 3; with
  `CLAUDE_GTM_COMPANY=othercompany`, `task --company runtime --template pending_commit --path x` and
  `resolve --company runtime …` → exit 3 `runtime_in_session` and nothing written or changed
  (falsified by admitting `runtime`); and (redaction rule above) a hipaa fixture notice whose title
  holds a marker, listed by a othercompany-bound session, never puts the marker in `list --json`
  output (falsified by removing the redaction), nor does an `act`-written non-hipaa notice's title.
- `write` (env-cleared shell writers only; `write_in_session` above): prints `{"ok": true,
  "notice_id": <id>, "created": true}` on creation. A dedupe hit (an `open` notice of the same
  company with the same `dedupe_key` **and the same `created_by`** exists) prints `{"ok": true,
  "notice_id": <existing id>, "created": false}`, exit 0, and changes nothing. An omitted
  `--dedupe-key` stores `dedupe_key: null`, and a null key is never deduped. `--created-by` is
  **required** and accepts only `gtm_session` and `run_gtm_job` (any other `NOTICE_CREATED_BY`
  member — `notices` and `session` included — is in-process or `task` only → exit 3
  `created_by_not_cli`), so nothing can forge from the CLI a notice attributed to `breaker`,
  `approvals_verify`, `act`, a hook or the fixed in-process `notices` templates. `--task` requires
  `--kind task` and `--kind task` requires `--task` (either alone → exit 2). `--kind` from the CLI
  is limited to `task`, `info`, `budget` and `trust`; any other kind → exit 3 `bad_kind`.
  **Reserved keys (hardening).** In order, after the company binding and `write_in_session`, first
  refusal wins, each exit 3 with nothing written:
  1. **Reserved dedupe prefixes, each owned by one writer:** `unsigned-caps:`, `tz_drift:`,
     `pacing_down:`, `purge_failed:` → `run_gtm_job`; `tcc:`, `env_canary:`, `lease:` →
     `gtm_session`; `signin_step:`, `card:`, `chain:`, `runaway_spend:`, `signin_missing:`,
     `baa:`, `card_deny:`, `weekly_report:`, `cancel_late:`, `spool_dropped:`,
     `lead_capture_stopped:`, `card_deny_after_approval:`, `approval_revoked:` → in-process writers
     only (`approval_revoked:` is no longer written as a notice key — R66 made it an event — and
     stays reserved so nothing else can take it);
     `lead_unanswered:`, `pending_commit:`, `restore_check:`, `lead_capture_window:` → `notices.py
     task` only. A key with a reserved prefix and any other `--created-by` → `reserved_dedupe_key`.
  2. **Kinds `budget` and `trust`** are accepted only with a reserved-prefix key whose owner is the
     given `--created-by` (so only the runner's `unsigned-caps:` and `gtm_session.sh`'s `tcc:` /
     `env_canary:` notices); any other `budget`/`trust` write → `kind_needs_reserved_key`. Every
     CLI-written `budget`/`trust` notice therefore has a named resolver (table below).
  So an injected session can neither pre-plant `env_canary:missing` as a silent squatter (it cannot
  `write` at all, nor touch `runtime`; and dedupe keys on `created_by`, so a squatter under another
  writer's name would not absorb the real urgent notice either) nor open an unresolvable
  `trust`/`budget` notice. The same `(company, dedupe_key, created_by)` dedupe rule binds the
  in-process API, `gtm_hooklib.write_notice_file` and both `approval_sig` writers
  (`requests/07_notices_schedules.md` R44).
- `resolve`: in session env, allowed **only** for an open `task` or `info` notice whose `created_by`
  is `session` (the session's own `notices.py task` notices) → else exit 3 `resolve_not_session_owned`;
  so an agent that forged a card "No" can never also clear the `card_deny:` notice that exists so a
  denial is never silent, nor any `act`/`notices`/shell-writer notice. **Outside** session env (the
  operator's terminal), allowed for any open `task`, `info` or `spool_dropped` notice. It stamps
  `resolved_by: "cli:<CLAUDE_GTM_SESSION or "none">"`. **`--resolution` in session env (r6):** the
  value must match `^[a-z0-9_ ]{1,40}$` (e.g. `done`, `not_needed`), else exit 3 `bad_resolution`,
  nothing changed — `list` prints `resolution` to later sessions, and no session writes free text
  anywhere a later session reads it (§7.1 "No free text from a session"). Outside session env the
  value is any single line of at most 200 characters (else exit 2 `usage`). **Operator override:**
  `resolve --operator` of
  a notice of any other kind succeeds only when a valid single-use operator marker
  `S/operator_ok/notice_resolve.<slug>.<notice_id>.json` exists, stamping `resolved_by:
  "operator"`; no valid marker → exit 3 `operator_marker_missing`, marker (if any) left in place. The
  marker command is **not yet defined** in 02_act.md §2.3 or 00_global_paths.md's
  `OPERATOR_OK_COMMANDS`: it is the open request `requests/07_notices_schedules.md` R45 (as amended
  by R63), and **`resolve --operator` ships only after R45 lands with its tests** — until then
  notices.py refuses the flag with exit 3 `operator_marker_missing` whatever exists on disk.
  **Validity (by exact reference):** a marker is valid exactly when
  `gtmlib.session.consume_operator_ok(ctx, "notice_resolve", <notice_id>)` accepts it — 00_global_paths.md
  §1.4 "Operator authority", checks (1)–(5): the `gtm.operator_ok.v1` record signed by GTMApprover
  and verified against **HEAD's** `approver_pubkey.pem`; canonical payload with exactly the keys
  `v, kind, command, company, target, nonce, expires`, `kind == "operator_ok"`; `command ==
  "notice_resolve"`, `company` = the notice's own `company` field (**`runtime` included**, for a
  runtime notice), `target` = the `notice_id`; `now < expires ≤ now + 15 min` (maximum age 15
  minutes from signing); nonce unused. **Order, single use:** notices.py takes the notices lock,
  re-reads the notice (still `open`, else `notice_not_open` and the marker is left in place), then
  calls `consume_operator_ok` — which appends the nonce `consume` line and deletes the marker under
  `S/operator_ok.lock` — and only after it returns writes `resolved` onto the notice; a crash between
  the two leaves the marker spent and the notice open (fail safe: the operator signs again). It is
  the documented way out for a notice whose owning mechanism can never fire (e.g. a `card` notice
  whose card was deleted by hand). **`--operator` scope:** in session env it is refused exit 3
  `resolve_not_session_owned` before any marker lookup (a session never consumes a marker); outside
  session env it applies only to kinds outside {`task`, `info`, `spool_dropped`}, and given with one
  of those three kinds it is refused exit 2 `usage` (they resolve without it; no marker is read or
  consumed). Without `--operator`, every other kind (`card`, `runaway_spend`,
  `trust`, `isolation_hit`, `breaker`, `chain`, `budget`, `money_card`, `hold`, `signin_missing`,
  `pause`, `agent_cancel`, `activity_log_failed`, `cancel_too_late`) → exit 3
  `resolve_kind_not_cli`: its owning mechanism resolves it in-process (table below), so a confused
  or injected session can never take an open card, runaway-spend, trust, breaker or chain notice off
  `GTM_Operator.html` or E6 — in particular a `card` notice (a pending shared-system or non-money
  revert card) stays on the page until its card is actually answered.
- **Resolver of every kind this file writes (named, so no notice stays open forever and dedupe
  never silently swallows a re-alert):**

  | notice (dedupe key) | written by | resolved by (in-process or `resolve-owned`) |
  |---|---|---|
  | `budget` `unsigned-caps:<slug>` | runner §7.2 | the runner, `resolve-owned --created-by run_gtm_job`, on the first run whose `caps --check` exits 0 (resolution `caps signed <run_id>`) |
  | `trust` `tcc:<grant>` (`<grant>` ∈ `accessibility`, `screen_recording`; no host segment) | `gtm_session.sh` step 3 | `gtm_session.sh` step 3, `resolve-owned --created-by gtm_session`, when the probe reports that grant `false` — whichever host app the session runs under, so a notice raised under Terminal is cleared by a clean probe under VS Code |
  | `trust` `tcc:probe_failed` | `gtm_session.sh` step 3 | `gtm_session.sh` step 3, the same way, when the probe exits 0 with parseable output |
  | `trust` `env_canary:missing` (`runtime`) | `gtm_session.sh` step 4(d) only (§7.5 E0 writes nothing; it ends the run) | `gtm_session.sh` step 4(d), `resolve-owned --created-by gtm_session`, after a session whose canary exists (§7.6) |
  | `info` `pacing_down:all` (`runtime`, urgent, pushed) / `info` `purge_failed:all` (`runtime`, urgent, pushed) | the holds job, §7.2 | the holds job, `resolve-owned --created-by run_gtm_job`, on the first holds run whose `act.py pacing --all` (resp. the `--age-only` purge) exits 0 |
  | `task` `lease:<run_id>` | §7.6 step 4 (`created_by: gtm_session`) | the operator (`notices.py resolve` in his terminal) once seen; a session cannot (not `session`-owned) |
  | `task` `lead_unanswered:<lead_id>`, `restore_check:<slug>`, `pending_commit:<path>`, `lead_capture_window:<date>` | `notices.py task` (I6, M1, W9, I1b; `created_by: session`) | the operator, or a session with `notices.py resolve` once the task is done; W9 never re-creates a `pending_commit` task for a path `act.py pending-commits` no longer reports (no diff against `HEAD`, R50), so a committed path stays quiet |
  | `info` `weekly_report:<run_id>` | W10 (`weekly_report.py`, in-process, `created_by: notices`) | `weekly_report.py` itself, in-process: writing a new week's notice resolves every older open `weekly_report:` notice of the company (`resolved_by: notices`); the operator may resolve one in his terminal |
  | `task` `tz_drift:<slug>` | the runner, §7.2 (`created_by: run_gtm_job`) | the runner, `resolve-owned --created-by run_gtm_job`, on the first run of that company whose `runner_probe` reports no drift (resolution `tz ok <run_id>`) |
  | `info` `card_deny:<request_id>` (warn, pushed: a `$` request denied by a mirror-card "No", E1b [R52]) | `act.py record-external`, in-process (`created_by: act`, R52) | the operator only (his terminal, allowed for `info`) once read; never a session (`resolve_not_session_owned`): it exists so a denial decided through the operator-input file (which many agents edit) is never silent |
  | `task` `baa:<slug>:lead_sink` ("lead sink has no BAA on record") | `act.py` (`created_by: act`, 03_schemas.md FID-19) | the operator (his terminal), once `lead_sink.baa_ref` is recorded |
  | `task` `lead_capture_stopped:<slug>:<date>` | `approval_sig.write_urgent_notice` (`created_by: approvals_verify`, 05_approver.md §5.5 step 0) | `notices.py task --template lead_capture_window` (I1b), in-process, on the first trusted inbox run after the tree clears |
  | `cancel_too_late` `cancel_late:<action_id>` | act.py (03_schemas.md §3.11 late cancel) | act.py, in-process, when `complete` records that action's outcome (`requests/07_notices_schedules.md` R62) |
  | `spool_dropped` `spool_dropped:<file name>` | act.py (02_act.md §2.4 pause spool) | the operator (his terminal, `notices.py resolve`) once read |
  | `card` `card:<action_id>` (an `awaiting_card` action) | `act.py authorize` / `revert` (02_act.md §2.4) | in-process by `act.py` when the card's answer is recorded — in scheduled runs by the §7.5 **E1b** step's `act.py record-external --kind approval --card <action_id> --action <action_id>` (any decision other than `unclear`), otherwise the approving `authorize`/`revert` step 2 — `requests/07_notices_schedules.md` R20 |
  | `card` `card:<action_id>` (a `refused` `meta.business_portfolio_*` action with `card_on_refuse: true`) | `act.py authorize` §2.6 rule 2 | in-process by `act.py record-external --kind approval --card <action_id> --action <action_id>` (E1b) once the informational card E4 posted for it is answered with any decision other than `unclear`; the action stays `refused` (NEVER is not operator-overridable) — `requests/07_notices_schedules.md` R36 as amended by R62 |
  | `money_card` / `runaway_spend` of an `awaiting_approval` action | `act.py authorize` (02_act.md §2.6) | in-process by `act.py` when the request is decided by a **signed** GTMApprover approval or denial file (plan §20.8); only in the [R52]-ratified variant (§7.5 E1b) also by a mirror-card `deny` recorded by E1b of a request **with no approval record** — never for a request the operator already signed (R66: that "No" changes nothing and raises `card_deny_after_approval:`), and never for a spend-reducing request, whose card "No" is a re-show request only |
  | `agent_cancel` `card_deny_after_approval:<request_id>` (push; `urgent` for an `urgency: urgent` request, else `warn`) | `act.py record-external --kind approval` (02_act.md §2.11, `requests/05_approver.md` R66(b)): a card "No" arrived for a request the operator already signed — **no state change, the signed approval stands** | the operator only, `notices.py resolve --operator` with a `notice_resolve` marker (`agent_cancel` is not CLI-resolvable without it); never a session, never in-process — it records that someone answered "No" in the many-writer operator-input file against an approval he signed, which no agent may dismiss |
  | `task` `signin_step:<step>:<id>` (§7.1 "Card drafts", sign-in card inputs (b)–(e)) | its producer (table there) | its producer, in-process, when the step is observed done (table there); the operator may also resolve it in his terminal (kind `task`) |
  | `chain` `chain:<slug>` | `card-draft --kind chain` | `chain-repair` (02_act.md §2.4), in-process |
  | any kind whose owner cannot fire | — | the operator, `notices.py resolve --operator` with a single-use `notice_resolve` marker (above) |

  D tests (each falsified by removing its resolver): caps unsigned → one `budget` notice and
  one push; next run signed → that notice `resolved` (`resolved_by: run_gtm_job`); a later run
  unsigned again → a **new** notice and a second push. `resolve` of an open `card` notice → exit 3
  and still open; in session env, `resolve` of an open `card_deny:` `info` notice (`created_by: act`)
  → exit 3 `resolve_not_session_owned` and still open, while the same command outside session env
  resolves it (falsified by admitting every `info` notice in session env); a second weekly report
  resolves the first week's `weekly_report:` notice.
- `card-mark`: requires a row in this company's `ST/cards_posted.jsonl` whose `card_id` equals
  `--card-id` (none → exit 3 `card_not_posted`), so a made-up card id can never mark a notice as
  carded. `--replaces <old>` is the only way to change a notice's `card_id`, and only for the chain
  post-deny path of "Card drafts" (below: the notice's current `card_id` must equal `<old>`,
  and `cards.answered_card(ctx, <old>).decision` must be `deny`; else exit 3 `card_id_conflict`).
- `card-draft --out` must resolve inside `<home>/.claude/gtm/drafts/` of `--company`'s home (else
  exit 2 `usage`).
D tests (each falsified by removing its clause): `resolve` of an open `runaway_spend`, `breaker` and
`chain` notice → exit 3 and still open; `write --created-by breaker` and `write --created-by notices`
→ exit 3 `created_by_not_cli`; `card-mark` with a card id absent from `ST/cards_posted.jsonl` → exit
3 and the notice stays `card_id: null`; a second `write` with the same `dedupe_key` prints `created:
false` and the first id; `write --task --kind info` → exit 2; `resolve` of a `session` `task` notice in
session env records `resolved_by: "cli:<session>"`; `resolve` of an already-resolved `task` notice →
exit 3 `notice_not_open`; `write --system gbp` → exit 2 (unknown flag); `write --body-file /tmp/x.txt`
→ exit 2 and no notice; `list --json` prints an array sorted by `created_at` and every record carries
a string `push_text`. **Hardening (each falsified by removing its rule):** with
`CLAUDE_GTM_COMPANY=other-company` set, `write …` (any company) → exit 3 (`company_mismatch` for
`--company othercompany`, `write_in_session` for `--company other-company`, `runtime_in_session` for
`--company runtime`); **the squat case:** a session-env `write --company runtime --kind info
--severity info --dedupe-key env_canary:missing --created-by gtm_session` → exit 3 and no notice,
and a later `gtm_session.sh` step 4(d) write of the real `env_canary:missing` notice creates it
(`created: true`, pushed urgent); with every session refusal removed but `(dedupe_key, created_by)`
matching kept, an env-cleared `write … --created-by run_gtm_job --dedupe-key env_canary:missing` →
exit 3 `reserved_dedupe_key`, and the real notice is still created (the second layer holds alone);
`write --kind trust --dedupe-key anything:1 --created-by gtm_session` → exit 3
`kind_needs_reserved_key`; `resolve --operator` of an open `breaker` notice with no marker → exit 3
`operator_marker_missing` and still open, with a valid marker → `resolved`, `resolved_by:
"operator"`, marker deleted (these two with R45; before R45 lands, the valid-marker case also exits 3
`operator_marker_missing`); a runtime notice is resolved only by a marker whose `company` is
`runtime`, and a marker naming its `origin_company` instead is left in place with exit 3; a marker
whose `expires` is 16 minutes after signing → exit 3, marker left; in session env, `resolve
--operator` of an open `breaker` notice with a valid marker present → exit 3
`resolve_not_session_owned` and the marker still exists; outside session env, `resolve --operator`
of an open `task` notice → exit 2 `usage` and no marker consumed; in session env `resolve --company
other-company --notice <own session task> --resolution "done"` → resolved, while `--resolution "see
http://x"` → exit 3 `bad_resolution` and still open (each falsified by removing its clause).

**Card drafts (FID-10; DECIDED HERE — the chain card is a recorded deviation from plan §20.11,
pending ratification, `requests/07_notices_schedules.md` R4).** Plan §20.11, which supersedes the
rest of the plan, keeps breaker trips, `PAUSE.budget` and `PAUSE.chain` on the page and names only
three card types (`$`, sign-in, Meta portfolio). This section nevertheless gives a chain break one
card, because `chain-repair` (02_act.md §2.4) is built on an answered card with subject
`chain_repair <slug>` (02_act.md §2.6 `CARD_SUBJECT_RE` already carries that subject), and the only
other operator-authority path, the `S/operator_ok/` marker (02_act.md §2.3), does not cover
`chain-repair`. `PAUSE.chain` is still shown on the page as §20.11 requires; the card is its lift
mechanism, not a new operator-decision type. If the ratification instead picks the marker, the
`--kind chain` branch below, E1's `card-post`, and the `chain` subject go, and E1 runs
`chain-repair` against the marker.
**Breaker trips get no card** (plan §20.11 supersedes §6.8's "+ card"): the pushed `breaker` notice
and `GTM_Operator.html` are the surface, and how the pause lifts is 02_act.md §2.9's rule (FID-11).
`card-draft` is read-only except for its `--out` file, (chain only) a missing `chain` notice, and
(signin only) the `signin_step:approver` notice of input (b) below:
- `--kind signin` — **the one batched sign-in card** (plan §20.10/§17k/§20.8; 05_approver.md and
  06_connectors.md "the batched sign-in card" point here). **Inputs** (every one an open notice of
  the company with `card_id: null`; each line's values come only from the notice's `system` /
  `dedupe_key` / `created_at` and the committed pack, never from a notice title or body):

  | input | source notice (producer) | fixed template line | resolver |
  |---|---|---|---|
  | (a) signed-out system — **including the first sign-in of an onboarding login** (the `/gtm-onboard` T0 baseline reads land on each system's login page and report it) and any login that needs a password, phone code or 2FA step (the operator does that step in the GTM browser) | `signin_missing` (`act`, `ingest-findings`, 02_act.md §2.4) | `- <system>: the <slug> GTM browser profile is signed out (seen <created_at>). Sign in once in the <slug> GTM browser (run /gtm-signin <system> in the <slug> GTM session to open that system's sign-in page), including any password or phone step.` | `ingest-findings` on the next clean read of that system (02_act.md §2.4) |
  | (b) approver not running | `task` `signin_step:approver` (written by `card-draft` itself, in-process, `created_by: notices`, warn, push, `task=True`; title exactly `GTMApprover not running (<slug>)`, body exactly `Last heartbeat <finished_at or "none">; <n> approval request(s) pending. Load com.oversight.gtm.approver (knowledge/oversight_install.md §2).`) when `R/schedules/heartbeats/com.oversight.gtm.approver.json` is absent, unparseable or has `finished_at` older than 15 min **and** the company has at least one pending approval request (03_schemas.md §3.7; the list the page's *Pending approval requests* section reads) | `- GTMApprover is not running (last heartbeat <finished_at or "none">): install and load it as knowledge/oversight_install.md §2's com.oversight.gtm.approver row says (the operator loads it; no agent does), then approve the pending request(s) there with Touch ID. Once it runs, a non-GTM runtime session (not a GTM session) flips that row's expected_state to loaded in a reviewed commit.` | `card-draft --kind signin` itself (`resolve_by_dedupe_key(…, created_by="notices", resolved_by="notices")`) on the first call that sees a heartbeat younger than 15 min, or no pending request |
  | (c) a secret the operator must type | `task` `signin_step:secret_prompt:<name>` (`secret_sink`, in-process, when its `--prompt` fallback is the only capture path, 06_connectors.md §6.6; `requests/07_notices_schedules.md` R40) | `- Secret <name>: run /opt/homebrew/opt/python@3.13/bin/python3.13 ~/.claude/tools/gtm/secret_sink.py --prompt <name> in Terminal and type the value there (never into a chat, a card or a file).` | `secret_sink`, in-process, when `<name>` is stored |
  | (d) an operator IAM grant | `task` `signin_step:iam:<system>` (`act`, in-process, when a connector's `impersonate` route fails `token_mint_failed`, 06_connectors.md §6.3; R40) | `- <system>: grant roles/iam.serviceAccountTokenCreator on <service_account_email> to <gcloud_account> (06_connectors.md §6.3), nothing wider.` (both values from the committed `connectors.json`) | `act`, in-process, on the next successful token mint for that system |
  | (e) a platform revocation step after ROTATE | `task` `signin_step:revoke:<ticket_id>` (`secret_sink` ROTATE path, 06_connectors.md §6.6; R40) | `- <system>: revoke the credential issued during setup ticket <ticket_id> (06_connectors.md §6.6 revocation step for <system>).` | `secret_sink`, in-process, when the re-capture for that action succeeds; else the operator (`notices.py resolve`, kind `task`) |

  Inputs (b)–(e) are `task` notices (on the page and E6 like every task) whose dedupe prefix
  `signin_step:` is reserved to in-process writers (§7.1 CLI rules, reserved-key rule 1); their `<name>`, `<system>` and
  `<ticket_id>` segments match their 00_global_paths.md §0.3 grammars (anything else is not
  rendered and is listed in the draft JSON's `skipped`). No input → prints `{"post": false}`, writes
  nothing (beyond input (b)'s notice). Otherwise writes the card body to `--out` and prints
  `{"post": true, "card_id": "signin_<slug>_<YYYYMMDDTHHMMSSZ>", "title": "Sign-in and setup
  steps (<slug>): <n>", "notice_ids": [...], "subject": null, "replaces": null, "skipped": [...]}` (a
  sign-in card gates nothing, so it is posted without `--subject`). Body (fixed template): the lines
  of every input, grouped (a)–(e) in that order and sorted within a group, then `No answer is needed
  here. Each line closes by itself when its step is seen done.` One card batches every pending step
  of the company (plan §20.10 "ONE batched sign-in card"); a step that appears after the card was
  posted starts the next card. D tests (with fixtures per input, each falsified by removing that
  input's branch): an open `signin_step:secret_prompt:gsc_key` task → the draft carries the (c) line
  naming `gsc_key`; an approver heartbeat 20 min old plus one pending request → one
  `signin_step:approver` task is written and the draft carries the (b) line, and a fresh heartbeat
  on the next call resolves it and drafts no (b) line; with no pending request, a stale heartbeat
  writes nothing; an open `signin_step:iam:google_ads` task → the (d) line names the pack's
  `service_account_email` and `gcloud_account`; an open `signin_step:revoke:<ticket_id>` → the (e)
  line; a `signin_step:secret_prompt:` key whose name fails its grammar → no line, listed in
  `skipped`; a notice title holding a marker string never reaches the body.
- `--kind chain`: `ST/PAUSE.chain` absent → `{"post": false}`. Present and no open `chain` notice →
  first writes one (`created_by: notices`, urgent, push, `dedupe_key: chain:<slug>`; title exactly
  `Action log integrity check failed (<slug>)`, body exactly `PAUSE.chain since <PAUSE.chain ts>
  (reason <PAUSE.chain reason>). Every GTM write for <slug> is refused until repair; a repair card
  follows.` — `<PAUSE.chain reason>` is the pause file's reason code, rendered only when it matches
  `^[a-z0-9_]{1,40}$` and as `unknown` otherwise, so no free text reaches a pushed title/body; the
  same rule applies to the card body's `<PAUSE.chain reason>` below). Post only when
  that open `chain` notice has `card_id: null`, or under the post-deny rule below; it prints
  `{"post": true, "card_id": …, "title": …, "notice_ids": [<the chain notice>], "subject":
  "chain_repair <slug>", "replaces": <old card_id or null>}` — the subject is what
  `cards.require_approved(ctx, card_id, "chain_repair <slug>")` (02_act.md §2.4 `chain-repair`)
  requires, and a card posted without it has subject `None` (02_act.md §2.6), which `chain-repair`
  refuses forever (`card_subject_mismatch`). Card id `chain_<slug>_<YYYYMMDDTHHMMSSZ>`, title
  `Action log integrity check failed (<slug>): repair?`, body (fixed template): `The GTM action log
  for <slug> failed its integrity check (<PAUSE.chain reason>, since <PAUSE.chain ts>). Until it is
  repaired every GTM write for <slug> is refused; new leads are kept in lead_fallback.jsonl
  (<N> so far). A failed integrity check can also mean the log was tampered with. Repair rotates
  the broken log aside (kept, never deleted), starts a new log carrying every open action, and
  replays the fallback leads. <K> action(s) have events recorded after the point where the log
  stops verifying: <ids>. Repair does NOT trust those events: each of these actions is carried
  into the new log as "proposed" and must be reviewed and authorized again. Answer to authorize
  repair, or to leave it paused while you look (answer grammar: 02_act.md §2.6 card rule).`
  `<K>`/`<ids>` come from a **read-only** fold, `gtmlib.chain.post_break_actions(ctx) ->
  list[str]` (02_act.md, `requests/07_notices_schedules.md` R21): the ids of every action with at
  least one event after the last entry whose hash verifies, sorted; the body lists at most 50 ids
  and then `(+<n> more)`; `K = 0` renders the sentence as `No action has events after the break.`
  The card states this because a chain break is also the tamper signal, and a "Yes" read as "fix
  the log" must never launder a forged post-break `authorized` event into the new genesis:
  `chain-repair` carries every post-break action as `proposed` — never `authorized`, `held` or
  `ticketed` (R21). D test: `PAUSE.chain` with two actions whose last event lies after the break →
  the draft body names both ids and the count 2. D/A2 test (with 02_act.md's fixtures): a forged
  `authorized` event appended after the break point ends up `proposed` after a "Yes" repair, and
  `act.py execute` on it exits 3 (falsified by carrying the folded state as-is).
  **Post-deny rule.** When the open `chain` notice's `card_id` answers `deny`
  (`cards.answered_card`), `card-draft` drafts a fresh card only once 7 days have passed since that
  card's `ST/cards_posted.jsonl` `ts`, printing `"replaces": <old card_id>`; the new body starts
  with the line `The previous repair card (<old card_id>) was answered "no" on <date>; asking
  again.` Before that, it prints `{"post": false, "denied": <old card_id>}`. An `unclear` answer
  never re-drafts (the operator re-answers the same card, 02_act.md §2.6). So a "no" pauses the
  question for a week instead of forever, and nothing needs hand-editing state.
- `card-mark` stamps `card_id` onto each named notice (under the notices lock; refuses exit 3 when a
  notice is unknown, not `open`, of another company, already carries a different `card_id` and
  `--replaces` does not name it under the rule above, or the card id has no `ST/cards_posted.jsonl`
  row). The session runs it only after `act.py card-post` exited 0, so a failed post leaves the
  notices un-carded and the next run retries.
D tests: two open `signin_missing` notices → one draft listing both; after `card-mark` → `post:
false`; a third notice afterwards → a new draft listing only it; `PAUSE.chain` with no notice →
the notice is created and a draft produced whose JSON carries `"subject": "chain_repair <slug>"`;
falsified by dropping the `card_id: null` filter (the second call drafts again). Chain post-deny
(each falsified by removing its clause): a chain card answered "No" → `card-draft` prints `post:
false, denied: <id>` on day 6 and `post: true, replaces: <id>` on day 8; `card-mark --replaces`
then moves the notice to the new id; `card-mark --replaces` against a card answered "Yes" → exit 3.
D/A2 end-to-end (with 02_act.md's `cards.py` fixtures): a chain card posted by E1's exact command
(§7.5) and answered "Yes" lets `act.py chain-repair --company <slug> --replay --card <id>` succeed
and remove `PAUSE.chain`; answered "No" → exit 3 `card_denied`; the same card posted without
`--subject` and answered "Yes" → exit 3 `card_subject_mismatch` (the regression this closes).

**Exit codes (I15), every `notices.py` subcommand:** 0 ok, 1 internal, 2 usage, 3 a refusal, 12
lock timeout. **Order of checks (first failure wins):** argument parsing (exit 2) → company binding
(`company_mismatch`, `runtime_in_session`) → session-env refusals (`write_in_session`,
`resolve_owned_in_session`) → value checks (`bad_kind`, `bad_company`, `bad_severity`,
`bad_created_by`, `created_by_not_cli`, `bad_template_arg`, `bad_resolution`) → reserved-key rules
(`reserved_dedupe_key`, `kind_needs_reserved_key`, `resolve_owned_prefix`) → state checks, in this
order (`unknown_notice`, `notice_not_open`, `resolve_not_session_owned` — for `resolve --operator` in
session env too, before any marker lookup —, then `--operator` with a `task`/`info`/`spool_dropped`
notice → exit 2 `usage` (the one usage refusal decided at the state stage, because it needs the
notice's kind), `resolve_kind_not_cli`, `operator_marker_missing`, `card_not_posted`,
`card_id_conflict`). The complete mapping:

| subcommand | condition | exit | `error.code` |
|---|---|---|---|
| any | unknown flag, missing required flag, mutually exclusive flags, bad flag syntax | 2 | `usage` |
| `list` | `--since` not in the pinned UTC form; `--status` outside the set | 2 | `usage` |
| `write` | `--task` without `--kind task` or the reverse; `--origin-company` without `--company runtime` | 2 | `usage` |
| `write` | `--task` with `--company runtime` | 2 | `runtime_has_no_home` |
| `card-draft` | `--out` outside the company's `drafts/` | 2 | `usage` |
| every company-taking subcommand | `--company` omitted or ≠ `CLAUDE_GTM_COMPANY` (runtime allowed for `list` only) | 3 | `company_mismatch` |
| `write`, `task`, `resolve`, `card-draft`, `card-mark` | `--company runtime` in session env | 3 | `runtime_in_session` |
| `write` | session env | 3 | `write_in_session` |
| `resolve-owned` | session env | 3 | `resolve_owned_in_session` |
| `write` | `--kind` a `NOTICE_KINDS` member other than `task`/`info`/`budget`/`trust`, or not a member | 3 | `bad_kind` |
| `write`, `task` | `--company` (or `--origin-company`) neither a `gtm_slugs()` member nor (`write` only) `runtime` | 3 | `bad_company` |
| `write` | `--severity` outside `info`/`warn`/`urgent` | 3 | `bad_severity` |
| `write`, `resolve-owned` | `--created-by` not in `NOTICE_CREATED_BY` | 3 | `bad_created_by` |
| `write`, `resolve-owned` | `--created-by` a member other than `gtm_session`/`run_gtm_job` | 3 | `created_by_not_cli` |
| `task` | unknown `--template`, or a flag value failing its grammar | 3 | `bad_template_arg` |
| `write` | reserved prefix owned by another writer | 3 | `reserved_dedupe_key` |
| `write` | `budget`/`trust` without an own reserved key | 3 | `kind_needs_reserved_key` |
| `resolve-owned` | key outside its prefix list | 3 | `resolve_owned_prefix` |
| `resolve`, `card-mark` | notice id unknown for that company | 3 | `unknown_notice` |
| `resolve`, `card-mark` | notice not `open` | 3 | `notice_not_open` |
| `card-mark` | notice of another company | 3 | `company_mismatch` |
| `resolve` | session env and `--resolution` failing `^[a-z0-9_ ]{1,40}$` | 3 | `bad_resolution` |
| `resolve` | outside session env and `--resolution` not one line of ≤ 200 characters | 2 | `usage` |
| `resolve` | session env and the notice is not a `session`-owned `task`/`info` | 3 | `resolve_not_session_owned` |
| `resolve --operator` | session env (whatever the notice; checked before any marker lookup) | 3 | `resolve_not_session_owned` |
| `resolve --operator` | outside session env, notice kind `task`, `info` or `spool_dropped` (no marker read) | 2 | `usage` |
| `resolve` | outside session env, kind not `task`/`info`/`spool_dropped`, no `--operator` | 3 | `resolve_kind_not_cli` |
| `resolve --operator` | no valid marker (and always, until R45 lands) | 3 | `operator_marker_missing` |
| `card-mark` | card id has no `ST/cards_posted.jsonl` row | 3 | `card_not_posted` |
| `card-mark` | notice carries a different `card_id` and `--replaces` does not name it, or `--replaces` against a card not answered `deny` | 3 | `card_id_conflict` |
| any | a notices or pushed lock not taken in 5 s | 12 | `lock_timeout` |

(`card_id_conflict` and the other `card-mark` refusals are those of "Card drafts", **above**.)
**Output shape (the `act.py` envelope of 02_act.md
§2.4 "Output", reused):** success prints one JSON object with `"ok": true` on stdout, except the
two list forms: `list --json` prints its array, and `list` without `--json` prints its text lines
— **the one non-JSON success output**. The exact success objects (r6; one per subcommand):
`write` / `task` / `resolve-owned` as given above; `resolve` → `{"ok": true, "notice_id": <id>,
"resolved_by": <str>}`; `push` → `{"ok": true, "pushed": <n>, "failed": <n>}` (from
`push_pending()`'s tuple); `prune` → `{"ok": true, "deleted": <n>, "pushed_rows": <n>}`; `render` →
`{"ok": true, "path": "<absolute path of the page written>"}`; `card-draft` → the objects given in
"Card drafts" below, each with `"ok": true` as an additional key; `card-mark` → `{"ok": true,
"marked": [<notice ids>]}`. Every exit 2 and 3 prints exactly
one JSON object `{"ok": false, "error": {"code": "<code>", "message": "<fixed text>"}}` on
**stdout**, newline-terminated, and nothing else there (human text to stderr only; parser errors
go through the same JSON parser class, exit 2 `usage`; the §7.2 runner and `gtm_session.sh` send
that stderr away from `.err.log`, §7.2 "Log files" (4)), so shell callers and the §7.2 runner parse
`error.code` exactly as for `act.py`; `message` never quotes a title, body or file content. D test:
every code above is produced by at least one fixture and printed in that shape, and every success
object above is printed exactly (key set compared); `push` exits 0 even when an individual osascript
push fails (it reports `{"ok": true, "pushed": N, "failed": N}` with `failed` ≥ 1), `render` exits 1
only when the page cannot be written. This is how
shell callers (`gtm_session.sh`, `run_gtm_job.sh`) write notices. `write_notice` best-effort calls
`render_operator_page()`. **Atomic page write:** `render_operator_page` writes the whole page to a
temp file in the same directory as `out` (`tempfile.NamedTemporaryFile(dir=out.parent,
delete=False)`, flushed and `fsync`ed) and then `os.replace`s it onto `out`, so concurrent renders
(every `write_notice`, `push`, `render`) can race only on which complete page wins, never leave a
torn `GTM_Operator.html`. D test: 20 concurrent renders leave a page that parses and whose CSP hash
matches its script. Pushes therefore happen at creation time in every session kind —
interactive P2–P7 sessions included — not only when `run_gtm_job.sh` or the holds job runs.

**GTM_Operator.html inputs** (self-contained, inline CSS/JS, per company sections): open notices;
pending approval requests (+ approval/denial files); held actions (countdown to `hold_until`);
recent completions (last 20 `completed` per company from actions fold); PAUSE files (`ST/PAUSE*`,
`S/PAUSE.trust`, `R/schedules/DISABLED`); agent-made cancels; last cycle per kind with
status; `signin_missing` notices; heartbeat freshness of `com.oversight.gtm.*` (with the fixed
`row needs flip: <label>` line of §7.3 for a fresh heartbeat whose `knowledge/oversight_install.md`
§2 row says `unloaded`); the path of the
newest weekly report per company (§7.5 W10; path only, never its contents); **Signed approvals:
card "No"s and revocations** (`requests/05_approver.md` R65 as amended by R66(d)). A card "No"
decides only an undecided request and **never revokes an approval the operator signed** (05 §5.1
step 5; plan §20.8 strikes the archive-answer path for money); only the operator's own non-agent
channels revoke one. The block has two row kinds: (i) every open `agent_cancel` notice whose
`dedupe_key` starts `card_deny_after_approval:` — a card said "No" to a request he signed, **the
approval stands** — one row each: `request_id`, the request's amount and unit (or `no amount`), its
`account_id` (the id, never a display name), the card id that said "No" (the notice's `card_id`,
else the request id), `created_at`; (ii) every `approval_revoked {request_id, who}` event of the
last 7 days from the actions fold (`who` ∈ `operator_script`, `approver_menu`, `hand_made_file` — the
operator's channels, R66(c)), one row each: `request_id`, amount and unit, `account_id`, `who`, the
event `ts`. So a "No" written into the many-writer operator-input file against a signed request is
never silently lost, and nothing on the page describes a card as having revoked a signed approval
(plan §20.7). D tests (each falsified by removing its row kind): a fixture
`card_deny_after_approval:<request_id>` notice appears as a kind (i) row with those five fields and a
marker in its title does not; a fixture `approval_revoked` event with `who: approver_menu` appears
as a kind (ii) row; A2/D end-to-end (with 02's fixtures): a card "No" archived against a signed
urgent stop (campaign pause, `"0.00"`) leaves it executable (the action's state unchanged, the
approval and its unconsumed nonce intact, `act.py execute` succeeds) and the block shows the kind (i)
row.

**Page safety (the page is a local file opened in a browser, and the notice titles/bodies it may
render can carry session-written, attacker-influenced text; lead `source`, finding `text` and
`evidence[]` never reach it at all, field allowlist below).**
- Every rendered value is passed through `html.escape(value, quote=True)`; no notice, action,
  request or finding text ever reaches a `<script>` body, an event-handler attribute, a `style`
  attribute, or a URL attribute (`href`/`src`). Links the page needs (approval files, the queue
  file) are built only from ids that match their 00_global_paths.md §0.3 grammar.
- The head carries `<meta http-equiv="Content-Security-Policy" content="default-src 'none';
  style-src 'unsafe-inline'; script-src 'sha256-<base64 of the one inline script>'; img-src data:;
  base-uri 'none'; form-action 'none'">` — no `connect-src`, so nothing on the page can reach the
  network; `render_operator_page` computes the hash from the exact script text it writes.
- **Field allowlist per section (every company, every pack; PHI and untrusted-text rule).**
  `~/Desktop/GTM_Operator.html` is outside every purge, so the page renders **only** the fields
  listed here; no section ever renders an action's `after`, `before`, `after_digest` preview,
  draft text, `target_ref`, recipient, account display name, lead `source` or any lead field,
  review/DM text, or finding `text`/`evidence[]` — for any pack:
  - *Held actions:* `action_id`, `row_id`, `system`, `state`, `hold_until` (countdown), held-at
    timestamp, and the hand-made cancel path `~/.claude/.gtm_state/cancels/<action_id>` plus the
    command `gtm_cancel.sh <action_id>` (both built from the `action_id` only, 00_global_paths.md
    §1.2 "Cancels").
  - *Pending approval requests* (+ approval/denial files, and every request decided in the last 7
    days): `request_id`, `action_id`, `system`, `state`/`decision`, **`decided_via`** (`signed` |
    `card`) and **`card_written_by_agent`** (bool, from the recorded card answer, 02_act.md
    §2.11; R52), `urgency`, the money amount and unit, `created_at`/`expires`/`signed_at` — so the
    operator can tell a card denial (possibly agent-written) from his own GTMApprover Deny.
    **Recorded deviation from plan §20.8 (pending ratification, `requests/07_notices_schedules.md`
    R38):** plan §20.8 lists each `$` proposal on `GTM_Operator.html` "with current metrics,
    best-practice source, expected effect, risk, reversal". The page renders **none** of those five
    `money_brief` fields (nor does the E4 mirror-card body), because they are session- or
    seat-written free text — untrusted, and on a hipaa pack possibly PHI-bearing — and the Desktop
    page sits outside every purge. The one place the brief is shown is **GTMApprover** (03_schemas.md
    §3.7 display rows `metrics_summary`, `best_practice_source`, `expected_effect`, `risk`,
    `reversal`; 05_approver.md §5.1), which is also where the operator signs; the page row names the
    `request_id` so he can find it there.
  - *Recent completions* and *agent-made cancels:* `action_id`, `row_id`, `system`, `state`, the
    cancelling agent type (cancels), timestamps.
  - *Last cycle per kind:* `run_id`, `status`, timestamps. *PAUSE files:* file name,
    `created_by`, `ruling_ref`, timestamp. *Heartbeats:* label, `status`, `finished_at`, age, the §2
    row's `expected_state`, and the fixed `row needs flip: <label>` line (§7.3).
  - *Notices* (incl. the `signin_missing` section): `notice_id`, `kind`, `severity`, `system`,
    `action_id`, `request_id`, `card_id`, `hold_until`, timestamps, and `NOTICE_KIND_LABEL[kind]`
    (the fixed per-kind label table above), plus — for an `isolation_hit` notice — the
    `REFUSAL_REASON_TEXT[reason_code]` line when the code is a key. The notice's own `title` and `body`
    are rendered **only** when neither the company's nor the `origin_company`'s pack has `regulated ∋
    hipaa` **and** the notice's `created_by` ∈ `PAGE_TEXT_WRITERS` (the fixed in-process templates of
    this file, the env-cleared shell writers' fixed templates and the path-naming trust notices). A
    `session` notice renders the label and its `dedupe_key` (composed by `notices.py task` from
    grammar-checked values only); in-process notices of every other writer (`act`, `run-holds`,
    `breaker`, `G-A`, …, whose text can quote action or finding fields) render the label and ids only.
  So the Desktop file never holds OtherCompany reply or DM text, recipients, lead sources or finding
  text, because nothing on the page can carry them — not because a writer promised not to.
D tests (each falsified by removing the clause): a notice titled `<script>alert(1)</script>` from
`created_by: notices` on a non-hipaa pack renders as escaped text; the written page's CSP meta hash
matches its inline script and the policy has no `connect-src`; a completed action whose `after`
holds a marker string does not put that string in the page; **a held identity-class action on a
hipaa pack whose `after` and recipient hold marker strings keeps both markers off the page**; a
pending approval request whose description holds a marker keeps it off the page; a hipaa-pack
notice whose title and body hold a marker keeps both off the page; an `act`-written `hold` notice
whose title holds a marker on a non-hipaa pack keeps it off the page; a `runtime` notice with a
hipaa `origin_company` whose title holds a marker keeps it off the page; an `isolation_hit` notice
with `reason_code: cross_company` renders the fixed `cross_company` text and no title.

### 7.2 `run_gtm_job.sh` (WP-D; never edits `run_oversight_job.sh`)

```
run_gtm_job.sh <job-label> <company-slug|all> <run-kind> <prompt-file|-> <cadence-text> <alarm-seconds> [--slot <HHMM>]
```
- `<alarm-seconds>` is positional and always rendered by the plists from the kind's `RUN_TIMES` row
  (§7.3, the one authority; the holds job's is 900); `--slot <HHMM>` (company-local, the `cadence.inbox_checks` entry this plist was
  rendered for, §7.3) is **required for `inbox` and refused for every other kind** (IMP-21,
  00_global_paths.md §0.3). Missing, extra, or not matching `^([01][0-9]|2[0-3])[0-5][0-9]$` (checked
  at argument parsing), or — checked right after `runner_probe.py`, from its `slot_valid` — not
  equal to one of the pack's `inbox_checks` with the colon removed → `failed` heartbeat, summary
  `usage`, exit 64.
- `run-kind` ∈ `inbox daily weekly monthly monthly_load holds`. `holds` requires `all` and `-`; it
  runs no claude. **`holds` skips** `company.py resolve`, the `ST/PAUSE` check, the unsigned-caps
  check, the cycle record and the lease — `run-holds --all` applies each company's pauses itself
  (03_schemas.md §3.11) — and keeps only the test-env and `CSA_DISABLE_HOOKS` refusals, the label
  check, the interpreter check, argument parsing, the `DISABLED` check and the heartbeats. After the
  `DISABLED` check it runs, in this order, each as `GTM_HOLDS_JOB=1 python3
  /Users/x/.claude/tools/gtm/<tool> …` (the env marker is the 02_act.md §2.3
  not-GTM-session exception): (1) the **hipaa age purge** `act.py purge-untrusted --all --hipaa-only
  --age-only`; (2) `act.py run-holds --all`; (3) `notices.py push` and `notices.py render`; (3b)
  `notices.py prune` (retention, §7.1: resolved notices older than 90 days and orphaned
  `pushed.jsonl` rows); (4) the **pacing check** `act.py pacing --all` (§7.4 `ad_spend_pacing`; last,
  so a slow platform read can never delay a hold release).
  **A retention or detection failure is never green (r5).** (1) nonzero → the holds heartbeat is
  `failed` whatever run-holds returns (summary `purge <n>; ` followed by the run-holds summary) and,
  through `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN`, `notices.py write
  --company runtime --kind info --severity urgent --title "GTM hipaa retention purge failed" --body
  "act.py purge-untrusted --all --hipaa-only --age-only exited <n>; see the com.oversight.gtm.holds
  heartbeat" --dedupe-key purge_failed:all --push --created-by run_gtm_job` (deduped, so one notice
  per outage); the first holds run whose purge exits 0 resolves it (`resolve-owned --created-by
  run_gtm_job --dedupe-key purge_failed:all --resolution "purge ok"`). (4) nonzero → status
  unchanged, `; pacing exit <n>` appended, and the heartbeat carries **`consecutive_pacing_failures`**
  (prior value + 1; reset to 0 by a pacing exit 0; carried from the prior heartbeat read before the
  START stub, like every streak below); when it reaches **4** (one hour of dead detection) the runner
  writes, the same env-cleared way, `notices.py write --company runtime --kind info --severity urgent
  --title "GTM ad-spend pacing check is failing" --body "act.py pacing --all failed on <n>
  consecutive holds runs; runaway spend is not being detected between daily runs" --dedupe-key
  pacing_down:all --push --created-by run_gtm_job`, resolved (`--dedupe-key pacing_down:all
  --resolution "pacing ok"`) by the first holds run whose pacing exits 0; `heartbeat_audit.py` flags
  `consecutive_pacing_failures ≥ 4` (watchdog bullet below). D tests (each falsified by removing
  its clause): a stub purge exiting 1 with run-holds exiting 0 → heartbeat `failed`, summary starting
  `purge 1; holds ok`, one open `purge_failed:all` notice, and the next clean run resolves it; four
  consecutive holds runs with a stub pacing exiting 1 → `consecutive_pacing_failures` 1–4, one
  pushed `pacing_down:all` notice on the fourth, none earlier, and a clean fifth run resolves it and
  writes 0.
  **Hipaa age purge (plan §20.4/§20.13 30-day window; runs with no AI session;
  `requests/07_notices_schedules.md` R41 as amended by R49):** `--all --hipaa-only` iterates
  `gtm_slugs()` and acts only on packs with `regulated ∋ hipaa`; **`--age-only`** deletes exactly
  three classes by age and nothing else — `ST/untrusted/**` files older than 30 days, `drafts/`
  files older than 24 h (00_global_paths.md §1.3's hipaa drafts rule), and transcript files older
  than 30 days — and **never touches `<home>/.playwright-mcp/`** (the full purge's
  "delete `H/.playwright-mcp/` entirely", 02_act.md §2.4, is not part of `--age-only`). The holds
  job takes no company lease, so a whole-directory purge from it would delete a live session's
  Playwright output mid-run (gtm-operator's acting-as screenshots that `complete` relies on,
  in-flight snapshots, and the setup-capture file 06_connectors.md §6.6 requires to match exactly
  once); `.playwright-mcp/` is purged only by the lease holder itself (§7.6 step 4(d), inside the
  lock) and by the runner's lease-probing backstop (Order, below). Nonzero → `failed` plus the
  `purge_failed:all` notice (above; no stderr line — nothing the runner writes after START goes to
  stderr, "Log files", below). **`DISABLED` is honoured (DECIDED HERE; supersedes the earlier purge-before-`DISABLED`
  placement):** runtime CLAUDE.md §13 says `~/.claude/schedules/DISABLED` "stops everything" and
  plan §6.8 says scheduled runs don't start under it; an operator may set it precisely to freeze
  state during an incident, and an unattended deletion job running through it would destroy
  evidence. So under `DISABLED` the holds job writes `skipped-disabled` and deletes nothing.
  **Stated retention lag:** while `DISABLED` is set, OtherCompany's 30-day / 24-hour deletions do not
  run from any schedule; they resume on the first holds run after `DISABLED` is removed (the age
  test catches everything that expired meanwhile), and any interactive session the operator starts
  still purges at its own exit (§7.6 step 4(d)). The same lag applies when the holds job is
  unloaded. **This lag is a recorded deviation from plan §20.13's 30-day deletion** (OtherCompany
  transcripts and untrusted files can outlive 30 days, and hipaa `drafts/` files 24 h, while
  `DISABLED` is set or the holds job is unloaded), carried to 08_seats_wps.md Appendix B for
  ratification with R4, R39 and R52 (`requests/07_notices_schedules.md` R63). (`purge-untrusted` stays **allowed** under `DISABLED`, 03_schemas.md §3.10 — that row is
  about what act.py permits, not about a schedule running it.) D tests (each falsified by removing
  its clause): with `DISABLED` present and a 31-day-old `ST/untrusted/` file in a hipaa fixture
  pack, a `holds` run writes `skipped-disabled` and the file **remains**; after `DISABLED` is
  removed, the next `holds` run deletes it and leaves a non-hipaa pack's 31-day-old file alone; a
  fresh `<home>/.playwright-mcp/page-x.yml` in a hipaa fixture pack survives a `holds` run **with
  the fixture lease held and with it free** (the holds job never deletes it; falsified by running
  the full purge); a 25-hour-old hipaa `drafts/` file is deleted and a 23-hour-old one is kept.
  **Holds deadline (the job's alarm, 900 s, is enforced, not advisory).** launchd never overlaps a
  job with itself, so an unbounded hung holds run would silently stop every later hold release and
  the hipaa purge. The runner therefore runs steps (1)–(4) against one deadline `start + <alarm>`:
  each step is started in the background with `set -m` (its own process group) under the §7.6
  step 4(c) watchdog pattern with the **remaining** seconds (`sleep <remaining>`, marker, `kill
  -TERM -- -<pgid>`, `sleep 30`, `kill -KILL -- -<pgid>`); a step that reaches the deadline →
  heartbeat `failed` / `timeout <step>` (`<step>` ∈ `purge`, `run_holds`, `push`, `render`,
  `prune`, `pacing`), the remaining steps are skipped, exit 0. A step started with less than 30 s remaining
  is skipped and appended as `; <step> skipped: deadline`. `act.py` releases its `flock`s when the
  process dies, so a killed step leaves no lock held. D test: a stub `run-holds` that sleeps past a
  5-second test alarm → heartbeat `failed` / `timeout run_holds`, its process group gone, and the
  runner exits within alarm + 35 s (falsified by running it in the foreground). Its heartbeat
  carries `company: "all"`, `run_id: null`, `cycle_record: null`; its status follows the
  runner-helper table below (`run-holds` exit 0 → `ok`, nonzero → `failed`). **`all` is valid
  only with `holds`** (F-holds): `all` with any other kind, or `holds` with a company slug or a
  prompt file, writes a `failed` heartbeat with summary `usage` and exits **64** — a nonzero runner
  exit reserved for a misconfigured plist.
- **Home paths are read only through `python3` (TCC).** Every GTM company home is under
  `~/Desktop`, and `knowledge/oversight_install.md` records (verified by execution, 2026-09-17) that
  under launchd `~/Desktop` is TCC-protected for `/bin/bash` and `perl` but not for `python3`; a bash
  `[ -e "$ST/PAUSE" ]` would read false and the manual pause would silently fail open. So every read
  of a home path in this runner (the pack and `ST/PAUSE`; heartbeats live under `R`, which bash can read)
  goes through one `python3 <R>/tools/gtm/runner_probe.py --company <slug> --kind <run-kind>
  [--slot HHMM]` (WP-D) that prints one JSON object `{"timezone": str, "today_local": "YYYY_MM_DD",
  "is_last_weekday": bool, "paused": bool, "slot_valid": bool|null, "run_date": "YYYY_MM_DD",
  "run_id": str, "render_tz": str|null, "machine_tz": str, "tz_drift": bool, "hipaa": bool}`
  (`hipaa` = the pack has `regulated ∋ hipaa`; it selects the session output routing below) and exits 0, or
  exits 1 on any `PermissionError`/unreadable path (→ runner `failed`/`tcc`), or exits 4 when the
  computed `run_id` fails `CYCLE_ID_RE` (→ runner `failed`/`run_id_grammar`, never reported as a
  TCC fault), or exits 5 when the machine timezone cannot be resolved (→ runner
  `failed`/`machine_tz_unknown`, §7.3 "Machine timezone"); **any other exit** (2 usage, a crash, or
  0 with output that does not parse to exactly that key set) → runner `failed` / `probe <n>` (`probe
  0` for unparseable output), no session. **Timezone drift (DECIDED HERE).** The plists fix their fire times once, at render
  time, in the machine timezone of that moment (§7.3); if the Mac's timezone later changes (the
  operator travels east), every fire lands before its company-local slot, `run_date` is the
  previous occurrence, and every run would be a silent `duplicate_cycle` no-op. So every company
  plist carries `EnvironmentVariables.GTM_RENDER_TZ` = the IANA machine zone it was rendered for
  (§7.3). **The runner validates it in bash, as its own Order step immediately before
  `runner_probe.py` (Order, below; r6):** `GTM_RENDER_TZ` unset **or empty** → the runner omits
  `--render-tz` entirely; otherwise it must match `^[A-Za-z0-9_+/-]{1,64}$` (the `machine_tz`
  grammar below, named here explicitly; checked with bash `[[ "$GTM_RENDER_TZ" =~ … ]]`), else
  heartbeat `failed` / `usage`, exit 64 (a misconfigured plist), no probe run; a matching value is
  passed as `runner_probe.py … --render-tz "$GTM_RENDER_TZ"`. **`--render-tz` is optional** for the
  probe; the probe itself refuses a value failing the same regex with exit 2 (so a stray caller gets
  `failed`/`probe 2`, never a drift verdict), which the runner never passes. The probe
  reports `machine_tz` = `render_plists.machine_tz()` (the one definition, §7.3 "Machine
  timezone") and `tz_drift` = `render_tz` is absent, or differs from `machine_tz` as an IANA name
  **and** in `utcoffset()` at any **whole UTC hour** of the next 365 days (8760 samples, starting at
  the current UTC hour truncated; every DST transition in the tz database falls on a whole or half
  hour, and a half-hour-only transition shifts the offset at the next whole hour too, so hourly
  sampling finds every difference) (so `US/Mountain` vs `America/Denver` is not drift).
  `--render-tz` absent (a plist rendered before `GTM_RENDER_TZ` existed, edited by hand, or carrying
  an empty value) is drift whose `<render_tz>` renders as the literal `unknown` (the probe reports
  `render_tz: null`). `tz_drift: true` → heartbeat `failed` /
  `tz_drift <render_tz or unknown> -> <machine_tz>`, no cycle opened, no session, plus `notices.py
  write --company <slug> --kind task
  --severity urgent --title "GTM schedules for <slug> were rendered for <render_tz>; the Mac is now
  in <machine_tz>" --body "re-render and reload: python3
  /Users/x/.claude/tools/gtm/render_plists.py --company <slug>, then reload the listed
  labels" --dedupe-key tz_drift:<slug> --push --task --created-by run_gtm_job` (through `env -u
  CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN`; `<machine_tz>` matches
  `^[A-Za-z0-9_+/-]{1,64}$` by construction of `machine_tz()` and `<render_tz>` is either such a
  name or the literal `unknown`), exit 0; a later run with no drift
  resolves it (`resolve-owned --created-by run_gtm_job --dedupe-key tz_drift:<slug> --resolution "tz
  ok <run_id>"`). D test: with `TZ=America/New_York` in the probe's environment against a plist
  env `GTM_RENDER_TZ=America/Denver` → `tz_drift: true`, heartbeat `failed`/`tz_drift …`, one open
  pushed `task` notice, no session; `GTM_RENDER_TZ=America/Denver` with `TZ=America/Denver` → no
  drift and the notice resolved; falsified by removing the comparison; a plist env with no
  `GTM_RENDER_TZ` → `failed` / `tz_drift unknown -> <machine_tz>` and the notice title names
  `unknown` (falsified by treating absence as no drift); a plist env with `GTM_RENDER_TZ=''` (empty)
  → the probe is called **without** `--render-tz` and the heartbeat is `failed` / `tz_drift unknown ->
  <machine_tz>` (falsified by passing the empty string, which the probe would refuse with exit 2);
  `GTM_RENDER_TZ='a b'` → `failed`/`usage`, exit 64 and the probe stub records no call (falsified by
  moving the check into the probe); a stub probe exiting 2 → `failed`/`probe 2`. All dates are
  company-local (pack `timezone`, never the machine's) in the `YYYY_MM_DD` form of
  00_global_paths.md §0.3. `slot_valid` = whether `--slot` equals one of the pack's `inbox_checks`
  with the colon removed (`null` when no `--slot` was given, i.e. every non-inbox kind).
  **`--kind interactive [--offset-minutes <n>]`** (`n` 0–4, default 0; used only by `gtm_session.sh`,
  §7.6 steps 1 and 4(a)): the instant `I` = now truncated to the minute plus `n` minutes, in the pack
  `timezone`; `run_date` = `I`'s company-local date and `run_id` =
  `cyc_<slug>_interactive_<run_date>_<HHMM of I>` — both from the same instant, so an hour, day or
  month rollover moves them together; `slot_valid: null`, `paused` as for any kind. No sleeping:
  a retry asks for the next `n`. For `--kind interactive` the drift rule is **not computed**:
  `--render-tz` is not passed (an interactive session has no plist), `render_tz: null` and
  `tz_drift: false` always (`machine_tz` is still reported), so the absent-render-tz-is-drift rule
  applies to scheduled kinds only.
  **`--session-tool-calls <uuid>` (second mode; `gtm_session.sh` step 4(d) only).** Argv is exactly
  `runner_probe.py --session-tool-calls <uuid>`: the flag is mutually exclusive with `--company`,
  `--kind`, `--slot`, `--render-tz` and `--offset-minutes`, and `<uuid>` must be a lowercase uuid4;
  any other argv → exit 2 (usage, one stderr line, nothing on stdout). It counts the `tool_use`
  blocks of that session's transcript, located through `transcript_index` (03_schemas.md §3.16), and
  prints exactly one JSON object with exactly one key, `{"tool_calls": <int ≥ 0>|null}` (`null` when
  no transcript is found or readable), exit 0. It reads no pack and computes no time. Its exit set is
  `{0, 2}` (a crash is whatever Python returns); `gtm_session.sh` treats any nonzero exit or
  unparseable stdout as `tool_calls: null`. D tests: `--session-tool-calls <uuid> --company x` →
  exit 2; a fixture transcript with three `tool_use` blocks → `{"tool_calls": 3}`; an unknown uuid →
  `{"tool_calls": null}`, exit 0.
  **`run_date` = the scheduled fire date**, for every kind: the company-local date of the most
  recent **scheduled occurrence** of this run at or before now — the kind's `RUN_TIMES` time (for
  `inbox`, the `--slot` time) on one of the kind's **scheduled company-local days** (`RUN_TIMES`
  days: Mon–Fri for `inbox`, `daily` and `monthly_load`; `cadence.weekly_day` for `weekly`;
  `cadence.monthly_day` for `monthly`), never merely "today". A fire at 00:20 company-local for
  `--slot 1500` gets the previous weekday's date; a coalesced wake-up fire (launchd delivers fires
  missed while the Mac slept as one on wake, §7.3) gets the date of the last occurrence it stands
  for — `inbox_0900` firing Monday 08:00 after a sleeping weekend gets **Friday's** date, never a
  Saturday or Sunday id, which would be a run that was never scheduled. `is_last_weekday` is
  computed on `run_date`, not on today: a `monthly_load` fire delivered on the 1st at 08:00 for the
  12:30 occurrence of the previous month's last weekday gets that last weekday as `run_date` and
  `is_last_weekday: true`, so the month's batch load still runs (under that month's id) instead of
  being skipped as "not last weekday". `today_local` stays the company-local date now (reported,
  used by nothing that names a run). `run_id` = `cyc_<slug>_<kind>_<run_date>` (+ `_<HHMM>` for
  inbox, `HHMM` = `--slot`), already checked against `CYCLE_ID_RE` (a mismatch → exit 4, above); a fire
  whose occurrence already ran hits the duplicate-cycle no-op below. So the runner does no pack read
  and no timezone arithmetic in bash. A nonzero exit **fails closed**: heartbeat `failed`, summary
  `tcc`, no session. D tests: with `ST` made unreadable (`chmod 000`), the runner writes
  `failed`/`tcc` and never starts `gtm_session.sh` (falsified by treating the error as "not
  paused"); an inbox fire at 00:20 company-local Wednesday with `--slot 1500` prints Tuesday's
  `run_date` and a `run_id` ending `_<that date>_1500`; **a weekend wake:** `--slot 0900` fired
  Monday 08:00 company-local prints Friday's `run_date` (falsified by ignoring the scheduled days);
  **a late monthly_load:** a pack whose month ends on Friday the 30th, fired Saturday the 1st 09:00,
  prints `run_date` = the 30th and `is_last_weekday: true` (falsified by computing it on today);
  `--slot 1100` against a pack whose `inbox_checks` are `09:00`/`15:00` prints `slot_valid: false`.
- **Interpreter pin (r6; applies `requests/05_approver.md` R59, which replaces R43's `__PY_DIR__`
  half; 05_approver.md §5.5 "Interpreter pin"; 02_act.md §2.1 "Interpreter" item (3) is asked to
  match in the same change, `requests/07_notices_schedules.md` R63).** `PY` =
  `gtm_env.TRUSTED_PYTHON` = the literal `/opt/homebrew/opt/python@3.13/bin/python3.13` (the
  Homebrew `opt` link, which survives `brew upgrade` within 3.13). **Notation rule for this whole
  file:** wherever a command form of this file shows `python3` in command position — a runner or
  `gtm_session.sh` step, a `notices.py`/`cycle.py`/`act.py`/`runner_probe.py`/`run_log_sink.py` call,
  the one literal caps command below, the §7.5 literal command form, the §7.6 step 5 `Bash(…)`
  rules, a fixed card or notice text telling the operator what to type — it is **written and
  rendered as `PY`, the full literal path**, never a bare `python3`: `run_gtm_job.sh` and
  `gtm_session.sh` each assign `PY=/opt/homebrew/opt/python@3.13/bin/python3.13` once, as the only
  interpreter token they use, and K writes the prompt files and renders the allowlist with the
  literal. A bare `python3` resolves through `PATH`, so it is only as good as that `PATH`, and no
  `PATH` value can pin it: `/opt/homebrew/bin/python3` is a symlink into whichever `python@3.x` Cellar
  Homebrew last linked (measured on this machine: `python@3.14`, not the 3.13 `TRUSTED_PYTHON`), a
  `realpath` of it names a Cellar directory that `brew cleanup` deletes, and
  `dirname(TRUSTED_PYTHON)` holds only `python3.13` (no `python3`, R59). So every GTM plist's
  `EnvironmentVariables.PATH` is exactly `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`
  — a **fallback for the non-Python tools** the scripts call (`uuidgen`, `lockf`, `mktemp`, `date`),
  **never relied on for Python**; there is no `__PY_DIR__` placeholder. The runner's step after the
  label check (Order, below) is `"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))'`;
  nonzero — including `PY` missing or not executable (bash exit 126/127) → heartbeat `failed`, summary
  `python_too_old`, exit 64 (a misconfigured machine). `render_plists.py` is itself run as `PY
  …/render_plists.py` and **refuses** (exit 3, naming both paths, nothing written) unless
  `os.path.realpath(sys.executable) == os.path.realpath(gtm_env.TRUSTED_PYTHON)` and
  `sys.version_info >= (3, 11)`, so a venv or pyenv shim can never render the plists. **TCC:** the
  2026-09-17 finding (above, `knowledge/oversight_install.md`) was verified for
  `/opt/homebrew/bin/python3`, whose realpath is a **different** Cellar interpreter; it is therefore
  **UNVERIFIED for `PY`** (whose realpath today is
  `/opt/homebrew/Cellar/python@3.13/3.13.14_1/Frameworks/Python.framework/Versions/3.13/bin/python3.13`).
  Probe f re-records `~/Desktop` read access under launchd **for `PY`'s realpath**, and until it does
  the TCC fail-closed rule above (`runner_probe.py` exit 1 → `failed`/`tcc`) is what catches a
  denial; a `brew upgrade` that moves `PY`'s realpath to a new Cellar directory re-opens the question
  the same way (the next run's `failed`/`tcc` heartbeat surfaces it). K tests (each falsified by
  reintroducing a bare `python3`): **every interpreter token** in `run_gtm_job.sh`, `gtm_session.sh`,
  every rendered plist, every prompt file and every rendered `Bash(…)` rule **equals
  `gtm_env.TRUSTED_PYTHON`** (a regex over the files for `python3` in command position finds none
  outside that literal); the rendered `PATH` equals the fixed string above; `render_plists.py` run
  under any other interpreter (or with `sys.executable` patched to `…/pyenv/shims/python3`) → exit 3
  and no file written. The
  unsigned-caps check has **one literal command form, used verbatim by both call sites** (this
  runner and `gtm_session.sh` step 1, §7.6): `"$PY" -I -S -B
  /Users/x/.claude/tools/gtm/ai_budget.py caps --company <slug> --check`
  (DECIDED (wave1e): no `-X pycache_prefix` token — with none set, 05_approver.md §5.5 step 0 (1)
  re-execs under a fresh `gtm_pyc_` prefix directly under `gtm_tmp_root()` and cleans it up; the old
  fixed `S/pycache` prefix is refused by step 0 (3) and was withdrawn by R41 (b)) (`"$PY"` = the
  pinned interpreter, notation rule above; wherever this file repeats the form as `python3 -I -S …`
  it means exactly this) (05_approver.md's
  request R14; absolute paths, no `$HOME`, so it is identical under launchd and in a terminal). If
  04_hooks.md §4.6 later has `ai_budget.py` re-exec itself under those flags, the flags stay in both
  call sites anyway (harmless) — the two never diverge. K test: the byte string of the command in
  `run_gtm_job.sh` equals the one in `gtm_session.sh` (with the slug variable name normalised), and
  both spell the interpreter `"$PY"`, whose one assignment in each script is the `PY` literal. D test (the harness runs a copy of the script whose one `PY=`
  assignment names a stub interpreter reporting 3.9; the shipped file's assignment is the K-tested
  literal): → `failed`/`python_too_old`, exit 64, no session; a `PY=` naming a missing file → the
  same.
- **GTM-company check first.** Every entry point that takes a slug — this runner, `gtm_session.sh`
  (§7.6 step 1) and `render_plists.py` (§7.3) — checks `slug ∈ company.gtm_slugs()`
  (00_global_paths.md §0.1 — never `registered_slugs()`, which returns `agency`; `gtm_slugs()`
  itself never stats before its Agency exclusion) **before** any `company.py
  resolve`, `company.load_pack` or home-path stat, so no GTM entry point ever stats into the Agency
  tree. The shell entry points run `python3 /Users/x/.claude/tools/gtm/company.py
  is-gtm <slug>` (exit 0 member, 13 not a GTM company; `requests/07_notices_schedules.md` R22);
  the renderer calls `gtm_slugs()` in-process. Not a member → runner heartbeat `failed`/`company`,
  `gtm_session.sh` exit 13, renderer exit 13. Test (D and K): `agency` is refused by all three and
  the no-Agency-touch oracle (00_global_paths.md §0.1) records nothing. **Neither exists yet:**
  `company.py` today has only `registered_slugs()` (which includes Agency) and no `is-gtm` CLI, its
  `resolve` exits 1 (not 13), and `harvest_tool_trail._registered_homes()` still calls
  `registered_slugs()`. So R22 (`gtm_slugs()` + `is-gtm`) and R16 (harvest on `gtm_slugs()`, plus its
  session-env positional-path refusal) are **hard prerequisites** in the WP ordering: WP-D's runner,
  WP-K's `gtm_session.sh`, renderer and weekly prompt ship only after both have landed with their
  tests (`requests/07_notices_schedules.md` R46 to 08_seats_wps.md §9). The **scheduled prompt
  files** have further hard prerequisites, and the runner's holds job and lease-probing backstop
  have their own (R41, R49, R56, R62 — every act.py/cycle.py/notices.py form the runner itself
  calls); both lists are given once, in §7.6 step 5.
- Order: refuse test env (00_global_paths.md §1.4; **exit 64 with no heartbeat** — the heartbeat
  directory is not trusted in a test env) → **refuse disabled hooks:** `CSA_DISABLE_HOOKS` non-empty
  and not `0` in the runner's environment → one stderr line `run_gtm_job: refusing to run with
  CSA_DISABLE_HOOKS set (every GTM hook would allow)`, **exit 64 with no heartbeat** (same class as
  a test env: a misconfigured plist or shell; under it every GTM hook returns allow before parsing,
  `_lib.disabled()`, so G-A's `playwright-gtm` default-deny and G-W's write scope vanish, 04_hooks.md
  §4.1) — `holds` included. **This predicate is deliberately wider than the real kill-switch:**
  `_lib.disabled()`, `bash_gate.sh` and `agent_budget` treat only the exact value `"1"` as off, so a
  value such as `"true"` leaves the hooks on, and the runner refuses it anyway — a plist or shell
  carrying any non-`0` value is misconfigured either way, and refusing costs nothing
  → **label check** (`$1`, taken raw before any other parsing: empty or not matching
  `^com\.oversight\.gtm\.[a-z0-9_.-]+$` → one stderr line `run_gtm_job: bad or missing job label`,
  **exit 64 with no heartbeat**, since there is no label to name the heartbeat file; `holds`
  included) → interpreter check (above; `holds` included) → **parse the remaining arguments**
  (arity, `<run-kind>` in the kind set, `--slot` presence and regex per kind, `all` only with
  `holds`, `holds` only with `all` and `-`, **`-` as the prompt only with `holds`** — `-` with any
  other kind is a usage error, `<alarm-seconds>` a positive integer; any failure → heartbeat
  `failed`, summary `usage`, exit 64; `holds` included) → `DISABLED` check (heartbeat
  `skipped-disabled`, exit 0; `holds` included — nothing is purged under `DISABLED`, above) →
  `holds` only: read its own prior heartbeat's `consecutive_pacing_failures` (missing or unreadable →
  0), then steps (1)–(4) of the holds job under its deadline (above), then its END heartbeat
  → **read the prior heartbeat** of this label (its `status` and `consecutive_*_skips`, held in
  memory and also written into the START stub as `prior_status`/`prior_streak`; the skip heartbeats
  below compute their streak from this carried value, never from the file on disk, which by then is
  this run's own START stub) → START heartbeat → GTM-company check (above; fail → `failed`/`company`)
  → `company.py resolve` (exit 13 → heartbeat `failed`, summary `company`; exit 1 with `error.code`
  `home_unreadable` — a `PermissionError` on the pack path, R22 as amended by R51 → `failed`/`tcc`;
  any other failure → `failed`/`company`) → **render-tz check** (bash; "Timezone drift", above:
  unset or empty → no `--render-tz`; else the explicit regex `^[A-Za-z0-9_+/-]{1,64}$`, failing →
  heartbeat `failed` / `usage`, exit 64, no probe) → `runner_probe.py` (exit 1 → `failed`/`tcc`, exit 4 →
  `failed`/`run_id_grammar`, exit 5 → `failed`/`machine_tz_unknown`, above) → `tz_drift` true → `failed`/`tz_drift …` plus the `tz_drift`
  task notice (above) → inbox only: `slot_valid` false → `failed`/`usage`, exit 64 → `monthly_load` only:
  `is_last_weekday` false (computed on the probe's `run_date`, the scheduled fire date, pack
  `timezone`, above) → heartbeat `status: "ok"`, summary
  `skipped: not last weekday`, exit 0 (launchd cannot express "last weekday", §7.3; this `ok`
  heartbeat replaces the START stub like any END heartbeat) → **`paused` (`ST/PAUSE` present):
  `monthly_load` → heartbeat `status: "skipped-paused"`, exit 0 (it only loads write batches);
  `inbox`, `daily`, `weekly` and `monthly` continue with `PAUSED=1`** and run only their reduced
  paused lists (§7.5 "Paused runs"; `monthly` keeps M1, M3, M4 and M5 — local or read-only — and
  skips only M2's director dispatch)
  (F17 as corrected here: plan §6.8 lets a manual `PAUSE` block T1+ actions and write
  tickets while "T0 reads + read tickets; lead-append" stay allowed, and only `DISABLED` stops
  scheduled starts; stopping inbox runs too would leave leads unlogged, against plan §5 — and an
  isolation hit with no system writes a manual `ST/PAUSE` by itself, 02_act.md §2.9 — so a paused
  company's inbox run still captures leads; and skipping every daily and weekly run for the length
  of a pause would drop the weekly backup (plan §3.2), the harvest/audit that detects outside
  changes (most needed while paused) and the daily trust check, all of which are local or read-only;
  03_schemas.md §3.10's PAUSE row is corrected to match, `requests/07_notices_schedules.md` R12 as
  amended by R23) → **unsigned-caps check (F6; every non-`holds` kind):** the one literal command
  form above (`python3 -I -S -B /Users/x/.claude/tools/gtm/ai_budget.py
  caps --company <slug> --check`). The predicate lives in that
  one flag (`requests/07_notices_schedules.md` R13 to 04_hooks.md §4.6, as amended by R32) so this
  runner and `gtm_session.sh` step 1 (§7.6) cannot drift apart. `caps` without `--check` prints
  exactly the `effective_ai_caps(company, now)` object of 04_hooks.md §4.6 — `{"opus": {"usd",
  "source", "forged"}, "sonnet": {…}}` (IMP-19). `--check` prints one JSON object `{"pass": bool,
  "reason": null|"unsigned"|"forged"|"malformed", "zero_cap": bool, "zero_cap_enforced": bool,
  "report_only_signed": bool}` (the five keys 04_hooks.md §4.6 now prints — `report_only_signed`
  **landed** with R34, `requests/04_hooks.md` R40) and exits 0 when `pass` is true, 77 otherwise. A bucket **passes** only when its `source` starts with
  `signed:` **and** its `forged` is `false`; `pass` is true only when both buckets pass. Any other
  bucket (`company_json`/`report_only` — the §20.6 AI-spend sign-off has not happened — or a forged
  bucket, whatever its `source`) fails. `zero_cap` = some passing bucket has `usd == "0.00"`;
  `zero_cap_enforced` = this `ai_budget.py` enforces `"0.00"` as a zero cap (R32; a constant `true`
  in the version that implements R32, absent before it). **The runner proceeds only when** `--check`
  exits 0, its output is one JSON object in which **the four keys `pass`, `reason`, `zero_cap`,
  `zero_cap_enforced` are present and well-typed** (`pass`/`zero_cap`/`zero_cap_enforced` booleans,
  `reason` null or one of the three strings; **extra keys are ignored**, so the five-key output
  passes), `pass` is true, and (`zero_cap` is false **or** `zero_cap_enforced` is true); it reads
  `report_only_signed` only to annotate (a missing or non-boolean value is read as `false`). Anything else — exit 77, 1 or a crash, unparseable output or a
  missing key (an `ai_budget.py` older than R13/R32 prints none of these keys, so it fails closed), or
  a zero cap not yet enforced — → heartbeat `status: "skipped-unsigned-caps"` + `notices.py write
  --company <slug> --kind budget --severity urgent --title "GTM run skipped: AI-spend caps not
  signed" --body "<fixed body by reason>" --dedupe-key unsigned-caps:<slug> --push --created-by
  run_gtm_job` (through `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN`, §7.1
  CLI rules, `write_in_session`), exit 0, where the fixed body is: `unsigned` → `sign the gtm_ai.weekly_cap_edit
  request(s) in GTMApprover`; `forged` → `the AI-cap approval records failed verification; see the
  open trust notice`; a zero cap not enforced → `a signed 0.00 AI cap is not yet enforced as a zero
  cap by this ai_budget.py (requests R32); scheduled runs stay off until it is`; anything else →
  `ai_budget.py caps --check failed (exit <n>)` — so a loaded schedule can never run with
  operator-unsigned, editable, report-only-by-default or forged AI caps, nor under a signed `0.00`
  that the hooks would read as unlimited. When the runner proceeds it resolves any open
  `unsigned-caps:<slug>` notice (`env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN
  python3 <R>/tools/gtm/notices.py resolve-owned --company <slug> --dedupe-key unsigned-caps:<slug>
  --resolution "caps signed <run_id>" --created-by run_gtm_job`, §7.1), so the next time the caps go
  bad a new notice and a new push are made.
  **A signed `"0.00"` is a zero cap (DECIDED HERE; supersedes the earlier "no cap — report only"
  reading, which reversed plan §20.13's "a pause is amount 0" and 03_schemas.md §3.7's
  `new_absolute_value` `"0.00"` = pause/stop/remove).** An operator who signs `0.00` to stop
  department AI spend (plan §20.6 counts that spend as `$`) gets exactly that: **budget state from
  the first dispatch** — every GTM dispatch denied except the plan §6.8 reserved lead-capture
  allowance, the same rule as budget state today (04_hooks.md §4.6) — never unlimited spend.
  04_hooks.md §4.6 must read it the same way in the same change (`requests/07_notices_schedules.md`
  R32; its current "`0.00` = report only" sentence is what R32 replaces), the approver dialog shows it
  as a zero cap, never as "no cap" (R33, superseding R24), and the ship-ordering rule above keeps
  every scheduled run off until R32 has landed. A run that proceeds under a signed zero cap appends
  `; caps: zero (budget state; lead capture only)` to its END heartbeat summary so the state stays
  visible. **Report-only after sign-off**, if the operator wants it, is its own signed value, never
  `0.00`: a `gtm_ai.weekly_cap_edit` request with `new_absolute_value: null` and `unit:
  "report_only"` (both inside the signed payload, so the 12-key payload set is unchanged; a fourth
  case of 03_schemas.md §3.7's null rule), shown in GTMApprover as `NO CAP — report only, unlimited
  AI spend`, and read by `effective_ai_caps` as `source: "signed:<request_id>"`, `usd: null`, a
  distinct passing bucket that `--check` reports as `report_only_signed: true`, and a run that
  proceeds with `report_only_signed: true` appends `; caps: report only (signed)` to its END summary
  (R34 to 03_schemas.md §3.4.4/§3.7, 05_approver.md, 04_hooks.md §4.6; 04's half has landed, the
  03/05 halves are still requests — until a signed report-only request can exist, `report_only_signed`
  is always `false` and an unsigned `report_only` bucket fails `--check` as above). D tests (each
  falsified by removing its clause): the real five-key output `{"pass": true, "reason": null,
  "zero_cap": false, "zero_cap_enforced": true, "report_only_signed": false}` → the session starts
  (falsified by an exact-key-set parse); the same with `report_only_signed: true` → the END summary
  carries `caps: report only (signed)`; a
  signed `"0.00"` bucket with `zero_cap_enforced` absent → `skipped-unsigned-caps` with the zero-cap
  body and no session; with `zero_cap_enforced: true` → the session starts, the END summary carries
  `caps: zero`, and (B2, with R32) a fixture non-inbox `gtm-analyst` dispatch in that run is denied
  while the reserved inbox lead-capture dispatch is allowed; a `--check` stub printing the pre-R13
  shape (no `pass` key) → `skipped-unsigned-caps`.
  → `run_id` = the probe's `run_id` (`cyc_<slug>_<kind>_<run_date>` (+ `_<HHMM>` for inbox, per 00_global_paths.md §0.3:
  `HHMM` = the `--slot` argument — the slot the firing plist was rendered for, **never computed
  from the clock**, so a late fire can never take a later slot's id — and its date = `run_date`, the
  scheduled fire date defined above for every kind (a late fire after company-local midnight, or a
  coalesced wake-up fire, keeps its occurrence's date); always the pack `timezone`, never the
  machine's) — computed by `runner_probe.py`, above,
  **once, before any lease wait**, already checked against `CYCLE_ID_RE`) → `SESSION=$(uuidgen |
  tr A-Z a-z)` → `cycle.py open --cycle <run_id> --company <slug> --trigger schedule --session
  $SESSION` (I3; **exit 3 with `error.code == "duplicate_cycle"`** — the distinct code 03_schemas.md
  §3.12 gives a duplicate open, `requests/07_notices_schedules.md` R62 — → heartbeat `status: "ok"`,
  summary `skipped: duplicate_cycle <run_id>`, exit 0; **any other exit 3** (an id/company/trigger
  mismatch, `bad_cycle_id_hhmm`, `test_mode_real_state`, a missing or unparseable `error.code`) →
  `failed` / `cycle_open 3:<code or unknown>`, no session, because a misconfigured run must never
  read as a healthy no-op. A duplicate means that slot has already run and its own cycle record
  carries its outcome, so a late or coalesced launchd fire that lands on an already-run slot is a no-op, never a `failed`
  heartbeat; IMP-21; the heartbeat carries the streak counter `consecutive_duplicate_skips`, below,
  so a schedule whose every fire lands on an already-run record is flagged, not silent) →
  **session-script check** (bash `[ -f … ] && [ -r … ]` on `/Users/x/.claude/scripts/gtm_session.sh`,
  which lives under `R` and is bash-readable under launchd; missing or unreadable → heartbeat
  `failed` / `internal session_script_missing`, `cycle.py close --cycle <run_id> --status failed
  --if-running`, no session — so bash's own 127 for a missing script is never misread as a `claude`
  exit) →
  `exec`-free call of `/bin/bash /Users/x/.claude/scripts/gtm_session.sh <slug> --print
  <prompt-file> --run <run_id> --session-id $SESSION --model sonnet --scheduled --alarm <alarm>
  [--paused]` (`--paused` exactly when `PAUSED=1`: `inbox`, `daily`, `weekly` or `monthly`), with
  `GTM_SESSION_TOKEN_FILE=/Users/x/.claude/.gtm_state/session_tokens/$SESSION.token` in its
  environment. **Exit-64 token capture (one method for every pack; r5).** Before the call the runner
  runs `mkdir -p -m 0700 /Users/x/.claude/.gtm_state/session_tokens` and removes any file
  at that path; `gtm_session.sh`, on every exit-64 refusal (§7.6 step 1), writes exactly one line
  `<token>` to `$GTM_SESSION_TOKEN_FILE` — only when the variable's value matches
  `^/Users/x/\.claude/\.gtm_state/session_tokens/[0-9a-f-]{36}\.token$`, else it writes
  nothing there — besides its one stderr line. After a session exit 64 the runner reads the file
  with `IFS= read -r TOKEN < "$FILE"` (`R` is bash-readable under launchd), keeps `TOKEN` only when
  it is one of the six tokens (else `unknown`; a missing file → `unknown`), and deletes the file
  whatever the exit. It never parses a log. **Session output routing (plan §20.4/§20.13; DECIDED
  HERE):** `claude -p` prints its final message to stdout, and whatever the runner does not redirect
  lands in the plist's `StandardOutPath`/`StandardErrorPath` under `schedules/logs/`, which nothing
  purges. **Non-hipaa packs:** the call is `… 2>&1` — the session's and `gtm_session.sh`'s stdout
  and stderr both go to `.out.log` (the watchdog's finish proxy, "Log files" below), never to
  `.err.log`. **Hipaa packs** (the probe's `hipaa` is `true`; bash cannot read the pack): the call is
  run directly in the runner's own shell — never inside `$(…)` or a subshell, where `PIPESTATUS`
  would be lost — exactly as `set -o pipefail; /bin/bash …/gtm_session.sh … 2>&1 | python3
  /Users/x/.claude/tools/gtm/run_log_sink.py --company <slug> --run <run_id>;
  PS=("${PIPESTATUS[@]}"); SESSION_EXIT=${PS[0]}; SINK_EXIT=${PS[1]}`: the sink (WP-D; python, so
  it can write the Desktop home under launchd) writes every byte to
  `<home>/.claude/gtm/state/untrusted/run_logs/<run_id>.log` (mode 0600; `ST/untrusted/**`, so the
  holds job's 30-day age purge deletes it and backups exclude it, R49) and **prints nothing** (it
  parses no token; the token file above is the only channel). `SINK_EXIT` nonzero → append `;
  run_log exit <n>`; the output is then lost, never written to `schedules/logs/`. The plist logs of
  a hipaa company therefore hold only the runner's own fixed `RUNNER:` lines. D tests: a fake hipaa
  `claude` that prints a marker on stdout and stderr leaves no marker anywhere under
  `/Users/x/.claude/schedules/logs/` and exactly one copy in the untrusted run log; a
  stub `gtm_session.sh` printing `gtm_session: hooks_disabled …` and writing its token file, then
  exiting 64, yields `session_usage: hooks_disabled` on a hipaa fixture (falsified by removing the
  pipe) **and**, on a non-hipaa fixture, a stub printing `gtm_session: bad_paused …` then exiting 64
  yields `session_usage: bad_paused` (falsified by reading the token from `.err.log`); a stub that
  exits 64 without writing the file → `session_usage: unknown`; a token file holding `rm -rf` →
  `unknown`. (**no** outer `perl` alarm, F-alarm: an
  outer SIGALRM kills only the exec'd `gtm_session.sh` and would leave its `lockf` and `claude`
  children running orphaned, still holding the lease, while `record-session` never ran; the
  timeout now runs **inside the locked child**, §7.6 step 4) (`gtm_session.sh` records the
  session's own spend itself, §7.6 — this runner never calls `record-session`, I8) → `cycle.py sync --cycle <run_id>
  --if-running`, then `cycle.py close --cycle <run_id>
  --status completed|failed|missed --if-running` (the status per the session-exit table below:
  `missed` for exit 77, `completed` for 0, `failed` otherwise), **both run after every session exit,
  75 and 142 included** (the runner cannot read the record itself — bash cannot
  read `ST` under launchd, and `cycle.py` has no read command — so "only if still running" is the
  flag's job: `--if-running` exits 0 and changes nothing when the record's status is not `running`,
  printing `{"ok": true, "closed": false, "status": <current>}`; `requests/07_notices_schedules.md`
  R35 to 03_schemas.md §3.12. `sync --if-running` is the same rule for `sync`: on a record that is
  not `running` — closed `failed` by `gtm_session.sh` after a 142 timeout, or `missed` after a 75 —
  it exits 0 with `{"ok": true, "synced": false, "status": <current>}` and changes nothing,
  because 03 §3.12 refuses a mutator on a closed cycle (R35 as amended by R54). Until R35/R54 land
  the runner calls plain `sync`/`close` and treats exit 3 with `error.code` `closed_cycle` from
  either as the same silent no-op, appending nothing) → **lease-probing backstop purge:**
  `act.py purge-untrusted --company <slug> --playwright-only --if-lease-free` (every run kind,
  §20.13/§17 l; `gtm_session.sh` already purges inside the lock when each session exits, §7.6 step
  4(d), so this only catches a child that died before (d); it runs after `gtm_session.sh` has
  returned, i.e. after `lockf` released the lease, so another session may already hold it:
  `--if-lease-free` makes act.py take `R/.gtm_state/leases/<slug>.lock` with a non-blocking
  `fcntl.flock(LOCK_EX | LOCK_NB)` — the lock `lockf` uses — hold it for the purge, and, when it is
  held, delete nothing and print `{"ok": true, "result": {"skipped": "lease_held"}}`, exit 0; R49.
  An interactive session that tries the lease during those milliseconds gets the ordinary "lease
  held" exit 75 and can simply be restarted. D tests (falsified by dropping `--if-lease-free`): with
  a fixture lease held by another process and a fresh `<home>/.playwright-mcp/page-x.yml`, the
  backstop leaves the file and prints `skipped: lease_held`; with the lease free, the file is
  deleted) → `notices.py push` → truthful END
  heartbeat (file-on-disk check like `run_oversight_job.sh`) → exit 0.
- **Model: always `sonnet`** for the top-level session (plan §5: the weekly run is "marketing-director
  (opus) dispatched top-level from a **sonnet** session"; monthly likewise). The prompt dispatches
  `marketing-director` (pinned opus) as a direct top-level `Agent` call; the session's own tokens are
  never opus. (Former DECIDED-HERE item 41 is struck.)
- **Session exit → heartbeat (I15):**

  | `gtm_session.sh` exit | heartbeat `status` | summary / cycle |
  |---|---|---|
  | 0 | `ok` | `close --status completed --if-running` |
  | 75 (lease timeout) | `missed` | exactly `lease_held`; `cycle.py missed` was recorded by `gtm_session.sh` (§7.6); `sync --if-running` and `close --status failed --if-running` both run and are no-ops (`synced`/`closed: false`), nothing appended |
  | 77 (unsigned caps, §7.6 belt-and-braces) | `skipped-unsigned-caps` | `close --status missed --if-running` (like every post-session close) |
  | 142 (`--alarm` timeout inside the locked child, §7.6) | `failed` | exactly `timeout`; the session already ran `record-session` and closed the cycle `failed`; `sync --if-running` and `close --status failed --if-running` both run and are no-ops, nothing appended |
  | 13 (company) | `failed` | `session_company`; `close --status failed --if-running` |
  | 64 (the session's own test-env, `CSA_DISABLE_HOOKS`, interpreter or argument refusal, §7.6) | `failed` | `session_usage: <token>`, where `<token>` is read from `$GTM_SESSION_TOKEN_FILE` ("Exit-64 token capture", above; `gtm_session.sh` writes it, and prints its one `gtm_session: <token> …` stderr line, before every exit 64; `<token>` ∈ `test_env`, `hooks_disabled`, `python_too_old`, `bad_args`, `bad_session_id`, `bad_paused`; a missing file or anything else → `unknown`); `close --status failed --if-running`. **The runner itself still exits 0** — its own exit 64 is reserved for its own usage errors (above), and this is a session outcome, recorded only in the heartbeat |
  | 1 (`gtm_session.sh` internal failure, §7.6) | `failed` | `internal`; `close --status failed --if-running` |
  | 100–127 (`claude` exited nonzero, §7.6) | `failed` | `claude_exit <n − 100>` (127 = 27 or more); `close --status failed --if-running`. **Caveat (stated):** 127 is also what bash returns when `gtm_session.sh` itself fails to exec a command as its last act; the session-script check above rules out a missing script, and `gtm_session.sh` reaches its final exit only through step 4(e)'s mapping, so a 127 here is read as `claude_exit 27` and a launcher fault that nonetheless yields 127 is visible only in the run's `.out.log`/run log |
  | any other nonzero (not a documented `gtm_session.sh` exit) | `failed` | `exit <n>`; `close --status failed --if-running` |
- **Error-code extraction (DECIDED (wave1c); the one mechanism for this runner and
  `gtm_session.sh`).** Every branch on a helper's `error.code` (`cycle.py open` → `duplicate_cycle`,
  `company.py resolve` → `home_unreadable`, and any later one) reads it from the helper's **captured
  stdout only** — `OUT=$("$PY" … 2>&3)` or `… 2>/dev/null)`, whichever "Log files" (4) names for
  that call (stderr is never mixed into `OUT`) — and only when the
  exit is nonzero, as `CODE=$(printf '%s' "$OUT" | "$PY" -I -S -c "$GTM_ERRCODE_PY")`, where both
  scripts assign `GTM_ERRCODE_PY` this one literal (K test: byte-equal in the two scripts):
  `import json,re,sys` / `try:` / `  d=json.loads(sys.stdin.read().strip() or "{}")` / `  c=(d.get("error") or {}).get("code") if isinstance(d,dict) else None` /
  `except Exception:` / `  c=None` / `print(c if isinstance(c,str) and re.fullmatch(r"[a-z0-9_]{1,40}",c) else "unknown")`
  (one statement per `/`-separated line; no `jq`, which is not guaranteed on the machine). It never
  fails and always prints one token, so `unknown` is the only fallback. `company.py resolve`'s failure
  JSON is on **stdout** (R51 as amended by `requests/07_notices_schedules.md` R64; on exit 0 stdout is
  the bare home path, which is never parsed as JSON). D/K tests, one per branch, each with a stub
  helper that also writes noise (`error: …`, a traceback) to stderr: `cycle.py open` stub exit 3
  `duplicate_cycle` → the duplicate branch; exit 3 `bad_cycle_id_hhmm` → `cycle_open 3:bad_cycle_id_hhmm`;
  exit 3 with non-JSON stdout → `cycle_open 3:unknown`; `company.py resolve` stub exit 1
  `home_unreadable` → `failed`/`tcc` (runner) and exit 1 (`gtm_session.sh`) — each falsified by
  parsing stdout and stderr together.
- **Runner-helper exit handling (every helper call of this runner; no case is left to the
  implementer).** "Append" = append `; <step> exit <n>` to the heartbeat summary and keep the status
  otherwise decided; the runner's own exit stays 0 in every row.

  | helper call | exit | heartbeat `status` / summary | session |
  |---|---|---|---|
  | `uuidgen` | nonzero or empty output | `failed` / `uuidgen` | none |
  | session-script check | `gtm_session.sh` missing or unreadable | `failed` / `internal session_script_missing` (cycle closed `failed`) | none |
  | render-tz check | `GTM_RENDER_TZ` set, non-empty and failing `^[A-Za-z0-9_+/-]{1,64}$` | `failed` / `usage`, runner exit 64 | none |
  | `cycle.py open` | 0 | — | starts |
  | `cycle.py open` | 3 with `error.code` `duplicate_cycle` | `ok` / `skipped: duplicate_cycle <run_id>` (above) | none |
  | `cycle.py open` | 3 with any other or no `error.code` | `failed` / `cycle_open 3:<code or unknown>` | none |
  | `cycle.py open` | any other nonzero (1, 2, 12 lock timeout, 13) | `failed` / `cycle_open <n>` | none |
  | unsigned-caps `notices.py write` | nonzero | `skipped-unsigned-caps` (unchanged), append `notice_write` | none |
  | `notices.py resolve-owned` (caps passed) | nonzero | append `notice_resolve` | starts |
  | `cycle.py sync --if-running` / `cycle.py close --if-running` | 0 with `synced: false` / `closed: false` (the session already closed the record, or `gtm_session.sh` marked it missed) — and, before R35/R54, exit 3 `closed_cycle` | session-derived status, **nothing appended** | (after) |
  | `cycle.py sync --if-running` / `cycle.py close --if-running` | any other nonzero | session-derived status (table above), append `cycle_sync`/`cycle_close` | (after) |
  | `act.py purge-untrusted --playwright-only --if-lease-free` | 0 (incl. `skipped: lease_held`) | nothing appended | (after) |
  | `act.py purge-untrusted --playwright-only --if-lease-free` | nonzero | session-derived status, append `purge` | (after) |
  | `run_log_sink.py` (hipaa packs) | nonzero | session-derived status, append `run_log` | (after) |
  | `notices.py write` (`tz_drift`) / `resolve-owned` (`tz_drift`) | nonzero | `failed` / `tz_drift …` unchanged, append `notice_write`; resp. status unchanged, append `notice_resolve` | none / starts |
  | `notices.py push` / `notices.py render` | nonzero | status unchanged, append `push`/`render` | (after) |
  | `holds`: `act.py purge-untrusted --all --hipaa-only --age-only` | nonzero | `failed`, summary prefixed `purge <n>; `, plus the `purge_failed:all` notice (holds bullet above) | — |
  | `holds`: `notices.py write`/`resolve-owned` (`purge_failed:`/`pacing_down:`) | nonzero | status unchanged, append `notice_write`/`notice_resolve` | — |
  | `holds`: `notices.py prune` | nonzero | status unchanged, append `prune` | — |
  | `holds`: `act.py pacing --all` | nonzero | status unchanged, append `pacing`, `consecutive_pacing_failures` + 1 (the `pacing_down:all` notice at 4) | — |
  | `holds`: `act.py pacing --all` | 0 | nothing appended, `consecutive_pacing_failures: 0`, open `pacing_down:all` resolved | — |
  | `holds`: any step past the deadline | — | `failed` / `timeout <step>` (above) | — |
  | `holds`: `act.py run-holds --all` | 0 | `ok` / `holds ok` | — |
  | `holds`: `act.py run-holds --all` | nonzero (1, 3, 12, …) | `failed` / `run_holds <n>` (push and render still run, appending on failure) | — |

  D tests: one per row (each with the helper stubbed to that exit), each asserting the heartbeat
  `status`/summary of its row, falsified by removing the row's branch; in particular a session exit
  142 (the session already closed the cycle `failed`) yields a heartbeat whose summary is exactly
  `timeout` with no `cycle_sync` or `cycle_close` append (stubs: `sync`/`close --if-running` report
  `synced`/`closed: false`, and, separately, the pre-R35 stubs exit 3 `closed_cycle`), a session exit
  75 yields exactly `lease_held` under both stub sets, and a session exit 64 whose stub wrote the
  token `hooks_disabled` yields `failed` / `session_usage: hooks_disabled`, runner `exit: 0`; a stub
  `cycle.py open` exiting 3 with `error.code` `bad_cycle_id_hhmm` yields `failed` / `cycle_open
  3:bad_cycle_id_hhmm` and no session (falsified by treating every exit 3 as a duplicate).
- Heartbeat `R/schedules/heartbeats/<job-label>.json`: `heartbeat_audit.REQUIRED_KEYS`
  (`job, started_at, finished_at, exit, cadence, summary`) + `status`
  (`started|ok|failed|missed|skipped-disabled|skipped-paused|skipped-unsigned-caps`) + `company` + `run_id` +
  `cycle_record` (path) + `session_exit`. **`exit` = the runner's own exit code** (0, or 64 for a
  usage error) — never `gtm_session.sh`'s; **`session_exit`** = `gtm_session.sh`'s exit code, or
  `null` when no session was started. So a `missed` heartbeat (session exit 75) carries `exit: 0`
  and `session_exit: 75`, and `heartbeat_audit.py`'s check #8 (`lock-refused`, `exit == 75`) never
  double-flags it next to `job-missed`; the legacy "status absent + nonzero exit" branch never sees a
  GTM heartbeat because `status` is always present. **Exact objects (r5; every key always present,
  so `heartbeat_audit.check` — whose `REQUIRED_KEYS` test is not gated by `inflight` — never reports
  `missing-keys`):**
  - **START stub** (after the prior-heartbeat read): `{"job": <label>, "started_at": <UTC>,
    "finished_at": null, "exit": null, "cadence": <cadence-text>, "summary": "STARTED <run-kind>
    <company arg>", "status": "started", "company": <slug arg>, "run_id": null, "cycle_record": null,
    "session_exit": null, "prior_status": <str|null>, "prior_streak": <int|null>}`.
  - **Early-failure heartbeats** (written before or instead of START — `usage`, `skipped-disabled`,
    `python_too_old`; and the holds job's END): the same keys with `started_at` = `finished_at` = now
    (holds: its real start and finish), `exit` = the runner's exit (64 or 0), `session_exit: null`,
    `company` = the raw company argument when it matches the slug grammar or is `all`, else `null`,
    `run_id: null`, `cycle_record: null`, no `prior_*` keys (holds adds
    `consecutive_pacing_failures`).
  - **END heartbeats after START:** the START keys with `finished_at`, `exit`, `status`, `summary`,
    `session_exit` filled, `run_id` = the probe's `run_id` once known (else `null`), `cycle_record` =
    `<home>/.claude/gtm/state/cycles/<run_id>.json` once `cycle.py open` exited 0 (else `null`),
    `prior_*` dropped, plus any streak key below.
  K/D test: a stub run of each shape (START stub, `usage`, `skipped-disabled`, holds END, a session
  END) passed to `heartbeat_audit.check` yields no `missing-keys` line (falsified by dropping `exit`
  from the stub). (`heartbeat_audit` treats `status: "started"` exactly as it treats a START stub
  today; watchdog bullet below.)
  **Log files (r5; the `run_oversight_job.sh` `_wrapper_say` lesson).** `heartbeat_audit.py`
  (`_log_times`) takes the `.err.log` mtime as the START proxy and the `.out.log` mtime as the
  FINISH proxy, and flags `timestamp-divergence` beyond 300 s. So: (1) the runner prints exactly one
  fixed stdout line `RUNNER: <status> <run_id or ->` immediately before writing **every** heartbeat
  that sets `finished_at` (every END, skip and early-failure heartbeat, holds included), which
  refreshes the finish proxy; (2) the runner writes to **stderr only before its START heartbeat**
  (the test-env, `CSA_DISABLE_HOOKS` and label refusals, which write no heartbeat) **plus exactly
  one fixed line `RUNNER: START <label>`**, printed to stderr immediately after the label check
  passes, on **every** run — holds and every early failure or skip included (DECIDED (wave1c):
  launchd's append-open of `.err.log` does not change its mtime, so without a write per spawn
  every heartbeat after the first run would be flagged `timestamp-divergence`, the holds job every
  15 minutes; the csa jobs are refreshed only by an accidental TCC `getcwd` error, which §7.3's
  `WorkingDirectory` removes); every failure after START — a helper's nonzero exit, a sink or
  purge failure — goes into the heartbeat summary only, never to stderr; (3) the session's own
  output never reaches `.err.log` (non-hipaa `2>&1` to `.out.log`, hipaa to the sink; "Session
  output routing", above), so a 45–120-minute run never moves the START proxy; (4) **every helper
  call after the `RUNNER: START` line has its stderr redirected** (notices.py and the other tools
  write human text and tracebacks there): for a non-hipaa company, to the runner's stdout (`.out.log`)
  — `2>&1` on an uncaptured call, `2>&3` on a call whose stdout is captured by `$( … )`, fd 3 being
  `exec 3>&1` run once right after the START line, so a captured JSON stdout is never mixed with
  stderr ("Error-code extraction", below); for the holds job, for a hipaa company, and for every call
  before the probe has reported `hipaa`, to `/dev/null` (the heartbeat summary carries the exit code;
  a hipaa company's plist logs keep only fixed `RUNNER:` lines). `gtm_session.sh` follows the same
  rule for its own helper calls after its step 1 stderr line. D tests (each falsified by removing its clause): a hipaa fixture run and a
  non-hipaa fixture run each leave `.out.log`'s mtime within 300 s of the heartbeat's `finished_at`,
  and `heartbeat_audit.check` reports no `timestamp-divergence` for either; a fixture whose purge
  helper fails after the session writes nothing to `.err.log` after START; **wave1c (each falsified
  by removing the `RUNNER: START` line):** with a pre-existing `.err.log` whose mtime is 1 hour old,
  a holds run and a non-hipaa session run each leave `.err.log`'s mtime within 300 s of the
  heartbeat's `started_at` (the holds END heartbeat's own start time) and `heartbeat_audit.check`
  reports no `timestamp-divergence`; a fixture whose `notices.py` stub writes a traceback to
  stderr after START leaves `.err.log`'s mtime unchanged by it (falsified by dropping clause (4)). A
  prior heartbeat that is itself a `started` stub (a run that crashed before its END heartbeat) is
  "any other prior status" for the streak rule: the streak resets to 1 and the stub's own
  `prior_streak` is not carried (the crash broke the run of identical outcomes). The runner itself exits 0 (launchd) in every case
  except a usage error, a test env or `CSA_DISABLE_HOOKS` (64), recording the outcome only in the
  heartbeat. A paused inbox run that completes writes `status: "ok"` with summary `paused: lead
  capture only`; a paused daily or weekly run, `status: "ok"` with summary `paused: reduced run`. **Streak counters (IMP-16),** carried in the heartbeat itself exactly like
  `run_oversight_job.sh`'s `consecutive_quota_skips`: a `skipped-paused` heartbeat carries
  `consecutive_paused_skips` and a `skipped-unsigned-caps` heartbeat carries
  `consecutive_unsigned_caps_skips`, and an `ok` heartbeat whose summary starts `skipped:
  duplicate_cycle` carries `consecutive_duplicate_skips` — the prior heartbeat's value + 1 when the prior heartbeat of
  this label had the same status (for duplicates: the same `duplicate_cycle` summary prefix), else 1 (any other prior status, a missing or unreadable prior
  heartbeat, resets to 1; the prior heartbeat is the one read **before** this run wrote its START
  stub, carried in memory as `prior_status`/`prior_streak` — the stub itself never counts). Test (D): with no signed
  `gtm_ai` approval the runner writes `skipped-unsigned-caps` and never starts `gtm_session.sh`; with
  `ST/PAUSE` a `monthly_load` run writes `skipped-paused`; these `caps` fixtures each decide as stated (IMP-19) —
  both buckets `signed:*`/`forged: false` → the session starts; one bucket `company_json`, one
  `report_only`, one `forged: true` with a `signed:` source, and unparseable output each →
  `skipped-unsigned-caps`; three consecutive paused runs → `consecutive_paused_skips` 1, 2, 3, and
  an `ok` run in between resets it (each run writes its START stub before its skip heartbeat, so
  this test fails if the streak is read from the file after START); a second fire for an
  already-opened `run_id` → `ok` heartbeat with summary `skipped: duplicate_cycle …` and no second
  session; an inbox fire with `--slot 0900` that starts at 15:20 company-local gets
  `run_id … _0900`, never `_1500`; `inbox` without `--slot`, or `daily` with one → `failed`/`usage`,
  exit 64; `daily` with `-` as its prompt → `failed`/`usage`, exit 64 (falsified by accepting `-` for
  any kind); a missing or malformed job label → exit 64, one stderr line, no heartbeat file anywhere
  under `R/schedules/heartbeats/`; a usage error found by argument parsing writes its `failed`
  heartbeat only after the label and interpreter checks passed (a stub `PY` interpreter reporting 3.9 with
  bad arguments → `python_too_old`, not `usage`); a test env → exit 64 and no heartbeat file written; `CSA_DISABLE_HOOKS=1` → exit 64,
  one stderr line and no heartbeat file written (for `holds` too); `CSA_DISABLE_HOOKS=0` proceeds;
  a `missed` heartbeat has `exit: 0`,
  `session_exit: 75`. **Pause scope (F17):** with `ST/PAUSE`, a `monthly_load` run writes
  `skipped-paused` and starts no session; a `daily`, a `weekly` and a `monthly` run start `gtm_session.sh …
  --paused` and end `ok` / `paused: reduced run`; an `inbox` run starts `gtm_session.sh … --paused`, appends a fixture
  lead through `act.py lead-append`, mints no write ticket (no `ticket --write` row in
  `S/tickets/`), and ends `ok` / `paused: lead capture only`; falsified by skipping inbox under
  pause. `monthly_load` on a non-last weekday: START stub, then `ok`/`skipped: not last weekday`,
  computed from the pack `timezone` (a pack in `Pacific/Auckland` on a machine in
  `America/Denver` decides by the Auckland date).
- **Watchdog coverage (IMP-16; WP-D owns the edit, 08_seats_wps.md §9 D row):** `hooks/heartbeat_audit.py`
  learns the four new statuses, reading the same fields: `started` → handled exactly like today's
  START stub (summary `STARTED`, `finished_at: null`; it is what an in-progress or crashed run leaves); `missed` → flagged every time (`job-missed:
  <stem>.json (<label>) status "missed" — <summary>`; a scheduled run that never ran is what the
  watchdog exists to surface); `skipped-unsigned-caps` with `consecutive_unsigned_caps_skips ≥ 3` and
  `skipped-paused` with `consecutive_paused_skips ≥ 3` → flagged with a streak line of the same shape
  as the quota streak (`… for <n> consecutive runs — sign the gtm_ai caps` / `— the company PAUSE
  is still present; remove it or unload the schedule`); fewer than 3 in a row stay silent. **An
  `ok` heartbeat with `consecutive_duplicate_skips ≥ 3`** is flagged too (`… landed on an
  already-run cycle for <n> consecutive fires — check the machine timezone and re-render the
  plists`). This, not an age cut-off on the existing record, is the duplicate-cycle alarm
  (DECIDED HERE; the reviewer's suggested "existing record opened > 20 h ago → `missed`" rule is
  not used, because the legitimate coalesced weekend wake — `inbox_0900` firing Monday 08:00 onto
  Friday's already-run record, ~71 h old — would be flagged every week, while a schedule that is
  genuinely wrong produces a duplicate on every fire and trips the streak within a day; the
  `tz_drift` probe check, §7.2, catches the known cause directly). **A holds heartbeat with
`consecutive_pacing_failures ≥ 4`** is flagged whatever its `status` (`… ad-spend pacing check
failed for <n> consecutive holds runs — runaway spend is not being detected`), so a dead detector
never stays green (r5). Its
  docstring's sanctioned non-failure list gains `skipped-paused` and `skipped-unsigned-caps` (both
  subject to the streak rule) and states that `missed` is flagged. D tests in `hooks/tests/test_heartbeat_audit.py`: one per new branch, each falsified by removing that branch; a
  `skipped-paused` streak of 2 is not flagged; a `consecutive_duplicate_skips` of 3 is flagged and
  one of 1 (a single coalesced wake fire) is not; an `ok` holds heartbeat with
`consecutive_pacing_failures: 4` is flagged and one with 3 is not; a `missed` heartbeat as this runner writes it
  (`exit: 0`, `session_exit: 75`) yields exactly one line (`job-missed`) and no `lock-refused`.

### 7.3 Plists

Labels: `com.oversight.gtm.approver` (WP-C), `com.oversight.gtm.holds` (WP-D; `StartInterval` 900,
cadence text `every 15 min`, `WorkingDirectory` `/Users/x/.claude`, `ProgramArguments`
`… run_gtm_job.sh com.oversight.gtm.holds all holds - 'every 15 min' 900`), and per company
`com.oversight.gtm.<slug>.{daily,weekly,monthly,monthly_load}` plus **one plist per inbox slot**,
`com.oversight.gtm.<slug>.inbox_<HHMM>` (`HHMM` = the company-local `cadence.inbox_checks` entry,
e.g. `inbox_0900`, `inbox_1500`) (WP-K). **Recorded deviation from plan §20.13**, which names one
job `com.oversight.gtm.<slug>.inbox`: a single plist cannot carry a per-slot `--slot` argument, and
the runner must never derive the slot from the clock (00_global_paths.md §0.3, IMP-21), so each slot
gets its own label; the plan text is to be updated (`requests/07_notices_schedules.md` R39). Shape = the existing `com.oversight.csa.daily.plist`
(absolute paths, the fixed `PATH` template of §7.2 "Interpreter pin", `HOME` env and, on every
company plist, `GTM_RENDER_TZ` = the IANA machine zone it was rendered for, §7.2 "Timezone drift";
`StandardOutPath` = exactly `/Users/x/.claude/schedules/logs/<label>.out.log` and
`StandardErrorPath` = exactly `/Users/x/.claude/schedules/logs/<label>.err.log`, the two
paths `hooks/heartbeat_audit.py`'s timestamp-divergence check stats by label; K test: every
rendered plist's two log paths equal those strings for its own label),
`ProgramArguments` = `/bin/bash -c "exec /bin/bash /Users/x/.claude/schedules/run_gtm_job.sh
<label> <slug> <kind> <prompt> '<cadence>' <alarm> [--slot <HHMM>]"` (`--slot` on inbox plists
only; `<prompt>` = `__PROMPT_FILE__` = exactly the absolute
`/Users/x/.claude/schedules/prompts/gtm_<kind>.txt`, never a relative path — a relative
path would resolve against the company home after `gtm_session.sh`'s `cd`, §7.6 step 2; K test:
every rendered plist's prompt argument equals that absolute string), `WorkingDirectory` = `/Users/x/.claude` for every GTM plist, exactly as the holds
job (the runner reads nothing through its cwd, §7.2, and a `~/Desktop` working directory would add
a TCC-denied `getcwd` to every launchd spawn for no benefit — that error is what refreshes the
csa jobs' `.err.log` mtime today, by accident; GTM jobs refresh it on purpose with the fixed
`RUNNER: START <label>` stderr line, §7.2 "Log files"; `gtm_session.sh` itself `cd`s into the
home, §7.6 step 2, where probe f records whether `claude` started from it can read the home).

**Run times (IMP-21 completeness; DECIDED HERE).** The pack's `cadence` object carries only
`inbox_checks`, `weekly_day`, `monthly_day` and `monthly_load_day` (08_seats_wps.md Appendix C;
`company.py validate` **will** refuse unknown `cadence` keys once R29 lands — today it checks only
top-level keys, so until then the renderer's own refusal below is the only check), so the times of the other runs are fixed here, once,
as the constant `RUN_TIMES` in `tools/gtm/render_plists.py` — every time **company-local**, the
same for every pack, and imported by anything else that needs an expected run time (03_schemas.md
§3.19 `missed_runs`, `requests/07_notices_schedules.md` R14):

| kind | company-local days | time | alarm (s) | source |
|---|---|---|---|---|
| `inbox` | Mon–Fri | each `cadence.inbox_checks` entry | 2700 | plan §5 ("business days") |
| `daily` | Mon–Fri | 10:00 | 3600 | plan §5 ("business days 10:00") |
| `monthly_load` | Mon–Fri (the runner's last-weekday guard skips all but one) | 12:30 | 3600 | decided here |
| `weekly` | `cadence.weekly_day` | 07:00 | 7200 | decided here |
| `monthly` | `cadence.monthly_day` | 05:00 | 7200 | decided here |

The decided times keep the default runs' **alarms** from overlapping on the one lease (the monthly
05:00 alarm ends by 07:00, before a same-day weekly; daily 10:00's by 11:00; monthly_load 12:30's by
13:30, between OtherCompanyB's 09:00 and 15:00 inbox slots). A run can still hold the lease a little
past its alarm — its own lease wait (≤ 600 s) and the runner's steps before and after the session
come on top — which the next run's 10-minute lease wait absorbs. A pack whose own inbox slot falls inside another
run's window gets a lease wait (10 min, §7.6) and, past it, a `missed` heartbeat that the watchdog
flags (§7.2); the renderer prints a warning line naming the overlap but does not refuse.

**Renderer (WP-K):** `PY /Users/x/.claude/tools/gtm/render_plists.py --company
<slug> [--check] [--install-rows]`. It reads the pack (`company.load_pack`) and `RUN_TIMES`,
converts every entry to machine time (below), and writes
`/Users/x/.claude/schedules/com.oversight.gtm.<slug>.<kind>.plist` (inbox:
`…<slug>.inbox_<HHMM>.plist`, one per slot) from the template
`schedules/templates/gtm_company_job.plist.tmpl` (placeholders `__LABEL__ __COMPANY__
__RUN_KIND__ __PROMPT_FILE__ __CADENCE__ __ALARM__ __SLOT_ARGS__ __CALENDAR_INTERVAL__
__RENDER_TZ__` — there is no `__COMPANY_HOME__` and no `__PY_DIR__` (r6, R59: the plist names no
interpreter; the scripts it runs name `PY` by full path, §7.2 "Interpreter pin"): `WorkingDirectory` is fixed to `/Users/x/.claude`
and no plist names a home path; `__ALARM__` = the kind's `RUN_TIMES` alarm, the one authority;
`__SLOT_ARGS__` = `--slot <HHMM>` for inbox, empty otherwise; `PATH` is the fixed string of §7.2
"Interpreter pin", written literally in the template;
`__RENDER_TZ__` = `machine_tz()`, below), removing any
`com.oversight.gtm.<slug>.inbox_*.plist` whose slot is no longer in the pack and printing, one per
line to stdout, `removed <label> — unload it: launchctl unload
~/Library/LaunchAgents/<label>.plist` for each (the label may still be loaded; the renderer never
runs `launchctl`), and WP-K removes that label's `knowledge/oversight_install.md` §2 row in the same
change. `--check` writes nothing and exits 3 when any file on disk differs from what it would
render **or** when a `com.oversight.gtm.<slug>.*.plist` exists that it would not render (a stale
extra file). `--install-rows` also prints, one per line, the `knowledge/oversight_install.md` §2
rows for the company's labels, in exactly the table's column order `| <label> | unloaded |
<cadence text> | /Users/x/.claude | schedules/prompts/gtm_<kind>.txt |
GTM <kind> run for <slug> (run_gtm_job.sh) |` — `label | expected_state | StartCalendarInterval |
repo (WorkingDirectory) | prompt file | does`, the shape `heartbeat_audit.parse_job_table` reads by
position (for an inbox slot `<kind>` is `inbox`, one row per slot) — which WP-K pastes into that
file (the renderer never edits it). K tests: the printed rows, placed under the §2 header and
separator lines, parse with `heartbeat_audit.parse_job_table` to exactly the rendered `(label,
"unloaded", cadence)` triples; `--check` with an extra stale `inbox_1100` plist present exits 3;
removing a slot prints its `removed` line. Exit
codes: 0 ok, 1 internal, 2 usage, 3 refusal (timezone rule below, a cadence text that
`heartbeat_audit.cadence_seconds` cannot parse, or `--check` drift — each naming the company), 13
unknown company. Cadence texts must parse with `heartbeat_audit.cadence_seconds` (verified to
parse: `"09:00 Mon-Fri"`, `"07:00 Tue-Sat"`, `"23:00 Sun-Thu"`, `"07:00 Sat"`, `"06:10 1st of
month"`, `"10:00 daily"`, `"every 15 min"`; a combined form such as `"09:00,15:00 Mon-Fri"` does
not). Each inbox slot's plist has its own calendar and its own cadence text (`"<machine HH:MM>
<machine day set>"`), so slots that convert to different day sets need no shared text.
**`monthly_load_day: last_weekday`**: calendar entries on every company-local weekday at 12:30
(converted), cadence text `"<HH:MM> <day set>"`, and `run_gtm_job.sh`'s last-weekday guard (§7.2)
skips every other day with an `ok` heartbeat.

**Cadence inputs and output forms (DECIDED HERE; `company.py validate` checks the same values,
`requests/07_notices_schedules.md` R29).** The renderer refuses (exit 3, naming the company and the
key) any value outside these forms, before writing anything:
- `cadence.inbox_checks`: a non-empty list of distinct `HH:MM` strings matching
  `^([01][0-9]|2[0-3]):[0-5][0-9]$`, **at most 2** (DECIDED HERE, replacing "at most 6": plan §6.8
  reserves at most 2 lead-capture `gtm-analyst` dispatches per day under budget state, so a third
  slot would capture no leads for as long as budget state lasted, against plan §5's "never lets a
  lead sit unlogged"; R29 as amended by R55). K test: a pack with three slots → exit 3, no file
  written.
- `cadence.weekly_day`: one of `MON TUE WED THU FRI SAT SUN` (upper case, exactly these spellings).
- `cadence.monthly_day`: an integer 1–28 (launchd's `Day` silently skips months without a day 29–31,
  so larger values are refused, never clamped).
- `cadence.monthly_load_day`: only the string `last_weekday`.
`__CALENDAR_INTERVAL__` is always a `StartCalendarInterval` **array** of dicts using only the launchd
integer keys `Weekday` (0 = Sunday … 6 = Saturday), `Day`, `Hour`, `Minute`: a weekday-set entry
renders one dict `{Weekday, Hour, Minute}` per machine weekday; `monthly` renders one dict `{Day,
Hour, Minute}`. Cadence texts (all in machine time, each checked with
`heartbeat_audit.cadence_seconds` before writing): weekday sets `"<HH:MM> <D1>-<D2>"` for a
contiguous range (wrapping past Sunday allowed, e.g. `"23:00 Sat-Mon"`, verified to parse) or
`"<HH:MM> <D>"` for one day (`Mon Tue Wed Thu Fri Sat Sun`); monthly
`"<HH:MM> <n><suffix> of month"` (e.g. `"05:00 1st of month"`), `<suffix>` by the one ordinal rule
for `n` = 1–28: `st` for 1 and 21, `nd` for 2 and 22, `rd` for 3 and 23, `th` for every other value
(4–20 and 24–28, so `11th`, `12th`, `13th`) — the parser ignores the suffix, but the rendered text
must be stable so `--check` never reports drift for it. A day set that is neither one
day nor a contiguous range is refused (exit 3). K tests: each invalid value above → exit 3 and no
file written; `monthly_day: 31` → exit 3; a `weekly_day: SAT` pack renders `Weekday` 6.

**Machine timezone (one definition, `render_plists.machine_tz() -> ZoneInfo`, imported by
`runner_probe.py`).** `ZoneInfo(os.environ["TZ"])` when `TZ` is present and non-empty; otherwise
the IANA name taken from `os.path.realpath("/etc/localtime")` after its last `zoneinfo/`
component (e.g. `/var/db/timezone/zoneinfo/America/Denver` → `America/Denver`). Never
`datetime.now().astimezone().tzinfo`, which is a fixed offset with no DST rules. A `TZ` value that
`ZoneInfo` rejects, a `/etc/localtime` with no `zoneinfo/` component, or a name `ZoneInfo` rejects
→ the renderer exits 3 `machine_tz_unknown`, nothing written; `runner_probe.py` exits 5 → runner
heartbeat `failed` / `machine_tz_unknown`, no session. **Test injection:** `render_plists.py
--machine-tz <IANA>` overrides it and is accepted only when `GTM_TEST=1` is set (else exit 2); the K
tests below use it, and the probe tests set `TZ`. K tests: `TZ=Mars/Olympus` → exit 3
`machine_tz_unknown`; `--machine-tz` without `GTM_TEST=1` → exit 2.

**Timezones (IMP-21; DECIDED HERE).** `StartCalendarInterval` fires in the **machine's** local
timezone; every pack time (`cadence.inbox_checks`, the weekly/monthly day, and every `RUN_TIMES`
time) is **company-local** (pack `timezone`). The renderer converts each `(weekday or day-of-month,
HH:MM)` from the pack timezone to the machine timezone when it writes `__CALENDAR_INTERVAL__` (the
weekday moves with the time when the conversion crosses midnight), and the cadence text is
rendered in machine time too (it is what `heartbeat_audit` compares against the machine clock). It
**refuses** (exit 3, naming the company) when the offset between the two timezones is not the same
at every rendered entry's instant: for each rendered entry (each inbox slot and each `RUN_TIMES`
time) and each of the next 365 days, the renderer compares `utcoffset()` of the pack timezone and of
the machine timezone **at that entry's company-local wall time on that day** (not at noon or
midnight, since DST transitions happen at different hours in different zones, and a slot rendered
at 02:00–03:00 on a transition day can fall on the other side of it) and refuses if the difference
ever changes (different DST rules); and when a day-of-month entry would cross
midnight — rendering either would fire at the wrong company-local time for part of the year. For a
pack in the machine's timezone the conversion is the identity. **The plist passes its slot**
(`--slot`, company-local, unconverted), so the runner never derives it from the clock (§7.2,
00_global_paths.md §0.3); a second fire for the same `run_id` (launchd coalesces fires missed
while the Mac slept into one per plist) is an `ok` no-op. K tests (`tools/gtm/tests/test_render_plists.py`,
each rendering from a fixture pack plus `RUN_TIMES`): an `America/Denver` pack on an
`America/Denver` machine renders `inbox_0900` and `inbox_1500` plists with Mon–Fri entries at
09:00 and 15:00 and `--slot 0900`/`--slot 1500`, `daily` Mon–Fri 10:00, `monthly_load` Mon–Fri
12:30 (cadence `"12:30 Mon-Fri"`), `weekly` Saturday 07:00, `monthly` day 1 05:00, each with the
alarm of its row; a pack in `America/New_York` rendered on a machine in `America/Denver` gets
`07:00` entries for its `09:00` slot and `08:00` for daily; a `Pacific/Honolulu` pack against a DST
machine timezone is refused; an inbox slot `23:30` (Mon–Fri) in a pack two hours ahead of the
machine renders at `21:30` Mon–Fri, and in a pack two hours behind renders at `01:30` Tue–Sat
(cadence `"01:30 Tue-Sat"`); a slot whose conversion
crosses midnight gets its own shifted day set (`"00:30 Tue-Sat"`) while the pack's other slot keeps
`Mon-Fri`; removing a slot from the pack deletes its plist; `--check` after a pack edit exits 3;
**per-entry DST sampling:** an `America/Chicago` pack with an inbox slot `01:30` on an
`America/New_York` machine is refused (on the March and November transition days New York has
already changed offset at 01:30 Chicago time while Chicago has not), while the same pack with only
a `09:00` slot renders — falsified by sampling each day at noon; `monthly_day` 1, 2, 3, 11, 12, 13,
21, 22, 23 render `1st 2nd 3rd 11th 12th 13th 21st 22nd 23rd`.

**WP-K owns every GTM `knowledge/oversight_install.md` §2 row** — its own company labels plus the
approver (label, cadence `every 5 min`, plist path handed over by WP-C) and the holds job (handed
over by WP-D) — each with `expected_state: unloaded`. C and D never edit that file. In the same
change WP-K rewrites that file's §7 (today: "No `com.oversight.*` label exists for [the GTM
department] and none should … sentinel's daily heartbeat audit must not flag the absence of a GTM
job") to describe the scheduled GTM labels (`com.oversight.gtm.approver`, `.holds`, the per-company
`<slug>.{inbox_<HHMM>,daily,weekly,monthly,monthly_load}` jobs), all `expected_state: unloaded`
until the operator loads them, and deletes the "none should" sentence, so the file never
contradicts its own §2 rows. **No WP loads, symlinks, or bootstraps any plist.**
**Flipping a row when the operator loads a label (plan §20.8 "flips in the same change"; r6).**
The operator loads; an agent never does. **The flip is made by a non-GTM interactive session** — a
runtime session started with no `CLAUDE_GTM_*` variable set (not `gtm_session.sh`) — because
04_hooks.md denies a GTM session every write under `R` outside `R/projects/*/memory/`
(`R/knowledge/**` explicitly; §4.3 `gtm-write-outside-drafts` and the §4.2 shell rules) and limits
its commits to the reviewed-patch apply and the pack-scoped commit (rule n), so a GTM session can
never edit `knowledge/oversight_install.md`. **Trigger:** `GTM_Operator.html`'s heartbeat section
marks every `com.oversight.gtm.*` label whose heartbeat is fresh (`finished_at` within twice its
cadence) while its §2 row says `unloaded` with a fixed `row needs flip: <label>` line (the renderer
reads the §2 rows with `heartbeat_audit.parse_job_table`; label and state only), and sentinel's
daily heartbeat audit reports the same label as `unexpected-loaded`. The non-GTM session then edits
that row's `expected_state` to `loaded` and commits it through the ordinary review gate (runtime
CLAUDE.md §10), naming the heartbeat file and its `finished_at` in the commit message; the reverse
(a row `loaded` whose heartbeat has gone stale past the watchdog's threshold) is the watchdog's
`expected-but-unloaded` finding, handled the same way. Until then `heartbeat_audit` reports
`unexpected-loaded` for that label, which is the intended prompt. No exception to 04's GTM-scope
write rules is taken. The sign-in card's input (b) line (§7.1) states this for the approver. D test:
a fixture §2 row `unloaded` with a heartbeat 5 minutes old → the page carries `row needs flip:
<label>`; with the row `loaded`, no such line (falsified by removing the comparison); B test (with
04): a GTM-scope Edit of `R/knowledge/oversight_install.md` is denied.

### 7.4 Collectors (WP-F ↔ A1 `read-run`)

`tools/gtm/collectors/registry.json` (WP-F; the full schema, r5 — `read-run` and `act.py pacing`
refuse exit 3 `collector_registry_invalid` on any deviation, naming the key):

| key | type | required / default | meaning |
|---|---|---|---|
| `schema` | int | required, exactly `1` | registry version |
| `collectors` | object `{<name>: entry}` | required | `<name>` matches `^[a-z][a-z0-9_]{1,40}$` |
| entry `file` | string | required | `collectors/<name>.py`, relative to `tools/gtm/`, no `..` |
| entry `systems` | list of strings | required, non-empty | tier systems (03_schemas.md §3.22 names) |
| entry `network_hosts` | list of strings | required (may be `[]`) | literal hostnames (`^[a-z0-9.-]{1,253}$`) or the one sentinel `"@pack.domains"` |
| entry `timeout_s` | int 1–900 | default `300` | subprocess timeout (`read-run`); per-company budget (`act.py pacing`) |
| entry `inbox_class` | bool | default `false` | output carries reviews/messages/Q&A/comments/form submissions/leads (hipaa routing below) |
| entry `findings` | bool | default `false` | `data.findings[]` is passed through the runaway branch (below) |
| entry `args` | object `{<key>: "path"\|"text"\|"int"}` | default `{}` | the only `--arg` keys `read-run` accepts ("`--arg` values", below) |

Unknown keys (top level or entry) → invalid. The three shipped entries, verbatim:
```json
{"schema": 1, "collectors": {
 "website_snapshot": {"file": "collectors/website_snapshot.py", "systems": ["website_wordpress"], "network_hosts": ["@pack.domains"], "timeout_s": 600, "inbox_class": false, "findings": false, "args": {}},
 "speed_to_lead": {"file": "collectors/speed_to_lead.py", "systems": ["crm"], "network_hosts": [], "timeout_s": 120, "inbox_class": false, "findings": false, "args": {}},
 "ad_spend_pacing": {"file": "collectors/ad_spend_pacing.py", "systems": ["google_ads", "meta"], "network_hosts": [], "timeout_s": 120, "inbox_class": false, "findings": true, "args": {}}}}
```
`speed_to_lead` and `ad_spend_pacing` declare **no** `network_hosts`: they do no network I/O of
their own — every platform or sink read goes through the 06_connectors.md connector `read.read` on a
`build_read_ctx` context (below), whose hosts are the connector's, not a collector's — so the
fetch helper refuses any direct request they might make (the empty allowlist). (`network_hosts`
entries are literal hostnames or the one sentinel `"@pack.domains"`, which
`read-run` expands per company to the union of the pack's `brands[].domains` and
`identity_allowlist.domains`, each with and without a leading `www.`; any other `@…` token → the
registry is invalid, `read-run` exits 3.)
(WP-F also ships `speed_to_lead` — `systems: ["crm"]`, **`inbox_class: false`** — which reads the
lead sink through `build_read_ctx` and outputs `data` = `{"median_minutes_7d": number|null,
"responded": int, "unresponded": int, "by_who": {"scout": int, "owner": int, "other": int}, "response_target_minutes":
int, "unresponded_past_target": [{"lead_id": str, "received_at": "<YYYY-MM-DDTHH:MM:SSZ>"}],
"skipped_received_at": int}` from `received_at`
vs `responded_by.ts`, where `unresponded_past_target` lists every lead with no `responded_by` whose
`received_at` is older than the pack's `lead_sink.response_target_minutes` (03_schemas.md §3.14,
`requests/07_notices_schedules.md` R37), sorted by `received_at`, at most 200 entries; `median`
is null when no lead was answered in the 7 days. **`received_at` normalization (r6):** the sink's
`received_at` is "a UTC ISO timestamp" (03_schemas.md §3.14), which in practice may carry fractional
seconds or a `+00:00`/other offset; `speed_to_lead` parses each with `datetime.fromisoformat`
(a trailing `Z` accepted), converts it to UTC, truncates to whole seconds and writes it in the
pinned form `YYYY-MM-DDTHH:MM:SSZ` — the only form `notices.py task --received-at` accepts (§7.1),
so I6 never refuses a well-formed lead for its timestamp spelling. A value it cannot parse, or one
with no offset at all (naive, so its UTC instant is unknown), is dropped from every computation
(median, counts and `unresponded_past_target`) and counted in `data.skipped_received_at` (0 when
none); D7/I6 report a nonzero count as one line `speed_to_lead: <n> lead(s) with unreadable
received_at`. F test (falsified by copying the sink value through): fixture leads with
`received_at` `2026-09-27T15:04:05.123456Z`, `2026-09-27T15:04:05+00:00` and `2026-09-27T09:04:05-06:00`
each appear in `unresponded_past_target` as `2026-09-27T15:04:05Z`, and one with `yesterday` is
absent and counted `skipped_received_at: 1`. **It is `inbox_class: false` because its output
carries no lead text at all** — only counts, the three fixed responder keys, lead ids in their own 03_schemas.md §3.14 grammar and timestamps; an F test asserts
the output's keys are exactly these (the six above plus `skipped_received_at`) and that a fixture lead whose name, contact and message hold
marker strings leaves no marker in the output file. So its output lands in `ST/collectors/` for
every pack, OtherCompany included, and the daily D7 and inbox I6 steps can read it. `by_who` counts
answered leads by their `responded_by.who` (03_schemas.md §3.11/§3.14): `scout` and `owner` are
counted under their own key, and any other value — including a missing or non-string `who` — under
`"other"`; all three keys are always present (0 when none), so no free-text responder value ever
reaches the output. F test: a fixture lead with `responded_by.who: "Dr. Marker"` is counted under
`other` and the marker is not in the output. Its metric id
`speed_to_lead_median_min_7d` is seeded into every pack's `metrics.json` with the §0 program ids.
WP-F also ships **`ad_spend_pacing`** (entry above) — which reads, through the connector read
API only, the ad account's own time zone (Google Ads `customer.time_zone`; Meta ad account
`timezone_name`), each campaign's/ad set's budget, today's spend and month-to-date spend, the
account's spend today and (Meta) its `spend_cap`/`amount_spent`, where **"today" and "this month"
are the account-local day and month** (platforms report and pace spend in the account's time zone,
never the company's or the machine's). **One evaluation function, two read paths (r5):** the module
exposes `evaluate(read_fn, pack, now) -> dict` (the `data` object below), where `read_fn(system, op,
params)` performs one connector read; its collector `__main__` (the `read-run` path, inside a GTM
session) builds `read_fn` from `build_read_ctx`, and `act.py pacing` (the holds job, no GTM
session, §7.4 "Seven-day detection") imports the module **in-process** and builds `read_fn` from
`connector_dispatch._build_ctx` under the `prove_holds_job` admission it already passed — the path
`run-holds --all` uses (06_connectors.md: `connector_dispatch` builds contexts with `_build_ctx` "under whichever admission the calling act.py command already passed … the holds-job proof `prove_holds_job`") — so neither path needs a
`build_read_ctx` exception (06_connectors.md §6.3 keeps "no exception exists for any other
caller"). It outputs `data.findings[]` in the 08_seats_wps.md §8.1 `findings[]` shape, one `kind:
"runaway_spend"`, `severity: "blocker"` entry per object over its trigger, each with a stable `id`
matching **`^rs_(google_ads|meta)_(acct|cmp|adset)_[0-9]{1,32}_[0-9]{4}_[0-9]{2}_[0-9]{2}$`**
(`rs_<system>_<level>_<object id digits>_<account-local YYYY_MM_DD>`; Meta's `act_` prefix is
dropped; an id that would not match — a non-numeric object id — is not emitted and is counted in
`data.skipped`), and a `stop` = a **complete 03_schemas.md §3.2 proposal** for the stopping change,
built by the evaluation from the read alone (the object's grammar-form `target_ref` and
`account_id`, `before.value` = the read's current state with `before.evidence_ref` = this output
file, `money_brief.urgency` `"urgent"`, every `money_brief` text field and `rationale`/`undo` the
fixed text `runaway spend <finding id>: <verb>; reverse by restoring <current value>`, `why.metric_id`
the finding's `metric_id`), or `stop: null` where no single stop exists:

| trigger | level | `stop` row and `after` |
|---|---|---|
| Google campaign over its delivery ceiling (below) | `cmp` | `google_ads.campaign_pause`, `new_absolute_value` `"0.00"` (verb `pause`) |
| Meta ad set over its ceiling (ad-set budget) | `adset` | `meta.adset_pause`, `"0.00"` |
| Meta **campaign-budget (CBO)** campaign over its ceiling | `cmp` | `meta.campaign_pause`, `"0.00"` — a new stopping row, `requests/07_notices_schedules.md` R62 to 02 §2.4's `--file` set; **until R62 lands** the finding carries `stop: null` and the fixed `stop_note: "cbo_no_stop_row"` |
| account spend today > the pack's `budget.paid_daily_usd_alarm`, **Meta** | `acct` | `meta.spending_limit_edit`, `new_absolute_value` = the account's current `amount_spent` as read (verb `cap spending at current spend`), so delivery stops at once; `before.value` = the current `spend_cap` (`null` when none is set — R62 asks 02 to treat an unset cap as above any value) |
| account spend today > `budget.paid_daily_usd_alarm`, **Google** | `acct` | `stop: null`, `stop_note: "google_no_account_stop"` — Google Ads has no single account-level stop; every campaign of that account that is itself over its ceiling carries its own `cmp` finding and stop, and the note says so |

`read-run` (and `act.py pacing`) passes a `"findings": true` collector's `data.findings[]` through
the same in-process branch as `ingest-findings` (runaway notices, dedupe
`runaway_spend:collector:<collector>:<finding id>`) and **stores each finding's `stop` in the
agent-unwritable state tree**, never in a session-writable path (r5): `ST/stops/<finding id>.json`
(written atomically, mode 0600; G-W denies every GTM-scope Write/Edit under `state/**`, 04_hooks.md
§4.3, and G-B's R53 rule denies a shell redirection to it), and appends to `ST/runaway_stops.jsonl`
`{"ts", "finding_id", "stop_sha256": <sha256 hex of the stored bytes>|null, "action_id": null}`
under `ST/runaway_stops.lock` (`null` when `stop` is null). It prints `result.runaway_spend:
[{"finding_id", "has_stop": bool, "stop_note": <str|null>}]` (`requests/07_notices_schedules.md`
R42 as amended by R62). A session proposes a stored stop **only** by id: `act.py propose --company
<slug> --stop <finding_id>` (R62) reads `ST/stops/<finding id>.json`, refuses exit 3
`stop_file_modified` when its sha256 differs from the ledger entry (nothing proposed), exit 3
`stop_already_proposed` when the entry already has an `action_id`, and otherwise proposes it (the
§2.4 urgent-stop exception, `drafted_by.agent_id: "collector:<collector>"`) and stamps `action_id`.
`propose --file` of a runaway stopping row is refused in a scheduled session (`CLAUDE_GTM_RUN` of
a scheduled kind → exit 3 `stop_requires_store`, R62), so the stored-stop path is the only one there.
So neither an injected session nor a confused one can retarget, re-value or re-word the stop the
operator will sign, and the only `money_brief` text GTMApprover shows for it (R38) is the fixed
text above. **Browser-only paid systems:** for a system in the entry's `systems` whose pack account
has no API read route (its `credential_ref` is `"browser:playwright-gtm"`, 06_connectors.md §6.3 —
e.g. OtherCompanyB's Meta until an app exists, plan §8), the evaluation reads nothing for it and
records `data.skipped: [{"system": <s>, "reason": "browser_only"}]`; this is **not** a collector
error (exit 0), and D3b reports the fixed note `ad_spend_pacing: <s> browser-only — runaway
detection only by the weekly W3 analyst pull and the platform's own spend alerts`. **Stated
detection latency:** for a browser-only paid system a runaway is seen by GTM only at the next W3
(up to 7 days) or an interactive analyst read; the hourly and daily checks cover API systems only.
F/D tests (each falsified by removing its row or clause): a Meta account over
`paid_daily_usd_alarm` → one `acct` finding whose stop is `meta.spending_limit_edit` at the read
`amount_spent`; a Google account over the alarm with one campaign over its ceiling → one `acct`
finding with `stop: null`/`google_no_account_stop` plus one `cmp` finding with a stop; a Meta CBO
campaign at 1.8× → a `cmp` finding (stop per the R62 state above); a pack whose Meta account is
browser-only → `data.skipped` names it, exit 0, and no Meta finding; every emitted id matches the
regex; a session-env Write to `ST/stops/x.json` is denied (B, with 04 §4.3); editing a stored stop's
bytes then `propose --stop` → exit 3 `stop_file_modified` (falsified by removing the hash check).
**Which accounts the evaluation reads (r6; positive isolation, plan §7 and §6.3, structured target
ids included).** The operator's own Google/Meta identity reaches ad accounts of his other businesses
(e.g. Meta ad account 12864445 belongs to another business, plan §2), so `evaluate` never discovers
accounts: it iterates **only** the `pack.accounts[]` entries whose `system` is in the registry
entry's `systems` **and** whose `account_id` is in the matching `identity_allowlist` list
(`ads_customer_ids` for `google_ads`, `meta_ad_account_ids` for `meta`; both sides normalized with
the system exactly as 03_schemas.md's `identity` kind does — so `100-200-3000` matches
`1002003000`, and Meta's `act_` prefix is handled the same way `authorize` handles it), and **never lists accounts through the API** (no Google
`customers:listAccessibleCustomers`/customer-client query, no Meta `me/adaccounts` or business
listing — `read_fn` is only ever called with an explicit account id). Every object a read returns
(campaign, ad set, the account itself) must report that same account as its parent (Google:
`customer.id` / the resource name's customer segment; Meta: `account_id`); an object that does not
is dropped, never evaluated, and counted as `data.skipped: [{"system": <s>, "reason":
"account_not_in_pack", "count": <n>}]` (ids never listed, so another business's ids never reach the
output file). **Before a stop is stored** (`ST/stops/`, by `read-run` and `act.py pacing` alike), its
`account_id` — and the account segment of its `target_ref` — is re-checked against the same
allowlist list; a mismatch stores nothing, writes no runaway notice for that finding, and counts it
under `account_not_in_pack`. So a pacing misread can never push an urgent notice about, store a stop
for, or have E2b propose a change to another business's spend — which `authorize` would refuse as an
isolation hit, tripping the breaker or a company PAUSE and naming another business on the operator
page. F tests (each falsified by removing its clause): a fixture token that sees two Meta accounts,
one in the pack's `meta_ad_account_ids` and one not, both over the alarm → findings and a stored stop
for the pack account only, `data.skipped` counts the other, and the stub records no listing call; a
read returning a campaign whose parent is another account → that campaign is not evaluated; a
hand-built finding whose stop names an out-of-pack `account_id` → nothing stored in `ST/stops/`.
**Delivery ceilings (DECIDED HERE; replaces the former flat 1.5× rule, which flagged normal
delivery).** Platforms legitimately spend above the daily budget on a given day, so a flat 1.5×
test would raise urgent pushed runaway notices and urgent `$` stop requests for healthy campaigns
routinely, training the operator to ignore or reflexively sign them (plan §20.6 urgent path). The
thresholds are one constant, `PACING_DOCTRINE` in `collectors/ad_spend_pacing.py`, per system,
each entry carrying `source_url` and `verified_at`:
- `google_ads` (campaign daily budget = Google's *average daily budget*): flagged when today's
  spend **> 2.0 ×** the average daily budget (Google documents that a campaign may spend up to 2×
  its average daily budget on a given day), **or** month-to-date spend **> 30.4 ×** the average
  daily budget (the documented monthly charging limit; pro-rating is Google's own, so a
  mid-month budget change uses the current budget, stated as a known approximation).
- `meta` (ad set or campaign **daily** budget): flagged when today's spend **> 1.75 ×** the daily
  budget (Meta documents daily overdelivery of up to 75 % above a daily budget). A **lifetime**
  budget is flagged only when total spend exceeds the lifetime budget. Any other budget type →
  no per-object test (the account-level alarm still applies).
Both numbers are **to be cited in the GTM KB** (claim ids in `PACING_DOCTRINE`, `kb_freshness.py`
re-checks them at M3) before WP-F ships; the constants are pinned by F tests so a doctrine change is
a reviewed code change. F tests (each falsified by reverting to the flat rule or the company
date): Google spend 1.9× its average daily budget → no finding, 2.1× → one finding; Meta daily
budget 1.7× → none, 1.8× → one; a Google campaign at 1.5× today but month-to-date 31× → one
finding; an account in `America/Los_Angeles` read at 23:30 local on the 3rd (06:30 UTC on the 4th)
counts spend of the 3rd and names the finding `…_<YYYY>_<MM>_03`.
**Seven-day detection (DECIDED HERE).** The daily run is Mon–Fri and so are inbox runs, so a
runaway starting Friday after 10:00 would otherwise go ~72 h unseen. The evaluation uses no AI, so
the holds job (§7.2, every 15 min, seven days) runs `GTM_HOLDS_JOB=1 act.py pacing --all` (R42 as
amended by R56 and R62): for each `gtm_slugs()` company with a paid system in scope, **at most once
per UTC hour** (it skips a company whose `ST/collectors/pacing/<UTC YYYYMMDDTHH>.json` exists), it
runs `ad_spend_pacing.evaluate` **in-process** with `_build_ctx` contexts under `prove_holds_job`
(above — never `build_read_ctx`, which refuses outside a GTM session, and never a subprocess), after
the same registry, scope and host checks as `read-run`, reading only that company's pack accounts
("Which accounts the evaluation reads", above — no account listing, parent check, allowlist re-check
before storing); writes the collector-shaped output to
`ST/collectors/pacing/<UTC YYYYMMDDTHH>.json` (`run_id: "pacing"`, a reserved literal only stamped);
and applies the same in-process runaway notice (dedupe
`runaway_spend:collector:ad_spend_pacing:<finding id>`, so the hourly and daily paths never
double-notify), the same `ST/stops/` store and the same `ST/runaway_stops.jsonl` ledger.
**Signable within the hour (DECIDED (wave1c): detection alone left a Friday-16:00 runaway with
nothing the operator could approve until Monday's inbox run, ~65 h, against plan §20.6).** For each
stop it stores, `pacing` then, in-process under the same `prove_holds_job` admission and with no AI,
runs the deterministic `propose --stop <finding_id>` code (same checks, `drafted_by.agent_id:
"collector:ad_spend_pacing"`) and `authorize` on the new action, so the urgent request reaches
`awaiting_approval` and GTMApprover lists it within the hour, seven days a week; the ledger entry is
stamped with the `action_id` and `proposed_by: "holds"`. A refusal (`PAUSE.chain` exit 10, a
blocking pause exit 5, any exit 3) changes nothing further and leaves the entry for the next
session's E2b; each company entry of the printed result gains `"requests": n` (stops brought to
`awaiting_approval`). Only the E4 mirror card waits for the next session run: `runaway-stops` also
prints `result.holds_proposed: [{"finding_id", "action_id"}]` — entries stamped `proposed_by:
"holds"` whose action is `reviewed` or `awaiting_approval` with no mirror card posted yet — and E2b
re-runs `authorize` on each (idempotent on `awaiting_*`) and posts E4. That remaining mirror-card
lag (until the next inbox, daily, weekly or monthly run) is a recorded deviation from plan §20.6
pending ratification in 08 Appendix B (`requests/07_notices_schedules.md` R64); the pushed urgent
notice and the signable request are not delayed. Per company
it stops after the entry's `timeout_s` (120 s) of wall clock — checked before each connector read,
every read carrying its connector's own request timeout — and records that company `failed` /
`timeout`; the whole step still runs under the holds deadline (§7.2). It also deletes
`ST/collectors/pacing/*.json` files older than 30 days (retention; 24 files per company per day).
It prints `{"ok": bool, "result": {"companies": [{"slug", "status": "read"|"skipped_hour"|"no_paid_system"|"failed", "code": <str|null>, "findings": n}]}}`
and exits 0 when no company is `failed`, 1 otherwise (§7.2's `consecutive_pacing_failures` and
`pacing_down:all` notice make a persistent failure visible). `read-run`'s `result.runaway_spend` and
the read command `act.py runaway-stops --company <slug>` (prints `result.runaway_spend:
[{"finding_id", "has_stop", "stop_note"}]` for ledger entries with `action_id: null`) list only
unproposed stops. The next session run picks them up in **E2b** (§7.5; its trigger includes
`runaway-stops`). A company under `DISABLED` gets no pacing check (the holds job does nothing then,
§7.2); a manual `ST/PAUSE` does not stop it (T0 reads, plan §6.8). D/F tests: a Saturday fixture
spend above ceiling → one pushed `runaway_spend` notice and one stored stop from a `holds` run, no
second notice from the next hour's run, **and a pending (`awaiting_approval`) approval request for
its stop before any session runs** (falsified by removing the in-process propose/authorize), and the
Monday inbox run's `runaway-stops` lists it once, in `holds_proposed` (never in `runaway_spend`);
after E4 posts its mirror card, `runaway-stops` lists nothing and a second `propose --stop` exits 3; **L test
(the blocker this closes):** a real `run_gtm_job.sh … holds` fixture run (no GTM session, no
`CLAUDE_GTM_COMPANY`, no lease) with stubbed connector reads produces a `read` status and the
expected finding (falsified by routing the read through `build_read_ctx`, which then refuses
`not_gtm_session` and the company is `failed`); `build_read_ctx` called in that same holds context
still raises `not_gtm_session` (06's rule unchanged).
(`inbox_class: true` for any collector that returns reviews, messages, Q&A, comments, form
submissions or leads — routed to `ST/untrusted/` for hipaa packs, 02_act.md §2.4 `read-run`).
Collector CLI: `python3 <R>/tools/gtm/<file> --company <slug> --run <run_id> --out <abs path> [--arg k=v …]`;
writes `{"schema": "gtm.collector.v1", "collector", "company", "run_id", "ts", "ok", "data", "errors": []}`
to `--out`; exit 0 on success, 1 on collector error, 3 on a refused host (output still written
with `ok: false` for 1 and 3; "Declared hosts are enforced", below).
`read-run` runs it via `subprocess` with that argv only (names outside the registry → exit 3); its
`--run` is the calling session's `CLAUDE_GTM_RUN` (`read-run` has no `--run` flag of its own and
refuses exit 3 `no_run_context` when the variable is unset or fails `CYCLE_ID_RE`), and its `--out`
is `<home>/.claude/gtm/state/collectors/<run_id>/<collector>.json` (`ST/collectors/…`, 02_act.md
§2.4 `read-run`; `ST/untrusted/<unt_id>.json` instead for an `inbox_class: true` entry on a hipaa
pack) — `requests/07_notices_schedules.md` R42.
**Host refusal (collectors run as subprocesses, outside G-A, so no hook sees their traffic):**
before starting a collector, `read-run` resolves its `network_hosts` and refuses (exit 3
`collector_host_denied`, nothing run) when any host equals or is a subdomain of a `phi_denylist`
host/suffix whose `applies_to` is absent or contains the company (03_schemas.md §3.20; Open Dental
and the Agency app hosts for OtherCompany, plan §20.3), or is a `github.com` host (the
`agency-boundary` target of 04_hooks.md §4.2 rule 3b cannot be excluded by host alone). D/F test (OtherCompany fixture pack with a `phi_denylist` entry
`applies_to: ["othercompany"]`): a registry entry whose `network_hosts` names that host → exit 3 and
no subprocess started; the same entry for a pack outside `applies_to` runs; falsified by removing
the check (`requests/07_notices_schedules.md` R15 carries the matching 02_act.md `read-run` text).
**Declared hosts are enforced on the traffic, not only on the declaration (DECIDED HERE;
`requests/07_notices_schedules.md` R27).**
- *One host resolver.* `collectors/hosts.py` (WP-F) `allowed_hosts(slug, collector) -> frozenset[str]`
  expands the entry's `network_hosts` (the `@pack.domains` rule above) and is the only definition;
  `read-run` and the fetch helper both call it.
- *Literal hosts (positive allowlist, DECIDED HERE — the plan's isolation posture, plan §7.1 and
  FID-02, not a denylist).* A literal `network_hosts` entry is accepted only when it equals, or is
  a subdomain of, a host in `system_names.platform_hosts(s)` for one of the entry's own `systems`
  `s`, or a host produced by this company's `@pack.domains` expansion; anything else → `read-run`
  (and `act.py pacing`) exits 3 `collector_host_denied` with nothing run. The negative check stays
  as a second layer: an accepted host that equals, or is a subdomain of, an identity value of
  **another** pack or of `other_businesses.json` (`identity_index.json`, 00_global_paths.md §1.2)
  is still refused, because the identifier lists are known to be incomplete (card O2) and the
  positive set is what bounds an unknown third-party host. `allowed_hosts()` applies the same rule,
  so the fetch helper enforces it per request. D/F tests (each falsified by removing its layer): a
  registry entry with `systems: ["website_wordpress"]` and a literal host `tracker.example.net`
  (in neither set) → exit 3 and no subprocess started; a literal host equal to a
  `platform_hosts("google_ads")` host on a `google_ads` collector runs; the same host on a
  `website_wordpress`-only collector → exit 3.
- *Fetch helper.* Every collector does all network I/O through `collectors/_http.py` (WP-F)
  `fetch(url, *, slug, collector, method="GET", timeout=30) -> Response`, built on
  `urllib.request` with automatic redirects **off**: it follows at most 5 redirects itself and, before
  the first request and before every hop, refuses a host not in `allowed_hosts(slug, collector)` or
  matching the `phi_denylist` / `github.com` rule above, raising `CollectorHostDenied`. A collector
  catching it writes its output with `ok: false`, `errors: [{"code": "collector_host_denied", "host":
  <host>}]` and exits 3 (the collector exit set becomes 0 ok, 1 collector error, 3 host denied;
  `read-run` reports a collector's 3 as its own exit 3 `collector_host_denied`). F test: a collector
  test forbids any import of `urllib`, `http.client`, `requests` or `socket` outside `_http.py`.
  D/F test: a fixture server on an allowed host answers `302` to a `phi_denylist` host → the
  collector exits 3 and the denylisted host receives no request; falsified by enabling automatic
  redirects.
- *`--arg` values.* `read-run` accepts only `--arg` keys the registry entry lists in a new
  `"args": {"<key>": "path|text|int"}` map (any other key → exit 2). A `path` value is
  `realpath`-resolved and must lie under the company home; one under `agency_root()` or matching the
  `phi_denylist` path/ancestor rule (04_hooks.md §4.4 logic, imported, not copied) → exit 3
  `collector_arg_denied`, nothing run. D test: `--arg path=~/Desktop/OtherApp/x` and a OtherCompany
  `phi_denylist` path each → exit 3 with no subprocess started.
- *Scope.* `read-run` refuses exit 3 `collector_out_of_scope` when none of the entry's `systems`
  equals `tier_system_of(c, pack)` (03_schemas.md) for any channel `c` in `scope.channels_in_scope`
  — the normalized comparison, so generic and tier channel names both match (§7.5 W1).
A collector that needs a platform read (API credential) obtains its context in-process with
`gtmlib.connector_dispatch.build_read_ctx(slug, system, brand)` and calls the connector's
`read.read(ctx, op, params)` (06_connectors.md §6.2–6.3) — it never fetches a GSM secret itself and no credential
ever travels through argv or env (F-cli). The one other read path is `act.py pacing`, which calls
`ad_spend_pacing.evaluate` in-process with `_build_ctx` contexts under `prove_holds_job` ("Seven-day
detection", above); no collector subprocess ever runs outside a GTM session.

### 7.5 Prompts (WP-K)

`schedules/prompts/gtm_{inbox,daily,weekly,monthly,monthly_load}.txt`. `gtm_session.sh --print`
prepends: `RUN CONTEXT: company=<slug> run=<run_id> kind=<kind> session=<uuid> paused=<0|1>
start=<UTC YYYY-MM-DDTHH:MM:SSZ of session start> home=<absolute company home path> hipaa=<0|1>` (`hipaa` =
the pack has `regulated ∋ hipaa`, read by `gtm_session.sh` through `runner_probe.py`; `kind` =
`CYCLE_ID_RE.match(run_id).group("kind")`, unambiguous because slugs contain no `_`; `paused=1`
exactly when `--paused` was passed; `home` = `company.py resolve <slug>`'s home, no trailing `/`) and the
rule that every dispatch's first prompt line is the 08_seats_wps.md §8.2 tag. (`gtm_session.sh`
purges `.playwright-mcp/` when every session exits, §7.6 step 4(d), and `run_gtm_job.sh` fills the
cycle record with `cycle.py sync`, §7.2.) The plan §10 skills (args, commands, refusals,
`test_k_skills.py`) are contracted in 08_seats_wps.md §9 "Skill contracts"; `/gtm-cycle <kind>` runs
this section's checklist for that kind inside an interactive cycle.

**Literal command form (the `-p` allowlist admits nothing else, §7.6 step 5).** In the prompt
files every tool command is written out as `PY /Users/x/.claude/tools/gtm/<tool> …`,
where `PY` is the literal pinned interpreter `/opt/homebrew/opt/python@3.13/bin/python3.13` (§7.2
"Interpreter pin"; this section's `python3 …` spellings below mean exactly that)
(the trust check is the canonical top-level `approval_sig.py`, 05_approver.md's request R20 —
never `gtmlib/approvals_verify.py`, whose `__main__` only re-execs it) — K expands it when it writes the file; no `<R>`, `~`, bare `act.py` or missing `python3` ever
reaches a prompt, and no bare `python3` either. The tables below abbreviate that prefix: a cell's
`act.py queue …` means `/opt/homebrew/opt/python@3.13/bin/python3.13
/Users/x/.claude/tools/gtm/act.py queue …`.
**Who fills each placeholder (one rule, no model judgement over paths).** The prompt files carry
exactly five **run constants** — `<slug>`, `<home>`, `<run_id>`, `<session>` and `<start>` — and
`gtm_session.sh` substitutes each **literally** when it composes the `-p` text (§7.6 step 4(c)),
with the same values it writes into the RUN CONTEXT header (every one grammar-checked before use:
slug §0.3, `run_id` `CYCLE_ID_RE`, session lowercase uuid4, `start` UTC `YYYY-MM-DDTHH:MM:SSZ`, `home` an absolute
path from `company.py resolve` containing no `<`, `>`, quote, backslash, newline, space, `(`, `)` or
`*` — characters that would break an unquoted literal command or the `Write(//…/**)` permission-rule
syntax — else exit 1; every current home matches, e.g. `/Users/x/Desktop/OtherCompany_GTM`).
So every path prefix in a prompt (`--out`, `--file`, `--body-file`, Write targets, Glob patterns)
reaches the model already complete, and matches the §7.6 step 5 Write rule exactly. **Everything
else in `<…>`** (`<action_id>`, `<agent_id>`, `<analyst id>`, `<ticket_id>`, `<card_id>`,
`<request_id>`, `<lead_id>`, `<i>`, `<n>`, `<id,…>`, `<title>` and the like) is a **per-item value
the model copies verbatim from a tool's output** in this run (a printed id, a draft's JSON field,
an `Agent` result's id); the model never composes, shortens or edits a path, and never derives one
from its working directory, and never computes one (no date or time arithmetic, no `today`, no
window: every such value is computed by a tool — D6's `--completed-before-hours`, D9's
`--since-last-daily`, M1's `<run_id>`-named directory). K test (`test_k_prompts.py`): a composed fixture prompt contains none
of the five run-constant placeholders and every `<home>` occurrence became the fixture's absolute
home; in every prompt file, **no placeholder other than the five run constants occurs in a path
position** (inside a `--out`, `--file`, `--to`, `--runtime-state-to`, `--body-file`, `--title-file`
argument, a Write target or a Glob pattern) except `<action_id>` and `<request_id>` (ids copied
verbatim; no prompt passes a tool-printed path any more — stored stops are proposed by id, §7.4), and no prompt contains `~` in a
command, a `<YYYY` placeholder, or any `<start…>` placeholder other than the exact `<start>`; every occurrence of a tool name from §7.6 step 5's list in a prompt file is immediately
preceded by `/opt/homebrew/opt/python@3.13/bin/python3.13 /Users/x/.claude/tools/gtm/`
(the literal equal to `gtm_env.TRUSTED_PYTHON`, compared against the constant), and every such command, after
substitution, matches one of the `--allowedTools` `Bash(...)` patterns; a bare `act.py status` line,
D1 without the interpreter, or any command starting with a bare `python3`, fails the test.

**Mandatory steps (F-prompts; the one checklist WP-K implements).** Each prompt file contains
every step of its list, in this order, as the exact command shown (the five run constants
substituted by `gtm_session.sh`, every other `<…>` copied by the model from a tool's output in this
run — "Who fills each placeholder", above). A step whose precondition is empty (no actions, no leads, no findings) is skipped with a
one-line note in the run's final message, never silently. Steps run only as far as the dispatch
cap and pauses allow; a denied step is reported, never retried in a loop.
**Final-message rule (every pack, every prompt file, stated verbatim in each; plan §20.4/§20.13).**
The run's final message — and every other line the session prints — carries only ids (action,
request, notice, card, ticket, cycle, lead, finding, cluster ids in their own grammars), counts,
exit and error codes, system and row names, timestamps, and the fixed notes this section spells
out. It never carries lead, review, DM, reply, draft, recipient, customer or finding text, nor a
URL or detail string copied from a tool's output. The final message reaches launchd's
`StandardOutPath` for non-hipaa packs (§7.2 "Session output routing") and a persistent report for
the weekly run (W10), so this is what keeps customer text out of both. K test: each prompt file
contains the rule sentence verbatim.

**`--company` on every `act.py` command (IMP-12).** Every `act.py <subcommand>` in a prompt carries
`--company <slug>`, except `execute` and `cancel` (`company_from: action_id`) and `run-holds --all`
(holds job only, never in a prompt). For `ticket`, 02_act.md §2.4 registers a callable
`company_from`: `--read` requires `--company`, while `--write`, `--write-batch` and `--close` derive
the company from the id and refuse a given `--company` that does not match. The prompts still pass
`--company <slug>` on every `ticket` form, so a wrong-company id is refused rather than acted on in
another company.

*Every prompt (F13, F5, FID-10), in addition to its list (E0, E1 report-only, E1b, E2b, E3, E4, E6 and E7 run even in a paused run — "Paused runs", below). Lines marked **[R52]** are the recorded plan deviations of `requests/07_notices_schedules.md` R52; they are **not** in the shipped prompt files until 08_seats_wps.md Appendix B records R52's ratification, and the plan-conformant default each one replaces is stated in its row:*

| # | Step | Command(s) |
|---|---|---|
| E0 | **env canary** — the very first tool call of every run (plan §20.13 fail-closed) | Glob `/Users/x/.claude/.gtm_state/env_canary/<session>.json` (`<session>` = the RUN CONTEXT `session`). Found → continue. Absent → the GTM hooks did not see `CLAUDE_GTM_COMPANY`, so every GTM-scoped control may be open: end the run at once with the final message `env canary missing — no dispatch`, with no `Agent` call and no further tool call (E6/E7 included). The session writes nothing; `gtm_session.sh` step 4(d) writes the urgent `trust` notice after `claude` exits (§7.6). The canary is written by the GTM path gate on the first GTM-scoped PreToolUse it sees in a session — this Glob itself (04_hooks.md §4.4, `requests/07_notices_schedules.md` R25). K test: the E0 line precedes every other tool line in each prompt file, and a fixture run with no canary makes no `Agent` call |
| E1 | **chain break** — the first step after E0 | Glob `<home>/.claude/gtm/state/PAUSE.chain`; absent → skip. Present → `notices.py card-draft --company <slug> --kind chain --out <home>/.claude/gtm/drafts/card_chain.md`; `post: true` → `act.py card-post --company <slug> --card-id <card_id> --title "<title>" --file <home>/.claude/gtm/drafts/card_chain.md --subject "chain_repair <slug>"` (the `subject` of the draft JSON; without it `chain-repair` can never pass, §7.1) → (exit 0 only) `notices.py card-mark --company <slug> --card-id <card_id> --notices <notice_ids>` (`<notice_ids>` = the draft JSON's `notice_ids` array joined with `,`, no spaces; plus `--replaces <replaces>` when the draft's `replaces` is non-null); `post: false` with `denied` → one-line note "repair card <id> was answered no; asking again after 7 days"; `post: false` otherwise → read the open `chain` notice's `card_id` from `notices.py list --company <slug> --json` and run `act.py chain-repair --company <slug> --replay --card <card_id>` (exit 3 while the card is unanswered, `unclear` or denied → one-line note, not retried). While `PAUSE.chain` stays, write-policy steps below exit 10 and are reported, never retried (leads still land in the fallback, I5) |
| E1b | **record card answers** — right after E1, every kind; also in paused runs (it only records answers the operator already gave; §7.1 resolver table rows `card`/`money_card`) | (1) `notices.py list --company <slug> --status open --json` → for each open notice of kind `card` (its `action_id` is also the card id E4 posted; dedupe key `card:<action_id>`): `act.py record-external --company <slug> --kind approval --card <action_id> --action <action_id>`. What it records (02_act.md §2.5 state table, §2.11): an `awaiting_card` action → `authorized`/`refused` on "Yes" (re-checked), `denied` on "No", and its `card` notice resolved (R20); a `refused` Meta-portfolio action's informational card (E4) → answer recorded and its `card` notice resolved, the action stays `refused` (R36). **`$` requests (plan §20.8, the shipped default):** `record-external` kind (b) never applies to `$` — a `$` request is decided **only** by a signed GTMApprover approval or denial, and its E4 mirror card is informational ("approving needs Touch ID there"); E1b records nothing for it. **The control is act.py, not the prompt (r6):** until 08_seats_wps.md Appendix B records R52's ratification, `act.py record-external --kind approval` refuses exit 3 `money_card_path_struck` (nothing recorded, no notice) whenever its `--card` names a request id with an **undecided** approval request (`awaiting_approval`) — so a session that runs the command itself (the scheduled allowlist grants the `act.py record-external` prefix) still cannot decide a `$` request by card, as plan §20.8 requires (`requests/07_notices_schedules.md` R63 to 02_act.md §2.11); leaving the (2) line out of the prompts is belt-and-braces only. A2 test (run directly, not through a prompt; falsified by removing the refusal): with a pending `$` request whose mirror card is archived `"No"`, `act.py record-external --company <slug> --kind approval --card <request_id>` exits 3 `money_card_path_struck` and the request stays `awaiting_approval`; the same command with an archived `"Yes"` exits 3 the same way. **[R52] (only after ratification):** (2) `act.py queue --company <slug> --kind approval` → for each row with a non-null `request_id`: `act.py record-external --company <slug> --kind approval --card <request_id>`; a mirror card "No" on a **spend-increasing** `$` request **that has no approval record** (only an undecided request is decided by a card — R66) → the request and action `denied` (`decided_via: card`, `card_written_by_agent` recorded) plus one pushed warn `info` notice `card_deny:<request_id>`; a card "No" on a **spend-reducing** `$` request (any request whose `after.new_absolute_value` is lower than `before.value.current_absolute_value`, or a pause/stop/remove — the urgent runaway stops included) is recorded only as a re-show request (GTMApprover shows it again) and the request stays `awaiting_approval` until a signed GTMApprover decision, so a forged or mistaken "No" in the many-writer operator-input file can never kill a spend reduction; a card "No" on a request the operator has **already signed** changes nothing — the approval stands, act.py raises the `card_deny_after_approval:<request_id>` notice (§7.1 resolver table) and the page's signed-approvals block lists it; a card "Yes" never approves `$`. Outcomes, none retried within the run: exit 0 → one line `<card id>: <decision> recorded (via <result.decided_via>, written by agent: <result.card_written_by_agent>)`; exit 3 `card_unanswered` (card still open, or never posted) → counted in one summary line `<n> card(s) still unanswered`; exit 3 `card_answer_unclear` → one-line note `card <id>: answer unclear — re-answer the same card`; exit 3 `card_subject_mismatch` (e.g. a revert child's card) → one-line note `card <id>: finish in an interactive session (act.py revert step 2)`; exit 5 (a pause still blocks; the approving card stays on record and the next `authorize` after the pause lifts needs no new card) or 10 (`PAUSE.chain`) → one-line note; exit 3 `money_card_path_struck` (cannot arise from the shipped (1) line, which never names a request id) → a failed step, reported; any other nonzero → a failed step, reported. K test: every prompt file and each of the four paused lists contains the E1b (1) line with `record-external`, `--kind approval` and `--card`, and — until the ratification is recorded — **no** E1b (2) line (no `record-external … --card <request_id>`); removing (1), or adding (2) before ratification, fails the test. D/A2 end-to-end (with 02_act.md's `cards.py` fixtures): a shared-class action → `authorize` → `awaiting_card` + open `card` notice → E4's exact `card-post` → the card archived with `"Yes"` → E1b's exact command → the action is `authorized` and the `card` notice `resolved` (`resolved_by: act`); archived `"No"` → `denied`, notice resolved; still open → exit 3 `card_unanswered`, action and notice unchanged; falsified by dropping E1b (the action stays `awaiting_card`). Default-form D test: a `$` request whose mirror card is archived `"No"` stays `awaiting_approval` after a full run (falsified by adding (2)). [R52] D/A2 (each falsified by removing its branch): a spend-increasing `$` request with no approval record archived `"No"` → `denied`, `decided_via: card`, one pushed `card_deny` notice; the same request **after** a signed GTMApprover approval, archived `"No"` → no state change (still executable), no `card_deny` notice, one `card_deny_after_approval:<request_id>` `agent_cancel` notice (falsified by dropping the "no approval record" limit); a non-urgent budget **decrease** archived `"No"` → still `awaiting_approval`, no notice, `result.decision: "reshow"` |
| E2 | findings and sign-in state — after **every** dispatch whose result carries `findings[]`, and after **every** `gtm-analyst` dispatch whatever it carries | `act.py ingest-findings --company <slug> --from-agent <agent_id>` in the same run (PHI paths, runaway alerts, `signin_missing` notices and their resolution — 02_act.md §2.4) |
| E2b | **runaway-spend stop** (plan §20.6; 02_act.md "Runaway-spend producer" step 2) — right after every E2 `ingest-findings` and every D3b `read-run ad_spend_pacing` whose printed `result.runaway_spend` is non-empty, **and** once per inbox, daily, weekly and monthly run right after E1b (wave1c: weekly and monthly added, so a weekend run also picks them up): `act.py runaway-stops --company <slug>` (stops stored by the holds job's hourly pacing check, §7.4, not yet proposed, plus `holds_proposed` — stops the holds job already brought to `awaiting_approval` whose mirror card is not posted); **also in paused runs** (proposing and authorizing up to `awaiting_approval` is not a T1+ execution, which is all plan §6.8's manual PAUSE blocks; plan §20.6 requires an **urgent** `$` card for a detected runaway, so a paused company still gets a prepared, signable stop) | For each reporting seat: (a) every index `i` of that seat's `gtm-result.proposals[]` whose row is one of the runaway stopping rows (02_act.md §2.4 `propose --file` restriction, widened by R62) and whose `money_brief.urgency` is `urgent` → `act.py propose --company <slug> --from-agent <agent_id> --index <i>`; (b) for a collector's findings (D3b, and `runaway-stops`; E2 results carry none): each `runaway-stops` `result.holds_proposed` entry → `act.py authorize --company <slug> --action <action_id>` (already proposed and authorized by the holds job, §7.4; the re-run returns `awaiting_approval`) → **E4**; each `result.runaway_spend` entry with `has_stop: true` → `act.py propose --company <slug> --stop <finding_id>` (§7.4: the stop was stored under `ST/stops/` by `read-run`/`pacing` from the connector read alone and its hash recorded; the session never sees, composes or edits it, and `propose --stop` refuses a stored stop whose bytes changed, `stop_file_modified`); (c) a seat finding with no urgent stopping proposal from that seat, or a collector entry with `has_stop: false` → one-line note `runaway <finding id>: no stop proposal (<stop_note or "none">); the urgent notice is the operator's surface`; `propose` exit 3 `stop_already_proposed` → one-line note, not a failed step; `stop_file_modified` → a failed step, reported (it means state was tampered with). Then, for each action proposed: `act.py authorize --company <slug> --action <new action id>` → `awaiting_approval` (urgent request, `runaway_spend` notice) → **E4** mirror card. `propose` exit 10 (`PAUSE.chain`), `authorize` exit 5 (a blocking pause), or any other exit 3 → one-line note, not retried. E2b dispatches no agent (a stop is amount-only, `lanes_key: none`, lands `reviewed`). **Execution under a manual `ST/PAUSE` — shipped default (plan §6.8):** nothing executes under the pause; a signed stop waits `authorized` and executes in the first non-paused run's I9 (a)/D5, and if the operator stops the campaign himself meanwhile, the action is closed in an interactive session with `act.py record-external --kind owner_executed --action <action_id>` (02_act.md §2.5). **[R52] (only after ratification):** a signed, spend-reducing stop (one of the runaway stopping rows, `after.new_absolute_value` lower than the current value) executes under a manual `ST/PAUSE` **only through S1** (below: the paused inbox/daily runs' one execution step; I9 and D5 do not run in a paused run). Even then S1 does not execute it under `PAUSE.chain`, `PAUSE.trust`, `DISABLED`, `PAUSE.budget` (browser rows: a browser stop needs a gtm-operator dispatch, which budget state denies), or a breaker `PAUSE.<system>` on the stop's own system (the breaker exists because that system misbehaved; executing into it is refused like any other T1+ write there, 02_act.md §2.9) — in each of those states the operator stops the campaign himself in the platform and the prepared action is closed with `record-external --kind owner_executed` as above. K test: the E2b line names `propose --company <slug> --from-agent`, `propose --company <slug> --stop <finding_id>` and `authorize`, and no prompt file contains `stop_`, `ST/stops` or `propose --file`; A1/D test (with 02_act.md fixtures): a fixture analyst result with one `runaway_spend` finding and one urgent `google_ads.campaign_pause` proposal → after E2 and E2b the action is `awaiting_approval` with a pending request and a mirror card in the operator-input file; falsified by removing E2b (no request exists); default-form D test (paused fixture, `ST/PAUSE` present): a runaway finding produces an `awaiting_approval` request and a mirror card, and after a signed approval the next paused daily run executes nothing (falsified by adding S1) |
| E3 | **sign-in card** (§7.1 "Card drafts", every input (a)–(e)) — once per run, **paused runs included** (posting a card is not a T1+ action, and a signed-out profile breaks the T0 reads a paused run still makes, so a long pause must not leave sign-in steps un-carded), **always** (not only after a ticket-holding dispatch: inputs (b)–(e) arise without one), after the last ticket-holding dispatch and before E6 | `notices.py card-draft --company <slug> --kind signin --out <home>/.claude/gtm/drafts/card_signin.md`; `post: true` → `act.py card-post --company <slug> --card-id <card_id> --title "<title>" --file <home>/.claude/gtm/drafts/card_signin.md` → (exit 0 only) `notices.py card-mark --company <slug> --card-id <card_id> --notices <notice_ids>` (`<notice_ids>` = the draft JSON's `notice_ids` joined with `,`, no spaces) |
| E4 | every other card — **after each `act.py authorize`** (I9 (b), W6, E2b), on its printed `result.state`; nothing else posts a card | `awaiting_card` (`shared` class, 02_act.md §2.6 rule 7): Write the body `Shared-system change <action_id> needs your go-ahead (reason: <result.reason>). The block above is rendered by act.py from the action itself.` to `<home>/.claude/gtm/drafts/card_<action_id>.md` → `act.py card-post --company <slug> --card-id <action_id> --title "Approve shared-system change <action_id>?" --file <home>/.claude/gtm/drafts/card_<action_id>.md --action <action_id>`. `awaiting_approval` (the `$` mirror of 05_approver.md §5.1): Write the body `Approval request <request_id> for action <action_id> is waiting in GTMApprover; approving needs Touch ID there. This card mirrors it.` to `<home>/.claude/gtm/drafts/card_<request_id>.md` → `act.py card-post --company <slug> --card-id <request_id> --title "$ approval waiting: <request_id>" --file <home>/.claude/gtm/drafts/card_<request_id>.md --action <action_id>`. Never `--subject` by hand: `--action` sets the subject (`authorize <action_id>`, or `approval <request_id>` for an `awaiting_approval` action, 02_act.md §2.4 `card-post`), and a gating card posted without `--action` has subject `None`, which `cards.require_approved` refuses forever. Exit 3 because the card id is already in the file (an earlier run posted it; a re-run `authorize` on `awaiting_*` returns the same state) → one-line note, not retried (`requests/07_notices_schedules.md` R30 asks 02 for the distinct code `card_id_exists`). `refused` **with `result.card_on_refuse: true`** — which 02_act.md now sets **only** for a `meta.business_portfolio_*` row refused on a non-hipaa pack for a reason other than `cross_company`, `unlisted_target` or `phi_target` (`requests/07_notices_schedules.md` R62, amending R36; plan §20.6/§20.11 "if Meta requires one, that step becomes a card", the third card type §20.11 keeps): Write the fixed body `Action <action_id> (<result.row_id>, <result.system>) was refused (reason <result.reason>). GTM agents never do this step (NEVER class). If Meta requires it, do it yourself outside GTM, entity-checked per the cross-business rule — never create or join a Business Portfolio that holds, or would hold, another of your businesses. Answer "Yes" or "No" to acknowledge. Nothing runs from this card.` to `<home>/.claude/gtm/drafts/card_<action_id>.md` → `act.py card-post --company <slug> --card-id <action_id> --title "Needs you: GTM refused <result.row_id> (<action_id>)" --file <home>/.claude/gtm/drafts/card_<action_id>.md` — **no `--action` and no `--subject`** (subject `null`: the card is informational and gates nothing, since NEVER is not operator-overridable; `--action` would imply the gating subject `authorize <action_id>`); its `card` notice is resolved by E1b's `record-external` once the card is answered (§7.1 resolver table, R36). **No card for isolation refusals (r5; supersedes the former five-branch bodies):** a `cross_company`, `unlisted_target` or `phi_target` refusal, and any refusal on a hipaa pack, posts **no** card — plan §20.11 names only three card types and CSA's card rule forbids cards the operator cannot meaningfully answer; act.py's pushed `isolation_hit` notice (with `reason_code`) and the breaker pause are the surface, and the page and push render the fixed `REFUSAL_REASON_TEXT` line for the code (§7.1) — the same per-reason wording the cards used to carry. The session reports each such refusal as a one-line note `refused <action_id>: <reason> (isolation notice)`. Every other `refused` result, and every other state → no card (a one-line note). A card is only ever posted with `act.py card-post` (never Write/Edit). K test: the E4 `card_on_refuse` line carries `card-post` with neither `--action` nor `--subject`, and no prompt file contains a card body naming `cross_company`, `unlisted_target` or `phi_target`; D/A2 tests (each falsified by removing the rule): a `cross_company` refusal posts **no** card, writes one `isolation_hit` notice with `reason_code: cross_company`, and the page shows the fixed `must not be done by anyone` text; the Meta portfolio card contains `never create or join a Business Portfolio`; D/A2 test: a `meta.business_portfolio_create` fixture proposal → `authorize` → `refused` with `card_on_refuse: true` → E4's exact command posts one card, and archiving it `"Yes"` then running E1b resolves the `card` notice while the action stays `refused` (falsified by removing the branch: the notice stays open and no card exists) |
| E5 | setup run whose `secret_sink.py` exits 3 `ROTATE` — **interactive sessions only**: setup runs never run from a schedule, `secret_sink.py` is not on the scheduled allowlist (§7.6 step 5), and no scheduled prompt file contains E5 (K test) | 06_connectors.md §6.6's rotation steps |
| E6 | second-to-last step, always | `notices.py list --company <slug> --status open --json` and `notices.py list --company runtime --status open --json` (in session env the runtime list holds only notices whose `origin_company` is `null` or this company, §7.1 company binding; no `--since`: a breaker or `PAUSE.budget` notice opened on an earlier run and still open must be listed) — **every** open notice of both lists in the final message, grouped by `kind` in this order: `isolation_hit`, `trust`, `chain`, `breaker`, `budget`, `runaway_spend`, `money_card`, `card`, `signin_missing`, `pause`, `hold`, `cancel_too_late`, `activity_log_failed`, `spool_dropped`, `agent_cancel`, `task`, `info` (one line each: `notice_id`, `kind`, `severity`, `system`, `action_id`/`request_id`, `created_at` — the §7.1 page field allowlist, so no title or body of an in-process notice is quoted; breakers get no card, §7.1; `task` rows are the operator tasks of I6, W9, M1 and the lease notice, §7.6). K test: the E6 line names all seventeen `NOTICE_KINDS` (§7.1), checked against the constant itself |
| E7 | last step, always — **only when the RUN CONTEXT says `hipaa=0`**; with `hipaa=1` the step is one final-message line `E7: no push relay (hipaa)` (§7.1 push rule), and the mechanical control is that §7.6 step 5 grants a hipaa pack's session no `PushNotification` at all, so an injected or confused model's call is denied | `notices.py list --company <slug> --status open --since <start> --json` and `notices.py list --company runtime --status open --since <start> --json` (`<start>` = the RUN CONTEXT run constant, substituted by `gtm_session.sh` in the pinned UTC form; the **tool** filters by time — the model compares no timestamps) → a `PushNotification` call for each returned record whose `push` is `true` — every notice created this run that `notices.py` meant to push, not only `urgent` ones (plan §20.7/§20.13: each new hold and each `$` card is pushed) — sending exactly that record's `push_text` (§7.1 push rule: the page's writer allowlist already applied), never composed text. Old open notices are not re-pushed. This is the second channel next to `notices.py`'s own osascript push at creation (§7.1), so a hold or `$` card still reaches the operator if probe o finds that osascript from a launchd-spawned session does not; **until probe o is recorded, E7 is the channel relied on for scheduled non-hipaa runs**, and if probe o shows `PushNotification` itself does not deliver from a `-p` session, the recorded fallback is the operator page plus E6's final message, stated in plan §17 (probe o) — which is also a hipaa pack's permanent channel set; for that reason a recorded probe o PASS for osascript from a launchd-spawned process is a precondition for loading any hipaa pack's schedules (§7.1 push rule, the recorded plan §20.8 deviation, R63). K test: the E7 line names `--since <start>`, `push_text` and `push`, does not restrict to `urgent`, and names the `hipaa=1` skip; K/B test (hipaa fixture): the rendered `--allowedTools` list contains no `PushNotification`, and a `-p` fixture session's `PushNotification` call is denied |

**Sign-in detection (FID-10; plan §18, §20.11).** Every dispatch prompt to a ticket-holding seat
(`gtm-analyst`, `gtm-operator`) carries this instruction verbatim: *"If any page for a system lands
on one of that system's runbook `login_hosts` (a sign-in page), stop work on that system, never type
anything there, and report one `findings[]` entry `{"kind": "signin_missing", "system": "<tier
system>", "severity": "warn"}` for it."* A read ticket's `allowed_hosts` already include the systems'
`login_hosts` (03_schemas.md §3.6), so a signed-out read lands on the page instead of being denied; a
write ticket's do not, so an operator redirected to a sign-in page reports it the same way. `ingest-findings` turns each such finding into the
`signin_missing` notice (push) and resolves the open ones the same seat read cleanly (02_act.md
§2.4); E3 then posts or skips the one batched card (§7.1 `card-draft`). This is what the page's
"missing sign-ins" section, 03_schemas.md §3.19's `expired_signins` and the approver read.

**Operator tasks for homes without a `local_jsonl` inbox (CSA; recorded deviation from plan §5).**
Plan §5 puts CSA's lead-unanswered and lease tasks on the tracking GitHub issue thread. No
**scheduled** GTM session can reach `gh` — its settings file admits no ambient allow rule and lists
no `gh` rule, and G-B's scheduled-scope rule denies every command outside the rendered list (§7.6
step 5, r6; before r6 this sentence relied on the `--allowedTools` list alone, which the machine's
ambient allow rules — CSA's `Bash(gh:*)` among them — would have widened) — and an interactive GTM
session's `gh` use is governed by 04_hooks.md G-B (whether GTM scope denies a `gh` write against the
example-org organization, which also holds the OtherApp repo, plan §20.9a, is asked of 04 in
`requests/07_notices_schedules.md` R63); no GTM step files an issue either way, a GTM seat must not
gain a GitHub path, and the pack names no tracking issue, so **DECIDED HERE:** for such homes the operator task
is the `task` notice itself — pushed at creation (`--push`), shown on `GTM_Operator.html`, and
listed by every run's E6 until resolved. Nothing mirrors it to GitHub. This deviation is carried to
08_seats_wps.md Appendix B for ratification (`requests/07_notices_schedules.md` R4); if it is
overruled, the mirror belongs in a non-GTM interactive step that files each open `task` notice
through `gh_issue.sh` and then resolves it with `notices.py resolve` from the operator's terminal (outside session env any open `task` may be resolved, §7.1).

**Paused runs (F17; `paused=1` in RUN CONTEXT; DECIDED HERE, `requests/07_notices_schedules.md`
R23, as amended here).** Under a manual `ST/PAUSE`, `monthly_load` runs do not start
(`skipped-paused`, §7.2); `inbox`, `daily`, `weekly` and `monthly` runs start with `--paused` and
run **only** these steps, in this order, naming every other step of their list in the final
message as `skipped: company PAUSE`:
- *inbox* — E0, E1 (report only), E1b, E2b (`runaway-stops`) with E4, [R52: **S1**,] I1b, I2a, I2,
  I3 (with its E2 `ingest-findings`, any E2b/E4 it triggers, its I3b verifies and its read-ticket
  `--close`), I5, I6, E3, E6, E7;
- *daily* — E0, E1 (report only), E1b, E2b (`runaway-stops`) with E4, [R52: **S1**,] D1, D2, D3, D3b
  (T0 API reads) with its E2b/E4, D6 (verification — T0 API reads and read tickets, plan §6.8 keeps
  `verify` and day-after verifies allowed under a pause — including its budget-state branch), D6b
  (owner-executed verification, reads plus a record of what the operator did), D7 (speed-to-lead, a
  T0 read), D9, D10, E3, E6, E7 — so verification of what was just published, and the
  two-`verify_failed` breaker input, never lapse during an incident, and the paused daily and paused
  inbox lists agree on speed-to-lead;
- *weekly* — E0, E1 (report only), E1b, E2b (`runaway-stops`) with E4, W1, W2, W3 (read ticket + analyst, with its E2 and any
  E2b/E4), W4, W7, W8, W9, **W10**, E3, E6, E7;
- *monthly* — E0, E1 (report only), E1b, E2b (`runaway-stops`) with E4, M1, M3, M4, M5, E3, E6, E7 (M2's director dispatch is the
  only skipped step).
**S1 [R52] (paused inbox and daily runs only; shipped only after R52's ratification is recorded —
until then no prompt file contains it, and a stop signed under a manual PAUSE follows E2b's shipped
default):** `act.py queue --company <slug> --kind authorized --stops-only` (only authorized,
**signed**, spend-reducing runaway stops whose own system has no breaker `PAUSE.<system>`; R52 as
amended by R62) → for each API row `act.py execute <id>`; exit 5 or 10 → one-line note, not retried;
a browser row is never executed under a pause (listed, left for the operator, E2b). S1 is the only
executor of a stop under a manual PAUSE: paused runs skip I9 and D5.
**"E1 (report only)"** = the E1 Glob of `PAUSE.chain` plus `notices.py list --company <slug> --status
open --json`, reporting the open `chain` notice (or its absence) in the final message — **no**
`notices.py card-draft` (it writes a `chain` notice), no `card-post`, no `card-mark`, no
`chain-repair`. D9 (`validate_run.py`, read-only) and D10 (`purge-untrusted`, local deletion of
expired untrusted data — allowed under every pause and under `DISABLED`, 03_schemas.md §3.10) are
kept so retention and validation never lapse for the length of a pause.
Every kept step is a T0 read, a read ticket, `lead-append`, a card-answer recording (E1b, which
records what the operator decided and never authorizes past a pause, 02_act.md §2.5), a
proposal/authorization that stops at `awaiting_approval` (E2b/E4: a `$` stop always needs the
operator's signature), a card post (E3), [R52: the one signed-stop execution S1,] or a local step (the trust check, queue
and budget reads, validation, the purge, harvest/render/audit, outside-actor reconcile, the perf
report, the backup and its restore spot-check, KB freshness, the budget and ladder reports, the
pending-commit list, the weekly report, notices), so plan §6.8's "T0 reads + read tickets;
lead-append" stay allowed under a pause while every other T1+ action and write ticket stays
blocked. A pause written automatically by an isolation hit (02_act.md §2.9) therefore never stops
lead capture or runaway-stop preparation, and a long pause never drops the weekly backup (plan
§3.2), the collector reads, the analyst change-history reads and `outside_actor.py reconcile` that
are the only way operator edits and the Agency co-actor changes of plan §20.9 are seen (most needed
while paused), the monthly restore spot-check and budget review, or the daily trust check.
K test: each of the four prompt files contains its paused-run step list verbatim (inbox and daily
lists include `E2b` and `E4`, and — until R52's ratification is recorded — **not** `S1`; the daily
list includes `D2`, `D6` (with its budget-state branch), `D6b` and `D7`; the inbox list includes
`I1b`, `I2a` and `I3b`; every list includes `E3`; the weekly list includes `W1`, `W3`, `W4`, `W7` and
`W10`; the monthly list excludes only `M2`).

| # | Inbox (`gtm_inbox.txt`; plan §5 inbox row) | Command(s) |
|---|---|---|
| I1 | release due holds | `act.py run-holds --company <slug>` |
| I1b | **lead-capture window task** (05_approver.md §5.5 step 0 item (3); `requests/05_approver.md` R54(c)) — every inbox run, paused included | `notices.py task --company <slug> --template lead_capture_window` (§7.1): when the company has open `lead_capture_stopped:` notices (a trust failure stopped lead capture), notices.py writes the one same-day `task` "GTM lead capture was stopped (<slug>)" with the window and inbox systems in its fixed body, and resolves those notices in-process; with none it writes nothing (`created: false`) — no note needed. Nonzero → a failed step, reported. K test: the inbox file contains this exact line |
| I2a | **budget-state day-after verifies** (plan §6.8/§5: `verify` and day-after verifies stay allowed under `PAUSE.budget`; r5, replaces D6's former accepted limitation) — every inbox run, paused included | `ai_budget.py state --company <slug>` → **only** when it reports budget state (a bucket over its cap, or `PAUSE.budget` present): `act.py status --company <slug> --state completed --unverified --completed-before-hours 18` → take the rows whose `route` is `browser` (R57 as amended by R62: every `status` row carries `route` ∈ {`api`, `browser`}) as this run's **verify rows**; when there is at least one, I2 uses its second literal form (below), which adds their systems inside act.py, and I3's analyst dispatch prompt names their action ids with the verify-read instruction. Not in budget state, or no such row → skip silently (D6 covers them) |
| I2 | one read ticket for every inbox system (plus I2a's verify-row systems) | `act.py ticket --read --company <slug> --inbox`, or — only when I2a found verify rows — `act.py ticket --read --company <slug> --inbox --plus-verify-rows 18`. **Inbox systems (DECIDED (wave1c); the one source, `requests/07_notices_schedules.md` R64):** `system_names.inbox_systems(pack)` = the sorted tier systems of `scope.channels_in_scope` that are `crm` or `call_tracking`, or whose connector manifest lists a non-empty `inbox_class_ops` (06_connectors.md §6.3); `--inbox` makes act.py compute them itself, and `--plus-verify-rows N` adds the systems of the rows `status --state completed --unverified --completed-before-hours N` reports with `route: browser`; act.py prints the final set as `result.systems`. The model chooses between the two literal lines and never writes a `--systems` value here. K test: the I2 line contains no `--systems` |
| I3 | analyst reads reviews/DMs/Q&A/lead notifications | `Agent` gtm-analyst (tagged), then `act.py ingest-findings --company <slug> --from-agent <analyst id>` (E2), then `act.py ticket --company <slug> --close <ticket_id>` (usually already closed by the SubagentStop hook; a close of an already-terminal ticket is an idempotent success, exit 0 with `result.already`, 03_schemas.md §3.6 — IMP-13) |
| I3b | **verify I2a's rows** (only when I2a found verify rows) — after I3's `ingest-findings` | `act.py verify --company <slug> --action <id> --from-agent <analyst id>` for each I2a verify row; exit 3 (the analyst reported no verification for it) → one-line note, the row stays unverified for the next run. The reserved lead-capture analyst dispatch (04_hooks.md §4.6, the one budget state still admits) does both jobs, so no extra dispatch is spent. D test (budget-state fixture): a browser action completed 20 h ago is verified by the next inbox run's I3b and `verify.status` is set (falsified by removing I2a) |
| I4 | record snapshots | `act.py snapshot --company <slug> --from-agent <analyst id>` |
| I5 | append every new lead (T1, exempt from `PAUSE.budget`) | for each index `i` of the analyst's `gtm-result.leads[]`: `act.py lead-append --company <slug> --from-agent <analyst id> --index <i>` — act.py reads the row from that analyst's **own** final `gtm-result` (via the transcript index, identity verified as `propose --from-agent`, 02_act.md §2.7(a); `requests/07_notices_schedules.md` R43), so the orchestrating session never re-types a lead's name, contact or message into a draft file or its own context, and a session that has read untrusted text cannot alter lead data before it lands. `--file` stays for interactive use only; no scheduled prompt uses it (K test: no prompt file contains `lead-append` with `--file`; A1 test: `lead-append --from-agent <aid> --index 0` appends exactly the fixture analyst's row, and an `--index` past the end → exit 3, nothing appended) |
| I6 | task for any lead unanswered past its response target | `act.py read-run speed_to_lead --company <slug>` (§7.4; the target is the pack's `lead_sink.response_target_minutes`, 03_schemas.md §3.14, `requests/07_notices_schedules.md` R37) → Read `<home>/.claude/gtm/state/collectors/<run_id>/speed_to_lead.json` and iterate its `data.unresponded_past_target[]` — **every** lead still unanswered past target, including leads appended on earlier runs (this run's `lead-append` ids play no part) — and for each entry: `notices.py task --company <slug> --template lead_unanswered --lead-id <lead_id> --received-at <received_at>` (§7.1: notices.py composes the fixed title and body from those two grammar-checked values, `created_by: session`, pushed, deduped per lead across runs). `<lead_id>` and `<received_at>` are that entry's two fields; a value failing its grammar → exit 3 `bad_template_arg`, a one-line note, and the next entry; the lead's `source`, name, contact or message never enter any command. `read-run` exit 3 `collector_out_of_scope` or a missing file → one-line note. K test: no prompt file contains `notices.py write`, `--title "`, `--body "`, `--body-file` or `--title-file`, and the I6 line names `speed_to_lead.json`, `unresponded_past_target` and `--template lead_unanswered`; D test: a fixture sink with one lead appended two days earlier and unanswered past a 60-minute target → one open `task` notice `lead_unanswered:<its id>` with `created_by: session`, and a second run creates none (falsified by iterating this run's `lead-append` ids) |
| I7 | owner-published items since last run (`owner_queue` actions — shadow, `--route owner`, 02_act.md §2.6; not the superseded O6 semi path) | `act.py record-external --company <slug> --kind owner_published --queue-item <action_id> --verify-from-agent <analyst id>` |
| I8 | draft replies → checker pre-screen → the two `review_reply` lanes (FID-12; plan §20.6 supersedes O6: replies are autonomous **after** the required reviews) | `Agent` gtm-drafter → `act.py propose --company <slug> --from-agent <drafter id> --index <i>` per proposal → `act.py status --company <slug> --action <id> --review-brief` per action (it writes the brief file and prints only `result.brief_path`, 02_act.md §2.4; the session collects those paths and **never Reads a brief file** — briefs carry the draft reply and the quoted review, untrusted and on a hipaa pack PHI-bearing, so they enter only the checker's and lane seats' own contexts; every dispatch below names the brief paths, never their contents; `requests/07_notices_schedules.md` R43) → **one** `Agent` gtm-checker covering every brief (pre-screen only: gtm-checker is not a `public_reviewers` seat for these rows, 02_act.md §2.7, so its verdicts are **not** recorded with `act.py review`; an action whose checker `reviews[]` entry is `fail` is left `proposed`, excluded from the lane dispatches, and listed in the final message for the next run's redraft) → **one** `Agent` content-strategist (`claims_voice` lane, non-drafting) and **one** `Agent` local-presence-architect (`compliance` lane, plus `hipaa` on `regulated ∋ hipaa` packs, 02_act.md §2.7), each covering every remaining brief → `act.py review --company <slug> --action <id> --reviewer-agent <that seat's id>` per action per seat. These are the lanes' `public_reviewers` (03_schemas.md §3.5); gtm-checker alone never satisfies them. **Hipaa packs (`hipaa=1`; r6, a recorded plan §20.13 amendment, `requests/07_notices_schedules.md` R63):** plan §20.13 keeps OtherCompany DM/review bodies in the analyst/drafter/checker dispatches only, and both lane seats hold Bash/WebFetch/WebSearch (08_seats_wps.md §8.6), so on a hipaa pack a lane seat is **never** given the full brief. Route (a) is taken: each action gets a second, **lane brief** from `act.py status --company <slug> --action <id> --review-brief --lane-variant` (R63 to 02_act.md §2.4; `result.brief_path` names `ST/review_briefs/<action_id>.lane.json`) = the full brief with every quoted inbound text (the review, DM or Q&A body the reply answers, and any other `after` field 02 marks inbound) replaced by `{"sha256": <hex>, "len": <n>}` — the draft reply text itself is kept, because checking the plan §20.5.1 non-confirming-reply rule and the `claims_voice` lane needs only the reply, never the review body. The content-strategist and local-presence-architect dispatches name **only** lane-brief paths; the gtm-checker dispatch (Read/Grep/Glob only) names the full briefs. `act.py review` binds a lane seat's verdict to the lane brief's recorded `brief_sha256` (R63 to 02). **Until R63's lane-variant, its review binding and the gate-gtm rule below have landed with their tests, route (b) applies instead:** a hipaa pack's scheduled inbox run dispatches **no** lane seat — the replies stay `proposed`/checker-screened and are listed as `needs interactive review: <action_id> (hipaa reply lanes)`, exactly as W6 handles non-roster reviewers — and the hipaa inbox prompt carries no lane-dispatch line. **Either route:** no inbox prompt is installed for a hipaa pack until probe f has recorded whether subagents dispatched from a `-p` session inherit the parent's `--allowedTools` or keep their own agent-file grants (§7.6 step 5's hard-prerequisite list). **Mechanical control (R63 to 04_hooks.md §4.6):** gate-gtm denies, for a hipaa pack, any `Agent`/`Task` dispatch whose prompt names a **full** review-brief path (`review_briefs/<action_id>.json`, not `.lane.json`) to a seat whose agent-file `tools:` include `WebFetch`, `WebSearch` or `Bash` (`gtm-hipaa-brief-egress`). D test (OtherCompany fixture, with 02/04): a marker placed in a fixture review's quoted body appears in no content-strategist or local-presence-architect dispatch prompt and in no file those seats can read under `ST/review_briefs/*.lane.json` (falsified by passing the full brief); B test: a dispatch naming a full hipaa brief path to `content-strategist` is denied, the same path to `gtm-checker` is allowed. Budget: analyst 1 + drafter 1 + checker 1 + lanes 2 + operator ≤3 = 8 = `dispatch_caps_per_run.inbox`, where the operator ≤3 covers **both** I9 parts (already-authorized holds and this run's new actions); hitting the cap before the lanes ends I8 with the replies left `proposed`/`changes_requested`, reported. K test: no scheduled prompt file tells the session to Read, Grep or print a path under `review_briefs/`, and the I8 and W6 dispatch lines name brief paths only; the hipaa-pack rendering of the inbox prompt (the `hipaa=1` branch) contains no lane-seat dispatch line until R63's lane variant is recorded as landed, and afterwards names `--lane-variant` on every lane dispatch |
| I9 | (a) execute what is already authorized (held actions released by I1 — plan §20.7: held replies run "at the next inbox/daily run after `hold_until`"), then (b) authorize and execute what tier + approvals allow for this run's proposals | (a) `act.py queue --company <slug> --kind authorized` → API rows `act.py execute <id>`; browser rows `act.py ticket --company <slug> --write <id>` → `Agent` gtm-operator → `act.py complete --company <slug> --action <id> --ticket <tkt> --from-agent <operator id>`; (b) `act.py authorize --company <slug> --action <id>` → API: `act.py execute <id>`; browser: `act.py ticket --company <slug> --write <id>` → `Agent` gtm-operator → `act.py complete --company <slug> --action <id> --ticket <tkt> --from-agent <operator id>`; every other `authorize` result state → E4 (card: `awaiting_card`, `awaiting_approval`, and `refused` with `card_on_refuse: true`) or a one-line note (`held`, `denied`, `refused` without `card_on_refuse`, `owner_queue`, `would_execute`). `ticket --write` or `execute` exiting 3 `quiet_hours`/`sms_window_closed` leaves the action `authorized`: one-line note "retry next run", not a failed step (02_act.md §2.4 `ticket`, FID-24). Both parts strictly one at a time, (a) before (b), sharing the operator ≤3 budget. `website_static` rows are authorized and executed only in an interactive session (02_act.md §2.4) — skipped here and listed in the final message; a scheduled prompt never dispatches a code-writing or repo-editing agent |

| # | Daily (`gtm_daily.txt`; plan §5 daily row, 05_approver.md §5.6) | Command(s) |
|---|---|---|
| D1 | trust check (reads JSON only) | `PY /Users/x/.claude/tools/gtm/approval_sig.py --trust-check` (`PY` = the literal pinned interpreter) (exit 0 ok; 11 trust failure → listed in the final message, `approval_sig` itself writes `PAUSE.trust` and its notice after a settle re-check; 1 internal → reported as a failed step) |
| D2 | refresh the transcript index | `transcript_index.py refresh` |
| D3 | breaker / lease / queue health | `act.py queue --company <slug> --kind hold`, `--kind failed`, `--kind approval`, `--kind card`; `ai_budget.py state --company <slug>`; `autonomy_ladder.py status --company <slug>` — findings listed in the final message |
| D3b | **daily ad-spend pacing** (plan §20.6 runaway detection; T0 API reads, no dispatch) | `act.py read-run ad_spend_pacing --company <slug>` (§7.4) → its `result.runaway_spend` goes through **E2b** (the in-process runaway notice is already written by `read-run`, R42); exit 3 `collector_out_of_scope` (no paid system in scope) → one-line note, not a failed step. So a runaway is seen within one business day by the daily run itself, not only by the weekly W3 pull or an inbox analyst. K test: the daily file contains the D3b line |
| D4 | release due holds | `act.py run-holds --company <slug>` |
| D5 | auto-publish already-approved items native schedulers cannot hold | `act.py queue --company <slug> --kind authorized` → API rows `act.py execute <id>`; browser rows `act.py ticket --company <slug> --write <id>` → gtm-operator → `act.py complete --company <slug> …`; `website_static` rows are left for an interactive session (02_act.md §2.4); exit 3 `quiet_hours`/`sms_window_closed` → "retry next run", as I9 |
| D6 | **day-after verification** of every `completed` action that has no `verify.status` yet and completed at least 18 h before the call — keyed on state, not on a calendar day, so Friday and weekend completions (Mon–Fri daily runs) are verified on Monday (this is what trips the 02_act.md §2.9 two-`verify_failed` breaker) | `act.py status --company <slug> --state completed --unverified --completed-before-hours 18` (the bound is computed by act.py from its own clock at call time — `completed_at <= now − 18 h` — never by the model; `requests/07_notices_schedules.md` R26 as amended by R57) → API rows `act.py verify --company <slug> --action <id> --auto`; browser rows: one `act.py ticket --read --company <slug> --systems <their systems>` + one gtm-analyst dispatch covering them → `act.py ingest-findings --company <slug> --from-agent <analyst id>` (E2) → `act.py verify --company <slug> --action <id> --from-agent <analyst id>` each. A `website_static` action refused exit 4 `not_deployed` is expected (not deployed yet, 02_act.md §2.4 `verify`) — one-line note, not a failed step. **Under budget state** (D3's `ai_budget.py state` reports a bucket over its cap, or `PAUSE.budget` present — every non-lead-capture dispatch is denied, 04_hooks.md §4.6): D6 runs its API rows only and dispatches no analyst; the browser rows stay `completed`/unverified, are listed in the final message as `verify waiting: budget state — next inbox run`, and are verified by the **next inbox run's I2a/I3b** through the reserved lead-capture analyst dispatch, which budget state still admits (r5; no plan deviation: plan §6.8/§5 keep `verify` allowed under `PAUSE.budget`). **Under a manual `ST/PAUSE`** D6 runs in full (paused daily list): verification is T0 reads and read tickets. K test: the D6 line names the budget-state branch and `next inbox run` |
| D6b | **owner-executed changes** (05_approver.md §5.8; `requests/05_approver.md` R48 as amended by R55) — only while HEAD's `tools/gtm/approver_probe_p.json` says `"probe_p": "fail"`, a gate the **tool** evaluates | `act.py queue --company <slug> --kind approval --owner-executable` (R62 to 02: returns rows **only** while HEAD — `git show HEAD:tools/gtm/approver_probe_p.json` in the runtime repo, never the working tree — says `"probe_p": "fail"` and HEAD has no `tools/gtm/approver_pubkey.pem`; otherwise `result.rows: []` and `result.probe_p` = the HEAD value; the session never reads the file) → empty → skip silently; else one `act.py ticket --read --company <slug> --systems <those rows' systems>` (shared with D6's browser-row ticket and analyst dispatch when both run: one ticket over the union of systems, one gtm-analyst dispatch naming both sets of action ids) + one gtm-analyst verify-read → `act.py ingest-findings --company <slug> --from-agent <analyst id>` (E2) → for each such action: `act.py record-external --company <slug> --kind owner_executed --card <request_id> --action <action_id> --verify-from-agent <analyst id>` (exit 3 `owner_observation_mismatch` — the platform does not show the requested value/status, R55(a) — → one-line note, not retried). Under budget state D6b dispatches no analyst (listed as `owner check waiting: budget state`). No operator reply is involved. K test: the daily file contains the D6b line with `--owner-executable` and `--kind owner_executed`; D/A2 test (with 05's fixtures): HEAD probe_p `fail` and an operator-made change observed → the action closed `owner_executed`; HEAD probe_p `pass` → `--owner-executable` returns no rows and D6b does nothing (falsified by gating on the working tree) |
| D7 | speed-to-lead measurement | `act.py read-run speed_to_lead --company <slug>` (WP-F collector, §7.4; `inbox_class: false`, so its output is in `ST/collectors/` for every pack, OtherCompany included) → Read `<home>/.claude/gtm/state/collectors/<run_id>/speed_to_lead.json` and take key `data.median_minutes_7d` as `<v>` → `scoreboard.py add --company <slug> --metric speed_to_lead_median_min_7d --value <v> --unit minutes --source collector:speed_to_lead`. `data.median_minutes_7d` null (no answered lead in 7 days), `ok: false`, or `read-run` exit 3 → no `scoreboard.py add`, one-line note. K test: the D7 line names `speed_to_lead.json` and `data.median_minutes_7d` |
| D8 | autonomy ladder | `autonomy_ladder.py promote --company <slug>` |
| D9 | validate every run since the previous daily run | `validate_run.py --company <slug> --since-last-daily` (R57): the tool itself lists `<home>/.claude/gtm/state/cycles/cyc_<slug>_*.json`, takes `P` = the latest company-local date (pack `timezone`) of a `cyc_<slug>_daily_*` record before today (none → yesterday; never more than 14 days back), and validates every cycle whose id date lies from `P` through yesterday (Monday: Friday's runs after the daily and the Saturday weekly; a missed daily widens the window by itself; cycle ids carry their company-local date, 00_global_paths.md §0.3), printing one JSON object `{"ok", "window": [first, last], "runs": [{"run_id", "ok", "errors": n}]}`; `validate_run` is read-only, so re-validating a run is harmless. The session composes no date and no glob. Each run with `ok: false` → one line `<run_id>: <errors> validation error(s)`. K test: the D9 line is exactly this command and contains no `Glob`; G test (with R57): a Monday fixture with Friday daily + inbox and Saturday weekly records validates exactly the runs after Friday's daily through Sunday, and a 20-day gap validates 14 days |
| D10 | purge | `act.py purge-untrusted --company <slug>` |

| # | Weekly (`gtm_weekly.txt`; plan §5 weekly row, §3.2, §11) | Command(s) |
|---|---|---|
| W1 | collectors | `act.py read-run <collector> --company <slug>` for every collector in `tools/gtm/collectors/registry.json`; exit 3 `collector_out_of_scope` (no system of the collector is in scope after `tier_system_of` normalization, §7.4 — the session never compares names itself) → one-line note, not a failed step |
| W2 | harvest → render → audit (the analyst has no Bash) | `harvest_tool_trail.py` (no arguments: default globs over `gtm_slugs()` homes; the allowlist admits **only** this exact no-argument command, §7.6 step 5) → `activity_log.py render --company <slug>` → `activity_log.py audit --company <slug> --days 7`. **Exit handling for all three, in order, each always run:** harvest nonzero (exit 1 on a registry error or an unresolvable company, whose records it reroutes to the unattributed sink) → a failed step reported as exactly `harvest exit <n>` (never its stderr text, which can name registry paths and slugs — the final-message rule), and render and audit **still run** (they read what the trail already holds); render nonzero → a failed step, audit still runs; audit as below. **Exit 1 is findings only when stdout contains a line starting `audit found `** (unexplained clusters or `gtm-offserver` records, `activity_log.py cmd_audit`) — list each cluster **by id and count only** in the final message (and it goes to W10's report the same way); it is not a failed step. For a pack with `regulated ∋ hipaa` the audit is run as `activity_log.py audit --company <slug> --days 7 --ids-only` (R58: prints cluster ids, kinds and counts, never offserver URLs or `sample_detail()` text), so that text never enters the scheduled session's context; for every pack the final-message rule applies (never a URL or detail string). Exit 1 with no such line is an uncaught error (e.g. `CompanyError` from `resolve_paths`, which exits 1 with a traceback) and, like any other nonzero exit, is a failed step. **Harvest is machine-wide by design:** with no arguments `harvest_tool_trail.py` harvests the transcripts of every `gtm_slugs()` home and appends each record to the trail of the company it attributes to (in that company's home, not this run's) or to the cross-company unattributed sink, taking every trail's lock in sorted lock-path order (`harvest_tool_trail._flush_locked`, fix #21), so two companies' weekly runs harvesting at once are safe. **What the session sees (DECIDED (wave1c);
`requests/07_notices_schedules.md` R64 amending R16/R63):** today, with no arguments, the harvester prints
`by company:` and one `<slug>: <n>` line for every GTM company that got records, so every company's
session would receive the other companies' slugs and activity counts, against §7.1's isolation stance;
so, in session env (`CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` set), it prints only `scanned <n>
transcript file(s)`, `new records: <total>` and `this company: <n>` for `CLAUDE_GTM_COMPANY` — never
another slug, never the `by company:` block (the unattributed count, which names no slug, stays);
W2 ships only after that lands (§7.6 step 5). D test (falsified by restoring the `by company:` block):
a OtherCompanyB-env harvest over fixture transcripts that include OtherCompany records prints no
`othercompany`. **Ships only after** `company.py` gains `gtm_slugs()` and `harvest_tool_trail._registered_homes()` switches from `registered_slugs()` (which includes Agency) to it (00_global_paths.md §0.1; today's code would glob Agency transcripts, which the Agency-separation ruling forbids); test: a registry holding `agency` produces no Agency project-dir glob (`requests/07_notices_schedules.md` R16). **Hipaa records in the trail (r6; plan §20.13 "never quoted into logs or reports", §20.4's purgeable side store):** the harvester today passes browser-call `text`/`value` only through a credentials-only `redact_text` and keeps `result_excerpt` (600 chars) and `prompt_excerpt` (400 chars), so a OtherCompany reply text or snapshot excerpt would land in `activity_log_dir/TOOL_TRAIL.jsonl`, which W8 backs up and nothing purges. **Ships only after** R63 (to `harvest_tool_trail.py`'s owner, amending R16) lands: for every record attributed to a pack with `regulated ∋ hipaa`, the trail line stores `{"sha256": <hex>, "len": <n>}` in place of `detail.text`, `detail.value`, `detail.element`, `result_excerpt` and `prompt_excerpt`; the full record, if kept at all, goes only to that home's `ST/untrusted/trail/` (0600, covered by the 30-day age purge, excluded from backups). D test: a OtherCompany fixture transcript whose `browser_type` text, tool result and dispatch prompt each hold a marker yields a `TOOL_TRAIL.jsonl` line with none of the markers (falsified by storing the excerpts verbatim) |
| W3 | analyst full pull + change-history reads | `act.py ticket --read --company <slug> --all-in-scope` (DECIDED (wave1c), R64: act.py names every tier system of `scope.channels_in_scope` that has a read connector, `system_names.read_systems(pack)`, and prints them as `result.systems`; K test: the W3 line contains no `--systems`) → `Agent` gtm-analyst → `act.py ingest-findings --company <slug> --from-agent <id>` (E2) → `act.py ticket --company <slug> --close <ticket_id>` (idempotent, as I3) → `act.py snapshot --company <slug> --from-agent <id>` |
| W4 | outside-actor reconcile | `outside_actor.py reconcile --company <slug> --run <run_id> --from-agent <analyst id>` |
| W5 | director diagnosis → specialists (proposals + 20% checker audit in the same dispatch) → cross-review + dissent ledger → convergence | top-level `Agent` marketing-director (never inside a Workflow); convergence decided only by `exit_contract.py`'s verdict, which the director reports verbatim; unconverged items carried to next week |
| W6 | drafter/checker for content, lane reviews, authorize, schedule | as I8–I9 (including I9's rule: `website_static` rows are authorized and executed only in an interactive session, 02_act.md §2.4, and a scheduled prompt never dispatches a code-writing or repo-editing agent), except that the lane dispatches are one per seat named by the batch's review briefs (`lanes_required`; `public_reviewers` on public rows, `internal_reviewers` otherwise, where gtm-checker's own verdict is then recorded with `act.py review`), each covering every brief needing that lane (plan §5: lane reviews ≤5); native-scheduler loads with `act.py ticket --company <slug> --write-batch <ids>` → gtm-operator → `act.py complete --company <slug> …` per item. **Non-roster reviewers:** a lane whose required reviewer is not in `system_names.GTM_SEATS ∪ DEPARTMENT_SEATS` — e.g. `trust-architect` on the `hipaa` lane's OtherCompany data-flow rows (03_schemas.md §3.5) — cannot be dispatched here (the §7.6 step 5 allowlist and gate-gtm's R19 rule deny it, by design); such actions are, like `website_static`, reviewed only in an interactive session: W6 dispatches nothing for them, leaves them `proposed`/`changes_requested`, and lists each in the final message as `needs interactive review: <action_id> (<lane>: <seat>)`. **Hipaa packs:** W6's lane seats get lane briefs only, and the I8 route-(b) rule applies until R63 lands, exactly as I8 states (a lane seat is never given a full hipaa brief). K test: the W6 line carries this rule, and no prompt file names `trust-architect` as a dispatch target |
| W7 | perf report + program metrics | `perf_report.py --company <slug> --days 28` → `scoreboard.py add --company <slug> --metric <id> --value <v> --unit count --source perf_report` for each of the four 03_schemas.md §3.19 program metrics |
| W8 | **backup** (plan §3.2 weekly step) | `backup_state.py --company <slug>` |
| W9 | **pending tracked changes** (plan §3.2) | `act.py pending-commits --company <slug> --older-than-days 14` (R50; read-only): act.py reads `<home>/.claude/gtm/state/pending_commit.txt` under its lock, keeps only paths that **still differ from `HEAD`** (`git -C <home> diff --quiet HEAD -- <path>` nonzero, or untracked-but-listed), and prints `{"ok": true, "result": {"pending": [{"path", "first_ts", "writers": [..]}], "stale": [<the subset whose earliest line is older than 14 days>]}}` — the age is the tool's, not the model's, and a committed path drops out by construction, so it never re-raises. List every `pending` path in the weekly report (W10 reads the same command's output itself); for each `stale` entry: `notices.py task --company <slug> --template pending_commit --path <path>` (§7.1; `<path>` copied verbatim from the output; notices.py refuses a path outside `^[A-Za-z0-9._/-]{1,200}$` or with a `..` segment, exit 3 `bad_template_arg` → a one-line note). D test: a path appended 20 days ago and since committed (no diff against `HEAD`) raises no notice and is absent from `pending`; an uncommitted 20-day-old path raises one `task`, and a second weekly run with it still uncommitted raises none (dedupe) |
| W10 | **weekly report** (mandatory; plan §5 weekly row "→ weekly report + perf report", plan §0 P7, plan §20.7's surfacing rule) — after W9, before E6 | `weekly_report.py --company <slug> --run <run_id>` (WP-D; read-only except its one output file and one notice). It writes **`<home>/.claude/gtm/state/reports/weekly_<run_date>.md`** (`<run_date>` = the run id's date; the `ST/reports/` store is the plan §3.2 **ignored** class, never committed; 00_global_paths.md §1.3, R59) atomically (same-dir temp + `os.replace`), with exactly these sections in this order, each rendered **only** from the §7.1 page field allowlist (ids, kinds, systems, row ids, states, amounts, timestamps, counts, exit codes — never an action's `after`/`before`/draft, a lead or review field, finding text, a notice title/body, a URL, or a seat's free text; for a hipaa pack every section is ids and counts only): (1) *Agent-made cancels* in the last 7 days (plan §20.7: "listed on GTM_Operator.html and in the weekly report so a needed fix is never silently blocked") — `action_id`, `row_id`, `system`, cancelling agent type, `ts`; (2) *Outside changes* — every `outside:unknown` row and every unmapped change of the week (03_schemas.md §3.23 and the rows 03_schemas.md routes to "the weekly report") — entry id, `system`, `ts`, classification state; (3) *Card-decided approvals* — every approval or denial of the week recorded from an operator-input card (`decided_via: card`), with `card_written_by_agent` (02_act.md §2.11 routes these here); (4) *Convergence* — W5's `exit_contract.py` verdict code for this run's cycle and the ids of the unconverged items it carried (read from the cycle record, never from the director's text); (5) *Pending commits* — W9's `pending` and `stale` paths (it runs `act.py pending-commits` itself); (6) *AI-cap and budget state* — `ai_budget.py caps` source/forged per bucket, week-to-date usd per bucket, `PAUSE.budget` presence; (7) *Open notices* — `notice_id`, `kind`, `severity` only; (8) *Perf report* — the path of W7's perf report output; (9) *Signed approvals: card "No"s and revocations* (`requests/05_approver.md` R65 as amended by R66(d)) — the page block's two row kinds (§7.1), over the last 7 days or still open: (i) every `agent_cancel` notice whose `dedupe_key` starts `card_deny_after_approval:` (a card said "No" to a request the operator signed; **the approval stands**) — `request_id`, amount and unit (or `no amount`), `account_id`, the card id, `created_at`; (ii) every `approval_revoked {request_id, who}` event (`who` ∈ the operator's channels) — `request_id`, amount and unit, `account_id`, `who`, `ts` — so a "No" written against a signed request is never silently lost; a card is never described as having revoked a signed approval (a card "No" decides only an undecided request). It then writes one `info` notice in-process (`created_by: notices`, severity `info`, `push=True`, `dedupe_key: weekly_report:<run_id>`, title exactly `Weekly GTM report ready (<slug>)`, body exactly the report's absolute path) and resolves every older open `weekly_report:` notice of the company (`resolve_by_dedupe_key` per key, `created_by="notices"`), so the page (§7.1 inputs) and E6 point to the newest report, and prints `{"ok": true, "report": <path>, "notice_id": <id>}`. Exit 0 ok; 1 internal; 3 `company_mismatch` (the §7.1 session binding) — nonzero → a failed step, reported (the report is the week's operator surface, so its failure is never a one-line note). K test: the weekly prompt contains the W10 line before E6 and the W10 line is in the paused weekly list; D tests (each falsified by removing its section): a fixture agent cancel appears in section (1) by `action_id`; a fixture `outside:unknown` row appears in (2); a card-decided approval with `card_written_by_agent: true` appears in (3) with that flag; a fixture `card_deny_after_approval:<request_id>` notice appears in (9) as a kind (i) row with its five fields, and a fixture `approval_revoked` event as a kind (ii) row; a hipaa fixture whose actions and notices carry marker strings in `after`, title and body produces a report with no marker; one `weekly_report:<run_id>` notice is written and a re-run of the same `run_id` writes none |

| # | Monthly (`gtm_monthly.txt`; plan §5 monthly row) | Command(s) |
|---|---|---|
| M1 | **backup restore spot-check** (**ships only after R43's `backup_state.py` JSON output and R60's `--latest` land** — today `--restore` prints one text line `restored X -> Y` with no counts or chain check; DECIDED (wave1c): until then `gtm_monthly.txt` itself does not ship and the monthly plist is not loaded — the monthly prompt never runs without M1 (§7.6 step 5 per-file list) — and the monthly K test requires M1) | `backup_state.py --restore --latest --company <slug> --to <home>/.claude/gtm/drafts/restore_check/<run_id> --runtime-state-to <home>/.claude/gtm/drafts/restore_check/<run_id>/_gtm_state` (`--latest` = backup_state.py picks the newest archive under `/Users/x/Backups/gtm/<slug>/` itself and prints its path as `result.archive`, R43 as amended by R60 — the session never globs, never types `~`, never composes a date) → report the entry counts `backup_state.py --restore` itself prints (`result.counts`, which includes the restored `<to>/.claude/gtm/state/actions.jsonl` line count and whether its hash chain verifies; `requests/07_notices_schedules.md` R43) — never a Read of the restored files, whose head/tail cannot count entries and on a hipaa pack can carry side-stored text; exit ≠ 0, a chain that does not verify, or no archive found → `notices.py task --company <slug> --template restore_check --run <run_id> --exit-code <n> --error-code <code>` (§7.1; `<n>` = the tool's exit code, `<code>` = its `error.code`, `chain_unverified` when the chain check failed with exit 0, or its own `no_archive` code — each copied from the tool's output). The restored tree lives under `drafts/`, so `purge-untrusted` deletes it after 30 days — **for a hipaa pack after 24 h**, like every `drafts/` file there (00_global_paths.md §1.3) — 02_act.md §2.4 |
| M2 | feature-inventory review + market-analyst delta | top-level `Agent` marketing-director, which dispatches the owning seats over `paths.feature_inventory_dir` and market-analyst for the delta |
| M3 | KB freshness | `kb_freshness.py --json` → stale/unverified claims listed for the director |
| M4 | budget review | `ai_budget.py usd --company <slug>` and `ai_budget.py caps --company <slug>`; a cap change is only ever a proposed `gtm_ai.weekly_cap_edit` (`$`, 03_schemas.md §3.4.4) |
| M5 | autonomy-ladder report | `autonomy_ladder.py status --company <slug>` and, while the company is in shadow, `autonomy_ladder.py shadow-exit --company <slug>` (report only; leaving shadow is `act.py autonomy`, 03_schemas.md §3.17) |

| # | Monthly load (`gtm_monthly_load.txt`; plan §5 monthly-load row) | Command(s) |
|---|---|---|
| L1 | approved next-month batch | `act.py queue --company <slug> --kind authorized`, keeping **only** rows whose `row_id` ends `.post_schedule` (every other authorized row is left for D5/I9 and not listed); `--write-batch` itself refuses (exit 3) any action whose row is not `*.post_schedule` (`requests/07_notices_schedules.md` R15) |
| L2 | one batch ticket + one operator dispatch per system | `act.py ticket --company <slug> --write-batch <id,…>` → `Agent` gtm-operator → `act.py complete --company <slug> --action <id> --ticket <tkt> --from-agent <operator id>` per item |

K test (P2, `tools/gtm/tests/test_k_prompts.py`): for each prompt file, every command string of
its table (the literal tool name plus subcommand, e.g. `act.py verify`, `backup_state.py --company`,
`backup_state.py --restore --latest` (M1), `ingest-findings`, `card-post`,
`act.py pending-commits`, `weekly_report.py`, `act.py runaway-stops`, `validate_run.py
--since-last-daily`, `notices.py task --company <slug> --template` (I1b, I6, W9, M1), `act.py queue
--company <slug> --kind approval --owner-executable` (D6b), `PushNotification` (E7)) occurs in the file,
and so does every E0–E7 command except E5 (the E0 canary Glob, `notices.py card-draft`, `notices.py
card-mark`, `chain-repair`, E1b's `record-external --company <slug> --kind approval`, E2b's `propose
--company <slug> --stop <finding_id>` and `authorize`, E7's `list … --since <start>`); no file contains
an [R52] line before the ratification is recorded;
removing any one line makes the test fail. **`--company` check (IMP-12):** every `act.py
<subcommand>` occurrence other than `act.py execute` and `act.py cancel` has `--company` within the
same command (up to the next `→`, `;` or table-cell end) — so `act.py ticket --close <ticket_id>`
alone fails the test; the I8 row names `gtm-checker`, `content-strategist` and
`local-presence-architect` (FID-12). **Further K checks:** the inbox file contains `act.py queue
--company <slug> --kind authorized` (I9 a); every `act.py card-post` command in E1 carries
`--subject "chain_repair <slug>"` (a chain card-post line without `--subject` fails the test);
every E4 gating `card-post` line (`awaiting_card`, `awaiting_approval`) carries `--action
<action_id>` and no `--subject` (such a line without `--action`, or with a hand-written `--subject`,
fails), while the E4 `card_on_refuse` line carries neither (its E4 row K test), and the files containing I9 or W6 contain the
E4 trigger sentence (`after each act.py authorize`) — removing it fails; no
scheduled prompt file contains the word `implement` (word boundary, any case) — the prompts never
dispatch a code-writing agent; the literal-command-form check above.

### 7.6 `gtm_session.sh` (WP-K)

```
/Users/x/.claude/scripts/gtm_session.sh <slug> [--print <prompt-file>] [--run <run_id>] [--session-id <uuid>] [--model sonnet|opus] [--scheduled] [--alarm <seconds>] [--paused]
```
The script lives at `/Users/x/.claude/scripts/gtm_session.sh` (the path §7.2 calls).
`--paused` is accepted only with `--scheduled` and a `--run` whose kind is `inbox`, `daily`, `monthly` or
`weekly` (else exit 64); it only sets `paused=1` in the RUN CONTEXT header (§7.5 "Paused runs"). Throughout, `<kind>` =
`CYCLE_ID_RE.match(run_id).group("kind")` (unambiguous: slugs contain no `_`), and every read of a
home path by this script goes through `python3` (the §7.2 TCC rule; an unreadable home → exit 1,
fail closed).
1. **Every exit-64 refusal prints exactly one stderr line `gtm_session: <token> <text>`** as its
   last stderr output, `<token>` ∈ `test_env`, `hooks_disabled`, `python_too_old`, `bad_args`,
   `bad_session_id`, `bad_paused`, and — when `GTM_SESSION_TOKEN_FILE` is set and matches the §7.2
   path regex — first writes the line `<token>` to that file (`printf '%s\n' "$TOKEN" >
   "$GTM_SESSION_TOKEN_FILE"`; the runner reads the token only from there, §7.2 "Exit-64 token
   capture"). **`--print` path check (r5):** `--print <file>` is accepted only when `python3 -c`
   `os.path.realpath(<file>)` is a regular file whose parent directory is exactly
   `/Users/x/.claude/schedules/prompts` (after `realpath` of that directory too) — a
   relative path, a symlink out of it, or any other location → `bad_args`, exit 64, so no file can
   become an unattended session's prompt; K test: `--print ./x.txt`, `--print /tmp/gtm_daily.txt` and
   a symlink under `prompts/` pointing to `/tmp` each exit 64 `bad_args` with no `claude` started.
   Refuse test env (00_global_paths.md §1.4; `test_env`, exit 64); **refuse disabled hooks:**
   `CSA_DISABLE_HOOKS` non-empty and not `0` → `gtm_session: hooks_disabled refusing to run with
   CSA_DISABLE_HOOKS set (every GTM hook would allow)`, exit 64, no `claude` (the §7.2 runner rule,
   deliberately wider than the exact-`"1"` kill-switch, for interactive and scheduled sessions alike
   — 04_hooks.md §4.1 cites this step); `python3 -c 'import sys; sys.exit(sys.version_info < (3,
   11))'` nonzero → `python_too_old`, exit 64 (§7.2 "Interpreter pin"); **GTM-company
   check** `python3 /Users/x/.claude/tools/gtm/company.py is-gtm <slug>` (§7.2; exit 13 →
   exit 13, before any `resolve` or home stat); then `company.py resolve <slug>` (exit 13 → exit 13;
   exit 1 with `error.code` `home_unreadable` (read from its captured stdout, §7.2 "Error-code
   extraction") — a `PermissionError` reading the pack, i.e. a TCC
   denial, R22 as amended by R51 → exit 1 with the stderr line `gtm_session: home unreadable (TCC)`,
   never misreported as "not a GTM company"; any other failure → exit 13); then `python3
   /Users/x/.claude/tools/gtm/runner_probe.py --company <slug> --kind interactive
   --offset-minutes 0` (§7.2's probe, whose `--kind` set gains `interactive`, WP-D), from whose output
   the script keeps `hipaa` (the RUN CONTEXT `hipaa=` value and the step 5 list variant) and, for an
   interactive session, the first candidate `run_id` (step 4(a)); a nonzero exit → exit 1. K test: with `company.py
   resolve` stubbed to exit 1 `home_unreadable` → exit 1, not 13.
   K tests: `CSA_DISABLE_HOOKS=1 gtm_session.sh <slug>` exits 64 with no `claude` started and
   `CSA_DISABLE_HOOKS=0` proceeds; `gtm_session.sh agency` exits 13 and the no-Agency-touch oracle
   (00_global_paths.md §0.1) records nothing. With `--scheduled`:
   the §7.2 **one literal command form**, verbatim (`python3 -I -S -B
   /Users/x/.claude/tools/gtm/ai_budget.py caps --company <slug> --check`) — the
   **exact §7.2 predicate** (both buckets have a `source` starting `signed:` **and** `forged ==
   false`; a nonzero exit, a missing bucket or key, or unparseable output fails; **and** a signed
   zero cap passes only when the output says `zero_cap_enforced: true`, the R32 ship-ordering rule),
   in the same single implementation §7.2 calls; any failure → exit 77, no session. A belt-and-braces
   refusal so a scheduled session can never start with unsigned, report-only or forged AI caps even
   if a caller skips the runner's check (F6). K test (`gtm_session.sh --scheduled`, IMP-19 fixture
   set): both buckets `signed:*`/`forged: false` → proceeds; a `company_json` bucket, a
   `report_only` bucket, a `forged: true` bucket with a `signed:` source, unparseable output, and a
   signed `"0.00"` bucket without `zero_cap_enforced: true` → each exit 77 with no `claude` started;
   the same `"0.00"` bucket with `zero_cap_enforced: true` → proceeds; falsified by dropping the
   `forged` clause (resp. the zero-cap clause).
2. `SESSION=<--session-id>` when given (must match a lowercase uuid4, else exit 64), else
   `$(uuidgen | tr A-Z a-z)`; `export CLAUDE_GTM_COMPANY=<slug> CLAUDE_GTM_SESSION=$SESSION
   [CLAUDE_GTM_RUN=<run_id>]`; `cd <home>` (**UNVERIFIED under launchd**: bash's access to a
   `~/Desktop` home is TCC-denied, §7.2; probe f records whether `cd` and the `claude` process
   started from it can read the home. If they cannot, `run_gtm_job.sh` launches this script as a
   child of `python3` — the pattern `run_oversight_job.sh` verified on 2026-09-17, where a bash
   child of `python3` inherited `python3`'s Desktop access — and the probe's recorded form wins).
   **DECIDED HERE:** the caller (`run_gtm_job.sh`)
   generates the uuid so the cycle record it opens and the session carry the same id;
   `leases/<slug>.json` is never used for that hand-off (the next session may overwrite it).
3. TCC check (§20.8, probe p): `python3 /Users/x/.claude/tools/gtm/tcc_probe.py` (WP-K),
   which calls `AXIsProcessTrusted()` (ApplicationServices) and `CGPreflightScreenCaptureAccess()`
   (CoreGraphics) through `ctypes` and prints `{"accessibility": bool, "screen_recording": bool}`.
   Plan §20.8 requires the Claude host process to hold **neither** grant. Every `notices.py` call of
   this step runs through `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN` (§7.1
   CLI rules, `write_in_session`; step 2 has already exported them). Either `true` → `notices.py write --company
   runtime --kind trust --severity warn --title "Claude host holds <Accessibility|Screen
   Recording>" --body "remove the grant in System Settings > Privacy & Security from the app that
   runs claude (plan §20.8)" --dedupe-key tcc:<accessibility|screen_recording> --created-by
   gtm_session --origin-company <slug>` (one notice per grant, deduped across sessions and across host apps — the key
   carries **no host segment**, because `tcc_probe.py`'s output names no bundle and which host app
   the grant is attributed to, macOS's "responsible process", is exactly what probe p has yet to
   record) and continue; each grant the probe reports `false` → `notices.py resolve-owned --company
   runtime --dedupe-key tcc:<that grant> --resolution "probe clean <SESSION>" --created-by
   gtm_session`, which clears that grant's open notice whichever host app raised it. The probe's own
   failure (nonzero exit, unparseable output) → the same write with title `TCC probe failed` and
   `--dedupe-key tcc:probe_failed`, and continue; a probe that exits 0 with parseable output resolves
   `tcc:probe_failed` the same way. Probe p's recorded command wins if it differs; if probe p later
   adds a `host_bundle_id` to the probe output, it goes into the notice body only, never the key.
   K tests: with `tcc_probe.py` stubbed to print `{"accessibility": true, "screen_recording":
   false}`, one `trust` notice `tcc:accessibility` is written under `runtime`, and a second session
   writes none; a later session whose stub prints `{"accessibility": false, …}` resolves it (falsified
   by keying on a host segment the probe cannot supply).
4. Lease: first `mkdir -p -m 0700 R/.gtm_state/leases` (so a fresh machine never fails the first
   session with lockf's 73; an existing directory is left as it is), then `/usr/bin/lockf -s -k -t
   <T> R/.gtm_state/leases/<slug>.lock /bin/bash -c '<locked child>' gtm_locked "$SLUG" "$RUN_ID"
   "$SESSION" "$ALARM" "$PRINT_FILE" "$MODEL" "$SCHEDULED" "$PAUSED" "$HOME_PATH" "$HIPAA"` (`R` =
   `~/.claude` in production — the launchers refuse `CLAUDE_DIR`, 00_global_paths.md §1.4). **The
   locked child reads its values only as these ten positional parameters** — `$1` slug, `$2` run_id (empty for an interactive session without `--run`; step
   (a) computes it), `$3` session uuid, `$4` alarm seconds (empty when no `--alarm`), `$5` prompt
   file (empty without `--print`), `$6` model (`sonnet`/`opus`, empty for the `claude` default), `$7`
   scheduled (`0`/`1`), `$8` paused (`0`/`1`), `$9` company home (absolute, from step 1's `company.py
   resolve`), `${10}` hipaa (`0`/`1`, step 1's probe) — an empty string for an absent value, plus the
   `CLAUDE_GTM_*` variables exported in step 2; **no value is spliced into the `-c` script text**. Everything the child needs is in that
   set: the holder-info `kind` comes from `$7`, `--model` from `$6`, the RUN CONTEXT `paused=` from
   `$8`, `home=` from `$9`, and `hipaa=` from `${10}`, `start=` is computed by the child itself (`date -u
   +%Y-%m-%dT%H:%M:%SZ`) immediately before it starts `claude`. K test (`test_gtm_session.sh`): with
   a fake `claude` that records its argv and `-p` text, a scheduled paused run on a fixture home
   yields `--model sonnet`, a RUN CONTEXT carrying `paused=1` and `home=<fixture home>`, and a holder
   file with `kind: "scheduled"`; the `-c` script text is byte-identical across two runs with
   different slugs (falsified by interpolating any value into it). `T = 0` interactive and `T = 600`
   with `--scheduled` (plan §3.4: wait up to 10 min). **Every interactive session prints the lease
   rule at start**, before `lockf` is tried, as one stderr line: `GTM: one session per company at a
   time. If another <slug> session holds the lease this one stops now; scheduled runs wait up to 10
   minutes for a session to finish and are then recorded as missed.` (plan §3.4). When the lease is
   held (lockf exit 75) it then prints exactly `GTM lease for <slug> is held by another session (see
   ~/.claude/.gtm_state/leases/<slug>.json). One GTM session per company at a time: close that
   session, or wait for it to finish.` to stderr and exits 75. K test: an interactive run with a free
   lease still prints the rule line first. **lockf's own exit codes** (`man lockf`): it returns the child's
   status only when it got the lock; otherwise 75 `EX_TEMPFAIL` (timeout), 64 `EX_USAGE`, 70
   `EX_SOFTWARE` (the child did not exit normally, e.g. killed by a signal), 71 `EX_OSERR`, 73
   `EX_CANTCREAT` (e.g. the leases directory is missing or unwritable). The locked child's exit set
   is only `{0, 1, 142, 100–127}` — it never exits 64, 70, 71, 73 or 75 — so the codes are
   unambiguous: 75 → the lease path below; **64, 70, 71 or 73 → `gtm_session.sh` exits 1
   (internal)** after one stderr line `lockf failed: exit <n>`, and for a scheduled run `cycle.py
   close --cycle <run_id> --status failed`. K test: with the leases directory made unwritable →
   exit 1 (not 73) and the stderr line names 73 (the `mkdir -p` succeeds on an existing read-only
   directory, so the 73 path stays reachable); on a fresh fixture `R` with no `leases/` directory an
   interactive session takes the lease (falsified by removing the `mkdir`). lockf exit 75 → scheduled: `cycle.py missed --cycle <run_id>
   --step lease --reason lease_held` (creates the record, or marks the one `run_gtm_job.sh` opened,
   03_schemas.md §3.12) + `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN notices.py write --company <slug> --kind task --severity warn --title "GTM run
   skipped: session lease held" --body "close your GTM session or let the next <kind> run proceed"
   --dedupe-key lease:<run_id> --push --task --created-by gtm_session` (the `--task` flag also
   appends the plan §3.4 task row to `ST/inbox.jsonl` for `local_jsonl` packs; for other homes
   (CSA) the notice alone is the task, listed by every run's E6 until resolved — the recorded plan §5
   deviation of §7.5 "Operator tasks");
   exit 75. **Everything that must happen while the lease is held runs in the locked child (I25,
   I3, I8)**, in this order: (a) interactive without `--run` only: `run_id` = the `run_id` of
   `runner_probe.py --company <slug> --kind interactive --offset-minutes <n>` (§7.2; `n` = 0 for the
   first try, the value step 1 already read) and `cycle.py open --cycle <run_id> --company <slug>
   --trigger interactive --session $SESSION`; **exit 3 with `error.code == "duplicate_cycle"`** (R62;
   extracted per §7.2 "Error-code extraction") →
   run the probe again with `n + 1` (no sleeping; the probe computes the next minute, rolling the
   hour and date with it) and retry, at most 5 tries in all (`n` = 0–4); a sixth duplicate, **any
   other exit 3** (e.g. `bad_cycle_id_hhmm`, a company mismatch, `test_mode_real_state`) or any
   other nonzero → exit 1 (internal) with the stdout line `gtm_session: cycle_open <n>:<code>`; then
   export `CLAUDE_GTM_RUN` — first, so the holder info below always carries the run id. **Every
   `cycle.py` call of this script** (`open` here, `missed` on a lease timeout, `sync`/`close` in (d)
   and on a lockf failure) runs through `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u
   CLAUDE_GTM_RUN`, because `cycle.py` refuses its lifecycle subcommands in session env (R62 to 03
   §3.12). K test: a stub `cycle.py open` reporting `duplicate_cycle` twice then 0 → the third
   probe offset (`n = 2`) is the opened id; a stub exiting 3 `bad_cycle_id_hhmm` → exit 1 on the
   first try (falsified by retrying every exit 3); (b) write holder info `leases/<slug>.json` `{"session_id", "pid",
   "started_at", "kind": "interactive|scheduled", "run_id"}` atomically, `run_id` never empty, `pid`
   = `$$` of the locked child (the ancestor of `claude` that `prove_gtm_session`'s ancestry walk
   looks for) — only the lock holder ever writes it, so a waiting session can never overwrite the
   live holder's info. K test: an interactive run's holder file has a non-empty `run_id` equal to
   the opened cycle's id;
   (c) **compose the `-p` text** (`--print` only): read `$5` (prompt files live under
   `R/schedules/prompts/`, which bash can read), replace each of the five run constants of §7.5
   (`<slug>`, `<home>`, `<run_id>`, `<session>`, `<start>`) with `$1`, `$9`, the run id, `$3` and the
   computed start, by bash quoted-pattern substitution only (`T=${T//"<home>"/"$9"}`; never `eval`,
   `sed` or a heredoc with the values), prepend the RUN CONTEXT header and the §8.2 tag rule, and
   write the result to a `mktemp` file (removed by the child's `EXIT` trap) that step 5 feeds to
   `claude` on stdin;
   then run `claude` (step 5) — without `--alarm`, in the foreground (interactive sessions, which
   need the TTY); with `--alarm N` (the runner always passes it, §7.2): `TMO=$(mktemp -d)` (removed by
   an `EXIT` trap), `set -m` so `claude` gets its own process group, start it in the background,
   start a watchdog subshell (`sleep N`, then `touch "$TMO/timed_out"` **before** `kill -TERM --
   -<claude pgid>`, `sleep 30`, then `kill -KILL -- -<claude pgid>`), `wait` for `claude`, then kill
   the watchdog and wait for it, and only then test the marker: **`$TMO/timed_out` present → the
   result is 142 whatever `wait` returned** (143 after TERM, or `claude`'s own code when it exited
   on its own at the moment the watchdog fired — a run that reached the alarm is a timeout);
   absent → `claude`'s own code. This keeps the timeout inside the locked child (F-alarm), so the
   whole `claude` process group — MCP servers included — is stopped, (d) still runs, and the lease
   is released when this child exits; nothing is orphaned holding it; (d) after `claude` exits
   (timeout included), for interactive **and** scheduled sessions, in this order:
   `perf_report.py record-session --company <slug> --run <run_id> --session $SESSION` (03_schemas.md §3.19; the
   known in-session blind spot is stated there); `python3 /Users/x/.claude/tools/gtm/act.py
   purge-untrusted --company <slug> --playwright-only` (plan §17 l: `.playwright-mcp/` page
   snapshots can hold customer PII, and for OtherCompany possibly PHI, so they go after **every**
   session — including interactive shadow runs, plan §14 P7, and every run while schedules are
   unloaded — not only after scheduled ones); for a pack with `regulated ∋ hipaa`, also the full
   `act.py purge-untrusted --company <slug>` (the 30-day transcript purge, plan §20.13: act.py
   itself purges, never depending on a schedule's load state); for an interactive run `cycle.py
   sync` + `cycle.py close --status completed|failed` — **`completed` exactly when `claude` exited
   0, `failed` for every other result** (any nonzero exit, and the 142 timeout) — (a scheduled run
   that timed out also runs `cycle.py close --cycle <run_id> --status failed`). K test: a fake
   interactive `claude` exiting 0 closes the cycle `completed`, one exiting 1 and one reaching
   `--alarm` close it `failed`. A failing purge prints one **stdout** line
   `gtm_session: purge exit <n>` and does not change the exit code (the runner's own purge, §7.2, is
   the backstop for scheduled runs). **Everything this script prints after `claude` starts goes to
   stdout, never stderr** (§7.2 "Log files": for a non-hipaa scheduled run stderr would otherwise
   land in `.err.log` and move the watchdog's START proxy; the runner routes this stdout to `.out.log`
   or the sink). Then, for a `--print` session only (its first tool call is §7.5 E0, which makes the
   path gate write the canary; an interactive session may make no tool call at all), the
   **env-canary check**: `R/.gtm_state/env_canary/$SESSION.json` absent → first `python3
   /Users/x/.claude/tools/gtm/runner_probe.py --session-tool-calls $SESSION` (WP-D: counts
   the `tool_use` blocks of this session's transcript, located through `transcript_index` (03_schemas.md
   §3.16), and prints `{"tool_calls": <n>|null}`, `null` when no transcript is found or readable;
   the mode's argv, output and exit set are defined once in §7.2 — a nonzero probe exit or
   unparseable output is treated as `tool_calls: null`).
   **Raise only when a tool call can have happened:** `claude` exited 0 or timed out (142), **or**
   `tool_calls ≥ 1` → `env -u CLAUDE_GTM_SESSION -u
   CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN notices.py write --company runtime
   --kind trust --severity urgent --title "GTM hooks did not see the session marker (<slug>)"
   --body "session <SESSION> left no env canary: the GTM hook controls may have been open (plan
   §20.13); scheduled runs stop at E0 until this is fixed" --dedupe-key env_canary:missing --push
   --created-by gtm_session --origin-company <slug>`; otherwise (`claude` exited nonzero — an auth or
   quota failure at start, a crash, an early exit — **and** `tool_calls` is `0` or `null`) → no
   notice, and the stdout line `gtm_session: no tool call (claude exit <n>)`, which the runner's
   heartbeat summary already reflects through the 100–127 row (so an out-of-credit account never
   raises a false tamper-class alarm); present → `env -u CLAUDE_GTM_SESSION -u CLAUDE_GTM_COMPANY -u
   CLAUDE_GTM_RUN python3 /Users/x/.claude/tools/gtm/notices.py resolve-owned --company
   runtime --dedupe-key env_canary:missing --resolution "canary seen <SESSION>" --created-by
   gtm_session`. Neither changes the exit code. K tests (each falsified by removing its clause): a
   fake `claude` run with `--print` that exits 0 and writes no canary → one urgent `trust` notice; a
   fake `claude` that exits 1 with no transcript tool call → no `trust` notice and the stdout line
   `gtm_session: no tool call (claude exit 1)`; one that exits 1 after a recorded tool call and no
   canary → one urgent notice; a later run whose fake `claude` writes the canary → that notice
   `resolved`;
   (e) exit 0 when `claude` exited 0, 142 on timeout, and
   otherwise `100 + min(n, 27)` for `claude`'s nonzero exit `n` (IMP-17: `claude`'s own codes — 1, 2,
   128+signal — can never collide with the reserved 1/13/64/75/77/142 the runner maps).
   K tests: with a fake `claude` that sleeps and spawns a child, `--alarm 2` → exit 142, both
   processes gone, `record-session` ran, and a second `lockf -t 0` on the lease succeeds at once; a
   fake `claude` that exits 0 exactly as the watchdog fires (marker written) → exit 142; a fake
   `claude` that writes `<home>/.playwright-mcp/page-x.yml` → no such file after an **interactive**
   `gtm_session.sh` returns, and none after the `--alarm` timeout path either; for a `hipaa` fixture
   pack the full `purge-untrusted` ran.
   **DECIDED HERE:** macOS ships `/usr/bin/lockf` (flock-compatible), not `flock`.
5. `claude --session-id $SESSION --strict-mcp-config --mcp-config <home>/.claude/gtm/mcp.json
   [--model <m>]`; with `--print`: `-p --setting-sources <none> --settings
   /Users/x/.claude/.gtm_state/scheduled_settings.$SESSION.json --permission-mode dontAsk
   --allowedTools <rule> <rule> … < <composed file>`.
   **No ambient allow rules (r6; DECIDED HERE — the scheduled-session hardening below rests on it).**
   Claude Code documents `--allowedTools` as **adding** to the settings `permissions.allow` rules, and
   this machine's settings carry wide ones (read with a JSON parse on 2026-09-28):
   `~/.claude/settings.json` allows `Bash(python3:*)`, `Bash(python:*)`, `Bash(rm -rf:*)`,
   `Bash(cp:*)` and `Bash(mkdir:*)`; CSA's `.claude/settings.json` allows bare `Bash`, `Bash(git:*)`
   and `Bash(gh:*)`; CSA's `.claude/settings.local.json` allows `Write`, `Edit`, `WebFetch`,
   `WebSearch` and bare `Agent`, with `defaultMode: auto`. Whether this CLI merges them into a `-p
   --allowedTools` session is **UNVERIFIED** (never executed); if it does, every scheduled session
   would hold `Bash(python3:*)` — so `python3 …/company.py unregister othercompany` (dropping
   OtherCompany from `gtm_slugs()` and every hook scope, the PHI gate included), arbitrary Bash, `gh`
   into the example-org organization that holds the OtherApp repo (plan §20.9a), and whole-tool
   `act.py`/`notices.py`/`cycle.py`/`backup_state.py` — defeating every prefix rule below. So the
   scheduled session is launched with **no ambient settings source at all**, and three independent
   controls stand behind that:
   (1) **Settings isolation.** `--setting-sources <none>` = the form probe f records as loading
       **none** of `user`, `project`, `local` (candidate: an empty value, `--setting-sources ""`;
       **UNVERIFIED** — if the CLI offers no such form, K uses the narrowest form probe f records
       and controls (2)–(3) carry the rest), plus `--settings
       /Users/x/.claude/.gtm_state/scheduled_settings.$SESSION.json`, generated per
       session in the locked child just before `claude` starts by `PY
       /Users/x/.claude/tools/gtm/scheduled_settings.py --session $SESSION --company
       <slug> --mode <m> --rules <rule> <rule> …` (WP-K; each rule one argv element). The file (0600,
       create-exclusive, removed by the locked child's `EXIT` trap after `claude` exits) holds exactly
       `{"hooks": <HEAD's hooks block>, "env": <HEAD's env block>, "permissions": {"allow": [<exactly
       the rendered rules, in order>], "deny": [<DENY>], "defaultMode": "<m>"}}`, where the `hooks` and
       `env` blocks are copied **verbatim** from `git -C /Users/x/.claude show
       HEAD:settings.json` (never the working tree, whose drift the settings guard heals only at
       session start) — dropping the user source would otherwise also drop G-A, G-B, G-W, gate-gtm
       and the path gate that writes the E0 canary. **`<DENY>` is never empty (DECIDED (wave1c):
       HEAD's deny list is copied, never dropped — `--setting-sources` none would otherwise also drop
       every ambient deny rule, e.g. Read of the gcloud ADC file, the Agency delegation config, the
       mcp-gdrive config and the Playwright pool state, `security find-generic-password`, `op item
       get`, `git push --force`, while the session holds `Read Grep Glob` and, off hipaa, web
       egress):** `<DENY>` = HEAD's `permissions.deny` array, **verbatim and in order**, then, for
       each of its `Read(…)`/`Edit(…)`/`Write(…)` rules whose path starts with a single `/`, the same
       rule with `//` (the absolute-path form, rule notes below — so the deny holds whichever way
       this CLI reads a single leading `/` from a settings file under `.gtm_state/`), then these GTM
       additions: `Read(//Users/x/.gtm_profiles/**)` (browser profiles holding every
       company's signed-in cookies), `Read(//Users/x/.config/**)`,
       `Read(//Users/x/.ssh/**)`, `Read(//Users/x/.claude/.gtm_state/scheduled_settings.*)`
       (duplicates removed, first occurrence kept). A HEAD with no `permissions.deny` array → the
       same exit 1 as a missing `hooks` object. A git failure, a HEAD `settings.json` with no
       `hooks` object, or a write failure → `gtm_session.sh` exits 1 (internal), no `claude`. The
       project's own hooks (e.g. CSA's formatter) are deliberately not loaded in a scheduled GTM
       session; G-W already confines it to `drafts/`. `--allowedTools` still carries the same list
       (so the list is identical whichever of the two the CLI honours).
   (2) **Hook backstop that does not depend on permission merging** (`requests/07_notices_schedules.md`
       R63 to 04_hooks.md §4.2): in GTM scope with `CLAUDE_GTM_RUN` of a **scheduled** kind, a new
       G-B rule `gtm-scheduled-bash-unlisted` reads
       `R/.gtm_state/scheduled_settings.<CLAUDE_GTM_SESSION>.json` (G-W denies GTM-scope writes
       there) and denies every Bash command that is not one simple command (no `;`, `&`, `|`,
       newline, backtick, `$(`, `<(` or `>(`; output redirections are judged by the R53 rule) whose
       text, leading whitespace stripped, either equals an exact rule's command or starts with a
       `…:*` rule's prefix followed by end of text or a space; a missing or unparseable file → every
       Bash command denied (fail closed in scheduled scope only; interactive GTM sessions are
       unaffected).
   (3) **`company.py` refuses its registry mutators in session env** (R63 to 00_global_paths.md
       §0.1 / `company.py`): `register`, `unregister` and `index` exit 3 `registry_in_session`,
       nothing written, whenever `CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is set — so leaving
       `company.py` off the list is no longer the only control.
   (4) **Probe f records the effective permission set** of a `-p` session started (a) with the
       operator's real user, project and local settings files and only `--allowedTools`, and (b)
       with this step's exact argv — which rules the session actually holds in each — and the
       `--setting-sources` form that loads none of them. Scheduled prompts ship only after (b) is
       recorded as holding exactly the rendered list.
   Tests (each falsified by removing its control; a scheduled fixture session run with the
   operator's **real** settings files in place, `CLAUDE_GTM_RUN` of kind `daily`): `PY
   /Users/x/.claude/tools/gtm/company.py unregister x` is denied (G-B) and, run directly
   in session env, exits 3 `registry_in_session` with the registry unchanged; `gh issue list` is
   denied; `rm -rf <home>/x` is denied and `<home>/x` still exists; a Write to `<home>/x.txt` (outside
   `drafts/`) is denied; a prefix-matched `PY …/notices.py list --company <slug> --json` is allowed;
   K test: the generated settings file's `hooks` equals HEAD's byte-for-byte after a JSON round
   trip, its `permissions.allow` equals the rendered `--allowedTools` list, its `permissions.deny`
   is a superset of `git show HEAD:settings.json`'s `permissions.deny` (and contains the GTM
   additions above), and a HEAD with no `hooks` block → exit 1 with no `claude` started; K/B test
   (falsified by writing `"deny": []`): in a scheduled fixture session a Read of
   `/Users/x/.config/gcloud/application_default_credentials.json` is denied. **Argv encoding (DECIDED HERE):** each rule of the list below is **one argv
   element** (bash array expansion `"${RULES[@]}"`, never one joined string, so a rule containing
   spaces such as `Bash(/opt/homebrew/opt/python@3.13/bin/python3.13 /Users/…/act.py:*)` is never split), all placed after
   `--allowedTools` and **last** on the command line; the composed prompt (step 4(c)) reaches
   `claude` on **stdin**, so no positional argument follows the variadic list for it to swallow.
   **UNVERIFIED:** that `-p` with the prompt on stdin and a variadic `--allowedTools` behaves so on
   this machine; probe f records the working form (this one, or a single comma-joined element), and
   its recorded form wins. K test: the rendered argv has exactly one element per rule and nothing
   after the last rule. **Never `acceptEdits`:** that mode auto-accepts file edits in the
   working directory whatever the allowlist says, and the working directory is the whole company
   home (for CSA, the whole application repo), so an unattended session could edit application code
   without a prompt, against plan §20.9c. `dontAsk` denies every tool not on the list without
   prompting — **but "the list" is the union of every allow rule the session holds**, which is why
   (1)–(4) above exist. **Permission mode is an allowlist, not a denylist (DECIDED HERE):** the mode is
   exactly `dontAsk`, or `default` **only if** probe f records that `default` under `-p` denies
   every tool not on the list without prompting; **every other mode is refused** — the installed
   CLI also offers `auto` (verified with `claude --help`: `acceptEdits`, `auto`,
   `bypassPermissions`, `default`, `dontAsk`, `plan`), in which a classifier approves tools that
   are not on the list, which would defeat the literal-command allowlist this design rests on.
   `gtm_session.sh` asserts it before starting `claude`: the value it is about to pass ∉
   {`dontAsk`, `default`} → exit 1 with the stderr line `gtm_session: permission mode <m> refused`.
   **UNVERIFIED:** how `dontAsk` (or `default`) interacts with `--allowedTools` under `-p` on this
   machine; probe f records which of the two runs the scheduled prompts unattended with only the
   list below, and its recorded mode wins **only within that set**. K test: the rendered argv's
   `--permission-mode` value ∈ {`dontAsk`, `default`}, and a script edited to pass `auto` exits 1
   before any `claude` start. **Output redirection (UNVERIFIED, recorded by probe f):** whether
   `-p --allowedTools 'Bash(PY X:*)'` admits `PY X … > <path>` (and `>>`, `&>`, `2>
   <file>`). Probe f records the answer; independently of it, 04_hooks.md's G-B must deny, in GTM
   scope, every Bash command carrying an output redirection whose target is not `/dev/null` or
   under `<home>/.claude/gtm/drafts/` (`requests/07_notices_schedules.md` R53), because the working
   directory of a CSA session is the whole application repo and a prefix-matched `python3
   /Users/x/.claude/tools/gtm/notices.py list --json > <home>/modules/billing/x.py`
   would otherwise write application code past R17's Write/Edit rule (`python3` there, as everywhere
   in this file's command forms, is the `PY` literal). **Three mechanical backstops that do not depend on the mode — all three now in 04_hooks.md
   (r5; `requests/04_hooks.md` R27 confirms):** (1) G-W denies, in GTM scope, every
   Write/Edit/MultiEdit/NotebookEdit outside `<home>/.claude/gtm/drafts/**` in a scheduled run
   (`gtm-write-outside-drafts`, 04_hooks.md §4.3, from R17; B1 test: a scheduled-session Edit of a CSA
   `modules/**` file is denied, a Write under drafts/ is allowed); (2) gate-gtm denies, when
   `CLAUDE_GTM_RUN` parses to a scheduled kind, every `Agent`/`Task` dispatch whose `subagent_type`
   is not in `system_names.GTM_SEATS ∪ DEPARTMENT_SEATS` (`gtm-nonroster-dispatch`, 04_hooks.md
   §4.6, from R19), so an injected scheduled session cannot dispatch `implement`,
   `general-purpose` or any other code-writing agent (plan §20.9c) — the prompt text and the K
   `implement`-word test constrain only what K writes, not what the model does; (3) G-B denies, in
   GTM scope, any Bash output redirection (`>`, `>>`, `&>`, `>|`, `N>` to a file) whose target is
   not `/dev/null` or under `<home>/.claude/gtm/drafts/` (the `redirect_targets` rule, 04_hooks.md
   §4.2, from R53; B test: `python3 …/notices.py list --json > <home>/modules/billing/x.py` from a
   scheduled session is denied and no file is written, `2> /dev/null` is allowed). Their text has
   landed; **their B tests green** remains a prerequisite below.
   **The one list of hard prerequisites (r5, complete; checked against 00–06 and the code).** K ships
   the scheduled prompt files, and D ships `run_gtm_job.sh`'s holds job and lease-probing backstop,
   only after every item of its list has landed with its tests green (§7.2's R16/R22 and R32
   orderings also apply to both):
   - **Scheduled prompts (K):** the three backstops above with their B tests (R17, R19, R53); R20
     and R36 as amended by R62 (02_act.md: `card`-notice resolution by `record-external`, the
     Meta-only `card_on_refuse` path — without them E1b on an informational card exits
     `card_subject_mismatch` and the notice never resolves); **R21** (02_act.md
     `gtmlib.chain.post_break_actions`, which E1's chain card needs); **R25** (04_hooks.md §4.4 env
     canary — today `env_canary` appears nowhere in 04, so every scheduled run would end at E0 and
     push an urgent `trust` notice); **R42** as amended by R56 and R62 (`read-run`'s `findings: true`
     branch, `ST/stops/`, `propose --stop`, `runaway-stops`, the new stopping rows, `status` `route`,
     `queue --owner-executable`, `duplicate_cycle`); R50, R57 and R59 (`pending-commits`,
     `--completed-before-hours`, `--since-last-daily`, `weekly_report.py` and its store); **R58**
     (`activity_log.py audit --ids-only`, which does not exist in today's `activity_log.py`); and
     `notices.py task` itself (WP-D); **R26 as amended by R57** (`status --unverified`, absent from
     02_act.md today); **R43** (the `queue` row keys, `status --review-brief`'s path-only stdout,
     `record-external` `card_unanswered` for a never-posted card, the `touchid:` notice dedupe); **the
     harvest session-env output narrowing** (`requests/07_notices_schedules.md` R64 amending R16/R63,
     §7.5 W2); **the `inbox_systems`/`--inbox`/`--all-in-scope` forms** (R64, §7.5 I2/W3); **r6 (all in `requests/07_notices_schedules.md` R63):** the
     settings isolation's `scheduled_settings.py` and probe f's recorded `--setting-sources` form and
     effective-permission-set result ((1) and (4) above), G-B's `gtm-scheduled-bash-unlisted` rule
     with its B tests ((2)), `company.py`'s `registry_in_session` refusal ((3)), the
     harvest hipaa-record hashing (§7.5 W2), act.py's `money_card_path_struck` refusal (§7.5 E1b);
     **for a hipaa pack additionally:** probe f's recorded answer on subagent tool inheritance
     (below), probe o's recorded osascript-from-launchd PASS (§7.1 push rule), and — for any lane
     dispatch in its inbox/weekly prompts — the lane-brief variant, its review binding and gate-gtm's
     `gtm-hipaa-brief-egress` rule (§7.5 I8); without them the hipaa prompts ship in the I8 route-(b)
     form. **R52 is not a prerequisite** (r5): the prompts ship in the
     plan-conformant form, and the [R52] lines are added only in the change that records R52's
     ratification in 08_seats_wps.md Appendix B (R61's earlier list, which named R52, is superseded
     by R62 and R64 — `requests/07_notices_schedules.md` R61 carries that note, so the two agree).
   - **Per prompt file (DECIDED (wave1c): each file waits for the forms it alone uses — safest
     option that keeps automation working, since a missing form would exit 2 on every run):**
     `gtm_inbox.txt` additionally requires **R43's `lead-append --from-agent <agent_id> --index <i>`**
     with its A1 tests (I5 is a scheduled run's only lead writer and may not use `--file`; without it
     I5 exits 2 every run and no lead reaches the sink, against plan §5 and the §6.8 lead-capture
     exemption). `gtm_monthly.txt` additionally requires **R43's `backup_state.py --restore` JSON
     `result.counts` and R60's `--latest`** and ships only **with** M1 in it — never without its
     restore check (plan §5 monthly row, §3.2); until both land, `gtm_monthly.txt` is not installed
     and the company's `monthly` plist is not loaded. **Coverage check (wave1c):** every §7.5
     command form absent from today's 02_act.md is on these lists — `lead-append --from-agent`
     (R43), `runaway-stops` and `propose --stop` (R42/R56/R62), `pending-commits` (R50), `queue
     --owner-executable` (R62), `status --unverified --completed-before-hours` (R26/R57), `status
     --review-brief --lane-variant` (R63, hipaa lane route (a) only), `ticket --read --inbox` /
     `--all-in-scope` (R64); `queue --stops-only` appears only on [R52] lines; `pacing --all`,
     `purge-untrusted --hipaa-only`/`--age-only`/`--if-lease-free` are the runner's (next item).
   - **`run_gtm_job.sh` holds job and backstop (D):** **R41** and **R49** (`purge-untrusted --all
     --hipaa-only --age-only` and `--playwright-only --if-lease-free`, neither in 02_act.md yet),
     **R56** as amended by R62 and R64 (`act.py pacing --all` with in-process `_build_ctx` reads, and — R64 — its in-process `propose --stop` + `authorize` of each stored stop), R35/R54
     (`--if-running`), `notices.py prune`, and the `duplicate_cycle` code (R62); **and, while any
     hipaa pack is registered, probe o's recorded osascript-from-launchd PASS** (§7.1 push rule).
   - **`notices.py resolve --operator` (D):** R45 as amended by R63 (the `notice_resolve` operator
     marker in 02_act.md §2.3 and `OPERATOR_OK_COMMANDS`); until it lands the flag always refuses
     `operator_marker_missing` (§7.1). Before those land
     each call would exit 2, and a silent retention lapse is exactly what §7.2's `failed` holds
     heartbeat and `purge_failed:all` notice now surface — but the job is not loaded until they have
     landed.
   Until its list is complete, scheduled prompts are not installed (GTM runs are interactive only)
   and `com.oversight.gtm.holds` stays unloaded. The
   list =
   - `Read Grep Glob ToolSearch`, plus `PushNotification WebFetch WebSearch` **only when the pack
     does not have `regulated ∋ hipaa`** — a hipaa pack's scheduled session reads DM, review and
     lead text through its seats, so it gets no egress tool of its own: no web tools (plan §20.13;
     its research runs in interactive sessions) and no `PushNotification`, a relay outside the
     machine (plan §20.5.6; §7.1 push rule, §7.5 E7). **This variant constrains only the
     orchestrator's own list.** The seats it dispatches keep, or inherit, their own grants (probe f,
     below), and two lane seats (content-strategist, local-presence-architect) hold Bash, WebFetch
     and WebSearch in their agent files — so on a hipaa pack no attacker-writable DM/review body and
     no PHI may reach them: they receive lane briefs only, and until those exist they are not
     dispatched from a scheduled session at all (§7.5 I8 routes (a)/(b), a recorded plan §20.13
     amendment, R63; gate-gtm's `gtm-hipaa-brief-egress` rule is the mechanical control). K test: the
     rendered list for a hipaa fixture pack contains none of `PushNotification`, `WebFetch`,
     `WebSearch`, and for a non-hipaa pack contains all three;
   - `Agent(<type>)` for each `<type>` in `system_names.GTM_SEATS ∪ DEPARTMENT_SEATS` — never a bare
     `Agent` (K test: the rendered list equals that union exactly, and contains no bare `Agent`);
     **UNVERIFIED:** whether `-p --allowedTools` honours per-type `Agent(<type>)` rules; probe f
     records it, and if it does not, (2) above is the only control, which is why K's prompts wait for
     R19;
   - `Write(//<home without its leading />/.claude/gtm/drafts/**)
     Edit(//<home without its leading />/.claude/gtm/drafts/**)` — the `//` form, because in a
     permission rule a single leading `/` means relative to the settings source, not the filesystem
     root (for OtherCompanyB: `Write(//Users/x/Desktop/OtherCompanyB/GTM/.claude/gtm/drafts/**)`)
     (card bodies for `act.py card-post --file`; notices take no file, §7.1 `notices.py task`) — the session's
     only write scope. **UNVERIFIED:** which form `--allowedTools` matches on this machine; probe f
     records it (the `//` form, or `./.claude/gtm/drafts/**` relative to the home cwd) and its
     recorded form wins. K test: a `-p` fixture session under `dontAsk` with this list writes one file
     under drafts/ (so an I5 lead row can never be silently denied, plan §5). **No** Write/Edit grant on the operator-input file (F5): cards are
     posted with `act.py card-post`, which can only append under `## Open` (02_act.md §2.4), and G-W denies
     GTM-scope writes to that file (04_hooks.md §4.3);
   - the `mcp__playwright-gtm__<tool>` names, **enumerated, never a wildcard**: exactly the union
     of every `mcp__playwright-gtm__…` name granted in the `tools:` frontmatter of the agent files of
     `system_names.GTM_SEATS` (today only the ticket-holding seats `gtm-analyst` and
     `gtm-operator` hold any), rendered sorted. **Why the orchestrator carries them at all:** it
     never browses itself, but probe f has not yet recorded whether a subagent dispatched from a `-p`
     session inherits the parent's `--allowedTools`; if it does, a seat whose browser tools are not
     on the parent's list could not browse. If probe f records that subagents keep their own agent-
     file grants, K drops this entry (the orchestrator then holds no browser tool). K test: the
     rendered set equals that union computed from fixture agent files, contains no `*`, and a seat
     file gaining a tool changes the rendered set;
   - **subcommand-prefix rules, never whole-tool `:*` rules for a tool with an admin or destructive
     subcommand (r5).** For each prefix `P` below, **both** `Bash(<PY>
     /Users/x/.claude/tools/gtm/P:*)` and `Bash(<PY> ~/.claude/tools/gtm/P:*)`, where
     `<PY>` is the literal `/opt/homebrew/opt/python@3.13/bin/python3.13` (= `gtm_env.TRUSTED_PYTHON`,
     §7.2 "Interpreter pin"; never a bare `python3`, which the ambient `Bash(python3:*)` rule would
     otherwise shadow), with `<slug>`/`<home>`/`<run_id>` substituted by `gtm_session.sh` (the list is rendered
     per session):

     | tool | prefixes granted (exactly these; every §7.5 command form matches one) |
     |---|---|
     | `act.py` | `act.py queue`, `act.py run-holds --company`, `act.py ticket`, `act.py ingest-findings`, `act.py snapshot`, `act.py lead-append --company`, `act.py read-run`, `act.py record-external`, `act.py propose --company`, `act.py status`, `act.py review`, `act.py authorize`, `act.py execute`, `act.py complete`, `act.py verify`, `act.py card-post`, `act.py chain-repair`, `act.py runaway-stops`, `act.py pending-commits`, `act.py purge-untrusted --company <slug>` |
     | `notices.py` | `notices.py list`, `notices.py card-draft`, `notices.py card-mark`, `notices.py task`, `notices.py resolve --company <slug> --notice` (never `write`, `resolve-owned`, `render`, `push`, `prune`) |
     | `cycle.py` | `cycle.py add-artifact`, `cycle.py add-metric`, `cycle.py add-dispatch` (annotation only; never `open`/`missed`/`sync`/`close`, which the tool also refuses in session env, R62) |
     | `backup_state.py` | `backup_state.py --company <slug>` (W8) and `backup_state.py --restore --latest --company <slug> --to <home>/.claude/gtm/drafts/restore_check/<run_id>` (M1; rendered per session with this run's `<run_id>`, so M1's command — which continues `restore_check/<run_id> --runtime-state-to …` — is the prefix followed by a space; a prefix ending at `restore_check/` would be followed by `<run_id>`, not a space, and G-B's `gtm-scheduled-bash-unlisted` would deny M1 on every monthly run) — and, because a prefix cannot pin the later `--runtime-state-to`, `backup_state.py` itself refuses in session env any `--restore` whose `--to` or `--runtime-state-to` does not resolve inside `<home>/.claude/gtm/drafts/restore_check/` (exit 3 `restore_target_denied`, R62), so a session can never roll back the live `actions.jsonl` with its chain anchor, the nonce ledger or the tickets |
     | `activity_log.py` | `activity_log.py render --company`, `activity_log.py audit --company` |
     | `ai_budget.py` | `ai_budget.py state --company`, `ai_budget.py usd --company`, `ai_budget.py caps --company` |
     | `autonomy_ladder.py` | `autonomy_ladder.py status --company`, `autonomy_ladder.py promote --company`, `autonomy_ladder.py shadow-exit --company` |
     | `outside_actor.py` | `outside_actor.py reconcile --company` |
     | `scoreboard.py` | `scoreboard.py add --company` |
     | `perf_report.py` | `perf_report.py --company` (W7; never `record-session`, which only `gtm_session.sh` runs) |
     | `validate_run.py` | `validate_run.py --company` |
     | `weekly_report.py` | `weekly_report.py --company` |
     | `transcript_index.py` | `transcript_index.py refresh` |
     | `kb_freshness.py` | `kb_freshness.py --json` |
     | `approval_sig.py` | `approval_sig.py --trust-check` |
     | `exit_contract.py`, `metrics.py`, `experiments.py`, `mission_record.py` | whole tool (`<tool>:*`) — no §7.5 step runs them; they are here only so a director or specialist that inherits this list (probe f) can record and evaluate its mission (`exit_contract.py` because W5's convergence verdict comes only from it). **UNVERIFIED:** that none of the last three has an admin or cross-company subcommand in session env; R62 asks their owning WPs to state it, and K replaces each `:*` with that tool's subcommand prefixes, or drops the tool if probe f records that subagents keep their own grants |

     **Dropped from the scheduled list (r5):** `company.py` (no §7.5 step uses it, and its
     `register`/`unregister`/`index` mutate the machine-wide GTM registry and identity index — an
     injected run could `unregister othercompany`, dropping it from `gtm_slugs()` and every hook scope,
     or `register x --root <Agency path>`; leaving it off the list is **not** the only control since
     r6: the settings isolation, G-B's `gtm-scheduled-bash-unlisted` rule and `company.py`'s own
     `registry_in_session` refusal, (1)–(3) above, each stop it independently) and `secret_sink.py` (setup only,
     E5, interactive). K test (each falsified by re-adding the rule): the rendered list contains no
     `company.py`, no `secret_sink.py`, no `:*` rule for `act.py`, `notices.py`, `cycle.py`,
     `backup_state.py` or `perf_report.py` whole, no `notices.py write` or `notices.py resolve-owned`
     prefix, and no `cycle.py open`/`missed`/`sync`/`close` prefix; every command string of every
     prompt file, after substitution, matches at least one rendered rule **under exactly G-B's
     `gtm-scheduled-bash-unlisted` semantics** (equal to an exact rule's command, or a `…:*` rule's
     prefix followed by end of text or a space — never a plain `startswith`; falsified by rendering
     the M1 prefix without `<run_id>`);
   - for `harvest_tool_trail.py`, **only the exact no-argument command** — `Bash(<PY>
     /Users/x/.claude/tools/gtm/harvest_tool_trail.py)` and `Bash(<PY>
     ~/.claude/tools/gtm/harvest_tool_trail.py)` (`<PY>` as above), with **no** `:*` suffix — because
     `harvest_tool_trail.resolve_transcript_paths` lets explicit argv paths win over its default
     globs, so a `:*` grant would let an injected scheduled session harvest any transcript (Agency's
     included) into company trails; `harvest_tool_trail.py` itself also refuses positional paths
     (exit 2, nothing written) when `CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is set
     (`requests/07_notices_schedules.md` R16 as amended). K test: the rendered list has no
     `harvest_tool_trail.py:*` rule; test with R16: a session-env harvest given an explicit transcript
     path exits nonzero and writes no trail line.
   **UNVERIFIED:** whether subagents dispatched from a `-p` session inherit the parent's
   `--allowedTools` or keep their own agent-file grants. Probe f must record the answer in plan §17
   before K ships the scheduled prompts; until then K's prompts must not depend on a specialist's
   WebFetch/WebSearch/Bash working in scheduled runs (their research runs in interactive sessions),
   and the list above already includes `exit_contract.py` (and, for non-hipaa packs,
   WebFetch/WebSearch) so a subagent inheriting it still works; a hipaa pack's scheduled seats get no
   WebFetch/WebSearch if they inherit, and keep their agent-file grants (Bash/WebFetch/WebSearch for
   both lane seats) if they do not — the case §7.5 I8's lane-brief rule and gate-gtm's
   `gtm-hipaa-brief-egress` rule are written for, so no hipaa inbox prompt ships before this is
   recorded. The weekly prompt's W5 depends on probe f's answer: if subagents keep
   their own grants, the director's agent-file grant must cover `exit_contract.py`.
   Probe f's recorded flags win if they differ.
6. Every home's `.claude/gtm/mcp.json` (WP-M) holds exactly one browser server:
   `{"mcpServers": {"playwright-gtm": {"command": "npx", "args": ["@playwright/mcp@0.0.76",
   "--user-data-dir", "/Users/x/.gtm_profiles/<slug>", "--browser", "chrome",
   "--output-dir", "<home>/.playwright-mcp"]}, "<read-only servers>": {"command":
   "/Users/x/.claude/tools/gtm/mcp_launch/<server>.sh", "args": ["--company", "<slug>"]}}}`
   — headed (no `--headless`), never `--isolated`, absolute paths, no `env` secrets. **Version pin
   `0.0.76`** (r5; `requests/04_hooks.md` R17): the version `live-testing/browser_pool.py`'s
   `_DEFAULT_MCP_VERSION` and `.mcp.json` pin and whose tool names 04_hooks.md §4.1 classifies
   (`browser_run_code_unsafe`, `browser_network_request`, `browser_drop` do not exist in 0.0.70);
   04's P2 test asserts the three version strings are equal, and K's mcp.json test reads the same
   constant. Every browser
   account in the pack uses `credential_ref: "browser:playwright-gtm"` (06_connectors.md §6.3, 08_seats_wps.md Appendix C item 16).

**`gtm_session.sh` exit codes (I15, IMP-17):** 0 `claude` exited 0; 1 internal (a step of the
script itself failed before `claude` started: `uuidgen`, the step-1 `runner_probe.py` call, the
holder-info write, a `cycle.py open` error other than the `duplicate_cycle` retries of step 4(a) (or
a sixth duplicate), an unreadable home (incl. `company.py resolve`
exit 1 `home_unreadable`), a permission mode outside {`dontAsk`, `default`} (step 5), a failure to
generate the scheduled settings file (step 5 (1)), or a lockf failure other
than 75 — its own 64/70/71/73, step 4; once `claude` has run, its outcome decides the
exit); 13 not a GTM company (`is-gtm`) or company resolution; 64 test env set, `CSA_DISABLE_HOOKS`
set (non-empty, not `0`), a `python3` older than 3.11, bad `--session-id`, or bad arguments (incl.
`--paused` without both `--scheduled` and an `inbox`, `daily`, `weekly` or `monthly` `--run`) — always with the one
`gtm_session: <token> …` stderr line of step 1 (`test_env`, `hooks_disabled`, `python_too_old`,
`bad_session_id`, `bad_paused`, `bad_args`), which the runner copies into its heartbeat (§7.2); 75 lease held/timeout; 77 unsigned AI caps (`--scheduled` only);
100–127 `claude` exited nonzero (`100 + min(n, 27)`); 142 `--alarm` timeout (session stopped, lease
released, spend recorded). Usage stays 64, not the act.py-style 2, because the runner's table
(§7.2) and plists already key on it. K test: a fake `claude` exiting 1, 13 and 143 yields 101, 113
and 127, and never 13/64/75/77/142; no path of the script exits 70, 71 or 73. `gtm_cancel.sh` / `gtm_approve.sh`: 05_approver.md §5.4.
