"""#23: the credential_ref and lead_sink.ref secret-scan exemptions are
scoped to an EXACT JSON path within company.json ONLY -- never a bare
key-name/kind match anywhere in the structure, and never inside mcp.json
at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


# --------------------------------------------------------------------------
# credential_ref: exact path only, company.json only
# --------------------------------------------------------------------------


def test_credential_ref_exempted_at_exact_accounts_path():
    """Finding #7 fix: the ORIGINAL version of this test called
    `find_secret_shapes` WITHOUT `is_company_json=True`, so the exact-path
    exemption this test claims to cover never actually ran -- it passed
    only because "browser:playwright-gtm" is ALSO a generic safe literal
    (`_BROWSER_REF_RE`), which clears the scan regardless of the
    exemption. As a further consequence, since every VALID credential_ref
    shape (`gsm:...` | `browser:...` | `none`) is itself a generic safe
    literal too (see `_is_safe_literal`), no valid shape can ever exercise
    this exemption's real effect -- only a genuinely secret-SHAPED value
    sitting at the exact path can. This test now opts in with
    `is_company_json=True` and uses exactly such a value (a real
    Stripe-shaped secret, which the generic scan DOES flag off-path -- see
    test_credential_ref_key_elsewhere_in_company_json_not_exempted) to
    prove the exact-path exemption itself does the clearing.

    RED-check: pass `is_company_json=False` (this test's pre-fix shape,
    or the function's own default) and this assertion fails -- the
    generic scan flags the Stripe-shaped value with no exemption active."""
    hits = company.find_secret_shapes(
        {"accounts": [{"credential_ref": "sk_" "live_abcdefgh12345678"}]},
        is_company_json=True,
    )
    assert hits == []


def test_credential_ref_key_elsewhere_in_company_json_not_exempted():
    """RED-check: revert the exact-path check back to a bare
    `key_name == "credential_ref"` match and this fails -- a
    credential_ref-named key OUTSIDE accounts[] must not get a free pass
    just because of its key name."""
    hits = company.find_secret_shapes({"some_other_object": {"credential_ref": "sk_" "live_abcdefgh12345678"}})
    assert hits != []


def test_credential_ref_inside_mcp_json_env_not_exempted():
    """#23's explicit test case: ya29. (a real Google OAuth access token
    shape) under a credential_ref-named key inside mcp.json's env block
    must be FLAGGED, not exempted, because mcp.json is scanned with
    is_company_json=False. RED-check: call find_secret_shapes without
    is_company_json=False (or remove the is_company_json gate on the
    credential_ref exemption) and this fails."""
    mcp_data = {
        "mcpServers": {
            "x": {"env": {"credential_ref": "ya29.a0AfH6SMBxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}}
        }
    }
    hits = company.find_secret_shapes(mcp_data, is_company_json=False)
    assert hits != []


def test_credential_ref_off_exact_path_relies_on_generic_safe_literal_check():
    """Off the exact $.accounts[<i>].credential_ref path, a
    credential_ref-named key falls through to the generic key-name branch
    (c), which checks the value against the GENERIC _is_safe_literal
    (which recognizes the browser:<server> shape as a safe literal
    independent of key name -- _BROWSER_REF_RE). This value stays clean;
    a genuinely secret-shaped value under the same off-path key name would
    NOT (see test_credential_ref_key_elsewhere_in_company_json_not_exempted,
    which uses a real Stripe-shaped secret and IS flagged)."""
    mcp_data = {
        "mcpServers": {
            "x": {"credential_ref": "browser:playwright-gtm"}
        }
    }
    hits = company.find_secret_shapes(mcp_data, is_company_json=True)
    assert hits == []  # "browser:playwright-gtm" IS a generically-safe literal shape


def test_credential_ref_value_shape_still_enforced_for_real_secrets_at_exact_path():
    """A real secret VALUE sitting at the exact accounts[i].credential_ref
    path is still exempted from the SECRET SCAN specifically (per #23's
    design: the shape check in validate_company is the authoritative
    enforcement point for that field, not the generic secret scanner) --
    confirmed via validate_company, which DOES reject it via the shape
    check."""
    pack = {"accounts": [{"system": "google_ads", "credential_ref": "ya29.a0AfH6SMBxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}]}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("credential_ref" in r for r in reasons)


def test_new_credential_ref_shape_regex_rejects_uppercase_browser_server():
    """#23's regex is `browser:[a-z0-9-]+` -- lowercase only. A pack using
    e.g. "browser:Playwright-GTM" is no longer exempted OR valid."""
    hits = company.find_secret_shapes({"accounts": [{"credential_ref": "browser:Playwright-GTM"}]})
    # Not exempted at the value-shape level (the lowercase form is exempt, see
    # the sibling test above, so this one is flagged) ...
    assert any("credential_ref" in h for h in hits)
    # ... and the authoritative enforcement of the narrowed shape is
    # validate_company's credential_ref shape check:
    pack = {"accounts": [{"system": "x", "credential_ref": "browser:Playwright-GTM"}]}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("credential_ref" in r for r in reasons)


# --------------------------------------------------------------------------
# lead_sink.ref: exact path only, company.json only
# --------------------------------------------------------------------------


def test_lead_sink_ref_exempted_at_exact_top_level_path():
    # nit: find_secret_shapes's is_company_json default flipped to False
    # (the safe default) -- this test is exercising the company.json-only
    # exemption itself, so it must opt in explicitly now.
    hits = company.find_secret_shapes(
        {"lead_sink": {"kind": "google_sheet", "ref": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"}},
        is_company_json=True,
    )
    assert hits == []


def test_google_sheet_kind_dict_elsewhere_not_exempted():
    """#23's explicit test case: sk_live_ under a `kind: google_sheet`
    dict that is NOT the top-level $.lead_sink object must be FLAGGED.
    RED-check: revert the exact-path check (`path == "$.lead_sink"`) back
    to a bare `obj.get("kind") == "google_sheet"` match anywhere in the
    structure and this fails."""
    pack = {
        "some_other_object": {
            "nested": {"kind": "google_sheet", "ref": "sk_" "live_abcdefgh12345678"}
        }
    }
    hits = company.find_secret_shapes(pack)
    assert hits != []


def test_lead_sink_ref_inside_mcp_json_not_exempted():
    """mcp.json is scanned with is_company_json=False -- even a
    perfectly-shaped $.lead_sink.ref-looking object inside mcp.json gets
    no exemption."""
    mcp_data = {"lead_sink": {"kind": "google_sheet", "ref": "sk_" "live_abcdefgh12345678"}}
    hits = company.find_secret_shapes(mcp_data, is_company_json=False)
    assert hits != []


def test_lead_sink_ref_not_exempted_when_nested_not_at_top_level():
    """RED-check: relax the exact-path check from `path == "$.lead_sink"`
    to something that matches any path ENDING in "lead_sink" (e.g. an
    endswith check) and this fails -- a nested $.wrapper.lead_sink object,
    even with the right kind/ref shape, must NOT be exempted; only the
    genuine top-level $.lead_sink is."""
    pack = {"wrapper": {"lead_sink": {"kind": "google_sheet", "ref": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"}}}
    hits = company.find_secret_shapes(pack)
    # The Google-Sheet-id-shaped ref value (44 chars, alphanumeric) DOES
    # match the generic 40+-char base64 secret-value pattern, so without
    # the (correctly withheld) exemption it is flagged here.
    assert hits == ["$.wrapper.lead_sink.ref"]
