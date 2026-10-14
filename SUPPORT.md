# Support

This is a free, open-source project maintained by one person alongside running a company. There is
**no SLA** — no guaranteed response time, no guaranteed fix time, no guaranteed anything — except the 72-hour
security acknowledgement in [`SECURITY.md`](SECURITY.md).

## Found a bug, or a gate that doesn't fire the way it's documented?

Open a [GitHub issue](https://github.com/1chrisshannon1-afk/claude-agentic-runtime-public/issues). Useful bug reports include:

- The gate/hook module involved (e.g. `hooks/precommit_review_gate.py`).
- The exact command you ran and what you expected vs. what happened.
- Whether enforcement is on (`~/.claude/.enforce`, `CSA_ENFORCE=1`, or a per-repo `.claude/.csa-enforce`;
  log-only vs. enforcing mode changes behavior — see
  [`docs/subsystems/gate-chain.md`](docs/subsystems/gate-chain.md)).
- Your OS — this system is macOS-tested only; a Linux/WSL-specific bug is real and welcome, but may
  sit longer before anyone with that environment can reproduce it.

Pull requests are welcome, especially test additions. If you're proposing a new gate or changing an
existing one's behavior, include the test file changes in the same PR — every gate in this repo
ships with its own test file, and that convention isn't optional for a new one.

## Want it installed and tuned for your team?

That's a paid engagement, not a support request. What is offered, and what it costs, is in
[`docs/consulting.md`](docs/consulting.md); or contact
[@1chrisshannon1-afk](https://github.com/1chrisshannon1-afk) (email on the profile) directly.

## What you should not expect

- A response within any particular timeframe (except the 72-hour security acknowledgement in
  [`SECURITY.md`](SECURITY.md)).
- Support for a fork, a heavily modified copy, or a different agent runtime that happens to share a
  file with this one.
- Verification against Windows or Linux — patches that add it are welcome; claims that it "should
  work" without someone having run it are not something I can back.
- Live debugging of your specific production incident. If your team needs that, that's the paid
  engagement in [`docs/consulting.md`](docs/consulting.md), not a free GitHub issue.

## Security issues

If you find something that looks like a real security hole (not "this gate could theoretically be
bypassed by an agent that ignores its own instructions," which is a known, stated limitation of
prompt-level enforcement in general) follow [`SECURITY.md`](SECURITY.md), or contact
[@1chrisshannon1-afk](https://github.com/1chrisshannon1-afk) (email on the profile) directly, rather than
opening a public issue.
