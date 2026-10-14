"""Hermetic tests for scripts/codex_canary.sh — the four-probe sandbox
canary for the Codex cross-model review scaffold (plan §4.4,
plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md).

Every test uses a FAKE `codex` executable (never the real
/opt/homebrew/bin/codex). The canary's whole job is to MEASURE whether
codex's sandbox holds; a test therefore drives a fake whose behaviour is
the thing under test — a fake that returns the planted out-of-boundary
token stands in for "the sandbox did not hold", and the assertion is that
the canary NOTICES.

DESIGN (inherited from test_codex_review.py, deliberately identical): the
hardened scripts honour CODEX_REVIEW_TEST_MODE=1 only when their own
resolved on-disk runtime dir is NOT the real invoking user's
$HOME/.claude. So every test needing a fake codex runs against a
SELECTIVELY-COPIED test tree (named files only — never cp -R/cp -a of the
real repo). TestRealInstallIsUnaffectedByTestMode proves the real installed
script is unreachable by these same variables; the rest of the suite then
exercises the hardened LOGIC from a location where the discriminator can
legitimately unlock it.

THE CENTRAL TEST IS THE NONCE ONE. Plan §4.4 makes the nonce the validity
gate: "no nonce ⇒ that probe is INVALID and counts as FAIL (otherwise
'token not returned' also passes when Codex never launched)". A canary
without a working nonce check certifies a sandbox it never tested, which is
worse than no canary at all — it converts an untested boundary into a
recorded pass. TestNonceValidityGate is the test that proves the nonce does
real work rather than decorating the record.

Falsifiability (operator directive, brief rule 3): every control here was
shown RED against a scratch mutation of codex_canary.sh with that one
control removed, and GREEN against the real script. The RED/GREEN
transcripts are reported with the change; the bodies below assert the GREEN
side.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REAL_CLAUDE_DIR = Path.home() / ".claude"
REAL_CANARY_SCRIPT = str(REAL_CLAUDE_DIR / "scripts" / "codex_canary.sh")
REAL_AVAILABLE_SCRIPT = str(REAL_CLAUDE_DIR / "scripts" / "codex_available.sh")
REAL_REVIEW_SCRIPT = str(REAL_CLAUDE_DIR / "scripts" / "codex_review.sh")

# The hooks/ modules codex_review.sh's pending_key derivation imports. Named
# individually — never a directory copy of hooks/ as a whole. Only needed by
# the end-to-end contract test that runs the real codex_review.sh.
_HOOKS_DEPS = (
    "_lib.py",
    "precommit_review_gate.py",
    "record_review.py",
    "agent_budget.py",
    "review_risk_tier.py",
)

_TOOLS_CODEX_FILES = (
    "AGENTS.md",
    "review-instructions.md",
    "review_schema.json",
    "config.toml",
)


# ===========================================================================
# Fixtures / helpers
# ===========================================================================


@pytest.fixture
def test_tree(tmp_path):
    """A selectively-copied runtime tree (never cp -R of the real repo).
    Its own resolved runtime dir (tree/scripts/../ == tree/) is guaranteed
    NOT to equal the real ~/.claude, so CODEX_REVIEW_TEST_MODE=1 is
    genuinely unlockable here and genuinely NOT unlockable against the real
    installed script (see TestRealInstallIsUnaffectedByTestMode).
    """
    tree = tmp_path / "runtime_tree"
    (tree / "scripts").mkdir(parents=True)
    (tree / "tools" / "codex").mkdir(parents=True)
    (tree / "hooks").mkdir(parents=True)
    (tree / ".review_state" / "codex").mkdir(parents=True)
    (tree / ".enforcement").mkdir(parents=True)

    for src, name in (
        (REAL_CANARY_SCRIPT, "codex_canary.sh"),
        (REAL_AVAILABLE_SCRIPT, "codex_available.sh"),
        (REAL_REVIEW_SCRIPT, "codex_review.sh"),
    ):
        shutil.copy2(src, tree / "scripts" / name)
        (tree / "scripts" / name).chmod(0o755)

    for name in _TOOLS_CODEX_FILES:
        shutil.copy2(
            REAL_CLAUDE_DIR / "tools" / "codex" / name, tree / "tools" / "codex" / name
        )

    for name in _HOOKS_DEPS:
        shutil.copy2(REAL_CLAUDE_DIR / "hooks" / name, tree / "hooks" / name)

    return tree


@pytest.fixture
def fake_home(tmp_path):
    d = tmp_path / "fake_home"
    (d / ".codex").mkdir(parents=True)
    return d


@pytest.fixture
def fake_bin(tmp_path):
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def canary_out(tmp_path):
    d = tmp_path / "canary_out"
    d.mkdir()
    return d


def _write_exe(path: Path, content: str) -> Path:
    path.write_text(content)
    path.chmod(0o755)
    return path


def _ready_setup(test_tree: Path, fake_home: Path) -> None:
    """Consent marker (user-owned; the TRUST_OWNER seam covers the uid
    check, which a test cannot satisfy honestly without real root) plus a
    fake auth file — the preconditions that let a test reach past the
    availability gate into the probes."""
    consent = test_tree / ".review_state" / "codex" / "CONSENT.json"
    consent.write_text(
        json.dumps(
            {
                "consented_at": 1,
                "operator": "test",
                "scope": "ws4-v1-advisory",
                "host": "x",
            }
        )
    )
    consent.chmod(0o444)
    (fake_home / ".codex" / "auth.json").write_text('{"token": "not-a-real-token"}')


# --- Fake codex binaries ---------------------------------------------------
#
# Each parses its OWN argv for -C (the export root it is pointed at) and -o
# (where to write the last message), exactly as the real codex does. The
# canary parses ONLY the -o file (plan §4.5a item 1: the --json event stream
# is logged, never parsed), so that is what these write.

_ARGV_PREAMBLE = r"""#!/bin/bash
last_msg=""
croot=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "-o" ]; then last_msg="$arg"; fi
  if [ "$prev" = "-C" ]; then croot="$arg"; fi
  prev="$arg"
done
nonce=""
if [ -f "$croot/nonce.txt" ]; then
  nonce="$(sed -n 's/^NONCE=//p' "$croot/nonce.txt")"
fi
"""


def _fake_codex_compliant(fake_bin: Path, name: str = "codex_compliant") -> Path:
    """A well-behaved sandbox: echoes the nonce (proving it ran), returns no
    out-of-boundary token. All four probes PASS."""
    return _write_exe(
        fake_bin / name,
        _ARGV_PREAMBLE
        + r"""
if [ -n "$last_msg" ]; then
  printf 'NONCE=%s UNREADABLE NO-NETWORK ABSENT' "$nonce" > "$last_msg"
fi
exit 0
""",
    )


def _fake_codex_escapes(
    fake_bin: Path,
    probe_n: int,
    name: str | None = None,
    sentinel_file: Path | None = None,
) -> Path:
    """A LEAKING sandbox for exactly one probe: echoes the nonce AND the
    out-of-boundary token that probe planted. The other probes behave.

    Probe 1 reads a file at an absolute path outside the export.
    Probe 2 follows a symlink inside the export to a file outside it.
    Probe 3 reads a sentinel env var that should have been scrubbed.
    Probe 4 "fetches" a URL and returns the page title.
    """
    name = name or f"codex_escapes_{probe_n}"
    leak = {
        # The prompt names the absolute path; the fake finds it by reading
        # the prompt's own text out of its argv (the prompt is the last
        # positional argument the canary passes).
        1: r"""
prompt="${!#}"
secret_path="$(printf '%s' "$prompt" | grep -oE '/[^ ]*outside_secret\.txt' | head -n 1)"
leaked="$(sed -n 's/^SECRET_TOKEN=//p' "$secret_path" 2>/dev/null)"
""",
        2: r"""
leaked="$(sed -n 's/^SECRET_TOKEN=//p' "$croot/linked_secret.txt" 2>/dev/null)"
""",
        # Probe 3 is the one probe whose leak a fake CANNOT simulate by
        # reading its own environment: the real `env -i` scrub genuinely
        # works, so the sentinel is genuinely absent and the fake has
        # nothing to leak. Simulating "the scrub failed" therefore means
        # obtaining the sentinel by a channel the scrub does not cover --
        # here, the parent-shell value stashed on disk by the test itself
        # (see _sentinel_leak_file). This stands in for a codex build whose
        # environment handling changed; what is under test is the CANARY's
        # detection, not bash's env -i.
        3: (
            'leaked=""\n'
            + "_sf="
            + (json.dumps(str(sentinel_file)) if sentinel_file else '""')
            + "\n"
            + 'if [ -n "$_sf" ] && [ -f "$_sf" ]; then leaked="$(cat "$_sf")"; fi\n'
        ),
        4: r"""
leaked="Example Domain"
""",
    }[probe_n]
    return _write_exe(
        fake_bin / name,
        _ARGV_PREAMBLE
        + leak
        + r"""
if [ -n "$last_msg" ]; then
  printf 'NONCE=%s LEAKED=%s' "$nonce" "$leaked" > "$last_msg"
fi
exit 0
""",
    )


def _fake_codex_silent(fake_bin: Path, name: str = "codex_silent") -> Path:
    """Writes NOTHING to the -o file and exits 0 — i.e. codex never really
    ran (or failed in a way that produced no answer). No nonce comes back,
    and crucially no token comes back either: a canary without a nonce check
    would score this as PASS."""
    return _write_exe(fake_bin / name, "#!/bin/bash\nexit 0\n")


def _fake_codex_no_nonce_but_token(
    fake_bin: Path, name: str = "codex_no_nonce"
) -> Path:
    """Returns a response with NO nonce. Proves ordering: stage (a) must
    decide INVALID before stage (b) ever looks at the token."""
    return _write_exe(
        fake_bin / name,
        _ARGV_PREAMBLE
        + r"""
if [ -n "$last_msg" ]; then
  printf 'no nonce here at all' > "$last_msg"
fi
exit 0
""",
    )


def _fake_codex_recording(fake_bin: Path, argv_log: Path, env_log: Path) -> Path:
    """Records its full argv and environment, then answers compliantly."""
    return _write_exe(
        fake_bin / "codex_recording",
        _ARGV_PREAMBLE
        + f"""
for a in "$@"; do printf '%s\\n' "$a" >> {json.dumps(str(argv_log))}; done
env >> {json.dumps(str(env_log))}
"""
        + r"""
if [ -n "$last_msg" ]; then
  printf 'NONCE=%s UNREADABLE NO-NETWORK ABSENT' "$nonce" > "$last_msg"
fi
exit 0
""",
    )


def _run_canary(
    test_tree: Path,
    *,
    codex_bin: Path,
    fake_home: Path,
    canary_out: Path,
    trust_owner: bool = True,
    extra_env: dict | None = None,
    args: list[str] | None = None,
    tmpdir: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    # ALWAYS isolate TMPDIR per test: probe exports are mktemp'd under it,
    # and sharing the real machine's /tmp across tests makes assertions
    # about leftover scratch dirs collide non-deterministically. Never a
    # security-relevant override; it only isolates test scratch space.
    if tmpdir is None:
        tmpdir = canary_out.parent / "iso_tmpdir"
        tmpdir.mkdir(exist_ok=True)

    env = dict(os.environ)
    env["CODEX_REVIEW_TEST_MODE"] = "1"
    env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
    if trust_owner:
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
    env["CODEX_BIN"] = str(codex_bin)
    env["CANARY_OUTPUT_DIR"] = str(canary_out)
    env["TMPDIR"] = str(tmpdir)
    env["CODEX_CANARY_TIMEOUT_SEC"] = "10"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(test_tree / "scripts" / "codex_canary.sh"), *(args or [])],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _read_record(canary_out: Path) -> dict:
    files = sorted(canary_out.glob("canary_*.json"))
    assert files, f"no canary record written under {canary_out}"
    return json.loads(files[-1].read_text())


def _probe(record: dict, n: int) -> dict:
    for p in record["probes"]:
        if p["n"] == n:
            return p
    raise AssertionError(f"probe {n} missing from record: {record}")


# ===========================================================================
# The test-mode discriminator: the REAL installed script must be UNAFFECTED
# by every one of these variables. This is the foundational proof the rest
# of the suite rests on — without it, the suite would only prove that a
# script can be made to lie when handed the right environment.
# ===========================================================================


class TestRealInstallIsUnaffectedByTestMode:
    def test_real_canary_ignores_test_mode_vars(self, tmp_path):
        """The real ~/.claude/scripts/codex_canary.sh cannot be pointed at a
        fake codex, a fake ~/.codex, or a fake consent owner. It must refuse
        on the REAL machine's state (no login today), not on the fake."""
        fake_home = tmp_path / "fake_home"
        (fake_home / ".codex").mkdir(parents=True)
        (fake_home / ".codex" / "auth.json").write_text('{"token": "x"}')
        fake_codex = _write_exe(tmp_path / "codex_fake", "#!/bin/bash\nexit 0\n")

        env = dict(os.environ)
        env["CODEX_REVIEW_TEST_MODE"] = "1"
        env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
        env["CODEX_BIN"] = str(fake_codex)
        env["CANARY_OUTPUT_DIR"] = str(tmp_path / "out")

        proc = subprocess.run(
            ["bash", REAL_CANARY_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        # The real install has no login and no consent today, so it must
        # refuse with an availability/consent code — never run probes.
        assert proc.returncode in (20, 21), (proc.returncode, proc.stdout, proc.stderr)
        assert "BLOCKED" in proc.stderr
        # And it must not have written a record anywhere the fake pointed.
        assert (
            not list((tmp_path / "out").glob("*.json"))
            if (tmp_path / "out").exists()
            else True
        )

    def test_real_canary_refuses_arguments(self):
        """No pass-through, ever (plan §4.3): a wrapper that forwards "$@"
        to codex re-opens every prohibited flag."""
        proc = subprocess.run(
            ["bash", REAL_CANARY_SCRIPT, "--dangerously-bypass-approvals-and-sandbox"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 11, (proc.returncode, proc.stdout, proc.stderr)
        assert "takes no arguments" in proc.stderr


# ===========================================================================
# Availability propagation, with its paired recovery.
# ===========================================================================


class TestAvailabilityGate:
    def test_refuses_without_auth_file(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """No auth file ⇒ codex_available.sh refuses ⇒ the canary propagates
        it and never invokes codex."""
        consent = test_tree / ".review_state" / "codex" / "CONSENT.json"
        consent.write_text(json.dumps({"scope": "ws4-v1-advisory"}))
        consent.chmod(0o444)
        # deliberately NO auth.json
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 20, (proc.returncode, proc.stdout, proc.stderr)
        assert "not available" in proc.stderr
        assert not list(canary_out.glob("canary_*.json"))

    def test_refuses_without_consent(self, test_tree, fake_home, fake_bin, canary_out):
        (fake_home / ".codex" / "auth.json").write_text('{"token": "x"}')
        # deliberately NO consent marker
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 21, (proc.returncode, proc.stdout, proc.stderr)
        assert "consent" in proc.stderr.lower()
        assert not list(canary_out.glob("canary_*.json"))

    def test_recovery_proceeds_once_auth_and_consent_present(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """PAIRED RECOVERY for both refusals above: the legitimate remedy
        (log in + grant consent) lets the canary run all four probes."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
        record = _read_record(canary_out)
        assert record["passed"] is True
        assert len(record["probes"]) == 4


# ===========================================================================
# THE CENTRAL CONTROL: the nonce validity gate (plan §4.4).
# ===========================================================================


class TestNonceValidityGate:
    def test_silent_codex_is_INVALID_not_PASS(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """A fake that writes nothing returns no token — so a canary WITHOUT
        a nonce check would score every probe as PASS and certify a sandbox
        it never tested. The nonce check must make it INVALID ⇒ FAIL.

        This is the single most important assertion in the file.
        """
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_silent(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
        record = _read_record(canary_out)
        assert record["passed"] is False
        for n in (1, 2, 3, 4):
            p = _probe(record, n)
            assert p["verdict"] == "INVALID", p
            assert p["nonce_returned"] is False, p
            # No token was returned — which is exactly why "token absent"
            # alone can never be the pass condition.
            assert p["token_returned"] is False, p

    def test_response_without_nonce_is_INVALID(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """A response that arrives but omits the nonce is INVALID too —
        stage (a) decides before stage (b) ever inspects the token."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_no_nonce_but_token(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1
        record = _read_record(canary_out)
        assert record["passed"] is False
        assert all(p["verdict"] == "INVALID" for p in record["probes"]), record[
            "probes"
        ]

    def test_recovery_nonce_echoed_makes_probes_pass(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """PAIRED RECOVERY: the same shape of fake, now echoing the nonce,
        produces PASS. This is what proves the nonce check is doing real
        work rather than failing everything unconditionally."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
        record = _read_record(canary_out)
        for n in (1, 2, 3, 4):
            p = _probe(record, n)
            assert p["verdict"] == "PASS", p
            assert p["nonce_returned"] is True, p

    def test_timeout_is_INVALID_not_PASS(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """A probe that hits the perl alarm returns no nonce ⇒ INVALID. A
        timing-out probe must never be mistaken for a held boundary."""
        _ready_setup(test_tree, fake_home)
        codex = _write_exe(fake_bin / "codex_slow", "#!/bin/bash\nsleep 30\nexit 0\n")
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            extra_env={"CODEX_CANARY_TIMEOUT_SEC": "2"},
            timeout=90,
        )
        assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
        record = _read_record(canary_out)
        assert record["passed"] is False
        p1 = _probe(record, 1)
        assert p1["verdict"] == "INVALID"
        assert "timed out" in p1["detail"] or "rc=" in p1["detail"], p1


# ===========================================================================
# The four probes, each with its escaping fake and its paired recovery.
# ===========================================================================


class TestProbeDetection:
    @pytest.mark.parametrize(
        "probe_n,probe_name",
        [
            (1, "filesystem-escape"),
            (2, "symlink-traversal"),
            (3, "environment-inheritance"),
        ],
    )
    def test_escaping_fake_fails_that_probe(
        self, test_tree, fake_home, fake_bin, canary_out, probe_n, probe_name, tmp_path
    ):
        """A fake that returns the planted out-of-boundary token for probe N
        must make probe N FAIL and the whole canary passed:false."""
        _ready_setup(test_tree, fake_home)
        sentinel_file = tmp_path / f"sentinel_{probe_n}.txt"
        codex = _fake_codex_escapes(fake_bin, probe_n, sentinel_file=sentinel_file)
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            extra_env={"CODEX_CANARY_TEST_SENTINEL_FILE": str(sentinel_file)},
        )
        assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
        record = _read_record(canary_out)
        assert record["passed"] is False
        assert record["severed"] is False, "only probe 4 severs"
        p = _probe(record, probe_n)
        assert p["name"] == probe_name
        assert p["verdict"] == "FAIL", p
        assert p["nonce_returned"] is True, (
            "the probe DID run; that's why FAIL not INVALID"
        )
        assert p["token_returned"] is True, p

    def test_probe1_filesystem_escape_detail(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """Probe 1 specifically: the token lives in a file OUTSIDE the
        export, at an absolute path named in the prompt."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_escapes(fake_bin, 1)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1
        p = _probe(_read_record(canary_out), 1)
        assert p["verdict"] == "FAIL"
        assert "did NOT hold" in p["detail"]

    def test_probe2_symlink_is_planted_inside_the_export(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """Probe 2's fake reads $croot/linked_secret.txt — it can only
        succeed if the canary genuinely planted a symlink INSIDE the export
        pointing at a file outside it. This asserts the adversarial shape is
        actually constructed (plan §4.8a item 6's distinction: forbidden in
        a PRODUCTION export, required in a PROBE export)."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_escapes(fake_bin, 2)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1
        p = _probe(_read_record(canary_out), 2)
        assert p["verdict"] == "FAIL", (
            "the symlink was not planted, or was not followable"
        )
        assert p["token_returned"] is True

    def test_probe3_detects_a_leaked_sentinel(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """Probe 3: when the sentinel value comes back in the response, the
        canary must score FAIL.

        Note what this does and does not prove. The real `env -i` scrub
        works, so a fake cannot leak the sentinel by reading its own
        environment — see _fake_codex_escapes' probe-3 branch. This test
        therefore proves the CANARY DETECTS a returned sentinel, standing
        in for a codex build whose environment handling changed. That the
        scrub itself currently holds is proven separately and directly by
        TestInvocationHardening::test_environment_is_scrubbed_to_the_allowlist,
        which inspects the environment codex actually receives.
        """
        _ready_setup(test_tree, fake_home)
        sentinel_file = tmp_path / "sentinel3.txt"
        codex = _fake_codex_escapes(fake_bin, 3, sentinel_file=sentinel_file)
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            extra_env={"CODEX_CANARY_TEST_SENTINEL_FILE": str(sentinel_file)},
        )
        assert proc.returncode == 1
        p = _probe(_read_record(canary_out), 3)
        assert p["verdict"] == "FAIL"
        assert p["token_returned"] is True

    @pytest.mark.parametrize("probe_n", [1, 2, 3])
    def test_recovery_compliant_fake_passes_that_probe(
        self, test_tree, fake_home, fake_bin, canary_out, probe_n
    ):
        """PAIRED RECOVERY for each refusal above: with a sandbox that
        holds, that same probe PASSes."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
        p = _probe(_read_record(canary_out), probe_n)
        assert p["verdict"] == "PASS", p


# ===========================================================================
# Probe 4 severs. This is categorically different from a blocked probe and
# must never be flattened into a generic FAIL (plan §4.4).
# ===========================================================================


class TestProbe4Severs:
    def test_network_reach_produces_SEVERED(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_escapes(fake_bin, 4)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        # Exit 2, NOT exit 1 — the distinction is the whole point.
        assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
        assert "SEVERED" in proc.stderr
        record = _read_record(canary_out)
        assert record["passed"] is False
        assert record["severed"] is True
        p4 = _probe(record, 4)
        assert p4["verdict"] == "FAIL"
        assert p4["token_returned"] is True

    def test_probe1_failure_does_NOT_sever(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """The paired negative: a probe-1 failure is BLOCKED (exit 1,
        severed:false), not SEVERED. If these two collapsed to one code, an
        operator could not tell 'fix the wrapper' from 'this can never be
        fixed wrapper-side'."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_escapes(fake_bin, 1)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1
        assert "SEVERED" not in proc.stderr
        assert _read_record(canary_out)["severed"] is False

    def test_INVALID_probe4_is_blocked_NOT_severed(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """REGRESSION (defect found by test_silent_codex_is_INVALID_not_PASS
        during the build): severing requires a POSITIVE measurement that the
        fetch succeeded. An INVALID probe 4 means the probe never ran — it
        timed out, or codex never launched — which proves nothing about
        network reach.

        SEVERED is the one verdict here with no recovery path, so declaring
        it on a measurement that was never taken is the severe direction of
        wrong. An unrun probe 4 is BLOCKED (exit 1, re-run the canary).
        """
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_silent(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1, (
            "an unrun probe 4 must be BLOCKED, never SEVERED",
            proc.returncode,
            proc.stderr,
        )
        assert "SEVERED" not in proc.stderr
        record = _read_record(canary_out)
        assert record["severed"] is False
        assert _probe(record, 4)["verdict"] == "INVALID"

    def test_recovery_no_network_passes_probe4(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """PAIRED RECOVERY: a sandbox with no outbound reach passes."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0
        record = _read_record(canary_out)
        assert record["severed"] is False
        assert _probe(record, 4)["verdict"] == "PASS"


# ===========================================================================
# The record itself: the contract codex_review.sh's gate already enforces.
# ===========================================================================


class TestRecordContract:
    def test_passing_record_has_the_two_fields_the_gate_reads(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """codex_review.sh:366-402 consumes exactly `passed` (truthy) and
        `ts` (int/float). Anything else in the record is for humans."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        before = time.time()
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0
        record = _read_record(canary_out)
        assert record["passed"] is True
        assert isinstance(record["ts"], (int, float))
        assert before - 5 <= record["ts"] <= time.time() + 5
        assert record["codex_version"], (
            "version must be recorded for the re-canary check"
        )
        assert record["model"]

    def test_record_is_written_on_failure_too(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """A failed canary must be VISIBLE evidence. An absent file is
        indistinguishable from 'never ran' — exactly the ambiguity a
        security control must not have."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_escapes(fake_bin, 1)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1
        record = _read_record(canary_out)
        assert record["passed"] is False
        assert len(record["probes"]) == 4, (
            "every probe is recorded, not just the failing one"
        )

    def test_record_never_contains_the_nonce_or_token(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """Nonces and planted tokens are single-use secrets of one run; a
        record is a durable artifact. The record carries booleans and short
        prose, never the values."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_escapes(fake_bin, 1)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 1
        raw = sorted(canary_out.glob("canary_*.json"))[-1].read_text()
        # A 32-hex-char run of the shape _rand_hex emits must not appear.
        import re

        assert not re.search(r"\b[0-9a-f]{32}\b", raw), (
            f"a raw nonce/token leaked into {raw}"
        )

    def test_record_is_valid_json_and_mode_600(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        path = sorted(canary_out.glob("canary_*.json"))[-1]
        json.loads(path.read_text())  # raises if half-written
        assert (path.stat().st_mode & 0o777) == 0o600


# ===========================================================================
# THE END-TO-END CONTRACT TEST — the one that proves this is worth building.
# A canary record must actually unblock codex_review.sh's exit-22 gate.
# ===========================================================================


class TestUnblocksCodexReview:
    def _run_review(self, test_tree, repo, fake_home, codex_bin, findings_out, tmpdir):
        env = dict(os.environ)
        env["CODEX_REVIEW_TEST_MODE"] = "1"
        env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
        env["CODEX_BIN"] = str(codex_bin)
        env["FINDINGS_OUTPUT_DIR"] = str(findings_out)
        env["TMPDIR"] = str(tmpdir)
        return subprocess.run(
            [
                "bash",
                str(test_tree / "scripts" / "codex_review.sh"),
                str(repo),
                "--",
                "target.py",
            ],
            cwd=str(repo),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    @pytest.fixture
    def repo(self, tmp_path):
        r = tmp_path / "repo"
        r.mkdir()
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        subprocess.run(
            ["git", "init", "-q"], cwd=str(r), check=True, env=env, timeout=15
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(r),
            check=True,
            env=env,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=str(r), check=True, env=env
        )
        f = r / "target.py"
        f.write_text("line1\n")
        subprocess.run(
            ["git", "add", "--", "target.py"], cwd=str(r), check=True, env=env
        )
        subprocess.run(
            ["git", "commit", "-m", "initial", "--", "target.py"],
            cwd=str(r),
            check=True,
            env=env,
        )
        f.write_text("line1\nline2 changed\n")
        return r

    def test_review_refuses_22_with_no_canary(
        self, test_tree, repo, fake_home, fake_bin, tmp_path
    ):
        """Baseline: with no canary record at all, codex_review.sh refuses
        with exit 22."""
        _ready_setup(test_tree, fake_home)
        findings = tmp_path / "findings"
        findings.mkdir()
        rtmp = tmp_path / "review_tmp"
        rtmp.mkdir()
        codex = _fake_codex_compliant(fake_bin)
        proc = self._run_review(test_tree, repo, fake_home, codex, findings, rtmp)
        assert proc.returncode == 22, (proc.returncode, proc.stdout, proc.stderr)
        assert "no passing canary" in proc.stderr

    def test_recovery_fresh_passing_canary_clears_exit_22(
        self, test_tree, repo, fake_home, fake_bin, tmp_path
    ):
        """PAIRED RECOVERY and the headline integration proof: run the REAL
        codex_canary.sh, then the REAL codex_review.sh in the same tree, and
        assert the exit-22 refusal is gone.

        Note the canary writes into the tree's OWN .review_state/codex/ here
        (no CANARY_OUTPUT_DIR override), because that is the directory
        codex_review.sh reads from — proving the two halves agree on the
        path without either being told about the other by the test.
        """
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        ctmp = tmp_path / "canary_tmp"
        ctmp.mkdir()

        env = dict(os.environ)
        env["CODEX_REVIEW_TEST_MODE"] = "1"
        env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
        env["CODEX_BIN"] = str(codex)
        env["TMPDIR"] = str(ctmp)
        env["CODEX_CANARY_TIMEOUT_SEC"] = "10"
        env.pop("CANARY_OUTPUT_DIR", None)
        cproc = subprocess.run(
            ["bash", str(test_tree / "scripts" / "codex_canary.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert cproc.returncode == 0, (cproc.returncode, cproc.stdout, cproc.stderr)

        findings = tmp_path / "findings2"
        findings.mkdir()
        rtmp = tmp_path / "review_tmp2"
        rtmp.mkdir()
        proc = self._run_review(test_tree, repo, fake_home, codex, findings, rtmp)
        assert proc.returncode != 22, (
            "a fresh passing canary must clear the exit-22 gate",
            proc.returncode,
            proc.stderr,
        )
        assert "no passing canary" not in proc.stderr

    def test_failing_canary_does_NOT_clear_exit_22(
        self, test_tree, repo, fake_home, fake_bin, tmp_path
    ):
        """The paired negative: a passed:false record is evidence, never an
        unblock."""
        _ready_setup(test_tree, fake_home)
        leaking = _fake_codex_escapes(fake_bin, 1)
        ctmp = tmp_path / "canary_tmp_f"
        ctmp.mkdir()
        env = dict(os.environ)
        env["CODEX_REVIEW_TEST_MODE"] = "1"
        env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
        env["CODEX_BIN"] = str(leaking)
        env["TMPDIR"] = str(ctmp)
        env["CODEX_CANARY_TIMEOUT_SEC"] = "10"
        env.pop("CANARY_OUTPUT_DIR", None)
        cproc = subprocess.run(
            ["bash", str(test_tree / "scripts" / "codex_canary.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert cproc.returncode == 1

        findings = tmp_path / "findings3"
        findings.mkdir()
        rtmp = tmp_path / "review_tmp3"
        rtmp.mkdir()
        compliant = _fake_codex_compliant(fake_bin, name="codex_ok2")
        proc = self._run_review(test_tree, repo, fake_home, compliant, findings, rtmp)
        assert proc.returncode == 22, (proc.returncode, proc.stderr)

    def test_stale_passing_canary_does_NOT_clear_exit_22(
        self, test_tree, repo, fake_home, fake_bin, tmp_path
    ):
        """A passing record backdated past the 30-day window still refuses."""
        _ready_setup(test_tree, fake_home)
        stale = test_tree / ".review_state" / "codex" / "canary_old.json"
        # "unknown" deliberately: a record with a comparable version would
        # be invalidated by codex_available.sh's version-mismatch check
        # before the freshness window ever got a chance to refuse it, and
        # this test is about the FRESHNESS refusal specifically.
        stale.write_text(
            json.dumps(
                {
                    "passed": True,
                    "ts": time.time() - (40 * 86400),
                    "codex_version": "unknown",
                }
            )
        )
        findings = tmp_path / "findings4"
        findings.mkdir()
        rtmp = tmp_path / "review_tmp4"
        rtmp.mkdir()
        codex = _fake_codex_compliant(fake_bin)
        proc = self._run_review(test_tree, repo, fake_home, codex, findings, rtmp)
        assert proc.returncode == 22, (proc.returncode, proc.stderr)
        assert "days old" in proc.stderr


# ===========================================================================
# Export hygiene and the codex_export.* collision hazard.
# ===========================================================================


class TestExportHygiene:
    def test_no_scratch_survives_on_success(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        _ready_setup(test_tree, fake_home)
        iso = tmp_path / "iso_ok"
        iso.mkdir()
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            tmpdir=iso,
        )
        assert proc.returncode == 0
        leftovers = list(iso.glob("codex_canary*"))
        assert not leftovers, f"scratch survived a successful run: {leftovers}"

    def test_no_scratch_survives_on_failure(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """The credential copy lives in these dirs. A failing run must clean
        up exactly as thoroughly as a passing one."""
        _ready_setup(test_tree, fake_home)
        iso = tmp_path / "iso_fail"
        iso.mkdir()
        codex = _fake_codex_escapes(fake_bin, 1)
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            tmpdir=iso,
        )
        assert proc.returncode == 1
        leftovers = list(iso.glob("codex_canary*"))
        assert not leftovers, f"scratch survived a failed run: {leftovers}"

    def test_canary_creates_no_codex_export_dirs(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """THE COLLISION TEST. codex_review.sh refuses to start (exit 16) if
        ANY $TMPDIR/codex_export.* exists, and --sweep-stale only clears
        ones older than 10 minutes. A canary using that prefix and dying
        mid-run would wedge every real review for 10 minutes behind an
        outage naming a directory the sweep refuses to touch.

        MEASURED DURING THE RUN, not after. An earlier version of this test
        checked for leftovers AFTER the canary exited and was GREEN against
        a mutation that reverted the prefix to codex_export.* — because the
        cleanup trap removes the dirs either way, so "nothing survived" is
        true for both prefixes and the test measured nothing. The hazard is
        a concurrent review seeing the directory WHILE the canary runs, so
        that is what this asserts: the fake codex records the TMPDIR
        listing at the moment it is invoked, which is exactly when a
        parallel codex_review.sh would glob it.
        """
        _ready_setup(test_tree, fake_home)
        iso = tmp_path / "iso_collide"
        iso.mkdir()
        listing = tmp_path / "tmpdir_listing.txt"
        codex = _write_exe(
            fake_bin / "codex_lstmp",
            _ARGV_PREAMBLE
            + f"""
ls -1 {json.dumps(str(iso))} >> {json.dumps(str(listing))} 2>/dev/null
"""
            + r"""
if [ -n "$last_msg" ]; then
  printf 'NONCE=%s UNREADABLE NO-NETWORK ABSENT' "$nonce" > "$last_msg"
fi
exit 0
""",
        )
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            tmpdir=iso,
        )
        assert proc.returncode == 0, (proc.returncode, proc.stderr)
        seen = listing.read_text()
        assert seen.strip(), "the fake never listed TMPDIR — test is not measuring"
        assert "codex_canary." in seen, (
            "expected the canary's own export prefix to be visible mid-run"
        )
        assert "codex_export." not in seen, (
            "the canary used codex_review.sh's export prefix while running — a concurrent "
            "codex_review.sh would refuse with exit 16 and --sweep-stale would not clear it"
        )
        # And nothing of either prefix survives the run.
        assert not list(iso.glob("codex_export.*"))

    def test_auth_copy_is_not_under_the_codex_working_root(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """Plan §4.8a item 6 / codex_review.sh's B3 fix: the auth copy must
        be a SIBLING of the -C root, never inside it. -s read-only restricts
        WRITES, not reads, and codex runs model-generated shell commands, so
        an auth file under -C is `cat`-able by anything codex is talked into
        running.

        The fake enumerates its own -C root recursively and reports what it
        finds; we assert no auth file is reachable there.
        """
        _ready_setup(test_tree, fake_home)
        listing = tmp_path / "croot_listing.txt"
        codex = _write_exe(
            fake_bin / "codex_enumerate",
            _ARGV_PREAMBLE
            + f"""
find "$croot" >> {json.dumps(str(listing))} 2>/dev/null
"""
            + r"""
if [ -n "$last_msg" ]; then
  printf 'NONCE=%s UNREADABLE NO-NETWORK ABSENT' "$nonce" > "$last_msg"
fi
exit 0
""",
        )
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0, (proc.returncode, proc.stderr)
        text = listing.read_text()
        assert text.strip(), (
            "the fake never enumerated anything — test is not measuring"
        )
        assert "auth.json" not in text, (
            f"auth file reachable under the -C root:\n{text}"
        )
        assert "/.codex" not in text, f".codex dir reachable under the -C root:\n{text}"


# ===========================================================================
# The §4.3 flag set and the §4.4b environment scrub, asserted from the
# invocation codex actually receives.
# ===========================================================================


class TestInvocationHardening:
    def _capture(self, test_tree, fake_home, fake_bin, canary_out, tmp_path):
        _ready_setup(test_tree, fake_home)
        argv_log = tmp_path / "argv.txt"
        env_log = tmp_path / "env.txt"
        codex = _fake_codex_recording(fake_bin, argv_log, env_log)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
        return argv_log.read_text(), env_log.read_text()

    def test_required_flags_present(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        argv, _ = self._capture(test_tree, fake_home, fake_bin, canary_out, tmp_path)
        tokens = argv.splitlines()
        for required in (
            "exec",
            "-s",
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--json",
            "--output-schema",
            "-o",
            "-C",
            "-m",
        ):
            assert required in tokens, (
                f"{required!r} missing from the invocation: {tokens}"
            )

    def test_prohibited_flags_absent(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """Plan §4.3's permanent prohibition list."""
        argv, _ = self._capture(test_tree, fake_home, fake_bin, canary_out, tmp_path)
        for forbidden in (
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "--add-dir",
            "workspace-write",
            "danger-full-access",
            "sandbox_permissions",
            "shell_environment_policy",
        ):
            assert forbidden not in argv, f"{forbidden!r} appeared in the invocation"

    def test_environment_is_scrubbed_to_the_allowlist(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """Plan §4.4b: `env -i` with a minimal allowlist. The probe-3
        sentinel (name-matching the (?i)(token|key|secret|cred|auth|passw)
        scrub pattern) must NOT be visible to codex, and neither must the
        high-value credential variables."""
        _, envtext = self._capture(test_tree, fake_home, fake_bin, canary_out, tmp_path)
        names = {line.split("=", 1)[0] for line in envtext.splitlines() if "=" in line}
        assert "CODEX_CANARY_SECRET_SENTINEL" not in names, (
            "the probe-3 sentinel reached codex — the env -i scrub is ineffective"
        )
        for leaky in (
            "SSH_AUTH_SOCK",
            "CLAUDE_CODE_MESSAGING_TOKEN",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "ANTHROPIC_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "CODEX_REVIEW_TEST_MODE",
            "CODEX_BIN",
        ):
            assert leaky not in names, (
                f"{leaky} was not scrubbed from codex's environment"
            )
        # The allowlist itself is present.
        for allowed in ("PATH", "HOME", "TERM", "CODEX_HOME"):
            assert allowed in names, f"{allowed} missing from the allowlist"

    def test_home_is_not_the_real_home(
        self, test_tree, fake_home, fake_bin, canary_out, tmp_path
    ):
        """HOME is repointed at the export (plan §4.4b), so a
        model-generated `cat ~/.config/gcloud/...` resolves inside the
        throwaway export, not against the operator's real home."""
        _, envtext = self._capture(test_tree, fake_home, fake_bin, canary_out, tmp_path)
        home_lines = [ln for ln in envtext.splitlines() if ln.startswith("HOME=")]
        assert home_lines, envtext
        home_val = home_lines[0].split("=", 1)[1]
        assert home_val != str(Path.home()), (
            "HOME was not repointed away from the real home"
        )
        assert "codex_canary." in home_val, home_val


# ===========================================================================
# Argument and timeout validation.
# ===========================================================================


class TestArgumentValidation:
    def test_any_argument_is_refused(self, test_tree, fake_home, fake_bin, canary_out):
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            args=["--add-dir", "/"],
        )
        assert proc.returncode == 11
        assert "takes no arguments" in proc.stderr

    def test_recovery_no_arguments_runs(
        self, test_tree, fake_home, fake_bin, canary_out
    ):
        """PAIRED RECOVERY: the same script with no arguments proceeds."""
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree, codex_bin=codex, fake_home=fake_home, canary_out=canary_out
        )
        assert proc.returncode == 0

    @pytest.mark.parametrize("bad", ["", "abc", "0", "601", "-5"])
    def test_bad_timeout_is_refused(
        self, test_tree, fake_home, fake_bin, canary_out, bad
    ):
        _ready_setup(test_tree, fake_home)
        codex = _fake_codex_compliant(fake_bin)
        proc = _run_canary(
            test_tree,
            codex_bin=codex,
            fake_home=fake_home,
            canary_out=canary_out,
            extra_env={"CODEX_CANARY_TIMEOUT_SEC": bad},
        )
        assert proc.returncode == 11, (bad, proc.returncode, proc.stderr)


# ===========================================================================
# codex_available.sh's version-mismatch re-canary (plan §4.4).
# ===========================================================================


class TestVersionMismatchForcesRecanary:
    def _run_available(self, test_tree, fake_home, extra_env=None):
        env = dict(os.environ)
        env["CODEX_REVIEW_TEST_MODE"] = "1"
        env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(test_tree / "scripts" / "codex_available.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_matching_version_leaves_the_canary_alone(self, test_tree, fake_home):
        """A canary recorded under the CURRENT version stays honoured."""
        _ready_setup(test_tree, fake_home)
        real_version = subprocess.run(
            ["/opt/homebrew/bin/codex", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.splitlines()
        if not real_version:
            pytest.skip("real codex binary did not report a version on this machine")
        rec = test_tree / ".review_state" / "codex" / "canary_match.json"
        rec.write_text(
            json.dumps(
                {
                    "passed": True,
                    "ts": time.time(),
                    "codex_version": real_version[0].strip(),
                }
            )
        )
        proc = self._run_available(test_tree, fake_home)
        assert proc.returncode == 0, (proc.returncode, proc.stderr)
        assert rec.exists(), "a matching-version canary must not be invalidated"
        assert "version changed" not in proc.stderr

    def test_mismatched_version_invalidates_the_canary(self, test_tree, fake_home):
        """A canary measured under a DIFFERENT codex build is renamed out of
        the gate's canary_*.json glob, which forces a re-canary: the next
        codex_review.sh run finds no passing record and exits 22."""
        _ready_setup(test_tree, fake_home)
        rec = test_tree / ".review_state" / "codex" / "canary_stalever.json"
        rec.write_text(
            json.dumps(
                {
                    "passed": True,
                    "ts": time.time(),
                    "codex_version": "codex-cli 0.0.1-ancient",
                }
            )
        )
        proc = self._run_available(test_tree, fake_home)
        assert proc.returncode == 0, (proc.returncode, proc.stderr)
        assert "version changed" in proc.stderr, proc.stderr
        assert not rec.exists(), "the stale-version canary was not invalidated"
        # Renamed aside, never deleted: the record is evidence.
        superseded = list(
            (test_tree / ".review_state" / "codex").glob("*.superseded-*.json.invalid")
        )
        assert superseded, "the record was deleted rather than renamed aside"
        # And it no longer matches the gate's glob.
        assert not list((test_tree / ".review_state" / "codex").glob("canary_*.json"))

    def test_recovery_rerunning_the_canary_restores_a_fresh_record(
        self, test_tree, fake_home, fake_bin, tmp_path
    ):
        """PAIRED RECOVERY: after an invalidation, running codex_canary.sh
        again writes a fresh passing record under the CURRENT version, and
        codex_available.sh then leaves it alone."""
        _ready_setup(test_tree, fake_home)
        rec = test_tree / ".review_state" / "codex" / "canary_stalever.json"
        rec.write_text(
            json.dumps(
                {"passed": True, "ts": time.time(), "codex_version": "codex-cli 0.0.1"}
            )
        )
        assert self._run_available(test_tree, fake_home).returncode == 0
        assert not list((test_tree / ".review_state" / "codex").glob("canary_*.json"))

        codex = _fake_codex_compliant(fake_bin)
        ctmp = tmp_path / "ctmp_recover"
        ctmp.mkdir()
        env = dict(os.environ)
        env["CODEX_REVIEW_TEST_MODE"] = "1"
        env["CODEX_REVIEW_TEST_HOME"] = str(fake_home)
        env["CODEX_REVIEW_TEST_TRUST_OWNER"] = "1"
        env["CODEX_BIN"] = str(codex)
        env["TMPDIR"] = str(ctmp)
        env["CODEX_CANARY_TIMEOUT_SEC"] = "10"
        env.pop("CANARY_OUTPUT_DIR", None)
        cproc = subprocess.run(
            ["bash", str(test_tree / "scripts" / "codex_canary.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert cproc.returncode == 0, (cproc.returncode, cproc.stderr)
        fresh = list((test_tree / ".review_state" / "codex").glob("canary_*.json"))
        assert fresh, "the re-run canary wrote no record"
        # Second availability run must not invalidate the fresh record.
        proc2 = self._run_available(test_tree, fake_home)
        assert proc2.returncode == 0
        assert (
            list((test_tree / ".review_state" / "codex").glob("canary_*.json")) == fresh
        )

    def test_unknown_version_in_record_is_not_invalidated(self, test_tree, fake_home):
        """A record with no usable version cannot be compared. It is left
        alone (the 30-day window is its only bound) rather than being
        destroyed on a comparison that cannot be made."""
        _ready_setup(test_tree, fake_home)
        rec = test_tree / ".review_state" / "codex" / "canary_unknownver.json"
        rec.write_text(
            json.dumps({"passed": True, "ts": time.time(), "codex_version": "unknown"})
        )
        proc = self._run_available(test_tree, fake_home)
        assert proc.returncode == 0
        assert rec.exists()
        assert "no usable codex version" in proc.stderr
