# Security policy

This repository is hooks, gates, agent definitions and scripts that run on your machine, inside your
Claude Code sessions. A flaw in a gate is a flaw in a safety control, so security reports are taken
seriously even though this is a one-person project.

## What counts as a security issue

Report these privately (see "How to report"):

- **A gate bypass.** A command, tool call or sub-agent dispatch that a gate documents as blocked (in
  enforcing mode) but that gets through, using an input an agent, or content an agent is reading, could
  produce: a quoting or heredoc trick, command substitution, an aliased or reordered verb, an escape
  variable smuggled into the command text, a pathspec the review gate resolves differently from git.
  The gates and their verdicts are described in
  [`docs/subsystems/gate-chain.md`](docs/subsystems/gate-chain.md).
- **A fail-open that should fail closed.** Gates fail open on their own internal errors by design: a
  crashing safety hook must never be worse than no hook. The documented exceptions fail closed, for
  example a git or gcloud command segment the tokenizer cannot parse, or a pathspec the review gate
  cannot resolve. A way to turn one of those into an allow, or to make a fail-closed gate error out
  into an allow with input an attacker controls, is a vulnerability. (A gate you believe *should* fail
  closed but is documented as failing open is a design discussion: open a normal issue.)
- **Secret leakage through a hook.** A hook, log row, ledger, telemetry file, redaction filter or
  script that writes, prints or sends a credential, token or private datum it should not. A miss in
  the browser-output redaction (`hooks/redact_browser_phi.py`) is in this class.
- **A redaction miss in this repository.** The public tree is produced from a private working tree by
  an automated export that redacts names, hosts and identifiers and runs a forbidden-pattern check. If
  a real credential, personal data, a customer- or company-identifying detail, or an internal hostname
  got through, report it privately instead of quoting it in a public issue. Say where it is; do not
  paste the value, and do not use a credential you find.
- **A safety rail that fails.** Scripts that delete or overwrite files carry rails, for example
  `scripts/ci_layout.sh` (refuses to act on or inside a real `~/.claude`) and `scripts/disk_janitor.sh`
  (deletion guards). A way to make one act outside its intended directory is in scope, as is unsafe
  handling of untrusted input in shipped code, such as path traversal when restoring an archive
  (`tools/gtm/backup_state.py`).

## How to report

Use GitHub's private vulnerability reporting: open this repository's **Security** tab and choose
**Report a vulnerability**. The maintainer is enabling that feature for the repository; if the button
is not there yet, use the private contact route published in
[`SUPPORT.md`](SUPPORT.md#security-issues) instead. Do not open a public issue, pull request or
discussion for anything above, and do not post it to a social account.

Include, as far as you can:

- the file or module, and the commit of this repository you tested;
- whether the gate was enforcing (a `~/.claude/.enforce` file, `CSA_ENFORCE=1`, or a
  `.claude/.csa-enforce` marker file at the root of the repository the command ran in) or in its default
  log-only mode;
- the smallest reproduction: the exact command, tool call or payload;
- what the gate should have done and what it did;
- the impact you think it has, and a fix idea if you have one;
- whether you plan to publish, and by when.

## What to expect

- **Acknowledgement within 72 hours.** This is the one response-time commitment the project makes;
  the "no SLA" statement in [`SUPPORT.md`](SUPPORT.md) applies to everything else.
- After triage you get a plain answer (confirmed, not reproducible, out of scope) and a plan. There is
  no fixed fix time: a bypass of an enforcing gate is worked first, but one person is doing the work.
- Fixes land on the default branch and in the next tagged release. Only the latest release and the
  default branch are supported; older tags are not patched.
- Disclosure is coordinated with you. A fix is published with a note under "Security" in
  [`CHANGELOG.md`](CHANGELOG.md), and you are credited by name or handle unless you prefer not to be.

Please test on a throwaway `$HOME`, never on a machine whose `~/.claude` you care about and never
against anyone else's systems; `scripts/ci_layout.sh` builds one (see [`CONTRIBUTING.md`](CONTRIBUTING.md)).
Good-faith testing under these terms is welcome.

## Out of scope

- Anything that needs the person running the agent to turn a control off first: removing a hook from
  `settings.json`, deleting an enforcement marker (`~/.claude/.enforce` or a repository's
  `.claude/.csa-enforce`), or setting the documented escape variables themselves. The hooks are a guardrail for agents, not a sandbox against a user with a shell.
- Log-only mode not blocking. It is the documented default; the Bash and Task gates only record a
  `would-block` row and allow the command.
- Gaps already listed under "Known gaps" in [`CHANGELOG.md`](CHANGELOG.md), such as the Bash gates
  (1, 2, 3, 3b, 3c and 4) not looking inside `bash -c`, `sh -c` or `eval` strings, so a wrapped commit
  skips the pathspec, review and claim checks. They are known and tracked; a *new* way past a documented
  gate is still in scope.
- A rule that exists only as prose (an agent definition, the operating contract) being ignored by a
  model. That is a known limit of prompt-level rules and the reason the hooks exist.
- Flaws in Claude Code itself, Anthropic's services, git, GitHub or Python: report those to their
  owners.
- Behaviour of forks or modified copies, and of platforms the project does not claim to support (see
  "Status and caveats" in [`README.md`](README.md)).
- Reports with no demonstrated path to a bypass, a leak or a destructive action, and raw output from an
  automated scanner without a working reproduction.

Not sure whether something is in scope? Report it privately; it is easier to downgrade a report than
to un-publish one.
