"""Blockers 3 and 4 — dedicated tests for the standing-approval wildcard
bypass rewrite and the widened secret scan.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


def _base_approval(**overrides) -> dict:
    approval = {"id": "R9", "verbatim": "some ruling text", "ts": "2026-01-01", "rows": ["gbp.hours_edit"]}
    approval.update(overrides)
    return approval


def _validate_approval(approval: dict) -> list[str]:
    pack = {"autonomy": {"level": "shadow", "standing_approvals": [approval]}}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    return reasons


# --------------------------------------------------------------------------
# Blocker 3: every named bypass shape
# --------------------------------------------------------------------------


def test_bypass_bare_wildcard_string_rejected():
    """RED-check: revert to the old `"*" in rows` (list-membership) check
    and this passes wrongly IF rows is exactly ["*"] -- it would actually
    still catch this one shape, which is why the OTHER three cases below
    are the ones that actually distinguish the fix from the old code."""
    reasons = _validate_approval(_base_approval(rows=["*"]))
    assert any("wildcard" in r for r in reasons)


def test_bypass_prefix_wildcard_gbp_star_rejected():
    """RED-check: the old `"*" in rows` check does a list membership test
    (is the STRING "*" itself an element of the list), which does NOT
    catch "gbp.*" as an element -- "gbp.*" != "*". This is the real
    bypass the old code missed."""
    reasons = _validate_approval(_base_approval(rows=["gbp.*"]))
    assert any("wildcard" in r for r in reasons)


def test_bypass_suffix_wildcard_star_publish_rejected():
    reasons = _validate_approval(_base_approval(rows=["*.publish"]))
    assert any("wildcard" in r for r in reasons)


def test_bypass_whitespace_padded_wildcard_rejected():
    reasons = _validate_approval(_base_approval(rows=[" *"]))
    assert any("wildcard" in r for r in reasons)


def test_clean_row_id_passes():
    reasons = _validate_approval(_base_approval(rows=["gbp.hours_edit", "yelp.profile_text_edit"]))
    approval_reasons = [r for r in reasons if "standing_approvals" in r]
    assert approval_reasons == []


def test_approval_missing_id_verbatim_or_ts_rejected():
    reasons = _validate_approval({"rows": ["gbp.hours_edit"]})
    assert any("id" in r for r in reasons)
    assert any("verbatim" in r for r in reasons)
    assert any("ts" in r for r in reasons)


def test_approval_empty_rows_rejected():
    reasons = _validate_approval(_base_approval(rows=[]))
    assert any("non-empty" in r for r in reasons)


def test_approval_row_with_surrounding_whitespace_variant_trailing():
    reasons = _validate_approval(_base_approval(rows=["gbp.hours_edit "]))
    assert any("whitespace" in r for r in reasons)


# --------------------------------------------------------------------------
# Blocker 4: secret scan
# --------------------------------------------------------------------------


def test_secret_new_value_patterns_all_flagged():
    cases = [
        "sk_" "live_abcdefgh12345678",
        "sk_" "test_abcdefgh12345678",
        "rk_" "live_abcdefgh12345678",
        "GOCSPX-abcdefgh12345678",
        "ghp_abcdefghijklmnopqrst1234",
        "gho_abcdefghijklmnopqrst1234",
        "github_pat_abcdefghijklmnopqrst1234",
        "1//0gABCDEFGHijklmno",
        "xoxb-1234567890-abcdefghij",
        "xoxp-1234567890-abcdefghij",
    ]
    for value in cases:
        hits = company.find_secret_shapes({"some_field": value})
        assert hits, f"expected a hit for {value!r}"


def test_secret_env_var_reference_not_flagged():
    hits = company.find_secret_shapes({"env": {"API_TOKEN": "${GOOGLE_ADS_TOKEN}"}})
    assert hits == []
    hits = company.find_secret_shapes({"env": {"API_TOKEN": "$GOOGLE_ADS_TOKEN"}})
    assert hits == []


def test_secret_gsm_reference_not_flagged():
    hits = company.find_secret_shapes({"credential_ref": "gsm:brightline-google-ads-token"})
    assert hits == []


def test_secret_bare_git_sha_not_flagged():
    hits = company.find_secret_shapes({"commit": "a" * 40})
    assert hits == []


def test_secret_token_none_prose_not_flagged():
    """RED-check: this is the exact false-positive the task calls out --
    remove the redact_matches-authoritative branch (fall through to the
    key-name-based check on the WHOLE string) and this fails."""
    hits = company.find_secret_shapes({"token": "none"})
    assert hits == []
    hits = company.find_secret_shapes({"some_field": "token: none"})
    assert hits == []


def test_secret_clean_ids_never_flagged():
    """Ads id, G-..., GTM-..., FB Page id, phone numbers must all stay
    clean."""
    clean_cases = {
        "ads_customer_id": "100-200-3000",
        "ga4_property_id": "G-ABC1234567",
        "gtm_container_id": "GTM-ABCD123",
        "facebook_page_id": "100000000000099",
        "phone": "+1-720-555-1212",
    }
    for key, value in clean_cases.items():
        hits = company.find_secret_shapes({key: value})
        assert hits == [], f"{key}={value!r} should be clean, got {hits}"


def test_secret_real_token_under_secret_key_name_flagged():
    hits = company.find_secret_shapes({"api_key": "reallylongsecretvalue1234567890"})
    assert hits
    hits = company.find_secret_shapes({"headers": {"Authorization": "Bearer reallylongsecretvalue1234567890"}})
    assert hits


def test_secret_env_object_nested_deep_still_scanned():
    hits = company.find_secret_shapes(
        {"mcpServers": {"x": {"env": {"CLIENT_SECRET": "reallylongsecretvalue1234567890"}}}}
    )
    assert hits
