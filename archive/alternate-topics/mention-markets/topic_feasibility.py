"""Data-availability check for the three candidate new topics (docs/NEW_TOPIC_OPTIONS.md).

Prints the counts quoted in that doc's numbers table. Needs internet; under 5 minutes.

    .venv/bin/python scripts/experiments/topic_feasibility.py

1. Kalshi mention markets: settled strikes / events / contracts per series, live + historical
   tiers combined (agri_hedge.kalshi.KalshiClient.list_all_markets), and whether archived
   markets still have hourly bid/ask candles.
2. Polymarket wallets: all-time PnL leaderboard (data-api v2) and per-wallet trade history.
3. Polymarket disputes: share of the highest-volume closed markets (gamma API) whose
   umaResolutionStatuses history contains "disputed".
"""
import datetime as dt
import json
import urllib.request

from agri_hedge.kalshi import KalshiClient

MENTION_SERIES = ["KXTRUMPMENTION", "KXTRUMPSAY", "KXFEDMENTION", "KXPOWELLMENTION",
                  "KXSNFMENTION", "KXEARNINGSMENTIONJPM"]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ece473-feasibility/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def kalshi_mentions():
    c = KalshiClient(delay=0.05)
    series = c.list_series(category="Mentions")
    print(f"[kalshi] series in category Mentions: {len(series)}")
    for tk in MENTION_SERIES:
        st = [m for m in c.list_all_markets(tk) if m.get("result") in ("yes", "no")]
        ev = {m["event_ticker"] for m in st}
        vol = sum(float(m.get("volume_fp") or m.get("volume") or 0) for m in st)
        yes = sum(m["result"] == "yes" for m in st)
        ct = sorted((m.get("close_time") or "")[:10] for m in st)
        span = f"{ct[0]}..{ct[-1]}" if ct else ""
        print(f"[kalshi] {tk}: {len(st)} settled strikes, {len(ev)} events, "
              f"yes-rate {yes / max(1, len(st)):.2f}, {int(vol):,} contracts, {span}")
    # Candle check on the oldest settled Fed-mention strike (archived tier).
    mk = sorted((m for m in c.list_all_markets("KXFEDMENTION") if m.get("result")),
                key=lambda m: m.get("close_time", ""))
    m = mk[len(mk) // 2]
    t0 = dt.datetime.fromisoformat(m["open_time"].replace("Z", "+00:00"))
    t1 = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
    cs, tier = c.get_candles_any("KXFEDMENTION", m["ticker"], int(t0.timestamp()),
                                 int(t1.timestamp()), m.get("_tier") == "historical",
                                 period_interval=60)
    has_ba = bool(cs) and "yes_bid" in cs[-1] and "yes_ask" in cs[-1]
    print(f"[kalshi] candles {m['ticker']} ({tier} tier): {len(cs)} hourly, bid/ask present: {has_ba}")


def polymarket_wallets():
    d = get_json("https://data-api.polymarket.com/v2/leaderboard?limit=5&time_period=all")["data"]
    for x in d:
        print(f"[polymarket] rank {x['rank']} {x['user_name'][:24]}: pnl ${x['pnl']:,.0f}, "
              f"volume ${x['volume']:,.0f}")
    w = d[0]["user_id"]
    t = get_json(f"https://data-api.polymarket.com/v2/trades?user={w}&limit=500")["data"]
    first = dt.datetime.fromtimestamp(min(x["timestamp"] for x in t), dt.timezone.utc) if t else None
    print(f"[polymarket] trades endpoint for rank-1 wallet: {len(t)} rows in first page, "
          f"oldest {first:%Y-%m-%d}" if first else "[polymarket] no trades returned")


def polymarket_disputes():
    seen, disputed, ex = 0, 0, []
    for off in range(0, 2000, 500):
        page = get_json("https://gamma-api.polymarket.com/markets?limit=500&offset="
                        f"{off}&closed=true&order=volumeNum&ascending=false")
        if not page:
            break
        for m in page:
            seen += 1
            s = m.get("umaResolutionStatuses") or "[]"
            try:
                s = json.loads(s)
            except (TypeError, ValueError):
                s = [s]
            if any("disput" in str(x).lower() for x in s):
                disputed += 1
                if len(ex) < 5:
                    ex.append(f"{m['question'][:60]} (${float(m.get('volumeNum') or 0):,.0f}, "
                              f"{sum('disput' in str(x) for x in s)} disputes)")
    print(f"[polymarket] disputed: {disputed} of {seen} highest-volume closed markets returned")
    for e in ex:
        print(f"[polymarket]   {e}")


if __name__ == "__main__":
    kalshi_mentions()
    polymarket_wallets()
    polymarket_disputes()
