"""B1: the secret scan must not reject valid, non-secret values:
credential_ref's own gsm:<name> | browser:<server> | none shape, and
lead_sink.ref (a Google Sheet id) when kind == "google_sheet".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


# --------------------------------------------------------------------------
# credential_ref: browser:<server> and gsm:<name> are safe; exempt from
# the key-name rule entirely (its shape is validated separately)
# --------------------------------------------------------------------------


def test_credential_ref_browser_playwright_gtm_not_flagged():
    """RED-check: remove BOTH the `if key_name == "credential_ref": return
    hits` early exit in find_secret_shapes AND the `_BROWSER_REF_RE`
    safe-literal check and this fails -- the key name "credential_ref"
    matches _SECRET_KEY_NAME_RE (contains "credential"), and removing only
    one of the two guards still leaves the other covering this exact
    value (verified by executing each removal independently 2026-09-27)."""
    hits = company.find_secret_shapes({"accounts": [{"credential_ref": "browser:playwright-gtm"}]})
    assert hits == []


def test_credential_ref_gsm_reference_not_flagged():
    hits = company.find_secret_shapes({"accounts": [{"credential_ref": "gsm:brightline-google-ads-token"}]})
    assert hits == []


def test_credential_ref_none_not_flagged():
    hits = company.find_secret_shapes({"accounts": [{"credential_ref": "none"}]})
    assert hits == []


def test_credential_ref_invalid_shape_caught_by_validator_not_secret_scan():
    """A credential_ref that does NOT match gsm:<name>|browser:<server>|none
    is still rejected -- but by the dedicated shape check in
    validate_company, not by the secret scan (which now exempts this key
    entirely, for a company.json-scoped scan)."""
    # nit: is_company_json defaults to False now -- opt in explicitly to
    # exercise the exemption itself.
    hits = company.find_secret_shapes({"accounts": [{"credential_ref": "not-a-valid-shape"}]}, is_company_json=True)
    assert hits == []  # secret scan itself stays silent on this key

    pack = {"accounts": [{"system": "google_ads", "credential_ref": "not-a-valid-shape"}]}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("credential_ref" in r and "must match" in r for r in reasons)


def test_credential_ref_real_secret_value_still_flagged_via_validator_shape_check():
    """A credential_ref holding an actual bare secret value (not any of
    the three valid shapes) is still rejected -- via the shape check,
    since it doesn't match gsm:/browser:/none either."""
    pack = {"accounts": [{"system": "google_ads", "credential_ref": "sk_" "live_abcdefgh12345678"}]}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("credential_ref" in r for r in reasons)


# --------------------------------------------------------------------------
# lead_sink.ref: a Google Sheet id, exempted only under kind=="google_sheet"
# and the 25-60-char alphanumeric/-/_ shape
# --------------------------------------------------------------------------


def test_lead_sink_google_sheet_ref_not_flagged():
    """RED-check: remove the is_google_sheet_lead_sink exemption block in
    find_secret_shapes and this fails -- a 44-char alphanumeric Sheet id
    matches the 40+-char base64 secret-value pattern."""
    # nit: is_company_json defaults to False now -- opt in explicitly to
    # exercise the exemption itself.
    hits = company.find_secret_shapes({
        "lead_sink": {"kind": "google_sheet", "ref": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"}
    }, is_company_json=True)
    assert hits == []


def test_lead_sink_ref_not_exempted_for_non_google_sheet_kind():
    """The exemption is SCOPED to kind == "google_sheet" -- the same
    ref-shaped value under a different kind must still be scanned
    normally (and in this case, since it's a real secret-shaped value,
    still flagged)."""
    hits = company.find_secret_shapes({
        "lead_sink": {"kind": "app_crm", "ref": "sk_" "live_abcdefgh12345678"}
    })
    assert hits != []


def test_lead_sink_ref_wrong_length_not_exempted():
    """A ref that does NOT match the 25-60-char google-sheet-id shape is
    not exempted even under kind == "google_sheet" -- e.g. a real secret
    value typed into the wrong field."""
    hits = company.find_secret_shapes({
        "lead_sink": {"kind": "google_sheet", "ref": "sk_" "live_abcdefgh12345678"}
    })
    assert hits != []


def test_lead_sink_ref_none_kind_unaffected():
    hits = company.find_secret_shapes({"lead_sink": {"kind": "none"}})
    assert hits == []


# --------------------------------------------------------------------------
# Real values, elsewhere, still flag correctly (no over-broadening)
# --------------------------------------------------------------------------


def test_other_credential_shaped_key_names_still_flagged():
    """The exemption is scoped to the EXACT key name "credential_ref" --
    a different key that also looks credential-ish must still be scanned
    normally."""
    hits = company.find_secret_shapes({"api_key": "reallylongsecretvalue1234567890"})
    assert hits != []


# --------------------------------------------------------------------------
# nit: _is_safe_literal's browser:* exemption is narrowed to the pack
# schema's OWN credential_ref browser-shape (lowercase-only server name),
# never a wider case-insensitive/mixed-case match -- _is_safe_literal is
# the GENERIC safe-value check used everywhere (mcp.json included), so a
# wider exemption there would be inconsistent with what validate_company's
# own credential_ref shape check actually allows.
# --------------------------------------------------------------------------


def test_mixed_case_browser_ref_value_under_a_secret_key_name_is_still_flagged():
    """RED-check: revert _BROWSER_REF_RE to the case-insensitive,
    mixed-case-server pattern and this fails -- a value like
    "Browser:MyServer" under a secret-shaped key name (e.g. mcp.json's
    env.API_TOKEN) would be treated as a safe literal even though it
    would FAIL validate_company's own credential_ref shape check
    (_CREDENTIAL_REF_SHAPE_RE requires a lowercase-only server name)."""
    hits = company.find_secret_shapes({"env": {"API_TOKEN": "Browser:MyServer"}})
    assert hits != []
    hits = company.find_secret_shapes({"env": {"API_TOKEN": "browser:MY_SERVER"}})
    assert hits != []


def test_lowercase_browser_ref_value_still_exempted_everywhere():
    """Paired recovery test: the genuinely schema-valid lowercase
    browser:<server> shape stays exempted everywhere _is_safe_literal is
    consulted, not just at $.accounts[i].credential_ref -- the narrowing
    must not become an overbroad refusal of the shape it's meant to keep
    exempting."""
    hits = company.find_secret_shapes({"env": {"API_TOKEN": "browser:playwright-gtm"}})
    assert hits == []
