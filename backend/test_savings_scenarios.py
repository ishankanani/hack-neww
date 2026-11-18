from test_combined import client


def test_csv_scenarios_match_recorded_service_and_replay_tariffs(client):
    response = client.get("/api/savings/scenarios", params={"lane": "R01", "reserve": 2})
    assert response.status_code == 200, response.text
    result = response.json()
    cases = {row["kind"]: row for row in result["scenarios"]}
    assert result["rows_scanned"] == 666
    assert cases["efficient"]["difference_eur"] == 0
    costly = cases["special_trips"]
    assert costly["date"] == "2025-09-16"
    assert costly["historical"]["special"] == 3
    assert costly["simulation"]["special"] == 0
    assert costly["difference_eur"] == 3140
    for row in cases.values():
        assert row["historical"]["dispatched_ldm"] == row["simulation"]["dispatched_ldm"]
        assert row["historical"]["deferred_ldm"] == row["simulation"]["deferred_ldm"]
        assert row["difference_eur"] == row["historical"]["cost_eur"] - row["simulation"]["cost_eur"]


def test_clear_demand_exposes_extra_cost_and_leaves_unserved_freight_visible(client):
    result = client.get("/api/savings/scenarios", params={"lane": "R01", "reserve": 2, "objective": "clear_demand"}).json()
    backlog = next(row for row in result["scenarios"] if row["kind"] == "freight_backlog")
    assert backlog["difference_eur"] == -2080
    assert backlog["additional_dispatch_ldm"] == 25
    assert backlog["simulation"]["deferred_ldm"] == 9.1
    assert backlog["simulation"]["regular"] == backlog["historical"]["regular"] + 2
    assert client.get("/api/savings/scenarios?reserve=5").status_code == 422
    assert client.get("/api/savings/scenarios?lane=unknown").status_code == 404
