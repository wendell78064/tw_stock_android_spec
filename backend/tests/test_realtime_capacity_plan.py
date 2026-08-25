from app.cli.realtime_capacity_plan import capacity_plan


def test_capacity_plan_deduplicates_p0_p1_and_reserves_p2_worst_case():
    result = capacity_plan(
        {"TWSE:2330", "TPEX:6488"},
        {"TWSE:2330", "TWSE:2454"},
        budget=5,
        provider_limit=200,
    )
    assert result == {
        "P0_MEMBERS": 2,
        "P1_MEMBERS": 2,
        "P0_P1_UNIQUE_TICKS": 3,
        "P2_WORST_CASE_ADDITION": 2,
        "CURRENT_BUDGET": 5,
        "PROVIDER_LIMIT": 200,
        "ROLLOUT_SAFE": "YES",
    }


def test_capacity_plan_requires_explicit_valid_budget_and_emits_only_bounded_counts():
    unconfigured = capacity_plan({"TWSE:2330"}, {"TWSE:2454"}, None)
    above_provider = capacity_plan(set(), set(), 201, provider_limit=200)
    assert unconfigured["ROLLOUT_SAFE"] == "NO"
    assert unconfigured["CURRENT_BUDGET"] == "UNCONFIGURED"
    assert above_provider["ROLLOUT_SAFE"] == "NO"
    assert set(unconfigured) == {
        "P0_MEMBERS",
        "P1_MEMBERS",
        "P0_P1_UNIQUE_TICKS",
        "P2_WORST_CASE_ADDITION",
        "CURRENT_BUDGET",
        "PROVIDER_LIMIT",
        "ROLLOUT_SAFE",
    }
