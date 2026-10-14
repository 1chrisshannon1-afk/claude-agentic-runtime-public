"""#27: host_systems is host-level only by default, so it can't tell two
brands apart on a shared host (business.google.com, facebook.com).
Optional path-prefix-keyed entries (host/path-prefix, e.g. a GBP location
id or Facebook Page id appearing in the URL) let one brand's clicks map to
gbp_restoration/facebook_restoration while a second brand's clicks on the
SAME host map to gbp_remodeling/facebook_remodeling. Tested with synthetic
ids matching the real-world digit lengths (a 19-digit GBP location id, a
15-digit Facebook Page id) -- never real identifiers, since this repo is
mirrored to GitHub.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402

_REMODELING_LOCATION_ID = "9000000000000000001"
_RESTORATION_LOCATION_ID = "9000000000000000002"
_REMODELING_FB_PAGE_ID = "100000000000001"


def _brightline_two_brand_pack() -> dict:
    return {
        "host_systems": {
            f"business.google.com/{_REMODELING_LOCATION_ID}": "gbp_remodeling",
            f"business.google.com/{_RESTORATION_LOCATION_ID}": "gbp_restoration",
            f"facebook.com/{_REMODELING_FB_PAGE_ID}": "facebook_remodeling",
        }
    }


def test_gbp_remodeling_location_id_in_url_maps_correctly():
    """RED-check: remove the path-scoped-entry check in host_system_for_url
    (or check plain host-only entries first) and this fails -- both
    Brightline GBP location ids share the SAME host, so without path
    scoping there would be no way to distinguish them at all."""
    pack = _brightline_two_brand_pack()
    url = f"https://business.google.com/locations/{_REMODELING_LOCATION_ID}/edit"
    assert htt.host_system_for_url(url, pack) == "gbp_remodeling"


def test_gbp_restoration_location_id_in_url_maps_correctly():
    pack = _brightline_two_brand_pack()
    url = f"https://business.google.com/locations/{_RESTORATION_LOCATION_ID}/edit"
    assert htt.host_system_for_url(url, pack) == "gbp_restoration"


def test_facebook_page_id_in_url_maps_correctly():
    pack = _brightline_two_brand_pack()
    url = f"https://www.facebook.com/{_REMODELING_FB_PAGE_ID}/settings"
    assert htt.host_system_for_url(url, pack) == "facebook_remodeling"


def test_path_scoped_entry_wins_over_plain_host_entry_for_same_host():
    """A pack combining BOTH a path-scoped entry and a plain host-only
    entry for the same host: the path-scoped one must win when its
    path-prefix is present in the URL."""
    pack = {
        "host_systems": {
            "business.google.com": "gbp",  # generic fallback for this host
            f"business.google.com/{_REMODELING_LOCATION_ID}": "gbp_remodeling",
        }
    }
    url = f"https://business.google.com/locations/{_REMODELING_LOCATION_ID}/edit"
    assert htt.host_system_for_url(url, pack) == "gbp_remodeling"


def test_plain_host_entry_still_used_when_no_path_prefix_matches():
    """A URL on the shared host that carries NEITHER brand's id falls back
    to the plain host-only entry (when one exists), never to a wrong
    brand's mapping."""
    pack = {
        "host_systems": {
            "business.google.com": "gbp",
            f"business.google.com/{_REMODELING_LOCATION_ID}": "gbp_remodeling",
            f"business.google.com/{_RESTORATION_LOCATION_ID}": "gbp_restoration",
        }
    }
    url = "https://business.google.com/dashboard"
    assert htt.host_system_for_url(url, pack) == "gbp"


def test_host_systems_path_scoped_key_validates_ok():
    """validate_company accepts a path-scoped host_systems key (host/path)
    the same way it accepts a plain host key -- the key format itself is
    never validated beyond being a non-empty string."""
    pack = {
        "host_systems": {
            f"business.google.com/{_REMODELING_LOCATION_ID}": "gbp_remodeling",
            f"business.google.com/{_RESTORATION_LOCATION_ID}": "gbp_restoration",
        }
    }
    ok, reasons = company.validate_company("acme", pack, siblings={})
    host_systems_reasons = [r for r in reasons if "host_systems" in r]
    assert host_systems_reasons == []


# --------------------------------------------------------------------------
# nit: a path-prefix id must match on a real token boundary, never as a
# bare substring that can match INSIDE a longer, unrelated id
# --------------------------------------------------------------------------


def test_shorter_id_does_not_spuriously_match_inside_longer_unrelated_id():
    """RED-check: revert host_system_for_url's path-prefix check back to a
    bare `path_prefix in haystack` substring test and this fails -- a
    shorter numeric id ('72655') matches as a SUBSTRING inside an unrelated
    longer id ('9172655813') that shares the same digits but is a
    genuinely different GBP location."""
    pack = {
        "host_systems": {
            "business.google.com/72655": "gbp_remodeling",
        }
    }
    # The URL carries ONLY the unrelated longer id -- '72655' is a bare
    # substring of '9172655813' but never appears at a real boundary.
    url = "https://business.google.com/locations/9172655813/edit"
    assert htt.host_system_for_url(url, pack) != "gbp_remodeling"


def test_id_matches_at_a_real_token_boundary():
    """Paired recovery test: the SAME shorter id genuinely present as its
    own path segment still matches correctly -- the boundary fix must not
    become an overbroad refusal of legitimate matches."""
    pack = {
        "host_systems": {
            "business.google.com/72655": "gbp_remodeling",
        }
    }
    url = "https://business.google.com/locations/72655/edit"
    assert htt.host_system_for_url(url, pack) == "gbp_remodeling"


def test_id_matches_in_query_string_at_boundary():
    pack = {
        "host_systems": {
            "business.google.com/72655": "gbp_remodeling",
        }
    }
    url = "https://business.google.com/dashboard?location=72655"
    assert htt.host_system_for_url(url, pack) == "gbp_remodeling"


# --------------------------------------------------------------------------
# nit: a path-prefix id must match against PATH + QUERY only, never the
# full URL (scheme and host included) -- a prefix that happens to equal a
# host LABEL must not match every URL on that host regardless of path.
# --------------------------------------------------------------------------


def test_path_scoped_id_matching_a_host_label_does_not_match_every_url_on_that_host():
    """RED-check: revert host_system_for_url's path-scoped match to test
    against the full `url` string (scheme and host included) and this
    fails -- a path-prefix that happens to equal a label appearing in the
    HOST itself ('business', present in 'business.google.com') would then
    match EVERY url on that host regardless of the actual path, defeating
    the whole point of a path-scoped entry (disambiguating two brands on
    one shared host)."""
    pack = {
        "host_systems": {
            "business.google.com/business": "gbp_remodeling",
        }
    }
    # The path-prefix "business" appears only in the HOST label
    # ("business.google.com"), never in the actual path or query.
    url = "https://business.google.com/dashboard?tab=overview"
    assert htt.host_system_for_url(url, pack) != "gbp_remodeling"


def test_path_scoped_id_genuinely_in_path_still_matches_even_when_it_equals_a_host_label():
    """Paired recovery test: the SAME prefix, when it genuinely appears in
    the path (not just the host), still matches -- the fix must not become
    an overbroad refusal of a legitimate path-borne match."""
    pack = {
        "host_systems": {
            "business.google.com/business": "gbp_remodeling",
        }
    }
    url = "https://business.google.com/locations/business/edit"
    assert htt.host_system_for_url(url, pack) == "gbp_remodeling"


# --------------------------------------------------------------------------
# nit: a host_systems key whose host part carries a scheme or ':' is
# rejected by validate_company (it would silently never match any real URL)
# --------------------------------------------------------------------------


def test_host_systems_key_with_scheme_prefix_rejected():
    """RED-check: remove the host-part shape check in validate_company and
    this fails -- 'https://facebook.com/x' partitions (via the harvester's
    own key.partition('/')) into host 'https:' and path prefix
    'facebook.com/x', which never matches any real URL's hostname, so this
    rule would silently NEVER fire -- a config mistake that validate_company
    must catch, not silently accept as valid."""
    pack = {"host_systems": {"https://facebook.com/x": "facebook_remodeling"}}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("host_systems" in r and "https://facebook.com/x" in r for r in reasons)


def test_host_systems_key_with_port_shaped_host_rejected():
    pack = {"host_systems": {"business.google.com:8080": "gbp"}}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("host_systems" in r for r in reasons)


def test_host_systems_key_bare_host_still_accepted():
    """Paired recovery test: a genuinely bare host (no scheme, no port, no
    path prefix) is still accepted -- the shape check must not become an
    overbroad refusal of legitimate keys."""
    pack = {"host_systems": {"business.google.com": "gbp"}}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    host_systems_reasons = [r for r in reasons if "host_systems" in r]
    assert host_systems_reasons == []


def test_host_systems_key_path_scoped_host_part_still_accepted():
    """A path-scoped key's HOST part (before the '/') is still checked and
    accepted when it is a genuinely bare host -- only the host PART is
    checked for a scheme/port, never the path-prefix segment after it
    (which may legitimately contain other characters)."""
    pack = {"host_systems": {f"business.google.com/{_REMODELING_LOCATION_ID}": "gbp_remodeling"}}
    ok, reasons = company.validate_company("acme", pack, siblings={})
    host_systems_reasons = [r for r in reasons if "host_systems" in r]
    assert host_systems_reasons == []
