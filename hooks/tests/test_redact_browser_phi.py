"""Hermetic tests for hooks/redact_browser_phi.py.

Ports the PROVEN behavior of ``~/.claude/scripts/pii_scrub.sh``: every vector
the bash scrubber guarantees (JWT redaction, Set-Cookie value redaction, named
cookie/token pair redaction, whole-value redaction under sensitive JSON keys,
JSON-in/JSON-out validity, non-JSON raw fallback, idempotency) is reproduced as
a pytest case, then expanded with adversarial inputs.

Every test that touches enforcement / logging runs under the `sandbox` fixture
so the real ~/.claude is never written. No network, no real git.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import redact_browser_phi as R

RED = "[REDACTED]"

# ---------------------------------------------------------------------------
# Manifest-driven cookie names (runtime_bundle_repo_agnostic_plan.md WS4.4,
# H7): the hook must union its GENERIC defaults (`session`, `refresh_token`,
# `auth_token`) with `manifest.security.auth_cookie_names` of the repo the
# PostToolUse hook's cwd resolves to (`git rev-parse --show-toplevel`); no
# repo, no manifest, an empty list, or a malformed manifest must all fall
# back to the generic defaults ONLY -- never a crash (fail-open, like every
# other hook in this chain). Written from the plan's spec. Falsifiability
# was proven the ordinary way here: on the pre-WS4.4 source (still hardcoding
# `app_auth_token`, no manifest lookup at all) every test below
# that depends on `security.auth_cookie_names` failed RED; WS4.4 landed
# mid-session and they now pass GREEN against the real implementation.
#
# Driven black-box via subprocess with `cwd=` set to the fixture repo, since
# the manifest resolution is inherently cwd-dependent (the hook's own
# PostToolUse invocation is a subprocess reading stdin) -- an in-process
# `os.chdir` would not exercise the real cwd-resolution mechanism, which the
# landed implementation does via a shelled-out `git rev-parse --show-toplevel`
# (see `redact_browser_phi._repo_root`).
#
# `widgetco_cred` (never `acme_auth_token`) is this section's fixture cookie
# name throughout: any name that merely CONTAINS a generic default as a
# substring (`acme_auth_token` contains `auth_token`) is already redacted by
# the generic set alone via the module's unanchored alternation regex, which
# would silently validate the wrong thing for a "manifest widened the set"
# assertion.
# ---------------------------------------------------------------------------

_HOOK_SCRIPT = Path(__file__).resolve().parent.parent / "redact_browser_phi.py"


def _git_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


def _write_manifest(repo: Path, security: dict | None, *, malformed: bool = False) -> None:
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    manifest_path = oversight / "manifest.json"
    if malformed:
        manifest_path.write_text("{not valid json,,,")
        return
    data = {
        "schema_version": 1,
        "product": {"name": "Widget Co", "slug": "widgetco"},
        "github": {"repo": "acme/widgetco"},
        "gtm": {"missions_dir": ".", "inbox_label": "dept:marketing"},
    }
    if security is not None:
        data["security"] = security
    manifest_path.write_text(json.dumps(data))


def _run_hook(cwd: Path, stdin_text: str, *, claude_dir: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if claude_dir is not None:
        env["CLAUDE_DIR"] = str(claude_dir)
    else:
        env.pop("CLAUDE_DIR", None)
    # Enforcement must be ON so the scrubbed (not the log-only original) text
    # is what main() emits -- these tests assert on the EMITTED payload.
    env["CSA_ENFORCE"] = "1"
    for var in ("CSA_DISABLE_HOOKS",):
        env.pop(var, None)
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        cwd=str(cwd),
        input=stdin_text,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_manifest_named_cookie_redacted_in_repo_with_matching_manifest(tmp_path):
    """RED today: the hook has no manifest lookup at all, so a custom cookie
    name declared only in the repo's manifest passes through unredacted.

    Uses `widgetco_cred` (not `acme_auth_token`) as the custom name: any
    name that merely CONTAINS one of the generic defaults as a substring
    (e.g. `acme_auth_token` contains `auth_token`) is already redacted by
    the generic set alone, via the module's own unanchored alternation
    regex -- that would validate the wrong thing here. `widgetco_cred`
    shares no substring with any generic default, so it isolates whether
    the manifest union actually widened the redacted set."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, {"auth_cookie_names": ["widgetco_cred"]})
    proc = _run_hook(repo, "Cookie: widgetco_cred=SECRET; other=1")
    assert proc.returncode == 0
    assert "SECRET" not in proc.stdout
    assert "widgetco_cred=" + RED in proc.stdout


def test_manifest_named_cookie_redacted_on_json_key_path_not_just_cookiepair(tmp_path):
    """The COOKIEPAIR (`name=value`) and JSON-key (`SENSITIVE_KEYS` exact
    membership) redaction paths have DIFFERENT matching semantics -- COOKIEPAIR
    is an unanchored substring alternation, so a name like `auth_token` also
    incidentally catches `app_auth_token` as a citer string;
    the JSON-key path is exact `k.lower() in SENSITIVE_KEYS` and does NOT.
    Every manifest test above drives stdin through the Cookie-header/COOKIEPAIR
    path only -- this is the one that proves the manifest mechanism ALSO
    widens the JSON-key path, which is CSA's actual real-world redaction
    route for its auth token in a JSON tool-result payload, and was
    previously untested entirely (a regression here would pass the whole
    suite green while silently un-redacting CSA's real token on this path)."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, {"auth_cookie_names": ["widgetco_cred"]})
    payload = json.dumps({"widgetco_cred": "SECRET"})
    proc = _run_hook(repo, payload)
    assert proc.returncode == 0
    assert "SECRET" not in proc.stdout
    parsed = json.loads(proc.stdout)
    assert parsed["widgetco_cred"] == RED


def test_manifest_named_cookie_paired_with_recovery_generic_default_still_works(tmp_path):
    """Required pairing for the redaction-gate assertion above: the generic
    default cookie names still redact in the SAME repo/manifest -- adding a
    custom name must never narrow or replace the generic set."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, {"auth_cookie_names": ["widgetco_cred"]})
    proc = _run_hook(repo, "Cookie: auth_token=SECRET2; other=1")
    assert proc.returncode == 0
    assert "SECRET2" not in proc.stdout
    assert "auth_token=" + RED in proc.stdout


def test_no_repo_manifest_named_cookie_not_redacted_but_generic_default_is(tmp_path):
    """Outside any git repo: no manifest can be resolved, so the manifest-only
    custom cookie name (`widgetco_cred`) must NOT be redacted -- but the
    hook must still redact its own generic default (`auth_token`), proving
    the no-repo path recovers to a working (if narrower) redaction set
    rather than silently redacting nothing at all."""
    outside = tmp_path / "not_a_repo"
    outside.mkdir()
    payload = "Cookie: widgetco_cred=KEEPME; auth_token=SECRET3"
    proc = _run_hook(outside, payload)
    assert proc.returncode == 0
    assert "widgetco_cred=KEEPME" in proc.stdout
    assert "SECRET3" not in proc.stdout
    assert "auth_token=" + RED in proc.stdout


def test_empty_auth_cookie_names_list_falls_back_to_generic_only(tmp_path):
    """`security.auth_cookie_names: []` in the manifest must still leave the
    GENERIC defaults redacting -- an explicit empty list is not a crash and
    not a "redact nothing" signal."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, {"auth_cookie_names": []})
    proc = _run_hook(repo, "Cookie: session=SECRET4; refresh_token=SECRET5")
    assert proc.returncode == 0
    assert "SECRET4" not in proc.stdout
    assert "SECRET5" not in proc.stdout
    assert "session=" + RED in proc.stdout
    assert "refresh_token=" + RED in proc.stdout


def test_malformed_manifest_falls_back_to_generic_only_no_traceback(tmp_path):
    """A manifest that fails to parse must never crash the hook (fail-open,
    like the rest of the chain) -- it degrades to the generic default cookie
    names, and the process must not print a Python traceback to stderr."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, None, malformed=True)
    proc = _run_hook(repo, "Cookie: auth_token=SECRET6")
    assert proc.returncode == 0
    assert "SECRET6" not in proc.stdout
    assert "auth_token=" + RED in proc.stdout
    assert "Traceback" not in proc.stderr


def test_malformed_manifest_recovery_fix_manifest_then_custom_name_redacted(tmp_path):
    """Required recovery pairing for the malformed-manifest gate above: once
    the SAME repo's manifest is fixed to a valid, well-formed one naming a
    custom cookie, that custom name starts redacting -- proving the
    malformed-manifest path is a genuine degrade, not a permanent wedge."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, None, malformed=True)
    broken = _run_hook(repo, "Cookie: widgetco_cred=SECRET7")
    assert broken.returncode == 0
    assert "widgetco_cred=SECRET7" in broken.stdout  # not redacted while broken

    _write_manifest(repo, {"auth_cookie_names": ["widgetco_cred"]})
    fixed = _run_hook(repo, "Cookie: widgetco_cred=SECRET7")
    assert fixed.returncode == 0
    assert "SECRET7" not in fixed.stdout
    assert "widgetco_cred=" + RED in fixed.stdout

# A realistic-looking JWT (header.payload.signature), all base64url.
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
# Two-segment JWT (header.payload, no signature) — the regex allows this.
JWT2 = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhYmMifQ"


# ===========================================================================
# scrub_text — the leaf string scrubber (PURE, never raises).
# ===========================================================================


def test_scrub_text_redacts_full_three_segment_jwt():
    assert R.scrub_text(JWT) == RED


def test_scrub_text_redacts_two_segment_jwt():
    assert R.scrub_text(JWT2) == RED


def test_scrub_text_jwt_embedded_in_bearer_header():
    out = R.scrub_text(f"Authorization: Bearer {JWT}")
    assert JWT not in out
    assert out == f"Authorization: Bearer {RED}"


def test_scrub_text_setcookie_value_redacted():
    out = R.scrub_text("Set-Cookie: session=abc123; Path=/; HttpOnly")
    # Everything after the header name up to EOL is redacted.
    assert out == f"Set-Cookie: {RED}"


def test_scrub_text_setcookie_case_insensitive():
    out = R.scrub_text("set-cookie: refresh_token=zzz")
    assert out == f"set-cookie: {RED}"


def test_scrub_text_setcookie_stops_at_newline():
    # The value is redacted only up to CRLF/EOL; a following line survives.
    out = R.scrub_text("Set-Cookie: session=abc\nX-Other: keep")
    assert out == f"Set-Cookie: {RED}\nX-Other: keep"


def test_scrub_text_named_cookie_pair_auth_token():
    """WS4.4: `auth_token` (not the old CSA-specific `app_auth_token`
    hardcode) is the generic default name under test here. The old assertion
    happened to still pass post-change too, but only because
    `app_auth_token` CONTAINS `auth_token` as a substring in
    the module's unanchored alternation regex -- that's a coincidence of this
    particular string, not evidence the CSA-specific name is still a generic
    default (see test_scrub_csa_specific_key_no_longer_hardcoded_generically
    for the case that actually isolates it)."""
    out = R.scrub_text("auth_token=secretvalue; foo=bar")
    assert out == f"auth_token={RED}; foo=bar"


def test_scrub_text_named_cookie_pair_refresh_token():
    out = R.scrub_text("cookie: refresh_token=abc,other=1")
    assert f"refresh_token={RED}" in out
    assert "abc" not in out


def test_scrub_text_named_cookie_pair_session():
    out = R.scrub_text("session=deadbeef")
    assert out == f"session={RED}"


def test_scrub_text_named_pair_case_insensitive():
    out = R.scrub_text("SESSION=UPPERvalue")
    assert out == f"SESSION={RED}"


def test_scrub_text_non_string_passthrough():
    # Non-str leaves are returned unchanged (walker relies on this).
    assert R.scrub_text(123) == 123
    assert R.scrub_text(None) is None


def test_scrub_text_clean_text_untouched():
    assert R.scrub_text("just a normal sentence") == "just a normal sentence"


def test_scrub_text_idempotent():
    once = R.scrub_text(f"Set-Cookie: session={JWT}")
    twice = R.scrub_text(once)
    assert once == twice == f"Set-Cookie: {RED}"


# ===========================================================================
# scrub — the top-level PURE scrubber. JSON-in -> valid JSON-out; else raw.
# ===========================================================================


def test_scrub_non_json_raw_text_fallback():
    raw = f"random log line with a token {JWT} inside"
    out = R.scrub(raw)
    assert JWT not in out
    assert RED in out
    # Not JSON in, so not JSON out — it's a plain string scrub.
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_scrub_json_string_value_scrubbed_stays_valid_json():
    payload = json.dumps({"body": f"token={JWT}"})
    out = R.scrub(payload)
    parsed = json.loads(out)  # must remain valid JSON
    assert JWT not in out
    assert parsed["body"] == "token=[REDACTED]"


def test_scrub_sensitive_key_value_redacted_wholesale():
    """Updated for WS4.4 (H7): the hook no longer hardcodes ExampleApp's
    own cookie name (`app_auth_token`) -- the generic defaults
    are `session` / `refresh_token` / `auth_token`, unioned at call time with
    whatever the CALLING repo's manifest supplies (see the manifest-driven
    tests below). `R.scrub` here runs against the module-level globals
    (generic defaults only, no repo context), so `auth_token` -- not the old
    CSA-specific name -- is the generic sensitive key under test."""
    payload = json.dumps(
        {
            "authorization": "Bearer literally-anything-here",
            "refresh_token": "not-even-a-jwt",
            "session": {"nested": "object"},
            "set-cookie": "session=abc; Path=/",
            "auth_token": "xyz",
        }
    )
    parsed = json.loads(R.scrub(payload))
    assert parsed["authorization"] == RED
    assert parsed["refresh_token"] == RED
    # Whole value (even a nested object) replaced under a sensitive key.
    assert parsed["session"] == RED
    assert parsed["set-cookie"] == RED
    assert parsed["auth_token"] == RED


def test_scrub_csa_specific_key_no_longer_hardcoded_generically():
    """WS4.4 removed the CSA-specific cookie name as a GENERIC default -- it
    is redacted only when the calling repo's own manifest names it (see the
    manifest-driven tests below), never unconditionally for every repo.
    Paired with the test above: the generic set still works; this asserts
    the narrowing is real, not a regression that silently keeps the old
    hardcoded name working everywhere by accident."""
    payload = json.dumps({"app_auth_token": "xyz"})
    parsed = json.loads(R.scrub(payload))
    assert parsed["app_auth_token"] == "xyz"


def test_scrub_sensitive_key_case_insensitive():
    payload = json.dumps({"Authorization": "Bearer x", "Set-Cookie": "session=a"})
    parsed = json.loads(R.scrub(payload))
    assert parsed["Authorization"] == RED
    assert parsed["Set-Cookie"] == RED


def test_scrub_nested_json_structures_walked():
    payload = json.dumps(
        {
            "headers": [
                {"name": "Set-Cookie", "value": f"session={JWT}"},
                {"name": "X-Trace", "value": "ok"},
            ],
            "meta": {"deep": {"tok": JWT}},
        }
    )
    parsed = json.loads(R.scrub(payload))
    # The list-of-header-objects: value strings scrubbed, keys not sensitive.
    assert parsed["headers"][0]["value"] == f"session={RED}"
    assert parsed["headers"][1]["value"] == "ok"
    assert parsed["meta"]["deep"]["tok"] == RED


def test_scrub_non_string_json_leaves_preserved():
    payload = json.dumps({"count": 3, "ok": True, "ratio": 1.5, "nil": None})
    parsed = json.loads(R.scrub(payload))
    assert parsed == {"count": 3, "ok": True, "ratio": 1.5, "nil": None}


def test_scrub_json_array_top_level():
    payload = json.dumps([f"tok={JWT}", "clean", {"session": "x"}])
    parsed = json.loads(R.scrub(payload))
    assert parsed[0] == "tok=[REDACTED]"
    assert parsed[1] == "clean"
    assert parsed[2]["session"] == RED


def test_scrub_empty_string_returns_empty():
    assert R.scrub("") == ""


def test_scrub_non_string_input_returns_empty_string():
    # Defensive: a non-str payload yields "" (never raises).
    assert R.scrub(None) == ""
    assert R.scrub(42) == ""


def test_scrub_json_number_top_level_stays_number():
    # A bare JSON scalar (a number) parses; walk returns it; re-dumps to "5".
    assert R.scrub("5") == "5"


def test_scrub_idempotent_on_json():
    payload = json.dumps({"authorization": "Bearer x", "b": f"t={JWT}"})
    once = R.scrub(payload)
    twice = R.scrub(once)
    assert json.loads(once) == json.loads(twice)


# ===========================================================================
# Adversarial vectors — malformed / evasion / injection attempts.
# ===========================================================================


def test_adv_multiple_jwts_all_redacted():
    out = R.scrub_text(f"a {JWT} b {JWT2} c")
    assert JWT not in out
    assert JWT2 not in out
    assert out.count(RED) == 2


def test_adv_jwt_adjacent_punctuation_boundaries():
    # JWT wrapped in quotes/commas — regex must catch the token, leave delimiters.
    out = R.scrub_text(f'"{JWT}",next')
    assert out == f'"{RED}",next'


def test_adv_eyJ_prefix_but_not_a_jwt_left_alone():
    # "eyJ" not followed by a second ".eyJ" segment is NOT a JWT — untouched.
    s = "eyJustAWordNotAToken"
    assert R.scrub_text(s) == s


def test_adv_almost_json_but_broken_falls_back_to_text_scrub():
    # Trailing brace missing -> json.loads fails -> raw text scrub still fires.
    raw = f'{{"authorization": "Bearer {JWT}"'
    out = R.scrub(raw)
    assert JWT not in out
    assert RED in out


def test_adv_token_split_by_setcookie_stops_at_crlf():
    # CRLF terminates a Set-Cookie value; a second header line is preserved.
    out = R.scrub_text("Set-Cookie: session=abc\r\nSet-Cookie: refresh_token=def")
    assert "abc" not in out
    assert "def" not in out
    # Both header lines get their values redacted.
    assert out.count(RED) == 2


def test_adv_sensitive_key_with_list_value_redacted_wholesale():
    payload = json.dumps({"session": ["a", "b", {"c": "d"}]})
    parsed = json.loads(R.scrub(payload))
    assert parsed["session"] == RED


def test_adv_json_string_that_itself_contains_json_scrubbed_as_text():
    # A string value that looks like JSON is scrubbed as TEXT (walker sees a str).
    inner = json.dumps({"authorization": "Bearer x"})
    payload = json.dumps({"blob": inner})
    parsed = json.loads(R.scrub(payload))
    # 'authorization' here is INSIDE a string, not a JSON key -> not wholesale
    # redacted, but the value has no JWT/cookie so it survives as-is text.
    assert parsed["blob"] == inner


def test_adv_deeply_nested_does_not_crash():
    payload = json.dumps({"a": {"b": {"c": {"d": {"tok": JWT}}}}})
    parsed = json.loads(R.scrub(payload))
    assert parsed["a"]["b"]["c"]["d"]["tok"] == RED


def test_adv_unicode_and_emoji_preserved():
    s = "café ☕ 你好 — no secrets"
    assert R.scrub_text(s) == s


def test_adv_cookie_pair_value_terminates_at_semicolon_and_comma():
    out = R.scrub_text("session=abc;def")
    assert out == f"session={RED};def"


# ===========================================================================
# decide — PURE decision function driving main(). Enforce vs log-only.
# ===========================================================================


def test_decide_enforce_emits_scrubbed():
    raw = json.dumps({"authorization": "Bearer x"})
    out, changed = R.decide(raw, enforce=True)
    assert changed is True
    assert json.loads(out)["authorization"] == RED


def test_decide_log_only_emits_original_but_flags_change():
    raw = json.dumps({"authorization": "Bearer x"})
    out, changed = R.decide(raw, enforce=False)
    # LOG-ONLY: original passes through unchanged...
    assert out == raw
    # ...but we still report that a scrub WOULD have fired.
    assert changed is True


def test_decide_clean_input_unchanged_either_way():
    raw = json.dumps({"body": "nothing secret"})
    out_e, changed_e = R.decide(raw, enforce=True)
    out_l, changed_l = R.decide(raw, enforce=False)
    assert changed_e is False and changed_l is False
    assert json.loads(out_e) == json.loads(raw)
    assert out_l == raw


def test_decide_non_str_raw_yields_empty():
    out, changed = R.decide(None, enforce=True)
    assert out == ""
    assert changed is False


# ===========================================================================
# _extract_payload / _reinject — envelope handling.
# ===========================================================================


def test_extract_payload_bare_text():
    payload, env, key = R._extract_payload("just text")
    assert payload == "just text"
    assert env is None and key is None


def test_extract_payload_invalid_json_bare_text():
    payload, env, key = R._extract_payload("{not json")
    assert payload == "{not json"
    assert env is None and key is None


def test_extract_payload_non_dict_json_bare_text():
    payload, env, key = R._extract_payload("[1, 2, 3]")
    assert payload == "[1, 2, 3]"
    assert env is None and key is None


def test_extract_payload_tool_response_string():
    raw = json.dumps({"tool_response": f"session={JWT}"})
    payload, env, key = R._extract_payload(raw)
    assert payload == f"session={JWT}"
    assert key == "tool_response"
    assert env["tool_response"] == f"session={JWT}"


def test_extract_payload_tool_response_object_serialized():
    raw = json.dumps({"tool_result": {"authorization": "Bearer x"}})
    payload, env, key = R._extract_payload(raw)
    assert key == "tool_result"
    # Object result serialized to text for scrubbing.
    assert json.loads(payload) == {"authorization": "Bearer x"}


def test_extract_payload_object_without_result_key_is_bare():
    raw = json.dumps({"headers": {"session": "x"}})
    payload, env, key = R._extract_payload(raw)
    # No result wrapper -> whole object scrubbed as the payload.
    assert payload == raw
    assert env is None and key is None


def test_reinject_string_stays_string():
    assert R._reinject("orig", "scrubbed") == "scrubbed"


def test_reinject_structured_reparsed():
    out = R._reinject({"a": 1}, json.dumps({"a": RED}))
    assert out == {"a": RED}


def test_reinject_structured_unparseable_falls_back_to_text():
    out = R._reinject({"a": 1}, "not json")
    assert out == "not json"


def test_safe_dumps_ok():
    assert R._safe_dumps({"a": 1}) == '{"a": 1}'


# ===========================================================================
# main() — thin driver: reads stdin, emits stdout, logs, exits 0.
# ===========================================================================


def _run_main(monkeypatch, capsys, stdin_text):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    rc = R.main()
    out = capsys.readouterr().out
    return rc, out


def test_main_master_off_passes_through_no_log(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    raw = json.dumps({"authorization": "Bearer x"})
    rc, out = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
    # Master OFF -> untouched passthrough.
    assert out == raw
    # And no log line written.
    assert not sandbox.log_file.exists()


def test_main_enforcing_scrubs_and_logs(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    raw = json.dumps({"tool_response": f"session={JWT}"})
    rc, out = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
    envelope = json.loads(out)
    # The result inside the envelope was scrubbed.
    assert envelope["tool_response"] == f"session={RED}"
    # A scrub was logged.
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["hook"] == "redact_browser_phi"
    assert rec["decision"] == "scrub"
    assert rec["redacted"] is True
    assert rec["enforced"] is True


def test_main_log_only_when_not_enforcing(sandbox, clean_env, monkeypatch, capsys):
    # No CSA_ENFORCE, no marker -> enforcing() is False -> LOG-ONLY.
    raw = json.dumps({"tool_response": f"session={JWT}"})
    rc, out = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
    # Original secret passes through UNCHANGED in log-only mode...
    assert json.loads(out)["tool_response"] == f"session={JWT}"
    # ...but the would-scrub is recorded.
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "scrub"
    assert rec["redacted"] is True
    assert rec["enforced"] is False


def test_main_clean_input_logs_clean(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    raw = json.dumps({"tool_response": "nothing to see"})
    rc, out = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
    assert json.loads(out)["tool_response"] == "nothing to see"
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "clean"
    assert rec["redacted"] is False


def test_main_bare_non_json_stdin_scrubbed(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    raw = f"raw browser dump {JWT} trailing"
    rc, out = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
    assert JWT not in out
    assert RED in out


def test_main_object_result_reinjected_as_object(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    raw = json.dumps({"tool_result": {"authorization": "Bearer x", "ok": 1}})
    rc, out = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
    envelope = json.loads(out)
    # Result re-injected as a structured object (not a JSON string).
    assert isinstance(envelope["tool_result"], dict)
    assert envelope["tool_result"]["authorization"] == RED
    assert envelope["tool_result"]["ok"] == 1


def test_main_empty_stdin_emits_empty(sandbox, clean_env, monkeypatch, capsys):
    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(monkeypatch, capsys, "")
    assert rc == 0
    assert out == ""


def test_main_stdin_read_raises_is_swallowed(sandbox, clean_env, monkeypatch, capsys):
    class Boom:
        def read(self):
            raise IOError("no stdin")

    monkeypatch.setattr("sys.stdin", Boom())
    rc = R.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""


def test_main_never_denies_via_exit_code(sandbox, clean_env, monkeypatch, capsys):
    # Even with a secret present and enforcing, exit is always 0 (deny is JSON,
    # never an exit code — and this scrubber never denies at all).
    clean_env.setenv("CSA_ENFORCE", "1")
    raw = json.dumps({"authorization": "Bearer x"})
    rc, _ = _run_main(monkeypatch, capsys, raw)
    assert rc == 0
