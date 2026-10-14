"""Minor 19: host map additions — localservices.google.com and
ads.google.com/localservices both map to 'lsa'; wp-login.php on a pack
domain maps to 'website_wordpress' (or the pack's override).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harvest_tool_trail as htt  # noqa: E402


def test_localservices_google_com_host_maps_to_lsa():
    assert htt.host_system_for_url("https://localservices.google.com/x", None) == "lsa"


def test_ads_google_com_localservices_path_maps_to_lsa():
    """RED-check: remove the _ADS_LSA_PATH_RE check (or its ordering
    before the DEFAULT_HOST_SYSTEMS lookup) and this fails -- the bare
    ads.google.com host would fall through to the generic 'google_ads'
    default instead."""
    assert htt.host_system_for_url("https://ads.google.com/localservices/campaigns", None) == "lsa"
    assert htt.host_system_for_url("https://ads.google.com/localservices", None) == "lsa"


def test_ads_google_com_other_paths_still_map_to_google_ads():
    """Paired recovery test: the path-specific LSA rule must not
    over-broaden to swallow the rest of ads.google.com."""
    assert htt.host_system_for_url("https://ads.google.com/aw/campaigns", None) == "google_ads"


def test_pack_host_systems_can_still_override_lsa_mapping():
    pack = {"host_systems": {"localservices.google.com": "lsa_custom_override"}}
    assert htt.host_system_for_url("https://localservices.google.com/x", pack) == "lsa_custom_override"


def test_wp_login_php_on_pack_domain_maps_to_website_wordpress():
    """RED-check: remove the wp-login.php alternative in _WP_ADMIN_PATH_RE
    and this fails -- only wp-admin would be recognized."""
    pack = {"brands": [{"id": "remodeling", "domains": ["example-remodeling.com"]}]}
    assert htt.host_system_for_url("https://example-remodeling.com/wp-login.php", pack) == "website_wordpress"


def test_wp_login_php_still_works_alongside_wp_admin():
    pack = {"brands": [{"id": "remodeling", "domains": ["example-remodeling.com"]}]}
    assert htt.host_system_for_url("https://example-remodeling.com/wp-admin/edit.php", pack) == "website_wordpress"
    assert htt.host_system_for_url("https://example-remodeling.com/wp-login.php", pack) == "website_wordpress"
    # A non-admin path on the same domain is unaffected.
    assert htt.host_system_for_url("https://example-remodeling.com/about", pack) != "website_wordpress"


def test_wp_login_php_pack_override_wins():
    pack = {
        "brands": [{"id": "remodeling", "domains": ["example-remodeling.com"]}],
        "host_systems": {"example-remodeling.com": "website_remodeling"},
    }
    # A pack-level host override matches the bare domain FIRST (before the
    # wp-login/wp-admin path special case is ever reached), so the whole
    # domain -- including /wp-login.php -- resolves to the pack's own
    # override name.
    assert htt.host_system_for_url("https://example-remodeling.com/wp-login.php", pack) == "website_remodeling"
