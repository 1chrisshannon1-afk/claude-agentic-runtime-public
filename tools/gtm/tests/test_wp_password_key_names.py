"""#25: the secret-scan key-name rule must catch WordPress application
passwords: WP_APP_PASS, APP_PASSWORD, application_password, and *_PASS
generally -- without false-flagging unrelated words merely containing
"pass" (passenger, bypass).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


def test_wp_app_pass_key_name_flagged():
    """RED-check: revert _SECRET_KEY_NAME_RE to the pre-#25 pattern (no
    app-password/*_PASS fragment) and this fails -- WP_APP_PASS contains
    neither "password" nor "passwd" as a substring."""
    hits = company.find_secret_shapes({"WP_APP_PASS": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_app_password_key_name_flagged():
    hits = company.find_secret_shapes({"APP_PASSWORD": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_application_password_key_name_flagged():
    hits = company.find_secret_shapes({"application_password": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_generic_underscore_pass_suffix_flagged():
    hits = company.find_secret_shapes({"DB_PASS": "reallylongsecretvalue1234567890"})
    assert hits != []
    hits = company.find_secret_shapes({"smtp_pass": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_bare_pass_key_name_flagged():
    hits = company.find_secret_shapes({"pass": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_unrelated_words_containing_pass_not_flagged():
    """Paired recovery test: the widened rule must not become a blanket
    "contains 'pass'" match -- passenger/bypass-shaped key names must stay
    clean when their value isn't independently secret-shaped."""
    hits = company.find_secret_shapes({"passenger_count": "42"})
    assert hits == []
    hits = company.find_secret_shapes({"bypass_cache": "true"})
    assert hits == []


def test_wp_app_pass_safe_literal_value_stays_clean():
    """A safe-literal value (env-var reference) under a WP-password-shaped
    key name is still exempted, same as any other secret-key-name match."""
    hits = company.find_secret_shapes({"WP_APP_PASS": "${WORDPRESS_APP_PASSWORD}"})
    assert hits == []


# --------------------------------------------------------------------------
# nit: camelCase *Pass-shaped key names (appPass, dbPass) with no
# separator at all -- the underscore-boundary rule above misses these
# entirely, since "Pass" is never preceded by `[_-]` or string-start.
# --------------------------------------------------------------------------


def test_camelcase_app_pass_key_name_flagged():
    """RED-check: revert _SECRET_KEY_NAME_RE to drop the camel-boundary
    alternative and this fails -- "appPass" contains no "_"/"-" before
    "Pass" and doesn't start the string with "pass", so none of the
    underscore-boundary alternatives match it."""
    hits = company.find_secret_shapes({"appPass": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_camelcase_db_pass_key_name_flagged():
    hits = company.find_secret_shapes({"dbPass": "reallylongsecretvalue1234567890"})
    assert hits != []


def test_camelcase_pass_still_exempts_safe_literal_value():
    """Paired recovery test: a safe-literal value under a camelCase
    *Pass-shaped key is still exempted, same as every other secret-key-name
    match."""
    hits = company.find_secret_shapes({"appPass": "${APP_PASS}"})
    assert hits == []


def test_unrelated_camelcase_words_still_not_flagged():
    """Paired recovery test: the camel-boundary alternative must not widen
    into a blanket "contains pass" match -- a genuinely unrelated
    camelCase key with no capital-P "Pass" boundary stays clean."""
    hits = company.find_secret_shapes({"passengerCount": "42"})
    assert hits == []
    hits = company.find_secret_shapes({"bypassCache": "true"})
    assert hits == []


# --------------------------------------------------------------------------
# Nit fix: the camel-boundary alternative's trailing boundary
# (`(?:[A-Z_-]|$)`) used to sit OUTSIDE the `(?-i:...)` case-sensitive
# group, so the leading `(?i)` flag made `[A-Z]` match a lowercase letter
# too -- "isPassenger" matched via "sPass" + the next lowercase "e" wrongly
# accepted as `[A-Z]`, and "userPassport" the same way via "rPass" + "p".
# --------------------------------------------------------------------------


def test_is_passenger_key_name_not_flagged():
    """RED-check: revert _SECRET_KEY_NAME_RE's camel-boundary alternative
    to `(?-i:[a-z]Pass)(?:[A-Z_-]|$)` (boundary outside the case-sensitive
    group) and this fails -- "isPassenger" matches via "sPass" followed by
    the lowercase "e" wrongly accepted as "[A-Z]" under the outer (?i)."""
    hits = company.find_secret_shapes({"isPassenger": "some ordinary non-secret value"})
    assert hits == []


def test_user_passport_key_name_not_flagged():
    hits = company.find_secret_shapes({"userPassport": "some ordinary non-secret value"})
    assert hits == []
