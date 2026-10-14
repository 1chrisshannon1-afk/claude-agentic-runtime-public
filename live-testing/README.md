# live-testing

Policy and tooling for letting an agent drive a real browser without letting it
touch anything it should not. In the published repo this directory is three things (two files ship;
`allowlist.json` is the one you create), plus a `tests/` folder for the pool. A maintainer's own
checkout carries more private files that are not published.

| File | What it is |
|---|---|
| `allowlist.json` | The machine-readable, default-deny policy. Per machine, never published. |
| `allowlist.example.json` | A generic seed for `allowlist.json` (localhost and `example.com` only). |
| `browser_pool.py` | Leases, renews and releases the numbered Playwright MCP slots. It reads the policy, but it does not launch slots with origin flags today (`_server_entry_numbered` computes them and discards them), so the hook below is the only origin control. |

The guard that enforces the policy is `hooks/block_prod_mutations.py`, a
`PreToolUse` hook registered on the `mcp__playwright.*` tools. It reads
`allowlist.json` on every call. Like the other gates it only blocks when
enforcement is on (`~/.claude/.enforce` exists, `CSA_ENFORCE=1`, or the project
carries a `.claude/.csa-enforce` marker); otherwise it records what it would
have denied and lets the call through. `CSA_DISABLE_HOOKS=1` turns it off
entirely.

## The allowlist

`allowlist.json` is a single JSON object. The hook ignores every key that starts
with `_`; those are documentation, except `_example`, which only the test suite
reads (see below). The rest are read like this:

| Key | Meaning | Read by |
|---|---|---|
| `allowed_origins` | Origin patterns an agent may talk to: scheme and host, shell-style `*` wildcards, optional port (`http://localhost:*`, `https://app.example.com`). A write to a host that matches none of them is denied. Never add a bare `https://*`: it turns the allowlist into a blocklist, and the test suite pins that it stays out. | hook (R0, R4) |
| `denied_action_patterns` | URL globs that a write may never reach, whatever the host policy says (`https://*.stripe.com/*`, `*/admin/*`). Only non-GET, non-HEAD methods are checked. The request URL is canonicalized first (case, port, dot segments, duplicate slashes, percent-encoding, backslashes, control characters), so a respelled URL does not slip past. The pattern is only lowercased, so write it in canonical form: no default port, no dot segments, no duplicate slashes, no percent-encoding. A pattern such as `https://app.example.com:443/api/billing/*` never matches anything. | hook (R1) |
| `allowed_company_tenants` | Tenant ids an agent may touch. A request to a tenant-scoped host whose URL carries any other tenant id (`/companies/<id>`, `/company/<id>`, `/c/<id>`, `/tenant/<id>`, `/tenants/<id>`, or a `company`, `company_id`, `companyId`, `tenant`, `tenant_id` or `tenantId` query parameter) is denied. | hook (R2) |
| `test_recipients` | `emails` and `phones` (E.164) that messages may be sent to. A write to an app-side comms path (`/send-email`, `/sms`, `/messages`, `/notify`, `/invite`, ...) is denied unless every recipient it names is listed, and is denied outright when it names none. A write to a messaging provider that matches a `denied_action_patterns` entry is already denied by R1, whatever its recipient, so listing a recipient never opens a provider. | hook (R3) |
| `read_only_hosts` | Bare hostnames (no scheme, no port) of production app hosts. On a slot whose last `browser_navigate` landed on one of them, or that has navigated nowhere, every interaction-class Playwright tool (click, type, fill, evaluate, upload, drag, and any tool the hook does not recognise as read-only) is denied. Navigation, snapshots, screenshots, waits and tab listing still work. One fixed session-banner snippet is exempt on `browser_evaluate`. | hook (R5) |
| `interactive_production_hosts` | Optional narrow re-opening of interaction on a read-only host. Maps a host to `{"tenants": [...], "allowed_paths": [...], "allowed_path_prefixes": [...]}`. Interaction is allowed only when the slot's recorded path is `/c/<tenant>/...` for a listed tenant and is exactly one of `allowed_paths` or under one of `allowed_path_prefixes`, and the slot must navigate again before each further interaction. `browser_run_code_unsafe`, `browser_file_upload` and `browser_drag` stay denied, and so does every `browser_evaluate` except the session-banner snippet. Empty by default. | hook (R5) |
| `third_party_form_hosts` | Exact hostnames of third-party form hosts for a project-level hook that implements a form-submission carve-out. The runtime hook does not read it. Leave empty unless you wrote such a hook. | project hooks only |
| `_environment_policy` | Prose rules for the agents themselves: staging is the default target, production only on an explicit human go-ahead, no real tenants in staging. Agent definitions point at it. | agents |
| `_example` | `true` tells the test suite this file is a seed copied from `allowlist.example.json` (edited or not), not the maintainer's live policy. Keep it. See "What `_example` does to the test suite" below. | the test suite; the hook ignores it |

The rules, in the order the hook applies them to a request that carries a URL:

- **R1** a write matching `denied_action_patterns` is denied.
- **R2** a request to a tenant-scoped host carrying a tenant id outside `allowed_company_tenants` is denied.
- **R3** a write to a comms endpoint with a recipient outside `test_recipients` (or none) is denied.
- **R0/R4** a read (GET, HEAD) is allowed; any other method is allowed only on an `allowed_origins` host.

**R5** is separate: it judges Playwright tools that carry no URL (click, type,
fill, ...) from the host of the slot's last `browser_navigate`, and denies an
interaction-class tool on a read-only host or on a slot with no recorded host.

A URL the hook cannot confidently parse is denied if it is a write. If the policy
file is absent, unreadable or not a JSON object, the loader returns `{}`, and
the hook then denies every write and every interaction-class browser tool. It
never falls back to the example.

One thing the example cannot do for you: R2 only polices the hosts listed in
`_TENANT_SCOPED_HOST_SUFFIXES` in `hooks/block_prod_mutations.py`. Out of the box
that is the loopback spellings (`localhost`, `127.0.0.1`, `::1`, ...) plus the
original author's own app hosts; your hosts are not in it. To have a request to
your own app host rejected for an off-list tenant id, add that host to the
tuple. Until you do, `allowed_company_tenants` has no effect on it, and
the other rules (R1, R3, R4, R5) are what protect it.

## Creating `allowlist.json` from the example

A fresh install has no `allowlist.json`, and the hook must not guess one. For now
you create it yourself, explicitly, from `allowlist.example.json`:

```sh
cp live-testing/allowlist.example.json live-testing/allowlist.json
```

Run it once, when `allowlist.json` does not exist yet (`cp` overwrites an existing
file). Nothing seeds it for you today: `scripts/init_repo.sh` scaffolds a product
repo's `.claude/` directory and seeds the per-machine files under `knowledge/`,
and does nothing with `live-testing/`. An installer that copies the example only
when `allowlist.json` is absent, says so on stdout and never overwrites an
existing one will seed it in a later release.

What the unedited seed does and does not stop:

- It denies any write (non-GET, non-HEAD) to a host outside its listed origins,
  and any write matching `denied_action_patterns`.
- It denies interaction-class tools (click, type, fill, evaluate, ...) on
  `app.example.com`, `api.example.com`, and any slot that has navigated nowhere.
- It does NOT limit navigation (GET) to any host, with one exception: R2 still
  denies a GET whose URL carries an off-list tenant id on a host R2 polices, which
  out of the box means the loopback hosts plus the original author's app hosts. And it does NOT limit clicking and
  typing on any host outside `read_only_hosts`.

So it is a harmless starting point and no protection for real hosts until you
tailor it. Above all, list every production host you can reach in
`read_only_hosts`.

## Tailoring it

1. Replace `app.example.com`, `api.example.com` and `staging.example.com` in
   `allowed_origins` with the hosts you actually test against. Keep the
   `http://localhost:*` and `http://127.0.0.1:*` entries for local work.
2. List every production app host in `read_only_hosts` (bare hostname). Staging
   hosts stay out of that list: they are where interaction is meant to happen.
3. Replace `example-tenant` in `allowed_company_tenants` with your test tenant
   ids only. A real customer's tenant does not belong here.
4. Replace the entries in `test_recipients` with mailboxes and numbers you own.
5. Keep the provider and `*/admin/*` entries in `denied_action_patterns` and add
   the billing, messaging and admin endpoints of your own stack.
6. Add your hosts to `_TENANT_SCOPED_HOST_SUFFIXES` in the hook if you want the
   tenant guard on them (see above).
7. Rewrite `_environment_policy` and `notes` to describe your environments.
8. Leave the `_example` key in place unless you also replace the maintainer's
   pinned-policy tests (see the last section). The hook ignores it; it only
   tells the test suite that this file is not the maintainer's live policy.

Check the result by asking the hook's own loader and decision function, from the
root of your install (`~/.claude`):

```sh
python3 - <<'EOF'
import sys
sys.path.insert(0, "hooks")
import block_prod_mutations as bpm

policy = bpm.load_allowlist()  # {} means absent, unreadable or not a JSON object
print(sorted(policy) or "EMPTY POLICY: every write will be denied")
for method, url in [
    ("GET", "http://localhost:3000/"),
    ("POST", "https://api.stripe.com/v1/charges"),
    ("POST", "https://unlisted.example.org/x"),
]:
    print(method, url, bpm.policy_decision(method, url, allowlist=policy))
EOF
```

The `hooks/check_safety_core_parity.py` checker also flags a missing or
unparseable `allowlist.json` and any missing required key (`allowed_origins`,
`allowed_company_tenants`, `test_recipients`, `denied_action_patterns`).

## What `_example` does to the test suite

`hooks/tests/test_block_prod_mutations.py` has two kinds of test:

- **Logic tests** run on a hermetic policy defined in the test file itself, so
  they behave the same on every machine. This includes the host-spelling,
  admin-path, control-character and dot-segment families.
- **Pinned-policy tests** load `live-testing/allowlist.json` and assert the
  maintainer's own live policy: specific hosts, tenants, patterns and
  production-host entries, and the same logic vectors replayed against those
  real hosts. They are drift guards for that one file.

The pinned-policy tests are skipped, with a printed reason, when
`allowlist.json` is absent or carries `_example: true`. They are never silently
passed: with the file absent and the skip removed, they fail loudly. If you
delete `_example`, they run against your file and fail wherever your values
differ from the maintainer's, which is expected. So keep the marker, even in a
tailored file, unless you maintain a fork and replace those assertions with
pins of your own; with the marker in place the default run stays green.

```sh
python3 -m pytest hooks/tests/test_block_prod_mutations.py -q -rs
```
