"""Prompt-driven contract advisor (doc 24): "I grow corn at this address on 300 acres" -> a designed contract.

Two modes behind one function, `advise(params)`:

* **claude**: when an Anthropic API key is available (the request's `api_key`, or the environment's
  ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN), Claude runs a tool-use loop over the project's own
  functions (geocode the address, look up the crop, check the location against the served area,
  compare every payoff shape for the key month, design the contract) and answers in plain language.
  It asks for what it still needs (where, what, how much) before designing.
* **rules**: with no key, a deterministic parser does the same job for the common phrasings, so the
  feature works offline and in tests. The reply says which mode ran.

Every number in a reply comes from `platform.exotic_quote` / `platform.exotic_compare`; the model is
told not to invent any. The designed contract (the full quote) is returned alongside the text so the
app can render the term sheet, ticket and basis-risk verdict with the same code as the designer tab.

Crop values are rough national averages for sizing only (see CROPS); the farmer can override them.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request

import numpy as np

from agri_hedge import hedge_builder as hb
from agri_hedge import platform as pf

MODEL = "claude-opus-5-5"
MAX_TURNS = 10
USER_AGENT = "AgriHedge-research/0.3 (ECE473 course project)"
DEFAULT_COVERAGE = 0.9

#: Approximate normal-year revenue per acre (USD) and the months whose rain sets the yield, with weights.
#: Values are rough 2025 US averages for sizing a quote (yield x price), not estimates for any farm:
#: the farmer should give their own value per acre. "rain_fit" says how far a one-month station rain
#: contract can go for the crop (irrigated or perennial crops: poor).
CROPS = {
    "corn": {"label": "corn (grain)", "value_per_acre_usd": 870, "season": {5: 0.10, 6: 0.25, 7: 0.45, 8: 0.20},
             "rain_fit": "good", "notes": "July rain matters most (doc 03a); a wet May delays planting, so May cover is the wet side."},
    "soybeans": {"label": "soybeans", "value_per_acre_usd": 545, "season": {6: 0.15, 7: 0.35, 8: 0.50},
                 "rain_fit": "good", "notes": "August rain sets pod fill (doc 03a)."},
    "wheat": {"label": "winter wheat", "value_per_acre_usd": 275, "season": {3: 0.2, 4: 0.4, 5: 0.4},
              "rain_fit": "fair", "notes": "Spring rain during jointing and heading; fall establishment matters too."},
    "sorghum": {"label": "grain sorghum", "value_per_acre_usd": 295, "season": {6: 0.3, 7: 0.45, 8: 0.25},
                "rain_fit": "good", "notes": "Drought tolerant; losses come in deep summer droughts."},
    "cotton": {"label": "cotton", "value_per_acre_usd": 580, "season": {6: 0.3, 7: 0.4, 8: 0.3},
               "rain_fit": "fair", "notes": "Dryland cotton; irrigated acres are rain-insensitive."},
    "hay": {"label": "hay (bermudagrass and other)", "value_per_acre_usd": 260,
            "season": {4: 0.15, 5: 0.25, 6: 0.25, 7: 0.10, 8: 0.10, 9: 0.15},
            "rain_fit": "good", "notes": "The PRF benchmark crop (doc 04); cutting season April to September."},
    "alfalfa": {"label": "alfalfa", "value_per_acre_usd": 660, "season": {4: 0.15, 5: 0.25, 6: 0.25, 7: 0.15, 8: 0.1, 9: 0.1},
                "rain_fit": "fair", "notes": "Often irrigated; dryland stands behave like hay."},
    "pasture": {"label": "pasture / rangeland (grazing)", "value_per_acre_usd": 25,
                "season": {4: 0.2, 5: 0.25, 6: 0.25, 7: 0.1, 9: 0.1, 10: 0.1},
                "rain_fit": "good", "notes": "Valued at pasture cash rent (docs 03b, 04); the PRF grazing benchmark."},
    "peanuts": {"label": "peanuts", "value_per_acre_usd": 1000, "season": {6: 0.2, 7: 0.4, 8: 0.4},
                "rain_fit": "fair", "notes": "Southeastern dryland peanuts; many acres are irrigated."},
    "rice": {"label": "rice", "value_per_acre_usd": 1100, "season": {6: 0.3, 7: 0.4, 8: 0.3},
             "rain_fit": "poor", "notes": "Flood irrigated: rain shortfall barely moves yield; a drought contract is a poor fit."},
    "orchard": {"label": "orchard / vineyard / citrus", "value_per_acre_usd": 3000, "season": {4: 0.2, 5: 0.2, 6: 0.2, 7: 0.2, 8: 0.2},
                "rain_fit": "poor", "notes": "Perennial and mostly irrigated; frost and heat matter more than monthly rain."},
    "vegetables": {"label": "vegetables", "value_per_acre_usd": 4000, "season": {5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25},
                   "rain_fit": "poor", "notes": "Mostly irrigated and high value; this product is not designed for it."},
}
CROP_ALIASES = {
    "corn": ["corn", "maize"], "soybeans": ["soybean", "soybeans", "soy", "beans"], "wheat": ["wheat"],
    "sorghum": ["sorghum", "milo"], "cotton": ["cotton"], "hay": ["hay", "bermuda", "bermudagrass", "fescue", "bahia"],
    "alfalfa": ["alfalfa"], "pasture": ["pasture", "rangeland", "grazing", "cattle", "cows", "cow-calf", "ranch", "forage", "graze", "stocker"],
    "peanuts": ["peanut", "peanuts"], "rice": ["rice"], "orchard": ["orchard", "pecan", "pecans", "citrus", "orange", "vineyard", "grapes", "almond", "almonds", "apple", "apples"],
    "vegetables": ["vegetable", "vegetables", "tomato", "tomatoes", "lettuce", "melon", "melons", "onions"],
}
MONTH_WORDS = {m.lower(): i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                                        "august", "september", "october", "november", "december"])}
MONTH_WORDS.update({m[:3]: i for m, i in list(MONTH_WORDS.items())})
PREFERENCES = {
    "exponential": ["catastroph", "disaster", "worst case", "worst-case", "only the worst", "wipeout", "wipe-out", "total loss"],
    "convex2": ["cheap", "budget", "bad years", "extra for worse", "pay more when", "convex"],
    "layered": ["layer", "escalat", "reinsurance"],
    "tiers": ["simple", "tier", "fixed payment", "fixed payments", "step"],
    "linear": ["like prf", "linear", "every dry", "frequent", "small payments", "proportional"],
    "capped": ["cap", "stop-loss", "stop loss", "full payment"],
    "both_tails": ["too much rain", "flood", "excess rain", "both", "wet and dry", "harvest rain"],
    "loss": ["my loss", "loss curve", "match my loss"],
}


# ---------------------------------------------------------------------------------------------
# tools shared by both modes
# ---------------------------------------------------------------------------------------------

def crop_profile(crop: str) -> dict:
    """Crop lookup by name or alias; unknown crops get the list of known ones."""
    c = crop_key(crop)
    if c is None:
        return {"known": False, "crop": crop, "known_crops": sorted(CROPS)}
    d = CROPS[c]
    return {"known": True, "crop": c, "label": d["label"], "value_per_acre_usd": d["value_per_acre_usd"],
            "season_month_weights": {hb.MONTH_ABBR[m - 1]: w for m, w in d["season"].items()},
            "key_month": hb.MONTH_ABBR[max(d["season"], key=d["season"].get) - 1],
            "key_month_number": max(d["season"], key=d["season"].get),
            "rain_fit": d["rain_fit"], "notes": d["notes"],
            "value_source": "approximate 2025 US average revenue per acre (yield x price), for sizing only"}


def crop_key(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    best = None
    for key, words in CROP_ALIASES.items():
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", t):
                if best is None or len(w) > len(best[1]):
                    best = (key, w)
    return best[0] if best else None


def _http_json(url: str, timeout: float = 10.0):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(address: str, timeout: float = 10.0) -> dict:
    """Address or place -> lat/lon. US Census geocoder for street addresses, OpenStreetMap Nominatim otherwise.

    Raises LookupError when neither finds it (or the machine is offline).
    """
    address = (address or "").strip()
    if not address:
        raise LookupError("no address given")
    m = re.match(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$", address)
    if m:
        return {"lat": float(m.group(1)), "lon": float(m.group(2)), "matched": address, "source": "coordinates"}
    errors = []
    if re.search(r"\d", address):           # a street number or zip: try the Census geocoder first
        try:
            u = ("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json"
                 "&address=" + urllib.parse.quote(address))
            d = _http_json(u, timeout)
            hits = d.get("result", {}).get("addressMatches", [])
            if hits:
                h = hits[0]
                return {"lat": float(h["coordinates"]["y"]), "lon": float(h["coordinates"]["x"]),
                        "matched": h.get("matchedAddress", address), "source": "US Census geocoder"}
            errors.append("Census geocoder: no match")
        except Exception as exc:  # offline, timeout, API change
            errors.append(f"Census geocoder: {type(exc).__name__}")
    try:
        u = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&q=" + urllib.parse.quote(address))
        d = _http_json(u, timeout)
        if d:
            return {"lat": float(d[0]["lat"]), "lon": float(d[0]["lon"]), "matched": d[0].get("display_name", address),
                    "source": "OpenStreetMap Nominatim"}
        errors.append("Nominatim: no match")
    except Exception as exc:
        errors.append(f"Nominatim: {type(exc).__name__}")
    raise LookupError(f"could not geocode {address!r} ({'; '.join(errors)})")


def check_location(lat: float, lon: float, months: list | None = None, coverage: float = DEFAULT_COVERAGE) -> dict:
    """Is the land inside the served area, which station settles it, and how well does that station track it by month?"""
    near = hb.nearest_stations(float(lat), float(lon), 3)
    out = {"lat": float(lat), "lon": float(lon),
           "nearest_stations": [{"station_key": r["station_key"], "series": r["series_ticker"], "name": r["name"],
                                 "distance_mi": round(float(r["distance_mi"]), 1)} for _, r in near.iterrows()]}
    try:
        p = hb.build_problem(hb.CoverageRequest(float(lat), float(lon), [hb.Window((7,), 1.0)], coverage, 1000.0))
        out.update({"served": True, "grid_id": p.grid_id, "station_key": p.station["station_key"],
                    "distance_mi": round(p.distance_mi, 1)})
    except ValueError as exc:
        out.update({"served": False, "reason": str(exc)})
        return out
    fits = []
    for m in (months or []):
        try:
            q = pf.exotic_quote({"lat": lat, "lon": lon, "month": int(m), "shape": "linear", "max_payout": 1000.0,
                                 "coverage": coverage, "price_source": "model"})
            fb = q["farm_basis_risk"] or {}
            fits.append({"month": hb.MONTH_ABBR[int(m) - 1], "month_number": int(m), "he": fb.get("he_exchange_vs_farm"),
                         "verdict": fb.get("verdict"), "normal_rain_in": q["product"]["normal_in"]})
        except ValueError as exc:
            fits.append({"month": hb.MONTH_ABBR[int(m) - 1], "month_number": int(m), "error": str(exc)})
    out["month_fit"] = fits
    return out


def size_contract(acres: float | None, value_per_acre: float | None, month_share: float, coverage: float,
                  value_total: float | None = None) -> dict:
    """Maximum payout for one month: acres x value x coverage x the month's share of the season (PRF's sizing)."""
    if value_total is not None and value_total > 0:
        season_value = float(value_total)
    elif acres and value_per_acre:
        season_value = float(acres) * float(value_per_acre)
    else:
        raise ValueError("need acres and value per acre, or a dollar value to cover")
    var = season_value * float(month_share)
    return {"season_value_usd": round(season_value, 2), "value_at_risk_usd": round(var, 2),
            "max_payout_usd": round(var * float(coverage), 2), "month_share": float(month_share), "coverage": float(coverage)}


def compact_quote(q: dict) -> dict:
    """The part of an exotic quote the model needs to write its answer (no backtest arrays)."""
    pr, fb, d = q["pricing"], q["farm_basis_risk"] or {}, q.get("design") or {}
    return {"shape": q["product"]["shape"], "shape_label": q["product"]["shape_label"],
            "station": q["product"]["station"], "station_name": q["product"]["station_name"],
            "distance_mi": q["product"]["distance_mi"], "month": q["product"]["month"],
            "contract_month": q["product"]["contract_month"], "normal_rain_in": q["product"]["normal_in"],
            "trigger_in": q["product"]["trigger_in"], "max_payout_usd": q["product"]["max_payout_usd"],
            "term_sheet": [{"rain": t["rain"], "payout_usd": t["payout_usd"], "years_in_bin": t["years_in_bin"]} for t in q["term_sheet"]],
            "fair_premium_usd": pr["fair_premium_usd"], "all_in_cost_usd": pr["all_in_usd"],
            "cost_per_dollar_expected": pr["cost_per_dollar_expected"], "fill_share": pr["fill_share"],
            "largest_fillable_max_payout_usd": pr["largest_fillable_max_payout_usd"],
            "legs_priced_from_order_book": pr["legs_priced_from_order_book"], "contracts": sum(t["contracts"] for t in q["ticket"]),
            "farm_fit_he": fb.get("he_exchange_vs_farm"), "farm_fit_verdict": fb.get("verdict"),
            "tail_capture": fb.get("tail_capture"), "farm_grid_id": fb.get("grid_id"),
            "years_paid_of": [q["backtest"]["years_paid"], len(q["backtest"]["years"])],
            "design": {k: d[k] for k in ("recommended_max_payout_usd", "recommended_premium_usd", "ce_gain_pct_of_value") if k in d}}


def compact_compare(c: dict) -> dict:
    keep = ("shape", "shape_label", "fair_premium_usd", "fill_share", "fill_share_equal_premium", "farm_he", "farm_verdict",
            "tail_capture", "ce_share_of_optimal", "ce_gain_pct_of_value", "utility_best_max_payout_usd", "largest_fillable_max_payout_usd")
    return {"station": c["product"]["station"], "month": c["product"]["month"], "bins": c["bins"],
            "rows": [{k: r.get(k) for k in keep} | {"term_sheet_usd": r["term_sheet_usd"]} for r in c["rows"]],
            "recommendation": c["recommendation"], "farmer": c["farmer"]}


TOOLS = [
    {"name": "geocode_address", "description": "Turn a street address, a town and state, a zip code, or 'lat, lon' into coordinates (US only).",
     "input_schema": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"], "additionalProperties": False},
     "strict": True},
    {"name": "crop_profile", "description": "Look up a crop: approximate value per acre, the months whose rain sets its yield (with weights), the key month, and how well a one-month rain contract fits it.",
     "input_schema": {"type": "object", "properties": {"crop": {"type": "string"}}, "required": ["crop"], "additionalProperties": False},
     "strict": True},
    {"name": "check_location", "description": "Check whether the land is inside the served area (within about 150 miles of a study station with gridded rain history), which Kalshi station settles it, and how well that station tracks the land in the given months (hedge effectiveness, 0-1).",
     "input_schema": {"type": "object", "properties": {"lat": {"type": "number"}, "lon": {"type": "number"},
                                                       "months": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 12}}},
                      "required": ["lat", "lon", "months"], "additionalProperties": False},
     "strict": True},
    {"name": "compare_shapes", "description": "Price every payoff shape for one month at this location: fair premium, how much of it today's Kalshi books fill (at the same maximum payout and at the same premium), how well each tracks the farm, and the utility ranking for a farmer with the given risk aversion. Returns a recommendation.",
     "input_schema": {"type": "object", "properties": {"lat": {"type": "number"}, "lon": {"type": "number"},
                                                       "month": {"type": "integer", "minimum": 1, "maximum": 12},
                                                       "max_payout_usd": {"type": "number", "exclusiveMinimum": 0},
                                                       "value_at_risk_usd": {"type": "number", "exclusiveMinimum": 0},
                                                       "coverage": {"type": "number", "minimum": 0.5, "maximum": 1.0},
                                                       "risk_aversion": {"type": "number", "minimum": 0.5, "maximum": 10}},
                      "required": ["lat", "lon", "month", "max_payout_usd", "value_at_risk_usd", "coverage", "risk_aversion"],
                      "additionalProperties": False},
     "strict": True},
    {"name": "design_contract", "description": "Design and price one exchange-settled contract: term sheet (payout per rain bin), fair premium and all-in cost, fill on today's books, replicating ticket, and the farm's basis-risk verdict. Call it once per month the farmer wants covered, after compare_shapes.",
     "input_schema": {"type": "object", "properties": {"lat": {"type": "number"}, "lon": {"type": "number"},
                                                       "month": {"type": "integer", "minimum": 1, "maximum": 12},
                                                       "shape": {"type": "string", "enum": list(pf.COMPARE_SHAPES) + ["both_tails"]},
                                                       "max_payout_usd": {"type": "number", "exclusiveMinimum": 0},
                                                       "value_at_risk_usd": {"type": "number", "exclusiveMinimum": 0},
                                                       "coverage": {"type": "number", "minimum": 0.5, "maximum": 1.0},
                                                       "risk_aversion": {"type": "number", "minimum": 0.5, "maximum": 10}},
                      "required": ["lat", "lon", "month", "shape", "max_payout_usd", "value_at_risk_usd", "coverage", "risk_aversion"],
                      "additionalProperties": False},
     "strict": True},
]


def run_tool(name: str, inp: dict, state: dict, live=None, today=None) -> dict:
    """Execute one tool; results are plain dicts (JSON for the model). `state` collects full quotes for the app."""
    if name == "geocode_address":
        try:
            return geocode(inp["address"])
        except LookupError as exc:
            return {"error": str(exc), "hint": "ask for a fuller street address, a town and state, or coordinates"}
    if name == "crop_profile":
        return crop_profile(inp["crop"])
    if name == "check_location":
        return check_location(inp["lat"], inp["lon"], inp.get("months") or [])
    if name == "compare_shapes":
        c = pf.exotic_compare({"lat": inp["lat"], "lon": inp["lon"], "month": int(inp["month"]), "max_payout": float(inp["max_payout_usd"]),
                               "value_at_risk": float(inp["value_at_risk_usd"]), "coverage": float(inp["coverage"]),
                               "risk_aversion": float(inp["risk_aversion"]), "price_source": state.get("price_source", "auto")},
                              live, today)
        state["comparison"] = c
        return compact_compare(c)
    if name == "design_contract":
        q = pf.exotic_quote({"lat": inp["lat"], "lon": inp["lon"], "month": int(inp["month"]), "shape": inp["shape"],
                             "max_payout": float(inp["max_payout_usd"]), "value_at_risk": float(inp["value_at_risk_usd"]),
                             "coverage": float(inp["coverage"]), "risk_aversion": float(inp["risk_aversion"]),
                             "price_source": state.get("price_source", "auto")}, live, today)
        state.setdefault("contracts", []).append(q)
        return compact_quote(q)
    return {"error": f"unknown tool {name}"}


# ---------------------------------------------------------------------------------------------
# Claude mode
# ---------------------------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the contract advisor of AgriHedge, a research prototype built by an ECE 473 student team. You design a one-month rain insurance contract for a farmer or rancher. The contract pays a fixed amount for each rain bin (1 inch or less, 1 to 2 inches, ...) of the month's official rain total at the nearest Kalshi weather station, so the issuer can replicate it exactly with Kalshi monthly-rain contracts. The farmer bears the gap between the airport's rain and their own land (the tools report it as a hedge-effectiveness number from 0 to 1 and a verdict).

Before designing you need: (1) where the land is (an address, a town and state, or coordinates), (2) what is grown or grazed, (3) the size: acres (with the farmer's own value per acre if they give one) or the dollar amount of production they want covered. If any of these is missing, ask for it in one short message and stop; do not design yet. Everything else you may assume and state: coverage 90% (the payout starts when the month's rain is below 90% of normal), the crop's key month from crop_profile unless the farmer names months, value per acre from crop_profile unless given, risk aversion 2 (use 4 if they want disaster cover only, 1 if they want frequent small payments).

Process once you have the essentials: geocode_address, then check_location with the months you plan to cover (stop and say so if the land is outside the served area or the fit is poor in every month), then crop_profile, then size the month: value at risk = acres x value per acre x the month's season weight (or the dollar amount x the weight), maximum payout = value at risk x coverage. Call compare_shapes for the key month, pick the shape (the recommendation's shape unless the farmer asked for something specific; convex shapes such as quadratic, layered and the data-optimal shape suit disaster cover and thin order books; linear suits frequent small payments; both_tails when excess rain matters too), then design_contract for that month. Cover a second month only if the farmer asked for it or the crop's season weights make two months comparable.

Write the answer for the farmer in plain words, under 250 words, no jargon and no markdown tables. Say: what the contract pays in each rain bin, the fair premium and the all-in cost, how well it tracks their land (turn the hedge-effectiveness number into a percentage of the year-to-year swing it covers, and quote the verdict), how much of it today's Kalshi books can fill and the largest size they fill, and the assumptions you made. If the fill is small, say to size down or wait for deeper books. Use only numbers that came back from the tools. End with one sentence that this is a research prototype, not insurance or investment advice, and that the contract settles on the airport's rain, not the farm's.

If the request is unrelated to farm weather risk, answer in one sentence and offer to design a contract."""


def _client(api_key: str | None):
    import anthropic
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def _create(client, messages, system):
    """One model call. Server-side refusal fallbacks are on by default; older SDKs fall back to the plain call."""
    kwargs = dict(model=MODEL, max_tokens=16000, system=system, tools=TOOLS, messages=messages,
                  output_config={"effort": "medium"})
    try:
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except TypeError:
        return client.messages.create(**kwargs)


def _dump(block) -> dict:
    return block if isinstance(block, dict) else block.model_dump(exclude_none=True)


def _text_of(content) -> str:
    return "\n".join(b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "") for b in content
                     if (b.get("type") if isinstance(b, dict) else getattr(b, "type", None)) == "text").strip()


def _text_only_history(history: list) -> list:
    """Drop tool blocks (used when a replayed history is rejected): keep each turn's text."""
    out = []
    for m in history:
        c = m.get("content")
        if isinstance(c, str):
            text = c
        else:
            text = _text_of(c)
            if not text and m.get("role") == "user":
                continue
        if text:
            out.append({"role": m["role"], "content": text})
    return out


def claude_advise(history: list, state: dict, api_key: str | None, client=None, live=None, today=None) -> dict:
    import anthropic
    client = client or _client(api_key)
    messages = list(history)
    calls = []
    reply, status = "", "info"
    for _ in range(MAX_TURNS):
        try:
            resp = _create(client, messages, SYSTEM_PROMPT)
        except anthropic.BadRequestError as exc:
            if messages is history or len(messages) == 1:
                raise
            messages = _text_only_history(history)          # a stale replay: retry with text only
            resp = _create(client, messages, SYSTEM_PROMPT)
        content = [_dump(b) for b in resp.content]
        messages.append({"role": "assistant", "content": content})
        if resp.stop_reason == "refusal":
            reply, status = "I can't help with that request.", "error"
            break
        if resp.stop_reason == "pause_turn":
            continue
        if resp.stop_reason == "max_tokens":
            reply, status = _text_of(content) or "The answer was cut off; please ask again.", "error"
            break
        uses = [b for b in content if b.get("type") == "tool_use"]
        if resp.stop_reason != "tool_use" or not uses:
            reply = _text_of(content)
            status = "designed" if state.get("contracts") else ("question" if reply.rstrip().endswith("?") else "info")
            break
        results = []
        for u in uses:
            inp = u.get("input") or {}
            if isinstance(inp, str):
                try:
                    inp = json.loads(inp)
                except json.JSONDecodeError:
                    results.append({"type": "tool_result", "tool_use_id": u["id"], "content": "Error: invalid JSON input", "is_error": True})
                    continue
            try:
                res = run_tool(u["name"], inp, state, live, today)
                err = isinstance(res, dict) and "error" in res and len(res) <= 2
            except Exception as exc:  # a tool failure is reported to the model, not raised
                res, err = {"error": f"{type(exc).__name__}: {exc}"}, True
            calls.append({"name": u["name"], "input": inp, "ok": not err})
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": json.dumps(res, default=pf.json_default),
                            "is_error": bool(err)})
        messages.append({"role": "user", "content": results})
    else:
        reply, status = reply or "I ran out of steps before finishing; please ask again with the details in one message.", "error"
    return {"reply": reply, "status": status, "history": messages, "tool_calls": calls}


# ---------------------------------------------------------------------------------------------
# rules mode (no API key)
# ---------------------------------------------------------------------------------------------

_NUM = r"(\d[\d,]*(?:\.\d+)?)"


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_request(text: str) -> dict:
    """Pull crop, acres, dollars, value per acre, coordinates, place, months, coverage and preference out of free text."""
    t = text.strip()
    low = t.lower()
    out: dict = {"crop": crop_key(low)}
    m = re.search(_NUM + r"\s*(?:acres?|ac)\b", low)
    out["acres"] = _num(m.group(1)) if m else None
    m = re.search(_NUM + r"\s*(?:dollars|\$|usd)?\s*(?:per|/|an|a)\s*acre", low) or re.search(r"\$\s*" + _NUM + r"\s*(?:per|/|an|a)\s*acre", low)
    out["value_per_acre"] = _num(m.group(1)) if m else None
    m = re.search(r"\$\s*" + _NUM + r"\s*(k|thousand|m|million)?\b(?!\s*(?:per|/|an|a)\s*acre)", low)
    if m:
        v = _num(m.group(1)) * {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get(m.group(2) or "", 1)
        if out["value_per_acre"] is None or abs(v - out["value_per_acre"]) > 1e-9:
            out["value_total"] = v
    out.setdefault("value_total", None)
    m = re.search(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", t)
    out["lat"], out["lon"] = (float(m.group(1)), float(m.group(2))) if m else (None, None)
    out["place"] = None if m else extract_place(t)
    out["months"] = sorted({MONTH_WORDS[w] for w in re.findall(r"\b([a-z]{3,9})\b", low) if w in MONTH_WORDS})
    m = re.search(r"(\d{2})\s*%\s*coverage", low)
    out["coverage"] = float(m.group(1)) / 100 if m else DEFAULT_COVERAGE
    out["preference"] = next((s for s, words in PREFERENCES.items() if any(w in low for w in words)), None)
    out["risk_aversion"] = 4.0 if out["preference"] == "exponential" else 1.0 if out["preference"] == "linear" else 2.0
    return out


_ADDR = re.compile(r"(\d{1,6}\s+[A-Za-z0-9.' -]*?(?:Road|Rd|Street|St|Avenue|Ave|Highway|Hwy|Lane|Ln|Drive|Dr|Boulevard|Blvd|Trail|Trl|"
                   r"Route|Rte|FM\s*\d+|CR\s*\d+|County Road\s*\d+|Farm to Market\s*\d+)\.?(?:,?\s+[A-Za-z .'-]+)?(?:,?\s+[A-Z]{2})?(?:\s+\d{5})?)")
_CITY = re.compile(r"\b((?:[A-Z][a-zA-Z.'-]+\s?){1,3}),\s*([A-Z]{2}|[A-Z][a-z]+(?: [A-Z][a-z]+)?)\b(\s+\d{5})?")
_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
_NEAR = re.compile(r"\b(?:at|in|near|outside|around|by)\s+([A-Z][A-Za-z .'-]+?(?:,\s*[A-Z]{2})?)(?=[.,;]|\s+(?:on|with|and|for|I|we|my|our)\b|$)")


def extract_place(text: str) -> str | None:
    for rx in (_ADDR, _CITY):
        m = rx.search(text)
        if m:
            return m.group(0).strip().rstrip(".,")
    m = _NEAR.search(text)
    if m and not re.fullmatch(r"\d+", m.group(1).strip()):
        return m.group(1).strip()
    m = _ZIP.search(text)
    return m.group(1) if m else None


def rules_advise(history: list, state: dict, live=None, today=None) -> dict:
    user_text = " ".join(_text_of(m["content"]) if not isinstance(m["content"], str) else m["content"]
                         for m in history if m["role"] == "user")
    r = parse_request(user_text)
    calls = []
    missing = []
    if r["lat"] is None and not r["place"]:
        missing.append("where the land is (a street address, a town and state, or coordinates)")
    if r["crop"] is None:
        missing.append("what you grow or graze there")
    if not r["acres"] and not r["value_total"]:
        missing.append("how big it is (acres, or the dollar value of production you want covered)")
    if missing:
        reply = "Happy to design a contract. I still need " + "; ".join(missing) + ". You can put it all in one message."
        return {"reply": reply, "status": "question", "history": history + [{"role": "assistant", "content": reply}],
                "tool_calls": calls, "parsed": r}
    lat, lon = r["lat"], r["lon"]
    place = r["place"]
    if lat is None:
        try:
            g = geocode(place)
            lat, lon, place = g["lat"], g["lon"], g["matched"]
            calls.append({"name": "geocode_address", "input": {"address": r["place"]}, "ok": True})
        except LookupError as exc:
            reply = (f"I could not place \"{place}\" on the map ({exc}). Give me a fuller street address with town and state, "
                     "a zip code, or latitude and longitude like 32.78, -97.81.")
            return {"reply": reply, "status": "question", "history": history + [{"role": "assistant", "content": reply}],
                    "tool_calls": calls, "parsed": r}
    crop = crop_profile(r["crop"])
    months = r["months"] or [crop["key_month_number"]]
    season = CROPS[r["crop"]]["season"]
    loc = check_location(lat, lon, months, r["coverage"])
    calls.append({"name": "check_location", "input": {"lat": lat, "lon": lon, "months": months}, "ok": loc["served"]})
    if not loc["served"]:
        ns = loc["nearest_stations"][0]
        reply = (f"Your land near {place} is outside the area this prototype serves. The nearest Kalshi rain station is "
                 f"{ns['station_key']} ({ns['name']}), {ns['distance_mi']:.0f} miles away, and we only hold gridded rain history "
                 f"within about 150 miles of our eight study stations. A contract settled that far away would mostly pay in the wrong years.")
        return {"reply": reply, "status": "info", "history": history + [{"role": "assistant", "content": reply}],
                "tool_calls": calls, "parsed": r, "location": loc}
    month = max(months, key=lambda m: season.get(m, 0.0)) if len(months) > 1 else months[0]
    in_season = month in season
    share = season[month] if in_season else 1.0 / max(len(season), 1)
    vpa = r["value_per_acre"] or crop["value_per_acre_usd"]
    size = size_contract(r["acres"], vpa, share, r["coverage"], r["value_total"])
    size["in_season"] = in_season
    comp = pf.exotic_compare({"lat": lat, "lon": lon, "month": month, "max_payout": size["max_payout_usd"],
                              "value_at_risk": size["value_at_risk_usd"], "coverage": r["coverage"],
                              "risk_aversion": r["risk_aversion"], "price_source": state.get("price_source", "auto")}, live, today)
    state["comparison"] = comp
    calls.append({"name": "compare_shapes", "input": {"month": month, "max_payout_usd": size["max_payout_usd"]}, "ok": True})
    shape = r["preference"] or comp["recommendation"]["shape"]
    q = pf.exotic_quote({"lat": lat, "lon": lon, "month": month, "shape": shape, "max_payout": size["max_payout_usd"],
                         "value_at_risk": size["value_at_risk_usd"], "coverage": r["coverage"], "risk_aversion": r["risk_aversion"],
                         "price_source": state.get("price_source", "auto")}, live, today)
    state["contracts"] = [q]
    calls.append({"name": "design_contract", "input": {"month": month, "shape": shape}, "ok": True})
    reply = explain_contract(q, comp, crop, r, place, size, loc)
    return {"reply": reply, "status": "designed", "history": history + [{"role": "assistant", "content": reply}],
            "tool_calls": calls, "parsed": r, "location": loc}


def explain_contract(q: dict, comp: dict, crop: dict, r: dict, place: str, size: dict, loc: dict) -> str:
    p, pr, fb = q["product"], q["pricing"], q["farm_basis_risk"] or {}
    pays = [t for t in q["term_sheet"] if t["payout_usd"] > 0.5]
    pay_txt = ", ".join(f"${t['payout_usd']:,.0f} if it is {t['rain']}" for t in pays[:5])
    he = fb.get("he_exchange_vs_farm")
    if he is None:
        fit_txt = "fit against your land could not be scored"
    elif he <= 0:
        fit_txt = "poor match: its payouts do not line up with your land's dry years at all (hedge effectiveness at or below zero)"
    else:
        fit_txt = (f"{fb.get('verdict', 'unknown fit')}: it covers about {100 * he:.0f}% of the year-to-year swing in your land's "
                   "rain-index payout")
    caution = ("Caution: " + comp["recommendation"]["why"] + " I designed the contract you can buy anyway, but the numbers below say "
               "it is a weak fit for this land and month.\n\n" if comp["recommendation"].get("worth_buying") is False else "")
    fill = pr["fill_share"]
    fill_txt = (f"Today's Kalshi books fill about {100 * fill:.0f}% of this order" + (
        f"; the largest size they fill in full is about ${pr['largest_fillable_max_payout_usd']:,.0f} of maximum payout"
        if pr.get("largest_fillable_max_payout_usd") else "") + "." if fill is not None and pr["legs_priced_from_order_book"] > 0 else
        "No Kalshi book is open for this month yet (each month lists about 30 days ahead), so prices are estimates: fair value plus a typical spread.")
    why = comp["recommendation"]["why"] if not r["preference"] else f"You asked for {p['shape_label'].lower()} cover."
    size_txt = (f"{r['acres']:,.0f} acres at ${size['season_value_usd'] / r['acres']:,.0f} per acre" if r["acres"]
                else f"${size['season_value_usd']:,.0f} of production")
    share_txt = (f"{p['month']} carries {100 * size['month_share']:.0f}% of the season" if size.get("in_season", True) else
                 f"{p['month']} is outside the usual {crop['label']} season, so I sized it at {100 * size['month_share']:.0f}% of the season's value")
    where = place or f"{p['farm_lat']:.2f}, {p['farm_lon']:.2f}"
    return (caution + f"Here is a {p['month']} contract for your {crop['label']} near {where} ({size_txt}; {share_txt}, so "
            f"${size['value_at_risk_usd']:,.0f} is at risk and the contract pays up to ${p['max_payout_usd']:,.0f}).\n\n"
            f"Shape: {p['shape_label']}. {why}\n\n"
            f"It settles on {p['month']} rain at {p['station']} ({p['station_name']}, {p['distance_mi']} miles from you; normal is "
            f"{p['normal_in']} in). It pays {pay_txt}, and nothing when the month is wetter.\n\n"
            f"Cost: fair premium ${pr['fair_premium_usd']:,.0f}; all-in about ${pr['all_in_usd']:,.0f} with spread, fees and carry "
            f"({pr['cost_per_dollar_expected'] or 0:.2f} per $1 of expected payout). {fill_txt}\n\n"
            f"How well it tracks your land ({fit_txt}; in the worst 10% of years it pays "
            f"{100 * (fb.get('tail_capture') or 0):.0f}% of what your land's index would).\n\n"
            f"Assumptions: {100 * r['coverage']:.0f}% coverage, risk aversion {r['risk_aversion']:g}, 1951-2025 rain history. "
            f"This is a research prototype (ECE 473), not insurance or investment advice; the contract pays on the airport's rain, not your farm's.")


# ---------------------------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------------------------

def api_key_from(params: dict | None = None) -> str | None:
    k = (params or {}).get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    return k.strip() if k else None


def status() -> dict:
    key = api_key_from()
    return {"mode": "claude" if key else "rules", "model": MODEL if key else None,
            "crops": {k: v["label"] for k, v in CROPS.items()},
            "note": ("Claude designs the contract with the project's tools." if key else
                     "No ANTHROPIC_API_KEY set: a rule-based parser handles common phrasings. Add a key for free-form conversation.")}


def advise(params: dict, client=None, live=None, today=None) -> dict:
    """params: messages (list of {role, content}; the last one from the user), optional api_key, price_source, mode."""
    t0 = time.time()
    history = params.get("messages") or []
    if not history or history[-1].get("role") != "user":
        raise ValueError("messages must end with a user turn")
    for m in history:
        if m.get("role") not in ("user", "assistant"):
            raise ValueError("message roles must be user or assistant")
    state = {"price_source": params.get("price_source", "auto")}
    key = api_key_from(params)
    mode = params.get("mode") or ("claude" if (key or client is not None) else "rules")
    if mode == "claude":
        try:
            out = claude_advise(history, state, key, client, live, today)
        except Exception as exc:        # no network, bad key, SDK missing: fall back to the rule-based designer
            out = rules_advise(history, state, live, today)
            out["fallback_reason"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            mode = "rules"
    else:
        out = rules_advise(history, state, live, today)
    contracts = state.get("contracts") or []
    out.update({"mode": mode, "model": MODEL if mode == "claude" else None,
                "contract": contracts[-1] if contracts else None, "contracts": contracts,
                "comparison": state.get("comparison"), "elapsed_s": round(time.time() - t0, 2)})
    return out
