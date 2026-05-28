"""Unit tests for jeromelu_shared.agent_audit pure helpers.

Covers cost estimation (per-model and fallback), server-tool pricing,
run-id format/uniqueness, and the recursive _truncate helper. The
AgentAuditLog class itself touches DB+S3 and belongs in integration/.
"""

import re

import pytest
from jeromelu_shared.agent_audit import (
    MODEL_PRICING,
    SERVER_TOOL_PRICING_USD,
    _truncate,
    estimate_server_tool_cost,
    estimate_token_cost,
    make_run_id,
)

# ---------------------------------------------------------------------------
# estimate_token_cost
# ---------------------------------------------------------------------------


class TestEstimateTokenCost:
    def test_zero_tokens_costs_zero(self):
        assert estimate_token_cost("claude-sonnet-4-6", 0, 0, 0, 0) == 0.0

    def test_sonnet_one_million_input_tokens(self):
        # Sonnet input is $3.00 / 1M tokens.
        cost = estimate_token_cost("claude-sonnet-4-6", 1_000_000, 0, 0, 0)
        assert cost == pytest.approx(3.00)

    def test_sonnet_one_million_output_tokens(self):
        # Sonnet output is $15.00 / 1M tokens.
        cost = estimate_token_cost("claude-sonnet-4-6", 0, 1_000_000, 0, 0)
        assert cost == pytest.approx(15.00)

    def test_opus_far_more_expensive_than_sonnet(self):
        sonnet = estimate_token_cost("claude-sonnet-4-6", 1_000_000, 1_000_000, 0, 0)
        opus = estimate_token_cost("claude-opus-4-7", 1_000_000, 1_000_000, 0, 0)
        # Opus is 5x sonnet on both input and output, so total should be 5x.
        assert opus == pytest.approx(5.0 * sonnet)

    def test_haiku_cheaper_than_sonnet(self):
        sonnet = estimate_token_cost("claude-sonnet-4-6", 1_000_000, 1_000_000, 0, 0)
        haiku = estimate_token_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000, 0, 0)
        assert haiku < sonnet

    def test_cache_read_priced_as_discount(self):
        # Cache reads should be ~10% of input price for sonnet/opus, 10% for haiku.
        for model in MODEL_PRICING:
            p = MODEL_PRICING[model]
            assert p["cache_read"] < p["input"], f"{model}: cache_read should undercut input"

    def test_cache_write_priced_above_input(self):
        # 5-min cache writes carry a 25% premium over normal input on Anthropic's grid.
        for model in MODEL_PRICING:
            p = MODEL_PRICING[model]
            assert p["cache_write_5m"] > p["input"], f"{model}: cache_write_5m should exceed input"

    def test_unknown_model_falls_back_to_sonnet(self):
        unknown = estimate_token_cost("claude-future-9-9", 1_000_000, 0, 0, 0)
        sonnet = estimate_token_cost("claude-sonnet-4-6", 1_000_000, 0, 0, 0)
        assert unknown == sonnet

    def test_mixed_token_breakdown_sums_correctly(self):
        # Hand-computed for sonnet: 100k in + 50k out + 10k cr + 5k cw.
        cost = estimate_token_cost("claude-sonnet-4-6", 100_000, 50_000, 10_000, 5_000)
        expected = (
            (100_000 / 1_000_000) * 3.00
            + (50_000 / 1_000_000) * 15.00
            + (10_000 / 1_000_000) * 0.30
            + (5_000 / 1_000_000) * 3.75
        )
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# estimate_server_tool_cost
# ---------------------------------------------------------------------------


class TestEstimateServerToolCost:
    def test_empty_dict_returns_zero(self):
        assert estimate_server_tool_cost({}) == 0.0

    def test_none_returns_zero(self):
        assert estimate_server_tool_cost(None) == 0.0

    def test_web_search_priced_per_call(self):
        # 100 searches at $0.01 each.
        assert estimate_server_tool_cost({"web_search": 100}) == pytest.approx(1.00)

    def test_web_fetch_currently_free(self):
        # Anthropic only bills tokens for fetches, not per-call.
        assert estimate_server_tool_cost({"web_fetch": 1000}) == 0.0

    def test_unknown_tool_treated_as_free(self):
        # Better to under-report than crash on a new tool the agent surfaced.
        assert estimate_server_tool_cost({"made_up_tool": 500}) == 0.0

    def test_mixed_tools_only_billable_count(self):
        cost = estimate_server_tool_cost(
            {
                "web_search": 5,
                "web_fetch": 100,
                "future_tool": 10,
            }
        )
        assert cost == pytest.approx(5 * SERVER_TOOL_PRICING_USD["web_search"])


# ---------------------------------------------------------------------------
# make_run_id
# ---------------------------------------------------------------------------


class TestMakeRunId:
    RUN_ID_PATTERN = re.compile(r"^([a-z_]+)-(\d{8})T(\d{6})-([0-9a-f]{6})$")

    def test_format_matches_spec(self):
        run_id = make_run_id("scout")
        match = self.RUN_ID_PATTERN.match(run_id)
        assert match is not None, f"Run id {run_id!r} doesn't match expected format"
        assert match.group(1) == "scout"

    def test_agent_id_carried_through_as_prefix(self):
        for agent in ["scout", "analyst", "critic", "bookkeeper"]:
            run_id = make_run_id(agent)
            assert run_id.startswith(f"{agent}-"), f"prefix mismatch for {agent}: {run_id}"

    def test_repeated_calls_unique(self):
        # Same-second triggers should still produce distinct ids thanks to
        # the hex nonce. 100 calls is plenty to surface a collision bug.
        ids = {make_run_id("scout") for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", limit=10) == "hello"

    def test_string_at_limit_unchanged(self):
        # Cutoff is strictly greater-than, so == limit stays untouched.
        s = "x" * 10
        assert _truncate(s, limit=10) == s

    def test_string_over_limit_trimmed_with_marker(self):
        s = "x" * 15
        result = _truncate(s, limit=10)
        assert result.startswith("x" * 10)
        assert "truncated 5 chars" in result

    def test_dict_values_truncated_recursively(self):
        big = "y" * 100
        result = _truncate({"a": big, "b": "short"}, limit=10)
        assert "truncated" in result["a"]
        assert result["b"] == "short"

    def test_list_values_truncated_recursively(self):
        big = "z" * 100
        result = _truncate([big, "short", 42], limit=10)
        assert "truncated" in result[0]
        assert result[1] == "short"
        assert result[2] == 42

    def test_nested_structures_truncated(self):
        big = "q" * 100
        result = _truncate({"a": [{"b": big}]}, limit=10)
        assert "truncated" in result["a"][0]["b"]

    @pytest.mark.parametrize("value", [42, 3.14, True, None, ("a", "b")])
    def test_non_string_non_collection_passthrough(self, value):
        # Tuples, ints, floats, bools, None aren't string/dict/list,
        # so they're returned untouched.
        assert _truncate(value, limit=5) == value
