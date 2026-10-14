"""Hermetic tests for hooks/cycle_budget.py.

No `sandbox`/HOME patching needed: cycle_budget.py never reads a global path
constant -- every ledger path is an explicit parameter (or a `--ledger`/
`CSA_CYCLE_LEDGER` override resolved at call time), so a `tmp_path`-rooted
ledger file plus explicit `environ` dicts fully isolate every test from the
operator's real ~/.claude/.agent_budget/spend.jsonl.
"""

from __future__ import annotations

import itertools
import json
import os

import cycle_budget as cb
import pytest

KNOWN_TYPES = frozenset({"implement", "code-reviewer", "test-writer"})


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _write_ledger(path, rows: list[dict]) -> None:
    """Write `rows` to a JSONL ledger. BLOCKER 2 (round 12, 2026-08-28):
    backfills a matching `tokens_total` for any row that does not already
    carry that key, computed from the row's OWN final `tokens` dict at
    write time (after any test has finished mutating it) -- mirroring the
    real ledger writer (`agent_budget.py`), which always writes a
    `tokens_total` field on every real row. This keeps the hundreds of
    existing tests that build a row via `_simple_row()` and then mutate
    `row["tokens"]` afterward realistic and passing under
    `price_tokens_usd()`'s new contract (an explicit, ledger-row-level
    `tokens_total` of `None`/missing is UNPRICEABLE, not "caller declined
    the check" -- see that function's docstring). A row that explicitly
    sets its own `tokens_total` (including explicitly to `None`, for a
    test that specifically exercises the missing/malformed case) is never
    touched here. A `tokens` dict that is not a plain dict of real,
    non-bool numeric values is left alone too -- those rows are already
    testing a DIFFERENT malformation that makes the row unpriceable
    regardless of what `tokens_total` says."""
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            row = dict(row)
            if "tokens_total" not in row:
                tokens = row.get("tokens")
                if isinstance(tokens, dict) and tokens:
                    values = list(tokens.values())
                    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                        row["tokens_total"] = sum(values)
            fh.write(json.dumps(row) + "\n")


def _simple_row(**overrides) -> dict:
    base = {
        "ts": "2026-08-28T10:00:00Z",
        "session": "sess-A",
        "agent_type": "implement",
        "model": "claude-sonnet-5",
        "tokens": {"input": 1000, "output": 2000, "cache_read": 0, "cache_creation": 0},
    }
    base.update(overrides)
    return base


WINDOW = dict(cycle_start_ts="2026-08-28T09:00:00Z", cycle_end_ts="2026-08-28T12:00:00Z")


# ---------------------------------------------------------------------------
# Expected-dollar derivation (2026-09-05).
#
# WHY THIS EXISTS: Anthropic's published rates changed and every hardcoded
# dollar literal in this file broke at once -- 70 failures, not one of which
# was a real defect. The overwhelming majority of those tests do not care
# what a token costs; they assert WHICH ROWS the attribution machinery
# summed, collapsed, excluded, or refused to price. For those, a dollar
# literal is incidental fixture arithmetic that silently rots on every
# pricing update, so they derive their expectation from the live table here
# instead.
#
# WHY THIS IS NOT CIRCULAR: `_usd()` re-derives the cost by INDEPENDENT
# arithmetic over `cb.PRICING_USD_PER_MTOK` -- it deliberately does NOT call
# `cb.price_tokens_usd()`, which is the function under test. It therefore
# still fails if `price_tokens_usd()` mis-sums, mis-scales, drops a field,
# or picks the wrong family. What it does NOT independently verify is the
# TABLE'S OWN VALUES -- so the tests whose actual purpose is asserting the
# published rate (the `test_price_tokens_usd_*` family) keep explicit
# literals and must never be converted to use these helpers.
# ---------------------------------------------------------------------------


def _usd(family: str, **token_fields: float) -> float:
    """Expected USD for `token_fields` at `family`'s live published rates.

    Unspecified token fields default to 0. Raises on an unknown family or an
    unknown field name rather than silently pricing it free -- a typo here
    must break loudly, not quietly weaken the assertion it feeds.
    """
    rates = cb.PRICING_USD_PER_MTOK[family]
    unknown = set(token_fields) - set(cb._TOKEN_FIELDS)
    if unknown:
        raise KeyError(f"unknown token field(s): {sorted(unknown)}")
    return sum(count * rates[field] / 1_000_000 for field, count in token_fields.items())


# The default `_simple_row()` token dict, priced. Used by the many tests that
# assert "only the default anchor row counted".
_SIMPLE_ROW_USD = _usd("sonnet", input=1000, output=2000)

# READING THE DOCSTRINGS BELOW: many narrate a historical bug in the dollar
# terms that were current when it was found and fixed ("before the fix this
# reported known/$150"). Those figures are priced at the RATES OF THAT DATE
# (sonnet $3/$15, opus $15/$75) and are deliberately left as written -- they
# are a record of what the module actually did at the time, and rewriting
# them to today's rates would falsify that record. They will NOT match what
# the same fixture prices at today; the assertions, not the prose, are the
# authority on current behavior. Comments stating LIVE arithmetic were
# corrected to current rates on 2026-09-05.

# The recurring fixture amounts across the attribution/collapse tests below.
# These name the SHAPE of a fixture row ("the anchor", "the reap"), not a
# price -- their dollar value moves with the published rates, which is the
# point: these tests assert which rows were summed, never what a token costs.
_ANCHOR_USD = _usd("sonnet", input=1_000_000)  # the standard 1M-input anchor row
_REAP_USD = _usd("sonnet", input=10_000_000)  # the standard 10M-input reap row
_BIG_ANCHOR_USD = _usd("sonnet", input=5_000_000)  # the 5M-input anchor variant
_BIG_REAP_USD = _usd("sonnet", input=50_000_000)  # the 50M-input reap variant

# BLOCKER 2 (round 14, 2026-08-28): the real combination space a correlated
# row + its anchor can occupy relative to THIS cycle's own [start_dt,
# end_dt] window -- FOUR positions on EACH axis, not two. See
# `test_falsify_correlated_row_anchor_position_grid_4x4`.
_GRID_POSITIONS = ("before", "in", "after", "undated")
_GRID_TS = {
    "before": "2026-08-28T07:00:00Z",  # before WINDOW's own 09:00 start
    "in": "2026-08-28T10:00:00Z",  # inside WINDOW's own 09:00-12:00 span
    "after": "2026-08-28T16:00:00Z",  # after WINDOW's own 12:00 end
    "undated": "not-a-real-timestamp",  # unparsable -- `_row_ts()` returns None
}


# ---------------------------------------------------------------------------
# Pure helpers: normalize_model / price_tokens_usd / pricing validation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model,expected",
    [
        ("claude-sonnet-5", "sonnet"),
        ("claude-opus-5[1m]", "opus"),
        ("claude-opus-4-8", "opus"),
        ("opus", "opus"),
        ("claude-haiku-4-5-20251001", "haiku"),
        ("claude-fable-5", "fable"),
        ("claude-mythos-5", "fable"),
        ("claude-imaginary-9", "unknown"),
        (None, "unknown"),
        ("", "unknown"),
        (123, "unknown"),
    ],
)
def test_normalize_model(model, expected):
    assert cb.normalize_model(model) == expected


@pytest.mark.parametrize(
    "family,input_rate,output_rate",
    [
        # Anthropic's published list price, USD per MILLION tokens, verified
        # against platform.claude.com/docs/en/about-claude/pricing on
        # 2026-09-05. These are DELIBERATELY hardcoded and must never be
        # derived from `cb.PRICING_USD_PER_MTOK` -- this test's entire job is
        # to pin that table to the published rate, so a test that read the
        # table to compute its own expectation would assert nothing at all.
        ("opus", 5.00, 25.00),  # Opus 4.5 through Opus 5
        ("sonnet", 2.00, 10.00),  # Sonnet 5 (introductory pricing made permanent)
        ("haiku", 1.00, 5.00),  # Haiku 4.5
        ("fable", 10.00, 50.00),  # Fable 5 / Mythos 5 (added 2026-09-05)
    ],
)
def test_pricing_table_matches_published_rates(family, input_rate, output_rate):
    """The table is a hardcoded copy of an EXTERNAL fact that changes without
    warning, and this module gates real spend against it -- a stale rate
    silently mis-gates every cycle. On 2026-09-05 every family in it was
    found stale (opus by 3x in both directions, having kept the RETIRED Opus
    4.1/4.0 $15/$75), and nothing failed, because no test asserted a rate
    for opus or haiku at all. This pins all four (fable added the same day
    once its rate was confirmed published -- see PRICING_USD_PER_MTOK's own
    "RESOLVED 2026-09-05" note).

    Cache rates are checked as MULTIPLES of input rather than as literals:
    Anthropic prices cache reads at 0.1x input and 5-minute cache writes at
    1.25x input across every model, so the multiplier is the published fact
    and re-stating derived dollars would just duplicate the arithmetic.
    """
    rates = cb.PRICING_USD_PER_MTOK[family]
    assert rates["input"] == pytest.approx(input_rate)
    assert rates["output"] == pytest.approx(output_rate)
    assert rates["cache_read"] == pytest.approx(input_rate * 0.1)
    assert rates["cache_creation"] == pytest.approx(input_rate * 1.25)


def test_pricing_table_covers_exactly_the_known_families():
    """A family added to the table without a published-rate assertion above
    would otherwise gate spend on an unverified number."""
    assert set(cb.PRICING_USD_PER_MTOK) == {"opus", "sonnet", "haiku", "fable"}


def test_price_tokens_usd_known_family():
    tokens = {"input": 1_000_000, "output": 1_000_000, "cache_read": 0, "cache_creation": 0}
    cost = cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK)
    assert cost == pytest.approx(2.00 + 10.00)  # sonnet: $2/MTok in + $10/MTok out


def test_price_tokens_usd_unknown_family_returns_none_not_zero():
    tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert cb.price_tokens_usd(tokens, "unknown", cb.PRICING_USD_PER_MTOK) is None


def test_price_tokens_usd_malformed_tokens_returns_none():
    assert cb.price_tokens_usd(None, "sonnet", cb.PRICING_USD_PER_MTOK) is None
    assert cb.price_tokens_usd({"input": "lots"}, "sonnet", cb.PRICING_USD_PER_MTOK) is None
    assert cb.price_tokens_usd({"input": -5}, "sonnet", cb.PRICING_USD_PER_MTOK) is None
    assert cb.price_tokens_usd({"input": True}, "sonnet", cb.PRICING_USD_PER_MTOK) is None


def test_falsify_price_tokens_usd_empty_dict_is_none_not_zero(tmp_path):
    """BLOCKER 2 (round 6, 2026-08-28), the reviewer's first repro: an EMPTY
    tokens dict used to price at a confident $0.00 (every field defaulted
    via `.get(field, 0)`) instead of refusing to guess. A required field
    ABSENT entirely must never be treated the same as that field being
    present with value 0."""
    assert cb.price_tokens_usd({}, "sonnet", cb.PRICING_USD_PER_MTOK) is None


def test_falsify_price_tokens_usd_one_missing_field_is_none_not_zero():
    """A tokens dict missing exactly one of the four known fields must also
    refuse to price -- not just a fully-empty dict."""
    missing_cache_creation = {"input": 1000, "output": 2000, "cache_read": 0}
    assert cb.price_tokens_usd(missing_cache_creation, "sonnet", cb.PRICING_USD_PER_MTOK) is None


def test_price_tokens_usd_field_present_with_value_zero_still_prices():
    """The other half of the BLOCKER 2 distinction: a field genuinely
    PRESENT with value 0 is real, known data (zero of that token type was
    used) and must still price normally -- only an ABSENT field refuses."""
    tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK) == pytest.approx(2.00)


def test_falsify_price_tokens_usd_tokens_total_mismatch_forces_none(tmp_path):
    """BLOCKER 2 (round 6, 2026-08-28), the reviewer's second repro: every
    KNOWN field present and all zero, but `tokens_total` reports 9,000,000
    -- simulating a real, future billable field (e.g. `reasoning`) this
    table's `_TOKEN_FIELDS` tuple does not yet enumerate, silently present
    in the row and silently priced as free. The `tokens_total` cross-check
    must catch this even though every field this function iterates is
    individually well-formed."""
    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK, tokens_total=9_000_000) is None


def test_price_tokens_usd_tokens_total_matching_sum_still_prices():
    """The paired non-regression case: when `tokens_total` genuinely equals
    the sum of the known fields, the cross-check must never itself block a
    normal, honest row from pricing."""
    tokens = {"input": 1_000_000, "output": 1_000_000, "cache_read": 0, "cache_creation": 0}
    cost = cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK, tokens_total=2_000_000)
    assert cost == pytest.approx(2.00 + 10.00)  # sonnet: $2/MTok in + $10/MTok out


def test_price_tokens_usd_tokens_total_omitted_skips_cross_check():
    """Omitting the `tokens_total` argument entirely (the default, and
    every pre-round-6 call site) must skip the cross-check -- purely
    additive, never a behavior change for a caller that cannot supply it."""
    tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK) == pytest.approx(2.00)


def test_falsify_price_tokens_usd_explicit_none_tokens_total_forces_unpriceable():
    """BLOCKER 2 (round 11 review finding, round 12 fix, 2026-08-28):
    corrects this test's own prior (incorrect) assertion that an
    EXPLICITLY passed `tokens_total=None` skips the cross-check the same
    way omitting the argument does. It must not: both of
    `attribute_cycle_spend()`'s real call sites always pass
    `row.get("tokens_total")`, which is `None` for BOTH a missing key and
    an explicit JSON `null` on a real ledger row -- and a real row missing
    this field is exactly the malformed-row case this function must refuse
    to price, never silently treat as 'caller opted out'."""
    tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK, tokens_total=None) is None


def test_falsify_price_tokens_usd_unknown_key_present_forces_none_even_when_tokens_total_consistent():
    """Finding #6 (round 8, 2026-08-28): the `tokens_total` cross-check only
    catches a new billable field if the WRITER also folds that field's
    value into `tokens_total` -- it is opt-in on the writer, not a general
    defense. A `reasoning_tokens` key present in `tokens` at all, even with
    a fully CONSISTENT `tokens_total` (so the old cross-check alone would
    never notice), must still refuse to price -- an unrecognized key is
    never assumed to be free."""
    tokens = {
        "input": 1_000_000,
        "output": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "reasoning_tokens": 5_000_000,
    }
    # tokens_total intentionally does NOT include reasoning_tokens, matching
    # the reviewer's exact repro shape (a writer that hasn't updated
    # tokens_total to reflect the new field yet).
    assert (
        cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK, tokens_total=1_000_000)
        is None
    )
    # And with no tokens_total supplied at all (skips the OTHER check only).
    assert cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK) is None


def test_price_tokens_usd_known_fields_only_still_prices_normally():
    """Paired non-regression: a tokens dict containing exactly the known
    fields (no extras) must still price exactly as before."""
    tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert cb.price_tokens_usd(tokens, "sonnet", cb.PRICING_USD_PER_MTOK) == pytest.approx(2.00)


def test_validate_pricing_table():
    assert cb._validate_pricing_table(cb.PRICING_USD_PER_MTOK) is True
    assert cb._validate_pricing_table({}) is False
    assert cb._validate_pricing_table({"sonnet": {"input": -1}}) is False
    assert cb._validate_pricing_table({"sonnet": "nope"}) is False
    assert cb._validate_pricing_table("nope") is False


def _all_rates(value: float) -> dict:
    return {field: value for field in cb._TOKEN_FIELDS}


def test_falsify_validate_pricing_table_rejects_unknown_sentinel_key():
    """BLOCKER 3 (round 8, 2026-08-28), the reviewer's exact repro: a
    pricing-file override keyed on the literal "unknown" sentinel
    `normalize_model()` returns for every unrecognized/null model must be
    REJECTED, not accepted -- accepting it turns the entire unpriced-model
    safety gate off (every unpriceable row silently prices at whatever rate
    the override names, including $0.00)."""
    assert cb._validate_pricing_table({"unknown": _all_rates(1.0)}) is False


def test_falsify_validate_pricing_table_rejects_all_zero_rates_for_real_family():
    """A real, known family (e.g. "sonnet") with an all-zero rate table is
    the identical failure by a different route -- it silently zeros out
    real spend for a family this module WOULD otherwise price correctly."""
    assert cb._validate_pricing_table({"sonnet": _all_rates(0.0)}) is False


def test_validate_pricing_table_rejects_invented_family_name():
    """Any key outside the real, known pricing families is rejected, not
    just the literal "unknown" string -- `normalize_model()` can never
    route a real model string to an invented/misspelled family either."""
    assert cb._validate_pricing_table({"claude-fable-5": _all_rates(1.0)}) is False


def test_falsify_cli_check_with_unknown_sentinel_pricing_file_is_rejected(tmp_path):
    """BLOCKER 3 (round 8, 2026-08-28), the reviewer's exact CLI-level
    repro: a `--pricing-file` containing only `{"unknown": {...}}` must
    make `check` fail with an argument error, never a confident
    `known`/$0.00 verdict for a row this module is specifically designed
    to refuse to price."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A", model=None)])
    pricing_file = tmp_path / "pricing.json"
    pricing_file.write_text(json.dumps({"unknown": _all_rates(0.0)}))
    exit_code, payload = cb.run(
        [
            "check",
            "--system",
            "loop",
            "--session",
            "sess-A",
            "--cycle-start",
            WINDOW["cycle_start_ts"],
            "--cycle-end",
            WINDOW["cycle_end_ts"],
            "--agent-types",
            "implement",
            "--ledger",
            str(ledger),
            "--pricing-file",
            str(pricing_file),
            "--expected-dispatches",
            "1",
            "--ceiling-usd",
            "100.0",
        ],
        environ={"HOME": str(tmp_path)},
    )
    assert exit_code == 2
    assert payload.get("error", "").startswith("invalid-arguments")


def test_load_pricing_file_roundtrip(tmp_path):
    good = tmp_path / "pricing.json"
    good.write_text(json.dumps(cb.PRICING_USD_PER_MTOK))
    loaded = cb._load_pricing_file(str(good))
    assert loaded == cb.PRICING_USD_PER_MTOK


def test_load_pricing_file_missing_or_invalid(tmp_path):
    assert cb._load_pricing_file(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert cb._load_pricing_file(str(bad)) is None
    invalid_shape = tmp_path / "invalid.json"
    invalid_shape.write_text(json.dumps({"sonnet": {"input": -1}}))
    assert cb._load_pricing_file(str(invalid_shape)) is None


# ---------------------------------------------------------------------------
# Timestamp helpers.
# ---------------------------------------------------------------------------


def test_parse_ts_accepts_runtime_format_and_iso():
    dt1 = cb._parse_ts("2026-08-28T09:00:00Z")
    dt2 = cb._parse_ts("2026-08-28T09:00:00+00:00")
    assert dt1 == dt2


def test_parse_ts_rejects_garbage():
    with pytest.raises(ValueError):
        cb._parse_ts("not-a-timestamp")
    with pytest.raises(ValueError):
        cb._parse_ts("")
    with pytest.raises(ValueError):
        cb._parse_ts(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Caller-misuse -> ValueError (never laundered into "unknown").
# ---------------------------------------------------------------------------


def test_attribute_rejects_empty_system(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(ValueError):
        cb.attribute_cycle_spend(
            str(ledger),
            system="",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            expected_dispatch_count=None,
            **WINDOW,
        )


def test_attribute_rejects_empty_session_id(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(ValueError):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="",
            known_agent_types=KNOWN_TYPES,
            expected_dispatch_count=None,
            **WINDOW,
        )


def test_attribute_rejects_empty_known_agent_types(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(ValueError):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=frozenset(),
            expected_dispatch_count=None,
            **WINDOW,
        )


def test_attribute_rejects_inverted_window(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(ValueError):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            expected_dispatch_count=None,
            cycle_start_ts="2026-08-28T12:00:00Z",
            cycle_end_ts="2026-08-28T09:00:00Z",
        )


def test_attribute_rejects_negative_expected_dispatch_count(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(ValueError):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            expected_dispatch_count=-1,
            **WINDOW,
        )


def test_attribute_rejects_bare_string_known_agent_types(tmp_path):
    """BLOCKER 1 (2026-08-28, real repro): passing the string 'implement'
    where a collection of agent_types was intended (the natural CLI-parsing
    mistake) must raise ValueError -- NOT silently iterate the string
    character-by-character, empty the ambiguous bucket, and return a false
    allowed=True/$0.00. This is exactly the laundering the module's own
    docstring promises never happens."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger,
        [_simple_row(session=None, agent_type="implement", model="claude-sonnet-5")],
    )
    with pytest.raises(ValueError, match="known_agent_types"):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types="implement",  # BUG: bare string, not a set/list
            expected_dispatch_count=None,
            **WINDOW,
        )
    with pytest.raises(ValueError, match="known_agent_types"):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=b"implement",  # bytes is the same failure mode
            expected_dispatch_count=None,
            **WINDOW,
        )
    # Confirm the correct call shape (a real set of the identical value)
    # still classifies the row as ambiguous -- proving the bug was in the
    # bare-string container, not the value itself.
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types={"implement"},
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.ambiguous_rows == 1


def test_decide_rejects_non_positive_ceiling(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row()])
    with pytest.raises(ValueError):
        cb.decide_cycle_budget(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            ceiling_usd=0,
            expected_dispatch_count=1,
            **WINDOW,
        )
    with pytest.raises(ValueError):
        cb.decide_cycle_budget(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            ceiling_usd=-5,
            expected_dispatch_count=1,
            **WINDOW,
        )


def test_decide_expected_dispatch_count_is_a_required_keyword_argument(tmp_path):
    """BLOCKER 3 (round 4): `decide_cycle_budget()` -- the actual gate a real
    dispatcher calls -- must reject an omitted `expected_dispatch_count`
    exactly like its callee `attribute_cycle_spend()` already does. Python
    itself enforces this: omitting the keyword raises TypeError before the
    function body ever runs."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(TypeError):
        cb.decide_cycle_budget(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            ceiling_usd=10.0,
            **WINDOW,
        )  # type: ignore[call-arg]


@pytest.mark.parametrize("bad_value", [True, False, "5", 1.5, 5.0])
def test_expected_dispatch_count_rejects_non_int_types(tmp_path, bad_value):
    """BLOCKER 7 (round 4): `False`/`0.0` alias to a valid-looking 0, `True`
    would render a nonsensical reason string, and a bare `str` previously
    raised an uncaught TypeError instead of this module's documented
    ValueError-for-caller-misuse contract. All of these must now raise a
    clear ValueError, on BOTH `attribute_cycle_spend()` and
    `decide_cycle_budget()`."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(ValueError, match="expected_dispatch_count"):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            expected_dispatch_count=bad_value,
            **WINDOW,
        )
    with pytest.raises(ValueError, match="expected_dispatch_count"):
        cb.decide_cycle_budget(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            ceiling_usd=10.0,
            expected_dispatch_count=bad_value,
            **WINDOW,
        )


# ---------------------------------------------------------------------------
# THE FALSIFIABLE CORE: refuse to guess -> explicit "unknown", never "$0".
# ---------------------------------------------------------------------------


def test_missing_ledger_is_unknown_not_zero(tmp_path):
    """No ledger file at all must never read as '$0 spent, keep going'."""
    missing = tmp_path / "does-not-exist.jsonl"
    attr = cb.attribute_cycle_spend(
        str(missing),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.spent_usd is None
    assert attr.reason == "ledger-unreadable"


def test_unreadable_ledger_directory_is_unknown(tmp_path):
    """A path that exists but is a directory, not a file: unknown, not zero."""
    directory = tmp_path / "spend.jsonl"
    directory.mkdir()
    attr = cb.attribute_cycle_spend(
        str(directory),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.spent_usd is None


def test_empty_ledger_with_zero_expected_is_known_zero(tmp_path):
    """The one legitimate zero: an empty ledger AND zero dispatches expected."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == 0.0


# ---------------------------------------------------------------------------
# BLOCKER 1 (round 3, 2026-08-28) -- the headline fix: zero matched rows with
# NO explicit dispatch-count assertion must NEVER read as "known, $0 spent" --
# it is exactly the state this module cannot tell apart from a wrong
# session id / wrong window swallowing this cycle's real spend.
# ---------------------------------------------------------------------------


def test_falsify_zero_matched_rows_no_count_asserted_is_unknown_not_known_zero(tmp_path):
    """THE reproduced blocker: a correct session_id, an empty ledger, and no
    `expected_dispatch_count` assertion (`None`) must come back `unknown`
    with the exact named reason -- never the pre-fix `known`/$0.00. Before
    round 3's fix, this exact call returned `status="known", spent_usd=0.0`
    (falsified separately by reverting the fix -- see the round's report)."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,  # no assertion made -- must NOT default to safe
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.spent_usd is None
    assert attr.reason == "no-matched-rows-and-no-dispatch-count-asserted"


def test_falsify_wrong_stale_session_id_no_count_asserted_is_unknown(tmp_path):
    """The real-world shape: the caller's session id has a plausible typo/
    staleness, so every real ledger row for this cycle is EXCLUDED (not
    matched) rather than absent outright -- zero matched rows all the same,
    and with no count asserted it must stay unknown, never a false
    known/$0.00 (which would silently hide that this cycle's spend never
    got attributed to it at all)."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A-STALE")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.spent_usd is None
    assert attr.reason == "no-matched-rows-and-no-dispatch-count-asserted"
    assert attr.excluded_rows == 1


def test_falsify_window_entirely_in_future_no_count_asserted_is_unknown(tmp_path):
    """A cycle window that (by caller error) sits entirely BEFORE every real
    ledger row: the row is dropped by the time-window filter, so zero rows
    ever reach the matched/ambiguous/excluded classification at all --
    still zero matched rows, and with no count asserted it must stay
    unknown, never a false known/$0.00."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A", ts="2026-08-29T01:00:00Z")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,  # window ends 2026-08-28T12:00:00Z -- strictly before the row's ts
    )
    assert attr.status == "unknown"
    assert attr.spent_usd is None
    assert attr.reason == "no-matched-rows-and-no-dispatch-count-asserted"


def test_falsify_wrong_session_with_asserted_count_is_unknown_dispatches_not_in_ledger(tmp_path):
    """The one repro cell that was ALREADY safe before round 3, preserved as
    the negative control: a wrong/stale session id PLUS an explicit
    `expected_dispatch_count=1` must still deny -- proving the fix didn't
    accidentally relax this already-correct path."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A-STALE")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "dispatches-not-in-ledger:expected=1"


def test_recovery_pair_explicit_zero_dispatch_count_is_still_known_zero(tmp_path):
    """The RECOVERY pair for the headline blocker: a cycle that genuinely
    expected and got zero dispatches (an EXPLICIT `expected_dispatch_count=
    0`) must still correctly resolve to `known`/$0.00 -- the fix narrows the
    unsafe DEFAULT, it does not remove the one legitimate zero case."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == 0.0


def test_expected_dispatch_count_is_a_required_keyword_argument(tmp_path):
    """BLOCKER 1 (round 3): `expected_dispatch_count` has no default -- a
    caller can no longer silently omit it and land on the unsafe default.
    Python itself enforces this: omitting the keyword raises TypeError
    before the function body ever runs."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    with pytest.raises(TypeError):
        cb.attribute_cycle_spend(
            str(ledger),
            system="loop",
            session_id="sess-A",
            known_agent_types=KNOWN_TYPES,
            **WINDOW,
        )  # type: ignore[call-arg]


def test_wrong_session_rows_are_excluded_not_matched(tmp_path):
    """A different (non-null) session is confidently NOT this cycle."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-OTHER")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == 0.0
    assert attr.excluded_rows == 1
    assert attr.matched_rows == 0


def test_ambiguous_unjoined_row_forces_unknown(tmp_path):
    """This is the exact ~26x-under-report failure mode: an unjoined
    (session: null) row, inside the cycle's window, whose agent_type IS one
    the cycle declared -- must NEVER be silently dropped (undercount) or
    silently included (unverified attribution). It must force `unknown`.
    """
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger,
        [
            _simple_row(session="sess-A"),  # confidently ours
            _simple_row(session=None, agent_type="implement"),  # ambiguous
        ],
    )
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.spent_usd is None
    assert attr.reason == "ambiguous-unjoined-rows-in-window"
    assert attr.ambiguous_rows == 1
    assert attr.matched_rows == 1


def test_unjoined_row_outside_known_agent_types_is_excluded_not_ambiguous(tmp_path):
    """An unjoined row for an agent type this cycle never declared is
    treated as unrelated background noise (documented, bounded assumption),
    not ambiguity -- otherwise a busy shared ledger would poison every cycle.
    """
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session=None, agent_type="trade-plumbing")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.excluded_rows == 1
    assert attr.ambiguous_rows == 0


def test_unexpected_agent_type_for_matched_session_forces_unknown(tmp_path):
    """Session matches exactly, yet the agent_type is one this cycle never
    declared -- 'agent types the cycle never dispatched' from the spec.
    """
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A", agent_type="trade-electrical")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "unexpected-agent-type-for-session"


def test_expected_dispatches_not_in_ledger_at_all_is_unknown(tmp_path):
    """The cycle believes it dispatched N agents; the ledger shows zero rows
    for that session in the window -- must never read as '$0 spent'.
    """
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-OTHER")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=3,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason.startswith("dispatches-not-in-ledger")
    assert attr.spent_usd is None


def test_expected_dispatch_count_mismatch_is_unknown(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=5,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "count-mismatch:expected=5:found=1"


def test_unpriced_model_forces_unknown_never_free(tmp_path):
    """A matched row with an unrecognized model family must never be priced
    at $0 -- it must make the whole attribution unknown.
    """
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A", model="claude-imaginary-9")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "unpriced-model-in-window"
    assert attr.unpriced_rows == 1


def test_rows_outside_time_window_are_ignored_entirely(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger,
        [
            _simple_row(session="sess-A", ts="2026-08-28T01:00:00Z"),  # before window
            _simple_row(session="sess-A", ts="2026-08-29T01:00:00Z"),  # after window
        ],
    )
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == 0.0
    assert attr.matched_rows == 0
    assert attr.excluded_rows == 0


def test_unparsable_row_ts_for_other_session_is_ignored_not_counted_either_way(tmp_path):
    """An unparsable-ts row belonging to some OTHER, non-matching session
    stays correctly dropped with no further bookkeeping -- ambiguous
    evidence about someone ELSE's spend genuinely isn't evidence about this
    cycle's own (this half of the split retains the pre-round-6 behavior,
    which was correct for this case)."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-OTHER", ts="garbage")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.matched_rows == 0
    assert attr.excluded_rows == 0
    assert attr.undated_matched_rows == 0


def test_falsify_unparsable_ts_for_this_sessions_own_row_forces_unknown(tmp_path):
    """BLOCKER 1 (round 6, 2026-08-28), the reviewer's exact repro (single-
    row simplification): a row whose `session` matches THIS cycle's own
    session_id but whose `ts` cannot be parsed is genuine, real spend of
    unknown timing -- it must NEVER be silently dropped the way an
    unparsable-ts row for someone ELSE's session correctly is. Before the
    fix this was treated identically to the other-session case and reported
    a confident `known`/$0 with the row completely invisible in every
    output field; the corrected behavior surfaces it via the dedicated
    `undated_matched_rows` counter and forces `unknown`."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A", ts="garbage")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "matched-row-with-unparsable-ts"
    assert attr.spent_usd is None
    assert attr.undated_matched_rows == 1
    assert attr.matched_rows == 0  # the row never entered `matched` -- it has no known timing


def test_falsify_hidden_spend_from_undated_matched_row_never_confidently_priced(tmp_path):
    """BLOCKER 1 (round 6, 2026-08-28), the reviewer's exact full repro: a
    good, parseable, cheap row ($3.00) plus a garbage-ts row carrying real,
    large spend ($1,800.00) -- BOTH belonging to this cycle's own session.
    Before the fix: `attribute_cycle_spend(..., expected_dispatch_count=1)`
    returned `known, spent_usd=3.0`, with the $1,800 completely invisible
    in every field (matched_rows, malformed_lines, no bucket counted it) --
    and `decide_cycle_budget(..., ceiling_usd=100.0)` returned
    `allowed=True`, when $1,803 of real same-session spend had actually
    occurred. The fix must never report a confident dollar figure here."""
    ledger = tmp_path / "spend.jsonl"
    good_row = _simple_row(session="sess-A")  # sonnet, 1M input == _ANCHOR_USD
    good_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    hidden_row = _simple_row(session="sess-A", ts="garbage")
    hidden_row["tokens"] = {
        "input": 100_000_000,
        "output": 100_000_000,
        "cache_read": 0,
        "cache_creation": 0,
    }  # sonnet: 100M in @ $2/MTok + 100M out @ $10/MTok == $1,200.00
    _write_ledger(ledger, [good_row, hidden_row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "matched-row-with-unparsable-ts"
    assert attr.spent_usd is None
    assert attr.undated_matched_rows == 1

    decision = cb.decide_cycle_budget(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=100.0,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert decision.allowed is False
    assert decision.status == "unknown"


def test_falsify_undated_null_session_declared_type_is_ambiguous_not_dropped(tmp_path):
    """BLOCKER 1 (round 8, 2026-08-28), the reviewer's exact repro: round 6
    only fixed the SESSION-MATCH half of an unparsable-ts row -- a
    null-session row whose `ts` cannot be parsed but whose `agent_type` IS
    one this cycle declared used to be silently dropped entirely (not
    ambiguous, not excluded, invisible in every field), when it is exactly
    the unjoined-row population the AMBIGUOUS bucket exists for. Reproduced
    with the reviewer's own numbers: a $0.015 own-session row plus a
    garbage-ts, null-session, declared-type $1,800 row -- must force
    unknown, never confidently report $0.015."""
    ledger = tmp_path / "spend.jsonl"
    good_row = _simple_row(session="sess-A")
    good_row["tokens"] = {"input": 5_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # sonnet 5K in -- a tiny row
    hidden_row = _simple_row(session=None, ts="garbage", agent_type="implement", model="claude-opus-5")
    hidden_row["tokens"] = {
        "input": 0,
        "output": 24_000_000,
        "cache_read": 0,
        "cache_creation": 0,
    }  # opus: 24M out @ $25/MTok == $600.00
    _write_ledger(ledger, [good_row, hidden_row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "ambiguous-unjoined-rows-in-window"
    assert attr.ambiguous_rows == 1
    assert attr.spent_usd is None

    # CONTROL: the identical hidden row with a PARSABLE ts already forces
    # unknown via the pre-existing (correct) ambiguous path -- confirms the
    # bug was specific to the unparsable-ts branch, not the type check.
    hidden_row_parsable = dict(hidden_row)
    hidden_row_parsable["ts"] = "2026-08-28T10:05:00Z"
    _write_ledger(ledger, [good_row, hidden_row_parsable])
    control = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert control.status == "unknown"
    assert control.reason == "ambiguous-unjoined-rows-in-window"


def test_undated_null_session_undeclared_type_still_correctly_dropped(tmp_path):
    """BLOCKER 1's paired negative case: an undated, null-session row whose
    agent_type this cycle never declared must still be silently dropped,
    exactly as before -- this fix only widens the ambiguous check to cover
    the null-session+undated combination, it must never turn every
    unparsable-ts row into ambiguity regardless of type."""
    ledger = tmp_path / "spend.jsonl"
    good_row = _simple_row(session="sess-A")
    undeclared_row = _simple_row(session=None, ts="garbage", agent_type="trade-plumbing")
    _write_ledger(ledger, [good_row, undeclared_row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.ambiguous_rows == 0
    assert attr.excluded_rows == 0  # dropped silently, exactly like an out-of-window row
    assert attr.undated_matched_rows == 0


def test_falsify_agent_id_correlated_unjoined_row_is_never_excluded(tmp_path):
    """BLOCKER 4 (round 8, 2026-08-28), the reviewer's exact repro: an
    unjoined (session: null) row sharing a real `agent_id` with a row
    already MATCHED to this cycle by session must never be classified
    independently by its own (undeclared placeholder) agent_type -- it is
    identity-correlated proof of the SAME agent's spend and must feed the
    existing duplicate-agent_id collapse/pricing machinery. row A: $3.00,
    matched by session. row B: agent_id-correlated, session None,
    agent_type "workflow-subagent" (undeclared), tool_use_id None, opus 24M
    output tokens == $1,800.00 -- the reap. Before the fix this reported
    `known, spent_usd=3.00, excluded=1` (the $1,800 hidden); after the fix
    the collapse correctly prices the larger (real) reading."""
    ledger = tmp_path / "spend.jsonl"
    row_a = _simple_row(session="sess-A", agent_id="AX", agent_type="implement", tool_use_id="tuA")
    row_a["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    row_b = _simple_row(
        session=None,
        agent_id="AX",
        agent_type="workflow-subagent",  # undeclared placeholder -- the exact bug
        tool_use_id=None,
        model="claude-opus-5",
    )
    row_b["tokens"] = {"input": 0, "output": 24_000_000, "cache_read": 0, "cache_creation": 0}  # opus 24M out
    _write_ledger(ledger, [row_a, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_usd("opus", output=24_000_000))  # the real, larger reading -- never the anchor alone
    assert attr.excluded_rows == 0  # the reap is never excluded as unrelated noise
    assert attr.collapsed_duplicate_rows == 1


def test_falsify_agent_id_correlated_row_with_unpriceable_model_forces_unknown(tmp_path):
    """The real, measured live-ledger shape (44/44 duplicate-agent_id
    groups, 2026-08-28): the correlated reap's `model` is `null`
    (unpriceable), not a priceable family. Before the fix this row was
    independently EXCLUDED (agent_type undeclared) and the confident $3.00
    from row A alone looked like the whole cycle's spend. After the fix,
    the correlated row is folded into the SAME collapse group as row A;
    since it cannot be priced, the whole attribution must force unknown --
    never silently report the smaller, priceable sibling's total as if the
    unpriceable reap did not exist. Deliberately uses an UNDECLARED
    agent_type on the correlated row (matching the exclusion-as-noise bug
    exactly, distinct from the pre-existing ambiguous path a DECLARED type
    would already hit): before this fix the correlated row was
    independently EXCLUDED and the attribution reported a confident
    `known`, $3.00 -- never `unpriced-model-in-window`."""
    ledger = tmp_path / "spend.jsonl"
    row_a = _simple_row(session="sess-A", agent_id="AX", agent_type="implement", tool_use_id="tuA")
    row_a["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    row_b = _simple_row(
        session=None,
        agent_id="AX",
        agent_type="engine-architect",  # undeclared -- not in KNOWN_TYPES
        tool_use_id=None,
        model=None,  # unpriceable -- matches the real live shape exactly
    )
    row_b["tokens"] = {"input": 236, "output": 49_748, "cache_read": 16_655_941, "cache_creation": 869_844}
    _write_ledger(ledger, [row_a, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "unpriced-model-in-window"


# ---------------------------------------------------------------------------
# Round 10 (2026-08-28): the correlated-row window exemption was unbounded
# in BOTH directions when the "later reap" rationale only ever justifies
# ONE direction (BLOCKER 1); 4 sub-clauses of round 8's own correlation
# code had zero test coverage (BLOCKER 2); and the duplicate-agent_id
# collapse could silently discard a genuinely-ambiguous correlated row
# instead of forcing unknown (BLOCKER 3).
# ---------------------------------------------------------------------------


def test_falsify_correlated_row_before_window_is_not_charged_to_this_cycle(tmp_path):
    """BLOCKER 1 (round 10, 2026-08-28), the reviewer's exact Repro A: an
    in-window anchor row ($15) plus a correlated row dated YESTERDAY
    ($150) must NOT charge the $150 to this cycle -- that row predates
    the window entirely, it is not a later reap of in-window work. Before
    the fix this reported known/$150 (the whole point of the correlation
    exemption was misapplied to the wrong direction); after the fix only
    the $15 in-window anchor counts."""
    ledger = tmp_path / "spend.jsonl"
    row_a = _simple_row(session="sess-A", agent_id="AX", tool_use_id="tuA")
    row_a["tokens"] = {"input": 5_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 5M in == _BIG_ANCHOR_USD
    row_b = _simple_row(
        session=None,
        agent_id="AX",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-27T10:00:00Z",  # YESTERDAY -- before cycle_start (08-28T09:00)
    )
    row_b["tokens"] = {"input": 50_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 50M in == _BIG_REAP_USD
    _write_ledger(ledger, [row_a, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_BIG_ANCHOR_USD)  # never the 50M-input row -- that row predates the window
    assert attr.matched_rows == 1
    assert attr.collapsed_duplicate_rows == 0


def test_falsify_correlated_row_after_window_still_charged_the_later_reap_case(tmp_path):
    """Paired non-regression + BLOCKER 2 mutant-1 kill: a correlated row
    dated AFTER cycle_end (a genuinely LATER reap of in-window work) must
    still be included and, per the existing duplicate-agent_id collapse,
    win on dollar value if it is the larger reading -- the ONE direction
    the exemption's own rationale actually covers. Deleting "and not
    is_agent_id_correlated" from the (now two-part) window check would
    wrongly drop this row on window grounds; asserting the LARGER,
    later-dated reading is the one actually priced kills that mutation."""
    ledger = tmp_path / "spend.jsonl"
    row_a = _simple_row(session="sess-A", agent_id="AY", tool_use_id="tuA2")
    row_a["tokens"] = {"input": 5_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 5M in == _BIG_ANCHOR_USD
    row_b = _simple_row(
        session=None,
        agent_id="AY",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T13:00:00Z",  # AFTER cycle_end (12:00) -- the later-reap case
    )
    row_b["tokens"] = {"input": 50_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 50M in == _BIG_REAP_USD
    _write_ledger(ledger, [row_a, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_BIG_REAP_USD)  # the later, larger reap reading wins the collapse
    assert attr.matched_rows == 2
    assert attr.collapsed_duplicate_rows == 1


def test_falsify_both_anchor_and_correlated_row_entirely_outside_window_is_unknown(tmp_path):
    """BLOCKER 1 (round 10, 2026-08-28), the reviewer's exact Repro B:
    neither the anchor (a direct session match, dated BEFORE cycle_start)
    nor the correlated row (also dated BEFORE cycle_start) is actually
    in-window. Before the fix this reported known/$60.00, matched_rows=1
    for a window with ZERO contributing rows -- the correlated row was
    exempted from the window check unconditionally, in both directions.
    After the fix, both rows are correctly dropped and zero matched rows
    with no dispatch count asserted forces unknown, exactly as it already
    does for a lone non-correlated row."""
    ledger = tmp_path / "spend.jsonl"
    anchor = _simple_row(session="sess-A", agent_id="AZ", tool_use_id="tuAZ", ts="2026-08-27T08:00:00Z")
    correlated = _simple_row(
        session=None,
        agent_id="AZ",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-27T09:00:00Z",  # also before cycle_start -- not a later reap
    )
    correlated["tokens"] = {"input": 20_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 20M in
    _write_ledger(ledger, [anchor, correlated])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "no-matched-rows-and-no-dispatch-count-asserted"
    assert attr.matched_rows == 0


def test_falsify_session_matched_agent_ids_includes_undated_anchor_rows(tmp_path):
    """BLOCKER 2 (round 10, 2026-08-28) mutant-2 kill: `_session_matched_
    agent_ids()` must register an agent_id from a directly-session-matched
    row even when THAT row's own timestamp is unparsable -- it is a pure
    identity fact ("session X dispatched agent_id Y"), independent of
    dateness (module docstring). The undated anchor forces the overall
    attribution to unknown via `undated_matched_rows` regardless -- but
    the correlated row (session None, undeclared agent_type, dated,
    in-window) must still land in `matched` via correlation, not be
    silently reclassified as excluded. Restricting the anchor lookup to
    only DATED rows (the mutant) drops this agent_id from
    `anchor_agent_ids` entirely, so the correlated row is classified
    independently instead -- observable via `matched_rows` dropping from
    1 to 0."""
    ledger = tmp_path / "spend.jsonl"
    anchor = _simple_row(session="sess-A", agent_id="X", ts="not-a-timestamp")
    row_b = _simple_row(session=None, agent_id="X", agent_type="engine-architect")  # undeclared
    _write_ledger(ledger, [anchor, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "matched-row-with-unparsable-ts"
    assert attr.matched_rows == 1  # row_b correlated in, despite the anchor's own ts being unparsable


def test_falsify_correlation_requires_null_session_never_pulls_in_other_concrete_session(tmp_path):
    """BLOCKER 2 (round 10, 2026-08-28) mutant-3 kill: agent_id correlation
    must require the candidate row's OWN `session` to be null -- a row
    belonging to some OTHER, concrete, non-null session sharing the same
    agent_id is never pulled into this cycle by agent_id alone (this
    guard is the module's ONLY defense against agent_id reuse across
    sessions). Replacing "row_session is None" with "True" would let
    sess-OTHER's own real $150.00 dispatch get attributed to sess-A
    merely for sharing an agent_id -- asserting the total stays at the
    anchor's own $3.00 and the other-session row is EXCLUDED kills that
    mutation."""
    ledger = tmp_path / "spend.jsonl"
    anchor = _simple_row(session="sess-A", agent_id="X", tool_use_id=None)
    anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    other_session_row = _simple_row(session="sess-OTHER", agent_id="X", tool_use_id=None)
    other_session_row["tokens"] = {
        "input": 0,
        "output": 10_000_000,
        "cache_read": 0,
        "cache_creation": 0,
    }  # sonnet 10M out
    _write_ledger(ledger, [anchor, other_session_row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # sess-OTHER's real dispatch must never be pulled in
    assert attr.matched_rows == 1
    assert attr.excluded_rows == 1


def test_falsify_correlated_row_with_unparsable_ts_never_silently_dropped(tmp_path):
    """BLOCKER 2 (round 10, 2026-08-28) mutant-4 kill: a correlated row
    whose own `ts` cannot be parsed must land in `undated_matched_rows`
    (forcing unknown) -- never silently dropped with no bookkeeping at
    all. A silent drop here would let a $500.00 correlated reap of unknown
    timing vanish completely, leaving a confident (and wrong) known/$3.00
    verdict from the anchor alone."""
    ledger = tmp_path / "spend.jsonl"
    anchor = _simple_row(session="sess-A", agent_id="AW", tool_use_id="tuAW")
    anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    correlated = _simple_row(
        session=None,
        agent_id="AW",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="not-a-real-timestamp",
    )
    correlated["tokens"] = {"input": 0, "output": 100_000_000, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [anchor, correlated])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "matched-row-with-unparsable-ts"
    assert attr.undated_matched_rows == 1
    assert attr.matched_rows == 1  # only the anchor -- the correlated row is counted separately


def test_falsify_later_cycle_anchor_and_reap_not_charged_to_earlier_cycle(tmp_path):
    """BLOCKER 1 (round 12, 2026-08-28), the reviewer's exact repro: the
    AFTER-window twin of
    `test_falsify_both_anchor_and_correlated_row_entirely_outside_window_is_unknown`.
    A same session id (`sess-A`) spans more than one bounded cycle. This
    cycle's own window is `WINDOW` (09:00-12:00). A LATER cycle's own
    direct dispatch (`agent_id="G2"`, dated 16:00, after THIS cycle's own
    end) is correctly dropped from `matched` on window grounds alone -- but
    (pre-fix) it still seeded the window-independent `anchor_agent_ids`
    with `G2`. An unjoined LATER reap of that SAME agent_id (dated 16:30,
    also after THIS cycle's end) was then wrongly exempted from the window
    check purely because `G2` was 'anchored', charging a LATER cycle's own
    $30.00 reap onto THIS (earlier) cycle. Before the fix this reported
    known/$33.00, matched_rows=2 for a cycle with only $3.00 of real
    in-window spend -- an 11x over-report with zero ambiguity signal. After
    the fix, both the later cycle's own anchor row and its reap are
    correctly excluded from THIS cycle's attribution."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    later_cycle_anchor = _simple_row(
        session="sess-A",
        agent_id="G2",
        tool_use_id="tuG2",
        ts="2026-08-28T16:00:00Z",  # AFTER this cycle's own end (12:00) -- a LATER cycle's own dispatch
    )
    later_cycle_anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    later_cycle_reap = _simple_row(
        session=None,
        agent_id="G2",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T16:30:00Z",  # also after this cycle's own end
    )
    later_cycle_reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, later_cycle_anchor, later_cycle_reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # never anchor+reap -- the later cycle's reap is not this cycle's
    assert attr.matched_rows == 1


def test_falsify_earlier_cycle_anchor_and_later_after_window_reap_not_charged(tmp_path):
    """BLOCKER 1 (round 12, 2026-08-28): the 4th cell of the {anchor
    in/out-of-window} x {correlated-row before/after THIS cycle's window}
    combination space -- an EARLIER cycle's own anchor (dated BEFORE this
    cycle's own start) paired with a correlated reap dated AFTER this
    cycle's own end. Neither the anchor's own before-window dating nor a
    naive 'is it after end_dt' check alone is enough here: the anchor must
    be excluded from the restricted this-cycle anchor set for being
    OUTSIDE THIS CYCLE'S WINDOW IN EITHER DIRECTION, not just the
    after-window direction the reviewer's own repro exercises."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    earlier_cycle_anchor = _simple_row(
        session="sess-A",
        agent_id="G3",
        tool_use_id="tuG3",
        ts="2026-08-28T07:00:00Z",  # BEFORE this cycle's own start (09:00) -- an EARLIER cycle's dispatch
    )
    earlier_cycle_anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    stray_reap = _simple_row(
        session=None,
        agent_id="G3",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T13:00:00Z",  # AFTER this cycle's own end (12:00)
    )
    stray_reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, earlier_cycle_anchor, stray_reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)
    assert attr.matched_rows == 1


def test_falsify_earlier_cycle_anchor_and_in_window_reap_not_charged(tmp_path):
    """BLOCKER 1 (round 14, 2026-08-28), the reviewer's exact CASE 1/CASE 2
    repro: round 12's own fix gated the restricted this-cycle anchor-set
    check ONLY inside the after-window (`row_dt > end_dt`) branch, leaving
    the IN-WINDOW correlated-row case completely ungated -- an 11x
    over-report survives via the identical root cause, one grid cell over.
    An EARLIER cycle's own anchor (`G3`, dated 07:00, BEFORE this cycle's
    own start 09:00) has an unjoined reap dated 10:30 -- INSIDE this
    cycle's own window (09:00-12:00), not after it. A stopped-unjoined
    reap row's timestamp records WHEN THE REAP RAN, not when the
    underlying work happened (module docstring) -- so this is a live,
    reachable shape, not a constructed edge case: an earlier cycle's
    agent, reaped inside a LATER cycle's own window.

    `expected_dispatch_count=None` deliberately (BLOCKER 2's own warning):
    a naive single expected-count value across every cell of this space
    can mask the dollar-value leak behind an unrelated `count-mismatch`
    verdict in some cells; omitting the assertion here isolates the pure
    attribution defect this test exists to catch. Pre-fix this reported
    known/$33.00 (matched_rows=2); after the fix it must report the real
    $3.00 in-window spend only."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    earlier_cycle_anchor = _simple_row(
        session="sess-A",
        agent_id="G3",
        tool_use_id="tuG3",
        ts="2026-08-28T07:00:00Z",  # BEFORE this cycle's own start (09:00) -- an EARLIER cycle's dispatch
    )
    earlier_cycle_anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    in_window_reap = _simple_row(
        session=None,
        agent_id="G3",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T10:30:00Z",  # INSIDE this cycle's own window -- the previously-ungated cell
    )
    in_window_reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, earlier_cycle_anchor, in_window_reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # never anchor+reap -- the earlier cycle's reap is not this cycle's
    assert attr.matched_rows == 1


def test_falsify_earlier_cycle_reap_alone_in_window_stays_unknown_not_a_confident_known(tmp_path):
    """BLOCKER 1 (round 14, 2026-08-28), the reviewer's CASE 2 repro -- the
    MORE dangerous half of the same bug: with no real in-window dispatch
    of its own this cycle, an earlier cycle's stray in-window reap
    (`$30.00`) used to be the ONLY matched row, so `matched_rows` was
    reported HONESTLY as 1 -- identical to what a genuine single real
    dispatch would look like. That honest count is exactly what let this
    leak sail straight past the `expected_dispatch_count` safety net
    undetected pre-fix: `expected_dispatch_count=1` matched `matched_rows
    == 1` with no discrepancy to catch, and the cycle reported a
    confident known/$30.00 for spend that was never its own. After the
    fix, the stray reap is excluded (its anchor is outside this cycle's
    own window), zero rows remain matched, and the module correctly
    refuses to guess -- `unknown`, never a confident `known/$0.00` either."""
    ledger = tmp_path / "spend.jsonl"
    earlier_cycle_anchor = _simple_row(
        session="sess-A",
        agent_id="G3",
        tool_use_id="tuG3",
        ts="2026-08-28T07:00:00Z",  # BEFORE this cycle's own start (09:00)
    )
    earlier_cycle_anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    in_window_reap = _simple_row(
        session=None,
        agent_id="G3",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T10:30:00Z",  # INSIDE this cycle's own window
    )
    in_window_reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [earlier_cycle_anchor, in_window_reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,  # the caller's honest belief: 1 real dispatch this cycle
        **WINDOW,
    )
    assert attr.status == "unknown"  # never a confident known/$30.00, and never a confident known/$0.00 either
    assert attr.spent_usd is None


def test_falsify_cli_status_earlier_cycle_anchor_and_in_window_reap_not_charged(tmp_path):
    """BLOCKER 1 (round 14, 2026-08-28), the reviewer's CASE 5 repro: the
    identical leak reproduces through the real CLI `status` command, not
    only the library entry point -- confirms the fix holds through the
    full argv-parsing path a real dispatcher actually calls.

    REWRITTEN (round 18, 2026-08-28), BLOCKER 1's OWN follow-up fix: the
    restricted-anchor rejection this test exercises (the reap's `agent_id`
    is correlated only via an anchor OUTSIDE this cycle's own window) used
    to `continue` unconditionally, consuming the row with ZERO
    bookkeeping. That was harmless for THIS test's own $3.00-vs-$33.00
    question (the row was never counted toward spend either way) but
    WRONG in general -- confirmed live-reachable against the real
    ~/.claude/.agent_budget/spend.jsonl (3 real rows affected): a
    rejected-correlation row is not PROVEN to be someone else's spend, it
    is exactly the unjoined population the AMBIGUOUS bucket exists for,
    and must now fall through to that normal classification tail instead
    of vanishing. The reap row here now uses a DECLARED `agent_type`
    ("implement", one `KNOWN_TYPES` recognizes) instead of the originally
    undeclared "workflow-subagent" specifically so this test can OBSERVE
    that fall-through -- an undeclared type lands in EXCLUDED either way
    and would never distinguish the two behaviors. The verdict is now
    `unknown`/`ambiguous-unjoined-rows-in-window`, never a confident
    known/$3.00 (nor a confident known/$0.00 -- this module never guesses
    either direction). Per this repo's CLAUDE.md §6 required-pairings
    rule, the paired POSITIVE case directly below locks the opposite
    direction: the identical reap, correlated via a genuinely IN-WINDOW
    anchor, must still report a confident known/$33.00, unaffected."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    earlier_cycle_anchor = _simple_row(
        session="sess-A", agent_id="G3", tool_use_id="tuG3", ts="2026-08-28T07:00:00Z"
    )
    earlier_cycle_anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    in_window_reap = _simple_row(
        session=None, agent_id="G3", agent_type="implement", tool_use_id=None, ts="2026-08-28T10:30:00Z"
    )
    in_window_reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [real_row, earlier_cycle_anchor, in_window_reap])

    argv = ["status"] + _argv_common(ledger)
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["status"] == "unknown"  # BLOCKER 1 (round 18): never a confident known/$3.00 either
    assert payload["reason"] == "ambiguous-unjoined-rows-in-window"
    assert payload["spent_usd"] is None


def test_falsify_cli_status_in_window_anchor_reap_still_charged(tmp_path):
    """Paired POSITIVE case for
    `test_falsify_cli_status_earlier_cycle_anchor_and_in_window_reap_not_
    charged` directly above (BLOCKER 1, round 18, 2026-08-28, per this
    repo's CLAUDE.md §6 required-pairings rule): the SAME reap shape,
    except its anchor genuinely belongs to THIS cycle's own window -- the
    reap must still report a confident known/$33.00, completely
    unaffected by round 18's fall-through fix (which only changes the
    fate of a REJECTED correlation, never an accepted one)."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    in_window_anchor = _simple_row(
        session="sess-A", agent_id="G3", tool_use_id="tuG3", ts="2026-08-28T10:00:00Z"
    )
    in_window_anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0 -- isolates reap
    reap = _simple_row(
        session=None, agent_id="G3", agent_type="implement", tool_use_id=None, ts="2026-08-28T10:30:00Z"
    )
    reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, in_window_anchor, reap])

    argv = ["status"] + _argv_common(ledger)
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["status"] == "known"
    assert payload["spent_usd"] == pytest.approx(_ANCHOR_USD + _REAP_USD)  # real + $0 anchor + reap
    assert payload["matched_rows"] == 3


@pytest.mark.parametrize("anchor_pos,reap_pos", list(itertools.product(_GRID_POSITIONS, _GRID_POSITIONS)))
def test_falsify_correlated_row_anchor_position_grid_4x4(tmp_path, anchor_pos, reap_pos):
    """BLOCKER 2 (round 14, 2026-08-28): the correlated-row combination
    space was enumerated as a 2x2 grid ({anchor in/out-of-window} x
    {correlated-row before/after window}) when it is actually 4x4 -- a
    correlated row's own window position, exactly like its anchor's, is
    one of FOUR values: before / IN / after / undated. The "IN" column
    was never written down anywhere before this test, so it was never
    tested, so BLOCKER 1's round-14 in-window leak shipped straight
    through review undetected. This is the SAME kind of enumeration gap
    this module has hit multiple times before.

    Sweeps all 16 cells and asserts, per cell, exactly the correct or
    documented behavior:

    - a correlated row dated BEFORE this cycle's own start is dropped
      UNCONDITIONALLY (round 10 ruling), regardless of its anchor's own
      position -- never evidence for this cycle.
    - an UNDATED anchor OR an UNDATED correlated row forces the whole
      verdict to `unknown` (module docstring's ROUND 6/8 sections):
      genuine spend of unknown timing is never silently dropped nor
      silently included, no matter what the OTHER axis's position is.
    - otherwise (a correlated row dated IN or AFTER this cycle's own
      window, with a dated, non-undated anchor), the row is included
      ONLY when its own anchor is genuinely dated INSIDE this cycle's own
      [start_dt, end_dt] window -- an anchor dated before or after this
      cycle's own window means the correlated row belongs to a DIFFERENT
      cycle sharing the same long-lived session id, and must be excluded
      regardless of the correlated row's OWN window position. This is
      BLOCKER 1's fix: round 12 enforced this only in the AFTER column;
      this test is what would have caught the gap.

    `expected_dispatch_count=None` throughout (BLOCKER 2's own warning
    about a single expected-count value masking the leak behind an
    unrelated `count-mismatch` verdict in some cells) -- the anchor row
    itself carries $0.00 tokens so its own inclusion (only possible when
    `anchor_pos == "in"`, where it is a genuine direct session match) never
    changes the DOLLAR total, keeping every dollar-value assertion below
    unambiguously about the REAP row's inclusion/exclusion alone.
    """
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T10:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD

    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuG3", ts=_GRID_TS[anchor_pos])
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- see docstring

    reap = _simple_row(
        session=None,
        agent_id="G3",
        agent_type="workflow-subagent",  # undeclared -- must never gate a correlated row
        tool_use_id=None,
        ts=_GRID_TS[reap_pos],
    )
    reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )

    if anchor_pos == "undated" or reap_pos == "undated":
        assert attr.status == "unknown"
        assert attr.reason == "matched-row-with-unparsable-ts"
        return

    if reap_pos == "before":
        included = False
    else:
        # reap_pos in {"in", "after"}: included only when the anchor
        # itself is genuinely dated inside THIS cycle's own window.
        included = anchor_pos == "in"

    assert attr.status == "known"
    expected_total = _ANCHOR_USD + (_REAP_USD if included else 0.0)
    assert attr.spent_usd == pytest.approx(expected_total)

    expected_matched_rows = 1  # real_row always lands in matched
    if anchor_pos == "in":
        expected_matched_rows += 1  # the anchor itself is a genuine direct in-window match
    if included:
        expected_matched_rows += 1  # the reap row
    assert attr.matched_rows == expected_matched_rows


# BLOCKER 1 (round 16, 2026-08-28): the real combination space a reap row
# occupies is not just {anchor position} x {reap position} (the 4x4 grid
# above) -- there is a THIRD, previously-untested axis: the reap row's OWN
# `session` classification. A reap's `session` field can be (a) null, (b) a
# stale/duplicate copy of THIS cycle's own session id, or (c) some OTHER,
# genuinely different, non-null session id. Per the module docstring's
# ROUND 16 CORRECTION / SCOPING sections, this axis matters DIFFERENTLY
# depending on the reap's own window position: for a reap dated AFTER this
# cycle's own end, all three session kinds must be included IDENTICALLY
# (a background reap's own session field is an artifact of when/how it
# ran, not a live ownership claim); for a reap dated INSIDE this cycle's
# own window, only "null" and "this cycle's own session" are included --
# "some other, genuinely different session" stays a live, contemporaneous
# declaration by that OTHER session and must NOT be merged in, exactly
# like `test_falsify_correlation_requires_null_session_never_pulls_in_
# other_concrete_session`'s own in-window guard (round 10), which this
# fix must NOT reopen. `_REAP_SESSION_KINDS` builds that third dimension's
# own session value for a fixed `session_id="sess-A"`.
_REAP_SESSION_KINDS = ("null", "this_cycle", "other")


def _reap_session_value(kind: str) -> str | None:
    return {"null": None, "this_cycle": "sess-A", "other": "sess-OTHER"}[kind]


@pytest.mark.parametrize(
    "reap_pos,session_kind",
    list(itertools.product(("before", "in", "after"), _REAP_SESSION_KINDS)),
)
def test_falsify_reap_session_classification_grid(tmp_path, reap_pos, session_kind):
    """BLOCKER 1 (round 16, 2026-08-28), the reviewer's exact repro plus its
    full 3x3 extension against an anchor genuinely proven INSIDE this
    cycle's own window (`G3`, dated 10:00):

    - `reap_pos="before"`: excluded UNCONDITIONALLY (round 10 ruling),
      regardless of `session_kind` -- never evidence for this cycle.
    - `reap_pos="after"`: included regardless of `session_kind` -- the
      reviewer's exact repro. Before the round-16 fix, `session_kind`
      "this_cycle" and "other" here silently vanished from EVERY count
      (not matched, ambiguous, excluded, unpriced, or undated) -- a
      5x-class UNDER-report, the dangerous direction for a spend-ceiling
      guard -- while "null" (already covered by the round-14 4x4 grid
      above) correctly reported the reap's spend.
    - `reap_pos="in"`: included for "null" (pre-existing agent_id
      correlation) and "this_cycle" (a genuine second direct session
      match), but EXCLUDED for "other" -- an IN-WINDOW row with a real,
      DIFFERENT session is a live, contemporaneous declaration by that
      OTHER session, not evidence of a reap, and must stay excluded
      exactly like round 10's own mutation-tested guard. This is the cell
      that proves round 16's widening is precisely scoped to AFTER this
      cycle's own window, not a blanket "any shared agent_id" rule.
    """
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T10:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD

    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuG3", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates the reap

    reap = _simple_row(
        session=_reap_session_value(session_kind),
        agent_id="G3",
        # A KNOWN agent_type on purpose (unlike the 4x4 grid test's
        # deliberately-undeclared "workflow-subagent"): at `reap_pos="in"`
        # + `session_kind="this_cycle"` this row is a genuine, NOT
        # agent_id-correlated, in-window direct session match (its own
        # `session` literally equals `session_id`) -- so the unexpected-
        # agent-type safety net legitimately still applies to it, same as
        # any other direct match, and a deliberately-undeclared type there
        # would force `unknown` for a reason UNRELATED to this test's own
        # session-classification axis. Using a known type here isolates
        # that axis cleanly; the separate "undeclared type must never gate
        # a correlated/exempted row" property is already covered by the
        # 4x4 grid test above.
        agent_type="implement",
        tool_use_id=None,
        ts=_GRID_TS[reap_pos],
    )
    reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )

    if reap_pos == "before":
        included = False
    elif reap_pos == "after":
        included = True  # round 16's own fix: uniform regardless of session_kind
    else:  # reap_pos == "in"
        included = session_kind in ("null", "this_cycle")  # "other" stays excluded (round 10 guard)

    assert attr.status == "known"
    expected_total = _ANCHOR_USD + (_REAP_USD if included else 0.0)
    assert attr.spent_usd == pytest.approx(expected_total)
    # real_row + anchor always match; the reap adds a 3rd when included.
    assert attr.matched_rows == (3 if included else 2)


@pytest.mark.parametrize("session_kind", _REAP_SESSION_KINDS)
def test_falsify_later_cycle_reap_excluded_regardless_of_own_session_value(tmp_path, session_kind):
    """BLOCKER 1 (round 16, 2026-08-28): the negative control proving the
    round-16 widening is PRECISE, not a re-opening of the round-14 fix
    (`test_falsify_later_cycle_anchor_and_reap_not_charged_to_earlier_cycle`
    above). Here the anchor (`G2`) is dated AFTER this cycle's own end
    (16:00) -- a LATER cycle's own dispatch, never proven to be inside THIS
    cycle's own window -- so a reap sharing `G2`'s agent_id must stay
    EXCLUDED, regardless of the reap's own `session` field (null, a stale
    copy of this cycle's own session, or some genuinely other session).
    Must report the same known/$3.00, matched_rows=1 in all 3 variants,
    identical to the pre-existing round-14 regression test's own
    (session_kind="null"-equivalent) result."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    later_cycle_anchor = _simple_row(
        session="sess-A",
        agent_id="G2",
        tool_use_id="tuG2",
        ts="2026-08-28T16:00:00Z",  # AFTER this cycle's own end (12:00) -- a LATER cycle's own dispatch
    )
    later_cycle_anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    later_cycle_reap = _simple_row(
        session=_reap_session_value(session_kind),
        agent_id="G2",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T16:30:00Z",  # also after this cycle's own end
    )
    later_cycle_reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, later_cycle_anchor, later_cycle_reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # never anchor+reap -- the later cycle's reap is not this cycle's
    assert attr.matched_rows == 1


def test_falsify_after_window_direct_match_duplicate_never_forces_unknown(tmp_path):
    """BLOCKER 2 (round 18, 2026-08-28), the reviewer's exact repro: a
    genuine after-window DIRECT SESSION MATCH (`row["session"] ==
    session_id` literally, dated after `cycle_end`, surviving the window
    check only via the after-window agent_id exemption) used to ALSO get
    flagged `is_correlated_for_bookkeeping=True` by a bare `row_dt >
    end_dt` term in that flag's formula -- reversing round 10's own
    explicit carve-out that a direct-session-match row's duplicates are
    NEVER ambiguous (both readings are already proven to be this
    session's own). When `_collapse_duplicate_agent_id_rows()` then drops
    this row (outbid by a larger-value same-agent_id sibling), the bug's
    erroneous correlated flag makes it look like a DROPPED,
    agent-id-correlated row with a declared type -- forcing a spurious
    `unknown` for spend that should have been a confident `known`.

    `G3` group: `anchor` ($30.00, the genuine winner, dated in-window) and
    `direct_match` ($3.00, a real, LITERAL session match on `G3`, dated
    AFTER cycle_end, surviving only via the after-window agent_id
    exemption) -- collapse drops `direct_match` (outbid), and since it IS
    a real, literal session match (not merely agent_id-correlated), its
    drop must never be treated as ambiguous, regardless of its own window
    position. Expected: known/$33.00 (`real_row` $3 + `anchor` $30),
    never `unknown`."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuG3", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD -- winner
    direct_match = _simple_row(
        session="sess-A",  # a REAL, literal session match -- never merely agent_id-correlated
        agent_id="G3",
        agent_type="implement",  # a DECLARED type -- triggers the bug's spurious ambiguity check
        tool_use_id=None,
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end -- survives only via the after-window exemption
    )
    direct_match["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD -- loser
    _write_ledger(ledger, [real_row, anchor, direct_match])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"  # BLOCKER 2 (round 18): never a spurious `unknown`
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD + _REAP_USD)  # real + anchor (the collapse's own winner)
    assert attr.matched_rows == 3  # real_row + anchor + direct_match (collapse drops one AFTER counting matched)


@pytest.mark.parametrize("candidate_tool_use_id", ["tuANCHOR", None])
def test_falsify_after_window_compatible_tool_use_id_still_included(tmp_path, candidate_tool_use_id):
    """Paired POSITIVE case for
    `test_falsify_after_window_independent_dispatch_never_summed_via_
    tool_use_id_conflict` below (BLOCKER 3, round 18, 2026-08-28, per this
    repo's CLAUDE.md §6 required-pairings rule): a candidate row sharing
    `G3`'s agent_id, dated after cycle_end, whose OWN `tool_use_id` is
    either genuinely the SAME as the in-window anchor's (`"tuANCHOR"`) or
    null (matches the shape a real `stopped-unjoined` reap row actually
    has) -- both COMPATIBLE with the anchor per
    `_collapse_duplicate_agent_id_rows()`'s own rule, and both must stay
    INCLUDED via `is_after_window_agent_id_match`, completely unaffected
    by round 18's new tool_use_id-compatibility gate."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuANCHOR", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates candidate
    candidate = _simple_row(
        session="sess-OTHER",  # a genuinely different, populated session -- round 16's own widening
        agent_id="G3",
        agent_type="implement",
        tool_use_id=candidate_tool_use_id,
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end
    )
    candidate["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, candidate])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD + _REAP_USD)  # real + $0 anchor + candidate -- still included
    assert attr.matched_rows == 3


def test_falsify_after_window_independent_dispatch_never_summed_via_tool_use_id_conflict(tmp_path):
    """BLOCKER 3 (round 18, 2026-08-28), the reviewer's exact axiom-conflict
    repro: `is_after_window_agent_id_match`'s round-16 "agent_id is unique
    per dispatch" channel used to pull in ANY row sharing an agent_id with
    an in-window anchor, dated after cycle_end -- regardless of that row's
    OWN `tool_use_id` -- directly contradicting
    `_collapse_duplicate_agent_id_rows()`'s own, stricter rule (2+
    DISTINCT non-null `tool_use_id`s on one `agent_id` proves 2+
    INDEPENDENT dispatches, summed separately, never treated as the same
    one). A candidate sharing `G3`'s agent_id but carrying a DIFFERENT,
    non-null `tool_use_id` than the in-window anchor's own is, by the
    collapse's own authoritative rule, proof of a genuinely SEPARATE
    dispatch that was never proven to belong to THIS cycle at all (its own
    `session` is a real, different, concrete session, "sess-OTHER") -- yet
    the old code pulled it into `matched` anyway (via agent_id alone) and
    then the collapse's own distinct-tool_use_id rule left it UNCOLLAPSED,
    silently SUMMING a foreign, independent dispatch's spend into this
    cycle's own confident total. Fixed: `is_after_window_agent_id_match`
    now defers to the SAME tool_use_id-compatibility rule the collapse
    uses, so a genuinely incompatible candidate like this one is never
    pulled in via this channel at all -- it is dropped by the shared
    after-window admission gate's own `continue` (`row_dt > end_dt and
    not is_after_window_exempt`) before ever reaching the tail's
    ambiguous/excluded classification lines, with ZERO bookkeeping
    (`excluded_rows` untouched, never landing in the EXCLUDED bucket) --
    exactly like the tail's own out-of-window `continue` for an
    unrelated row (see `cycle_budget.py`'s `correlation_rejected` NOTE).
    A live, different, non-null session was never evidence for this
    cycle either way. Expected: known/$3.00 (`real_row` only;
    the $0.00 anchor contributes nothing), never a confident known/$33.00
    that silently includes the foreign $30.00 dispatch."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuANCHOR", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates candidate
    independent_dispatch = _simple_row(
        session="sess-OTHER",  # a real, different, concrete session -- never proven to be this cycle's
        agent_id="G3",  # shares G3's agent_id -- the ONLY thing the old code checked
        agent_type="implement",
        tool_use_id="tuDIFFERENT",  # a DIFFERENT, non-null tool_use_id than the anchor's own "tuANCHOR"
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end
    )
    independent_dispatch["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, independent_dispatch])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # never anchor+reap -- the foreign dispatch is not this cycle's
    assert attr.matched_rows == 2  # real_row + anchor only -- the independent dispatch never joins `matched`


def test_falsify_after_window_null_session_independent_dispatch_never_summed_via_tool_use_id_conflict(
    tmp_path,
):
    """BLOCKER 1 (round 20, 2026-08-28), route (b) of the round-19 finding:
    round 18's tool_use_id-compatibility gate was wired into
    `is_after_window_agent_id_match`'s OWN predicate, which governs only
    the foreign-session route (route a; see
    `test_falsify_after_window_independent_dispatch_never_summed_via_
    tool_use_id_conflict` above). A NULL-session candidate reaching the
    SAME shared after-window admission via `is_agent_id_correlated` (route
    b) carrying a DIFFERENT, non-null `tool_use_id` than the in-window
    anchor's own is, by `_collapse_duplicate_agent_id_rows()`'s own
    authoritative rule, proof of a genuinely SEPARATE dispatch -- but the
    compatibility gate never governed this route before round 20, so it
    was still summed in whole. Expected: known/$3.00 (`real_row` only; the
    $0.00 anchor contributes nothing), never a confident known/$33.00 that
    silently includes the conflicting $30.00 reading."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuANCHOR", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates candidate
    candidate = _simple_row(
        session=None,  # route (b): null-session agent_id correlation, window-independent
        agent_id="G3",  # shares G3's agent_id
        agent_type="implement",
        tool_use_id="tuDIFFERENT",  # a DIFFERENT, non-null tool_use_id than the anchor's own "tuANCHOR"
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end
    )
    candidate["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, candidate])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # never anchor+reap -- the conflicting reading is not this cycle's
    assert attr.matched_rows == 2  # real_row + anchor only -- the conflicting candidate never joins `matched`


def test_falsify_after_window_direct_match_independent_dispatch_never_summed_via_tool_use_id_conflict(
    tmp_path,
):
    """BLOCKER 1 (round 20, 2026-08-28), route (c) of the round-19 finding:
    a REAL, LITERAL direct session match (`row["session"] == session_id`)
    dated after cycle_end, carrying a DIFFERENT, non-null `tool_use_id`
    than the in-window anchor's own -- proof, by the collapse's own rule,
    of an independent dispatch that merely happens to reuse `G3`'s
    agent_id (and, in this repro, a literal copy of this cycle's own
    session id). The compatibility gate never governed this route before
    round 20 either, so it was also still summed in whole. Expected:
    known/$3.00, matched_rows=2, exactly like routes (a)/(b)."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuANCHOR", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates candidate
    candidate = _simple_row(
        session="sess-A",  # route (c): a literal, genuine direct session match
        agent_id="G3",
        agent_type="implement",
        tool_use_id="tuDIFFERENT",  # a DIFFERENT, non-null tool_use_id than the anchor's own "tuANCHOR"
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end
    )
    candidate["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, candidate])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)  # never anchor+reap -- the conflicting reading is not this cycle's
    assert attr.matched_rows == 2  # real_row + anchor only -- the conflicting candidate never joins `matched`


def test_falsify_after_window_direct_match_undeclared_type_not_denied_round16_restored(tmp_path):
    """BLOCKER 2 (round 20, 2026-08-28): round 18's fix to the (then-single)
    `is_correlated_for_bookkeeping` flag (excluding `is_session_match`
    unconditionally) was correct for the duplicate-collapse ambiguity
    consumer it targeted, but it fed the SAME flag to a second, separate
    consumer -- the unexpected-agent-type safety net -- and silently
    reversed round 16's own documented intent there: a reap-shaped row
    with `session` literally equal to this cycle's own `session_id` (a
    stale copy of an in-window anchor's own session -- a REAL direct
    match, not merely agent_id-correlated), `agent_type` undeclared
    ("stopped-unjoined"), `tool_use_id` null, dated after `cycle_end`,
    surviving the window check only via the after-window agent_id
    exemption. Per round 16's own docstring ("The unexpected-agent-type
    safety net ... deliberately never applies to ... the after-window
    direct-match exemption"), this must be known/$33.00, never
    `unexpected-agent-type-for-session`."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuG3", ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates reap
    reap = _simple_row(
        session="sess-A",  # a stale copy of the in-window anchor's own session -- a REAL direct match
        agent_id="G3",
        agent_type="stopped-unjoined",  # undeclared -- must never trigger the safety net here
        tool_use_id=None,  # compatible with the anchor -- a genuine reap shape
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end -- survives only via the after-window exemption
    )
    reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"  # BLOCKER 2 (round 20): never a spurious `unknown`
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD + _REAP_USD)  # real + $0 anchor + reap
    assert attr.matched_rows == 3


def test_falsify_after_window_empty_anchor_tool_use_ids_admits_arbitrary_candidate(tmp_path):
    """Lower-severity item (a), round 19 review: `_this_cycle_anchor_tool_
    use_ids()`'s own documented carve-out -- an `agent_id` with ZERO
    non-null anchor `tool_use_id`s has nothing yet PROVEN to conflict
    with, so a single non-null candidate stays 'compatible' by
    construction (the collapse's own rule only fires at 2+ DISTINCT
    non-null values) -- was previously documented but never pinned by a
    test. This is INTENTIONAL, not a gap: an anchor that never wrote a
    non-null `tool_use_id` for `G3` cannot yet distinguish a genuine reap
    from an independent dispatch by this signal alone, so the module
    defers to its other safeguards (agent_id correlation itself) rather
    than refusing to price. Pinning this as the documented, intended
    behavior."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T11:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id=None, ts="2026-08-28T10:00:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates candidate
    candidate = _simple_row(
        session="sess-OTHER",  # a genuinely different, populated session -- round 16's own widening
        agent_id="G3",
        agent_type="implement",
        tool_use_id="tuARBITRARY",  # non-null, arbitrary -- the anchor has NO non-null tool_use_id to conflict with
        ts="2026-08-28T16:00:00Z",  # AFTER cycle_end
    )
    candidate["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, candidate])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD + _REAP_USD)  # real + $0 anchor + candidate -- intentionally admitted
    assert attr.matched_rows == 3


@pytest.mark.parametrize(
    "anchor_pos,reap_pos,reap_type_kind",
    list(itertools.product(_GRID_POSITIONS, _GRID_POSITIONS, ("declared", "undeclared"))),
)
def test_falsify_correlated_row_anchor_position_grid_4x4_by_declared_type(
    tmp_path, anchor_pos, reap_pos, reap_type_kind
):
    """Round-19 finding 5: `test_falsify_correlated_row_anchor_position_
    grid_4x4` above always used a deliberately-UNDECLARED reap agent_type
    ("workflow-subagent"), so every cell where round 18's BLOCKER 1
    `correlation_rejected` fall-through is exercised (`anchor_pos` in
    {"before", "after"} -- i.e. the anchor belongs to a DIFFERENT cycle --
    combined with a dated, non-undated `reap_pos`) always landed in the
    EXCLUDED half of the fall-through's own ambiguous/excluded tail, never
    the AMBIGUOUS half. This sibling re-sweeps the identical 16-cell grid
    with a DECLARED reap `agent_type` ("implement", a member of
    KNOWN_TYPES) added as a second, orthogonal axis, so the ambiguous
    branch of that same fall-through is actually exercised across the full
    position space too, not left permanently untested.

    A rejected row's own window position further splits this: only a
    `reap_pos == "in"` (in-window) rejected row ever reaches the tail's
    ambiguous/excluded classification lines at all -- a `reap_pos ==
    "after"` rejected row is dropped by the SAME tail's own `row_dt >
    end_dt` window filter first, with zero bookkeeping, regardless of its
    `agent_type` (see the round-20 correction to the module's own
    `correlation_rejected` fall-through comment)."""
    ledger = tmp_path / "spend.jsonl"
    real_row = _simple_row(session="sess-A", agent_id="G1", tool_use_id="tuG1", ts="2026-08-28T10:00:00Z")
    real_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD

    anchor = _simple_row(session="sess-A", agent_id="G3", tool_use_id="tuG3", ts=_GRID_TS[anchor_pos])
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00

    reap_agent_type = "implement" if reap_type_kind == "declared" else "workflow-subagent"
    reap = _simple_row(
        session=None,
        agent_id="G3",
        agent_type=reap_agent_type,
        tool_use_id=None,
        ts=_GRID_TS[reap_pos],
    )
    reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [real_row, anchor, reap])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )

    if anchor_pos == "undated" or reap_pos == "undated":
        assert attr.status == "unknown"
        assert attr.reason == "matched-row-with-unparsable-ts"
        return

    if reap_pos == "before":
        # A correlated row dated before this cycle's own start is dropped
        # unconditionally (round 10 ruling), regardless of type -- but the
        # anchor itself still separately matches when it is genuinely
        # in-window.
        assert attr.status == "known"
        assert attr.spent_usd == pytest.approx(_ANCHOR_USD)
        assert attr.matched_rows == (2 if anchor_pos == "in" else 1)
        return

    if anchor_pos == "in":
        # A genuinely correlated row is included regardless of its own
        # (possibly undeclared) agent_type -- the safety net never applies
        # to a correlated row.
        assert attr.status == "known"
        assert attr.spent_usd == pytest.approx(_ANCHOR_USD + _REAP_USD)
        assert attr.matched_rows == 3
        return

    # anchor_pos in {"before", "after"}: the anchor belongs to a DIFFERENT
    # cycle sharing the same long-lived session id -- `correlation_rejected`
    # fires and the reap falls through to the tail below.
    if reap_pos == "in" and reap_type_kind == "declared":
        # The ONLY cell where the fall-through's AMBIGUOUS branch is
        # actually reachable: in-window, rejected, and a declared type.
        assert attr.status == "unknown"
        assert attr.reason == "ambiguous-unjoined-rows-in-window"
        return

    # Either reap_pos == "after" (dropped by the tail's own window filter
    # before the ambiguous/excluded classification lines are ever reached,
    # regardless of type), or reap_pos == "in" with an undeclared type
    # (the tail's EXCLUDED branch).
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)
    assert attr.matched_rows == 1


def test_falsify_malformed_list_agent_id_never_raises(tmp_path):
    """BLOCKER 3 (round 11 review finding, round 12 fix, 2026-08-28): a
    ledger row with a malformed (JSON list) `agent_id` must never raise out
    of `attribute_cycle_spend()` -- `isinstance(row_agent_id, str)` at the
    agent_id-correlation predicate is the load-bearing guard (mutation-
    tested: removing it raises `TypeError: unhashable type: 'list'` from
    the `row_agent_id in anchor_agent_ids` membership check). This module's
    documented contract is that it NEVER raises for ledger data problems --
    only for caller misuse -- so a malformed agent_id must degrade into a
    normal classification (excluded/ambiguous/etc.), never a crash."""
    ledger = tmp_path / "spend.jsonl"
    anchor = _simple_row(session="sess-A", agent_id="normal-id", tool_use_id="tuN")
    anchor["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    malformed_row = _simple_row(session=None, agent_id=["not", "a", "string"], agent_type="engine-architect")
    _write_ledger(ledger, [anchor, malformed_row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    # Never raises. The malformed-agent_id row is neither session-matched
    # nor agent_id-correlated (it fails the isinstance(str) guard), and its
    # undeclared agent_type means it lands in `excluded_rows`, not
    # `ambiguous_rows`.
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_ANCHOR_USD)
    assert attr.matched_rows == 1
    assert attr.excluded_rows == 1


def test_falsify_real_ledger_row_null_tokens_total_forces_unpriced(tmp_path):
    """BLOCKER 2 (round 11 review finding, round 12 fix, 2026-08-28): a
    REAL ledger row with `tokens_total: null` (and a non-empty, otherwise
    well-formed `tokens` dict) must be treated as UNPRICEABLE, never
    silently pass the round-6 cross-check by having it treated as 'the
    caller declined to assert a tokens_total'. That silent-pass reading is
    exactly what let 48 real live-ledger rows with `tokens_total: null`
    slip through undetected."""
    ledger = tmp_path / "spend.jsonl"
    row = _simple_row(session="sess-A", agent_id="NT", tool_use_id="tuNT")
    row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    row["tokens_total"] = None
    _write_ledger(ledger, [row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "unpriced-model-in-window"
    assert attr.unpriced_rows == 1


def test_falsify_ambiguous_correlated_declared_type_dropped_by_collapse_forces_unknown(tmp_path):
    """BLOCKER 3 (round 10, 2026-08-28), the reviewer's exact repro: row A
    (session=S, matched, $30.00, agent_type "implement" DECLARED) and row
    B (session=null, agent_id-correlated to A, $9.00, agent_type
    "implement" DECLARED) share an agent_id with 0 distinct tool_use_ids
    -- round 8's collapse would silently keep the $30.00 winner and
    discard B as "the same dispatch read twice". But B's own declared
    type means the module genuinely cannot tell duplicate-reading apart
    from real additional spend -- round 7's promise ("never turns
    AMBIGUOUS into MATCHED") is preserved by forcing unknown here instead
    of silently guessing the smaller-total answer."""
    ledger = tmp_path / "spend.jsonl"
    row_a = _simple_row(session="sess-A", agent_id="X", agent_type="implement", tool_use_id=None)
    row_a["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    row_b = _simple_row(session=None, agent_id="X", agent_type="implement", tool_use_id=None)
    row_b["tokens"] = {"input": 3_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 3M in
    _write_ledger(ledger, [row_a, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "ambiguous-duplicate-agent-id-declared-type"
    assert attr.ambiguous_rows == 1
    assert attr.matched_rows == 2  # both rows reached `matched` before the collapse ran


def test_falsify_dropped_correlated_row_with_undeclared_type_still_collapses_normally(tmp_path):
    """Paired non-regression for BLOCKER 3: the SAME shape as the test
    above, except row B's agent_type is one this cycle never declared.
    An undeclared type on the dropped row carries no ambiguity signal at
    all (this cycle never said it might dispatch that type), so the
    existing round 3/4/8 collapse behavior is unchanged -- the group still
    collapses to its larger reading, exactly as
    test_falsify_agent_id_correlated_unjoined_row_is_never_excluded
    already covers for the winning-correlated-row case."""
    ledger = tmp_path / "spend.jsonl"
    row_a = _simple_row(session="sess-A", agent_id="X", agent_type="implement", tool_use_id=None)
    row_a["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    row_b = _simple_row(session=None, agent_id="X", agent_type="workflow-subagent", tool_use_id=None)
    row_b["tokens"] = {"input": 3_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 3M in
    _write_ledger(ledger, [row_a, row_b])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_REAP_USD)
    assert attr.collapsed_duplicate_rows == 1


def test_documents_correlated_row_in_distinct_tool_use_id_group_still_sums(tmp_path):
    """BLOCKER 2 (round 10), combination (b): a correlated row landing in a
    group that ALSO contains 2+ distinct non-null tool_use_ids (round 6's
    rule) must produce the SAME already-documented, accepted overcount
    tradeoff as test_documents_known_overcount_tradeoff_of_distinct_tool_
    use_id_rule -- never a new bug, and never this round's new ambiguous-
    forcing check (which only ever applies to a row the collapse actually
    DROPS; a 2+-distinct-tool_use_id group is never collapsed at all).
    row1/row2: two real, independent 1M-input dispatches (distinct
    tool_use_ids), both matched directly by session. row3: a
    null-tool_use_id, agent_id-correlated reap of one of them, also 1M in.
    2 distinct tool_use_ids (tu1, tu2) means the whole group of 3 is left
    uncollapsed -- 3 rows' worth reported for 2 rows of genuine spend, documented,
    fail-closed, unchanged by agent_id correlation being involved."""
    ledger = tmp_path / "spend.jsonl"
    row1 = _simple_row(session="sess-A", agent_id="a", tool_use_id="tu1")
    row1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    row2 = _simple_row(session="sess-A", agent_id="a", tool_use_id="tu2")
    row2["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    row3 = _simple_row(session=None, agent_id="a", agent_type="workflow-subagent", tool_use_id=None)
    row3["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    _write_ledger(ledger, [row1, row2, row3])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(3 * _ANCHOR_USD)
    assert attr.collapsed_duplicate_rows == 0
    assert attr.matched_rows == 3


def test_malformed_lines_are_skipped_not_fatal(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    with open(ledger, "w", encoding="utf-8") as fh:
        fh.write("not json at all\n")
        fh.write(json.dumps(_simple_row(session="sess-A", tokens_total=3000)) + "\n")
        fh.write("[1, 2, 3]\n")  # valid JSON, not an object
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.malformed_lines == 2
    assert attr.matched_rows == 1


def test_falsify_duplicate_collapse_winner_is_dollars_not_token_count(tmp_path):
    """BLOCKER 1 (round 4, 2026-08-28), the reviewer's exact repro: round 3's
    own fix picked the duplicate-collapse winner by summing raw TOKEN
    COUNTS -- but token fields are priced at very different rates, so
    "most tokens" and "most dollars" can name different rows. row1 has 1M
    OUTPUT tokens; row2 has 2M CACHE_READ tokens -- TWICE the raw token
    count, but output is priced 50x cache_read, so row2 is 25x LESS real
    spend. The collapse must keep the dollar-larger (output) row, and a
    ceiling set below it must correctly DENY.

    The dollar figures are derived from the live pricing table rather than
    hardcoded: the property under test is "dollars, not token count, picks
    the winner", which holds at any rates so long as output out-prices
    cache_read. The ceiling is likewise derived at HALF the winning row's
    own value, so the DENY it asserts always rests on a real dollar gap --
    never on a spend-exactly-equals-ceiling float knife-edge, which would
    silently degrade this into a test of the `>` vs `>=` boundary instead
    of the collapse behavior it exists to prove."""
    ledger = tmp_path / "spend.jsonl"
    row1 = _simple_row(session="sess-A", agent_id="dup-agent")
    row1["tokens"] = {"input": 0, "output": 1_000_000, "cache_read": 0, "cache_creation": 0}
    row2 = _simple_row(session="sess-A", agent_id="dup-agent")
    row2["tokens"] = {"input": 0, "output": 0, "cache_read": 2_000_000, "cache_creation": 0}
    _write_ledger(ledger, [row1, row2])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    winner_usd = _usd("sonnet", output=1_000_000)
    loser_usd = _usd("sonnet", cache_read=2_000_000)
    assert winner_usd > loser_usd  # the premise: fewer tokens, more dollars
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(winner_usd)  # the output row wins, not the cache_read one

    decision = cb.decide_cycle_budget(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=winner_usd / 2,  # a real gap, not a knife-edge equality
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert decision.allowed is False  # real spend genuinely OVER the ceiling must deny
    assert decision.status == "known"
    assert decision.spent_usd == pytest.approx(winner_usd)


def test_falsify_distinct_tool_use_ids_are_never_collapsed_into_one_dispatch(tmp_path):
    """BLOCKER 3 (round 6, 2026-08-28), the reviewer's exact repro: two rows
    share an `agent_id` but each carries its OWN, DISTINCT, non-null
    `tool_use_id` -- proof of two INDEPENDENT real Task dispatches, never
    two readings of the same one (contrast with
    test_falsify_duplicate_agent_id_matched_rows_do_not_double_count_spend
    above, where both rows share the SAME dispatch and collapsing to one is
    correct). Before the fix this group was collapsed to a single
    winner, discarding the second dispatch's real spend -- exactly the same
    2x under-report `churn_report.dedup_spend_lines()` was already designed
    to never produce for identical bytes (it never dedups rows carrying
    distinct non-null tool_use_ids)."""
    ledger = tmp_path / "spend.jsonl"
    row1 = _simple_row(session="sess-A", agent_id="a", tool_use_id="tu1")
    row1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    row2 = _simple_row(session="sess-A", agent_id="a", tool_use_id="tu2")
    row2["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [row1, row2])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(2 * _ANCHOR_USD)  # both dispatches counted, never collapsed
    assert attr.collapsed_duplicate_rows == 0
    assert attr.matched_rows == 2


def test_duplicate_agent_id_one_distinct_tool_use_id_still_collapses(tmp_path):
    """The paired non-regression case: a group with only ONE distinct
    non-null tool_use_id (a normal release plus a null-tool_use_id reap of
    the SAME dispatch -- the case this collapse was actually designed for)
    must still collapse exactly as before round 6."""
    ledger = tmp_path / "spend.jsonl"
    released = _simple_row(session="sess-A", agent_id="dup-agent", tool_use_id="tu1")
    released["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    reaped = _simple_row(session="sess-A", agent_id="dup-agent", tool_use_id=None)
    reaped["tokens"] = {"input": 2_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [released, reaped])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_usd("sonnet", input=2_000_000))  # only the larger (2M input) reading counts
    assert attr.collapsed_duplicate_rows == 1
    assert attr.matched_rows == 2


def test_documents_known_overcount_tradeoff_of_distinct_tool_use_id_rule(tmp_path):
    """Finding #7 (round 8, 2026-08-28): the 2+-distinct-tool_use_id rule
    (round 6) can OVER-count when a group also contains an embedded,
    null-tool_use_id reap of one of the group's own real rows. Two REAL,
    independent 1M-input dispatches (distinct tool_use_id each) plus a
    null-tool_use_id reap of the FIRST dispatch's own underlying spend
    reports 3 rows' worth for 2 rows of genuine spend -- documented here as an
    accepted, safe (fail-CLOSED, never under-counts) tradeoff, not a bug to
    fix."""
    ledger = tmp_path / "spend.jsonl"
    row1 = _simple_row(session="sess-A", agent_id="a", tool_use_id="tu1")
    row1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    row2 = _simple_row(session="sess-A", agent_id="a", tool_use_id="tu2")
    row2["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    reap_of_row1 = _simple_row(session="sess-A", agent_id="a", tool_use_id=None)
    reap_of_row1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 1M in == _ANCHOR_USD
    _write_ledger(ledger, [row1, row2, reap_of_row1])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert attr.status == "known"
    # 2+ distinct tool_use_ids in the group (tu1, tu2) means the WHOLE
    # group is left uncollapsed -- all three rows priced and summed,
    # 3 rows' worth reported for 2 rows of real, distinct spend. Documented
    # fail-closed tradeoff, not a silent under-count.
    assert attr.spent_usd == pytest.approx(3 * _ANCHOR_USD)
    assert attr.collapsed_duplicate_rows == 0


def test_documents_overlapping_same_session_windows_each_count_the_same_spend(tmp_path):
    """Review finding #2 (round 16, 2026-08-28): 'KNOWN, ACCEPTED TRADEOFF
    #2' (round 14, module docstring lines ~888-908) is documented but had
    ZERO test coverage -- unlike its sibling TRADEOFF #1, locked in above.
    This test constructs the EXACT documented scenario: cycle A
    `[09:00, 12:00]` and cycle B `[11:00, 14:00]` on the SAME session id,
    genuinely OVERLAPPING (this module's documented OPERATING PRECONDITION
    is that a caller's own cycle windows for a given session are
    non-overlapping -- a caller that schedules genuinely overlapping
    cycles is outside that precondition and gets exactly this double-
    count). An agent (`agent_id="X"`) anchored at 11:30 -- inside BOTH
    windows -- has an unjoined reap at 15:00 -- after BOTH windows' own
    end. Each cycle, independently and CORRECTLY per its own window math,
    reports known/$30.00 -- the SAME real $30.00 counted twice across the
    two reports. This locks in the documented, accepted (fail-CLOSED,
    never under-counts) behavior so a future change can't silently break
    it without a test noticing."""
    ledger = tmp_path / "spend.jsonl"
    anchor = _simple_row(session="sess-A", agent_id="X", tool_use_id="tuX", ts="2026-08-28T11:30:00Z")
    anchor["tokens"] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}  # $0.00 -- isolates the reap
    reap = _simple_row(
        session=None,
        agent_id="X",
        agent_type="workflow-subagent",
        tool_use_id=None,
        ts="2026-08-28T15:00:00Z",  # after BOTH cycle A's (12:00) and cycle B's (14:00) own end
    )
    reap["tokens"] = {"input": 10_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}  # 10M in == _REAP_USD
    _write_ledger(ledger, [anchor, reap])

    attr_a = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        cycle_start_ts="2026-08-28T09:00:00Z",
        cycle_end_ts="2026-08-28T12:00:00Z",
    )
    attr_b = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,
        cycle_start_ts="2026-08-28T11:00:00Z",
        cycle_end_ts="2026-08-28T14:00:00Z",
    )
    assert attr_a.status == "known"
    assert attr_b.status == "known"
    # The SAME real $30.00 counted twice across the two overlapping-window
    # reports -- documented, accepted, fail-closed (never a silent
    # under-count of either cycle's own window math).
    assert attr_a.spent_usd == pytest.approx(_REAP_USD)
    assert attr_b.spent_usd == pytest.approx(_REAP_USD)


@pytest.mark.parametrize(
    "clean_tokens,malformed_tokens,malformed_tokens_total",
    [
        (
            {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0},
            {"input": -5, "output": 0, "cache_read": 0, "cache_creation": 0},
            999_999_999,
        ),
        (
            {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0},
            None,
            999_999_999,
        ),
    ],
    ids=["variant-a-negative-tokens", "variant-b-tokens-none"],
)
def test_falsify_duplicate_group_malformed_row_never_vanishes_from_pricing(
    tmp_path, clean_tokens, malformed_tokens, malformed_tokens_total
):
    """BLOCKER 2 (round 4, 2026-08-28), variants A/B: a malformed/unpriceable
    row sharing an agent_id with a clean row must NOT silently vanish from
    the pricing sum when it loses the duplicate-collapse comparison -- the
    whole attribution must return unknown, exactly as a LONE malformed row
    already correctly does."""
    ledger = tmp_path / "spend.jsonl"
    clean = _simple_row(session="sess-A", agent_id="dup", tokens_total=1_000_000)
    clean["tokens"] = clean_tokens
    malformed = _simple_row(session="sess-A", agent_id="dup", tokens_total=malformed_tokens_total)
    malformed["tokens"] = malformed_tokens
    _write_ledger(ledger, [clean, malformed])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "unpriced-model-in-window"


def test_falsify_duplicate_group_unpriced_model_sibling_never_vanishes(tmp_path):
    """BLOCKER 2 (round 4, 2026-08-28), variant C: a duplicate-agent_id
    pairing of a priceable sonnet row (5M tokens) and an unpriced-model row
    ('claude-imaginary-9', 1M tokens) must NOT collapse to a confident dollar figure --
    the unpriced model's contribution must not be silently dropped just
    because it lost the collapse comparison to its priceable sibling."""
    ledger = tmp_path / "spend.jsonl"
    sonnet_row = _simple_row(session="sess-A", agent_id="dup", model="claude-sonnet-5", tokens_total=5_000_000)
    sonnet_row["tokens"] = {"input": 5_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    unpriced_row = _simple_row(session="sess-A", agent_id="dup", model="claude-imaginary-9", tokens_total=1_000_000)
    unpriced_row["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [sonnet_row, unpriced_row])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "unpriced-model-in-window"


def test_expected_dispatch_count_zero_with_priced_rows_present_is_count_mismatch(tmp_path):
    """Combination-coverage cell (#6, round 4): `expected_dispatch_count=0`
    asserted while the ledger actually has priced (non-zero) matched rows
    must be rejected as a count mismatch -- `0` only ever means "known/$0"
    when the matched-row count is ALSO genuinely zero (see
    test_empty_ledger_with_zero_expected_is_known_zero); it must never
    silently ignore real matched spend."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=0,
        **WINDOW,
    )
    assert attr.status == "unknown"
    assert attr.reason == "count-mismatch:expected=0:found=1"


def test_expected_dispatch_count_none_with_duplicate_collapse_group(tmp_path):
    """Combination-coverage cell (#6, round 4): `expected_dispatch_count=None`
    (no assertion made) combined with a duplicate-agent_id collapse group.
    This cell is exercised implicitly by BLOCKER 1/2's own falsifying tests
    above (all pass `expected_dispatch_count=1`, not `None`) -- so this test
    closes the specific `None` combination directly rather than assuming
    it's covered: with no count asserted, a duplicate-collapse group must
    still gate correctly (collapsing to one real dispatch and pricing it),
    never mistaking the raw 2-line count for 2 real dispatches and never
    silently accepting an ambiguous count."""
    ledger = tmp_path / "spend.jsonl"
    row1 = _simple_row(session="sess-A", agent_id="dup-agent", tokens_total=1_000_000)
    row1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    row2 = _simple_row(session="sess-A", agent_id="dup-agent", tokens_total=2_000_000)
    row2["tokens"] = {"input": 2_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [row1, row2])

    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=None,  # no assertion made at all
        **WINDOW,
    )
    # No count was asserted, so the count-mismatch check never fires; the
    # collapse still applies and the larger (2M input @ $2/MTok) row
    # is the one priced.
    assert attr.status == "known"
    assert attr.spent_usd == pytest.approx(_usd("sonnet", input=2_000_000))
    assert attr.collapsed_duplicate_rows == 1


def test_falsify_duplicate_agent_id_matched_rows_do_not_double_count_spend(tmp_path):
    """BLOCKER 3 defense-in-depth (2026-08-28): the SAME agent_id can appear
    as two independent ledger LINES sharing this cycle's own session -- a
    normal claim/release plus a LATER, LARGER cumulative 'stopped-unjoined'
    reap of the SAME agent's still-running spend (see
    spend_attribution.py's module docstring for the measured real example).
    Naively summing both MATCHED rows would double-count real spend. Only
    the larger (later) reading may be priced; `matched_rows` itself still
    reports both rows genuinely matched this cycle's session, and
    `collapsed_duplicate_rows` discloses the collapse.

    BLOCKER 2 (round 3, 2026-08-28): the caller HONESTLY declares
    `expected_dispatch_count=1` (there is exactly ONE real agent here, even
    though it produced 2 raw ledger lines) -- this must be accepted, never
    rejected as a count mismatch, because the comparison runs against the
    POST-COLLAPSE distinct-dispatch count (1), not the raw pre-collapse row
    count (2). Before the round-3 fix this exact honest declaration was
    wrongly rejected as `count-mismatch:expected=1:found=2`."""
    ledger = tmp_path / "spend.jsonl"
    row1 = _simple_row(session="sess-A", agent_id="dup-agent", tokens_total=1_000_000)
    row1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    row2 = _simple_row(session="sess-A", agent_id="dup-agent", tokens_total=2_000_000)
    row2["tokens"] = {"input": 2_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [row1, row2])
    attr = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=1,  # the honest count: ONE real agent, not two lines
        **WINDOW,
    )
    assert attr.status == "known"
    assert attr.matched_rows == 2  # both rows genuinely matched this session
    # Only the larger (2M input tokens @ $2/MTok sonnet) reading counts
    # -- summing both readings of the same dispatch would over-report.
    assert attr.spent_usd == pytest.approx(_usd("sonnet", input=2_000_000))
    assert attr.collapsed_duplicate_rows == 1


def test_expected_dispatch_count_compares_against_post_collapse_count_not_raw_rows(tmp_path):
    """BLOCKER 2 (round 3, 2026-08-28), the falsifying pair: a cycle with 2
    DISTINCT real agents -- one of which (agent 'dup-agent') legitimately
    produced 2 ledger lines -- has a post-collapse distinct-dispatch count
    of 2 (dup-agent's winner + agent 'solo-agent'). Declaring the honest,
    post-collapse count of 2 must be ACCEPTED; declaring the raw pre-
    collapse row count of 3 (the pre-fix, wrong comparison basis) must be
    REJECTED as a mismatch -- proving the comparison is keyed on the
    post-collapse count, not the number of ledger lines."""
    ledger = tmp_path / "spend.jsonl"
    dup1 = _simple_row(session="sess-A", agent_id="dup-agent", tokens_total=1_000_000)
    dup1["tokens"] = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    dup2 = _simple_row(session="sess-A", agent_id="dup-agent", tokens_total=2_000_000)
    dup2["tokens"] = {"input": 2_000_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    solo = _simple_row(session="sess-A", agent_id="solo-agent", tokens_total=500_000)
    solo["tokens"] = {"input": 500_000, "output": 0, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [dup1, dup2, solo])

    correct = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=2,  # post-collapse distinct count: dup-agent + solo-agent
        **WINDOW,
    )
    assert correct.status == "known"
    assert correct.collapsed_duplicate_rows == 1
    assert correct.spent_usd == pytest.approx(_usd("sonnet", input=2_000_000) + _usd("sonnet", input=500_000))  # 2M in + 500K in

    wrong = cb.attribute_cycle_spend(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        expected_dispatch_count=3,  # raw pre-collapse row count -- must be rejected
        **WINDOW,
    )
    assert wrong.status == "unknown"
    assert wrong.reason == "count-mismatch:expected=3:found=2"


# ---------------------------------------------------------------------------
# THE CEILING ACTUALLY REFUSES.
# ---------------------------------------------------------------------------


def test_decide_allows_when_under_ceiling(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])  # == _SIMPLE_ROW_USD
    decision = cb.decide_cycle_budget(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=100.0,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert decision.allowed is True
    assert decision.status == "known"
    assert decision.reason == "under-ceiling"
    assert decision.remaining_usd is not None and decision.remaining_usd > 0


def test_decide_refuses_when_at_or_over_ceiling(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    # This test's name states its own contract: refuse at OR over. The
    # ceiling is therefore set to EXACTLY the row's own cost, which is the
    # "at" boundary -- spend == ceiling, remaining == 0, and the decision
    # must still DENY. Derived from the live table so the boundary stays
    # exact across pricing changes; a hardcoded literal silently turns this
    # into an "under ceiling" case (which ALLOWS) the moment rates move.
    row = _simple_row(session="sess-A")
    row["tokens"] = {"input": 1_000_000, "output": 1_000_000, "cache_read": 0, "cache_creation": 0}
    exact_spend = _usd("sonnet", input=1_000_000, output=1_000_000)
    _write_ledger(ledger, [row])
    decision = cb.decide_cycle_budget(
        str(ledger),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=exact_spend,
        expected_dispatch_count=1,
        **WINDOW,
    )
    assert decision.allowed is False
    assert decision.status == "known"
    assert decision.reason == "ceiling-reached"
    assert decision.spent_usd == pytest.approx(exact_spend)
    assert decision.remaining_usd == pytest.approx(0.0)


def test_decide_refuses_on_unknown_attribution_never_zero_spend(tmp_path):
    """The load-bearing behavior: an unknown ledger slice must DENY, exactly
    like being over budget -- never 'allowed=True, spent $0'.
    """
    missing = tmp_path / "does-not-exist.jsonl"
    decision = cb.decide_cycle_budget(
        str(missing),
        system="loop",
        session_id="sess-A",
        known_agent_types=KNOWN_TYPES,
        ceiling_usd=1000.0,  # a ceiling so large it could never be the reason to deny
        expected_dispatch_count=None,
        **WINDOW,
    )
    assert decision.allowed is False
    assert decision.status == "unknown"
    assert decision.spent_usd is None
    assert decision.reason == "ledger-unreadable"


# ---------------------------------------------------------------------------
# CLI: run()/main() argv handling and exit codes.
# ---------------------------------------------------------------------------


def _argv_common(ledger, extra: list[str] | None = None) -> list[str]:
    argv = [
        "--system",
        "loop",
        "--session",
        "sess-A",
        "--cycle-start",
        "2026-08-28T09:00:00Z",
        "--cycle-end",
        "2026-08-28T12:00:00Z",
        "--agent-types",
        "implement,code-reviewer,test-writer",
        "--ledger",
        str(ledger),
    ]
    return argv + (extra or [])


def test_cli_status_reports_known_spend(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    argv = ["status"] + _argv_common(ledger, ["--expected-dispatches", "1"])
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["status"] == "known"
    assert payload["spent_usd"] > 0


def test_cli_status_with_ceiling_reports_remaining(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    argv = ["status"] + _argv_common(ledger, ["--expected-dispatches", "1", "--ceiling-usd", "10"])
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["ceiling_usd"] == 10.0
    assert payload["remaining_usd"] == pytest.approx(10.0 - payload["spent_usd"])


def test_cli_check_exit_0_when_allowed(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    argv = ["check"] + _argv_common(ledger, ["--expected-dispatches", "1", "--ceiling-usd", "1000"])
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["allowed"] is True


def test_cli_check_exit_2_when_over_ceiling(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    row = _simple_row(session="sess-A")
    row["tokens"] = {"input": 1_000_000, "output": 1_000_000, "cache_read": 0, "cache_creation": 0}
    _write_ledger(ledger, [row])
    argv = ["check"] + _argv_common(ledger, ["--expected-dispatches", "1", "--ceiling-usd", "1"])
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 2
    assert payload["allowed"] is False
    assert payload["status"] == "known"


def test_cli_check_exit_3_when_unknown(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger,
        [
            _simple_row(session="sess-A"),
            _simple_row(session=None, agent_type="implement"),
        ],
    )
    argv = ["check"] + _argv_common(
        ledger, ["--expected-dispatches", "1", "--ceiling-usd", "1000"]
    )
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 3
    assert payload["allowed"] is False
    assert payload["status"] == "unknown"


def test_cli_check_exit_2_on_bad_arguments(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [])
    argv = [
        "check",
        "--system",
        "loop",
        "--session",
        "sess-A",
        "--cycle-start",
        "2026-08-28T09:00:00Z",
        "--agent-types",
        "",
        "--expected-dispatches",
        "0",
        "--ledger",
        str(ledger),
        "--ceiling-usd",
        "1000",
    ]
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 2
    assert "error" in payload


def test_cli_check_missing_expected_dispatches_is_argument_error(tmp_path):
    """BLOCKER 1 (round 3, 2026-08-28): `--expected-dispatches` is REQUIRED
    on `check` -- the gate a dispatcher actually spawns/denies work on can
    never be allowed to silently default into the unsafe unasserted path.
    Omitting it is an argparse argument error, exactly like omitting any
    other required flag (`--system`, `--ceiling-usd`, etc.)."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    argv = ["check"] + _argv_common(ledger, ["--ceiling-usd", "1000"])
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 2
    assert "error" in payload


def test_cli_status_works_without_expected_dispatches(tmp_path):
    """`status` stays OPTIONAL for `--expected-dispatches` -- it is a pure
    report, never a gate, and a matched, priceable slice must still report
    known spend with no count assertion at all."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    argv = ["status"] + _argv_common(ledger)
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["status"] == "known"
    assert payload["spent_usd"] > 0


def test_cli_doctor_reports_health(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger,
        [
            _simple_row(session="sess-A"),
            _simple_row(session=None, agent_type="implement"),
            _simple_row(session="sess-A", model="claude-imaginary-9"),
        ],
    )
    code, payload = cb.run(["doctor", "--ledger", str(ledger)], environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["ledger_exists"] is True
    assert payload["ledger_readable"] is True  # BLOCKER 4 (round 6): a real, readable ledger
    assert payload["row_count"] == 3
    assert payload["unjoined_session_rows"] == 1
    assert "unknown" in payload["unpriced_families_seen"]
    assert payload["pricing_table_valid"] is True


def test_falsify_doctor_oldest_newest_ts_are_real_min_max_not_file_order(tmp_path):
    """#8 (round 10, 2026-08-28): `oldest_row_ts`/`newest_row_ts` used to be
    `rows[0]`/`rows[-1]` -- assuming the ledger's own append-only file
    order is chronological, which it is never guaranteed to be (concurrent
    writers, a reap process appending a late-arriving row, etc.). The
    ledger below is written deliberately OUT of chronological order, plus
    one row with an unparsable `ts` that must never win either boundary."""
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(
        ledger,
        [
            _simple_row(session="sess-A", ts="2026-08-28T10:00:00Z"),
            _simple_row(session="sess-A", ts="not-a-timestamp"),
            _simple_row(session="sess-A", ts="2026-08-27T05:00:00Z"),  # actually oldest
            _simple_row(session="sess-A", ts="2026-08-29T22:00:00Z"),  # actually newest
        ],
    )
    code, payload = cb.run(["doctor", "--ledger", str(ledger)], environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["oldest_row_ts"] == "2026-08-27T05:00:00Z"
    assert payload["newest_row_ts"] == "2026-08-29T22:00:00Z"


def test_cli_doctor_missing_ledger(tmp_path):
    missing = tmp_path / "nope.jsonl"
    code, payload = cb.run(["doctor", "--ledger", str(missing)], environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["ledger_exists"] is False
    assert payload["row_count"] == 0
    assert payload["ledger_readable"] is False  # BLOCKER 4 (round 6): a missing ledger


def test_falsify_doctor_ledger_readable_is_false_for_unreadable_existing_file(tmp_path):
    """BLOCKER 4 (round 6, 2026-08-28), the reviewer's exact repro: before
    the fix, `ledger_readable` was computed as `rows is not None` AFTER
    `rows = rows or []` had already made `rows` unconditionally a list --
    so this key was ALWAYS `True`, even for a ledger that genuinely exists
    but cannot be read (a permission error, an OS-level failure). This is
    the exact health signal an operator/oversight job reads to know whether
    the guard is functioning, and it must never lie in the direction that
    hides a broken gate."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permissions; cannot exercise a real permission error")
    unreadable = tmp_path / "unreadable.jsonl"
    unreadable.write_text(json.dumps(_simple_row(session="sess-A")) + "\n")
    os.chmod(unreadable, 0o000)
    try:
        code, payload = cb.run(["doctor", "--ledger", str(unreadable)], environ={"HOME": str(tmp_path)})
    finally:
        os.chmod(unreadable, 0o644)  # restore so tmp_path cleanup can remove it
    assert code == 0
    assert payload["ledger_exists"] is True  # the file genuinely exists
    assert payload["ledger_readable"] is False  # but it could not be read
    assert payload["row_count"] == 0


def test_default_ledger_path_env_override():
    assert cb._default_ledger_path({"CSA_CYCLE_LEDGER": "/tmp/custom.jsonl"}) == "/tmp/custom.jsonl"


def test_default_ledger_path_falls_back_to_home():
    path = cb._default_ledger_path({"HOME": "/home/x"})
    assert path == os.path.join("/home/x", ".claude", ".agent_budget", "spend.jsonl")


def test_cli_pricing_file_override(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A", model="claude-imaginary-9")])
    pricing_file = tmp_path / "pricing.json"
    custom_pricing = dict(cb.PRICING_USD_PER_MTOK)
    # "claude-imaginary-9" still normalizes to "unknown" -- an override file
    # cannot rescue an unrecognized model family without also adding an
    # "unknown" price, which would defeat the whole "refuse to guess"
    # contract. Confirm it stays unknown even with a pricing override.
    pricing_file.write_text(json.dumps(custom_pricing))
    argv = ["status"] + _argv_common(
        ledger, ["--expected-dispatches", "1", "--pricing-file", str(pricing_file)]
    )
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 0
    assert payload["status"] == "unknown"
    assert payload["reason"] == "unpriced-model-in-window"


def test_cli_bad_pricing_file_is_invalid_arguments(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    bad_pricing = tmp_path / "bad_pricing.json"
    bad_pricing.write_text("not json")
    argv = ["status"] + _argv_common(
        ledger, ["--expected-dispatches", "1", "--pricing-file", str(bad_pricing)]
    )
    code, payload = cb.run(argv, environ={"HOME": str(tmp_path)})
    assert code == 2
    assert "error" in payload


def test_main_prints_json_and_returns_exit_code(tmp_path, capsys):
    ledger = tmp_path / "spend.jsonl"
    _write_ledger(ledger, [_simple_row(session="sess-A")])
    argv = ["status"] + _argv_common(ledger, ["--expected-dispatches", "1"])
    code = cb.main(argv)
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "known"


def test_main_missing_required_arg_exits_nonzero_no_crash(capsys):
    code = cb.main(["check", "--system", "loop"])
    assert code != 0
