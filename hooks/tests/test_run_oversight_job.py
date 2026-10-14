"""Tests for run_oversight_job.sh's quota pre-flight (THE ISSUE WHEEL plan,
WS1-C.1 / Phase C item 1) and the `status` heartbeat field (WS1-B.1 / Phase B
item 1).

These invoke the REAL `schedules/run_oversight_job.sh` via subprocess, never
`claude -p` for real — a fake `claude` script is placed first on PATH inside
an isolated `$HOME`, so nothing here touches the real heartbeats directory,
the real launch-agents state, or the network. `CSA_WHEEL_SKIP_PREFLIGHT=1`
(the escape hatch this commit adds, tests-only per its own comment) is used
for the tests that are not specifically exercising the pre-flight itself.

GH #4767 (the wheel launcher): every wheel-slug run now also needs the launch
fixture (`_wheel_fixture`: a git repo, wheel_repos.json, settings files, the
preamble, TMPDIR, CSA_ENFORCE=1 and the WHEEL_* set), because the wrapper
refuses before launch without them. The second half of this file tests the
launcher itself: kill switch, launch context, the exact grant set, the
wrapper-written START, the sink-written END and the `WRAPPER:` line every
early exit prints.

The wrapper under test is the one in THIS tree (`<this file>/../../schedules/
run_oversight_job.sh`), so a copy of this file next to a copy of the wrapper
tests that copy; nothing here reads the live ~/.claude.
"""

from __future__ import annotations

import glob
import json
import os
import re
import signal
import stat
import subprocess
import textwrap
import time

import pytest

_REPO_CLAUDE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_WRAPPER_SH = os.path.join(_REPO_CLAUDE_DIR, "schedules", "run_oversight_job.sh")

# ---------------------------------------------------------------------------
# Env hygiene + the wheel fixture (GH #4767)
# ---------------------------------------------------------------------------

# Every test's subprocess env starts from os.environ MINUS these: a developer shell with
# CSA_DISABLE_HOOKS=1 (or a stray WHEEL_*/OVERSIGHT_* from a /wheel session) would otherwise turn
# every wheel test into a refusal, and TMPDIR is set per test so temp-dir cleanup is observable.
_SCRUB_ENV_RE = re.compile(r"^(WHEEL_|OVERSIGHT_|CSA_)")


def _base_env() -> dict:
    return {k: v for k, v in os.environ.items() if not _SCRUB_ENV_RE.match(k) and k != "TMPDIR"}


def _wheel_fixture(tmp_path, home, slug: str = "csa") -> dict:
    """Builds everything a wheel launch needs under tmp_path/home and returns the env additions.

    - repo = realpath(tmp/repo) with a .git/ dir;
    - $HOME/.claude/knowledge/wheel_repos.json with `slug`;
    - $HOME/.claude/settings.json allowing python3, with three additionalDirectories: a stand-in
      "App Support/SomeApp" (exercises a space), a stand-in sandbox, and ~/.claude/plans (skipped
      by the launcher because it is under ~/.claude);
    - repo/.claude/settings.local.json with $HOME/.claude/schedules (skipped: under ~/.claude);
    - _preamble.txt next to the prompt file (tmp_path/prompt.txt);
    - TMPDIR = tmp/tmpdir;  CSA_ENFORCE=1;  the full WHEEL_* set (FIX/CLOSE 0);
    - the leg4b probe file present (GATE-3B-FIRES) and leg4c MISSING.
    """
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    repo = type(repo)(os.path.realpath(repo))
    claude = home / ".claude"
    (claude / "knowledge").mkdir(parents=True, exist_ok=True)
    (claude / "knowledge" / "wheel_repos.json").write_text(json.dumps({
        slug: {"venv_python": ".venv/bin/python", "trust_surface_prefixes": [],
               "mandatory_registration_paths": [], "estimate_loop_exclusive_prefixes": [],
               "board_regen_command": None},
    }))
    someapp = tmp_path / "stand" / "App Support" / "SomeApp"
    sandbox = tmp_path / "stand" / "sandbox"
    someapp.mkdir(parents=True, exist_ok=True)
    sandbox.mkdir(parents=True, exist_ok=True)
    (claude / "settings.json").write_text(json.dumps({"permissions": {
        "allow": ["Bash(python3:*)"],
        "additionalDirectories": [str(someapp), str(sandbox), "~/.claude/plans"],
    }}))
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.local.json").write_text(json.dumps({"permissions": {
        "additionalDirectories": [f"{home}/.claude/schedules"],
    }}))
    (tmp_path / "_preamble.txt").write_text("PREAMBLE-SENTINEL-4767\n")
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    spike = claude / "schedules" / "spike"
    spike.mkdir(parents=True, exist_ok=True)
    (spike / f"leg4b_results_{slug}.json").write_text(json.dumps({"verdict": "GATE-3B-FIRES"}))
    return {
        "TMPDIR": str(tmpdir),
        "CSA_ENFORCE": "1",
        "WHEEL_REPO": str(repo),
        "WHEEL_SLUG": slug,
        "WHEEL_GH_REPO": "example-org/example-repo",
        "WHEEL_PROJECT": "7",
        "WHEEL_PROJECT_OWNER": "example-org",
        "WHEEL_LEDGER_REL": "plans/wheel_ledger.jsonl",
        "WHEEL_RANKED_GLOB": "ranked-*.json",
        "WHEEL_LANE_CAP": "1",
        "WHEEL_TRIAGE_SEED_CAP": "10",
        "WHEEL_FIX_ENABLED": "0",
        "WHEEL_CLOSE_ENABLED": "0",
    }


@pytest.fixture(autouse=True)
def _reap_hang_mode_orphans(tmp_path):
    """The "hang" fake-claude mode forks a `sleep 600` that deliberately
    outlives the perl-alarm kill of its own parent shell -- that orphan is
    exactly the real bug this commit's own falsifiability testing found in
    the production wrapper (see run_oversight_job.sh's own comment on the
    fix). Reap it after each test so the suite doesn't leave real `sleep`
    processes running on the machine: the "hang" fake claude (below)
    APPENDS its OWN pid to a file inside `tmp_path` the instant it starts
    (a single test can invoke the fake claude TWICE -- once for the
    pre-flight, once for the main CLI run -- so every line must be kept,
    never just the last), so this fixture can `kill` every EXACT pid
    recorded -- never a name/pattern match that could risk touching an
    unrelated process elsewhere on the machine.
    """
    yield
    pid_file = tmp_path / "hang_pid"
    if pid_file.exists():
        for line in pid_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                os.kill(int(line), 9)
            except (ValueError, ProcessLookupError, PermissionError, OSError):
                pass


def _write_fake_claude(bin_dir: str, mode: str, hang_pid_file: str | None = None) -> None:
    """Writes a fake `claude` executable to `bin_dir` whose behavior is
    switched by the FAKE_CLAUDE_MODE env var (never by parsing argv --
    both the pre-flight call and the main-run call share the same
    `$CLAUDE_BIN`, so a mode env var is the simplest fully-deterministic
    way to control each without depending on prompt-text argv parsing).

    mode:
      "limit"  -- prints a quota-limit message and exits 0 (mirrors a real
                  `claude -p` response when the account is rate-limited).
      "clean"  -- prints ordinary output and exits 0.
      "limit_exit1" -- prints the real CLI's session-limit line and exits 1
                  (the shape measured on the 2026-09-24 04:10Z/04:40Z fires, F6).
      "error_exit1" -- prints a non-limit error and exits 1 (a network or
                  auth failure; must fail OPEN).
      "throttle_exit1" -- prints the real server-throttle line and exits 1.
      "limit_exit2" -- prints limit text but exits 2 (never inspected).
      "hang"   -- appends its own pid to `hang_pid_file` (so the autouse
                  reaper fixture above can kill it precisely by pid after
                  the test), then sleeps past any reasonable alarm bound,
                  so the wrapper's own perl-alarm idiom kills the PARENT
                  shell (exit 142) while this `sleep` itself is orphaned --
                  reproducing the exact grandchild-outlives-the-alarm shape
                  that motivated the production fix.
    """
    path = os.path.join(bin_dir, "claude")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_fake_claude_body(mode, hang_pid_file))
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _fake_claude_body(mode: str, hang_pid_file: str | None = None) -> str:
    if mode == "limit":
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "You have hit your session limit -- resets 10:20pm"
            exit 0
            """
        )
    if mode == "limit_exit1":
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "You've hit your session limit · resets 9:20am"
            exit 1
            """
        )
    if mode == "throttle_exit1":
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited"
            exit 1
            """
        )
    if mode == "weekly_limit_exit1":
        # #5922: the weekly-limit text, distinct wording from "session limit" -- exercises the
        # same exit-1 inspection window as limit_exit1, with the OTHER limit-text pattern.
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "You've hit your weekly limit · resets Tuesday 8:00am"
            exit 1
            """
        )
    if mode == "quota_and_throttle_exit1":
        # #5922 fix round (item 7): both patterns present in the SAME output -- a pathological
        # case the wrapper's own comment above the two-way split names explicitly ("a single
        # probe's output somehow matched both patterns -- quota exhaustion is the higher-signal,
        # more actionable condition of the two"). The wrapper's `if ...session/weekly...; elif
        # ...throttle...; fi` structure makes quota win by construction (elif is never reached once
        # the if-branch matches) -- this test exercises that ordering directly rather than trusting
        # it from reading the shell.
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "You've hit your session limit · resets 9:20am"
            echo "API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited"
            exit 1
            """
        )
    if mode == "limit_exit142":
        # #5922 fix round (item 6): prints the limit text, then sleeps well past any test's
        # alarm bound so the wrapper's own perl-alarm idiom kills it (exit 142) with the limit text
        # already flushed to the (file-backed) output capture -- exercising the pre-flight's
        # inspection window at its THIRD member, 142, not just 0/1 (the two already covered by
        # "limit"/"limit_exit1"). MUST be `exec sleep 600`, never a bare foreground `sleep 600`: a
        # bare `sleep 600` is a CHILD of this script's own bash process, and perl's SIGALRM targets
        # only the directly-exec'd process (this bash script) -- killing bash orphans the `sleep`
        # child, which then leaks as a real, live process reparented to pid 1 for the remainder of
        # its 600s (reproduced directly: five such orphans measured live across this file's own
        # test runs before this fix, `ppid == 1`, `sleep 600` each). `exec sleep 600` REPLACES this
        # script's own process image with `sleep` itself, so perl's SIGALRM lands directly on what
        # is now the sleep process -- there is no separate child left to orphan, and no
        # hang_pid_file bookkeeping is needed for this mode (unlike "hang" mode above, which
        # deliberately backgrounds its sleep and so still needs that cleanup).
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "You've hit your session limit · resets 9:20am"
            exec sleep 600
            """
        )
    if mode == "limit_exit2":
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "You've hit your session limit · resets 9:20am"
            exit 2
            """
        )
    if mode == "error_exit1":
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "API Error: Connection error."
            exit 1
            """
        )
    if mode == "clean":
        return textwrap.dedent(
            """\
            #!/bin/bash
            echo "quota preflight ok"
            exit 0
            """
        )
    if mode == "hang":
        assert hang_pid_file, "hang mode requires hang_pid_file"
        return textwrap.dedent(
            f"""\
            #!/bin/bash
            sleep 600 &
            echo $! >> {hang_pid_file}
            wait
            """
        )
    if mode == "truthful_end":
        # Mirrors a REAL session's own _preamble.txt step 5 END write: no
        # `status` key at all (production cannot produce one from the
        # session side -- only this wrapper's own failure paths write it),
        # `exit` taken from FAKE_CLAUDE_TRUTHFUL_END_EXIT (defaults to "0").
        # Writes to $HOME/.claude/schedules/heartbeats/$FAKE_CLAUDE_TRUTHFUL_END_JOB.json
        # -- both env vars are set by the test itself and inherited by this
        # exec'd child exactly like a real launchd-spawned `claude -p` would
        # inherit HOME (JOB_LABEL/HEARTBEAT_FILE are NOT exported by the
        # wrapper itself, so this script cannot read them directly -- these
        # two test-only vars are the substitute). This mode is used ONLY for
        # the MAIN CLI invocation in a test (never the pre-flight call,
        # which must always be skipped via CSA_WHEEL_SKIP_PREFLIGHT=1 when
        # this mode is in play), so there is no risk of the pre-flight call
        # also overwriting the heartbeat with this same write.
        return textwrap.dedent(
            """\
            #!/bin/bash
            python3 - "$HOME/.claude/schedules/heartbeats/${FAKE_CLAUDE_TRUTHFUL_END_JOB}.json" \\
                "$FAKE_CLAUDE_TRUTHFUL_END_JOB" "${FAKE_CLAUDE_TRUTHFUL_END_EXIT:-0}" <<'PYEOF'
import json, sys, datetime
path, job, exit_code = sys.argv[1:4]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": now,
        "finished_at": now,
        "exit": int(exit_code),
        "cadence": "22:10 Mon-Fri",
        "summary": "did the job" if exit_code == "0" else "step 3 failed",
    }, fh)
PYEOF
            exit "${FAKE_CLAUDE_TRUTHFUL_END_EXIT:-0}"
            """
        )
    if mode == "argv_json":
        return _ARGV_JSON_FAKE
    raise ValueError(f"unknown fake claude mode: {mode!r}")


def _run_wrapper(
    tmp_path,
    *,
    fake_claude_mode: str,
    extra_env: dict | None = None,
    alarm_seconds: str = "5",
    job_label: str = "com.oversight.wheel.csa",
    wheel_slug: str | None = "csa",
):
    """Invokes the real run_oversight_job.sh under an isolated $HOME, with a
    fake `claude` first on PATH. Returns (returncode, heartbeat_dict_or_None).

    `wheel_slug` defaults to "csa" (matching production, where every real
    wheel plist exports WHEEL_SLUG alongside its job label -- fix round,
    BLOCKER 2: the quota pre-flight and second-slot skip are now both gated
    on WHEEL_SLUG being set, so a test exercising either must set it, same
    as a real wheel job would). Pass `wheel_slug=None` for a non-wheel job
    test (WHEEL_SLUG genuinely unset, e.g. testarch/trustarch/daily).
    """
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_claude(str(bin_dir), fake_claude_mode, hang_pid_file=str(tmp_path / "hang_pid"))

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the job\n")

    env = _base_env()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env.setdefault("CSA_WHEEL_SKIP_PREFLIGHT", "0")
    if wheel_slug is not None:
        env.update(_wheel_fixture(tmp_path, home, wheel_slug))
        env["WHEEL_SLUG"] = wheel_slug
    else:
        env.pop("WHEEL_SLUG", None)
    if extra_env:
        env.update(extra_env)

    heartbeat_dir = home / ".claude" / "schedules" / "heartbeats"

    # IMPORTANT (found during this commit's own falsifiability testing):
    # `subprocess.run(capture_output=True)` pipes the WRAPPER's stdout/
    # stderr back to this test process. A "hang" fake claude that forks a
    # child before the perl-alarm idiom kills its own direct exec target
    # leaves an ORPHANED grandchild that inherits those same pipe FDs --
    # `communicate()` then blocks until every FD-holder closes, even though
    # the wrapper process itself has already exited cleanly (reproduced
    # directly: the wrapper returned in ~2s while `communicate()` still
    # hung past 60s on the orphan). Redirecting to REGULAR FILES instead of
    # a pipe sidesteps this exactly like the production fix in
    # run_oversight_job.sh's own quota pre-flight does -- a file write is
    # never blocked by a lingering descendant holding it open.
    out_path = tmp_path / "wrapper.out"
    err_path = tmp_path / "wrapper.err"
    with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
        completed = subprocess.run(
            ["/bin/bash", _WRAPPER_SH, job_label, str(prompt_file), "22:10 Mon-Fri", alarm_seconds],
            env=env,
            stdout=out_fh,
            stderr=err_fh,
            timeout=30,
        )
    proc = _CompletedProcessLike(
        returncode=completed.returncode,
        stdout=out_path.read_text(errors="replace"),
        stderr=err_path.read_text(errors="replace"),
    )
    hb_path = heartbeat_dir / f"{job_label}.json"
    hb = None
    if hb_path.exists():
        with open(hb_path, encoding="utf-8") as fh:
            hb = json.load(fh)
    return proc, hb


class _CompletedProcessLike:
    """A tiny stand-in for subprocess.CompletedProcess exposing just the
    attributes this test file reads (.returncode/.stdout/.stderr), so
    _run_wrapper's callers need no changes after switching to file-backed
    output capture above.
    """

    def __init__(self, *, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_wrapper_again(
    tmp_path,
    home,
    bin_dir,
    *,
    fake_claude_mode: str,
    extra_env: dict | None = None,
    alarm_seconds: str = "5",
    job_label: str = "com.oversight.wheel.csa",
    wheel_slug: str | None = "csa",
    run_n: int = 2,
):
    """A second (or later) real wrapper invocation against an ALREADY-EXISTING home/bin_dir pair
    (built by a prior `_run_wrapper`-style call), so it genuinely observes that prior call's own
    real on-disk heartbeat -- never a hand-written stand-in for one. Mirrors
    `_run_wrapper_truthful_end`'s same-home-reuse shape (#5922: the streak/retry-slot tests
    need this same reuse for the plain quota-pre-flight fake-claude modes, not just the
    truthful_end mode that helper is restricted to). `run_n` only distinguishes this call's own
    output files from a sibling call's so their stdout/stderr are never overwritten."""
    _write_fake_claude(str(bin_dir), fake_claude_mode, hang_pid_file=str(tmp_path / "hang_pid"))

    prompt_file = tmp_path / "prompt.txt"
    if not prompt_file.exists():
        prompt_file.write_text("do the job\n")

    env = _base_env()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env.setdefault("CSA_WHEEL_SKIP_PREFLIGHT", "0")
    if wheel_slug is not None:
        env.update(_wheel_fixture(tmp_path, home, wheel_slug))
        env["WHEEL_SLUG"] = wheel_slug
    else:
        env.pop("WHEEL_SLUG", None)
    if extra_env:
        env.update(extra_env)

    heartbeat_dir = home / ".claude" / "schedules" / "heartbeats"
    out_path = tmp_path / f"wrapper_{run_n}.out"
    err_path = tmp_path / f"wrapper_{run_n}.err"
    with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
        completed = subprocess.run(
            ["/bin/bash", _WRAPPER_SH, job_label, str(prompt_file), "22:10 Mon-Fri", alarm_seconds],
            env=env,
            stdout=out_fh,
            stderr=err_fh,
            timeout=30,
        )
    proc = _CompletedProcessLike(
        returncode=completed.returncode,
        stdout=out_path.read_text(errors="replace"),
        stderr=err_path.read_text(errors="replace"),
    )
    hb_path = heartbeat_dir / f"{job_label}.json"
    hb = None
    if hb_path.exists():
        with open(hb_path, encoding="utf-8") as fh:
            hb = json.load(fh)
    return proc, hb


# ---------------------------------------------------------------------------
# quota pre-flight
# ---------------------------------------------------------------------------


def test_preflight_limit_text_exits_70_and_status_skipped_quota(tmp_path):
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="limit")
    assert proc.returncode == 70, proc.stderr
    assert hb is not None, "expected a heartbeat file to exist"
    assert hb["status"] == "skipped-quota"
    assert hb["exit"] == 70
    # NEVER 75 -- that is this wrapper's own lock-refused convention.
    assert hb["exit"] != 75
    assert hb["consecutive_quota_skips"] == 1


def test_preflight_limit_text_on_exit_1_is_a_quota_skip_F6(tmp_path):
    """F6: the real CLI exits 1 on a session/weekly limit (measured 2026-09-24:
    `PREFLIGHT_DIAG exit=1 bytes=60 head=You've hit your session limit`). That
    night must be a skipped-quota heartbeat with exit 70, never a main run."""
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="limit_exit1")
    assert proc.returncode == 70, proc.stderr
    assert hb is not None, "expected a heartbeat file to exist"
    assert hb["status"] == "skipped-quota"
    assert hb["exit"] == 70
    assert hb["consecutive_quota_skips"] == 1
    assert "PREFLIGHT_DIAG exit=1" in proc.stderr


def test_preflight_exit_1_without_limit_text_fails_open_F6(tmp_path):
    """F6's fail-open pair: an exit 1 WITHOUT limit text (network or auth
    error) must proceed to the main run, never be read as a quota skip."""
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="error_exit1")
    assert proc.returncode != 70, proc.stderr
    assert hb is not None
    assert hb.get("status") != "skipped-quota"
    assert hb.get("exit") != 70
    # The pre-flight really ran and the main run really happened (not a
    # launch-context refusal that would also satisfy the negatives above).
    assert "PREFLIGHT_DIAG exit=1" in proc.stderr
    assert hb["status"] == "failed"
    assert hb["exit"] == 1
    assert "claude process exited (code=1)" in hb.get("summary", "")


def test_preflight_server_throttle_on_exit_1_is_recorded_as_throttle_skip_F5922(tmp_path):
    """#5922 (F6 follow-up, supersedes the old
    test_preflight_server_throttle_on_exit_1_is_recorded_as_quota_skip_F6): a server-side throttle
    is NOT quota exhaustion -- the account's own usage limit is fine, the server is momentarily
    rate-limiting requests -- so it now gets its own status, `skipped-throttle`, excluded from the
    quota streak `heartbeat_audit.py` check #9 reads. F6 originally folded this into
    `skipped-quota` (disclosed, not decided); this is the decision. Exit stays 70 (shared "main run
    not dispatched this slot" convention), and it carries its own `consecutive_throttle_skips`
    counter rather than `consecutive_quota_skips`."""
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="throttle_exit1")
    assert proc.returncode == 70, proc.stderr
    assert hb["status"] == "skipped-throttle"
    assert hb["exit"] == 70
    assert hb.get("status") != "skipped-quota"
    assert "consecutive_quota_skips" not in hb
    assert hb["consecutive_throttle_skips"] == 1


def test_preflight_weekly_limit_text_on_exit_1_is_a_quota_skip_F5922(tmp_path):
    """#5922: the weekly-limit wording (distinct from the session-limit wording F6 measured)
    is the OTHER half of the quota-limit pattern and must be caught the same way, exit 70,
    status skipped-quota."""
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="weekly_limit_exit1")
    assert proc.returncode == 70, proc.stderr
    assert hb is not None, "expected a heartbeat file to exist"
    assert hb["status"] == "skipped-quota"
    assert hb["exit"] == 70
    assert hb["consecutive_quota_skips"] == 1


def test_preflight_quota_wins_when_both_patterns_present_F5922(tmp_path):
    """#5922 fix round (item 7): a single probe output that matches BOTH the session/weekly-
    limit pattern AND the throttle pattern must be recorded as `skipped-quota`, never
    `skipped-throttle` -- quota exhaustion is the higher-signal, more actionable condition, and the
    wrapper's own if/elif ordering makes it win by construction. This is the direct, executed proof
    of that ordering, not an inference from reading the shell."""
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="quota_and_throttle_exit1")
    assert proc.returncode == 70, proc.stderr
    assert hb is not None, "expected a heartbeat file to exist"
    assert hb["status"] == "skipped-quota"
    assert hb["exit"] == 70
    assert hb["consecutive_quota_skips"] == 1
    assert "consecutive_throttle_skips" not in hb


def test_preflight_two_throttles_in_a_row_give_streak_2_F5922(tmp_path):
    """#5922 fix round (item 7): the throttle streak carries forward across consecutive
    `skipped-throttle` heartbeats exactly like the quota streak does -- the direct mirror of
    test_preflight_quota_streak_carries_forward_from_prior_skipped_quota_F5922, for throttle."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    job_label = "com.oversight.wheel.csa"

    proc1, hb1 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="throttle_exit1", job_label=job_label, run_n=1,
    )
    assert proc1.returncode == 70, proc1.stderr
    assert hb1["status"] == "skipped-throttle"
    assert hb1["consecutive_throttle_skips"] == 1

    proc2, hb2 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="throttle_exit1", job_label=job_label, run_n=2,
    )
    assert proc2.returncode == 70, proc2.stderr
    assert hb2["status"] == "skipped-throttle"
    assert hb2["consecutive_throttle_skips"] == 2


def test_preflight_limit_text_on_exit_142_is_a_quota_skip_F5922(tmp_path):
    """#5922: the pre-flight's inspection window is {0, 1, 142} -- 142 is the alarm-kill exit,
    covering a probe that printed a partial limit message before being killed. This exercises that
    third member directly (only 0 and 1 were covered by name before)."""
    proc, hb = _run_wrapper(
        tmp_path,
        fake_claude_mode="limit_exit142",
        alarm_seconds="1",
        extra_env={"CSA_WHEEL_PREFLIGHT_ALARM_SECONDS": "1"},
    )
    assert proc.returncode == 70, proc.stderr
    assert hb is not None, "expected a heartbeat file to exist"
    assert hb["status"] == "skipped-quota"
    assert hb["exit"] == 70
    assert hb["consecutive_quota_skips"] == 1


def test_preflight_quota_streak_carries_forward_from_prior_skipped_quota_F5922(tmp_path):
    """#5922: a prior `skipped-quota` heartbeat for this label must make the NEXT quota skip's
    `consecutive_quota_skips` == 2, not reset to 1 -- this is the streak check #9
    (heartbeat_audit.py) actually depends on, and until this test it was only ever exercised at
    streak==1."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    job_label = "com.oversight.wheel.csa"

    proc1, hb1 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="limit", job_label=job_label, run_n=1,
    )
    assert proc1.returncode == 70, proc1.stderr
    assert hb1["status"] == "skipped-quota"
    assert hb1["consecutive_quota_skips"] == 1

    proc2, hb2 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="limit", job_label=job_label, run_n=2,
    )
    assert proc2.returncode == 70, proc2.stderr
    assert hb2["status"] == "skipped-quota"
    assert hb2["consecutive_quota_skips"] == 2


def test_preflight_throttle_between_quota_skips_does_not_extend_quota_streak_F5922(tmp_path):
    """#5922: a throttle skip sandwiched between two quota skips must NOT carry the quota
    streak forward -- `run_oversight_job.sh` only carries `consecutive_quota_skips` forward when
    the PRIOR heartbeat's status is exactly `skipped-quota`; a prior `skipped-throttle` resets it to
    1, same as any other non-quota-skip prior status. This is the direct falsification of the
    quota/throttle streaks ever being conflated."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    job_label = "com.oversight.wheel.csa"

    proc1, hb1 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="limit", job_label=job_label, run_n=1,
    )
    assert hb1["status"] == "skipped-quota"
    assert hb1["consecutive_quota_skips"] == 1

    proc2, hb2 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="throttle_exit1", job_label=job_label, run_n=2,
    )
    assert hb2["status"] == "skipped-throttle"
    assert hb2["consecutive_throttle_skips"] == 1

    proc3, hb3 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="limit", job_label=job_label, run_n=3,
    )
    assert proc3.returncode == 70, proc3.stderr
    assert hb3["status"] == "skipped-quota"
    # The throttle skip in between reset the streak -- this must be 1, never 2 or 3.
    assert hb3["consecutive_quota_skips"] == 1


def test_retry_slot_runs_after_a_prior_skipped_quota_heartbeat_F5922(tmp_path):
    """#5922: the retry slot's second-slot-skip logic (~:997) only skips when the label's
    existing heartbeat shows `status == "ok"` on today's UTC calendar date -- a prior
    `skipped-quota` heartbeat is neither `"ok"` nor a genuine completion, so the retry slot must
    run for real (dispatch claude again), never silently no-op. This was correct by reading the
    script (per the issue) but had no direct test before this one."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    job_label = "com.oversight.wheel.csa"

    # Slot 1 (22:10 primary): the pre-flight catches a quota limit, main run never dispatched.
    proc1, hb1 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="limit", job_label=job_label, run_n=1,
    )
    assert proc1.returncode == 70, proc1.stderr
    assert hb1["status"] == "skipped-quota"

    # Slot 2 (03:30 retry): quota has cleared -- the pre-flight now passes clean and the main run
    # genuinely dispatches (the "clean" fake claude exits 0 with no truthful END write of its own,
    # so the wrapper's own post-CLI fail-fast diagnostic fires -- the same expected shape
    # test_preflight_clean_output_proceeds_to_main_run already relies on). The load-bearing
    # assertions are that it did NOT take the second-slot-skip shortcut (no "skipped" summary) and
    # genuinely proceeded past the pre-flight (status/exit are not the quota-skip shape).
    proc2, hb2 = _run_wrapper_again(
        tmp_path, home, bin_dir, fake_claude_mode="clean", job_label=job_label, run_n=2,
    )
    assert hb2 is not None
    assert hb2["status"] != "skipped-quota"
    assert hb2["exit"] != 70
    assert "skipped" not in hb2["summary"].lower()


def test_preflight_limit_text_on_other_exit_codes_is_never_inspected_F6(tmp_path):
    """The inspection window is exactly {0, 1, 142}: limit text on any other
    exit code (here 2) is "probe itself failed" and fails OPEN."""
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="limit_exit2")
    assert proc.returncode != 70, proc.stderr
    assert hb is not None
    assert hb.get("status") != "skipped-quota"
    assert "PREFLIGHT_DIAG exit=2" in proc.stderr


def test_preflight_clean_output_proceeds_to_main_run(tmp_path):
    # The fake "clean" claude exits 0 immediately with no truthful END
    # heartbeat write of its own (it isn't a real session) -- so the
    # wrapper's own post-CLI fail-fast diagnostic fires. That is the
    # expected shape here: the important assertion is that the wrapper did
    # NOT stop at the pre-flight (exit is not 70, no skipped-quota status),
    # i.e. it genuinely proceeded past the pre-flight into the main run.
    proc, hb = _run_wrapper(tmp_path, fake_claude_mode="clean")
    assert proc.returncode == 0
    assert hb is not None
    assert hb["status"] != "skipped-quota"
    assert hb["exit"] != 70


def test_preflight_hung_proceeds_after_bound_never_exits_142_out_of_wrapper(tmp_path):
    # A hung pre-flight must fail OPEN (proceed to the main run) rather than
    # ever propagating the perl-alarm idiom's own 142 exit code out of the
    # WRAPPER's process. Both the pre-flight and the main-run fake claude
    # hang in this test (same fake binary for both calls), so the wrapper's
    # own main-run alarm also fires -- the assertion that matters is the
    # wrapper's OWN exit code is never 142 (that would mean the alarm-kill
    # leaked out of the wrapper unhandled) and a heartbeat was still written
    # (the wrapper's own contract: something truthful always lands).
    proc, hb = _run_wrapper(
        tmp_path,
        fake_claude_mode="hang",
        alarm_seconds="1",
        extra_env={"CSA_WHEEL_PREFLIGHT_ALARM_SECONDS": "1"},
    )
    assert proc.returncode != 142
    assert hb is not None
    # Never skipped-quota -- a hang is not a limit-text match.
    assert hb.get("status") != "skipped-quota"


def test_preflight_skippable_via_env_var(tmp_path):
    # CSA_WHEEL_SKIP_PREFLIGHT=1 (tests-only escape hatch) must skip the
    # pre-flight call entirely -- even a "limit" fake claude must NOT be
    # read as a quota skip when this is set, proving the probe itself never
    # ran (the main-run fake claude also prints the limit text, but the
    # main-run's own output is never inspected for quota text -- only the
    # pre-flight's is).
    proc, hb = _run_wrapper(
        tmp_path,
        fake_claude_mode="limit",
        extra_env={"CSA_WHEEL_SKIP_PREFLIGHT": "1"},
    )
    assert proc.returncode != 70
    assert hb is not None
    assert hb.get("status") != "skipped-quota"


def test_preflight_never_runs_for_a_non_wheel_job_even_on_limit_text(tmp_path):
    """BLOCKER 2 (fix round): the quota pre-flight is scoped to WHEEL_SLUG-
    bearing invocations only. A non-wheel scheduled job (testarch/trustarch/
    agentarch/daily/launchdir/productqa -- none of which export WHEEL_SLUG
    and none of which has a retry slot) must behave EXACTLY as it did before
    this whole change: a limit-text-emitting fake claude must NOT be read as
    a quota signal at all -- no skip, no exit 70, no status:"skipped-quota".
    For a monthly job, one transient quota window hitting an unscoped
    pre-flight would silently lose that job's entire audit for up to a
    month (a single skipped-quota heartbeat is streak 1 and is deliberately
    never flagged by heartbeat_audit.py's job-failed check)."""
    proc, hb = _run_wrapper(
        tmp_path,
        fake_claude_mode="limit",
        job_label="com.oversight.csa.testarch",
        wheel_slug=None,
    )
    assert proc.returncode != 70
    assert hb is not None
    assert hb.get("status") != "skipped-quota"
    assert hb.get("exit") != 70
    # It genuinely proceeded to (and only to) the MAIN run -- the main run's
    # own fake claude ALSO prints the limit text (same fake binary for both
    # calls), which is exactly the point: if the pre-flight had run at all
    # for this label, it would have caught this same limit text and skipped
    # with exit 70. It didn't, because WHEEL_SLUG is unset for this label.
    assert "skipped-quota" not in hb["summary"].lower()


# ---------------------------------------------------------------------------
# status field on other wrapper-owned exit paths
# ---------------------------------------------------------------------------


def test_empty_prompt_file_status_failed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_claude(str(bin_dir), "clean")

    empty_prompt = tmp_path / "empty_prompt.txt"
    empty_prompt.write_text("")

    env = _base_env()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CSA_WHEEL_SKIP_PREFLIGHT"] = "1"

    proc = subprocess.run(
        ["/bin/bash", _WRAPPER_SH, "com.oversight.csa.daily", str(empty_prompt), "05:10 daily"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0  # this exit path always exits 0, per the script's own contract
    hb_path = home / ".claude" / "schedules" / "heartbeats" / "com.oversight.csa.daily.json"
    with open(hb_path, encoding="utf-8") as fh:
        hb = json.load(fh)
    assert hb["status"] == "failed"
    assert hb["exit"] == 78


def test_wrapper_fail_fast_diagnostic_status_failed(tmp_path):
    # The fake "clean" claude exits 0 but writes no truthful END heartbeat of
    # its own -- the wrapper's own post-CLI verification then writes its
    # fail-fast WRAPPER: diagnostic, which must carry status: "failed".
    proc, hb = _run_wrapper(
        tmp_path,
        fake_claude_mode="clean",
        extra_env={"CSA_WHEEL_SKIP_PREFLIGHT": "1"},
    )
    assert hb is not None
    assert hb["summary"].startswith("WRAPPER:")
    assert hb["status"] == "failed"


# ---------------------------------------------------------------------------
# second-slot skip
# ---------------------------------------------------------------------------


def _run_wrapper_truthful_end(
    tmp_path,
    home,
    bin_dir,
    *,
    job_label: str,
    cli_exit: str = "0",
    wheel_slug: str | None = "csa",
    extra_env: dict | None = None,
):
    """Invokes the real wrapper with the "truthful_end" fake claude mode
    (a genuine session-shaped END heartbeat write, no `status` key -- see
    _fake_claude_body's own docstring), against an ALREADY-EXISTING
    home/bin_dir pair so a second call in the same test genuinely observes
    the first call's own real on-disk heartbeat, never a hand-written
    stand-in for one. Returns (proc, heartbeat_dict_or_None)."""
    prompt_file = tmp_path / "prompt.txt"
    if not prompt_file.exists():
        prompt_file.write_text("do the job\n")

    env = _base_env()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CSA_WHEEL_SKIP_PREFLIGHT"] = "1"  # the pre-flight is not under test here
    env["FAKE_CLAUDE_TRUTHFUL_END_JOB"] = job_label
    env["FAKE_CLAUDE_TRUTHFUL_END_EXIT"] = cli_exit
    if wheel_slug is not None:
        env.update(_wheel_fixture(tmp_path, home, wheel_slug))
        env["WHEEL_SLUG"] = wheel_slug
    else:
        env.pop("WHEEL_SLUG", None)
    if extra_env:
        env.update(extra_env)

    out_path = tmp_path / f"wrapper_{job_label}_{cli_exit}.out"
    err_path = tmp_path / f"wrapper_{job_label}_{cli_exit}.err"
    with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
        completed = subprocess.run(
            ["/bin/bash", _WRAPPER_SH, job_label, str(prompt_file), "22:10 Mon-Fri", "5"],
            env=env,
            stdout=out_fh,
            stderr=err_fh,
            timeout=30,
        )
    proc = _CompletedProcessLike(
        returncode=completed.returncode,
        stdout=out_path.read_text(errors="replace"),
        stderr=err_path.read_text(errors="replace"),
    )
    hb_path = home / ".claude" / "schedules" / "heartbeats" / f"{job_label}.json"
    hb = None
    if hb_path.exists():
        with open(hb_path, encoding="utf-8") as fh:
            hb = json.load(fh)
    return proc, hb


def test_second_slot_skips_when_earlier_slot_already_ok_tonight(tmp_path):
    """Re-derived (fix round, BLOCKER 1) from a heartbeat PRODUCED BY AN
    ACTUAL WRAPPER RUN, never hand-written: run 1 (the 22:10 primary slot)
    invokes the wrapper with the "truthful_end" fake claude (exit 0) --
    this exercises the B1 fix itself (the wrapper's own post-CLI
    verification stamps status:"ok" onto the session's truthful-but-
    status-less END heartbeat). Run 2 (the 03:30 retry slot, same job
    label, same on-disk heartbeat file) must then see that REAL status:"ok"
    heartbeat and skip."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_claude(str(bin_dir), "truthful_end", hang_pid_file=str(tmp_path / "hang_pid"))
    job_label = "com.oversight.wheel.csa"

    proc1, hb1 = _run_wrapper_truthful_end(tmp_path, home, bin_dir, job_label=job_label, cli_exit="0")
    assert proc1.returncode == 0, proc1.stderr
    assert hb1 is not None
    assert hb1["status"] == "ok", f"B1 stamp did not land: {hb1}"

    proc2, hb2 = _run_wrapper_truthful_end(tmp_path, home, bin_dir, job_label=job_label, cli_exit="0")
    assert proc2.returncode == 0, proc2.stderr
    assert hb2 is not None
    assert hb2["status"] == "ok"
    assert "skipped" in hb2["summary"].lower()


def test_second_slot_runs_when_earlier_slot_failed(tmp_path):
    """Paired negative for the test above (B1's own explicit non-goal): a
    FAILED first run (truthful END heartbeat, but exit != 0 -- the exact
    #4825/F3 shape: a truthful write that still reports failure) must NEVER
    get status:"ok" stamped, so the second slot's retry genuinely runs
    rather than being silently skipped."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_claude(str(bin_dir), "truthful_end", hang_pid_file=str(tmp_path / "hang_pid"))
    job_label = "com.oversight.wheel.csa"

    proc1, hb1 = _run_wrapper_truthful_end(tmp_path, home, bin_dir, job_label=job_label, cli_exit="1")
    assert proc1.returncode == 0, proc1.stderr
    assert hb1 is not None
    assert hb1["exit"] == 1
    assert hb1.get("status") != "ok", f"a FAILED run must never be stamped ok: {hb1}"

    proc2, hb2 = _run_wrapper_truthful_end(tmp_path, home, bin_dir, job_label=job_label, cli_exit="0")
    assert proc2.returncode == 0, proc2.stderr
    assert hb2 is not None
    # It genuinely ran the retry (and this run's own truthful_end wrote
    # exit 0, later stamped ok) -- the point is it did NOT take the
    # second-slot-skip shortcut on the FIRST (failed) run's heartbeat.
    assert "skipped" not in hb2["summary"].lower()
    assert hb2["exit"] == 0
    assert hb2["status"] == "ok"


def test_second_slot_skip_never_fires_for_manual_wheel_label(tmp_path):
    """B1's second half: the second-slot skip is guarded on
    IS_SCHEDULED_WHEEL_JOB (com.oversight.wheel.*), never on bare WHEEL_SLUG
    -- a manual-wheel-<slug> label (what /wheel exports) also carries
    WHEEL_SLUG for the concurrency guard, but has no retry slot of its own
    to protect. An operator's SECOND manual /wheel run later the same day
    must never silently no-op just because an earlier run already stamped
    status:"ok" for this exact label."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_claude(str(bin_dir), "truthful_end", hang_pid_file=str(tmp_path / "hang_pid"))
    job_label = "manual-wheel-csa"

    proc1, hb1 = _run_wrapper_truthful_end(tmp_path, home, bin_dir, job_label=job_label, cli_exit="0")
    assert proc1.returncode == 0, proc1.stderr
    assert hb1 is not None
    assert hb1["status"] == "ok"

    proc2, hb2 = _run_wrapper_truthful_end(tmp_path, home, bin_dir, job_label=job_label, cli_exit="0")
    assert proc2.returncode == 0, proc2.stderr
    assert hb2 is not None
    # A second manual run on the SAME label with an already-"ok" heartbeat
    # must still genuinely run (never silently skip) -- manual labels are
    # never IS_SCHEDULED_WHEEL_JOB, so the second-slot-skip guard above must
    # never fire for them regardless of what the existing heartbeat says.
    assert "skipped" not in hb2["summary"].lower()


def test_second_slot_does_not_skip_when_no_prior_ok_tonight(tmp_path):
    # No prior heartbeat at all -- must proceed normally (not skip), proving
    # the skip is never the default when nothing can be positively confirmed.
    proc, hb = _run_wrapper(
        tmp_path,
        fake_claude_mode="clean",
        extra_env={"CSA_WHEEL_SKIP_PREFLIGHT": "1"},
    )
    assert hb is not None
    # It proceeded to the main run (and the fake claude wrote no truthful END
    # heartbeat, so the wrapper's own fail-fast diagnostic fired) -- the
    # point is it did NOT take the second-slot-skip shortcut, which would
    # have produced status: "ok" with a "skipped" summary immediately.
    assert not ("skipped" in hb["summary"].lower() and hb["status"] == "ok")


# ---------------------------------------------------------------------------
# UTC-date invariant (fix round, item 7): the second-slot skip compares
# finished_at[:10] == wrapper_start_iso[:10] -- a UTC CALENDAR-DATE match.
# That holds for today's schedule (22:10/22:40 local -> 04:10/04:40Z, 03:30
# local -> 09:30Z, same UTC date, including across the DST change -- launchd
# interprets StartCalendarInterval in LOCAL wall-clock time, never UTC, per
# heartbeat_audit.py's own most_recent_scheduled_fire() docstring) but this
# is SILENTLY SCHEDULE-COUPLED: moving the primary slot to e.g. 18:00 local
# would put its UTC fire on a DIFFERENT calendar date than the 03:30-local
# retry slot in some timezones, quietly disabling the skip with no error
# anywhere. This test asserts the invariant directly against every INSTALLED
# wheel plist's own real slot times (skipped, with a stated reason, where none
# are installed -- they are per-machine and not shipped) AND against the
# shipped `schedules/example.wheel.plist`, so the logic is exercised in every
# checkout and a future schedule edit that breaks it fails a test instead of
# silently regressing.
# ---------------------------------------------------------------------------


def _local_naive_to_utc_date(dt_local_naive, utc_offset_hours=None) -> str:
    """Mirrors heartbeat_audit.py's own most_recent_scheduled_fire() local-
    time contract: a naive datetime is LOCAL wall-clock time (launchd's own
    interpretation of StartCalendarInterval), converted to its real UTC
    instant, then read back as a UTC calendar date.

    `utc_offset_hours=None` uses the machine's own zone (`.astimezone()`),
    which is the right question for a job installed on THIS machine. A number
    pins the zone instead (hours east of UTC, e.g. -6): used for the pinned
    schedules below, which were designed for US Mountain time. Their verdict
    must not depend on whichever zone the test happens to run in -- on a UTC
    runner (the GitHub default, and `scripts/ci_layout.sh`'s `TZ=UTC`) a
    22:10 -> 03:30 pair straddles midnight UTC for ANY such schedule, so
    judging them in the ambient zone is an environment test, not a schedule
    test."""
    import datetime

    if utc_offset_hours is None:
        aware_local = dt_local_naive.astimezone()  # attaches the SYSTEM's local tz
    else:
        aware_local = dt_local_naive.replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=utc_offset_hours))
        )
    return aware_local.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")


# (primary_weekdays, primary_hour, primary_minute, retry_weekdays, retry_hour, retry_minute)
# for each wheel plist whose schedule this test pins. A schedule edit to one of
# these must be re-derived here, not silently widened. `example.wheel.plist` is
# the SHIPPED template (present in every checkout, so the invariant logic runs
# even where no job is installed); its slots mirror the first live job's.
_WHEEL_SLOT_EXPECTATIONS = {
    "com.oversight.wheel.csa.plist": ([1, 2, 3, 4, 5], 22, 10, [2, 3, 4, 5, 6], 3, 30),
    "com.oversight.wheel.agency.plist": ([1, 2, 3, 4, 5], 22, 40, [2, 3, 4, 5, 6], 3, 30),
    "example.wheel.plist": ([1, 2, 3, 4, 5], 22, 10, [2, 3, 4, 5, 6], 3, 30),
}


def _wheel_plist_params() -> list:
    """Every installed `schedules/com.oversight.wheel.*.plist` (the second-slot
    skip is wheel-only: `IS_SCHEDULED_WHEEL_JOB`, `com.oversight.wheel.*`) plus
    the shipped `example.wheel.plist`. Installed job plists are per-machine and
    not shipped, so a checkout without them gets one explicit, reasoned skip
    instead of a collection-time empty set or a failing open() on a file that
    was never meant to be there."""
    installed = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(_REPO_CLAUDE_DIR, "schedules", "com.oversight.wheel.*.plist"))
    )
    params = [pytest.param(name, id=name) for name in installed]
    if not installed:
        params.append(
            pytest.param(
                None,
                id="no-installed-wheel-plists",
                marks=pytest.mark.skip(
                    reason="no schedules/com.oversight.wheel.*.plist in this checkout: installed "
                    "job plists are per-machine and not shipped; the shipped "
                    "example.wheel.plist case below still runs"
                ),
            )
        )
    params.append(pytest.param("example.wheel.plist", id="example.wheel.plist"))
    return params


def _slots_for(plist_name: str, intervals: list) -> tuple:
    """The pinned expectation for a known plist; for an installed wheel plist
    this table does not record (an operator's own job), derive the pair from
    the plist itself -- late hours (>= 12) are the primary slot, early hours
    the retry slot -- so the UTC-date invariant is still checked for it. A
    plist without exactly one primary and one retry time has no second slot to
    verify, and says so by skipping."""
    known = _WHEEL_SLOT_EXPECTATIONS.get(plist_name)
    if known is not None:
        return known
    intervals = [
        d for d in intervals if isinstance(d, dict) and {"Weekday", "Hour", "Minute"} <= d.keys()
    ]
    primary_times = sorted({(d["Hour"], d["Minute"]) for d in intervals if d["Hour"] >= 12})
    retry_times = sorted({(d["Hour"], d["Minute"]) for d in intervals if d["Hour"] < 12})
    if len(primary_times) != 1 or len(retry_times) != 1:
        pytest.skip(
            f"{plist_name}: no recorded expectation and not a single primary + single retry "
            "slot shape; nothing for the second-slot UTC-date invariant to check"
        )
    (p_hour, p_min), (r_hour, r_min) = primary_times[0], retry_times[0]
    primary_days = sorted(d["Weekday"] for d in intervals if (d["Hour"], d["Minute"]) == (p_hour, p_min))
    retry_days = sorted(d["Weekday"] for d in intervals if (d["Hour"], d["Minute"]) == (r_hour, r_min))
    return (primary_days, p_hour, p_min, retry_days, r_hour, r_min)


@pytest.mark.parametrize("plist_name", _wheel_plist_params())
def test_second_slot_utc_date_invariant_holds_for_live_plists(plist_name):
    """Reads the REAL plist's StartCalendarInterval (not a hardcoded
    duplicate) and asserts every primary-weekday -> retry-weekday pairing
    lands on the SAME UTC calendar date, for representative dates in BOTH
    DST states (a fixed mid-summer MDT date and a fixed mid-winter MST
    date) -- proving the invariant the second-slot skip depends on actually
    holds for the schedule as installed today. Runs against every installed
    wheel job plist and against the shipped `example.wheel.plist` template."""
    import datetime
    import plistlib

    plist_path = os.path.join(_REPO_CLAUDE_DIR, "schedules", plist_name)
    with open(plist_path, "rb") as fh:
        plist = plistlib.load(fh)
    intervals = plist.get("StartCalendarInterval")
    if plist_name not in _WHEEL_SLOT_EXPECTATIONS and not isinstance(intervals, list):
        pytest.skip(f"{plist_name}: no StartCalendarInterval list, so no second slot to verify")
    assert isinstance(intervals, list)
    (
        primary_weekdays,
        primary_hour,
        primary_minute,
        retry_weekdays,
        retry_hour,
        retry_minute,
    ) = _slots_for(plist_name, intervals)

    live_primary = {
        (d["Weekday"], d["Hour"], d["Minute"])
        for d in intervals
        if d.get("Hour") == primary_hour and d.get("Minute") == primary_minute
    }
    live_retry = {
        (d["Weekday"], d["Hour"], d["Minute"])
        for d in intervals
        if d.get("Hour") == retry_hour and d.get("Minute") == retry_minute
    }
    assert live_primary == {(w, primary_hour, primary_minute) for w in primary_weekdays}, (
        f"{plist_name}: live primary slot weekdays do not match what this test expects -- "
        "the schedule changed; re-derive this test's own expectation, don't just widen it"
    )
    assert live_retry == {(w, retry_hour, retry_minute) for w in retry_weekdays}, (
        f"{plist_name}: live retry slot weekdays do not match what this test expects -- "
        "the schedule changed; re-derive this test's own expectation, don't just widen it"
    )

    # launchd Weekday: 1=Monday..7=Sunday (0 also means Sunday, unused here).
    # Python's date.weekday(): 0=Monday..6=Sunday. Convert launchd's 1-7 to
    # Python's 0-6 (Sunday=7 -> 6, everything else -1).
    def _launchd_weekday_to_python(wd: int) -> int:
        return 6 if wd == 7 else wd - 1

    # Two representative anchor Mondays, one in each DST state (MDT is UTC-6
    # in September; MST is UTC-7 in January) -- a fixed date, not "today", so
    # this test is deterministic regardless of when it runs. A schedule this
    # test pins (its table entry above) is judged in its DESIGN zone, US
    # Mountain, with those fixed offsets, so the verdict is the same in every
    # runner's timezone. A wheel plist the table does not know is somebody's
    # own job on this machine: it is judged in the machine's own zone (offset
    # None), the only zone it will actually run in.
    pinned = plist_name in _WHEEL_SLOT_EXPECTATIONS
    anchor_mondays = [
        (datetime.date(2026, 9, 21), -6 if pinned else None),  # a Monday, MDT (summer/DST)
        (datetime.date(2027, 1, 4), -7 if pinned else None),  # a Monday, MST (winter/standard)
    ]

    for anchor_monday, utc_offset_hours in anchor_mondays:
        for primary_wd in primary_weekdays:
            retry_wd = primary_wd + 1 if primary_wd < 7 else 1  # Sat(6)->Sun(7) never occurs here
            assert retry_wd in retry_weekdays, (
                f"primary weekday {primary_wd}'s successor {retry_wd} is not in the retry set "
                f"{retry_weekdays} -- the two schedules are not actually paired as expected"
            )
            primary_py_wd = _launchd_weekday_to_python(primary_wd)
            retry_py_wd = _launchd_weekday_to_python(retry_wd)
            primary_date = anchor_monday + datetime.timedelta(
                days=(primary_py_wd - anchor_monday.weekday()) % 7
            )
            retry_date = anchor_monday + datetime.timedelta(
                days=(retry_py_wd - anchor_monday.weekday()) % 7
            )
            primary_dt_local = datetime.datetime.combine(
                primary_date, datetime.time(primary_hour, primary_minute)
            )
            retry_dt_local = datetime.datetime.combine(
                retry_date, datetime.time(retry_hour, retry_minute)
            )
            primary_utc_date = _local_naive_to_utc_date(primary_dt_local, utc_offset_hours)
            retry_utc_date = _local_naive_to_utc_date(retry_dt_local, utc_offset_hours)
            assert primary_utc_date == retry_utc_date, (
                f"{plist_name}: primary slot on launchd weekday {primary_wd} "
                f"({primary_dt_local} local) resolves to UTC date {primary_utc_date}, "
                f"but its retry slot on weekday {retry_wd} ({retry_dt_local} local) "
                f"resolves to UTC date {retry_utc_date} -- the second-slot skip's "
                "finished_at[:10]==wrapper_start_iso[:10] comparison would NEVER match "
                "for this pairing, silently disabling the skip"
            )


def test_pinned_zone_verdict_does_not_depend_on_the_runners_timezone():
    """The pinned schedules are judged in their design zone, so the answer is the
    same under any ambient TZ -- and the ambient-zone answer is NOT: on a UTC
    runner the 22:10 -> 03:30 pair straddles midnight UTC. This is the
    regression the fixed offsets exist for (the example plist failed on every
    UTC CI leg while passing on a Mountain-time laptop)."""
    import datetime
    import time

    primary = datetime.datetime(2026, 9, 21, 22, 10)  # Monday 22:10 local
    retry = datetime.datetime(2026, 9, 22, 3, 30)  # Tuesday 03:30 local
    previous_tz = os.environ.get("TZ")
    try:
        for tz_name in ("UTC", "America/Denver", "Asia/Tokyo"):
            os.environ["TZ"] = tz_name
            time.tzset()
            assert _local_naive_to_utc_date(primary, -6) == _local_naive_to_utc_date(retry, -6) == "2026-09-22"
            if tz_name == "UTC":
                # ambient-zone evaluation disagrees with itself here: Monday vs Tuesday
                assert _local_naive_to_utc_date(primary) != _local_naive_to_utc_date(retry)
    finally:
        if previous_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_tz
        time.tzset()


def test_a_primary_slot_that_lands_on_an_earlier_utc_date_is_detected_in_the_design_zone():
    """Falsifiability of the invariant itself: the failure shape the section
    comment warns about (a primary slot moved earlier in the day) must come out
    as DIFFERENT UTC dates, or the real-plist test could never go red."""
    import datetime

    early_primary = datetime.datetime(2026, 9, 21, 17, 0)  # Monday 17:00 MDT = 23:00Z Monday
    retry = datetime.datetime(2026, 9, 22, 3, 30)  # Tuesday 03:30 MDT = 09:30Z Tuesday
    assert _local_naive_to_utc_date(early_primary, -6) == "2026-09-21"
    assert _local_naive_to_utc_date(retry, -6) == "2026-09-22"


# ===========================================================================
# THE WHEEL LAUNCHER (GH #4767): kill switch, launch context, grant set, START/END, early-exit
# log lines. Spec: the L1.1 design §3-§8 and knowledge/oversight_install.md §1 ("PERMISSION
# MODEL OF A HEADLESS JOB"). The EXPECTED_* constants below are written from the design's §6,
# NEVER derived from wheel_launch_context.py, so a drift in either side fails the exact-argv test.
# ===========================================================================

_SINK_REAL = os.path.realpath(os.path.join(_REPO_CLAUDE_DIR, "hooks", "wheel_sink.py"))
_HISTORY_REAL = os.path.realpath(os.path.join(_REPO_CLAUDE_DIR, "hooks", "wheel_history.py"))

EXPECTED_TOOLS = "Bash,Read,Write,Workflow,TaskOutput,TaskStop,PushNotification,ToolSearch"


def EXPECTED_ALLOW(repo: str, sink: str) -> list:
    return [
        "Workflow(issue-wheel-triage)",
        "Bash(gh issue list:*)",
        "Bash(gh issue view:*)",
        f"Bash(git -C {repo} status:*)",
        f"Bash(git -C {repo} rev-parse:*)",
        "Bash(git rev-parse:*)",
        "Bash(git log:*)",
        "Bash(git show:*)",
        f"Bash(python3 {sink}:*)",
    ]


def EXPECTED_DENY(home: str, repo: str, extra_dirs: list) -> list:
    # BLOCKER B2 + N1 (trust-architect, fix round): whole-$HOME Edit/Write, fourteen Read denies, and
    # the expanded git/gh Bash families -- see wheel_launch_context.disallowed_tools()'s own
    # docstring and hooks/tests/test_wheel_launch_context.py's _spec_tail for the full rationale.
    deny = [f"Edit(//{home.lstrip('/')}/.claude/**)", f"Write(//{home.lstrip('/')}/.claude/**)",
            f"Edit(//{home.lstrip('/')}/**)", f"Write(//{home.lstrip('/')}/**)",
            f"Edit(//{repo.lstrip('/')}/**)", f"Write(//{repo.lstrip('/')}/**)"]
    for d in extra_dirs:
        deny += [f"Edit(//{d.lstrip('/')}/**)", f"Write(//{d.lstrip('/')}/**)"]
    deny += ["mcp__workspace__gmail_send", "mcp__workspace__drive_share"]
    deny += [
        "Bash(rm:*)", "Bash(rmdir:*)", "Bash(mv:*)", "Bash(cp:*)", "Bash(mkdir:*)", "Bash(touch:*)",
        "Bash(ln:*)", "Bash(chmod:*)", "Bash(tee:*)", "Bash(sed -i:*)", "Bash(rsync:*)",
        "Bash(git worktree:*)", "Bash(git clone:*)", "Bash(git archive:*)", "Bash(git commit:*)",
        "Bash(git push:*)", "Bash(git add:*)", "Bash(git restore:*)", "Bash(git checkout:*)",
        "Bash(git reset:*)", "Bash(git clean:*)", "Bash(git stash:*)", "Bash(git apply:*)",
        "Bash(git config:*)", "Bash(git remote:*)", "Bash(git pull:*)", "Bash(git fetch:*)",
        "Bash(git merge:*)", "Bash(git rebase:*)", "Bash(git cherry-pick:*)", "Bash(git revert:*)",
        "Bash(git rm:*)", "Bash(git mv:*)", "Bash(git tag:*)", "Bash(git update-ref:*)",
        "Bash(git submodule:*)", "Bash(git branch:*)", "Bash(git switch:*)", "Bash(git am:*)",
        "Bash(git notes:*)", "Bash(git replace:*)", "Bash(git gc:*)", "Bash(git init:*)",
        "Bash(git log *--output*)", "Bash(git show *--output*)",
        "Bash(gh issue delete:*)", "Bash(gh issue close:*)", "Bash(gh issue edit:*)",
        "Bash(gh issue create:*)", "Bash(gh issue reopen:*)", "Bash(gh issue transfer:*)",
        "Bash(gh issue comment:*)", "Bash(gh issue develop:*)", "Bash(gh issue lock:*)",
        "Bash(gh issue unlock:*)", "Bash(gh issue pin:*)", "Bash(gh issue unpin:*)",
        "Bash(gh repo:*)", "Bash(gh api:*)", "Bash(gh pr:*)", "Bash(gh release:*)",
        "Bash(gh secret:*)", "Bash(gh workflow:*)", "Bash(gh auth:*)", "Bash(gh label:*)",
        "Bash(gh project:*)", "Bash(gh ssh-key:*)", "Bash(gh gpg-key:*)", "Bash(gh gist:*)",
        "Bash(gh extension:*)", "Bash(gh variable:*)", "Bash(gh run:*)", "Bash(gh cache:*)",
        "Bash(gh codespace:*)", "Bash(gh alias:*)", "Bash(gh config:*)",
        "Bash(gcloud:*)", "Bash(bq:*)", "Bash(launchctl:*)", "Bash(curl:*)", "Bash(wget:*)",
        "Bash(open:*)", "Bash(osascript:*)",
        "Bash(~/.claude/scripts/legacy/get_test_secret.sh:*)",
        f"Bash({home}/.claude/scripts/legacy/get_test_secret.sh:*)",
        "Bash(~/.claude/scripts/gh_issue.sh:*)",
        f"Bash({home}/.claude/scripts/gh_issue.sh:*)",
    ]
    deny += [f"Read(//{home.lstrip('/')}/.claude/gate-secrets/**)", f"Read(//{home.lstrip('/')}/.ssh/**)",
             f"Read(//{home.lstrip('/')}/.config/**)", f"Read(//{home.lstrip('/')}/.aws/**)",
             f"Read(//{home.lstrip('/')}/.netrc)", f"Read(//{home.lstrip('/')}/.docker/**)",
             f"Read(//{home.lstrip('/')}/.gnupg/**)", f"Read(//{home.lstrip('/')}/.kube/**)",
             f"Read(//{home.lstrip('/')}/.npmrc)", f"Read(//{home.lstrip('/')}/.pypirc)",
             f"Read(//{home.lstrip('/')}/.git-credentials)", f"Read(//{home.lstrip('/')}/.claude.json)",
             f"Read(//{home.lstrip('/')}/Library/Keychains/**)",
             f"Read(//{home.lstrip('/')}/.claude/.model_exceptions/**)"]
    return deny


def EXPECTED_TAIL(scratch: str, home: str, repo: str, sink: str, extra_dirs: list) -> list:
    return ["--add-dir", scratch, "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--tools", EXPECTED_TOOLS, "--allowedTools", *EXPECTED_ALLOW(repo, sink),
            "--disallowedTools", *EXPECTED_DENY(home, repo, extra_dirs)]


_ARGV_JSON_FAKE = """\
#!/usr/bin/env python3
# fake claude, mode argv_json: records argv (never lossy), OVERSIGHT_* env, whether the
# --add-dir scratch exists, and the heartbeat as it stands at launch; optionally writes a
# session-shaped END through the REAL sink, exactly as the prompt instructs a session to.
import json, os, subprocess, sys
argv = sys.argv[1:]
scratch = argv[argv.index("--add-dir") + 1] if "--add-dir" in argv else None
start_hb = None
label = os.environ.get("OVERSIGHT_JOB_LABEL")
if label:
    try:
        with open(os.path.join(os.environ["HOME"], ".claude", "schedules", "heartbeats", label + ".json")) as fh:
            start_hb = json.load(fh)
    except Exception:
        start_hb = None
rec = {"argv": argv, "env": {k: v for k, v in os.environ.items() if k.startswith("OVERSIGHT_")},
       "scratch_exists": bool(scratch and os.path.isdir(scratch)), "start_hb": start_hb}
with open(os.environ["FAKE_CLAUDE_DUMP"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\\n")
if scratch and os.environ.get("FAKE_CLAUDE_WRITE_END") == "1":
    end = os.path.join(scratch, "end.json")
    with open(end, "w", encoding="utf-8") as fh:
        json.dump({"exit": 0, "finished_at": "now",
                   "summary": "triaged 0 / closed 0 / transitions 0 / lanes 0 / landed 0 / parked 0"}, fh)
    subprocess.run(["python3", os.environ["FAKE_CLAUDE_SINK"], "heartbeat", "--from", end], check=False)
print("OK")
"""


class _Wheel:
    """One isolated HOME + fake-claude bin + prompt file, reusable across several wrapper runs
    (so recovery and nonce tests observe real state from a previous run)."""

    def __init__(self, tmp_path, *, slug="csa", mode="argv_json", fixture=True):
        self.tmp = tmp_path
        self.slug = slug
        self.home = tmp_path / "home"
        self.home.mkdir(exist_ok=True)
        self.bin = tmp_path / "bin"
        self.bin.mkdir(exist_ok=True)
        _write_fake_claude(str(self.bin), mode, hang_pid_file=str(tmp_path / "hang_pid"))
        self.prompt = tmp_path / "prompt.txt"
        self.prompt.write_text("do the job\n")
        self.dump = tmp_path / "dump.jsonl"
        self.env = _base_env()
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = f"{self.bin}:{self.env.get('PATH', '')}"
        self.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "1"
        self.env["FAKE_CLAUDE_DUMP"] = str(self.dump)
        self.env["FAKE_CLAUDE_SINK"] = _SINK_REAL
        if fixture:
            self.env.update(_wheel_fixture(tmp_path, self.home, slug))
        else:
            (tmp_path / "tmpdir").mkdir(exist_ok=True)
            self.env["TMPDIR"] = str(tmp_path / "tmpdir")
        self.label = f"com.oversight.wheel.{slug}"
        self.runs = 0

    @property
    def claude(self):
        return self.home / ".claude"

    @property
    def repo(self) -> str:
        return self.env["WHEEL_REPO"]

    @property
    def tmpdir(self):
        return type(self.tmp)(self.env["TMPDIR"])

    @property
    def logs_dir(self):
        return self.claude / "schedules" / "logs"

    def hb_path(self, label=None):
        return self.claude / "schedules" / "heartbeats" / f"{label or self.label}.json"

    def run(self, *, label=None, wrapper=None, launchd_logs=False, pre_age=None):
        label = label or self.label
        self.runs += 1
        if launchd_logs:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            out_path = self.logs_dir / f"{label}.out.log"
            err_path = self.logs_dir / f"{label}.err.log"
            for p in (out_path, err_path):
                p.touch()
                if pre_age is not None:
                    os.utime(p, (pre_age, pre_age))
            mode = "ab"
        else:
            out_path = self.tmp / f"wrapper_{self.runs}.out"
            err_path = self.tmp / f"wrapper_{self.runs}.err"
            mode = "wb"
        size_out = out_path.stat().st_size if out_path.exists() else 0
        size_err = err_path.stat().st_size if err_path.exists() else 0
        with open(out_path, mode) as out_fh, open(err_path, mode) as err_fh:
            completed = subprocess.run(
                ["/bin/bash", str(wrapper or _WRAPPER_SH), label, str(self.prompt), "22:10 Mon-Fri", "20"],
                env=self.env, stdout=out_fh, stderr=err_fh, timeout=60,
            )
        with open(out_path, "rb") as fh:
            fh.seek(size_out)
            out = fh.read().decode(errors="replace")
        with open(err_path, "rb") as fh:
            fh.seek(size_err)
            err = fh.read().decode(errors="replace")
        proc = _CompletedProcessLike(returncode=completed.returncode, stdout=out, stderr=err)
        hb = None
        if self.hb_path(label).exists():
            hb = json.loads(self.hb_path(label).read_text())
        return proc, hb

    def dumps(self) -> list:
        if not self.dump.exists():
            return []
        return [json.loads(line) for line in self.dump.read_text().splitlines() if line.strip()]

    def main_run(self) -> dict:
        runs = [d for d in self.dumps() if d["argv"][1] != "quota preflight — reply OK"]
        assert len(runs) == 1, runs
        return runs[0]

    def leftovers(self) -> list:
        return sorted(p.name for p in self.tmpdir.glob("oversight_wheel*"))

    def extra_dirs(self) -> list:
        stand = self.tmp / "stand"
        return [str(stand / "App Support" / "SomeApp"), str(stand / "sandbox")]


def _wrapper_lines(text: str) -> list:
    return [line for line in text.splitlines() if line.startswith("WRAPPER: ")]


def _nonce_of(prompt: str) -> str:
    m = re.match(r"^=== WRAPPER CONTEXT ([0-9a-f]{16}) ", prompt)
    assert m, prompt[:120]
    return m.group(1)


# --- grant set / argv ---------------------------------------------------------


# Both labels a wheel run can launch under with the full grant tail: the scheduled plist's label,
# and the on-demand `/wheel <slug>` label. A gate keyed on IS_SCHEDULED_WHEEL_JOB instead of bare
# WHEEL_SLUG would silently drop the least-privilege flags (and the START heartbeat / OVERSIGHT_*
# export) on every manual run while these tests stayed green if they only ever ran the scheduled
# label (round-3 adversarial verification, mutants N7/N8/N9/N15). See also _KILL_SWITCH_LABELS
# below, which pins the same shape for the kill switch.
_ARGV_TEST_LABELS = ["com.oversight.wheel.csa", "manual-wheel-csa"]


@pytest.mark.parametrize("label", _ARGV_TEST_LABELS)
def test_wheel_main_argv_is_exact_set(tmp_path, label):
    w = _Wheel(tmp_path)
    if label.startswith("manual-"):
        w.env["WHEEL_ONDEMAND"] = "1"
    proc, hb = w.run(label=label)
    rec = w.main_run()
    argv = rec["argv"]
    scratch = argv[argv.index("--add-dir") + 1]
    assert argv[0] == "-p"
    assert argv[2:] == ["--model", "sonnet", "--permission-mode", "acceptEdits",
                        *EXPECTED_TAIL(scratch, str(w.home), w.repo, _SINK_REAL, w.extra_dirs())]
    # ~/.claude/plans and $HOME/.claude/schedules are additionalDirectories too, but they sit under
    # the ~/.claude deny already and must NOT get their own entries.
    flat = "\n".join(argv)
    assert "/.claude/plans/**" not in flat and "/.claude/schedules/**" not in flat
    if label.startswith("manual-"):
        assert "trigger=ondemand" in rec["argv"][1]


def test_wheel_add_dir_is_one_fresh_scratch_outside_dot_claude_and_removed(tmp_path):
    w = _Wheel(tmp_path)
    w.run()
    rec = w.main_run()
    argv = rec["argv"]
    assert argv.count("--add-dir") == 1
    scratch = argv[argv.index("--add-dir") + 1]
    assert rec["scratch_exists"] is True
    assert scratch == os.path.realpath(scratch)
    assert os.path.commonpath([scratch, os.path.realpath(w.tmpdir)]) == os.path.realpath(w.tmpdir)
    assert ".claude" not in scratch.split(os.sep)
    assert not os.path.exists(scratch), "the run scratch must be removed when the wrapper exits"
    assert w.leftovers() == []


def test_wheel_add_dir_realpaths_a_symlinked_tmpdir(tmp_path):
    """N4 (trust-architect, fix round; adopted from the round-3 verifier probe
    test_x_symlinked_tmpdir.py). Production TMPDIR is routinely a symlinked path
    (/tmp -> /private/tmp, /var/folders -> /private/var/folders on macOS). A wheel run with a
    symlinked TMPDIR must still launch claude with a realpath'd --add-dir scratch -- the wrapper's
    own RUN_SCRATCH realpath step (and the helper's scratch-unavailable check, which requires
    `os.path.realpath(scratch) == scratch`) must survive a symlink one level up the tree, not just
    a non-symlinked TMPDIR."""
    w = _Wheel(tmp_path)
    real = tmp_path / "realtmp"
    real.mkdir()
    link = tmp_path / "linktmp"
    os.symlink(real, link)
    w.env["TMPDIR"] = str(link)
    proc, hb = w.run()
    runs = w.dumps()
    assert len(runs) == 1, (proc.stdout, hb)
    argv = runs[0]["argv"]
    scratch = argv[argv.index("--add-dir") + 1]
    assert scratch == os.path.realpath(scratch)
    assert hb.get("hard_stop") is None


def test_wheel_deny_path_entries_use_double_slash_absolute_form(tmp_path):
    w = _Wheel(tmp_path)
    w.run()
    argv = w.main_run()["argv"]
    deny = argv[argv.index("--disallowedTools") + 1:]
    path_rules = [t for t in deny if t.startswith(("Edit(", "Write("))]
    # 5 pairs (BLOCKER B2 fix round: home/.claude, whole-home, repo, 2 extra dirs) x 2 = 10.
    assert len(path_rules) == 10
    for tok in path_rules:
        assert tok.startswith(("Edit(//", "Write(//")), tok
        assert not tok.startswith(("Edit(///", "Write(///")), tok


def test_non_wheel_argv_prompt_env_unchanged(tmp_path):
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    proc, hb = w.run(label="com.oversight.csa.testarch")
    runs = w.dumps()
    assert len(runs) == 1
    assert runs[0]["argv"] == ["-p", "do the job", "--model", "sonnet", "--permission-mode", "acceptEdits"]
    assert runs[0]["env"] == {}
    assert w.leftovers() == []
    assert _wrapper_lines(proc.stdout) == []


def test_scope_pin_non_wheel_job_keeps_session_enforced_kill_switch_F7(tmp_path):
    """Deliberate scope pin, NOT intended end-state: F7 (ExampleApp#5913) moves the global
    kill switch into the wrapper for every job; that change flips this assertion."""
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    (w.claude / "schedules").mkdir(parents=True, exist_ok=True)
    (w.claude / "schedules" / "DISABLED").touch()
    w.run(label="com.oversight.csa.testarch")
    assert len(w.dumps()) == 1, "a non-wheel job still launches claude; its session enforces DISABLED"


def test_preflight_argv_is_least_privilege_F5922(tmp_path):
    """#5922 (F6 out-of-scope follow-up item, fix round item 9): the pre-flight needs no tools
    at all, so it is launched restricted to the logical floor -- no MCP servers reachable, every
    built-in tool disabled outright (`--tools ""`, per the CLI's own --help), and
    `--permission-mode default` (never `acceptEdits`, which auto-accepts EDIT prompts specifically
    -- meaningless once `--tools ""` has already disabled edits along with everything else) --
    rather than the main run's full, unrestricted grant set. This replaces the old
    `test_preflight_argv_unchanged`, which pinned the UNrestricted argv this issue exists to
    close."""
    w = _Wheel(tmp_path)
    w.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "0"
    w.run()
    runs = w.dumps()
    assert runs[0]["argv"] == [
        "-p", "quota preflight — reply OK", "--model", "sonnet",
        "--permission-mode", "default",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--tools", "",
    ]
    assert len(runs) == 2


# --- kill switch --------------------------------------------------------------


# Both labels a wheel run can carry: the scheduled plist's, and the on-demand `/wheel <slug>` one
# (commands/wheel.md step 1: "The wrapper also enforces both kill switches itself (GH #4767)").
# The switch is gated on WHEEL_SLUG, never on the scheduled-label test, so a /wheel run with DISABLED
# present must not launch claude either (fix round 2, blocker 3: a scheduled-only gate passed 166/166).
_KILL_SWITCH_LABELS = ["com.oversight.wheel.csa", "manual-wheel-csa"]


@pytest.mark.parametrize("label", _KILL_SWITCH_LABELS)
def test_global_kill_switch_skips_before_any_claude_call(tmp_path, label):
    w = _Wheel(tmp_path)
    w.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "0"  # a misordered switch would reach the pre-flight call
    (w.claude / "schedules" / "DISABLED").touch()
    proc, hb = w.run(label=label)
    assert proc.returncode == 0
    assert w.dumps() == [], "claude (pre-flight or main) must never be invoked"
    assert hb is not None, f"no heartbeat for {label}"
    assert hb["job"] == label
    assert hb["status"] == "skipped-disabled"
    assert hb["hard_stop"] == "1"
    assert hb["exit"] == 0
    window = (w.claude / "schedules" / "heartbeats" / "_disabled_window.jsonl").read_text().splitlines()
    assert len(window) == 1 and json.loads(window[0])["job"] == label
    assert not (w.claude / "schedules" / "locks").exists(), "the switch must run before the lock"
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1 and lines[0].startswith("WRAPPER: skipped-disabled (global)"), proc.stdout
    assert lines[0] in proc.stderr
    assert w.leftovers() == []


@pytest.mark.parametrize("label", _KILL_SWITCH_LABELS)
def test_per_job_kill_switch_skips_without_window_line(tmp_path, label):
    """N4 (trust-architect, fix round): CSA_WHEEL_SKIP_PREFLIGHT=0 here (never the fixture's
    default skip) and the explicit no-locks-dir assertion, matching the global kill-switch test
    above (K8) -- without both, a future change moving this switch after the lock and the
    pre-flight API call could still pass this test while genuinely regressing the ordering."""
    w = _Wheel(tmp_path)
    w.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "0"
    (w.claude / "schedules" / "DISABLED.wheel.csa").touch()
    proc, hb = w.run(label=label)
    assert w.dumps() == [], "claude must never be invoked"
    assert hb is not None, f"no heartbeat for {label}"
    assert hb["job"] == label
    assert hb["status"] == "skipped-disabled"
    assert hb["hard_stop"] == "2"
    assert not (w.claude / "schedules" / "heartbeats" / "_disabled_window.jsonl").exists()
    assert not (w.claude / "schedules" / "locks").exists(), "the switch must run before the lock"
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1 and lines[0].startswith("WRAPPER: skipped-disabled (per-job)"), proc.stdout


def test_other_slug_kill_switch_does_not_skip(tmp_path):
    w = _Wheel(tmp_path)
    (w.claude / "schedules" / "DISABLED.wheel.agency").touch()
    w.run()
    assert len(w.dumps()) == 1


def test_kill_switch_recovery_after_marker_removed(tmp_path):
    w = _Wheel(tmp_path)
    marker = w.claude / "schedules" / "DISABLED"
    marker.touch()
    _, hb1 = w.run()
    assert hb1["status"] == "skipped-disabled"
    marker.unlink()
    w.env["FAKE_CLAUDE_WRITE_END"] = "1"
    _, hb2 = w.run()
    assert len(w.dumps()) == 1
    assert hb2["status"] == "ok"
    assert hb2["written_via"] == "wheel_sink"


# --- prompt / context ------------------------------------------------------------


def test_prompt_is_context_then_preamble_then_job_prompt(tmp_path):
    w = _Wheel(tmp_path)
    w.run()
    prompt = w.main_run()["argv"][1]
    nonce = _nonce_of(prompt)
    i_over = prompt.index("PREAMBLE OVERRIDES FOR THIS JOB")
    i_end = prompt.index(f"=== END WRAPPER CONTEXT {nonce} ===")
    i_pre = prompt.index("PREAMBLE-SENTINEL-4767")
    assert i_over < i_end < i_pre
    assert prompt.endswith("do the job")


def test_context_nonce_is_fresh_and_paired(tmp_path):
    w = _Wheel(tmp_path)
    w.run()
    w.run()
    prompts = [d["argv"][1] for d in w.dumps()]
    assert len(prompts) == 2
    nonces = []
    for p in prompts:
        n = _nonce_of(p)
        assert re.fullmatch(r"[0-9a-f]{16}", n)
        assert f"=== END WRAPPER CONTEXT {n} ===" in p
        nonces.append(n)
    assert nonces[0] != nonces[1]


def test_context_carries_run_facts(tmp_path):
    w = _Wheel(tmp_path)
    w.run()
    rec = w.main_run()
    prompt, argv = rec["argv"][1], rec["argv"]
    scratch = argv[argv.index("--add-dir") + 1]
    lines = prompt.splitlines()
    assert f"started_at={rec['start_hb']['started_at']}   (the START heartbeat already carries this value)" in lines
    assert any(line.startswith(f"RUN_SCRATCH={scratch}   ") for line in lines)
    assert f"SINK=python3 {_SINK_REAL}" in lines
    assert f"  WHEEL_REPO={json.dumps(w.repo)}" in lines
    assert f"JOB={w.label}" in lines
    assert "trigger=nightly" in lines
    probe = [line for line in lines if line.startswith("  HARD STOP 7 ")]
    assert len(probe) == 1
    assert "leg4b (~/.claude/schedules/spike/leg4b_results_csa.json): GATE-3B-FIRES" in probe[0]
    assert "leg4c (none): MISSING" in probe[0]
    assert "probe_file_missing=true" in probe[0] and "fix_half_probe_ok=false" in probe[0]
    assert any(line.startswith("GRANTS: tools Bash, Read, Write, Workflow") for line in lines)
    assert "  HARD STOP 4b WHEEL_EXCLUDE_ISSUES: unset" in lines
    assert "  HARD STOP 6 worktree.baseRef: absent" in lines


def test_context_overrides_preamble_step_6_comment_fallback(tmp_path):
    """Round-3 lens note: preamble step 6's comment fallback tells the session to read a
    ~/.claude file (oversight_install.md §0's TRACKING line) it has no read grant for, and to
    run gh issue comment, which is not in the wheel's allowedTools. WRAPPER CONTEXT must say so
    explicitly, so no compliant session is told to read a forbidden file."""
    w = _Wheel(tmp_path)
    w.run()
    prompt = w.main_run()["argv"][1]
    assert "preamble step 6 (NOTIFY)'s PushNotification half applies as written" in prompt
    assert "Its comment fallback does NOT" in prompt
    # N2 (trust-architect, fix round): reworded as a prohibition ("do not read"), not a false
    # "you have no read grant" claim, and `gh issue comment` is now genuinely denied (not merely
    # absent from allowedTools) -- both wordings are mechanically true against the argv.
    assert "do not read ~/.claude files" in prompt
    assert "`gh issue comment` is in your disallowed tools" in prompt
    assert "never attempt the comment fallback and never read a ~/.claude file to find it" in prompt
    # the blanket "applies as written" no longer covers step 6 on its own
    assert "preamble steps 2 and 4, the HARD RULES and the TIMESTAMP/PIN-SUSPECT rules apply as written" in prompt
    assert "preamble steps 2, 4 and 6" not in prompt
    # N2's own mechanical proof: the claim in the prompt text is actually backed by a real deny.
    argv = w.main_run()["argv"]
    assert "Bash(gh issue comment:*)" in argv[argv.index("--disallowedTools") + 1:]


# --- START / END ---------------------------------------------------------------


@pytest.mark.parametrize("label", _ARGV_TEST_LABELS)
def test_start_heartbeat_written_by_wrapper_before_launch(tmp_path, label):
    w = _Wheel(tmp_path)
    if label.startswith("manual-"):
        w.env["WHEEL_ONDEMAND"] = "1"
    w.run(label=label)
    start = w.main_run()["start_hb"]
    assert start is not None
    assert start["finished_at"] is None
    assert start["exit"] == 1
    assert start["summary"] == "STARTED " + start["started_at"]
    assert start["job"] == label


@pytest.mark.parametrize("label", _ARGV_TEST_LABELS)
def test_end_via_real_sink_gets_status_ok_and_marker(tmp_path, label):
    w = _Wheel(tmp_path)
    if label.startswith("manual-"):
        w.env["WHEEL_ONDEMAND"] = "1"
    w.env["FAKE_CLAUDE_WRITE_END"] = "1"
    proc, hb = w.run(label=label)
    assert hb["status"] == "ok", hb
    assert hb["written_via"] == "wheel_sink"
    assert hb["sink_version"] == 1
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", hb["finished_at"])
    assert hb["finished_at"] >= hb["started_at"]
    assert not hb["summary"].startswith("WRAPPER:")
    assert hb["job"] == label
    audit = (w.claude / "telemetry" / "wheel" / "csa" / "sink_audit.jsonl").read_text().splitlines()
    assert [json.loads(line)["kind"] for line in audit] == ["heartbeat"]


def test_session_without_end_gets_wrapper_failure(tmp_path):
    w = _Wheel(tmp_path)
    proc, hb = w.run()
    assert hb["status"] == "failed"
    assert hb["summary"].startswith("WRAPPER:")


# --- refusals ------------------------------------------------------------------


def _mut_not_enforcing(w):
    w.env.pop("CSA_ENFORCE")


def _fix_not_enforcing(w):
    w.env["CSA_ENFORCE"] = "1"


def _mut_repo(w):
    notrepo = w.tmp / "notrepo"
    notrepo.mkdir(exist_ok=True)
    w.env["WHEEL_REPO"] = str(notrepo)


def _fix_repo(w):
    (w.tmp / "notrepo" / ".git").mkdir()


def _mut_slug_unknown(w):
    (w.claude / "knowledge" / "wheel_repos.json").write_text(json.dumps({"_comment": {}, "other": {}}))


def _fix_slug_unknown(w):
    # N8 (trust-architect, fix round): restore the slug as a real key -- mirrors _wheel_fixture's
    # own initial write, so recovery genuinely re-derives a valid wheel_repos.json entry rather
    # than just deleting the mutation.
    (w.claude / "knowledge" / "wheel_repos.json").write_text(json.dumps({
        w.slug: {"venv_python": ".venv/bin/python", "trust_surface_prefixes": [],
                 "mandatory_registration_paths": [], "estimate_loop_exclusive_prefixes": [],
                 "board_regen_command": None},
    }))


def _mut_env(w):
    w.env.pop("WHEEL_GH_REPO")


def _fix_env(w):
    w.env["WHEEL_GH_REPO"] = "example-org/example-repo"


def _mut_exclude(w):
    w.env["WHEEL_EXCLUDE_ISSUES"] = "12,abc"


def _fix_exclude(w):
    w.env.pop("WHEEL_EXCLUDE_ISSUES", None)


def _mut_preamble(w):
    (w.tmp / "_preamble.txt").unlink()


def _fix_preamble(w):
    (w.tmp / "_preamble.txt").write_text("PREAMBLE-SENTINEL-4767\n")


def _user_settings(w, **perms):
    (w.claude / "settings.json").write_text(json.dumps({"permissions": perms}))


def _mut_python3(w):
    _user_settings(w, allow=[], additionalDirectories=w.extra_dirs())


def _fix_python3(w):
    _user_settings(w, allow=["Bash(python3:*)"], additionalDirectories=w.extra_dirs())


def _mut_additional_dir(w):
    _user_settings(w, allow=["Bash(python3:*)"], additionalDirectories=w.extra_dirs() + ["relative/dir"])


def _fix_additional_dir(w):
    _user_settings(w, allow=["Bash(python3:*)"], additionalDirectories=w.extra_dirs())


def _mut_settings(w):
    (type(w.tmp)(w.repo) / ".claude" / "settings.json").write_text("{not json")


def _fix_settings(w):
    (type(w.tmp)(w.repo) / ".claude" / "settings.json").unlink()


def _mut_fix_enabled(w):
    w.env["WHEEL_FIX_ENABLED"] = "1"


def _fix_fix_enabled(w):
    w.env["WHEEL_FIX_ENABLED"] = "0"


def _mut_close_enabled(w):
    w.env["WHEEL_CLOSE_ENABLED"] = "1"


def _fix_close_enabled(w):
    w.env["WHEEL_CLOSE_ENABLED"] = "0"


def _mut_label_mismatch(w):
    # N8 (trust-architect, fix round): the "4-label" case has no mutator (its refusal comes
    # purely from the fixed `label="manual-wheel-agency"` param vs WHEEL_SLUG="csa"), so its own
    # recovery cannot be "run again with the same label" -- it needs a real state change. Widen
    # wheel_repos.json to ALSO carry an "agency" entry and point WHEEL_REPO/WHEEL_SLUG at it, so
    # the fix below can make the SAME label ("manual-wheel-agency") genuinely match WHEEL_SLUG.
    (w.claude / "knowledge" / "wheel_repos.json").write_text(json.dumps({
        w.slug: {"venv_python": ".venv/bin/python", "trust_surface_prefixes": [],
                 "mandatory_registration_paths": [], "estimate_loop_exclusive_prefixes": [],
                 "board_regen_command": None},
        "agency": {"venv_python": ".venv/bin/python", "trust_surface_prefixes": [],
                   "mandatory_registration_paths": [], "estimate_loop_exclusive_prefixes": [],
                   "board_regen_command": None},
    }))


def _fix_label_mismatch(w):
    w.env["WHEEL_SLUG"] = "agency"


_REFUSALS = [
    ("3-not-enforcing", _mut_not_enforcing, _fix_not_enforcing, None),
    ("4-repo", _mut_repo, _fix_repo, None),
    ("4-slug-unknown", _mut_slug_unknown, _fix_slug_unknown, None),
    ("4-label", _mut_label_mismatch, _fix_label_mismatch, "manual-wheel-agency"),
    ("4-env", _mut_env, _fix_env, None),
    ("fix-close-not-granted", _mut_fix_enabled, _fix_fix_enabled, None),
    ("4b-exclude-malformed", _mut_exclude, _fix_exclude, None),
    ("preamble-unreadable", _mut_preamble, _fix_preamble, None),
    ("precondition-python3-allow", _mut_python3, _fix_python3, None),
    ("additional-dir-unsafe", _mut_additional_dir, _fix_additional_dir, None),
    ("settings-unreadable", _mut_settings, _fix_settings, None),
]


def test_refuse_fix_close_not_granted_for_close_flag_too(tmp_path):
    """WHEEL_CLOSE_ENABLED gets its own case (same code, the other flag) because the check tests
    both flags independently — a mutant that checked only WHEEL_FIX_ENABLED would pass the
    parametrized _REFUSALS case above but still fail open when only the close half is turned on."""
    w = _Wheel(tmp_path)
    _mut_close_enabled(w)
    proc, hb = w.run()
    assert proc.returncode == 0
    assert w.dumps() == [], "claude must not be launched on a refusal"
    assert hb["hard_stop"] == "fix-close-not-granted"
    assert hb["status"] == "failed"
    assert hb["exit"] == 79
    assert "WHEEL_CLOSE_ENABLED" in hb["summary"]
    _fix_close_enabled(w)
    proc2, hb2 = w.run()
    assert len(w.dumps()) == 1, "recovery after fixing WHEEL_CLOSE_ENABLED: claude must launch"
    assert hb2.get("hard_stop") is None


@pytest.mark.parametrize("code,mutate,fix,label", _REFUSALS, ids=[r[0] for r in _REFUSALS])
def test_refuse(tmp_path, code, mutate, fix, label):
    w = _Wheel(tmp_path)
    if mutate:
        mutate(w)
    proc, hb = w.run(label=label)
    assert proc.returncode == 0
    assert w.dumps() == [], "claude must not be launched on a refusal"
    assert hb["hard_stop"] == code
    assert hb["status"] == "failed"
    assert hb["exit"] == 79
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1 and lines[0].startswith(f"WRAPPER: refused before launch — {code}: "), proc.stdout
    assert hb["summary"] == lines[0]
    assert w.leftovers() == []
    if code == "4b-exclude-malformed":
        assert hb["exclude_issues_malformed"] is True
        assert hb["exclude_issues_raw"] == "12,abc"
    if fix:
        fix(w)
        proc2, hb2 = w.run(label=label)
        assert len(w.dumps()) == 1, f"recovery after fixing {code}: claude must launch"
        assert hb2.get("hard_stop") is None


def test_python3_precondition_accepts_project_scope_allow(tmp_path):
    w = _Wheel(tmp_path)
    _user_settings(w, allow=[], additionalDirectories=w.extra_dirs())
    (type(w.tmp)(w.repo) / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(python3:*)"]}}))
    proc, hb = w.run()
    assert len(w.dumps()) == 1, proc.stdout


# --- the wrapper fails closed around the helper ------------------------------------------


def _runtime_with_stub(tmp_path, stub_body: str):
    rt = tmp_path / "rt"
    (rt / "schedules").mkdir(parents=True)
    (rt / "hooks").mkdir()
    wrapper = rt / "schedules" / "run_oversight_job.sh"
    wrapper.write_bytes(open(_WRAPPER_SH, "rb").read())
    (rt / "hooks" / "wheel_launch_context.py").write_text(stub_body)
    (rt / "hooks" / "wheel_sink.py").write_bytes(open(_SINK_REAL, "rb").read())
    (rt / "hooks" / "wheel_history.py").write_bytes(open(_HISTORY_REAL, "rb").read())
    return wrapper


def _real_runtime_with_history_body(tmp_path, history_body: str, *, name: str = "rt_history_body"):
    """A REAL wheel-launch runtime (genuine wheel_launch_context.py + wheel_sink.py + _lib.py, not
    stubs) with a CUSTOM hooks/wheel_history.py body -- so a test can exercise the append call at
    its real position in the real trap, with the append itself failing in a controlled way.
    Blocker 2 (review round): the previous version of this test used _runtime_with_stub (a STUBBED
    wheel_launch_context.py) with no _lib.py present, so the launch-context helper's own `import
    _lib` inside wheel_launch_context.py crashed before the appender was ever reached at all --
    every assertion in that test was vacuously true against a run that never got past launch
    refusal. This helper mirrors the reviewer's own rev1b/probe/test_review_probe.py `_rt()`."""
    rt = tmp_path / name
    (rt / "schedules").mkdir(parents=True)
    (rt / "hooks").mkdir()
    wrapper = rt / "schedules" / "run_oversight_job.sh"
    wrapper.write_bytes(open(_WRAPPER_SH, "rb").read())
    for mod in ("wheel_launch_context.py", "wheel_sink.py", "_lib.py"):
        (rt / "hooks" / mod).write_bytes(open(os.path.join(_REPO_CLAUDE_DIR, "hooks", mod), "rb").read())
    (rt / "hooks" / "wheel_history.py").write_text(history_body)
    return wrapper


_STUB_SILENT = "import sys\nsys.exit(0)\n"
_STUB_EMPTY_FILE = textwrap.dedent("""\
    import os, sys
    out = sys.argv[sys.argv.index("--out-dir") + 1]
    open(os.path.join(out, "context.txt"), "w").write({ctx!r})
    open(os.path.join(out, "argv.txt"), "w").write({argv!r})
    print("launch")
    """)


def _assert_launch_context_error(w, proc, hb):
    assert w.dumps() == []
    assert hb["hard_stop"] == "launch-context-error"
    assert hb["exit"] == 79
    assert hb["status"] == "failed"
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1 and lines[0].startswith("WRAPPER: refused before launch — launch-context-error: ")
    assert w.leftovers() == []


def test_launch_context_helper_silent_fails_closed(tmp_path):
    w = _Wheel(tmp_path)
    proc, hb = w.run(wrapper=_runtime_with_stub(tmp_path, _STUB_SILENT))
    _assert_launch_context_error(w, proc, hb)


@pytest.mark.parametrize("ctx,argv", [("", "--add-dir\n/x\n"), ("CONTEXT\n", "")], ids=["empty-context", "empty-argv"])
def test_launch_with_empty_context_file_fails_closed(tmp_path, ctx, argv):
    w = _Wheel(tmp_path)
    proc, hb = w.run(wrapper=_runtime_with_stub(tmp_path, _STUB_EMPTY_FILE.format(ctx=ctx, argv=argv)))
    _assert_launch_context_error(w, proc, hb)


# --- BLOCKER B1 (trust-architect fix round): argv.txt TOCTOU + wheel-label guard -------------
#
# B1(a): argv.txt was checked non-empty by `[ -s ]` but not actually READ into "$@" until far
# below, after the lock, the helper, START and a quota pre-flight of up to 60s. A file that is
# non-empty at the `[ -s ]` check but does not parse into a well-formed `--add-dir ...` tail (the
# real-world trigger: deleted/truncated in that window, reproduced here directly via a malformed
# stub write, which is the observable-equivalent shape once the file is captured into "$@" right
# after the check) must never let claude launch with zero flags. Falsified by reverting the read
# to the exec site (its pre-fix location): these fail RED because the exec would run before the
# shape is ever checked.
_STUB_MALFORMED_ARGV = textwrap.dedent("""\
    import os, sys
    out = sys.argv[sys.argv.index("--out-dir") + 1]
    open(os.path.join(out, "context.txt"), "w").write("CONTEXT\\n")
    open(os.path.join(out, "argv.txt"), "w").write("not-add-dir\\n/x\\n")
    print("launch")
    """)


def test_launch_with_malformed_argv_tail_fails_closed_not_unrestricted(tmp_path):
    """argv.txt is non-empty (passes [ -s ]) but its first token is not --add-dir -- the shape a
    since-deleted-then-partially-replaced or truncated file could produce. Must refuse before any
    claude call, never exec claude with whatever token list resulted."""
    w = _Wheel(tmp_path)
    proc, hb = w.run(wrapper=_runtime_with_stub(tmp_path, _STUB_MALFORMED_ARGV))
    _assert_launch_context_error(w, proc, hb)


_STUB_EMPTY_TOKEN_ARGV = textwrap.dedent("""\
    import os, sys
    out = sys.argv[sys.argv.index("--out-dir") + 1]
    open(os.path.join(out, "context.txt"), "w").write("CONTEXT\\n")
    # non-empty on disk (passes [ -s ]) but every line is blank. CORRECTED (trust re-review round
    # 4, item c): the read loop (`while IFS= read -r _tok || [ -n "$_tok" ]`) on three blank lines
    # does NOT yield zero tokens -- measured directly: `printf '\\n\\n\\n'` through this exact loop
    # gives argc=3, three EMPTY-STRING tokens ($1="" $2="" $3=""), not argc=0. The shape check
    # still refuses correctly here because $1 ("") != "--add-dir", not because argc is zero.
    open(os.path.join(out, "argv.txt"), "w").write("\\n\\n\\n")
    print("launch")
    """)


def test_launch_with_blank_lines_argv_yields_empty_string_tokens_fails_closed(tmp_path):
    """The exact repro shape from the review: a file that is non-empty (passes [ -s ]) but whose
    content is all blank lines produces three empty-string tokens (argc=3, not argc=0) from the
    read loop -- must still refuse, because $1 is "" rather than --add-dir, not exec claude with
    an empty flag tail (no --tools/--allowedTools/--disallowedTools at all)."""
    w = _Wheel(tmp_path)
    proc, hb = w.run(wrapper=_runtime_with_stub(tmp_path, _STUB_EMPTY_TOKEN_ARGV))
    _assert_launch_context_error(w, proc, hb)


# Non-blocking item (b) (trust re-review round 4): "no test reproduces the real trigger: a
# pre-flight that deletes argv.txt. The exec-site re-assert is unreachable by any test." Reproduce
# the trigger directly with a fake pre-flight `claude` that deletes CTX_DIR/argv.txt as a side
# effect of the quota-preflight call -- the same pattern already used above (N5) for a fake
# pre-flight that touches DISABLED. B1's fix reads argv.txt into "$@" BEFORE the preflight call
# (right after the [ -s ] check, not deferred to the exec site), so "$@" is already captured by
# the time this deletion happens: the main run must still launch with the full, correct flag tail
# even though the file is gone from disk by the time of the exec-site re-check. This is what makes
# the exec-site re-assert actually reachable and exercised: it re-validates the shape of "$@" (not
# the file), and this test is the first one where the file genuinely does not exist at exec time.
_FAKE_CLAUDE_DELETES_ARGV_MID_PREFLIGHT = """\
#!/usr/bin/env python3
# Pre-flight call (argv[2] == the fixed preflight prompt): deletes CTX_DIR/argv.txt as a side
# effect (the real-world trigger the review named -- a pre-flight window in which the file is
# removed from disk), simulating the exact TOCTOU window B1 closes. A SECOND invocation (the main
# run) must still launch with the full, correct flag tail, because B1 already captured argv.txt
# into "$@" BEFORE this pre-flight call ran -- record every invocation so the test can assert on
# both the count and the main run's actual argv.
import glob, json, os, subprocess, sys
dump = os.environ["FAKE_CLAUDE_DUMP"]
argv = sys.argv[1:]
if len(argv) > 1 and argv[1] == "quota preflight — reply OK":
    with open(dump, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"preflight_argv": argv}) + "\\n")
    tmpdir = os.environ["TMPDIR"]
    for ctx_dir in glob.glob(os.path.join(tmpdir, "oversight_wheel_ctx.*")):
        argv_txt = os.path.join(ctx_dir, "argv.txt")
        if os.path.exists(argv_txt):
            os.remove(argv_txt)
    print("quota preflight ok")
    sys.exit(0)
# Main run: same shape as the real argv_json fake claude (dump argv, optionally write a
# session-shaped END through the real sink).
scratch = argv[argv.index("--add-dir") + 1] if "--add-dir" in argv else None
rec = {"argv": argv, "env": {k: v for k, v in os.environ.items() if k.startswith("OVERSIGHT_")},
       "scratch_exists": bool(scratch and os.path.isdir(scratch))}
with open(dump, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\\n")
if scratch:
    end = os.path.join(scratch, "end.json")
    with open(end, "w", encoding="utf-8") as fh:
        json.dump({"exit": 0, "finished_at": "now", "summary": "done"}, fh)
    subprocess.run(["python3", os.environ["FAKE_CLAUDE_SINK"], "heartbeat", "--from", end], check=False)
print("OK")
sys.exit(0)
"""


def test_argv_txt_deleted_during_preflight_window_still_launches_with_full_flags(tmp_path):
    """B1's early-read design (argv.txt captured into "$@" before the preflight, not just before
    the exec) makes a mid-preflight deletion of the file harmless: the main run launches with the
    full, correct --disallowedTools tail even though the file no longer exists on disk by the time
    of the exec-site re-check. Falsified by reverting the early read back to the exec site (its
    pre-fix location): this test goes RED because the exec-site read would then see an
    already-deleted file and refuse, or (pre-B1-entirely) launch with zero tokens."""
    w = _Wheel(tmp_path)
    w.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "0"
    fake = w.bin / "claude"
    fake.write_text(_FAKE_CLAUDE_DELETES_ARGV_MID_PREFLIGHT)
    fake.chmod(0o755)
    proc, hb = w.run()
    invocations = w.dumps()
    main_runs = [r for r in invocations if "argv" in r]
    preflight_calls = [r for r in invocations if "preflight_argv" in r]
    assert len(preflight_calls) == 1, f"pre-flight must fire exactly once: {invocations}"
    assert len(main_runs) == 1, f"main run must fire exactly once with argv.txt deleted mid-preflight: {invocations}"
    argv = main_runs[0]["argv"]
    assert "--add-dir" in argv, argv
    assert "--disallowedTools" in argv, argv
    assert hb is not None
    assert hb.get("hard_stop") is None, hb
    assert hb.get("status") == "ok", hb


# B1(b): a label that LOOKS like a wheel job (either plist naming convention, or the wheel's own
# prompt file) but with WHEEL_SLUG unset/empty previously took the wrapper's unrestricted
# non-wheel branch outright -- no kill switch, no lock, no launch-context flags. Every combination
# below must refuse before any claude call, paired with a recovery test proving the exact same
# label DOES launch (fully gated, taking the real wheel path) once WHEEL_SLUG is set.
_WHEEL_LOOKING_LABELS = ["com.oversight.wheel.csa", "manual-wheel-csa"]


@pytest.mark.parametrize("label", _WHEEL_LOOKING_LABELS)
def test_wheel_looking_label_with_missing_slug_refuses_before_any_claude_call(tmp_path, label):
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    proc, hb = w.run(label=label)
    assert proc.returncode == 0
    assert w.dumps() == [], "claude must not be launched when a wheel-looking label has no WHEEL_SLUG"
    assert hb["hard_stop"] == "wheel-slug-missing"
    assert hb["status"] == "failed"
    assert hb["exit"] == 79
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1 and lines[0].startswith("WRAPPER: refused before launch — wheel-slug-missing: "), proc.stdout
    assert hb["summary"] == lines[0]


@pytest.mark.parametrize("label", _WHEEL_LOOKING_LABELS)
def test_wheel_looking_label_with_missing_slug_also_refuses_when_disabled_is_present(tmp_path, label):
    """The label guard fires BEFORE the kill switch (it has no WHEEL_SLUG to check DISABLED.wheel.*
    against anyway) -- a DISABLED marker present must not change the refusal code or let claude
    launch either way."""
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    (w.claude / "schedules").mkdir(parents=True, exist_ok=True)
    (w.claude / "schedules" / "DISABLED").touch()
    proc, hb = w.run(label=label)
    assert w.dumps() == []
    assert hb["hard_stop"] == "wheel-slug-missing"


@pytest.mark.parametrize("label", _WHEEL_LOOKING_LABELS)
def test_wheel_looking_label_recovers_and_launches_fully_gated_once_slug_set(tmp_path, label):
    """Recovery pair for the two tests above: the exact same label, with WHEEL_SLUG restored,
    must launch claude through the real wheel path (flags present), never through the
    unrestricted non-wheel branch."""
    w = _Wheel(tmp_path)
    if label.startswith("manual-"):
        w.env["WHEEL_ONDEMAND"] = "1"
    proc, hb = w.run(label=label)
    rec = w.main_run()
    assert "--add-dir" in rec["argv"]
    assert "--disallowedTools" in rec["argv"]
    assert hb.get("hard_stop") is None


def test_non_wheel_prompt_file_named_issue_wheel_txt_with_missing_slug_refuses(tmp_path):
    """The guard also fires off the PROMPT FILE basename, not only the job label: a non-wheel-
    looking label launched with issue_wheel.txt as its prompt (e.g. a misconfigured plist) must
    still refuse rather than run the wheel's own prompt with zero restrictions."""
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    wheel_prompt = w.tmp / "issue_wheel.txt"
    wheel_prompt.write_text("do the wheel job\n")
    w.prompt = wheel_prompt
    proc, hb = w.run(label="com.oversight.csa.testarch")
    assert w.dumps() == []
    assert hb["hard_stop"] == "wheel-slug-missing"


def test_ordinary_non_wheel_job_is_unaffected_by_the_label_guard(tmp_path):
    """A genuinely non-wheel label with a genuinely non-wheel prompt file and no WHEEL_SLUG must
    behave exactly as before: launches claude on the unrestricted non-wheel branch."""
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    proc, hb = w.run(label="com.oversight.csa.testarch")
    assert len(w.dumps()) == 1
    assert hb.get("hard_stop") is None
# --- end BLOCKER B1 tests -------------------------------------------------------------------


# --- N5 (trust-architect, fix round): DISABLED created in the pre-flight/helper window --------
#
# Both kill switches are checked once, before the lock. Launch comes after the helper and a
# pre-flight of up to 60s, and WRAPPER CONTEXT then tells the session "both switches were absent,
# do not check them." A DISABLED marker created in that window previously still got a full run.
# A fake pre-flight `claude` that touches DISABLED mid-preflight reproduces the window directly:
# the wrapper's own second (main-run) claude invocation must never follow.
_FAKE_CLAUDE_TOUCH_DISABLED_MID_PREFLIGHT = """\
#!/usr/bin/env python3
# Pre-flight call: argv[1] is the quota-preflight prompt text. Touch DISABLED as a side effect
# (simulating an operator creating it in the window between the initial kill-switch check and the
# exec) and print ordinary quota-preflight-ok output. A SECOND invocation (the main run) must
# never happen if N5's pre-exec re-check works -- record every invocation so the test can assert
# on the count.
import os, sys
dump = os.environ["FAKE_CLAUDE_TOUCH_DUMP"]
with open(dump, "a", encoding="utf-8") as fh:
    fh.write(repr(sys.argv[1:3]) + "\\n")
if len(sys.argv) > 2 and sys.argv[2] == "quota preflight — reply OK":
    disabled = os.path.join(os.environ["HOME"], ".claude", "schedules", "DISABLED")
    open(disabled, "w").close()
    print("quota preflight ok")
    sys.exit(0)
print("OK")
sys.exit(0)
"""


def test_disabled_created_during_preflight_window_blocks_the_main_run(tmp_path):
    w = _Wheel(tmp_path)
    w.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "0"
    dump = tmp_path / "touch_dump.txt"
    w.env["FAKE_CLAUDE_TOUCH_DUMP"] = str(dump)
    fake = w.bin / "claude"
    fake.write_text(_FAKE_CLAUDE_TOUCH_DISABLED_MID_PREFLIGHT)
    fake.chmod(0o755)
    proc, hb = w.run()
    invocations = dump.read_text().splitlines() if dump.exists() else []
    assert len(invocations) == 1, f"the main run must never fire once DISABLED exists: {invocations}"
    assert hb is not None
    assert hb["status"] == "skipped-disabled"
    assert hb["hard_stop"] == "1"
    assert "created after the initial check" in hb["summary"]
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert any(line.startswith("WRAPPER: skipped-disabled (global)") for line in lines), proc.stdout


_FAKE_CLAUDE_TOUCH_PER_JOB_DISABLED_MID_PREFLIGHT = """\
#!/usr/bin/env python3
import os, sys
dump = os.environ["FAKE_CLAUDE_TOUCH_DUMP"]
with open(dump, "a", encoding="utf-8") as fh:
    fh.write(repr(sys.argv[1:3]) + "\\n")
if len(sys.argv) > 2 and sys.argv[2] == "quota preflight — reply OK":
    disabled = os.path.join(os.environ["HOME"], ".claude", "schedules", "DISABLED.wheel." + os.environ["WHEEL_SLUG"])
    open(disabled, "w").close()
    print("quota preflight ok")
    sys.exit(0)
print("OK")
sys.exit(0)
"""


def test_per_job_disabled_created_during_preflight_window_blocks_the_main_run(tmp_path):
    w = _Wheel(tmp_path)
    w.env["CSA_WHEEL_SKIP_PREFLIGHT"] = "0"
    dump = tmp_path / "touch_dump.txt"
    w.env["FAKE_CLAUDE_TOUCH_DUMP"] = str(dump)
    fake = w.bin / "claude"
    fake.write_text(_FAKE_CLAUDE_TOUCH_PER_JOB_DISABLED_MID_PREFLIGHT)
    fake.chmod(0o755)
    proc, hb = w.run()
    invocations = dump.read_text().splitlines() if dump.exists() else []
    assert len(invocations) == 1, f"the main run must never fire once DISABLED.wheel.<slug> exists: {invocations}"
    assert hb is not None
    assert hb["status"] == "skipped-disabled"
    assert hb["hard_stop"] == "2"


def test_dangling_symlink_disabled_marker_blocks_the_run(tmp_path):
    """N5's second fix: `[ -e ]` alone is false for a DANGLING symlink (one whose target no
    longer exists) -- `[ -e X ] || [ -L X ]` catches it regardless. Create DISABLED as a symlink
    to a target that never exists."""
    w = _Wheel(tmp_path)
    (w.claude / "schedules").mkdir(parents=True, exist_ok=True)
    dangling_target = w.claude / "schedules" / "does-not-exist-target"
    disabled_link = w.claude / "schedules" / "DISABLED"
    os.symlink(dangling_target, disabled_link)
    assert not os.path.exists(disabled_link)  # confirms it really is dangling
    assert os.path.islink(disabled_link)
    proc, hb = w.run()
    assert w.dumps() == [], "a dangling-symlink DISABLED marker must still block the run"
    assert hb["status"] == "skipped-disabled"
    assert hb["hard_stop"] == "1"
# --- end N5 tests --------------------------------------------------------------------------


# --- early exits leave out.log fresh (round-2 B2) ------------------------------------------


def _prep_second_slot(w):
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    w.hb_path().parent.mkdir(parents=True, exist_ok=True)
    w.hb_path().write_text(json.dumps({"job": w.label, "started_at": now, "finished_at": now, "exit": 0,
                                       "cadence": "22:10 Mon-Fri", "status": "ok", "summary": "did it"}))


def _prep_lock_held(w):
    lock = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    lock.mkdir(parents=True)
    (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "started_iso": "x",
                                                 "started_epoch": time.time(), "alarm_seconds": 7200}))


def _prep_lock_mkdir_fails(w):
    (w.claude / "schedules").mkdir(parents=True, exist_ok=True)
    (w.claude / "schedules" / "locks").write_text("a file, so mkdir -p fails")


def _prep_lock_io_error(w):
    locks = w.claude / "schedules" / "locks"
    locks.mkdir(parents=True)
    locks.chmod(0o500)


def _prep_empty_prompt(w):
    w.prompt.write_text("")


_EARLY_EXITS = {
    "global-kill": (lambda w: (w.claude / "schedules" / "DISABLED").touch(), "argv_json", None),
    "per-job-kill": (lambda w: (w.claude / "schedules" / "DISABLED.wheel.csa").touch(), "argv_json", None),
    "helper-refusal": (_mut_not_enforcing, "argv_json", None),
    "launch-context-error": (None, "argv_json", _STUB_SILENT),
    "second-slot-skip": (_prep_second_slot, "argv_json", None),
    "quota-skip": (lambda w: w.env.__setitem__("CSA_WHEEL_SKIP_PREFLIGHT", "0"), "limit", None),
    "lock-held": (_prep_lock_held, "argv_json", None),
    "empty-prompt": (_prep_empty_prompt, "argv_json", None),
}


@pytest.fixture
def _restore_modes(tmp_path):
    yield
    for p in tmp_path.rglob("locks"):
        try:
            p.chmod(0o755)
        except OSError:
            pass


@pytest.mark.parametrize("path_name", list(_EARLY_EXITS), ids=list(_EARLY_EXITS))
def test_early_exit_paths_leave_no_timestamp_divergence(tmp_path, path_name, _restore_modes):
    import heartbeat_audit as ha

    prep, mode, stub = _EARLY_EXITS[path_name]
    w = _Wheel(tmp_path, mode=mode)
    if prep:
        prep(w)
    wrapper = _runtime_with_stub(tmp_path, stub) if stub else None
    day_ago = time.time() - 86400
    proc, hb = w.run(wrapper=wrapper, launchd_logs=True, pre_age=day_ago)
    assert hb is not None and hb.get("finished_at"), (path_name, hb)
    times = ha._log_times(str(w.logs_dir), w.label)
    lines = ha.check([], None, {w.label: hb}, {w.label: times}, loaded_labels=set())
    assert not [line for line in lines if line.startswith("timestamp-divergence")], (path_name, lines)
    assert _wrapper_lines(proc.stdout), (path_name, proc.stdout)


_LEGACY_EXITS = {
    "second-slot-skip": (_prep_second_slot, "argv_json"),
    "quota-skip": (lambda w: w.env.__setitem__("CSA_WHEEL_SKIP_PREFLIGHT", "0"), "limit"),
    "lock-mkdir-failure": (_prep_lock_mkdir_fails, "argv_json"),
    "lock-io-error": (_prep_lock_io_error, "argv_json"),
    "lock-held": (_prep_lock_held, "argv_json"),
    "empty-prompt": (_prep_empty_prompt, "argv_json"),
}


@pytest.mark.parametrize("path_name", list(_LEGACY_EXITS), ids=list(_LEGACY_EXITS))
def test_wrapper_say_lines_on_legacy_early_exits(tmp_path, path_name, _restore_modes):
    prep, mode = _LEGACY_EXITS[path_name]
    w = _Wheel(tmp_path, mode=mode)
    prep(w)
    proc, hb = w.run()
    assert w.dumps() == [] or path_name == "quota-skip"
    assert hb["summary"].startswith("WRAPPER: "), hb
    assert _wrapper_lines(proc.stdout) == [hb["summary"]], (proc.stdout, hb["summary"])
    assert hb["summary"] in proc.stderr


def test_empty_prompt_non_wheel_job_prints_its_wrapper_line(tmp_path):
    """The one change non-wheel jobs see (GH #4767 round-2 B2): the shared empty-prompt exit now
    states its reason on stdout (the job's .out.log) and stderr, like every wrapper-owned exit."""
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    w.prompt.write_text("")
    proc, hb = w.run(label="com.oversight.csa.daily")
    assert w.dumps() == []
    assert hb["exit"] == 78 and hb["status"] == "failed"
    assert _wrapper_lines(proc.stdout) == [hb["summary"]]
    assert hb["summary"] in proc.stderr


# =============================================================================
# WS14-S1 slice, item 1, paragraph 1b: the per-night history appender.
# Item 1c (green_nights(), the `streak` CLI, the auditor check) is NOT tested here.
# =============================================================================


def _history_lines(w, label=None) -> list:
    path = w.hb_path(label).parent / "history" / f"{label or w.label}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_appender_present_lock_and_scratch_dirs_still_removed_on_exit(tmp_path):
    """The history appender runs INSIDE the unified _wrapper_exit_cleanup trap, never as a second,
    competing `trap ... EXIT` -- the lock dir, the wheel launch-context dir and the run's own
    scratch dir must still be removed on a normal exit, exactly as before this change."""
    w = _Wheel(tmp_path, mode="argv_json")
    proc, hb = w.run()
    assert hb is not None
    assert w.leftovers() == []
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert not lock_dir.exists()


def _lock_existence_probe_body(home_env_var: str, slug_env_var: str, out_path: str) -> str:
    """A history-body variant that records whether ITS OWN slug's lock directory still exists AT
    THE MOMENT it is invoked -- proving the append runs BEFORE the lock release, not after (a
    stamp-then-append-then-release ordering bug would show `False` here instead of `True`)."""
    return (
        "import json, os\n"
        f"home = os.environ[{home_env_var!r}]\n"
        f"slug = os.environ.get({slug_env_var!r}, '')\n"
        "lock = os.path.join(home, '.claude', 'schedules', 'locks', slug + '.lock')\n"
        f"with open({out_path!r}, 'a') as fh:\n"
        "    fh.write(json.dumps({'lock_exists': os.path.isdir(lock)}) + chr(10))\n"
    )


def test_appender_runs_while_lock_still_held_blocker3(tmp_path):
    """Blocker 3 (review round): a Python-level ordering guard, independent of the shell suite --
    the appender's OWN process observes its slug's lock directory as still PRESENT at call time,
    proving stamp -> append -> release, never append -> release -> ... or release -> append."""
    w = _Wheel(tmp_path, mode="argv_json")
    probe_out = tmp_path / "probe.jsonl"
    body = _lock_existence_probe_body("HOME", "WHEEL_SLUG", str(probe_out))
    wrapper = _real_runtime_with_history_body(tmp_path, body)
    proc, hb = w.run(wrapper=wrapper)
    assert w.main_run(), "the run never reached the real CLI at all"
    assert probe_out.exists(), "the appender was never invoked"
    records = [json.loads(line) for line in probe_out.read_text().splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["lock_exists"] is True, records
    # ...and it IS eventually released, after the append observed it held.
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert not lock_dir.exists()


def _release_before_append_mutant(tmp_path) -> "os.PathLike[str]":
    """Scratch mutant: moves the `rm -rf "$LOCKDIR"` release AHEAD of the per-night history append
    block (swapping their order) in a scratch copy of the CURRENT (already-fixed) wrapper --
    reproducing the "release before append" ordering bug blocker 3 guards against. Built fresh
    under tmp_path every call; never touches the repo file or the shared WS14-S1 mirror."""
    text = open(_WRAPPER_SH, encoding="utf-8").read()
    append_start = text.index('    # --- Per-night history append (WS14-S1')
    append_end = text.index('\n', text.index('    # --- end per-night history append ---')) + 1
    release_start = append_end
    release_end = text.index('}\ntrap _wrapper_exit_cleanup EXIT')
    append_block = text[append_start:append_end]
    release_block = text[release_start:release_end]
    mutated = text[:append_start] + release_block + append_block + text[release_end:]
    dest = tmp_path / "run_oversight_job.release_before_append.sh"
    dest.write_text(mutated)
    dest.chmod(0o755)
    return dest


def test_release_before_append_mutant_is_detected(tmp_path):
    """Falsifiability check for the ordering guard above: a mutant wrapper that releases the lock
    BEFORE appending must make the probe observe `lock_exists: False` -- this must go RED, proving
    test_appender_runs_while_lock_still_held_blocker3 actually catches the ordering bug rather
    than passing vacuously."""
    w = _Wheel(tmp_path, mode="argv_json")
    probe_out = tmp_path / "probe.jsonl"
    body = _lock_existence_probe_body("HOME", "WHEEL_SLUG", str(probe_out))
    mutant_wrapper = _release_before_append_mutant(tmp_path)
    rt = tmp_path / "rt_release_before_append"
    (rt / "schedules").mkdir(parents=True)
    (rt / "hooks").mkdir()
    wrapper = rt / "schedules" / "run_oversight_job.sh"
    wrapper.write_bytes(mutant_wrapper.read_bytes())
    for mod in ("wheel_launch_context.py", "wheel_sink.py", "_lib.py"):
        (rt / "hooks" / mod).write_bytes(open(os.path.join(_REPO_CLAUDE_DIR, "hooks", mod), "rb").read())
    (rt / "hooks" / "wheel_history.py").write_text(body)
    proc, hb = w.run(wrapper=wrapper)
    assert w.main_run(), "the run never reached the real CLI at all"
    records = [json.loads(line) for line in probe_out.read_text().splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["lock_exists"] is False, "expected the mutant's release-before-append to be observable"


def _stamp_after_append_mutant(tmp_path) -> "os.PathLike[str]":
    """Scratch mutant: moves the ENTIRE outer `if [ -n "${LOCKDIR:-}" ] && [ "${WHEEL_LOCK_HELD...
    ]; then ... fi` block (which wraps the `lock_force_reclaimed` heartbeat stamp) to AFTER the
    per-night history append (instead of before it), in a scratch copy of the CURRENT
    (already-fixed) wrapper -- reproducing the ordering bug where a force-reclaimed run's history
    line would NOT carry lock_force_reclaimed:true, because the append read the heartbeat before
    the stamp wrote it. Moving only the INNER `if [ "${LOCK_FORCE_RECLAIMED...` block (without its
    wrapping outer `if`/`fi`) leaves an orphaned `fi` behind and produces a syntactically broken
    script -- the outer block's own boundaries are what must move as a unit."""
    text = open(_WRAPPER_SH, encoding="utf-8").read()
    outer_marker = '    if [ -n "${LOCKDIR:-}" ] && [ "${WHEEL_LOCK_HELD:-0}" = "1" ]; then\n'
    outer_start = text.index(outer_marker)
    # The outer block's own closing `fi` is the first `\n    fi\n` after the outer_start, which
    # sits right before the per-night history append's own leading comment.
    append_start = text.index('    # --- Per-night history append (WS14-S1')
    outer_end = text.rindex('\n    fi\n', outer_start, append_start) + len('\n    fi\n')
    append_end = text.index('\n', text.index('    # --- end per-night history append ---')) + 1
    outer_block = text[outer_start:outer_end]
    append_block = text[outer_end:append_start] + text[append_start:append_end]
    mutated = text[:outer_start] + append_block + outer_block + text[append_end:]
    dest = tmp_path / "run_oversight_job.stamp_after_append.sh"
    dest.write_text(mutated)
    dest.chmod(0o755)
    return dest


def test_stamp_after_append_mutant_is_detected(tmp_path):
    """Falsifiability check: a mutant wrapper that stamps lock_force_reclaimed AFTER appending
    must produce a history line missing (or false on) lock_force_reclaimed -- this must go RED."""
    w = _Wheel(tmp_path)
    lock = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    lock.mkdir(parents=True)
    stale_epoch = time.time() - 999999
    (lock / "owner.json").write_text(json.dumps({"pid": 999999999, "started_iso": "x",
                                                 "started_epoch": stale_epoch, "alarm_seconds": 1}))
    w.env["CSA_WHEEL_FORCE_UNLOCK"] = "1"
    mutant_wrapper = _stamp_after_append_mutant(tmp_path)
    rt = tmp_path / "rt_stamp_after_append"
    (rt / "schedules").mkdir(parents=True)
    (rt / "hooks").mkdir()
    wrapper = rt / "schedules" / "run_oversight_job.sh"
    wrapper.write_bytes(mutant_wrapper.read_bytes())
    for mod in ("wheel_launch_context.py", "wheel_sink.py", "_lib.py"):
        (rt / "hooks" / mod).write_bytes(open(os.path.join(_REPO_CLAUDE_DIR, "hooks", mod), "rb").read())
    (rt / "hooks" / "wheel_history.py").write_bytes(open(_HISTORY_REAL, "rb").read())
    proc, hb = w.run(wrapper=wrapper)
    assert hb.get("lock_force_reclaimed") is True, hb  # the heartbeat itself is stamped correctly
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0].get("lock_force_reclaimed") is not True, (
        "expected the mutant's stamp-after-append ordering to leave the history line unstamped"
    )


def test_force_reclaimed_run_history_line_carries_lock_force_reclaimed_true(tmp_path):
    """N5 (1b review nit, WS14-S1 item 1c, GH #4767): a POSITIVE check against the REAL
    (unmutated) wrapper -- a force-reclaimed run's own history line carries
    `lock_force_reclaimed: true`, mirroring the shell suite's own CASE6 assertion
    (schedules/tests/test_run_oversight_job_lock.sh) but from the Python suite, against a
    genuinely live, in-TTL lock (not merely a stale one) -- proving the force flag overrides a
    live lock and that the append observes the SAME stamp the heartbeat itself carries."""
    w = _Wheel(tmp_path)
    lock = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    lock.mkdir(parents=True)
    live_epoch = time.time()  # genuinely live, well within TTL -- a normal acquire would refuse
    (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "started_iso": "x",
                                                 "started_epoch": live_epoch, "alarm_seconds": 300}))
    w.env["CSA_WHEEL_FORCE_UNLOCK"] = "1"
    proc, hb = w.run()
    assert hb.get("lock_force_reclaimed") is True, hb
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0].get("lock_force_reclaimed") is True, lines[0]
    # The forced run also released the lock after appending (append-before-release, never after).
    assert not lock.is_dir()


def _build_second_trap_mutant(tmp_path) -> "os.PathLike[str]":
    """A scratch copy of the CURRENT (already-fixed) wrapper with a SEPARATE `trap ... EXIT`
    appended near the top -- reproducing exactly the hazard this file's own top-of-script comment
    warns about (`trap` REPLACES, it does not stack): the second registration silently deletes the
    first one's cleanup, so the lock directory is left behind on exit. Built fresh under tmp_path
    every call; never touches the repo file or the shared WS14-S1 mirror."""
    text = open(_WRAPPER_SH, encoding="utf-8").read()
    anchor = 'trap _wrapper_exit_cleanup EXIT\n'
    assert text.count(anchor) == 1, "expected exactly one trap registration in the current wrapper"
    mutated = text.replace(
        anchor,
        anchor + 'trap \'echo "second trap fired" >&2\' EXIT  # MUTANT: replaces the unified trap\n',
        1,
    )
    dest = tmp_path / "run_oversight_job.mutant.sh"
    dest.write_text(mutated)
    dest.chmod(0o755)
    return dest


def test_second_exit_trap_mutant_leaves_the_lock_dir_behind(tmp_path):
    """Falsifiability check (CLAUDE.md §6): a mutant wrapper that registers a SECOND `trap ... EXIT`
    after the unified one must leave the lock directory behind on exit -- proving the existing
    single-trap design (which the history-appender change deliberately preserves, per its own "No
    new trap" instruction) is load-bearing, not incidental. This must go RED on the mutant."""
    w = _Wheel(tmp_path, mode="argv_json")
    mutant = _build_second_trap_mutant(tmp_path)
    proc, hb = w.run(wrapper=mutant)
    assert hb is not None
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert lock_dir.exists(), "expected the mutant's second trap to leave the lock dir behind"
    assert "second trap fired" in proc.stderr


def test_appender_writes_one_line_per_wrapper_exit_across_early_exits(tmp_path, _restore_modes):
    """The direct mirror of test_early_exit_paths_leave_no_timestamp_divergence, for the history
    appender: every wrapper-owned early exit in _EARLY_EXITS gets exactly one history line, whose
    content matches the heartbeat written for that same run."""
    for path_name, (prep, mode, stub) in _EARLY_EXITS.items():
        case_dir = tmp_path / path_name
        case_dir.mkdir()
        w = _Wheel(case_dir, mode=mode)
        if prep:
            prep(w)
        wrapper = _runtime_with_stub(case_dir, stub) if stub else None
        proc, hb = w.run(wrapper=wrapper)
        assert hb is not None, path_name
        lines = _history_lines(w)
        assert len(lines) == 1, (path_name, lines)
        assert lines[0]["exit"] == hb["exit"], path_name
        assert lines[0]["status"] == hb.get("status"), path_name
        assert lines[0]["summary"] == hb["summary"], path_name


def test_appender_second_slot_skip_record_carries_wrapper_skip_second_slot(tmp_path):
    """The second-slot skip record gains wrapper_skip: "second-slot" (slice text) so the future
    evaluator (item 1c) can identify and exclude it without matching on summary text."""
    w = _Wheel(tmp_path, mode="argv_json")
    _prep_second_slot(w)
    proc, hb = w.run()
    assert hb["wrapper_skip"] == "second-slot"
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0]["wrapper_skip"] == "second-slot"


def test_appender_kill_switch_exit_gets_a_history_line(tmp_path):
    w = _Wheel(tmp_path, mode="argv_json")
    (w.claude / "schedules" / "DISABLED").touch()
    proc, hb = w.run()
    assert hb["status"] == "skipped-disabled"
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0]["status"] == "skipped-disabled"


def test_appender_early_1_abort_writes_nothing_and_raises_no_error(tmp_path):
    """The earliest possible abort -- a missing <job-label> positional argument, which fires the
    `${1:?}` guard before HEARTBEAT_FILE or JOB_LABEL are ever assigned -- must write NO history
    line (there is no job to label it with) and must not itself error out of the trap."""
    w = _Wheel(tmp_path, mode="argv_json")
    home = w.home
    env = dict(w.env)
    proc = subprocess.run(
        ["/bin/bash", _WRAPPER_SH],  # no job-label, no prompt-file argv at all
        env=env, capture_output=True, text=True, timeout=30,
    )
    # bash's `${1:?msg}` aborts with a non-zero exit and a message on stderr; the trap still fires
    # (EXIT traps run on any exit, including this one), but with HEARTBEAT_FILE/JOB_LABEL unset,
    # the appender's own guard must have produced no history file anywhere under home.
    assert proc.returncode != 0
    # Finding 6 (review round): the trap's new `${HEARTBEAT_FILE:-}`/`${JOB_LABEL:-}`/
    # `${WHEEL_HISTORY_PY:-}` guards must be genuinely `:-`-safe under `set -u` -- an unguarded
    # reference anywhere in the new append block would itself raise "unbound variable" on this
    # exact abort path (the one case where those vars are truly never assigned), turning a clean
    # abort into a second, wrapper-caused error.
    assert "unbound variable" not in proc.stderr, proc.stderr
    history_dirs = list((home / ".claude" / "schedules" / "heartbeats").glob("history")) if \
        (home / ".claude" / "schedules" / "heartbeats").exists() else []
    for hd in history_dirs:
        assert list(hd.glob("*.jsonl")) == [], "no history line should exist after the ${1:?} abort"


def _failing_history_body(kind: str, marker_path: str) -> str:
    """A history-body variant that first proves it was actually INVOKED (writes `marker_path`,
    so a passing test can never be vacuous over a wrapper that never calls the appender at all),
    then fails in the given way."""
    write_marker = f"open({marker_path!r}, 'w').close()\n"
    if kind == "sys-exit-3":
        return write_marker + "import sys\nsys.exit(3)\n"
    if kind == "raises":
        return write_marker + "raise RuntimeError('boom')\n"
    if kind == "sigkills-self":
        return write_marker + "import os\nos.kill(os.getpid(), 9)\n"
    raise ValueError(kind)


@pytest.mark.parametrize("kind", ["sys-exit-3", "raises", "sigkills-self"])
def test_appender_failure_on_lock_held_path_keeps_exit_75_and_lock_untouched(tmp_path, kind):
    """Blocker 2 (review round): a genuinely FAILING appender (nonzero exit, an uncaught
    exception, or self-SIGKILL) must never change the wrapper's own outcome on the lock-held
    refusal path -- exit stays 75, and the OTHER run's lock (never ours to remove) is left alone.
    Uses a REAL launch runtime (_real_runtime_with_history_body), not a stub, so the appender
    genuinely executes at its real call site inside the real trap. The marker file proves the
    appender was actually invoked -- without it this test would pass just as trivially against
    the UNMODIFIED live wrapper, which never calls any appender at all."""
    w = _Wheel(tmp_path)
    _prep_lock_held(w)
    marker = tmp_path / "invoked.marker"
    wrapper = _real_runtime_with_history_body(tmp_path, _failing_history_body(kind, str(marker)))
    proc, hb = w.run(wrapper=wrapper)
    assert marker.exists(), "the appender was never actually invoked on the lock-held path"
    assert proc.returncode == 75, (proc.returncode, proc.stderr[-800:])
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert lock_dir.exists(), "the lock-held refusal must never touch a lock it doesn't own"


@pytest.mark.parametrize("kind", ["sys-exit-3", "raises", "sigkills-self"])
def test_appender_failure_on_normal_run_keeps_exit_0_and_cleans_up(tmp_path, kind):
    """The paired positive case: a genuinely FAILING appender on an ORDINARY (lock-acquiring) run
    must never change the wrapper's own process exit (0) and must never prevent the lock, launch
    context dir, and run scratch dir from being cleaned up -- `|| true` on the whole append call
    is the only thing standing between a broken wheel_history.py and a wedged lock. The marker
    file proves the appender was actually invoked (never vacuous over a wrapper with no append
    call at all)."""
    w = _Wheel(tmp_path, mode="argv_json")
    marker = tmp_path / "invoked.marker"
    wrapper = _real_runtime_with_history_body(tmp_path, _failing_history_body(kind, str(marker)))
    proc, hb = w.run(wrapper=wrapper)
    assert w.main_run(), "the run never reached the real CLI at all"
    assert marker.exists(), "the appender was never actually invoked on the normal-run path"
    assert proc.returncode == 0, (proc.returncode, proc.stderr[-800:])
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert not lock_dir.exists()
    assert w.leftovers() == []


def test_appender_normal_run_history_line_is_not_stale(tmp_path):
    """Every wrapper-owned heartbeat write in a normal run carries the SAME WRAPPER_START_ISO the
    wrapper generated at the top of this run (the START write, and every early-exit write, all
    thread the same $WRAPPER_START_ISO through) -- so a normal run's own history line must be
    stale: false. The mismatch case (a heartbeat left by a genuinely DIFFERENT run) is exercised
    directly and exhaustively against wheel_history.py's own append CLI in
    hooks/tests/test_wheel_history.py::test_append_stale_true_when_started_at_differs_from_start_iso,
    since forcing a real cross-run mismatch through the wrapper itself would require a crash
    between the heartbeat write and the trap firing -- not reproducible via a clean subprocess
    call."""
    w = _Wheel(tmp_path, mode="argv_json")
    proc, hb = w.run()
    assert hb is not None
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0].get("stale") is False, lines[0]


# =============================================================================
# Finding 6 (review round): ship the reviewer's scratch probes as real tests.
# =============================================================================


def test_appender_wheel_slug_missing_gets_one_line_exit_79(tmp_path):
    w = _Wheel(tmp_path, mode="argv_json")
    w.env.pop("WHEEL_SLUG")
    proc, hb = w.run()
    assert hb["hard_stop"] == "wheel-slug-missing"
    assert hb["exit"] == 79
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0]["exit"] == 79
    assert lines[0]["stale"] is False
    assert "ready_json_mtime" not in lines[0]


@pytest.mark.parametrize(
    "prep", [_prep_lock_mkdir_fails, _prep_lock_io_error], ids=["lock-mkdir-fail", "lock-io-error"]
)
def test_appender_lock_setup_failure_exits_75_with_one_history_line(tmp_path, prep, _restore_modes):
    w = _Wheel(tmp_path, mode="argv_json")
    prep(w)
    proc, hb = w.run()
    assert proc.returncode == 75
    lines = _history_lines(w)
    assert len(lines) == 1
    assert lines[0]["exit"] == 75
    assert lines[0]["stale"] is False


def test_appender_manual_label_writes_its_own_history_file(tmp_path):
    w = _Wheel(tmp_path, mode="argv_json")
    proc, hb = w.run(label="manual-wheel-csa")
    lines = _history_lines(w, "manual-wheel-csa")
    assert len(lines) == 1, lines
    assert lines[0]["launch"] == "manual"
    assert lines[0]["slot"] is None
    assert lines[0]["night"] is None
    # its own file, distinct from the scheduled label's
    assert _history_lines(w, "com.oversight.wheel.csa") == []


def test_appender_ready_json_mtime_end_to_end_via_real_wrapper(tmp_path):
    w = _Wheel(tmp_path, mode="argv_json")
    ready_dir = w.claude / "telemetry" / "wheel" / "csa"
    ready_dir.mkdir(parents=True)
    (ready_dir / "ready.json").write_text("{}")
    proc, hb = w.run()
    lines = _history_lines(w)
    assert len(lines) == 1
    assert "ready_json_mtime" in lines[0], lines[0]
    assert lines[0]["launch"] == "scheduled"


def test_appender_non_wheel_job_has_no_stale_key_and_null_slot(tmp_path):
    w = _Wheel(tmp_path, fixture=False)
    w.env.pop("WHEEL_SLUG", None)
    proc, hb = w.run(label="com.oversight.csa.daily")
    lines = _history_lines(w, "com.oversight.csa.daily")
    assert len(lines) == 1, lines
    assert lines[0]["launch"] == "scheduled"
    assert "stale" not in lines[0]
    assert lines[0]["slot"] is None


def test_appender_unwritable_history_dir_leaves_exit_heartbeat_and_cleanup_intact(tmp_path):
    """An unwritable `history/` path (a plain FILE where a directory is expected, so `os.makedirs`
    fails) must never change the wrapper's own exit, must still leave a valid heartbeat, and must
    never block the lock/scratch/context cleanup the trap is responsible for."""
    w = _Wheel(tmp_path, mode="argv_json")
    hbdir = w.claude / "schedules" / "heartbeats"
    hbdir.mkdir(parents=True)
    (hbdir / "history").write_text("not a directory")
    proc, hb = w.run()
    assert proc.returncode == 0
    assert hb is not None
    assert "could not write history line" in proc.stderr
    assert w.leftovers() == []
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert not lock_dir.exists()


def test_appender_sigterm_mid_run_trap_fires_once(tmp_path):
    """A SIGTERM sent to the wrapper mid-run must still fire the trap: exactly one history line,
    the lock and run-scratch dirs removed, and the wrapper exits on the signal (bash's own
    128+SIGTERM convention, 143, or a raw negative-signal wait() result depending on how the
    subprocess module reports it)."""
    w = _Wheel(tmp_path, mode="hang")
    out = open(tmp_path / "o.txt", "wb")
    err = open(tmp_path / "e.txt", "wb")
    p = subprocess.Popen(
        ["/bin/bash", _WRAPPER_SH, w.label, str(w.prompt), "22:10 Mon-Fri", "60"],
        env=w.env, stdout=out, stderr=err,
    )
    pidf = tmp_path / "hang_pid"
    for _ in range(200):
        if pidf.exists() and pidf.read_text().strip():
            break
        time.sleep(0.05)
    time.sleep(0.3)
    lock_dir = w.claude / "schedules" / "locks" / f"{w.slug}.lock"
    assert lock_dir.exists(), "the stub never actually started under the lock"
    p.send_signal(signal.SIGTERM)
    rc = p.wait(timeout=30)
    out.close()
    err.close()
    lines = _history_lines(w)
    assert rc in (143, -15), rc
    assert len(lines) == 1
    assert not lock_dir.exists()
    assert w.leftovers() == []
