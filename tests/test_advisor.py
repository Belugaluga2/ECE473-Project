"""Tests for the prompt-driven advisor (doc 24): parsing, the rule-based designer, the Claude tool loop (fake client),
and the shape comparison endpoint."""
import json

import pytest

from agri_hedge import advisor as adv
from agri_hedge import platform as pf

DFW = "32.7771, -97.8059"


def test_parse_request_extracts_the_fields():
    r = adv.parse_request(f"I'm growing corn at {DFW} on 300 acres, worth $900 per acre. I only care about July and August disasters.")
    assert r["crop"] == "corn" and r["acres"] == 300 and r["value_per_acre"] == 900
    assert r["lat"] == 32.7771 and r["lon"] == -97.8059 and r["place"] is None
    assert r["months"] == [7, 8] and r["preference"] == "exponential" and r["risk_aversion"] == 4.0 and r["coverage"] == 0.9
    r2 = adv.parse_request("We run cattle on 1,200 acres near Weatherford, TX and want to cover $50k of grazing value with 80% coverage")
    assert r2["crop"] == "pasture" and r2["acres"] == 1200 and r2["value_total"] == 50000 and r2["coverage"] == 0.8
    assert r2["place"] == "Weatherford, TX" and r2["preference"] is None and r2["risk_aversion"] == 2.0
    assert adv.extract_place("Our farm is at 1234 FM 51, Weatherford, TX 76086 and we grow hay").startswith("1234 FM 51")
    assert adv.extract_place("zip 76086 please") == "76086"
    assert adv.crop_profile("milo")["crop"] == "sorghum" and adv.crop_profile("soy beans")["crop"] == "soybeans"
    assert adv.crop_profile("corn")["key_month"] == "Jul" and adv.crop_profile("quinoa")["known"] is False


def test_rules_advisor_asks_for_missing_essentials():
    out = adv.advise({"messages": [{"role": "user", "content": "Can you design me a drought contract?"}], "mode": "rules"})
    assert out["mode"] == "rules" and out["status"] == "question" and out["contract"] is None
    low = out["reply"].lower()
    assert "where" in low and "grow" in low and "acres" in low
    assert out["history"][-1]["role"] == "assistant"
    with pytest.raises(ValueError):
        adv.advise({"messages": []})


def test_rules_advisor_designs_a_contract_from_coordinates():
    msgs = [{"role": "user", "content": f"I grow hay on 150 acres at {DFW}. Cover November."}]
    out = adv.advise({"messages": msgs, "mode": "rules", "price_source": "model"})
    assert out["status"] == "designed" and out["mode"] == "rules"
    q = out["contract"]
    assert q["product"]["station"] == "DFW" and q["product"]["month"] == "Nov" and q["product"]["farm_lat"] == 32.7771
    assert q["term_sheet"][0]["payout_usd"] > 0 and out["comparison"]["rows"]
    assert out["contract"]["product"]["shape"] == out["comparison"]["recommendation"]["shape"]
    assert "Nov" in out["reply"] and "not insurance" in out["reply"]
    assert [c["name"] for c in out["tool_calls"]] == ["check_location", "compare_shapes", "design_contract"]
    # the farmer's own words pick the shape
    out2 = adv.advise({"messages": [{"role": "user", "content": f"150 acres of hay at {DFW}, November, I only want catastrophe cover"}],
                       "mode": "rules", "price_source": "model"})
    assert out2["contract"]["product"]["shape"] == "exponential"
    # sizing: acres x value x season share x coverage (November is outside the hay season: one sixth of the season)
    size = adv.size_contract(150, 260, 1 / 6, 0.9)
    assert out2["contract"]["product"]["max_payout_usd"] == pytest.approx(size["max_payout_usd"])


def test_rules_advisor_reports_unserved_land():
    out = adv.advise({"messages": [{"role": "user", "content": "500 acres of wheat at 44.0, -120.0"}], "mode": "rules",
                      "price_source": "model"})
    assert out["status"] == "info" and out["contract"] is None and "outside" in out["reply"]
    assert out["location"]["served"] is False


class _Resp:
    def __init__(self, content, stop):
        self.content, self.stop_reason = content, stop


class _FakeMessages:
    """Scripted Claude: ask a question, then on the next turn call two tools and answer."""

    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        msgs = kw["messages"]
        assert kw["model"] == adv.MODEL and kw["tools"] is adv.TOOLS and kw["system"]
        last = msgs[-1]
        if isinstance(last["content"], list) and last["content"] and last["content"][0].get("type") == "tool_result":
            res = [json.loads(b["content"]) for b in last["content"]]
            assert not any(b["is_error"] for b in last["content"]), res
            assert res[0]["served"] is True and res[1]["term_sheet"][0]["payout_usd"] > 0
            return _Resp([{"type": "text", "text": f"Your November contract pays ${res[1]['term_sheet'][0]['payout_usd']:,.0f} in a very dry month."}],
                         "end_turn")
        if len(msgs) == 1:
            return _Resp([{"type": "text", "text": "How many acres do you farm?"}], "end_turn")
        return _Resp([{"type": "thinking", "thinking": "", "signature": "x"},
                      {"type": "tool_use", "id": "t1", "name": "check_location", "input": {"lat": 32.7771, "lon": -97.8059, "months": [11]}},
                      {"type": "tool_use", "id": "t2", "name": "design_contract",
                       "input": {"lat": 32.7771, "lon": -97.8059, "month": 11, "shape": "convex2", "max_payout_usd": 5000,
                                 "value_at_risk_usd": 15000, "coverage": 0.9, "risk_aversion": 2}}], "tool_use")


class _FakeClient:
    def __init__(self):
        self.beta = type("B", (), {})()
        self.beta.messages = _FakeMessages()
        self.messages = self.beta.messages


def test_claude_loop_runs_tools_and_returns_the_contract():
    client = _FakeClient()
    out = adv.advise({"messages": [{"role": "user", "content": f"hay at {DFW}"}], "price_source": "model"}, client=client)
    assert out["mode"] == "claude" and out["status"] == "question" and out["reply"].endswith("?") and out["contract"] is None
    history = out["history"] + [{"role": "user", "content": "150 acres, November"}]
    out2 = adv.advise({"messages": history, "price_source": "model"}, client=client)
    assert out2["status"] == "designed" and out2["contract"]["product"]["shape"] == "convex2"
    assert out2["contract"]["product"]["max_payout_usd"] == 5000
    assert [c["name"] for c in out2["tool_calls"]] == ["check_location", "design_contract"] and all(c["ok"] for c in out2["tool_calls"])
    assert "$" in out2["reply"]
    assert out2["history"][-1]["role"] == "assistant" and out2["history"][-2]["content"][0]["type"] == "tool_result"
    assert client.beta.messages.calls[-1]["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_failure_falls_back_to_rules():
    class Broken:
        class beta:
            class messages:
                @staticmethod
                def create(**kw):
                    raise RuntimeError("no network")
    out = adv.advise({"messages": [{"role": "user", "content": f"150 acres of hay at {DFW}, November"}], "price_source": "model"},
                     client=Broken())
    assert out["mode"] == "rules" and out["status"] == "designed" and "RuntimeError" in out["fallback_reason"]


def test_status_reports_mode_and_crops(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    s = adv.status()
    assert s["mode"] == "rules" and "corn" in s["crops"]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert adv.status()["mode"] == "claude" and adv.api_key_from({"api_key": " k "}) == "k"


def test_exotic_compare_and_the_optimal_shape():
    c = pf.exotic_compare({"lat": 32.7771, "lon": -97.8059, "month": 11, "max_payout": 6000, "price_source": "model"})
    shapes = {r["shape"] for r in c["rows"]}
    assert {"linear", "convex2", "exponential", "optimal"} <= shapes and not c["errors"]
    lin = next(r for r in c["rows"] if r["shape"] == "linear")
    assert lin["max_payout_equal_premium_usd"] == 6000 and c["equal_premium_reference"] == "linear"
    quad = next(r for r in c["rows"] if r["shape"] == "convex2")
    assert quad["max_payout_equal_premium_usd"] > 6000 and quad["fair_premium_usd"] < lin["fair_premium_usd"]
    for r in c["rows"]:
        assert r["fair_premium_usd"] > 0 and 0 <= r["ce_share_of_optimal"] <= 1.001
    assert next(r for r in c["rows"] if r["shape"] == "optimal")["ce_share_of_optimal"] == pytest.approx(1.0)
    assert c["recommendation"]["shape"] in shapes and c["recommendation"]["best_fixed_shape"] != "optimal"
    opt = pf.exotic_quote({"lat": 32.7771, "lon": -97.8059, "month": 11, "shape": "optimal", "max_payout": 6000,
                           "value_at_risk": 20000, "price_source": "model"})
    assert opt["design"]["recommended_max_payout_usd"] > 0 and opt["term_sheet"][0]["payout_usd"] == pytest.approx(6000)
    assert opt["replication"]["cash_leg"] == pytest.approx(0.0) and all(t["side"] == "NO" for t in opt["ticket"])
    with pytest.raises(ValueError):
        pf.exotic_quote({"station_key": "DFW", "month": 11, "shape": "optimal", "max_payout": 1000, "price_source": "model"})
