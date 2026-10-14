"""Minor 16: validate_add_fields rejects an ambiguous actor for a NEW
entry. Valid: an agent shape (<seat>:<agent_id>, main-session) or an
explicit non-agent (owner..., outside:<who>). Legacy lines (read, not
written) are never subject to this check.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402


_SYSTEMS = ("google_ads",)


def _fields(**overrides) -> dict:
    fields = {
        "system": "google_ads", "action": "update", "object": "x", "before": None, "after": None,
        "why": "y", "actor": "gtm-operator:ac06afdc5dc9de0f3", "evidence": [], "undo": "z",
        "approval": "a", "status": "done", "account": None, "notes": None,
    }
    fields.update(overrides)
    return fields


def test_valid_agent_shape_accepted():
    activity_log.validate_add_fields(_fields(actor="gtm-operator:ac06afdc5dc9de0f3"), _SYSTEMS)


def test_valid_main_session_accepted():
    activity_log.validate_add_fields(_fields(actor="main-session"), _SYSTEMS)


def test_valid_main_session_prefix_accepted():
    activity_log.validate_add_fields(
        _fields(actor="main-session (executing paid-acquisition-strategist ruling)"), _SYSTEMS
    )


def test_valid_owner_accepted():
    activity_log.validate_add_fields(_fields(actor="owner"), _SYSTEMS)


def test_valid_owner_prefix_accepted():
    activity_log.validate_add_fields(_fields(actor="owner (via main session)"), _SYSTEMS)


def test_valid_outside_accepted():
    activity_log.validate_add_fields(_fields(actor="outside:vendor"), _SYSTEMS)


def test_ambiguous_bare_specialist_name_rejected():
    """RED-check: remove the is_valid_new_actor_shape call in
    validate_add_fields and this fails -- 'brand-architect' (a real
    Brightline free-text actor value that is NOT a known agent shape) would
    be silently accepted for a brand-new entry."""
    try:
        activity_log.validate_add_fields(_fields(actor="brand-architect"), _SYSTEMS)
        assert False, "expected ValidationError"
    except activity_log.ValidationError as exc:
        assert "ambiguous" in str(exc)


def test_ambiguous_unknown_backfill_rejected():
    try:
        activity_log.validate_add_fields(_fields(actor="unknown (backfill)"), _SYSTEMS)
        assert False, "expected ValidationError"
    except activity_log.ValidationError:
        pass


def test_bare_outside_with_no_who_rejected():
    """outside: alone (no <who>) is still ambiguous -- the shape requires
    a non-empty who after the colon."""
    try:
        activity_log.validate_add_fields(_fields(actor="outside:"), _SYSTEMS)
        assert False, "expected ValidationError"
    except activity_log.ValidationError:
        pass


def test_empty_actor_rejected():
    try:
        activity_log.validate_add_fields(_fields(actor="   "), _SYSTEMS)
        assert False, "expected ValidationError"
    except activity_log.ValidationError:
        pass


# --------------------------------------------------------------------------
# Legacy lines stay readable -- this check is write-only, never applied on
# read (is_agent_actor / read_jsonl / audit are unaffected)
# --------------------------------------------------------------------------


def test_legacy_ambiguous_actor_still_readable_by_is_agent_actor():
    """is_valid_new_actor_shape is a WRITE-time gate only -- a legacy line
    already on disk with an ambiguous free-text actor (e.g.
    "brand-architect") must still be readable and classifiable by
    is_agent_actor without raising."""
    # is_agent_actor never raises -- it simply classifies (False for this
    # shape, per major 5), proving legacy free-text actors remain readable.
    assert activity_log.is_agent_actor("brand-architect") is False
