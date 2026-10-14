"""Tests for tools/gtm/harvest_tool_trail.py — company attribution
precedence, idempotency, and off-server capture into the correct company's
trail. Ports the intent of Brightline's harvest tests. Uses tmp CLAUDE_DIR +
registry + packs + synthetic transcript files; never touches real
~/.claude/projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
import company  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402


def _minimal_pack(slug: str, domains: list[str] | None = None) -> dict:
    return {
        "schema_version": 1, "slug": slug, "legal_name": slug, "display_names": [slug],
        "business_model": "local_service", "brands": [],
        "persona_file": "x.md", "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": [], "channels_out_of_scope": []},
        "accounts": [],
        "identity_allowlist": {
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": domains or [], "listing_urls": [],
        },
        "claims_policy": {"terms": []},
        "ai_content_policy": {"mode": "strip_before_publish"},
        "autonomy": {"level": "shadow", "standing_approvals": []},
        "spend": {"currency": "USD", "monthly_cap_total": 0, "cap_ruling_ref": "none"},
        "budget": {"weekly_usd_cap_opus": 0, "weekly_usd_cap_sonnet": 0, "dispatch_caps_per_run": {
            "inbox": 8, "daily": 4, "weekly": 30, "monthly": 8, "mission": 60, "monthly_load": 8}},
        "operator_input": "from_manifest", "inbox": "local_jsonl",
        "lead_sink": {"kind": "none"},
        "cadence": {"inbox_checks": ["09:00"], "weekly_day": "SAT", "monthly_day": 1, "monthly_load_day": "last_weekday"},
        "paths": {
            "missions_dir": "gtm_mission", "mission_records": "ignored",
            "activity_log_dir": ".claude/gtm/state/activity_log",
            "scoreboard": ".claude/gtm/state/scoreboard.csv",
            "snapshots_dir": ".claude/gtm/state/snapshots",
            "metrics": ".claude/gtm/metrics.json",
            "feature_inventory_dir": ".claude/gtm/feature_inventory",
            "plans_dir": ".claude/gtm/plans",
            "data_dir": ".claude/gtm/data",
        },
    }


@pytest.fixture()
def two_companies(tmp_path, monkeypatch):
    """Registers 'csa' (no identity hosts declared, cwd-based attribution
    only) and 'brightline' (declares brightline-example.com as an identity
    host)."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)

    csa_home = tmp_path / "home_csa"
    (csa_home / ".claude" / "gtm").mkdir(parents=True)
    (csa_home / ".claude" / "gtm" / "company.json").write_text(
        json.dumps(_minimal_pack("csa")), encoding="utf-8"
    )

    ts_home = tmp_path / "home_brightline"
    (ts_home / ".claude" / "gtm").mkdir(parents=True)
    (ts_home / ".claude" / "gtm" / "company.json").write_text(
        json.dumps(_minimal_pack("brightline", domains=["brightline-example.com"])), encoding="utf-8"
    )

    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {
            "csa": {"root": str(csa_home)},
            "brightline": {"root": str(ts_home)},
        }}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    company.write_identity_index()

    return {"csa": csa_home, "brightline": ts_home, "claude_dir": claude_dir}


def _write_transcript(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def _navigate_and_click_lines(session_id: str, url: str, cwd: str, tool_use_id_prefix: str = "tu") -> list[dict]:
    return [
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:00-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_use", "id": f"{tool_use_id_prefix}_nav", "name": "mcp__playwright-gtm__browser_navigate", "input": {"url": url}},
            ]},
        },
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:01-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"{tool_use_id_prefix}_nav", "content": f"- Page URL: {url}"},
            ]},
        },
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:02-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_use", "id": f"{tool_use_id_prefix}_click", "name": "mcp__playwright-gtm__browser_click", "input": {"element": "Save button"}},
            ]},
        },
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:03-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"{tool_use_id_prefix}_click", "content": f"- Page URL: {url}"},
            ]},
        },
    ]


# --------------------------------------------------------------------------
# attribution precedence 1: identity-index host wins
# --------------------------------------------------------------------------


def test_identity_host_attribution_wins_even_from_csa_cwd(two_companies, tmp_path):
    """A CSA-cwd transcript that navigates to a Brightline identity host
    must attribute to Brightline, not CSA (plan §11.3, explicitly required
    by the task spec). Major 7: only the MUTATING click is captured now
    (the navigate is non-mutating and no longer captured at all)."""
    transcript = tmp_path / "transcript.jsonl"
    lines = _navigate_and_click_lines(
        session_id="sess1",
        url="https://brightline-example.com/admin",
        cwd=str(two_companies["csa"]),  # CWD says CSA...
    )
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    ts_paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(ts_paths.trail_jsonl)
    assert len(records) == 1  # only the mutating click

    csa_paths = activity_log.resolve_paths("csa")
    csa_records, _ = activity_log.read_jsonl(csa_paths.trail_jsonl)
    assert len(csa_records) == 0


# --------------------------------------------------------------------------
# attribution precedence 2: playwright-gtm server + cwd under a home
# (major 7: this is now the ONLY cwd-based rung, and it fires ONLY for the
# playwright-gtm server -- cwd-only attribution for any OTHER server is
# removed entirely, see test_cwd_only_attribution_dropped_for_non_gtm_server
# below)
# --------------------------------------------------------------------------


def test_playwright_gtm_cwd_attribution_when_no_identity_host_matches(two_companies, tmp_path):
    """A mutating call on playwright-gtm to a non-identity-host URL still
    attributes by cwd (rung 2) -- capture path (b) ("any mutating call on
    playwright-gtm") applies regardless of the URL's host."""
    transcript = tmp_path / "transcript2.jsonl"
    lines = _navigate_and_click_lines(
        session_id="sess2",
        url="https://unrelated-generic-site.example.org/page",
        cwd=str(two_companies["csa"]),
    )
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    csa_paths = activity_log.resolve_paths("csa")
    records, _ = activity_log.read_jsonl(csa_paths.trail_jsonl)
    assert len(records) == 1  # only the mutating click


def test_cwd_only_attribution_dropped_for_non_gtm_server(two_companies, tmp_path):
    """Major 7 (replaces the old cwd-only-attribution-locking test):
    on a NON-playwright-gtm, NON-identity-host call, cwd-only attribution
    is REMOVED entirely -- neither capture path (a) (identity host, any
    server) nor (b) (playwright-gtm, any host) applies, so the call is not
    eligible for capture at all, regardless of a matching registered-home
    cwd. RED-check: reinstate the old rung-3 "cwd alone" fallback in
    attribute_company() (or drop the on_identity_host/on_gtm_server
    eligibility gate in try_classify_call) and this test's zero-records
    assertion fails."""
    transcript = tmp_path / "transcript2b.jsonl"
    lines = [
        {
            "sessionId": "sess2b", "timestamp": "2026-01-01T10:00:00-06:00", "cwd": str(two_companies["csa"]),
            "message": {"content": [
                {"type": "tool_use", "id": "tu2b_click", "name": "mcp__playwright-adhoc__browser_click", "input": {"element": "Save"}},
            ]},
        },
        {
            "sessionId": "sess2b", "timestamp": "2026-01-01T10:00:01-06:00", "cwd": str(two_companies["csa"]),
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu2b_click", "content": "- Page URL: https://unrelated-generic-site.example.org/page"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    for slug in ("csa", "brightline"):
        paths = activity_log.resolve_paths(slug)
        records, _ = activity_log.read_jsonl(paths.trail_jsonl)
        assert len(records) == 0
    unattributed_path = company.gtm_state_dir() / "unattributed_trail.jsonl"
    records, _ = activity_log.read_jsonl(unattributed_path)
    assert len(records) == 0


def test_no_attribution_when_url_matches_nothing_and_cwd_matches_nothing(two_companies, tmp_path):
    transcript = tmp_path / "transcript3.jsonl"
    lines = _navigate_and_click_lines(
        session_id="sess3",
        url="https://unrelated-generic-site.example.org/page",
        cwd="/some/random/unregistered/path",
    )
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    for slug in ("csa", "brightline"):
        paths = activity_log.resolve_paths(slug)
        records, _ = activity_log.read_jsonl(paths.trail_jsonl)
        assert len(records) == 0


# --------------------------------------------------------------------------
# idempotency
# --------------------------------------------------------------------------


def test_idempotent_by_tool_use_id_across_reruns(two_companies, tmp_path):
    transcript = tmp_path / "transcript4.jsonl"
    lines = _navigate_and_click_lines(
        session_id="sess4",
        url="https://brightline-example.com/admin",
        cwd=str(two_companies["csa"]),
    )
    _write_transcript(transcript, lines)

    htt.main([str(transcript)])
    htt.main([str(transcript)])  # re-run on the SAME transcript

    ts_paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(ts_paths.trail_jsonl)
    # Still only 1 record (the mutating click; the navigate is non-mutating
    # and never captured under major 7), not 2 -- no duplicate append.
    assert len(records) == 1


def test_rerun_summary_reports_appended_not_candidate_counts(two_companies, tmp_path, capsys):
    """Regression fix (post-#21 lock-narrowing): new_by_company/
    new_unattributed hold every CANDIDATE the scan produced, including ones
    already on disk from a prior run -- the 'by company:'/'new records:'
    summary must report what `_flush_locked` actually APPENDED this run,
    not the raw candidate count, or a second run over an unchanged
    transcript set falsely reports activity that never happened.

    RED-check: revert main()'s summary block to print
    `len(new_by_company[company])` / `len(new_unattributed)` directly (its
    pre-fix shape) and this fails -- the second run's output still shows
    'by company:\\n  brightline: 1' and 'new records: 1' even though
    nothing new was appended."""
    transcript = tmp_path / "transcript_rerun_summary.jsonl"
    lines = _navigate_and_click_lines(
        session_id="sess_rerun_summary",
        url="https://brightline-example.com/admin",
        cwd=str(two_companies["csa"]),
    )
    _write_transcript(transcript, lines)

    htt.main([str(transcript)])
    first_out = capsys.readouterr().out
    assert "new records: 1" in first_out
    assert "by company:" in first_out
    assert "brightline: 1" in first_out

    htt.main([str(transcript)])  # re-run on the SAME transcript -- nothing new
    second_out = capsys.readouterr().out
    assert "new records: 0" in second_out
    assert "by company:" not in second_out, (
        f"second run over an unchanged transcript must report no per-company line, got:\n{second_out}"
    )


def test_reattribution_across_companies_never_duplicates_the_same_call(two_companies, tmp_path):
    """#21 regression: a real tool call must land in AT MOST ONE company's
    trail, even when its attribution changes between two harvest runs
    (e.g. the URL's own host was not yet declared by any pack on the first
    run -- landing on playwright-gtm+cwd attribution to 'csa' -- and a
    domain declaration later makes it identity-match 'brightline' on a
    re-index-and-reharvest). load_existing_ids's own docstring: idempotency
    "must hold globally, not per-file". RED-check: revert _flush_locked to
    read existing_ids from only its own `target` trail (drop the
    all_trail_paths union) and this fails -- the click lands in BOTH
    csa's and brightline's trails instead of exactly one."""
    click_url = "https://not-yet-a-declared-domain.example.net/admin"
    transcript = tmp_path / "transcript_reattr.jsonl"
    lines = _navigate_and_click_lines(
        session_id="sess_reattr",
        url=click_url,
        cwd=str(two_companies["csa"]),  # playwright-gtm + cwd under csa's home
    )
    _write_transcript(transcript, lines)

    # First run: no pack declares this domain, so the click attributes via
    # playwright-gtm+cwd to csa.
    htt.main([str(transcript)])

    csa_paths = activity_log.resolve_paths("csa")
    ts_paths = activity_log.resolve_paths("brightline")
    csa_records_1, _ = activity_log.read_jsonl(csa_paths.trail_jsonl)
    ts_records_1, _ = activity_log.read_jsonl(ts_paths.trail_jsonl)
    assert [r["tool_use_id"] for r in csa_records_1] == ["tu_click"]
    assert ts_records_1 == []

    # brightline now declares the domain and the identity index is rebuilt
    # -- the SAME click would attribute to brightline on a fresh scan.
    ts_pack_path = two_companies["brightline"] / ".claude" / "gtm" / "company.json"
    ts_pack = json.loads(ts_pack_path.read_text(encoding="utf-8"))
    ts_pack["identity_allowlist"]["domains"] = ["not-yet-a-declared-domain.example.net"]
    ts_pack_path.write_text(json.dumps(ts_pack), encoding="utf-8")
    company.write_identity_index()

    htt.main([str(transcript)])

    csa_records_2, _ = activity_log.read_jsonl(csa_paths.trail_jsonl)
    ts_records_2, _ = activity_log.read_jsonl(ts_paths.trail_jsonl)
    all_ids = [r["tool_use_id"] for r in csa_records_2] + [r["tool_use_id"] for r in ts_records_2]
    assert all_ids.count("tu_click") == 1, (
        f"tool_use_id 'tu_click' must appear in exactly one company's trail, "
        f"found csa={[r['tool_use_id'] for r in csa_records_2]} "
        f"brightline={[r['tool_use_id'] for r in ts_records_2]}"
    )


# --------------------------------------------------------------------------
# major 6: trail appends need the lock
# --------------------------------------------------------------------------


def test_concurrent_appends_produce_a_valid_chain_no_duplicate_ids(two_companies, tmp_path):
    """Real concurrency: N threads each append a DISTINCT record to the
    SAME company trail file at (as close to) the same time as the GIL
    allows, racing on the read-last-line-then-append sequence inside
    _append_chained_trail. Without the lock (major 6), two threads can both
    read the same "last line" and each compute prev_hash from it -- a
    fork, not a chain -- which verify_chain() then detects as broken.

    RED-check: remove the `with activity_log_mod.LockedFile(lock_path):`
    wrapper in harvest_tool_trail._append_chained_trail (revert to a bare
    call with no lock) and this test goes RED -- flakily, as any real race
    condition does, but reliably enough at N=40 threads on this file
    layout to have been caught by hand before writing this comment."""
    import threading

    ts_paths = activity_log.resolve_paths("brightline")
    ts_paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)

    n_threads = 40
    barrier = threading.Barrier(n_threads)
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            barrier.wait()  # maximize actual overlap of the race window
            record = {
                "tool_use_id": f"concurrent_tu_{i}",
                "ts": f"2026-01-01T10:00:{i:02d}-06:00",
                "session_id": "concurrent_sess",
                "agent_id": "main",
                "actor_label": "main-session",
                "tool": "mcp__playwright-gtm__browser_click",
                "transcript": "concurrent.jsonl",
                "url": "https://brightline-example.com/x",
                "system": "gtm_browser",
                "mutating": True,
                "detail": {},
                "result_excerpt": "",
            }
            htt._append_chained_trail(ts_paths.trail_jsonl, record)
        except BaseException as exc:  # noqa: BLE001 - capture for the main thread to re-raise
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, errors

    records, bad = activity_log.read_jsonl(ts_paths.trail_jsonl)
    assert bad == []
    assert len(records) == n_threads

    ids = [r["tool_use_id"] for r in records]
    assert len(ids) == len(set(ids)), "duplicate tool_use_id written under concurrency"

    chain_ok, reason = activity_log.verify_chain(ts_paths.trail_jsonl)
    assert chain_ok, reason


# --------------------------------------------------------------------------
# unattributable mutating call -> sink
# --------------------------------------------------------------------------


def test_offserver_mutating_identity_host_call_is_captured_and_flagged(two_companies, tmp_path):
    """Finding 12 (gtm-offserver): a MUTATING call on a NON-playwright-gtm
    server to an identity-index host is still captured (capture path (a)
    applies regardless of server) and attributed via precedence 1, but is
    flagged `offserver: true` -- the plan's G-A §7.1 calls this exact shape
    detect-after (the action happened outside the governed
    playwright-gtm server/ticket system). RED-check: remove the
    `record["offserver"] = True` line in try_classify_call's
    `on_identity_host and not on_gtm_server` branch and this test's flag
    assertion fails while attribution still passes -- proving the flag,
    not just the attribution, is under test."""
    transcript = tmp_path / "transcript5.jsonl"
    lines = [
        {
            "sessionId": "sess5", "timestamp": "2026-01-01T10:00:00-06:00", "cwd": "/unregistered/path",
            "message": {"content": [
                {"type": "tool_use", "id": "tu5_click", "name": "mcp__playwright-adhoc__browser_click",
                 "input": {"element": "Save"}},
            ]},
        },
        {
            "sessionId": "sess5", "timestamp": "2026-01-01T10:00:01-06:00", "cwd": "/unregistered/path",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu5_click", "content": "- Page URL: https://brightline-example.com/settings"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)
    rc = htt.main([str(transcript)])
    assert rc == 0
    # This URL DOES match the brightline identity host, so precedence 1
    # attributes it there even off the playwright-gtm server and off any
    # registered cwd -- confirming "mutating calls on ANY playwright server
    # to an identity-index host are captured" from an off-server call, now
    # flagged rather than silently blended in with governed activity.
    ts_paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(ts_paths.trail_jsonl)
    assert len(records) == 1
    assert records[0]["server"] == "playwright-adhoc"
    assert records[0]["offserver"] is True


def test_genuinely_unattributable_mutating_identity_call_goes_to_sink():
    """Finding 12: a mutating call that DOES match capture path (b) (on
    the `playwright-gtm` server, so eligible regardless of host) but whose
    cwd does NOT sit under ANY registered home is eligible for capture yet
    attribute_company() itself returns None (rung 1 needs an identity-index
    hit, which this URL doesn't have; rung 2 needs a matching home, which
    no `homes` entry provides) -- exercising the `company is None` branch
    that used to be DEAD CODE (finding 12's root defect: the old code
    returned early on `company is None` right after computing it, before
    this second, reachable check could ever run).

    RED-check: restore the old early `if company is None: return None`
    immediately after the `attribute_company(...)` call (before the
    `action in (...)` detail-formatting block) and this test's
    `classified is not None` assertion fails -- the call is dropped
    entirely instead of reaching the sink."""
    identity_index = htt.IdentityIndex(value_to_company={}, account_id_to_company={})  # empty: rung 1 can never hit
    homes: dict[str, Path] = {"csa": Path("/some/registered/home")}  # present but cwd below never matches it
    last_url_by_server: dict[str, str] = {}

    classified = htt.try_classify_call(
        tid="tu_sink_1",
        name="mcp__playwright-gtm__browser_click",  # capture path (b): eligible regardless of host
        tool_input={"element": "Save"},
        result_text="- Page URL: https://totally-unrelated-host.example.net/x",
        ts="2026-01-01T10:00:00-06:00",
        session_id="sess_sink",
        agent_id=None,
        cwd="/nowhere/registered",
        transcript_path=Path("sink_test.jsonl"),
        last_url_by_server=last_url_by_server,
        identity_index=identity_index,
        homes=homes,
        packs={},
    )
    assert classified is not None, "eligible mutating call must not be silently dropped"
    company, record = classified
    assert company is None, "attribute_company must genuinely fail to resolve a single company here"


# --------------------------------------------------------------------------
# major finding #1 (regression fix): a slug attributed by harvest_transcript
# but absent from company_trail_paths (stale identity index, unregistered/
# duplicate slug, or a load_pack/trail-path failure) must never be dropped
# -- it goes to the unattributed sink with a warning, and main() exits
# non-zero.
# --------------------------------------------------------------------------


def test_unresolvable_trail_path_routes_to_unattributed_sink_not_dropped(two_companies, tmp_path, monkeypatch, capsys):
    """RED-check: restore the old `if target is None: continue` (with no
    sink write, no warning, exit 0) and this test's sink-length assertion
    fails -- the record is silently dropped instead of landing in
    unattributed_trail.jsonl, and rc stays 0 instead of 1."""
    ts_home = two_companies["brightline"]

    transcript = tmp_path / "unresolvable.jsonl"
    _write_transcript(
        transcript,
        _navigate_and_click_lines(
            "sess_unresolvable",
            "https://brightline-example.com/settings",
            str(ts_home),
            tool_use_id_prefix="tu_unresolvable",
        ),
    )

    # Simulate a stale identity_index.json / load_pack failure: the
    # identity index and registry both still name "brightline", but
    # _trail_path_for_company cannot resolve a trail path for it (e.g.
    # `company.py unregister brightline` ran with no re-index, or
    # load_pack now fails for some other reason).
    orig_trail_path = htt._trail_path_for_company

    def _broken_trail_path(slug: str) -> Path:
        if slug == "brightline":
            raise company.CompanyError("simulated: no resolvable trail path")
        return orig_trail_path(slug)

    monkeypatch.setattr(htt, "_trail_path_for_company", _broken_trail_path)

    rc = htt.main([str(transcript)])

    assert rc != 0, "main() must exit non-zero when a company's records could not be filed to its own trail"

    unattributed_path = company.gtm_state_dir() / "unattributed_trail.jsonl"
    assert unattributed_path.exists(), "the unresolvable company's records must land in the unattributed sink"
    sink_records, _ = activity_log.read_jsonl(unattributed_path)
    assert len(sink_records) == 1
    assert sink_records[0]["tool_use_id"] == "tu_unresolvable_click"

    stderr = capsys.readouterr().err
    assert "brightline" in stderr
    assert "1" in stderr


def test_rerouted_unresolvable_records_not_double_counted_in_summary(two_companies, tmp_path, monkeypatch, capsys):
    """Regression fix: a record rerouted from an unresolvable company (added
    to new_unattributed via the `target is None` branch) must be counted
    ONCE in the summary -- under the unattributed line via its actual
    _flush_locked append count -- never also under its original company's
    line. Pre-fix, `new_by_company[company]` still held the record (it is
    only ADDED to new_unattributed, never removed from new_by_company), so
    the raw-candidate-count summary would have shown it in both places.

    RED-check: revert the summary block to print candidate counts
    (len(new_by_company[company]) / len(new_unattributed)) instead of the
    tracked appended counts and this fails -- 'brightline: 1' appears under
    'by company:' even though brightline's own trail was never written to
    (the record actually landed in the unattributed sink)."""
    ts_home = two_companies["brightline"]

    transcript = tmp_path / "unresolvable_summary.jsonl"
    _write_transcript(
        transcript,
        _navigate_and_click_lines(
            "sess_unresolvable_summary",
            "https://brightline-example.com/settings",
            str(ts_home),
            tool_use_id_prefix="tu_unresolvable_summary",
        ),
    )

    orig_trail_path = htt._trail_path_for_company

    def _broken_trail_path(slug: str) -> Path:
        if slug == "brightline":
            raise company.CompanyError("simulated: no resolvable trail path")
        return orig_trail_path(slug)

    monkeypatch.setattr(htt, "_trail_path_for_company", _broken_trail_path)

    htt.main([str(transcript)])
    out = capsys.readouterr().out

    assert "new records: 1" in out
    assert "brightline" not in out, (
        f"brightline's own line must not appear in the 'by company:' summary -- its record was "
        f"rerouted to the unattributed sink, not appended to brightline's own trail, got:\n{out}"
    )
    assert "unattributed" in out


# --------------------------------------------------------------------------
# Major finding #1 (regression fix): a registered home with NO GTM pack
# (README §3.1 -- a pack-less registered repo, e.g. one registered only in
# repo_registry.json for other tooling, is not a GTM company at all) must
# never make a scheduled harvest exit non-zero. Rung 2 attribution is now
# scoped to homes that actually have a loadable pack, and the non-zero exit
# fires only when a genuinely NEW record was rerouted this run because its
# company was unresolvable -- never merely because an unresolvable company
# was seen.
# --------------------------------------------------------------------------


@pytest.fixture()
def registered_home_with_no_pack(two_companies, tmp_path):
    """Adds a THIRD registered home, 'nopack', with NO .claude/gtm/
    company.json at all -- a repo registered (e.g. in repo_registry.json)
    for other tooling, never onboarded as a GTM company."""
    claude_dir = two_companies["claude_dir"]
    nopack_home = tmp_path / "home_nopack"
    nopack_home.mkdir(parents=True)

    registry_path = claude_dir / "knowledge" / "repo_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["repos"]["nopack"] = {"root": str(nopack_home)}
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    return {**two_companies, "nopack": nopack_home}


def test_pack_less_registered_home_goes_to_unattributed_sink_with_exit_0(
    registered_home_with_no_pack, tmp_path, capsys
):
    """RED-check: widen rung 2's `homes` back to the FULL registered-homes
    dict (undo the `attribution_homes` narrowing in main()) and this fails
    -- the playwright-gtm call's cwd (under 'nopack', a pack-less home)
    gets attributed to 'nopack' by rung 2, 'nopack' has no trail path (no
    pack to derive one from), and the run wrongly exits 1 for a completely
    healthy setup."""
    nopack_home = registered_home_with_no_pack["nopack"]

    transcript = tmp_path / "nopack.jsonl"
    _write_transcript(
        transcript,
        _navigate_and_click_lines(
            "sess_nopack",
            "https://not-an-identity-host.example.com/settings",
            str(nopack_home),
            tool_use_id_prefix="tu_nopack",
        ),
    )

    rc = htt.main([str(transcript)])
    assert rc == 0, "a pack-less registered home must never make a healthy harvest exit non-zero"

    unattributed_path = company.gtm_state_dir() / "unattributed_trail.jsonl"
    assert unattributed_path.exists()
    sink_records, _ = activity_log.read_jsonl(unattributed_path)
    assert len(sink_records) == 1
    assert sink_records[0]["tool_use_id"] == "tu_nopack_click"

    stderr = capsys.readouterr().err
    assert "no trail path" not in stderr, (
        f"a pack-less home must never be reported as an unresolvable-company warning, got:\n{stderr}"
    )


def test_second_run_over_same_transcript_exits_0(two_companies, tmp_path, monkeypatch):
    """A genuinely unresolvable company (finding #1's ORIGINAL scenario --
    a registered, packed company whose trail path fails to resolve, e.g.
    a stale identity index) makes the FIRST run exit non-zero, but a
    SECOND run over the identical transcript -- nothing new to append,
    since the record already landed in the unattributed sink -- must exit
    0. A scheduled harvest re-running nightly over overlapping transcript
    globs must not stay red forever for a condition whose real effect
    (the reroute) already happened and was already recorded.

    RED-check: revert `had_unresolvable_company` to fire whenever an
    unresolvable company was merely SEEN this run (the pre-fix behavior,
    ignoring _flush_locked's actual appended-ids result) and this fails --
    the second run's rc is 1 even though `_flush_locked` appended 0 new
    unattributed records."""
    ts_home = two_companies["brightline"]

    transcript = tmp_path / "unresolvable_twice.jsonl"
    _write_transcript(
        transcript,
        _navigate_and_click_lines(
            "sess_unresolvable_twice",
            "https://brightline-example.com/settings",
            str(ts_home),
            tool_use_id_prefix="tu_unresolvable_twice",
        ),
    )

    orig_trail_path = htt._trail_path_for_company

    def _broken_trail_path(slug: str) -> Path:
        if slug == "brightline":
            raise company.CompanyError("simulated: no resolvable trail path")
        return orig_trail_path(slug)

    monkeypatch.setattr(htt, "_trail_path_for_company", _broken_trail_path)

    rc_first = htt.main([str(transcript)])
    assert rc_first != 0, "setup invariant: the first run must genuinely reroute a new record"

    rc_second = htt.main([str(transcript)])
    assert rc_second == 0, (
        "a second run over the same transcript, with nothing NEW to append (the record was "
        "already rerouted to the unattributed sink on the first run), must exit 0"
    )
