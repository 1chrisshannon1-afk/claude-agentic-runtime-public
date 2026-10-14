"""Tests for hooks/agent_telemetry.py.

These assert INTENDED behavior from the plan spec
(`~/.claude/plans/agent_telemetry_dashboard_plan.md` §1 and §3), never a
snapshot of what the module currently prints. Where a rule exists to prevent
a specific wrong number, the fixture is built so the WRONG implementation
produces a materially different, provably wrong value, and the test states
both -- per plan §3.2, falsifiability is the bar, not green.

The three rules under heaviest test:

  R2 / the reliability partition -- the plan's own highest-risk rule. Fixtures
     put fast joined rows next to slow unjoined ones so a whole-ledger average
     lands on a number that is wrong in a stated direction.
  Provenance -- an unattributable input must never be laundered into a
     confident value, and the vocabulary must be closed.
  Percentiles from raw values -- a fixture where averaging pre-aggregated
     per-bucket percentiles gives a provably different answer than sorting raw.
"""

from __future__ import annotations

import json
import os
import sys

import re

import pytest

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import agent_telemetry as at  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_ccdash_from_the_operators_real_database(request, tmp_path, monkeypatch):
    """Every test in this file is hermetic against ccdash by default.

    Without this, any test that reaches `collect_all()` (or any ccdash_*
    function directly) queries the OPERATOR'S REAL usage-dashboard database
    (3.4M+ rows) -- slow (measured: pushed this file's runtime from a few
    seconds to 149s) AND a hermeticity violation: a test's pass/fail would
    depend on live data outside this file's control, exactly the thing
    `conftest.py`'s own sandbox fixture exists to prevent for spend.jsonl and
    the enforcement ledger. Point `DB_PATH` at a path that does not exist by
    default (ccdash reports itself unavailable, never crashes); the
    `ccdash_db` fixture below overrides this with a real throwaway database
    for tests that actually need ccdash data.

    OPT-OUT: a test marked `@pytest.mark.live_machine` is exempt. That marker
    exists for SMOKE tests whose entire purpose is to exercise the real code
    path against real data -- a hermetic fixture cannot catch a defect that
    only manifests when the data IS available, which is exactly how a dead
    panel shipped past 4,605 green tests. Such tests must skip themselves when
    the real sources are absent (CI, another machine).

    ccdash itself is OPTIONAL and private: on a machine without the
    usage-dashboard checkout `at.ccdash_parser` is None (see the module's
    own degrade path, `agent_telemetry.py` "Imported lazily-tolerant"). There
    is then no real database to isolate from, so this fixture RETURNS EARLY
    (it does not skip) -- every test that does not need a ccdash database,
    including the tests that prove the metrics degrade explicitly instead of
    crashing, must still run. Only tests that need a real ccdash (the
    `ccdash_db` fixture below, `_require_ccdash()`) skip when ccdash is ABSENT,
    with a stated reason -- and FAIL when it is present but broken.
    """
    if request.node.get_closest_marker("live_machine"):
        return
    if at.ccdash_parser is None:
        return
    monkeypatch.setattr(at.ccdash_parser, "DB_PATH", tmp_path / "no_such_ccdash_db.sqlite")


_CCDASH_ABSENT_REASON = "ccdash (usage-dashboard) not installed; ccdash-backed telemetry is optional"

# What agent_telemetry records (CCDASH_IMPORT_ERROR) when `import ccdash` finds no
# such package at all -- the only import failure that means "not installed".
_CCDASH_NOT_INSTALLED_ERROR = "ModuleNotFoundError: No module named 'ccdash'"


def _classify_ccdash(parser, import_error) -> str:
    """"present", "absent" or "broken".

    "absent" is ONLY the not-installed case. Any other import failure -- a
    SyntaxError, an ImportError, or a ModuleNotFoundError naming some OTHER
    module (a dependency of ccdash, or `ccdash.parser` itself) -- means ccdash is
    there and damaged, and must show up as a failure, not hide behind "optional"."""
    if parser is not None:
        return "present"
    if import_error == _CCDASH_NOT_INSTALLED_ERROR:
        return "absent"
    return "broken"


def _require_ccdash() -> None:
    """Call at the top of a test (or fixture) that needs the real ccdash package.

    Skips with a stated reason when ccdash is not installed; FAILS, showing the
    recorded import error, when it is installed but cannot be imported."""
    state = _classify_ccdash(at.ccdash_parser, at.CCDASH_IMPORT_ERROR)
    if state == "absent":
        pytest.skip(_CCDASH_ABSENT_REASON)
    if state == "broken":
        pytest.fail(
            "ccdash is installed but failed to import, so its tests cannot run: "
            f"CCDASH_IMPORT_ERROR = {at.CCDASH_IMPORT_ERROR!r}",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def make_row(**overrides):
    """A ledger row with every key the real writer emits.

    Defaults describe a JOINED row; pass join_state="no-claim" plus the nulls
    to build the unjoined shape.
    """
    row = {
        "ts": "2026-09-01T12:00:00Z",
        "session": "sess-1",
        "agent_type": "implement",
        "model": "claude-sonnet-5",
        "tool_use_id": "toolu_1",
        "agent_id": "agent-1",
        "duration_ms": 1000,
        "tokens": {"input": 100, "output": 200, "cache_read": 300, "cache_creation": 400},
        "tokens_total": 1000,
        "tokens_error": None,
        "late": False,
        "unreleased": False,
        "reaped": None,
        "join_state": "joined",
    }
    row.update(overrides)
    return row


def make_no_claim_row(**overrides):
    """The no-claim shape: session/model/tool_use_id/duration_ms ALL null.

    This is not a stylistic choice -- it is the measured shape, with zero
    exceptions across the whole ledger.
    """
    base = make_row(
        session=None,
        model=None,
        tool_use_id=None,
        duration_ms=None,
        join_state="no-claim",
        reaped="stopped-unjoined",
        unreleased=True,
    )
    base.update(overrides)
    return base


def write_ledger(tmp_path, rows):
    path = tmp_path / "spend.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return str(path)


def write_transcript(root, project, session, agent_id, entries, workflow=None):
    """Write a transcript + meta pair at one of the two legitimate depths."""
    parts = [str(root), project, session, "subagents"]
    if workflow:
        parts += ["workflows", workflow]
    directory = os.path.join(*parts)
    os.makedirs(directory, exist_ok=True)
    stem = os.path.join(directory, f"agent-{agent_id}")
    with open(stem + ".jsonl", "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    with open(stem + ".meta.json", "w", encoding="utf-8") as fh:
        json.dump({"agentType": "implement", "spawnDepth": 1}, fh)
    return stem


def assistant_turn(tools=(), ts="2026-09-01T12:00:00.000Z"):
    content = [{"type": "tool_use", "name": name} for name in tools]
    return {"type": "assistant", "timestamp": ts, "message": {"content": content}}


# ---------------------------------------------------------------------------
# Provenance rules (plan §3.1)
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_provenance_vocabulary_is_closed(self):
        """An unrecognized provenance string must RAISE, not pass through.

        A typo'd provenance reads to a renderer as "some other kind of
        confident." Wrong implementation: accept any string, and a value
        tagged "recovred" renders as if it were first-party.
        """
        assert at.PROVENANCES == {
            at.ORIGINAL,
            at.RECOVERED,
            at.DECLARED,
            at.DERIVED,
            at.UNATTRIBUTABLE,
        }
        with pytest.raises(ValueError):
            at.Value(1, "confident", "somewhere")
        with pytest.raises(ValueError):
            at.Value(1, "recovred", "typo")

    def test_unattributable_value_cannot_carry_a_number(self):
        """THE core provenance rule: no laundering.

        An unattributable input has no value. Constructing
        Value(0, UNATTRIBUTABLE, ...) would let a renderer plot 0 as though
        it were measured -- the exact defect the rule exists to prevent.
        Wrong implementation permits it and the dashboard shows a confident 0.
        """
        with pytest.raises(ValueError):
            at.Value(0, at.UNATTRIBUTABLE, "no data")
        with pytest.raises(ValueError):
            at.Value(0.0, at.UNATTRIBUTABLE, "no data")
        assert at.unattributable("no data").value is None

    def test_every_value_serializes_with_its_provenance(self):
        payload = at.Value(5, at.DERIVED, "computed").to_dict()
        assert payload == {"value": 5, "provenance": at.DERIVED, "source": "computed"}
        assert set(payload) == {"value", "provenance", "source"}

    def test_missing_agent_type_is_unattributable_not_a_persona(self):
        """The three coexisting 'missing' spellings normalize together.

        None, "", and whitespace are all absent -- and must NOT become a
        agent named "" that sorts into the roster as if it were real.
        """
        for absent in (None, "", "   ", 123):
            name, provenance = at.normalize_agent_type(absent)
            assert name == at.MISSING_AGENT_TYPE
            assert provenance == at.UNATTRIBUTABLE

    def test_case_variants_fold_to_one_key(self):
        """`explore` (232 rows) and `Explore` (8) are ONE agent, not two.

        Wrong implementation reports two roster entries and understates the
        real agent's dispatch count by its case-variant share.
        """
        assert at.normalize_agent_type("Explore")[0] == at.normalize_agent_type("explore")[0]
        assert at.normalize_agent_type(" Explore ")[0] == "explore"
        assert at.normalize_agent_type("Explore")[1] == at.ORIGINAL

    def test_dollar_figures_carry_a_declared_price_table_version(self, tmp_path):
        """Plan R3: no dollar renders without a price-table version.

        Recomputing history against a changed table rewrites what was
        actually paid, so the table identity must travel with the number --
        and as DECLARED (configuration), never ORIGINAL (measured).
        """
        path = write_ledger(tmp_path, [make_row()])
        rows, _ = at.read_ledger(path)
        result = at.spend_usd(rows)
        version = result["price_table_version"]
        assert version.provenance == at.DECLARED
        assert version.value == at.PRICE_TABLE_VERSION


# ---------------------------------------------------------------------------
# The reliability partition (plan §1.1, R2) -- highest-risk rule.
# ---------------------------------------------------------------------------


class TestReliabilityPartition:
    def test_latency_is_computed_over_joined_only(self, tmp_path):
        """R2, the plan's own top risk, with both numbers stated.

        Fixture: 4 joined rows at 40s, plus unjoined rows whose duration_ms
        was (wrongly) populated at 300s. A naive whole-ledger p50 lands near
        300000ms; the correct joined-only p50 is exactly 40000ms.
        """
        rows = [make_row(duration_ms=40000, agent_id=f"j{i}", tool_use_id=f"t{i}") for i in range(4)]
        rows += [
            make_no_claim_row(duration_ms=300000, agent_id=f"u{i}", tokens_total=1000)
            for i in range(6)
        ]
        result = at.latency_percentiles(rows)

        assert result["partition"] == at.JOINED
        assert result["n"] == 4, "denominator must be the joined rows only"
        assert result["p50_ms"].value == 40000.0
        assert result["p50_ms"].value != 300000.0
        # The wrong (whole-ledger) answer, stated so the test documents it.
        naive = sorted([40000.0] * 4 + [300000.0] * 6)
        naive_p50 = naive[int(0.5 * len(naive)) - 1]
        assert naive_p50 == 300000.0
        assert result["p50_ms"].value != naive_p50

    def test_latency_reports_what_it_excluded(self, tmp_path):
        """A partition-filtered panel must state its own exclusions.

        Silently dropping half the ledger is precisely the failure R2 names.
        """
        rows = [make_row()] + [make_no_claim_row(agent_id=f"u{i}") for i in range(9)]
        result = at.latency_percentiles(rows)
        assert result["excluded_non_joined_rows"].value == 9

    def test_panel_refuses_to_render_without_its_denominator(self):
        """Plan §3.2: the panel REFUSES rather than emitting a number from an
        unknown population."""
        rows = [make_no_claim_row(agent_id=f"u{i}") for i in range(5)]
        with pytest.raises(at.PartitionError):
            at.latency_percentiles(rows)
        with pytest.raises(at.PartitionError):
            at.session_metrics(rows)

    def test_no_claim_rows_are_kept_for_tokens(self):
        """The other half of R2, and the one that is easy to get backwards.

        No-claim rows lose their join fields but KEEP tokens -- they are ~46%
        of all tokens. Filtering to joined "to be safe" would silently delete
        the larger half of real activity. Fixture: 1 joined row of 1000
        tokens + 4 unjoined of 1000 each. Correct total is 5000; a
        joined-only implementation reports 1000.
        """
        rows = [make_row()]
        rows += [
            make_no_claim_row(
                agent_id=f"u{i}",
                tokens={"input": 100, "output": 200, "cache_read": 300, "cache_creation": 400},
                tokens_total=1000,
            )
            for i in range(4)
        ]
        result = at.token_buckets(rows)
        assert result["partition"] == "all"
        assert result["n"] == 5
        total = sum(result["buckets"][f].value for f in at.TOKEN_FIELDS)
        assert total == 5000, "no-claim tokens must be counted"
        assert total != 1000, "a joined-only filter would report this wrong number"

    def test_by_model_breakdown_declares_the_joined_partition(self):
        """`model` is null on every no-claim row, so a by-model panel that
        spans the whole ledger describes only the joined half while appearing
        to describe everything."""
        rows = [make_row()] + [make_no_claim_row(agent_id=f"u{i}") for i in range(3)]
        result = at.dispatch_counts(rows)
        by_model = result["by_model"]
        assert by_model["partition"] == at.JOINED
        assert by_model["n"] == 1
        assert by_model["excluded_rows_without_model"].value == 3

    def test_partition_rows_never_guesses_an_absent_join_state(self):
        """Two real rows predate the join_state field. They must land in an
        explicit 'absent' bucket, never be guessed into a real state."""
        row = make_row()
        del row["join_state"]
        buckets = at.partition_rows([row, make_row(), make_no_claim_row(agent_id="u")])
        assert buckets["absent"] == [row]
        assert len(buckets[at.JOINED]) == 1
        assert len(buckets[at.NO_CLAIM]) == 1


# ---------------------------------------------------------------------------
# Percentiles from raw values (plan §3.1)
# ---------------------------------------------------------------------------


class TestPercentiles:
    def test_percentile_of_raw_beats_averaging_pre_aggregated(self):
        """ClickHouse's documented failure, reproduced as a fixture.

        Two buckets of UNEQUAL size -- which is what makes averaging wrong,
        because it silently weights a small bucket equally with a large one.
        Bucket A: 4 slow dispatches (1000ms). Bucket B: 16 fast ones (10ms).

        Averaging the per-bucket p50s gives (1000 + 10) / 2 = 505ms -- a
        latency NO dispatch ever experienced. The true p50 over the raw 20
        values is 10ms, because 16 of 20 dispatches were fast.
        """
        bucket_a = [1000.0] * 4
        bucket_b = [10.0] * 16

        p50_a = at.percentile(sorted(bucket_a), 0.50)
        p50_b = at.percentile(sorted(bucket_b), 0.50)
        averaged_p50 = (p50_a + p50_b) / 2
        true_p50 = at.percentile(sorted(bucket_a + bucket_b), 0.50)

        assert averaged_p50 == 505.0, "the wrong method's answer"
        assert true_p50 == 10.0, "the raw-value answer the plan mandates"
        assert true_p50 != averaged_p50
        # 505 is not merely a different number -- it is a value that appears
        # nowhere in the data at all. That is the plan's point: an averaged
        # percentile "is not a worse p99, it is not a p99 at all."
        assert averaged_p50 not in (bucket_a + bucket_b)

    def test_percentile_edge_cases(self):
        assert at.percentile([], 0.5) is None, "empty must be None, never 0.0"
        assert at.percentile([5.0], 0.5) == 5.0
        assert at.percentile([5.0], 0.99) == 5.0
        # Odd n
        assert at.percentile([1.0, 2.0, 3.0], 0.5) == 2.0
        # Even n -- nearest-rank, never interpolated into a value that was
        # never observed.
        assert at.percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
        assert at.percentile([1.0, 2.0, 3.0, 4.0], 1.0) == 4.0

    def test_percentile_rejects_out_of_range_q(self):
        with pytest.raises(ValueError):
            at.percentile([1.0], 0.0)
        with pytest.raises(ValueError):
            at.percentile([1.0], 1.5)

    def test_p99_suppressed_below_100_samples(self):
        """'One data point wearing a statistical costume' (plan §1.8).

        Below n=100 the p99 must be UNATTRIBUTABLE -- and therefore carry no
        number at all, per the provenance rule.
        """
        rows = [make_row(duration_ms=1000 + i, agent_id=f"j{i}", tool_use_id=f"t{i}") for i in range(50)]
        result = at.latency_percentiles(rows)
        assert result["n"] == 50
        assert result["p99_ms"].provenance == at.UNATTRIBUTABLE
        assert result["p99_ms"].value is None
        assert result["p50_ms"].value is not None, "p50 is fine at n=50"

    def test_p99_reported_at_or_above_threshold(self):
        rows = [
            make_row(duration_ms=1000 + i, agent_id=f"j{i}", tool_use_id=f"t{i}")
            for i in range(at.P99_MIN_SAMPLES)
        ]
        result = at.latency_percentiles(rows)
        assert result["p99_ms"].provenance == at.DERIVED
        assert result["p99_ms"].value is not None


# ---------------------------------------------------------------------------
# tokens_total is the anti-metric (plan §1.3)
# ---------------------------------------------------------------------------


class TestAntiMetric:
    def test_renderer_guard_rejects_a_tokens_total_panel(self):
        """The mechanical backstop. Prose alone is the dead-check class.

        A panel declaring tokens_total as its plotted source must raise.
        """
        with pytest.raises(at.PartitionError):
            at.assert_no_tokens_total_headline(
                [{"id": "headline", "source": "spend.jsonl:tokens_total"}]
            )

    def test_renderer_guard_allows_legitimate_panels(self):
        at.assert_no_tokens_total_headline(
            [
                {"id": "spend", "source": "price_tokens_usd"},
                {"id": "buckets", "source": "spend.jsonl:tokens.cache_read"},
            ]
        )

    def test_token_buckets_reports_four_buckets_not_a_total(self):
        """The four buckets must be separately available, because cache_read
        dominates and a single total hides that entirely."""
        rows = [make_row()]
        result = at.token_buckets(rows)
        assert set(result["buckets"]) == set(at.TOKEN_FIELDS)
        for field in at.TOKEN_FIELDS:
            assert isinstance(result["buckets"][field], at.Value)
        # tokens_total is present ONLY behind an explicit anti-metric label.
        assert "anti_metric" in result
        assert result["anti_metric"]["field"] == at.ANTI_METRIC_FIELD
        assert "NEVER a headline" in result["anti_metric"]["warning"]
        assert at.ANTI_METRIC_FIELD not in result["buckets"]


# ---------------------------------------------------------------------------
# Collapse / dedup (plan §1.4)
# ---------------------------------------------------------------------------


class TestCollapse:
    def test_duplicate_agent_id_is_collapsed_not_summed(self):
        """The dominant real shape: one joined row + a later, larger no-claim
        reap OF THE SAME AGENT.

        Naive sum = 1000 + 1700 = 2700 tokens for one agent that really spent
        1700. The activity collapse reports 1700.
        """
        rows = [
            make_row(agent_id="same", tool_use_id="t1", tokens_total=1000),
            make_no_claim_row(
                agent_id="same",
                tokens={"input": 100, "output": 200, "cache_read": 1000, "cache_creation": 400},
                tokens_total=1700,
            ),
        ]
        kept, report = at.collapse_duplicate_agents(rows, at.BASIS_ACTIVITY)
        assert len(kept) == 1
        assert kept[0]["tokens_total"] == 1700
        assert report["rows_dropped"] == 1
        naive = sum(r["tokens_total"] for r in rows)
        assert naive == 2700, "the wrong answer a naive sum produces"

    def test_two_distinct_tool_use_ids_are_never_collapsed(self):
        """The refinement that is inert on today's data and load-bearing the
        moment it isn't.

        Two rows sharing an agent_id but carrying DISTINCT non-null
        tool_use_ids are provably independent dispatches. Collapsing them was
        a measured 2x UNDER-report: 1000 reported for 2000 of real spend.
        """
        rows = [
            make_row(agent_id="same", tool_use_id="t1", tokens_total=1000),
            make_row(agent_id="same", tool_use_id="t2", tokens_total=1000),
        ]
        for basis in (at.BASIS_ACTIVITY, at.BASIS_COST):
            kept, report = at.collapse_duplicate_agents(rows, basis)
            assert len(kept) == 2, f"{basis}: independent dispatches must both survive"
            assert report["groups_left_uncollapsed_multi_tool_use_id"] == 1
            total = sum(r["tokens_total"] for r in kept)
            assert total == 2000
            assert total != 1000, "the 2x under-report a naive collapse produces"

    def test_cost_basis_prefers_the_priceable_row(self):
        """Why there are two bases at all, and why neither is 'the' answer.

        The dominant dup shape pairs a smaller PRICEABLE joined row with a
        larger UNPRICEABLE no-claim row (model is null). The cost basis must
        crown the priceable one -- an unpriceable candidate can never win
        merely by looking numerically large. The activity basis crowns the
        larger one. Measured live: the two disagree on 336 of 341 groups.
        """
        priceable = make_row(agent_id="same", tool_use_id="t1", tokens_total=1000)
        bigger_unpriceable = make_no_claim_row(
            agent_id="same",
            tokens={"input": 100, "output": 200, "cache_read": 1000, "cache_creation": 400},
            tokens_total=1700,
        )
        rows = [priceable, bigger_unpriceable]

        cost_kept, _ = at.collapse_duplicate_agents(rows, at.BASIS_COST)
        assert cost_kept[0]["model"] == "claude-sonnet-5"
        assert at.row_price_usd(cost_kept[0]) is not None

        activity_kept, _ = at.collapse_duplicate_agents(rows, at.BASIS_ACTIVITY)
        assert activity_kept[0]["tokens_total"] == 1700
        assert cost_kept[0] is not activity_kept[0], "the two bases answer different questions"

    def test_null_tool_use_id_rows_are_never_deduped_away(self):
        """Rule 2 of the authoritative dedup: a null tool_use_id is never
        collapsed. 52% of the ledger carries one, so dropping them would
        delete half the data."""
        rows = [
            make_no_claim_row(agent_id=f"a{i}", tokens_total=100) for i in range(5)
        ]
        kept, report = at.prepare_rows(rows, at.BASIS_ACTIVITY)
        assert len(kept) == 5
        assert report["tool_use_id_dedup"]["null_tool_use_id_rows"] == 5

    def test_malformed_tool_use_id_is_counted_not_silently_dropped(self):
        rows = [make_row(tool_use_id=12345, agent_id="a1")]
        _, report = at.prepare_rows(rows, at.BASIS_ACTIVITY)
        assert report["tool_use_id_dedup"]["malformed_tool_use_id_rows"] == 1

    def test_unknown_basis_rejected(self):
        with pytest.raises(ValueError):
            at.collapse_duplicate_agents([make_row()], "vibes")

    def test_rows_without_agent_id_are_never_grouped(self):
        rows = [make_row(agent_id=None, tool_use_id="t1"), make_row(agent_id="", tool_use_id="t2")]
        kept, _ = at.collapse_duplicate_agents(rows, at.BASIS_ACTIVITY)
        assert len(kept) == 2


# ---------------------------------------------------------------------------
# Pricing (plan §2, decision 0.1)
# ---------------------------------------------------------------------------


class TestPricing:
    def test_uses_the_single_shared_pricing_table(self):
        """A second pricing table that can drift is the exact bug decision
        0.1 just fixed -- so this module must IMPORT, never redefine."""
        import cycle_budget

        assert at.PRICING_USD_PER_MTOK is cycle_budget.PRICING_USD_PER_MTOK
        assert at.normalize_model is cycle_budget.normalize_model
        assert at.price_tokens_usd is cycle_budget.price_tokens_usd

    def test_unpriceable_rows_are_excluded_never_priced_at_zero(self):
        """The silent-understatement failure.

        A row with no model cannot be priced. Pricing it at $0 would report
        total spend as if those rows were free -- and they are ~52% of the
        ledger. They must be excluded AND counted.
        """
        priceable = make_row(agent_id="a1", tool_use_id="t1")
        unpriceable = [make_no_claim_row(agent_id=f"u{i}", tokens_total=1000) for i in range(3)]

        alone = at.spend_usd([priceable])
        mixed = at.spend_usd([priceable] + unpriceable)

        assert mixed["n"] == 1, "only the priceable row counts toward the total"
        assert mixed["unpriceable"]["rows"].value == 3
        assert mixed["unpriceable"]["by_reason"].value["no_model_on_row"] == 3
        assert "never priced at $0" in mixed["unpriceable"]["note"]
        assert mixed["total_usd"].value > 0

        # THE load-bearing assertion: adding three unpriceable rows must not
        # change the total, the denominator, or the per-bucket breakdowns.
        # An implementation that prices them at $0 keeps total_usd identical
        # but silently inflates n and the by_agent_type population, reporting
        # those rows as measured-and-free rather than unmeasurable.
        assert mixed["total_usd"].value == alone["total_usd"].value
        assert mixed["n"] == alone["n"]
        assert mixed["by_agent_type"].value == alone["by_agent_type"].value
        assert mixed["by_day"].value == alone["by_day"].value
        assert mixed["by_model_family"].value == alone["by_model_family"].value
        # Coverage must DROP, because 3 of 4 rows could not be priced. An
        # implementation that prices them at $0 reports 100% coverage over a
        # ledger that is 75% unpriceable.
        assert mixed["pricing_coverage"].value == 0.25
        assert alone["pricing_coverage"].value == 1.0

    def test_unrecognized_model_is_unpriceable_by_policy_not_by_accident(self):
        """A model string that does not normalize to a known pricing family
        (e.g. an unpublished/internal code name) is deliberately absent from
        the pricing table so it can never be silently priced. It must land
        in the model-not-in-table bucket, not be guessed into a family.

        `claude-fable-5` was this test's example (and its own name) until
        2026-09-05, when Fable 5's published $10/$50-per-MTok rate was added
        to cycle_budget.PRICING_USD_PER_MTOK and it became a real priceable
        family -- see that table's own "RESOLVED 2026-09-05" note.
        `claude-imaginary-9` is the current stand-in for a genuinely
        unpriceable model; the refusal-to-guess behavior under test is
        unchanged."""
        assert at.normalize_model("claude-imaginary-9") == "unknown"
        rows = [make_row(model="claude-imaginary-9", agent_id="a1", tool_use_id="t1")]
        result = at.spend_usd(rows)
        assert result["unpriceable"]["by_reason"].value["model_not_in_pricing_table"] == 1

    def test_pricing_coverage_is_reported(self):
        rows = [make_row(agent_id="a1", tool_use_id="t1")]
        rows += [make_no_claim_row(agent_id="u1", tokens_total=1000)]
        result = at.spend_usd(rows)
        assert result["pricing_coverage"].value == 0.5


# ---------------------------------------------------------------------------
# ccdash-backed metrics (added 2026-09-05).
#
# spend.jsonl is a severely degraded sample: 52.5% of its rows carry
# model=null and are unpriceable, understating both total spend (~30%) and
# any single model's share (Fable measured 24x understated: 1.9% of a ledger
# total vs ~32% of ccdash's complete total over the same window). These
# tests assert the ccdash-backed metrics recover the honest figures, degrade
# explicitly (never silently) when ccdash is unavailable, and never invent a
# fourth pricing table.
# ---------------------------------------------------------------------------


@pytest.fixture
def ccdash_db(tmp_path, monkeypatch):
    """A hermetic ccdash sqlite database, built via ccdash's OWN schema.

    Monkeypatches `at.ccdash_parser.DB_PATH` so every ccdash-backed function
    under test reads this throwaway file instead of the real
    ~/.claude/usage-dashboard/data/dashboard.db -- the operator's live
    telemetry must never be touched by a test run.

    Skips (with a stated reason) when ccdash is not installed: a test that
    needs a real ccdash database cannot run without the package that defines
    its schema. Fails, showing CCDASH_IMPORT_ERROR, when ccdash is installed
    but broken.
    """
    _require_ccdash()
    db_path = tmp_path / "dashboard_test.db"
    monkeypatch.setattr(at.ccdash_parser, "DB_PATH", db_path)

    def insert(
        agent_id=None,
        is_sidechain=0,
        model="claude-sonnet-5",
        timestamp_utc="2026-09-05T12:00:00Z",
        input_tokens=100,
        output_tokens=50,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        ephemeral_5m_tokens=None,
        ephemeral_1h_tokens=0,
        file_path="test.jsonl",
        line_no=None,
        message_id=None,
    ):
        conn = at.ccdash_parser.get_connection()
        if ephemeral_5m_tokens is None:
            # Mirrors ccdash's own ingest-time rule: an unset breakdown
            # defaults the whole write to the 5-minute TTL.
            ephemeral_5m_tokens = cache_creation_input_tokens
        nonlocal _next_line_no
        if line_no is None:
            line_no = _next_line_no
            _next_line_no += 1
        conn.execute(
            """
            INSERT INTO usage_events (
                file_path, line_no, agent_id, is_sidechain, model, timestamp_utc,
                input_tokens, output_tokens, cache_creation_input_tokens,
                cache_read_input_tokens, ephemeral_5m_tokens, ephemeral_1h_tokens,
                message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_path, line_no, agent_id, is_sidechain, model, timestamp_utc,
                input_tokens, output_tokens, cache_creation_input_tokens,
                cache_read_input_tokens, ephemeral_5m_tokens, ephemeral_1h_tokens,
                message_id,
            ),
        )
        conn.commit()
        conn.close()

    _next_line_no = 0
    return insert


class TestCcdashContentBlockDedup:
    """One billed API call must count ONCE, however many transcript records
    it was written as.

    THE DEFECT (found 2026-09-05 by adversarial audit): Claude Code writes an
    assistant response as one record per content block (thinking / text /
    tool_use), each repeating the SAME usage verbatim. Summing rows counted a
    single billed call N times. Measured on the live store: 1,348,569 rows but
    only 663,651 distinct message_id -- every ccdash-sourced dollar figure was
    inflated 2.03x.
    """

    def test_three_content_blocks_of_one_response_count_once(self, ccdash_db):
        # One API response, written as 3 records under one message_id, each
        # repeating the identical usage -- exactly the live shape verified in
        # msg_011CeTpf... (thinking/text/tool_use, one requestId).
        for _ in range(3):
            ccdash_db(
                model="claude-sonnet-5",
                input_tokens=1_000_000,
                output_tokens=0,
                message_id="msg_one_response",
                timestamp_utc="2026-09-05T00:00:00Z",
            )
        result = at.ccdash_spend_by_model(since_iso="2026-09-01T00:00:00Z")
        assert result["ccdash_available"] is True
        # 1M sonnet-5 input at $2.00/MTok, counted ONCE -- not $6.00.
        assert result["by_model"].value["claude-sonnet-5"] == pytest.approx(2.00, rel=1e-6)

    def test_distinct_responses_are_never_collapsed(self, ccdash_db):
        """The cure must not under-count: two genuinely separate API calls
        keep their own rows even when otherwise identical."""
        for mid in ("msg_a", "msg_b"):
            ccdash_db(
                model="claude-sonnet-5",
                input_tokens=1_000_000,
                output_tokens=0,
                message_id=mid,
                timestamp_utc="2026-09-05T00:00:00Z",
            )
        result = at.ccdash_spend_by_model(since_iso="2026-09-01T00:00:00Z")
        assert result["by_model"].value["claude-sonnet-5"] == pytest.approx(4.00, rel=1e-6)

    def test_legacy_null_message_id_rows_each_form_their_own_group(self, ccdash_db):
        """A row ingested before message_id existed carries NULL. Those must
        NOT all collapse into a single group -- under-counting is not an
        acceptable cure for over-counting."""
        for _ in range(3):
            ccdash_db(
                model="claude-sonnet-5",
                input_tokens=1_000_000,
                output_tokens=0,
                message_id=None,
                timestamp_utc="2026-09-05T00:00:00Z",
            )
        result = at.ccdash_spend_by_model(since_iso="2026-09-01T00:00:00Z")
        assert result["by_model"].value["claude-sonnet-5"] == pytest.approx(6.00, rel=1e-6)


class TestCcdashAvailability:
    def test_no_database_file_degrades_explicitly_never_crashes(self, tmp_path, monkeypatch):
        """No db file on this machine (the usage-dashboard package IS installed):
        every ccdash-backed function must say so in plain English, never raise
        and never silently fall back to spend.jsonl wearing ccdash's label."""
        _require_ccdash()
        monkeypatch.setattr(at.ccdash_parser, "DB_PATH", tmp_path / "nope.db")
        status = at.ccdash_status()
        assert status["available"] is False
        assert "no database file" in status["reason"]

        for fn in (at.ccdash_token_split, at.ccdash_cache_ttl_split, at.ccdash_spend_by_model):
            result = fn()
            assert result["ccdash_available"] is False
            assert isinstance(result["reason"], str) and result["reason"]

        rows = [make_row(agent_id="a1")]
        join = at.ccdash_agent_type_join(rows, since_iso="2026-09-01T00:00:00Z")
        assert join["ccdash_available"] is False

    def test_import_failure_degrades_explicitly(self, monkeypatch):
        """A missing usage-dashboard checkout entirely (import error, not
        just an empty db) must degrade the same way -- never crash the
        collector that calls it."""
        monkeypatch.setattr(at, "CCDASH_AVAILABLE", False)
        monkeypatch.setattr(at, "CCDASH_IMPORT_ERROR", "ModuleNotFoundError: no ccdash")
        status = at.ccdash_status()
        assert status["available"] is False
        assert "no ccdash" in status["reason"]

        # Every ccdash-backed metric (not just the status probe) must degrade the
        # same way, naming the import error -- never raise, never fall back to
        # spend.jsonl under ccdash's label. This runs wherever ccdash is absent
        # too, so the degrade path is exercised in CI.
        ledger_rows = [make_row(agent_id="a1")]
        metrics = (
            ("ccdash_token_split", lambda: at.ccdash_token_split()),
            ("ccdash_cache_ttl_split", lambda: at.ccdash_cache_ttl_split()),
            ("ccdash_spend_by_model", lambda: at.ccdash_spend_by_model()),
            (
                "ccdash_agent_type_join",
                lambda: at.ccdash_agent_type_join(ledger_rows, since_iso="2026-09-01T00:00:00Z"),
            ),
        )
        for name, call in metrics:
            result = call()
            assert result["ccdash_available"] is False, name
            assert isinstance(result["reason"], str) and "no ccdash" in result["reason"], name

    def test_empty_database_degrades_explicitly(self, ccdash_db):
        """A real db file with a real schema but zero rows (a fresh
        usage-dashboard checkout that has never scanned) must not be
        confused with n=0-but-available -- it is UNAVAILABLE, with a reason
        naming the empty table, not a metric silently returning zeroes."""
        # ccdash_db's own fixture setup already creates the schema (via
        # get_connection()) without inserting any row -- calling ccdash_status
        # directly exercises exactly that state, since `insert` is never called.
        status = at.ccdash_status()
        assert status["available"] is False
        assert "empty" in status["reason"]


class TestCcdashAbsentVersusBroken:
    """ccdash is optional, so its tests skip when it is not installed -- but only
    then. A ccdash that is present and fails to import must make its tests FAIL
    with the recorded error, or a broken install hides as "optional" (30 tests
    quietly skipped)."""

    def test_an_imported_ccdash_is_present(self):
        assert _classify_ccdash(object(), None) == "present"

    def test_a_missing_ccdash_package_is_absent(self):
        assert _classify_ccdash(None, "ModuleNotFoundError: No module named 'ccdash'") == "absent"

    @pytest.mark.parametrize(
        "import_error",
        [
            # a dependency OF ccdash is what is missing: ccdash is installed, damaged
            "ModuleNotFoundError: No module named 'numpy'",
            # ccdash is a package but lacks / cannot load its submodule
            "ModuleNotFoundError: No module named 'ccdash.parser'",
            "ImportError: cannot import name 'parser' from 'ccdash'",
            "SyntaxError: invalid syntax (parser.py, line 3)",
            "AttributeError: partially initialized module 'ccdash' has no attribute 'x'",
            None,
            "",
        ],
    )
    def test_any_other_import_failure_is_broken_not_absent(self, import_error):
        assert _classify_ccdash(None, import_error) == "broken"

    def test_a_broken_ccdash_fails_with_the_import_error_not_a_skip(self, monkeypatch):
        monkeypatch.setattr(at, "ccdash_parser", None)
        monkeypatch.setattr(at, "CCDASH_IMPORT_ERROR", "SyntaxError: invalid syntax (parser.py, line 3)")
        with pytest.raises(pytest.fail.Exception) as raised:
            _require_ccdash()
        assert "SyntaxError: invalid syntax (parser.py, line 3)" in str(raised.value)

    def test_an_absent_ccdash_skips_with_the_stated_reason(self, monkeypatch):
        monkeypatch.setattr(at, "ccdash_parser", None)
        monkeypatch.setattr(at, "CCDASH_IMPORT_ERROR", _CCDASH_NOT_INSTALLED_ERROR)
        with pytest.raises(pytest.skip.Exception) as raised:
            _require_ccdash()
        assert "not installed" in str(raised.value)


class TestCcdashTokenSplit:
    def test_subagent_vs_main_thread_split_is_a_real_headline(self, ccdash_db):
        """A fact spend.jsonl could never show: it has no is_sidechain
        equivalent at all. Fixture: 3 sidechain rows of 100 tokens each (300
        total) vs 1 main-thread row of 100 tokens -- wrong implementation
        that ignores is_sidechain reports a 50/50-looking blend instead of
        the true 75/25 split.
        """
        for i in range(3):
            ccdash_db(agent_id=f"sub{i}", is_sidechain=1, input_tokens=100, output_tokens=0)
        ccdash_db(agent_id="main1", is_sidechain=0, input_tokens=100, output_tokens=0)

        result = at.ccdash_token_split()
        assert result["ccdash_available"] is True
        assert result["n"] == 4
        assert result["subagent_tokens"].value == 300
        assert result["main_thread_tokens"].value == 100
        assert result["subagent_token_share"].value == 0.75
        assert result["subagent_token_share"].provenance == at.DERIVED

    def test_window_excludes_rows_outside_since_iso(self, ccdash_db):
        """The windowed call must not silently include rows outside the
        requested window -- a wrong implementation that ignores since_iso
        would report the lifetime total under a 7-day label."""
        ccdash_db(agent_id="old", is_sidechain=1, timestamp_utc="2026-08-01T00:00:00Z",
                  input_tokens=1000, output_tokens=0)
        ccdash_db(agent_id="new", is_sidechain=1, timestamp_utc="2026-09-05T00:00:00Z",
                  input_tokens=100, output_tokens=0)

        windowed = at.ccdash_token_split(since_iso="2026-09-01T00:00:00Z")
        assert windowed["n"] == 1
        assert windowed["subagent_tokens"].value == 100

        lifetime = at.ccdash_token_split()
        assert lifetime["n"] == 2
        assert lifetime["subagent_tokens"].value == 1100

    def test_synthetic_marker_rows_are_excluded(self, ccdash_db):
        """`<synthetic>` is Claude Code's own internal marker for
        locally-injected messages that never hit the API -- it must never
        count as real usage, mirroring aggregate.load_rows's own filter."""
        ccdash_db(agent_id="real", model="claude-sonnet-5", input_tokens=100, output_tokens=0)
        ccdash_db(agent_id="fake", model="<synthetic>", input_tokens=99999, output_tokens=0)
        result = at.ccdash_token_split()
        assert result["n"] == 1
        assert result["main_thread_tokens"].value == 100


class TestCcdashCacheTtlSplit:
    def test_5m_and_1h_writes_are_reported_separately(self, ccdash_db):
        """The plan's own note called this unattributable from spend.jsonl
        (it collapses both TTLs into one cache_creation bucket) -- ccdash
        carries them as separate columns and this metric must actually split
        them, not just repeat the unattributable claim under a new name."""
        ccdash_db(agent_id="a1", ephemeral_5m_tokens=700, ephemeral_1h_tokens=300, cache_read_input_tokens=0)
        result = at.ccdash_cache_ttl_split()
        assert result["ccdash_available"] is True
        assert result["writes_5m_tokens"].value == 700
        assert result["writes_1h_tokens"].value == 300
        assert result["writes_5m_tokens"].provenance == at.ORIGINAL
        assert result["writes_1h_tokens"].provenance == at.ORIGINAL
        assert result["share_1h_of_writes"].value == 0.3

    def test_ttl_split_is_no_longer_unattributable_when_ccdash_available(self, ccdash_db):
        """The stale claim this task requires fixing: `cache_detail()`'s own
        ttl_split field (spend.jsonl-sourced) stays unattributable by
        necessity, but that must not be read as 'the fleet cannot know this
        at all' -- ccdash_cache_ttl_split proves the split IS knowable."""
        ccdash_db(agent_id="a1", ephemeral_5m_tokens=100, ephemeral_1h_tokens=50)
        ccdash_result = at.ccdash_cache_ttl_split()
        assert ccdash_result["writes_1h_tokens"].provenance != at.UNATTRIBUTABLE

        ledger_result = at.cache_detail([make_row(agent_id="a1")])
        assert ledger_result["ttl_split"].provenance == at.UNATTRIBUTABLE


class TestCcdashSpendByModel:
    def test_fable_recovers_its_real_share_from_complete_data(self, ccdash_db):
        """THE headline defect this task exists to fix. Fixture: one Fable
        row that a hook-based ledger would likely miss (no agent_id join
        needed here -- ccdash prices every row it parsed, unconditionally)
        alongside one Sonnet row of equal token volume -- a correct
        implementation must show them at comparable spend, not Fable at a
        tiny fraction the way spend.jsonl would if it had dropped most of
        Fable's rows to model=null.
        """
        ccdash_db(agent_id="f1", model="claude-fable-5", input_tokens=1_000_000, output_tokens=0)
        ccdash_db(agent_id="s1", model="claude-sonnet-5", input_tokens=1_000_000, output_tokens=0)
        result = at.ccdash_spend_by_model()
        assert result["ccdash_available"] is True
        by_model = result["by_model"].value
        assert "claude-fable-5" in by_model
        assert "claude-sonnet-5" in by_model
        # Published input rates: Fable 5 = $10/MTok, Sonnet 5 = $2/MTok, so
        # equal token volumes must show a 5.0x ratio exactly.
        #
        # UPDATED 2026-09-05: the Sonnet leg was $3/MTok until ccdash's stale
        # intro-pricing date branch was removed (Anthropic cancelled the
        # 2026-09-01 rise back to $3/$15; $2/$10 is the standard price), which
        # moved this ratio from 3.33x to 5.0x and made the old EXCLUSIVE upper
        # bound of 5.0 fail on the boundary. Both rates are asserted
        # explicitly, so a future rate change fails loudly here instead of
        # silently sliding the ratio.
        assert by_model["claude-fable-5"] == pytest.approx(10.00, rel=1e-6)
        assert by_model["claude-sonnet-5"] == pytest.approx(2.00, rel=1e-6)
        ratio = by_model["claude-fable-5"] / by_model["claude-sonnet-5"]
        assert ratio == pytest.approx(5.0, rel=1e-6)
        # The original intent of this test, kept: Fable must show a REAL,
        # comparable share -- never the ~24x-understated sliver that a
        # model=null-dropping ledger produced.
        assert ratio > 1.5, "Fable must show a real, comparable share, not a rounding error"

    def test_unpriceable_rows_excluded_never_priced_at_zero(self, ccdash_db):
        """Mirrors spend_usd()'s own discipline exactly -- a second source
        must not re-introduce the $0-pricing defect the first source was
        already fixed against."""
        ccdash_db(agent_id="known", model="claude-sonnet-5", input_tokens=1000)
        ccdash_db(agent_id="unknown", model="claude-imaginary-9", input_tokens=999999)
        result = at.ccdash_spend_by_model()
        assert result["n"] == 1
        assert result["unpriceable"]["rows"].value == 1
        assert "claude-imaginary-9" in result["unpriceable"]["by_model"].value
        assert result["pricing_coverage"].value == 0.5

    def test_no_fourth_pricing_table(self):
        """Constraint from the task: this module must call INTO
        ccdash.pricing, never redefine rates of its own."""
        _require_ccdash()
        assert at.ccdash_pricing.compute_cost_usd is not None
        # The function actually used by ccdash_spend_by_model must be the
        # real module attribute, not a local reimplementation -- verified by
        # identity, the same style TestPricing uses for cycle_budget.
        import ccdash.pricing as real_ccdash_pricing

        assert at.ccdash_pricing is real_ccdash_pricing


class TestCcdashAgentTypeJoin:
    def test_join_recovers_per_agent_type_spend_from_complete_tokens(self, ccdash_db):
        """The single highest-value join: ccdash has complete tokens but no
        agent_type; spend.jsonl has agent_type but only for priced rows.
        Fixture: a ledger row naming 'implement' for agent_id 'a1', and a
        ccdash row for that SAME agent_id with real tokens -- the join must
        attribute ccdash's dollar figure to 'implement', not report it as
        unattributed the way spend.jsonl alone would if this row had no
        model.
        """
        ccdash_db(agent_id="a1", model="claude-sonnet-5", input_tokens=1_000_000, output_tokens=0,
                  timestamp_utc="2026-09-05T00:00:00Z")
        ledger_rows = [make_row(agent_id="a1", agent_type="implement", tool_use_id="t1")]

        result = at.ccdash_agent_type_join(ledger_rows, since_iso="2026-09-01T00:00:00Z")
        assert result["ccdash_available"] is True
        assert result["n"] == 1
        # 1M sonnet-5 input tokens at the published $2.00/MTok. (Was 3.00 until
        # 2026-09-05: ccdash carried a stale intro-pricing date branch that
        # reverted sonnet-5 to $3/$15 after 2026-08-31, but Anthropic cancelled
        # that increase and $2/$10 is the standard price. The rate is asserted
        # explicitly rather than derived from the pricing table, so this test
        # keeps proving the JOIN attributes real dollars to a named type -- a
        # value derived from the same table it prices with would assert nothing.)
        assert result["by_agent_type_usd"].value.get("implement") == pytest.approx(2.00, rel=1e-6)

    def test_unmatched_agent_id_is_not_folded_into_a_named_type(self, ccdash_db):
        """A ccdash row whose agent_id has no ledger match at all must not
        silently vanish into some other agent's total or get attributed to
        a name it never carried."""
        ccdash_db(agent_id="orphan", model="claude-sonnet-5", input_tokens=1000,
                  timestamp_utc="2026-09-05T00:00:00Z")
        ledger_rows = [make_row(agent_id="a1", agent_type="implement", tool_use_id="t1")]
        result = at.ccdash_agent_type_join(ledger_rows, since_iso="2026-09-01T00:00:00Z")
        assert result["n"] == 0
        assert result["by_agent_type_usd"].value == {}
        assert result["total_ccdash_rows_in_window"].value == 1

    def test_since_iso_is_required_and_the_reason_is_stated(self, ccdash_db):
        """Task constraint: an unwindowed call must never silently report the
        misleading lifetime rate (measured 11%) as if it were normal --
        this function refuses outright rather than let a caller forget.

        Requires ccdash to genuinely be available first (a real row must be
        inserted) -- otherwise this test could pass for the wrong reason
        (ccdash being unavailable) rather than the one under test (since_iso
        being omitted).
        """
        ccdash_db(agent_id="a1", model="claude-sonnet-5", input_tokens=100,
                  timestamp_utc="2026-09-05T00:00:00Z")
        ledger_rows = [make_row(agent_id="a1", agent_type="implement")]
        result = at.ccdash_agent_type_join(ledger_rows, since_iso=None)
        assert result["ccdash_available"] is True
        assert result.get("renderable") is False
        assert "since_iso is required" in result["error"]

    def test_join_rate_is_reported_and_low_confidence_is_labeled_honestly(self, ccdash_db):
        """The task's own constraint: measure the join rate, never assume it
        clean, and fall back (label as low-confidence) rather than fabricate
        a join over a population where it mostly fails. Fixture: 1 of 4
        ccdash rows in the window matches a ledger agent_id -- 25%, well
        below the 50% reliability floor.
        """
        ccdash_db(agent_id="matched", model="claude-sonnet-5", input_tokens=100,
                  timestamp_utc="2026-09-05T00:00:00Z")
        for i in range(3):
            ccdash_db(agent_id=f"orphan{i}", model="claude-sonnet-5", input_tokens=100,
                      timestamp_utc="2026-09-05T00:00:00Z")
        ledger_rows = [make_row(agent_id="matched", agent_type="implement", tool_use_id="t1")]

        result = at.ccdash_agent_type_join(ledger_rows, since_iso="2026-09-01T00:00:00Z")
        assert result["join_rate"].value == 0.25
        assert result["reliable"] is False
        assert "LOW CONFIDENCE" in result["note"]

    def test_generic_and_missing_agent_types_do_not_count_as_real_attribution(self, ccdash_db):
        """A ledger agent_id whose agent_type is missing or one of the
        client's generic buckets (e.g. 'general-purpose') must not be
        treated as a real join target -- that would attribute ccdash's
        complete dollar data to a non-persona, which is exactly the
        laundering the provenance rule exists to prevent."""
        ccdash_db(agent_id="a1", model="claude-sonnet-5", input_tokens=1000,
                  timestamp_utc="2026-09-05T00:00:00Z")
        ledger_rows = [make_row(agent_id="a1", agent_type="general-purpose", tool_use_id="t1")]
        result = at.ccdash_agent_type_join(ledger_rows, since_iso="2026-09-01T00:00:00Z")
        assert result["n"] == 0, "a generic bucket must not be joined as if it were a real persona"


# ---------------------------------------------------------------------------
# account_capacity (added 2026-09-06, operator finding).
#
# The operator's actual cost structure: SIX Claude Max seats at $200/mo each
# ($1,200/mo FIXED, not metered API billing) -- so the scarce resource is
# per-account QUOTA, not dollars, and "am I load-balancing across the
# capacity I already pay for" is the question this metric answers.
# `session_accounts` is written by a SEPARATE hook
# (usage-dashboard/hooks/session_account_snapshot.py), not by ccdash's own
# schema -- so every test in this class creates it itself on the SAME
# throwaway `ccdash_db` fixture's database, exactly mirroring the real
# runtime's two-hook write pattern.
# ---------------------------------------------------------------------------


@pytest.fixture
def session_accounts_table(ccdash_db):
    """Creates `session_accounts` on the SAME throwaway db `ccdash_db` uses,
    and returns an `insert(session_id, email, ...)` helper.

    `ccdash_db` must run FIRST (it monkeypatches `DB_PATH` to the throwaway
    file) -- depending on it here, rather than monkeypatching independently,
    guarantees this table is created on the exact same file every
    ccdash-backed function in this test will open.
    """
    conn = at.ccdash_parser.get_connection()
    conn.execute(
        """
        CREATE TABLE session_accounts (
            session_id TEXT PRIMARY KEY,
            account_uuid TEXT,
            email TEXT,
            org_uuid TEXT,
            org_name TEXT,
            org_type TEXT,
            seat_tier TEXT,
            hook_source TEXT,
            recorded_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    def insert(session_id: str, email: str, recorded_at: str = "2026-09-05T00:00:00Z") -> None:
        conn = at.ccdash_parser.get_connection()
        conn.execute(
            "INSERT INTO session_accounts (session_id, email, recorded_at) VALUES (?, ?, ?)",
            (session_id, email, recorded_at),
        )
        conn.commit()
        conn.close()

    return insert


class TestAccountCapacity:
    def test_missing_session_accounts_table_degrades_explicitly_never_crashes(self, ccdash_db):
        """THE defect found while building this metric: `session_accounts` is
        written by a DIFFERENT hook than the one that creates `usage_events`,
        so a database that has real usage rows but has never had that other
        hook run against it is missing the table entirely. Before the fix,
        this raised a raw sqlite3.OperationalError straight out of
        `account_capacity()` -- exactly the crash this module's ccdash
        metrics otherwise never produce."""
        ccdash_db(agent_id="a1", model="claude-sonnet-5", input_tokens=100)
        result = at.account_capacity()
        assert result["ccdash_available"] is False
        assert "session_accounts" in result["reason"]

    def test_per_account_calls_and_share_from_the_join(self, ccdash_db, session_accounts_table):
        """The headline fact: which of six paid seats is actually doing the
        work. Fixture: account A gets 3 calls, account B gets 1 -- a correct
        implementation reports A at 75% share, never a 50/50 split that
        ignores which session did the work."""
        session_accounts_table("sess-a", "a@example.com")
        session_accounts_table("sess-b", "b@example.com")
        for _ in range(3):
            ccdash_db(agent_id="x", model="claude-sonnet-5", input_tokens=100,
                      timestamp_utc="2026-09-05T00:00:00Z")
        # ccdash_db's own `insert()` has no top_session_id parameter, so
        # patch it in directly via a second raw insert carrying one.
        conn = at.ccdash_parser.get_connection()
        conn.execute(
            "UPDATE usage_events SET top_session_id = 'sess-a' WHERE agent_id = 'x'"
        )
        conn.commit()
        conn.close()
        ccdash_db(agent_id="y", model="claude-sonnet-5", input_tokens=100,
                  timestamp_utc="2026-09-05T00:00:00Z")
        conn = at.ccdash_parser.get_connection()
        conn.execute(
            "UPDATE usage_events SET top_session_id = 'sess-b' WHERE agent_id = 'y'"
        )
        conn.commit()
        conn.close()

        result = at.account_capacity()
        assert result["ccdash_available"] is True
        assert result["n"] == 4
        accounts = result["accounts"]
        assert accounts["a@example.com"]["calls"].value == 3
        assert accounts["b@example.com"]["calls"].value == 1
        assert accounts["a@example.com"]["share_of_attributed_calls"].value == 0.75
        assert accounts["b@example.com"]["share_of_attributed_calls"].value == 0.25

    def test_unattributed_rows_are_counted_never_folded_into_an_account(
        self, ccdash_db, session_accounts_table
    ):
        """A usage row whose top_session_id has no session_accounts match
        must be counted separately, never silently dropped or attributed to
        whichever account happens to be first."""
        session_accounts_table("sess-known", "known@example.com")
        ccdash_db(agent_id="a1", model="claude-sonnet-5", input_tokens=100)
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-known' WHERE agent_id = 'a1'")
        conn.commit()
        conn.close()
        # A second row whose top_session_id matches nothing.
        ccdash_db(agent_id="a2", model="claude-sonnet-5", input_tokens=100)
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-orphan' WHERE agent_id = 'a2'")
        conn.commit()
        conn.close()

        result = at.account_capacity()
        assert result["ccdash_available"] is True
        assert result["n"] == 1, "only the attributed row counts toward the denominator"
        assert result["unattributed_rows"].value == 1
        assert result["total_rows_seen"] == 2
        assert list(result["accounts"]) == ["known@example.com"]

    def test_imbalance_names_the_busiest_account_and_counts_idle_ones(
        self, ccdash_db, session_accounts_table
    ):
        """The ACTIONABLE signal: one account carries the load, several sit
        idle relative to it. Fixture: account A gets 80 calls, B gets 19
        (well ABOVE 10% of A's share -- not idle), C gets 1 (well BELOW --
        idle); a wrong implementation that reports only a bare 'imbalanced'
        verdict with no denominator would be unfalsifiable."""
        session_accounts_table("sess-a", "a@example.com")
        session_accounts_table("sess-b", "b@example.com")
        session_accounts_table("sess-c", "c@example.com")
        for i, (sess, n) in enumerate((("sess-a", 80), ("sess-b", 19), ("sess-c", 1))):
            for j in range(n):
                ccdash_db(agent_id=f"a{i}-{j}", model="claude-sonnet-5", input_tokens=10,
                          timestamp_utc="2026-09-05T00:00:00Z")
            conn = at.ccdash_parser.get_connection()
            conn.execute(
                "UPDATE usage_events SET top_session_id = ? WHERE agent_id LIKE ?",
                (sess, f"a{i}-%"),
            )
            conn.commit()
            conn.close()

        result = at.account_capacity()
        imbalance = result["imbalance"]
        assert imbalance["busiest_account"] == "a@example.com"
        assert imbalance["busiest_share"].value == pytest.approx(0.80, rel=1e-6)
        # B's share is 0.19 -- well above 10% of A's 0.80 (0.08) -- and must
        # NOT be flagged; only C (0.01, well under 0.08) is.
        #
        # The field is "quiet", never "idle": an unbounded/short window cannot
        # establish that an account is unused, only that it was quiet in the
        # window. Measured on real data, a 7-day window showed 82% on one
        # account while 30 days showed the same six balanced 35/19/15/12/10/9.
        assert imbalance["quiet_accounts"].value == ["c@example.com"]
        assert imbalance["quiet_account_count"].value == 1
        assert imbalance["account_count"].value == 3
        assert "idle" not in imbalance, (
            "'idle' asserts a conclusion this data cannot support and which was "
            "measured FALSE; the field must stay named 'quiet'."
        )

    def test_an_unpriceable_call_is_excluded_never_counted_as_zero(
        self, ccdash_db, session_accounts_table
    ):
        """An unpriceable model must be EXCLUDED from the dollar figure and
        COUNTED as excluded -- never silently priced at $0.

        Regression guard for review nit 3: a mutation that priced unpriceable
        rows at 0.0 instead of excluding them left the whole suite GREEN. A
        silent $0 understates api-equivalent value and, worse, makes an
        unpriced model invisible -- which is the exact failure class that let
        three pricing tables drift for weeks.
        """
        session_accounts_table("sess-a", "a@example.com")
        # One priceable call and one whose model no pricing table knows.
        ccdash_db(agent_id="p1", model="claude-sonnet-5", input_tokens=1_000_000,
                  output_tokens=0, timestamp_utc="2026-09-05T00:00:00Z")
        ccdash_db(agent_id="u1", model="claude-unpriceable-model-9",
                  input_tokens=1_000_000, output_tokens=0,
                  timestamp_utc="2026-09-05T00:00:00Z")
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-a'")
        conn.commit()
        conn.close()

        result = at.account_capacity()
        acct = result["accounts"]["a@example.com"]
        # $2.00 for the sonnet-5 call ALONE -- the unpriceable one contributes
        # nothing rather than a $0 line that looks like a real priced call.
        assert acct["api_equivalent_usd"].value == pytest.approx(2.00, rel=1e-6)
        # ...and the exclusion is COUNTED, per account, so it is visible
        # rather than merely absent.
        assert acct["unpriced_calls"].value == 1
        assert acct["calls"].value == 2, "both calls still counted as calls"

    def test_a_window_shorter_than_the_billing_period_warns(
        self, ccdash_db, session_accounts_table
    ):
        """A capacity read over less than one quota cycle must SAY SO.

        Regression guard for the 2026-09-06 correction: Claude Max quota resets
        monthly, so a 7-day slice of a monthly cycle is not a smaller version of
        the same picture -- it is a different and misleading one. On real data it
        showed 82% concentration where the billing period showed balance, and
        nearly drove a recommendation to consolidate actively-used seats.
        """
        import datetime as _dt

        session_accounts_table("sess-a", "a@example.com")
        # RELATIVE to now, never a hardcoded date. This test compares a
        # `now - 7 days` window against a `now - 45 days` one, so a fixed
        # "2026-09-05" seed sat inside the short window when this was
        # written and fell OUTSIDE it from 2026-09-12 onward -- leaving
        # n=0, which account_capacity correctly refuses with
        # PartitionError. The test then failed for a CALENDAR reason
        # rather than a behavioural one, which is worse than useless: it
        # reports a defect that does not exist while no longer checking
        # the one it was written for.
        _seed = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)
        ccdash_db(agent_id="x1", model="claude-sonnet-5", input_tokens=10,
                  timestamp_utc=_seed.strftime("%Y-%m-%dT%H:%M:%SZ"))
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-a'")
        conn.commit()
        conn.close()

        short = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7)).isoformat()
        full = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=45)).isoformat()

        short_imb = at.account_capacity(since_iso=short)["imbalance"]
        assert short_imb["window_covers_billing_period"] is False
        assert short_imb["window_warning"] is not None
        assert "resets every 30 days" in short_imb["window_warning"]

        full_imb = at.account_capacity(since_iso=full)["imbalance"]
        assert full_imb["window_covers_billing_period"] is True
        assert full_imb["window_warning"] is None

    def test_shares_are_labelled_as_claude_code_work_not_quota(
        self, ccdash_db, session_accounts_table
    ):
        """These shares must never be readable as 'share of quota consumed'.

        ccdash sees only Claude Code transcripts on this machine; claude.ai web
        and Desktop draw on the same quota invisibly, so these figures cannot
        reconcile with the console's percent-of-quota and must not imply they do.
        """
        session_accounts_table("sess-a", "a@example.com")
        ccdash_db(agent_id="x1", model="claude-sonnet-5", input_tokens=10,
                  timestamp_utc="2026-09-05T00:00:00Z")
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-a'")
        conn.commit()
        conn.close()

        note = at.account_capacity()["imbalance"]["scope_note"]
        assert "NOT share of quota" in note
        assert "claude.ai web" in note

    def test_daily_calls_series_is_reported_per_account(self, ccdash_db, session_accounts_table):
        """The DAILY series the task requires -- not just a snapshot share --
        so a caller can plot a load-balance TREND."""
        session_accounts_table("sess-a", "a@example.com")
        for day, n in (("2026-09-01T00:00:00Z", 2), ("2026-09-02T00:00:00Z", 5)):
            for j in range(n):
                ccdash_db(agent_id=f"d{day}-{j}", model="claude-sonnet-5", input_tokens=10,
                          timestamp_utc=day)
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-a'")
        conn.commit()
        conn.close()

        result = at.account_capacity()
        daily = result["accounts"]["a@example.com"]["daily_calls"].value
        assert daily == {"2026-09-01": 2, "2026-09-02": 5}

    def test_api_equivalent_usd_is_priced_through_ccdash_pricing_not_a_new_table(
        self, ccdash_db, session_accounts_table
    ):
        """Constraint from the task: never a second pricing table. Fixture:
        1M sonnet-5 input tokens at the published $2/MTok rate."""
        session_accounts_table("sess-a", "a@example.com")
        ccdash_db(agent_id="a1", model="claude-sonnet-5", input_tokens=1_000_000, output_tokens=0,
                  timestamp_utc="2026-09-05T00:00:00Z")
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-a'")
        conn.commit()
        conn.close()

        result = at.account_capacity()
        assert result["accounts"]["a@example.com"]["api_equivalent_usd"].value == pytest.approx(
            2.00, rel=1e-6
        )

    def test_window_excludes_rows_outside_since_iso(self, ccdash_db, session_accounts_table):
        session_accounts_table("sess-a", "a@example.com")
        ccdash_db(agent_id="old", model="claude-sonnet-5", input_tokens=100,
                  timestamp_utc="2026-08-01T00:00:00Z")
        ccdash_db(agent_id="new", model="claude-sonnet-5", input_tokens=100,
                  timestamp_utc="2026-09-05T00:00:00Z")
        conn = at.ccdash_parser.get_connection()
        conn.execute("UPDATE usage_events SET top_session_id = 'sess-a'")
        conn.commit()
        conn.close()

        windowed = at.account_capacity(since_iso="2026-09-01T00:00:00Z")
        assert windowed["n"] == 1
        assert windowed["accounts"]["a@example.com"]["calls"].value == 1

        lifetime = at.account_capacity()
        assert lifetime["n"] == 2
        assert lifetime["accounts"]["a@example.com"]["calls"].value == 2


# ---------------------------------------------------------------------------
# quality_outcomes (added 2026-09-06, operator finding).
#
# Reads the estimate-engine self-correcting loop's own recorded CONCUR/
# DISSENT verdicts and consolidator_decision findings. Uses a hermetic
# `cycles_dir` (tmp_path) in every test -- the operator's own cycle
# telemetry (~/.claude/telemetry/cycles/) must never be read by a test run,
# mirroring the `ccdash_db` fixture's own throwaway-database discipline for
# ccdash. `cycle_telemetry.write_cycle` builds a spec-valid record without
# this test file needing to know every field that module's own validator
# requires.
# ---------------------------------------------------------------------------


def write_cycle_fixture(cycles_dir, system, cycle_id, verdicts=(), findings=()):
    """A minimal-but-valid cycle record, using `cycle_telemetry`'s own
    validated writer -- never a hand-rolled dict that could drift from what
    the real writer actually produces."""
    import cycle_telemetry as ct

    record = {
        "schema_version": 1,
        "system": system,
        "cycle_id": cycle_id,
        "started_at": "2026-09-01T00:00:00Z",
        "ended_at": "2026-09-01T01:00:00Z",
        "repo": "test-repo",
        "dispatches": [],
        "stages": [],
        "verdicts": list(verdicts),
        "findings": list(findings),
        "calibration": {
            "plant_id": None,
            "planted_in": None,
            "slot": None,
            "caught_by": [],
            "missed_by": [],
        },
        "cost": {"source": "unavailable", "total_tokens": None, "total_usd": None, "reason": "test fixture"},
        "notes": [],
    }
    ct.write_cycle(record, cycles_dir=str(cycles_dir))
    return record


def write_malformed_cycle_file(cycles_dir, system, cycle_id, verdicts=(), findings=()):
    """Writes a cycle JSON file DIRECTLY, bypassing `write_cycle`'s own
    schema validation.

    Used only for the one test that asserts `quality_outcomes()` tolerates a
    verdict value the CURRENT writer would refuse to produce (e.g. a future
    vocabulary addition, or a legacy/hand-edited file) -- the collector's
    job is to read what is actually on disk, not to assume every file was
    written by today's validator."""
    import cycle_telemetry as ct

    record = {
        "schema_version": 1,
        "system": system,
        "cycle_id": cycle_id,
        "started_at": "2026-09-01T00:00:00Z",
        "ended_at": "2026-09-01T01:00:00Z",
        "repo": "test-repo",
        "dispatches": [],
        "stages": [],
        "verdicts": list(verdicts),
        "findings": list(findings),
        "calibration": {
            "plant_id": None,
            "planted_in": None,
            "slot": None,
            "caught_by": [],
            "missed_by": [],
        },
        "cost": {"source": "unavailable", "total_tokens": None, "total_usd": None, "reason": "test fixture"},
        "notes": [],
    }
    path = ct.cycle_path(system, cycle_id, cycles_dir=str(cycles_dir))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    return record


def make_verdict(dispatch_label, verdict, scenario="s1", problem_count=0, confidence=None):
    return {
        "dispatch_label": dispatch_label,
        "verdict": verdict,
        "scenario": scenario,
        "problem_count": problem_count,
        "confidence": confidence,
    }


def make_finding(finding_id, consolidator_decision, raised_by=("plumbing",)):
    return {
        "finding_id": finding_id,
        "claim_symptom": "x",
        "claim_cause": "y",
        "raised_by": list(raised_by),
        "consolidator_decision": consolidator_decision,
        "already_tracked_as": None,
        "fights_ruling": None,
        "fix_status": None,
        "verifier_verdict": None,
        "verifier_cause_upheld": None,
    }


class TestQualityOutcomes:
    def test_missing_cycles_directory_degrades_explicitly(self, tmp_path):
        """No loop has ever run on this machine, or the directory does not
        exist yet -- must say so in plain English, never crash and never
        report a fabricated 0% dissent rate over zero data."""
        result = at.quality_outcomes(cycles_dir=str(tmp_path / "nonexistent"))
        assert result["cycle_telemetry_available"] is False
        assert isinstance(result["reason"], str) and result["reason"]

    def test_empty_cycles_directory_degrades_explicitly(self, tmp_path):
        (tmp_path / "cycles").mkdir()
        result = at.quality_outcomes(cycles_dir=str(tmp_path / "cycles"))
        assert result["cycle_telemetry_available"] is False

    def test_concur_and_dissent_are_counted_and_rated(self, tmp_path):
        """The headline count this task exists to surface. Fixture: 3
        CONCUR + 1 DISSENT -- a wrong implementation that counts verdicts by
        RECORD instead of by individual verdict entry would report n=2
        (two cycle files) instead of n=4."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "trade_round_1",
            verdicts=[
                make_verdict("plumbing:s1", "CONCUR"),
                make_verdict("plumbing:s2", "CONCUR"),
            ],
        )
        write_cycle_fixture(
            cycles, "sys", "trade_round_2",
            verdicts=[
                make_verdict("plumbing:s3", "CONCUR"),
                make_verdict("plumbing:s4", "DISSENT"),
            ],
        )
        result = at.quality_outcomes(cycles_dir=str(cycles))
        assert result["cycle_telemetry_available"] is True
        assert result["n"] == 4
        assert result["verdicts"]["concur"].value == 3
        assert result["verdicts"]["dissent"].value == 1
        assert result["verdicts"]["dissent_rate"].value == 0.25

    def test_dissent_rate_by_trade_excludes_thin_trades(self, tmp_path):
        """The task's own floor: a rate off too few verdicts is 'one data
        point wearing a statistical costume'. Fixture: 'plumbing' gets 12
        verdicts (rateable), 'tile' gets 3 (must be excluded, not shown off
        a handful of samples)."""
        cycles = tmp_path / "cycles"
        verdicts = [make_verdict(f"plumbing:s{i}", "CONCUR") for i in range(10)]
        verdicts += [make_verdict("plumbing:s10", "DISSENT"), make_verdict("plumbing:s11", "DISSENT")]
        verdicts += [make_verdict(f"tile:s{i}", "CONCUR") for i in range(3)]
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=verdicts)

        result = at.quality_outcomes(cycles_dir=str(cycles))
        by_trade = result["dissent_rate_by_trade"].value
        assert "plumbing" in by_trade
        assert by_trade["plumbing"]["n"] == 12
        # The metric rounds to 4 decimal places (matching this module's own
        # convention elsewhere), so compare against that same rounding.
        assert by_trade["plumbing"]["dissent_rate"].value == round(2 / 12, 4)
        assert "tile" not in by_trade
        assert result["dissent_rate_by_trade_excluded_thin"].value == {"tile": 3}

    def test_trade_name_case_variants_fold_together(self, tmp_path):
        """Mirrors this module's own agent_type normalization: 'GC' (12
        verdicts) and 'gc' (170 verdicts) measured live as two literal case
        variants of one trade -- they must rate as ONE trade, not two."""
        cycles = tmp_path / "cycles"
        verdicts = [make_verdict(f"GC:s{i}", "CONCUR") for i in range(6)]
        verdicts += [make_verdict(f"gc:s{i}", "DISSENT") for i in range(6)]
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=verdicts)

        result = at.quality_outcomes(cycles_dir=str(cycles))
        by_trade = result["dissent_rate_by_trade"].value
        assert list(by_trade.keys()) == ["gc"], "case variants must fold into ONE key"
        assert by_trade["gc"]["n"] == 12
        assert by_trade["gc"]["dissent_rate"].value == 0.5

    def test_round_number_is_parsed_not_string_sorted(self, tmp_path):
        """THE task's own named defect: 'round_10' before 'round_2' under a
        naive string sort. Fixture: round_2 at a high dissent rate, round_10
        at a low one -- a string-sorted series would place round_10 BEFORE
        round_2, inverting the trend a reader would see."""
        cycles = tmp_path / "cycles"
        for n, rate_verdicts in (
            (2, [make_verdict("plumbing:s1", "DISSENT")] * 10),
            (10, [make_verdict("plumbing:s1", "CONCUR")] * 10),
        ):
            write_cycle_fixture(cycles, "sys", f"trade_round_{n}", verdicts=rate_verdicts)

        result = at.quality_outcomes(cycles_dir=str(cycles))
        series = result["convergence_by_round"].value
        rounds_in_order = [r["round"] for r in series]
        assert rounds_in_order == sorted(rounds_in_order), "must be numerically ordered"
        assert rounds_in_order == [2, 10]
        # The wrong (string-sort) order this fixture would produce if a
        # naive `sorted(strings)` were used instead of parsing the number.
        wrong_order = sorted(["trade_round_2", "trade_round_10"])
        assert wrong_order == ["trade_round_10", "trade_round_2"], "the wrong order this guards against"
        by_round = {r["round"]: r["dissent_rate"] for r in series}
        assert by_round[2] == 1.0
        assert by_round[10] == 0.0

    def test_cycle_ids_without_a_parseable_round_are_counted_not_dropped(self, tmp_path):
        """A cycle_id like 'gcreview_demo_2026-09-05' (measured live, one of
        19 real cycle files) carries no round number at all -- its verdicts
        still count toward every OTHER total, and the exclusion itself is
        reported rather than silently shrinking the round series."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "gcreview_demo_2026-09-05",
            verdicts=[make_verdict("gc:s1", "CONCUR")],
        )
        result = at.quality_outcomes(cycles_dir=str(cycles))
        assert result["n"] == 1, "the verdict still counts toward the overall total"
        assert result["convergence_by_round"].value == [], "no round-numbered series entry"
        assert result["rounds_without_a_parseable_number"].value == 1

    def test_findings_by_consolidator_decision_are_counted(self, tmp_path):
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "trade_round_1",
            verdicts=[make_verdict("plumbing:s1", "CONCUR")],
            findings=[
                make_finding("f1", "CONTESTED"),
                make_finding("f2", "CONTESTED"),
                make_finding("f3", "ACCEPT"),
            ],
        )
        result = at.quality_outcomes(cycles_dir=str(cycles))
        assert result["findings"]["total"] == 3
        assert result["findings"]["by_consolidator_decision"].value == {"CONTESTED": 2, "ACCEPT": 1}

    def test_unrecognized_verdict_value_is_counted_separately_never_folded_in(self, tmp_path):
        """A verdict value that is neither CONCUR nor DISSENT (a future
        vocabulary addition, or a malformed record) must not silently
        inflate either rate. Uses `write_malformed_cycle_file` because
        `cycle_telemetry`'s OWN writer refuses to persist an unrecognized
        verdict value -- this collector must still tolerate a file that
        exists on disk regardless of how it got there."""
        cycles = tmp_path / "cycles"
        write_malformed_cycle_file(
            cycles, "sys", "trade_round_1",
            verdicts=[make_verdict("plumbing:s1", "CONCUR"), make_verdict("plumbing:s2", "ABSTAIN")],
        )
        result = at.quality_outcomes(cycles_dir=str(cycles))
        assert result["verdicts"]["other"].value == {"ABSTAIN": 1}
        assert result["verdicts"]["concur"].value == 1
        assert result["verdicts"]["dissent"].value == 0
        assert result["n"] == 2, "the unrecognized verdict still counts toward the total denominator"

    def test_multiple_systems_are_all_read(self, tmp_path):
        """The task's own framing ('read the cycle telemetry') is not scoped
        to one system's name -- verdicts from a different system directory
        under the same cycles root must count too."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(cycles, "sys-a", "trade_round_1", verdicts=[make_verdict("gc:s1", "CONCUR")])
        write_cycle_fixture(cycles, "sys-b", "trade_round_1", verdicts=[make_verdict("gc:s2", "DISSENT")])
        result = at.quality_outcomes(cycles_dir=str(cycles))
        assert result["n"] == 2
        assert result["cycles_read"].value == 2


# ---------------------------------------------------------------------------
# cost_vs_quality (added 2026-09-06, operator finding).
#
# THE JOIN this task exists to build: cost (spend_usd().by_agent_type) and
# quality (quality_outcomes().dissent_rate_by_trade) render as two panels
# that share no axis today. These tests assert the join resolves by
# DERIVATION (never a hardcoded roster), that a trade with no ledger match
# keeps its quality figures with an explicit unjoined cost (never $0), that
# thin trades are excluded via the SAME floor quality_outcomes() already
# uses, and that usd_per_verdict divides correctly.
#
# Fixtures build REAL ledger rows and call the REAL at.spend_usd(rows) --
# never a hand-rolled spend_usd()-shaped dict -- so these tests exercise the
# same cost path collect_all() does, mirroring this file's existing
# never-fork discipline.
# ---------------------------------------------------------------------------


def _rated_verdicts(trade: str, n_concur: int, n_dissent: int) -> list[dict]:
    """`n_concur` + `n_dissent` verdicts for one trade, enough to clear
    DISSENT_RATE_MIN_VERDICTS by construction of the caller's own counts."""
    out = [make_verdict(f"{trade}:c{i}", "CONCUR") for i in range(n_concur)]
    out += [make_verdict(f"{trade}:d{i}", "DISSENT") for i in range(n_dissent)]
    return out


class TestCostVsQuality:
    def test_quality_unavailable_is_reported_as_its_own_reason(self, tmp_path):
        """Three distinct unavailability reasons must never collapse into
        one generic 'unavailable' -- this is the quality-side one."""
        quality = at.quality_outcomes(cycles_dir=str(tmp_path / "nonexistent"))
        rows = [make_row(agent_type="general-contractor", agent_id="a1", tool_use_id="t1")]
        spend = at.spend_usd(rows)
        result = at.cost_vs_quality(quality, spend)
        assert result["renderable"] is False
        assert "quality unavailable" in result["reason"]

    def test_cost_unavailable_is_reported_as_its_own_reason(self, tmp_path):
        """The cost-side unavailability reason, distinct from the quality one
        above -- a wrong implementation that reports one generic string for
        both would make the two failure modes indistinguishable."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "trade_round_1",
            verdicts=_rated_verdicts("gc", 8, 2),
        )
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        # An empty rows list makes spend_usd() raise PartitionError, exactly
        # like every other partition-dependent metric in this module --
        # collect_all() catches this into an {"error": ...} shape, which is
        # the shape cost_vs_quality() itself must accept as input.
        broken_spend = {"metric": "spend_usd", "error": "spend_usd: refusing to render "
                        "over partition 'all' with n=0", "renderable": False}
        result = at.cost_vs_quality(quality, broken_spend)
        assert result["renderable"] is False
        assert "cost unavailable" in result["reason"]

    def test_join_resolves_by_derivation_not_a_hardcoded_roster(self, tmp_path):
        """THE headline behavior. A trade whose ledger agent_type is
        'trade-<name>' -- a name this module's own roster dict never
        mentions -- must still join, because the resolver DERIVES the match
        rather than looking it up in a fixed table. Fixture uses a fictional
        trade name ('masonry') that could not possibly appear in any
        hardcoded list, to prove the match is genuinely derived."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "trade_round_1",
            verdicts=_rated_verdicts("masonry", 8, 2),
        )
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        ledger_rows = [
            make_row(agent_type="trade-masonry", agent_id="a1", tool_use_id="t1")
        ]
        spend = at.spend_usd(ledger_rows)

        result = at.cost_vs_quality(quality, spend)
        assert result["renderable"] is True
        row = result["rows"]["masonry"]
        assert row["resolved_agent_type"].value == "trade-masonry"
        assert row["resolved_agent_type"].provenance == at.DERIVED
        assert "masonry" not in at.TRADE_AGENT_TYPE_EXCEPTIONS, (
            "the fixture trade must NOT be the one named exception, or this "
            "test would pass for the wrong reason"
        )

    def test_gc_resolves_through_the_one_named_exception(self, tmp_path):
        """'gc' shares no substring with 'general-contractor' -- the only
        trade this is true of -- so it needs the one named exception rather
        than the derived exact/endswith match every other trade uses."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=_rated_verdicts("gc", 5, 5))
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        ledger_rows = [make_row(agent_type="general-contractor", agent_id="a1", tool_use_id="t1")]
        spend = at.spend_usd(ledger_rows)

        result = at.cost_vs_quality(quality, spend)
        row = result["rows"]["gc"]
        assert row["resolved_agent_type"].value == "general-contractor"
        assert row["dissent_rate"].value == 0.5

    def test_unjoined_trade_keeps_quality_and_is_marked_unjoined_never_zero(self, tmp_path):
        """A trade with NO matching ledger agent_type must keep its real
        quality figures (verdicts, dissent_rate) and report cost as
        explicitly UNJOINED -- never dropped from the result, and never
        rendered as a confident $0, which would silently claim the trade is
        free rather than simply unmeasured on the cost side."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "trade_round_1",
            verdicts=_rated_verdicts("phantom_trade", 6, 4),
        )
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        # Ledger carries real agent_type spend, but NONE of it is
        # "trade-phantom_trade" or ends with "phantom_trade".
        ledger_rows = [make_row(agent_type="general-contractor", agent_id="a1", tool_use_id="t1")]
        spend = at.spend_usd(ledger_rows)

        result = at.cost_vs_quality(quality, spend)
        assert result["renderable"] is True
        assert "phantom_trade" in result["rows"], "never dropped"
        row = result["rows"]["phantom_trade"]
        assert row["verdicts"] == 10, "real quality figures are kept"
        assert row["dissent_rate"].value == 0.4
        assert row["resolved_agent_type"].provenance == at.UNATTRIBUTABLE
        assert row["resolved_agent_type"].value is None
        assert row["api_equivalent_usd"].provenance == at.UNATTRIBUTABLE
        assert row["api_equivalent_usd"].value is None, "never a confident $0"
        assert row["usd_per_verdict"].provenance == at.UNATTRIBUTABLE
        assert "phantom_trade" in result["unjoined_trades"].value

    def test_thin_trades_are_excluded_via_the_shared_floor(self, tmp_path):
        """Reuses quality_outcomes()'s OWN DISSENT_RATE_MIN_VERDICTS floor --
        never a second, independently invented one. A trade below the floor
        must not appear in cost_vs_quality()'s rows at all, mirroring
        quality_outcomes()'s own thin-trade exclusion exactly."""
        cycles = tmp_path / "cycles"
        verdicts = _rated_verdicts("plumbing", 8, 2)  # n=10, clears the floor
        verdicts += _rated_verdicts("tile", 2, 1)  # n=3, below the floor
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=verdicts)
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        ledger_rows = [
            make_row(agent_type="trade-plumbing", agent_id="a1", tool_use_id="t1"),
            make_row(agent_type="trade-tile", agent_id="a2", tool_use_id="t2"),
        ]
        spend = at.spend_usd(ledger_rows)

        result = at.cost_vs_quality(quality, spend)
        assert "plumbing" in result["rows"]
        assert "tile" not in result["rows"], "below DISSENT_RATE_MIN_VERDICTS, must be excluded"
        assert result["min_verdicts"] == at.DISSENT_RATE_MIN_VERDICTS

    def test_usd_per_verdict_arithmetic(self, tmp_path):
        """usd_per_verdict = api_equivalent_usd / verdicts, exactly. Fixture:
        2 ledger rows of $2.00 sonnet-5 input each (see make_row's default
        1000 tokens_total / cache-heavy tokens dict -- priced through the
        real cycle_budget table, not a stubbed number) against 10 verdicts,
        so the per-verdict figure is a real division a wrong
        implementation (e.g. dividing by dissent count instead of total
        verdicts) would get wrong in a provable direction."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(
            cycles, "sys", "trade_round_1",
            verdicts=_rated_verdicts("drywall", 7, 3),
        )
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        ledger_rows = [
            make_row(agent_type="trade-drywall", agent_id="a1", tool_use_id="t1"),
            make_row(agent_type="trade-drywall", agent_id="a2", tool_use_id="t2"),
        ]
        spend = at.spend_usd(ledger_rows)
        total_usd = spend["by_agent_type"].value["trade-drywall"]

        result = at.cost_vs_quality(quality, spend)
        row = result["rows"]["drywall"]
        assert row["verdicts"] == 10
        assert row["api_equivalent_usd"].value == round(total_usd, 4)
        assert row["usd_per_verdict"].value == round(total_usd / 10, 4)
        # The wrong (dissent-count) denominator this fixture would catch:
        # dividing by 3 dissents instead of 10 verdicts gives a materially
        # different, provably wrong number.
        wrong = round(total_usd / 3, 4)
        assert row["usd_per_verdict"].value != wrong

    def test_no_rated_trade_at_all_degrades_explicitly(self, tmp_path):
        """Every trade below the floor -- a genuinely thin loop run -- must
        say so rather than report an empty, silently-succeeding result."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=_rated_verdicts("tile", 2, 1))
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        ledger_rows = [make_row(agent_type="trade-tile", agent_id="a1", tool_use_id="t1")]
        spend = at.spend_usd(ledger_rows)

        result = at.cost_vs_quality(quality, spend)
        assert result["renderable"] is False
        assert "no trade carried enough verdicts" in result["reason"]

    def test_provenance_vocabulary_is_respected_throughout(self, tmp_path):
        """Every value in a joined row is a real at.Value with a legal
        provenance -- never a bare number laundered past the Value wrapper."""
        cycles = tmp_path / "cycles"
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=_rated_verdicts("hvac", 6, 4))
        quality = at.quality_outcomes(cycles_dir=str(cycles))
        ledger_rows = [make_row(agent_type="trade-hvac", agent_id="a1", tool_use_id="t1")]
        spend = at.spend_usd(ledger_rows)

        result = at.cost_vs_quality(quality, spend)
        row = result["rows"]["hvac"]
        for field in ("dissent_rate", "resolved_agent_type", "api_equivalent_usd", "usd_per_verdict"):
            assert isinstance(row[field], at.Value)
            assert row[field].provenance in at.PROVENANCES

    def test_wired_into_collect_all(self, tmp_path, monkeypatch):
        """cost_vs_quality must be reachable from collect_all() without a
        second cycles/pricing pass -- verified here by pointing collect_all
        at hermetic tmp_path roots and confirming the joined key exists."""
        ledger_path = write_ledger(
            tmp_path,
            [make_row(agent_type="trade-tile", agent_id="a1", tool_use_id="t1")],
        )
        cycles = tmp_path / "telemetry" / "cycles"
        write_cycle_fixture(cycles, "sys", "trade_round_1", verdicts=_rated_verdicts("tile", 6, 4))
        monkeypatch.setattr(at, "default_ledger_path", lambda environ=None: ledger_path)

        # Capture the REAL function before patching -- the fake must call
        # the original implementation redirected to the hermetic cycles
        # dir, never `at.quality_outcomes` (which, post-patch, would be
        # this very fake, recursing into itself rather than reading data).
        _real_quality_outcomes = at.quality_outcomes

        def _fake_quality_outcomes(cycles_dir=None):
            return _real_quality_outcomes(cycles_dir=str(cycles))

        monkeypatch.setattr(at, "quality_outcomes", _fake_quality_outcomes)
        tel = at.collect_all(ledger_path=ledger_path, include_transcripts=False, ingest=False)
        assert "cost_vs_quality" in tel
        assert tel["cost_vs_quality"]["renderable"] is True
        assert "tile" in tel["cost_vs_quality"]["rows"]


# ---------------------------------------------------------------------------
# The two-depth meta tree (plan §1.2) -- COUNT PARITY, not presence.
# ---------------------------------------------------------------------------


class TestMetaTreeDepths:
    def test_count_parity_across_both_depths(self, tmp_path):
        """A presence-only test passes under a half-blind glob -- which is
        exactly the defect this rule exists to catch (rev 1 claimed the
        workflow depth returned zero files).

        Fixture: 3 flat + 2 workflow. Correct total is 5. A glob that sees
        only the flat depth reports 3; only the workflow depth reports 2.
        """
        root = tmp_path / "projects"
        for i in range(3):
            write_transcript(root, "proj", "sess", f"flat{i}", [assistant_turn()])
        for i in range(2):
            write_transcript(root, "proj", "sess", f"wf{i}", [assistant_turn()], workflow="wf_1")

        counts = at.meta_depth_counts(str(root))
        assert counts["flat"] == 3
        assert counts["workflow"] == 2
        assert counts["total"] == 5
        assert counts["total"] == counts["flat"] + counts["workflow"], "COUNT PARITY"
        assert counts["total"] != counts["flat"], "a flat-only glob would report this"
        assert counts["total"] != counts["workflow"], "a workflow-only glob would report this"

    def test_iter_meta_paths_yields_both_depths(self, tmp_path):
        root = tmp_path / "projects"
        write_transcript(root, "p", "s", "flat1", [assistant_turn()])
        write_transcript(root, "p", "s", "wf1", [assistant_turn()], workflow="wf_a")
        found = {at.agent_id_from_path(p) for p in at.iter_meta_paths(str(root))}
        assert found == {"flat1", "wf1"}

    def test_agent_id_extracted_from_both_file_kinds(self):
        assert at.agent_id_from_path("/x/subagents/agent-abc123.meta.json") == "abc123"
        assert at.agent_id_from_path("/x/subagents/agent-abc123.jsonl") == "abc123"
        assert at.agent_id_from_path("/x/subagents/not-an-agent.txt") is None


# ---------------------------------------------------------------------------
# Transcript-derived metrics
# ---------------------------------------------------------------------------


class TestTranscriptMetrics:
    def test_turns_counts_assistant_messages_only(self, tmp_path):
        root = tmp_path / "projects"
        entries = [
            assistant_turn(),
            {"type": "user", "timestamp": "2026-09-01T12:00:01.000Z"},
            assistant_turn(),
            {"type": "user", "timestamp": "2026-09-01T12:00:02.000Z"},
            assistant_turn(),
        ]
        write_transcript(root, "p", "s", "a1", entries)
        result = at.turns_per_dispatch(str(root))
        assert result["n"] == 1
        assert result["total_turns"].value == 3, "user turns must not be counted"

    def test_tool_calls_are_ordered_not_aggregated(self, tmp_path):
        """Order is what makes loop detection possible; an aggregate Counter
        cannot tell a repeated cycle from unrelated calls."""
        entries = [assistant_turn(tools=["Read", "Bash"]), assistant_turn(tools=["Read"])]
        names = at.ordered_tool_calls(entries)
        assert names == ["Read", "Bash", "Read"], "call ORDER must be preserved"

    def test_tool_call_totals(self, tmp_path):
        root = tmp_path / "projects"
        write_transcript(root, "p", "s", "a1", [assistant_turn(tools=["Read", "Bash", "Read"])])
        result = at.tool_calls_per_dispatch(str(root))
        assert result["total_tool_calls"].value == 3
        assert result["by_tool"].value == {"Read": 2, "Bash": 1}

    def test_true_duration_spans_transcript_timestamps(self, tmp_path):
        """Recovers a duration for dispatches whose ledger duration_ms is
        null, without touching the hook."""
        entries = [
            assistant_turn(ts="2026-09-01T12:00:00.000Z"),
            assistant_turn(ts="2026-09-01T12:05:00.000Z"),
        ]
        assert at.transcript_span_seconds(entries) == 300.0

    def test_single_timestamp_is_unmeasurable_not_zero(self):
        """A lone timestamp gives a span of 0, which reads as an
        instantaneous dispatch rather than an unmeasurable one."""
        assert at.transcript_span_seconds([assistant_turn()]) is None
        assert at.transcript_span_seconds([]) is None

    def test_implausible_spans_are_excluded_and_counted(self, tmp_path):
        """Wall-clock only: machine sleep silently inflates a span, and there
        is no sleep-corrected clock. Such spans are flagged, never averaged
        in and never silently dropped."""
        root = tmp_path / "projects"
        write_transcript(
            root,
            "p",
            "s",
            "sane",
            [assistant_turn(ts="2026-09-01T12:00:00.000Z"), assistant_turn(ts="2026-09-01T12:05:00.000Z")],
        )
        write_transcript(
            root,
            "p",
            "s",
            "slept",
            [assistant_turn(ts="2026-09-01T12:00:00.000Z"), assistant_turn(ts="2026-09-02T12:00:00.000Z")],
        )
        result = at.true_duration(str(root))
        assert result["n"] == 1, "only the plausible span counts"
        assert result["implausible_spans_excluded"].value == 1
        assert result["p50_sec"].value == 300.0

    def test_call_graph_reports_unresolved_parents(self, tmp_path):
        """A parent id that does not resolve must be counted, never silently
        treated as a root -- which would understate nesting."""
        root = tmp_path / "projects"
        directory = root / "p" / "s" / "subagents"
        os.makedirs(directory)
        with open(directory / "agent-child.meta.json", "w", encoding="utf-8") as fh:
            json.dump({"agentType": "implement", "spawnDepth": 2, "parentAgentId": "ghost"}, fh)
        result = at.call_graph(str(root))
        assert result["rows_with_parent"].value == 1
        assert result["unresolved_parents"].value == 1


class TestLoopDetection:
    def test_repeated_cycle_is_detected(self):
        findings = at.find_repeated_subsequences(["Read", "Bash"] * 4)
        assert len(findings) == 1
        assert findings[0]["pattern"] == ["Read", "Bash"]
        assert findings[0]["repeats"] == 4

    def test_same_tool_run_is_not_a_loop(self):
        """The distinction that makes this metric mean anything.

        Measured 2026-09-05 on 300 live transcripts: counting same-tool runs
        reported an 86.3% loop rate, which measures nothing -- `Bash` fifteen
        times is an agent using Bash a lot. Requiring >=2 distinct tools in
        the repeated window moved the live rate to ~19%, comparable to MAST's
        reported 15.7% for FM-1.3 Step Repetition.
        """
        assert at.find_repeated_subsequences(["Bash"] * 15) == []
        assert at.find_repeated_subsequences(["Read"] * 30) == []

    def test_shortest_true_cycle_wins(self):
        """A Read,Bash cycle repeated 6 times is one finding of window=2, not
        a window=4 multiple of it."""
        findings = at.find_repeated_subsequences(["Read", "Bash"] * 6)
        assert len(findings) == 1
        assert findings[0]["window"] == 2
        assert findings[0]["repeats"] == 6

    def test_below_min_repeats_is_not_a_loop(self):
        assert at.find_repeated_subsequences(["Read", "Bash", "Read", "Bash"]) == []

    def test_non_repeating_sequence_is_clean(self):
        assert at.find_repeated_subsequences(["Read", "Edit", "Bash", "Write", "Grep"]) == []

    def test_short_transcripts_excluded_from_denominator(self, tmp_path):
        """A transcript too short to contain the pattern is not evidence of
        its absence -- it must not be counted as a clean pass."""
        root = tmp_path / "projects"
        write_transcript(root, "p", "s", "short", [assistant_turn(tools=["Read"])])
        write_transcript(root, "p", "s", "loopy", [assistant_turn(tools=["Read", "Bash"] * 4)])
        result = at.loop_detection(str(root))
        assert result["n"] == 1, "the 1-call transcript is not in the denominator"
        assert result["dispatches_with_loops"].value == 1
        assert result["rate"].value == 1.0


# ---------------------------------------------------------------------------
# Ledger reading
# ---------------------------------------------------------------------------


class TestLedgerReading:
    def test_snapshot_read_is_a_single_pass(self, tmp_path):
        """The ledger is live-appended while being read. A collector that
        re-reads and compares disagrees with itself for no reason."""
        path = write_ledger(tmp_path, [make_row(), make_row(agent_id="a2", tool_use_id="t2")])
        rows, report = at.read_ledger(path)
        assert len(rows) == 2
        assert report["rows_parsed"] == 2
        assert report["unparseable_lines"] == 0

    def test_unparseable_lines_counted_never_fatal(self, tmp_path):
        path = tmp_path / "spend.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(make_row()) + "\n")
            fh.write("{not json\n")
            fh.write("[1,2,3]\n")  # valid JSON, wrong shape
            fh.write("\n")
        rows, report = at.read_ledger(str(path))
        assert len(rows) == 1
        assert report["unparseable_lines"] == 2

    def test_missing_ledger_is_not_an_error(self, tmp_path):
        rows, report = at.read_ledger(str(tmp_path / "nope.jsonl"))
        assert rows == []
        assert report["exists"] is False

    def test_ts_order_is_never_assumed(self, tmp_path):
        """1345 of 5743 live rows are out of order relative to their
        predecessor (a joined row is stamped with its CLAIM time but appended
        at RELEASE time). Day bucketing must not depend on file order."""
        rows = [
            make_row(ts="2026-09-03T12:00:00Z", agent_id="a1", tool_use_id="t1"),
            make_row(ts="2026-09-01T12:00:00Z", agent_id="a2", tool_use_id="t2"),
            make_row(ts="2026-09-02T12:00:00Z", agent_id="a3", tool_use_id="t3"),
        ]
        result = at.dispatch_counts(rows)
        assert result["by_day"].value == {
            "2026-09-01": 1,
            "2026-09-02": 1,
            "2026-09-03": 1,
        }

    def test_parse_ts_handles_both_ledger_and_transcript_shapes(self):
        assert at.parse_ts("2026-09-01T12:00:00Z") is not None
        assert at.parse_ts("2026-09-01T12:00:00.123Z") is not None
        assert at.parse_ts(None) is None
        assert at.parse_ts("not a date") is None
        assert at.parse_ts(12345) is None


# ---------------------------------------------------------------------------
# ledger_health + aggregate + CLI
# ---------------------------------------------------------------------------


class TestLedgerHealth:
    def test_reports_the_join_mix_over_raw_rows(self):
        """ledger_health describes the LEDGER, so it must not collapse first
        -- collapsing would hide the very duplication it exists to report."""
        rows = [make_row(agent_id="same", tool_use_id="t1")]
        rows += [make_no_claim_row(agent_id="same")]
        result = at.ledger_health(rows)
        assert result["n"] == 2, "raw row count, pre-collapse"
        assert result["duplicate_agent_id_groups"].value == 1
        assert result["join_state_mix"].value == {"joined": 1, "no-claim": 1}
        assert result["join_rate"].value == 0.5

    def test_confidence_clause_states_the_partition(self):
        """Plan R3: the verdict line carries a ledger-confidence clause."""
        rows = [make_row()] + [make_no_claim_row(agent_id=f"u{i}") for i in range(3)]
        result = at.ledger_health(rows)
        clause = result["confidence_clause"].value
        assert "1 of 4" in clause
        assert "joined" not in clause.lower() or "partition" in clause.lower()

    def test_retention_horizon_is_reported(self):
        """spend.jsonl rolls off at ~11 days, so a 'vs prior 7d' tile sits at
        the edge of the window. The horizon must be stated, not implied."""
        rows = [
            make_row(ts="2026-09-01T00:00:00Z", agent_id="a1", tool_use_id="t1"),
            make_row(ts="2026-09-11T00:00:00Z", agent_id="a2", tool_use_id="t2"),
        ]
        result = at.ledger_health(rows)
        assert result["retention_horizon_days"].value == 10.0
        assert "rolls off" in result["retention_warning"]

    def test_horizon_unattributable_when_no_timestamps(self):
        rows = [make_row(ts=None, agent_id="a1", tool_use_id="t1")]
        result = at.ledger_health(rows)
        assert result["retention_horizon_days"].provenance == at.UNATTRIBUTABLE
        assert result["retention_horizon_days"].value is None


class TestCollectAllAndCLI:
    def test_a_failing_panel_does_not_abort_the_collection(self, tmp_path):
        """A dashboard that renders nothing because one panel lacks data is
        worse than one that renders what it can and says which it cannot."""
        path = write_ledger(tmp_path, [make_no_claim_row(agent_id="u1")])
        root = tmp_path / "projects"
        os.makedirs(root)
        payload = at.collect_all(ledger_path=path, projects_root=str(root))
        # latency has no joined rows -> not renderable, but token_buckets works.
        assert payload["latency_percentiles"]["renderable"] is False
        assert "error" in payload["latency_percentiles"]
        assert payload["token_buckets"]["n"] == 1

    def test_json_mode_serializes_every_value_with_provenance(self, tmp_path, capsys):
        path = write_ledger(tmp_path, [make_row()])
        root = tmp_path / "projects"
        os.makedirs(root)
        rc = at.main(["--json", "--ledger", path, "--projects-root", str(root)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        version = payload["price_table_version"]
        assert version["provenance"] == at.DECLARED
        buckets = payload["token_buckets"]["buckets"]
        for field in at.TOKEN_FIELDS:
            assert set(buckets[field]) == {"value", "provenance", "source"}

    def test_text_mode_runs(self, tmp_path, capsys):
        path = write_ledger(tmp_path, [make_row()])
        root = tmp_path / "projects"
        os.makedirs(root)
        rc = at.main(["--ledger", path, "--projects-root", str(root)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "AGENT TELEMETRY" in out
        assert "partition=" in out

    def test_no_transcripts_flag_skips_transcript_metrics(self, tmp_path):
        path = write_ledger(tmp_path, [make_row()])
        root = tmp_path / "projects"
        os.makedirs(root)
        payload = at.collect_all(
            ledger_path=path, projects_root=str(root), include_transcripts=False
        )
        assert "call_graph" not in payload
        assert "loop_detection" not in payload
        assert "token_buckets" in payload


class TestRendererPanelsActuallyRender:
    """The renderer's own panels must be ALIVE, not merely self-contained.

    WHY THIS EXISTS (review finding 2, 2026-09-06): a one-word typo — a
    constant deleted in one place and still referenced in another — killed the
    recent-window account panel on EVERY render. The full 4,605-test suite
    stayed green and `--verify` reported "self-contained OK", because neither
    checks whether a panel produced data. A broad `except Exception` then
    laundered the NameError into "ccdash unavailable", so the operator saw a
    DATA problem where there was a CODE problem.

    These are smoke tests against the LIVE machine, deliberately. They are
    skipped where the data sources are absent (CI, another developer), because
    their whole purpose is to catch a code path that only breaks when the data
    IS available -- a hermetic fixture would not have caught the original bug.
    """

    @staticmethod
    def _renderer():
        import importlib.util
        import pathlib

        path = pathlib.Path.home() / ".claude" / "scripts" / "render_agent_telemetry.py"
        if not path.exists():
            pytest.skip("render_agent_telemetry.py not present on this machine")
        spec = importlib.util.spec_from_file_location("_rat_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @pytest.mark.live_machine
    @pytest.mark.parametrize("days", [7, 30])
    def test_both_account_windows_are_available_at_every_days_value(self, days):
        """The central requirement of the billing-period correction: ALWAYS
        compute and show BOTH windows. `days == BILLING_PERIOD_DAYS` takes a
        different branch, so both values must be exercised -- the original bug
        fired on every value, but a days-only test could easily miss a branch."""
        rat = self._renderer()
        data = rat.load_metrics(None, None, days, False, ingest=False)
        if not data["account_capacity_30d"].get("ccdash_available"):
            pytest.skip("ccdash not available on this machine")

        recent = data["account_capacity_recent"]
        assert recent.get("ccdash_available") is True, (
            f"recent-window panel is DEAD at days={days}: {recent.get('reason')!r}. "
            f"A reason naming NameError/AttributeError is a CODE defect being "
            f"reported as a data outage."
        )

    @pytest.mark.live_machine
    def test_a_code_defect_is_never_reported_as_a_data_outage(self):
        """`reason` must never carry a programming error.

        The degradation path exists for missing/unreadable DATA. If it ever
        reports a NameError, AttributeError, ImportError or TypeError, a bug is
        wearing a data-availability costume -- which is precisely how the
        original defect reached the operator's page as body copy.
        """
        rat = self._renderer()
        data = rat.load_metrics(None, None, 7, False, ingest=False)
        for key in ("account_capacity_30d", "account_capacity_recent"):
            reason = str((data.get(key) or {}).get("reason") or "")
            for programming_error in ("NameError", "AttributeError", "ImportError", "TypeError"):
                assert programming_error not in reason, (
                    f"{key} degraded with {programming_error} in its reason ({reason!r}) -- "
                    f"that is a code defect, not a data outage."
                )


class TestAccountBalanceTileDerivesItsVerdict:
    """The tile must COMPUTE its conclusions, never assert them.

    This class exists because the same defect recurred three times in three
    consecutive fix rounds, each time relocated:
      v1  concluded five of six accounts were IDLE off a 7-day window --
          false, and it recommended consolidating seats the operator uses.
      v2  hardcoded the string "balanced" -- printed on a 90/10 split.
      v3  hardcoded "a genuinely BALANCED spread across all six seats" in the
          chart caption, where it would have sat directly beneath a chart the
          tile itself was calling "concentrated".
    Every one shipped past a fully green suite because nothing fed the tile an
    input whose correct answer was different.
    """

    @staticmethod
    def _tile():
        import importlib.util
        import pathlib

        path = pathlib.Path.home() / ".claude" / "scripts" / "render_agent_telemetry.py"
        if not path.exists():
            pytest.skip("render_agent_telemetry.py not present on this machine")
        spec = importlib.util.spec_from_file_location("_rat_tile_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.account_balance_tile

    @staticmethod
    def _capacity(shares):
        accounts = {
            email: {
                "calls": at.Value(int(share * 1000), at.DERIVED, "synthetic"),
                "share_of_attributed_calls": at.Value(share, at.DERIVED, "synthetic"),
                "api_equivalent_usd": at.Value(0.0, at.DERIVED, "synthetic"),
            }
            for email, share in shares.items()
        }
        busiest = max(shares, key=shares.get)
        quiet = [e for e, v in shares.items() if e != busiest and v < shares[busiest] * 0.10]
        return {
            "ccdash_available": True,
            "n": 1000,
            "accounts": accounts,
            "imbalance": {
                "quiet_account_count": at.Value(len(quiet), at.DERIVED, "synthetic"),
                "busiest_share": at.Value(shares[busiest], at.DERIVED, "synthetic"),
            },
        }

    @pytest.mark.parametrize(
        "label,shares,expected",
        [
            ("two-account 90/10", {"a@x": 0.90, "b@x": 0.10}, "concentrated"),
            ("even six", {"1@x": .35, "3@x": .19, "5@x": .15, "i@x": .12, "2@x": .10, "4@x": .09}, "balanced"),
            ("two-account 50/50", {"a@x": 0.50, "b@x": 0.50}, "uneven"),
            ("majority + a quiet tail", {"a@x": .50, "b@x": .47, "c@x": .03}, "concentrated"),
        ],
    )
    def test_the_spread_word_flips_with_the_data(self, label, shares, expected):
        cap = self._capacity(shares)
        tile = self._tile()(cap, cap, 7)
        assert tile["spread_word"] == expected, f"{label}: {tile['delta']!r}"
        # ...and the word the page prints is the word that was computed, so a
        # caption cannot drift away from the tile beside it.
        assert expected in tile["delta"]

    def test_running_hot_names_the_ACCELERATING_account_not_the_biggest(self):
        """Selection must be by acceleration over an account's OWN baseline.

        Regression guard for the cold-review blocker: the loop selected the
        largest recent share and never consulted the baseline, while the
        docstring and the operator hint both promised the opposite. Here b@x
        goes 5% -> 45% (9x its own pace, the real quota-exhaustion precursor)
        while a@x COOLS from 55% to 45%. Selecting by size names a@x -- an
        account that is slowing down -- and misses b@x entirely.
        """
        baseline = self._capacity({"a@x": 0.55, "b@x": 0.05, "c@x": 0.40})
        recent = self._capacity({"a@x": 0.45, "b@x": 0.45, "c@x": 0.10})
        tile = self._tile()(baseline, recent, 7)
        assert tile["running_hot_account"] == "b@x", (
            f"named {tile['running_hot_account']!r} -- selecting by size rather "
            f"than by acceleration over the account's own baseline."
        )
        assert tile["flagged"] is True

    def test_an_account_that_is_cooling_never_flags(self):
        """The paired negative: every account at or below its own pace is not
        a quota risk, however uneven the raw shares look."""
        baseline = self._capacity({"a@x": 0.60, "b@x": 0.40})
        recent = self._capacity({"a@x": 0.55, "b@x": 0.45})
        tile = self._tile()(baseline, recent, 7)
        assert tile["flagged"] is False
        assert tile["running_hot_account"] is None

    def test_delta_lines_are_two_short_window_labeled_lines(self):
        """2026-09-06 operator complaint ("fix the account and wrapping on
        this"): the tile's subtitle is TWO short lines, never one run-on
        sentence. Line 1 is the 30d billing-period window, line 2 the
        recent window -- requirement 3 (both windows always shown) in the
        new format. Falsified against the pre-fix source: reverting
        delta_lines makes every assertion here fail (KeyError), which the
        review found the 18 pre-existing tests could NOT do."""
        baseline = self._capacity({"a@x": 0.55, "b@x": 0.45})
        recent = self._capacity({"a@x": 0.60, "b@x": 0.40})
        tile = self._tile()(baseline, recent, 7)
        lines = tile["delta_lines"]
        assert isinstance(lines, list) and len(lines) == 2
        assert lines[0].startswith("30d: ")
        assert lines[1].startswith("7d: ")
        # Short local-part labels only -- never a full email in the lines.
        assert "@x" not in lines[0] and "@x" not in lines[1]

    def test_delta_lines_recent_window_falls_back_honestly_with_no_recent_data(self):
        """Requirement 3's fallback: when the recent window has no attributed
        accounts, line 2 says so plainly rather than being dropped -- both
        windows stay visible in every state."""
        baseline = self._capacity({"a@x": 0.55, "b@x": 0.45})
        tile = self._tile()(baseline, {"ccdash_available": False}, 7)
        assert tile["delta_lines"][1] == "7d: no attributed recent data"

    def test_delta_is_the_joined_fallback_of_delta_lines(self):
        """The plain `delta` string stays as the join of the two lines, so
        every pre-existing consumer/assertion of `delta` keeps working."""
        baseline = self._capacity({"a@x": 0.55, "b@x": 0.45})
        recent = self._capacity({"a@x": 0.60, "b@x": 0.40})
        tile = self._tile()(baseline, recent, 7)
        assert tile["delta"] == "; ".join(tile["delta_lines"])


class TestRendererTilesAndContracts:
    """Coverage for the renderer functions that produce every number the
    operator reads.

    All five defects found across four review rounds lived in this file and
    NONE was reachable by a test, because the renderer had no unit tests at
    all -- only live smoke tests that check degradation reasons. These are
    hermetic (synthetic inputs, no live data) so they run in the default suite.
    """

    @staticmethod
    def _mod():
        import importlib.util
        import pathlib

        path = pathlib.Path.home() / ".claude" / "scripts" / "render_agent_telemetry.py"
        if not path.exists():
            pytest.skip("render_agent_telemetry.py not present on this machine")
        spec = importlib.util.spec_from_file_location("_rat_contracts", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_leverage_prorates_the_fixed_cost_to_the_window(self):
        """$1,200/mo over a 7-day window is $280, so $2,800 of
        api-equivalent value is 10x -- not 2.33x (a full-month denominator)
        and not 233x (a per-day one)."""
        mod = self._mod()
        spend = {"ccdash_available": True, "n": 100, "total_usd": at.Value(2800.0, at.DERIVED, "t")}
        tile = mod.leverage_tile(spend, 7)
        assert tile.get("error") is None
        assert "10x" in tile["value"]

    def test_leverage_never_calls_the_dollar_figure_money_spent(self):
        """The operator pays a FIXED subscription; a dollar figure presented
        as spend would imply a variable cost that does not exist."""
        mod = self._mod()
        spend = {"ccdash_available": True, "n": 100, "total_usd": at.Value(2800.0, at.DERIVED, "t")}
        text = " ".join(str(v) for v in mod.leverage_tile(spend, 7).values()).lower()
        assert "equivalent" in text, "dollars must be labelled as metered-API-equivalent"
        assert "spent" not in text

    def test_quality_direction_pools_rounds_rather_than_averaging_rates(self):
        """Rule 5 of this module: never average pre-aggregated buckets.

        Two prior rounds -- one tiny and terrible (n=10, 90%), one large and
        good (n=1000, 10%) -- pool to ~10.8%. An unweighted mean would read
        50% and call a final 20% round an IMPROVEMENT; pooled, 20% is a
        REGRESSION against the 10.8% that actually happened.
        """
        mod = self._mod()
        q = {
            "cycle_telemetry_available": True,
            "verdicts": {
                "total": 1210,
                "dissent": at.Value(200, at.DERIVED, "t"),
                "dissent_rate": at.Value(0.165, at.DERIVED, "t"),
            },
            "cycles_read": 3,
            "convergence_by_round": [
                {"round": 1, "n": 10, "dissent_rate": 0.90},
                {"round": 2, "n": 1000, "dissent_rate": 0.10},
                {"round": 3, "n": 200, "dissent_rate": 0.20},
            ],
        }
        assert mod.quality_tile(q)["direction"] == "up", (
            "pooled prior is 10.8%, so a 20% final round is a REGRESSION; "
            "an unweighted mean (50%) would wrongly read it as improvement."
        )

    def test_body_only_fragment_carries_no_document_wrapper(self):
        """The Operator Hub inlines this fragment into an existing page."""
        mod = self._mod()
        data = mod.load_metrics(None, None, 7, False, ingest=False)
        frag = mod.render_html(data, body_only=True)
        for tag in ("<!doctype", "<html", "<head", "<body", "</html>"):
            assert tag not in frag.lower(), f"fragment must not contain {tag}"
        assert mod.find_external_resources(frag) == [], "no external resource loads"

    def test_scoped_css_drops_print_for_embedding_but_keeps_it_standalone(self):
        """A second @media print block in the host defeats the hub's own
        falsifiability guard, which strips the FIRST one and asserts none
        remain."""
        mod = self._mod()
        assert "@media print" not in mod.scoped_css(drop_print=True)
        assert "@media print" in mod.scoped_css(drop_print=False)

    def test_scoped_css_confines_every_rule_and_stays_balanced(self):
        """This module's selectors are deliberately generic (h1/p/table/.card)
        and would restyle the host page if injected unscoped. `:root` must be
        RETARGETED, not prefixed -- `.agent-telemetry :root` matches nothing,
        so every CSS variable would resolve empty."""
        mod = self._mod()
        css = mod.scoped_css(".agent-telemetry")
        assert css.count("{") == css.count("}"), "unbalanced braces"
        unscoped = [
            line for line in css.splitlines()
            if line.strip() and not line.strip().startswith((".agent-telemetry", "@"))
        ]
        assert not unscoped, f"unscoped rules would leak into the host: {unscoped[:3]}"
        assert ".agent-telemetry :root" not in css, ":root must be retargeted, not prefixed"


class TestRendererPrimitivesEnforceTheirInvariants:
    """The small helpers every panel is built from.

    These are where the page's stated invariants actually live -- a bare
    percentage or a non-zero-based bar is a defect no matter which panel
    produced it -- and they were the last untested surface after the tile
    contracts landed.
    """

    @staticmethod
    def _mod():
        import importlib.util
        import pathlib

        path = pathlib.Path.home() / ".claude" / "scripts" / "render_agent_telemetry.py"
        if not path.exists():
            pytest.skip("render_agent_telemetry.py not present on this machine")
        spec = importlib.util.spec_from_file_location("_rat_primitives", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_pct_can_never_produce_a_bare_percentage(self):
        """A bare percentage is unfalsifiable: 97% could be 97-of-100 or
        970,000-of-1,000,000, and those carry very different confidence.
        `pct` is the one place that guarantee is enforced, so it must be
        impossible to get a percentage out of it without its denominator."""
        mod = self._mod()
        out = mod.pct(97, 100)
        assert "97.0%" in out and "of 100" in out
        big = mod.pct(970_000, 1_000_000)
        assert "97.0%" in big and "of 1,000,000" in big
        # Same ratio, different confidence -- and the page can tell them apart.
        assert out != big

    def test_pct_refuses_a_zero_denominator_instead_of_dividing(self):
        """n=0 must say so, never ZeroDivisionError and never a fake 0%."""
        assert "denominator 0" in self._mod().pct(5, 0)

    def test_ranked_bar_chart_is_zero_based(self):
        """A bar chart with a non-zero baseline exaggerates small differences
        -- the reason the plan mandates zero-based axes. Two values differing
        by 2x must render bars differing by 2x, not by a truncated-axis
        illusion."""
        mod = self._mod()
        markup = mod.ranked_bar_chart([("a", 100.0), ("b", 50.0)], "calls")
        # Bars are CSS-percentage divs, not SVG rects.
        widths = [float(w) for w in re.findall(r"width:([0-9.]+)%", markup)]
        assert len(widths) >= 2, f"expected two bars, got {widths}"
        assert widths[0] / widths[1] == pytest.approx(2.0, rel=0.05), (
            f"bar widths {widths} do not preserve the 2:1 ratio -- a "
            f"non-zero-based axis would exaggerate the difference."
        )

    def test_ranked_bar_chart_survives_an_all_zero_series(self):
        """A quiet window is not an error. All-zero data must render rather
        than divide by its own maximum."""
        mod = self._mod()
        assert mod.ranked_bar_chart([("a", 0.0), ("b", 0.0)], "calls")

    def test_sparkline_and_charts_never_emit_an_external_resource(self):
        """Every chart is hand-rolled inline SVG precisely so the page stays
        self-contained with no CDN and no webfont."""
        mod = self._mod()
        markup = mod.sparkline([1.0, 5.0, 3.0]) + mod.ranked_bar_chart([("a", 1.0)], "u")
        assert mod.find_external_resources(markup) == []

    def test_vget_returns_the_default_rather_than_raising_on_a_missing_path(self):
        """Panels degrade; they do not explode. Every metric read goes through
        this, so a missing key must never abort a render."""
        mod = self._mod()
        assert mod.vget({}, "nope", default="fallback") == "fallback"
        assert mod.vget({"a": {"b": at.Value(7, at.DERIVED, "t")}}, "a", "b") == 7


class TestSeriesGapsDistinguishLostFromRenumbered:
    """A round number with no record is TWO different things.

    A round that RAN but whose self-log did not fire (18' -- the authoritative
    ledger has its 28/198) is real missing data. A round number that NEVER
    EXISTED (3 and 9 -- verified 2026-09-06 against the ledger, whose full
    inventory is 1,2,4-8,10-18,18p) is a renumbering, and nothing is lost.

    Reporting both as "missing" overstates the problem and teaches a reader to
    ignore the field -- which is worse than not having it, because the field's
    entire job is to stop a gapped series from reading as a continuous trend.
    """

    def test_never_ran_rounds_are_declared_not_inferred(self):
        """Absence alone CANNOT tell the two apart -- both look like a missing
        integer. The classification must come from the authoritative ledger and
        be marked DECLARED, so a reader knows it rests on a cross-check that
        needs re-verifying if the ledger's inventory changes."""
        q = at.quality_outcomes()
        if not q.get("cycle_telemetry_available"):
            pytest.skip("cycle telemetry unavailable on this machine")
        never_ran = q["series_gaps_never_ran"]
        assert never_ran.provenance == at.DECLARED, (
            "a never-ran classification inferred from absence would be "
            "indistinguishable from a lost record"
        )
        assert "ledger" in never_ran.source

    def test_the_two_gap_classes_are_reported_separately(self):
        q = at.quality_outcomes()
        if not q.get("cycle_telemetry_available"):
            pytest.skip("cycle telemetry unavailable on this machine")
        assert "series_gaps" in q and "series_gaps_never_ran" in q, (
            "collapsing these into one field loses the distinction between a "
            "lost record and a renumbering"
        )

    def test_a_lost_record_is_never_classified_as_never_ran(self):
        """Round 18' RAN -- the ledger holds 28 dissents / 198 verdicts -- so
        it must never be excused as a renumbering. This is the asymmetry that
        matters: mislabelling a renumbering as lost is noise; mislabelling a
        LOST round as never-ran hides real missing data."""
        assert 18 not in at.KNOWN_NEVER_RAN_ROUNDS
        for n in at.KNOWN_NEVER_RAN_ROUNDS:
            assert isinstance(n, int)


class TestRenderedOutputHasNoTrailingWhitespace:
    """The pre-commit trim-trailing-whitespace hook rewrites the built HTML on
    every commit that has any, forcing an extra record-review/commit cycle
    (found 2026-09-06 by exampleapp-c3 after the hook fired on a
    hub regen). The source of one such line was traced to an f-string in this
    module ending in a literal trailing space before its closing quote --
    cheap to prevent at the source, expensive to keep re-discovering at commit
    time on every regen thereafter."""

    def test_no_emitted_line_ends_in_whitespace(self):
        import pathlib

        path = pathlib.Path.home() / ".claude" / "scripts" / "render_agent_telemetry.py"
        if not path.exists():
            pytest.skip("render_agent_telemetry.py not present on this machine")
        import importlib.util

        spec = importlib.util.spec_from_file_location("_rat_ws", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        data = mod.load_metrics(None, None, 7, False, ingest=False)
        frag = mod.render_html(data, body_only=True)
        css = mod.scoped_css()
        bad = [
            (i, line)
            for i, line in enumerate(f"<style>{css}</style>{frag}".splitlines())
            if line != line.rstrip()
        ]
        assert not bad, f"trailing whitespace on {len(bad)} line(s), e.g. {bad[0]!r}"
