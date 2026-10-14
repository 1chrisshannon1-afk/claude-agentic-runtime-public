"""Hermetic tests for hooks/mint_prod_session.py.

Ports the PROVEN behavior of ~/.claude/scripts/get_test_secret.sh. The bash exit
codes are the spec; every one is reproduced here as a pytest case against the
PURE decide() function, then expanded for full-coverage of main()'s wiring.

The keychain is NEVER invoked: fetch_secret() is the sole side-effectful call and
is monkeypatched in every test that reaches the fetch path, so the validation
branches (usage / illegal-chars / bad-prefix) are exercised WITHOUT touching the
real `security` binary. All tests run against the `sandbox` fixture ($HOME + the
_lib path constants pointed into a tmp dir), so the real ~/.claude — its log,
enforcement state — is never touched, and nothing spawns network or the keychain.
"""

from __future__ import annotations

import io
import json

import mint_prod_session as mps
import pytest

# ===========================================================================
# decide() — PURE validation. The bash exit codes ARE the spec.
#
#   0 ok · 2 usage (no/empty arg) · 3 bad-name (illegal chars OR bad prefix) ·
#   (4 lookup is a fetch outcome, not a decide() verdict).
# ===========================================================================


# --- the REQUIRED bash test vectors (exit-code parity) ---------------------


def test_decide_no_arg_is_usage():
    # bash: NAME="" -> "usage: ..." -> exit 2.
    assert mps.decide(None).code == mps.CODE_USAGE
    assert mps.decide("").code == mps.CODE_USAGE


def test_decide_illegal_chars_is_bad_name():
    # bash: case "$NAME" in *[!A-Za-z0-9._-]*) "illegal characters" -> exit 3.
    d = mps.decide("csa-livetest-x;y")
    assert d.code == mps.CODE_BAD_NAME
    assert "illegal characters" in d.reason


def test_decide_bad_prefix_is_bad_name():
    # bash: prefix not allowlisted -> "refused — ... not an allowlisted" exit 3.
    d = mps.decide("some-other-secret")
    assert d.code == mps.CODE_BAD_NAME
    assert "allowlisted" in d.reason


def test_decide_allowlisted_name_is_ok():
    # bash: csa-livetest-other-company-token passes both guards -> proceeds (exit 0).
    d = mps.decide("csa-livetest-other-company-token")
    assert d.code == mps.CODE_OK
    assert d.ok is True


# --- broader parity + edge vectors -----------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "csa-livetest-other-company-token",
        "csa-livetest-",  # bare prefix is still allowlisted (matches bash `case`)
        "csa-livetest-A.B_C-1",  # all-legal chars incl . _ -
        "csa-livetest-0",
    ],
)
def test_decide_ok_names(name):
    assert mps.decide(name).ok is True


@pytest.mark.parametrize(
    "name",
    [
        "prod-secret",
        "csa-live-test-x",  # close but NOT the allowlisted prefix
        "livetest-csa-x",
        "CSA-LIVETEST-X",  # prefix is case-sensitive in bash `case`
        "xcsa-livetest-y",  # prefix not at the START
    ],
)
def test_decide_bad_prefix_names(name):
    d = mps.decide(name)
    assert d.code == mps.CODE_BAD_NAME
    assert "allowlisted" in d.reason


@pytest.mark.parametrize(
    "name",
    [
        "csa-livetest-a b",  # space
        "csa-livetest-a;rm",  # semicolon
        "csa-livetest-$(x)",  # command-substitution chars
        "csa-livetest-a`b",  # backtick
        "csa-livetest-a/b",  # slash is not in the allowed set
        "csa-livetest-a|b",  # pipe
        "csa-livetest-é",  # non-ASCII
        "csa-livetest-a\nb",  # newline
    ],
)
def test_decide_illegal_char_names(name):
    d = mps.decide(name)
    assert d.code == mps.CODE_BAD_NAME
    assert "illegal characters" in d.reason


def test_decide_illegal_chars_checked_before_prefix():
    # A name with a bad prefix AND illegal chars is reported as illegal-chars
    # first (char `case` precedes the prefix loop in the bash), even though both
    # map to exit 3. Reason text distinguishes the branch.
    d = mps.decide("bad prefix ;")
    assert d.code == mps.CODE_BAD_NAME
    assert "illegal characters" in d.reason


def test_decide_reason_is_secret_free_and_str():
    # Reasons must be safe to log/emit (they only ever contain the item name,
    # never a value — decide never sees a value).
    for name in (None, "", "nope", "csa-livetest-ok", "bad;char"):
        assert isinstance(mps.decide(name).reason, str)


# ===========================================================================
# fetch_secret() — the ONLY side-effectful call. We mock subprocess.run so the
# real `security` binary is never invoked.
# ===========================================================================


class _Proc:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout


def test_fetch_success_strips_single_trailing_newline(monkeypatch):
    # `security -w` appends a newline; fetch strips exactly that one.
    monkeypatch.setattr(mps.subprocess, "run", lambda *a, **k: _Proc(0, "s3cr3t-value\n"))
    r = mps.fetch_secret("csa-livetest-x")
    assert r.ok is True
    assert r.value == "s3cr3t-value"


def test_fetch_preserves_interior_and_trailing_when_no_newline(monkeypatch):
    monkeypatch.setattr(mps.subprocess, "run", lambda *a, **k: _Proc(0, "a b c"))
    r = mps.fetch_secret("csa-livetest-x")
    assert r.ok is True
    assert r.value == "a b c"


def test_fetch_nonzero_returncode_is_failure(monkeypatch):
    # bash: _rc != 0 -> exit 4.
    monkeypatch.setattr(mps.subprocess, "run", lambda *a, **k: _Proc(44, ""))
    r = mps.fetch_secret("csa-livetest-x")
    assert r.ok is False
    assert r.value is None


def test_fetch_empty_value_is_failure(monkeypatch):
    # bash: -z "$VALUE" -> exit 4 even with rc 0.
    monkeypatch.setattr(mps.subprocess, "run", lambda *a, **k: _Proc(0, "\n"))
    r = mps.fetch_secret("csa-livetest-x")
    assert r.ok is False
    assert r.value is None


def test_fetch_subprocess_raises_is_failure(monkeypatch):
    def boom(*a, **k):
        raise OSError("security not found")

    monkeypatch.setattr(mps.subprocess, "run", boom)
    r = mps.fetch_secret("csa-livetest-x")
    assert r.ok is False
    assert r.value is None


def test_fetch_passes_name_as_argv_not_shell(monkeypatch):
    # Defense-in-depth: the name is passed as an argv element, never as a shell
    # string. Assert the exact argv the wrapper builds.
    captured = {}

    def fake_run(argv, *a, **k):
        captured["argv"] = argv
        captured["shell"] = k.get("shell", False)
        return _Proc(0, "v\n")

    monkeypatch.setattr(mps.subprocess, "run", fake_run)
    mps.fetch_secret("csa-livetest-name")
    assert captured["argv"] == [
        "security",
        "find-generic-password",
        "-w",
        "-s",
        "csa-livetest-name",
    ]
    assert captured["shell"] is False


# ===========================================================================
# emit_value() — the value reaches EXACTLY one destination (stdout), once,
# with no trailing newline or commentary (bash `printf '%s'`).
# ===========================================================================


def test_emit_value_writes_raw_no_newline(capsys):
    mps.emit_value("raw-secret")
    out = capsys.readouterr().out
    assert out == "raw-secret"  # no trailing newline, nothing else


# ===========================================================================
# _requested_name / _is_target — event plumbing.
# ===========================================================================


def test_requested_name_from_tool_input_keys():
    assert mps._requested_name({"tool_input": {"item": "csa-livetest-a"}}) == ("csa-livetest-a")
    assert mps._requested_name({"tool_input": {"name": "csa-livetest-b"}}) == ("csa-livetest-b")
    assert mps._requested_name({"tool_input": {"secret": "csa-livetest-c"}}) == ("csa-livetest-c")


def test_requested_name_from_bare_command_first_nonflag():
    ev = {"tool_input": {"command": "mint_prod_session --foo csa-livetest-z"}}
    assert mps._requested_name(ev) == "csa-livetest-z"


def test_requested_name_none_when_absent():
    assert mps._requested_name({}) is None
    assert mps._requested_name({"tool_input": {}}) is None
    assert mps._requested_name({"tool_input": {"command": "mint_prod_session"}}) is None


def test_requested_name_tool_input_not_dict():
    assert mps._requested_name({"tool_input": "nope"}) is None


def test_requested_name_swallows_get_exception():
    class RaisingGet:
        def get(self, *a, **k):
            raise RuntimeError("boom")

    assert mps._requested_name(RaisingGet()) is None


def test_requested_name_ignores_nonstr_and_empty_values():
    # non-str / empty structured values are skipped; falls through to None.
    assert mps._requested_name({"tool_input": {"item": 5, "name": ""}}) is None


def test_is_target_by_tool_name():
    assert mps._is_target({"tool_name": mps.TOOL_NAME}) is True


def test_is_target_by_command_program():
    assert mps._is_target({"tool_input": {"command": "mint_prod_session csa-x"}}) is True
    assert (
        mps._is_target({"tool_input": {"command": "/usr/local/bin/get_test_secret.sh csa-x"}})
        is True
    )


def test_is_target_false_for_other_tools():
    assert mps._is_target({"tool_name": "Bash", "tool_input": {"command": "ls -la"}}) is (False)
    assert mps._is_target({}) is False


# ===========================================================================
# main() — the thin wiring. Always returns 0; deny is via JSON. LOG-ONLY unless
# enforcing(); CSA_DISABLE_HOOKS master-off. The keychain is always mocked.
# ===========================================================================


def _stdin(monkeypatch, ev):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(ev)))


def _no_fetch(monkeypatch):
    """Guard: if any test path unexpectedly reaches fetch_secret, fail loudly."""

    def guard(name):
        raise AssertionError("fetch_secret must not be called on this path")

    monkeypatch.setattr(mps, "fetch_secret", guard)


def test_main_master_off_is_noop(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    _no_fetch(monkeypatch)
    _stdin(monkeypatch, {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "bad;"}})
    assert mps.main() == 0
    assert capsys.readouterr().out == ""
    assert not sandbox.log_file.exists()  # master-off: nothing logged at all


def test_main_non_target_event_is_noop(sandbox, clean_env, monkeypatch, capsys):
    _no_fetch(monkeypatch)
    _stdin(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert mps.main() == 0
    assert capsys.readouterr().out == ""
    assert not sandbox.log_file.exists()


def test_main_usage_log_only_when_not_enforcing(sandbox, clean_env, monkeypatch, capsys):
    _no_fetch(monkeypatch)
    _stdin(monkeypatch, {"tool_name": mps.TOOL_NAME, "tool_input": {}})
    assert mps.main() == 0
    out = capsys.readouterr().out
    assert out == ""  # LOG-ONLY: no deny JSON emitted when not enforcing
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["hook"] == mps.HOOK
    assert rec["decision"] == "deny"
    assert rec["code"] == mps.CODE_USAGE


def test_main_usage_denies_when_enforcing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    _no_fetch(monkeypatch)
    _stdin(monkeypatch, {"tool_name": mps.TOOL_NAME, "tool_input": {}})
    assert mps.main() == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "usage" in obj["systemMessage"]


def test_main_bad_prefix_denies_when_enforcing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    _no_fetch(monkeypatch)
    _stdin(
        monkeypatch,
        {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "prod-real-secret"}},
    )
    assert mps.main() == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "allowlisted" in obj["systemMessage"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["code"] == mps.CODE_BAD_NAME
    assert rec["item"] == "prod-real-secret"


def test_main_illegal_char_denies_when_enforcing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    _no_fetch(monkeypatch)
    _stdin(
        monkeypatch,
        {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "csa-livetest-a;b"}},
    )
    assert mps.main() == 0
    obj = json.loads(capsys.readouterr().out)
    assert "illegal characters" in obj["systemMessage"]


def test_main_ok_mints_value_to_stdout_and_logs_without_value(
    sandbox, clean_env, monkeypatch, capsys
):
    # The happy path: value goes to the jar path (stdout) ONLY; the log records
    # the decision + item name but NEVER the secret value.
    monkeypatch.setattr(mps, "fetch_secret", lambda n: mps.FetchResult(True, "SECRET-XYZ"))
    _stdin(
        monkeypatch,
        {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "csa-livetest-other-company"}},
    )
    assert mps.main() == 0
    out = capsys.readouterr().out
    assert out == "SECRET-XYZ"  # exactly the value, once, no commentary
    log_text = sandbox.log_file.read_text()
    assert "SECRET-XYZ" not in log_text  # value NEVER logged
    rec = json.loads(log_text.strip().splitlines()[-1])
    assert rec["decision"] == "minted"
    assert rec["code"] == mps.CODE_OK
    assert rec["item"] == "csa-livetest-other-company"


def test_main_ok_mints_even_when_not_enforcing(sandbox, clean_env, monkeypatch, capsys):
    # Minting a valid, allowlisted secret is the tool's JOB — it succeeds
    # regardless of enforcing(); enforcing only gates the DENY paths.
    monkeypatch.setattr(mps, "fetch_secret", lambda n: mps.FetchResult(True, "V"))
    _stdin(
        monkeypatch,
        {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "csa-livetest-ok"}},
    )
    assert mps.main() == 0
    assert capsys.readouterr().out == "V"


def test_main_lookup_failure_log_only_when_not_enforcing(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setattr(mps, "fetch_secret", lambda n: mps.FetchResult(False, None))
    _stdin(
        monkeypatch,
        {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "csa-livetest-missing"}},
    )
    assert mps.main() == 0
    assert capsys.readouterr().out == ""  # no value, and LOG-ONLY -> no deny JSON
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "lookup-failed"
    assert rec["code"] == mps.CODE_LOOKUP


def test_main_lookup_failure_denies_when_enforcing(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    monkeypatch.setattr(mps, "fetch_secret", lambda n: mps.FetchResult(False, None))
    _stdin(
        monkeypatch,
        {"tool_name": mps.TOOL_NAME, "tool_input": {"item": "csa-livetest-missing"}},
    )
    assert mps.main() == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "keychain lookup failed" in obj["systemMessage"]


def test_main_via_bare_command_line(sandbox, clean_env, monkeypatch, capsys):
    # Invocation as a bare command line (program + name) is also gated + minted.
    monkeypatch.setattr(mps, "fetch_secret", lambda n: mps.FetchResult(True, "CMDVAL"))
    _stdin(
        monkeypatch,
        {"tool_input": {"command": "mint_prod_session csa-livetest-cli"}},
    )
    assert mps.main() == 0
    assert capsys.readouterr().out == "CMDVAL"


def test_main_garbage_stdin_is_noop(sandbox, clean_env, monkeypatch, capsys):
    _no_fetch(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert mps.main() == 0
    assert capsys.readouterr().out == ""
    assert not sandbox.log_file.exists()


def test_main_uses_event_cwd_for_enforce_resolution(
    sandbox, clean_env, monkeypatch, capsys, git_repo, enforce_marker
):
    # A per-project .csa-enforce marker in the event's cwd turns on enforcement,
    # so a bad name in that repo produces a deny (proving main() resolves
    # enforcing() against the EVENT cwd, not the process cwd).
    enforce_marker(git_repo)
    _no_fetch(monkeypatch)
    _stdin(
        monkeypatch,
        {
            "tool_name": mps.TOOL_NAME,
            "cwd": str(git_repo),
            "tool_input": {"item": "not-allowlisted"},
        },
    )
    assert mps.main() == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
