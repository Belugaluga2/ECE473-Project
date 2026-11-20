"""Expansion study: compare every expansion strategy head to head (doc 25, "Head-to-head comparison").

Question: of the expansion strategies doc 25 considered, which is most likely to succeed, against which
rivals, and why? Scores are the team's 1-5 judgments from the cited evidence (5 = best for a small
platform). They live with a one-line justification per strategy in
data/processed/expansion_strategy_scores.csv. That file is the input; edit it, not this script.

Method
  1. Criteria (all 1-5, 5 = best). Base weights are the team's judgment and sum to 1:
       demand_evidence   someone already pays for this, or measured losses imply they would      0.16
       market_size       annual premium or fees reachable in the US, from the demand model       0.10
       hedge_quality     out-of-sample HE / basis risk the buyer keeps                           0.12
       legal_path        no insurer, swap-dealer, IB or CTA registration needed to start         0.13
       capital_light     risk capital the team must hold (5 = none)                              0.09
       pricing_risk      drift, ENSO adverse selection, settlement quirks (5 = low)              0.09
       time_to_proof     can be shown working by the Dec 15 paper with team code and data        0.10
       defensibility     edge over Arbol, Blanket, Sensible, CelsiusPro, Kalshi itself           0.09
       liquidity         can it execute at today's Kalshi depth, or does not need it (5 = yes)    0.12
  2. Two aggregations:
       additive          weighted mean of scores (a strength can offset a weakness)
       weak-link         weighted geometric mean: a mild extra penalty on low scores (a 1 instead of
                         a 3 on a 0.10-weight criterion multiplies the score by 0.90). It is not a gate.
     A third view drops time_to_proof (a course deadline, not a business criterion) and renormalizes
     the other weights: the "long-run" ranking.
  3. Uncertainty: 20,000 draws. Each draw takes weights ~ Dirichlet(40 x base weights), so weights
     wander around the base (about +/-0.05 each), and each score s -> s + e with e in {-1, 0, +1},
     clipped to 1..5. Judgment criteria move with probability 0.4 (0.2 each way); criteria backed by
     a measurement (hedge_quality, market_size, liquidity) move with probability 0.2. These
     percentages measure how robust the ranking is to the team's scoring, not the odds of
     commercial success.
       P(first), P(top 3), median rank    per strategy and aggregation
       head-to-head matrix                P(row strategy scores above column strategy), weak-link
       flat-weight check                  same with weights ~ Dirichlet(1,...,1) (any weighting at all)
  4. "Why it loses": for each strategy, the weighted criterion gaps to the weak-link leader.
  5. Bias check ("data-neutral" view). The project's data and code are about PRF ranchers, so the
     scoring can favor them. This view (a) drops time_to_proof, which rewards existing team code, and
     (b) applies data/processed/expansion_strategy_overrides.csv: scores that judged non-farm segments
     in the strict cash frame while ranchers were judged in the narrow frame (doc 25, "Bias check").

Outputs (data/processed/):
  expansion_compare_summary.csv      one row per strategy: scores, both aggregates, P(first), P(top 3), ranks
  expansion_compare_h2h.csv          head-to-head probability matrix (weak-link, base-centered weights)
  expansion_compare_why.csv          each strategy's three largest weighted gaps to the leader
Figure: docs/figures/expansion_compare.png
Doc: rewrites the AUTO block in docs/analysis/25_weather_hedging_expansion.md

Usage: python scripts/run_expansion_compare.py   (about 5 s)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
FIG = REPO / "docs" / "figures"
DOC = REPO / "docs" / "analysis" / "25_weather_hedging_expansion.md"

CRITERIA = {
    "demand_evidence": 0.16,
    "market_size": 0.10,
    "hedge_quality": 0.12,
    "legal_path": 0.13,
    "capital_light": 0.09,
    "pricing_risk": 0.09,
    "time_to_proof": 0.10,
    "defensibility": 0.09,
    "liquidity": 0.12,
}
MEASURED = {"hedge_quality", "market_size", "liquidity"}
LABELS = {
    "demand_evidence": "Demand evidence",
    "market_size": "Market size",
    "hedge_quality": "Hedge quality",
    "legal_path": "Legal path",
    "capital_light": "Capital light",
    "pricing_risk": "Pricing risk",
    "time_to_proof": "Time to proof",
    "defensibility": "Defensibility",
    "liquidity": "Liquidity",
}
N_DRAWS = 20_000
CONCENTRATION = 40.0
SEED = 473
BEGIN = "<!-- BEGIN AUTO: head-to-head comparison (scripts/run_expansion_compare.py) -->"
END = "<!-- END AUTO: head-to-head comparison (scripts/run_expansion_compare.py) -->"


def additive(scores: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted mean. scores (..., n_strat, n_crit), w (..., n_crit) -> (..., n_strat)."""
    return np.einsum("...sc,...c->...s", scores, w)


def weak_link(scores: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted geometric mean: exp(sum w log s). Scores are >= 1, so it is always defined."""
    return np.exp(np.einsum("...sc,...c->...s", np.log(scores), w))


def ranks_desc(x: np.ndarray) -> np.ndarray:
    """Rank 1 = highest along the last axis; ties broken by order (stable)."""
    order = np.argsort(-x, axis=-1, kind="stable")
    r = np.empty_like(order)
    idx = np.arange(x.shape[-1])
    np.put_along_axis(r, order, np.broadcast_to(idx + 1, order.shape), axis=-1)
    return r


def simulate(S: np.ndarray, base_w: np.ndarray, rng: np.random.Generator, n: int,
             concentration: float | None, noise: bool = True,
             p_move: np.ndarray | None = None) -> dict:
    """Monte Carlo over weights (and score noise). Returns per-draw aggregates for both rules.

    p_move: per-criterion probability that a score moves by one (half up, half down); default 0.4.
    """
    k = len(base_w)
    alpha = base_w * concentration if concentration else np.ones(k)
    W = rng.dirichlet(alpha, size=n)
    if noise:
        pm = np.full(k, 0.4) if p_move is None else np.asarray(p_move, float)
        u = rng.random((n,) + S.shape)
        e = np.where(u < pm / 2, -1, np.where(u < pm, 1, 0))
        Sd = np.clip(S[None] + e, 1, 5).astype(float)
    else:
        Sd = np.broadcast_to(S[None].astype(float), (n,) + S.shape)
    return {"additive": additive(Sd, W), "weak_link": weak_link(Sd, W)}


def h2h_matrix(agg: np.ndarray) -> np.ndarray:
    """P(row > column) across draws; ties count half."""
    a = agg[:, :, None]
    b = agg[:, None, :]
    return (a > b).mean(0) + 0.5 * (a == b).mean(0)


def main() -> None:
    t0 = time.time()
    sc = pd.read_csv(PROC / "expansion_strategy_scores.csv")
    crit = list(CRITERIA)
    missing = [c for c in crit if c not in sc.columns]
    if missing:
        sys.exit(f"scores file lacks {missing}")
    S = sc[crit].to_numpy(float)
    if (S < 1).any() or (S > 5).any():
        sys.exit("scores must be 1-5")
    base_w = np.array([CRITERIA[c] for c in crit])
    base_w = base_w / base_w.sum()
    names = sc["strategy"].tolist()
    rng = np.random.default_rng(SEED)

    out = sc[["key", "strategy", "group"] + crit].copy()
    out["additive"] = additive(S, base_w)
    out["weak_link"] = weak_link(S, base_w)
    out["equal_total"] = S.sum(1)

    p_move = np.array([0.2 if c in MEASURED else 0.4 for c in crit])
    sims = simulate(S, base_w, rng, N_DRAWS, CONCENTRATION, p_move=p_move)
    flat = simulate(S, base_w, rng, N_DRAWS, None, p_move=p_move)
    # long-run view: drop time_to_proof (a course deadline) and renormalize
    keep = np.array([c != "time_to_proof" for c in crit])
    w_lr = base_w[keep] / base_w[keep].sum()
    out["weak_link_longrun"] = weak_link(S[:, keep], w_lr)
    lr = simulate(S[:, keep], w_lr, rng, N_DRAWS, CONCENTRATION, p_move=p_move[keep])
    r_lr = ranks_desc(lr["weak_link"])
    out["p_first_longrun"] = (r_lr == 1).mean(0)
    out["rank_longrun"] = ranks_desc(out["weak_link_longrun"].to_numpy())
    # how often the top three slots all come from the base top four
    r_wl = ranks_desc(sims["weak_link"])
    top4 = np.argsort(-out["weak_link"].to_numpy(), kind="stable")[:4]
    in_top3 = (r_wl[:, top4] <= 3).sum(1)
    out.attrs["p_top3_all_from_top4"] = float((in_top3 == 3).mean())
    out.attrs["p_first_from_top4"] = float((r_wl[:, top4] == 1).any(1).mean())
    for rule in ("additive", "weak_link"):
        r = ranks_desc(sims[rule])
        out[f"p_first_{rule}"] = (r == 1).mean(0)
        out[f"p_top3_{rule}"] = (r <= 3).mean(0)
        out[f"median_rank_{rule}"] = np.median(r, 0)
        rf = ranks_desc(flat[rule])
        out[f"p_first_{rule}_anyweights"] = (rf == 1).mean(0)
        out[f"p_top3_{rule}_anyweights"] = (rf <= 3).mean(0)
    out["rank_weak_link"] = ranks_desc(out["weak_link"].to_numpy())
    out["rank_additive"] = ranks_desc(out["additive"].to_numpy())
    attrs = dict(out.attrs)
    # bias check: frame-matched overrides, no time_to_proof
    ov_path = PROC / "expansion_strategy_overrides.csv"
    ov = pd.read_csv(ov_path) if ov_path.exists() else pd.DataFrame(columns=["key", "criterion", "value", "reason"])
    S_n = S.copy()
    for _, o in ov.iterrows():
        S_n[sc["key"].tolist().index(o["key"]), crit.index(o["criterion"])] = float(o["value"])
    out["weak_link_neutral"] = weak_link(S_n[:, keep], w_lr)
    out["rank_neutral"] = ranks_desc(out["weak_link_neutral"].to_numpy())
    neu = simulate(S_n[:, keep], w_lr, rng, N_DRAWS, CONCENTRATION, p_move=p_move[keep])
    r_n = ranks_desc(neu["weak_link"])
    out["p_first_neutral"] = (r_n == 1).mean(0)
    out["p_top3_neutral"] = (r_n <= 3).mean(0)
    out = out.sort_values(["rank_weak_link"]).reset_index(drop=True)
    out.attrs.update(attrs)
    out.to_csv(PROC / "expansion_compare_summary.csv", index=False)

    order = [names.index(s) for s in out["strategy"]]
    H = h2h_matrix(sims["weak_link"])[np.ix_(order, order)]
    keys = out["key"].tolist()
    h2h = pd.DataFrame(H, index=keys, columns=keys)
    h2h.to_csv(PROC / "expansion_compare_h2h.csv", float_format="%.3f")

    leader = out.iloc[0]
    why_rows = []
    for _, row in out.iterrows():
        gaps = {c: base_w[crit.index(c)] * (leader[c] - row[c]) for c in crit}
        worst = sorted(gaps.items(), key=lambda kv: -kv[1])[:3]
        best = sorted(gaps.items(), key=lambda kv: kv[1])[:1]
        why_rows.append({
            "key": row["key"], "strategy": row["strategy"],
            "loses_most_on": "; ".join(f"{LABELS[c]} ({row[c]:.0f} vs {leader[c]:.0f})" for c, g in worst if g > 0),
            "beats_leader_on": "; ".join(f"{LABELS[c]} ({row[c]:.0f} vs {leader[c]:.0f})" for c, g in best if g < 0),
        })
    why = pd.DataFrame(why_rows)
    why.to_csv(PROC / "expansion_compare_why.csv", index=False)

    pd.DataFrame([attrs]).to_csv(PROC / "expansion_compare_cluster.csv", index=False)
    print(f"P(one of the top four ranks first) = {attrs['p_first_from_top4']:.3f}; "
          f"P(top three all from the top four) = {attrs['p_top3_all_from_top4']:.3f}")
    make_figure(out, h2h)
    write_doc(out, h2h, why, sc, ov)
    print(out[["strategy", "weak_link", "additive", "p_first_weak_link", "p_top3_weak_link",
               "median_rank_weak_link", "p_top3_weak_link_anyweights"]].to_string(index=False))
    print(f"done in {time.time() - t0:.1f}s")


def make_figure(out: pd.DataFrame, h2h: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(out)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 0.42 * n + 2.2),
                                   gridspec_kw={"width_ratios": [1.0, 1.35]})
    y = np.arange(n)[::-1]
    ax1.barh(y, out["p_top3_weak_link"], color="#2a6f97", label="P(top 3), base weights ± noise")
    ax1.scatter(out["p_top3_weak_link_anyweights"], y, color="#e07a5f", zorder=3, s=22,
                label="P(top 3), any weights")
    ax1.set_yticks(y)
    ax1.set_yticklabels(out["strategy"], fontsize=8.5)
    ax1.set_xlim(0, 1)
    ax1.set_xlabel("Probability of ranking in the top 3 (weak-link score)")
    ax1.legend(loc="lower right", fontsize=8, frameon=False)
    ax1.spines[["top", "right"]].set_visible(False)

    im = ax2.imshow(h2h.to_numpy(), cmap="RdBu", vmin=0, vmax=1)
    ax2.set_xticks(range(n))
    ax2.set_xticklabels(range(1, n + 1), fontsize=8)
    ax2.set_yticks(range(n))
    ax2.set_yticklabels([f"{i + 1}. {k}" for i, k in enumerate(out["key"])], fontsize=8)
    ax2.set_xlabel("Column strategy (numbered as rows)")
    ax2.set_title("P(row beats column), weak-link score", fontsize=10)
    for i in range(n):
        for j in range(n):
            if i != j:
                v = h2h.iat[i, j]
                ax2.text(j, i, f"{v * 100:.0f}", ha="center", va="center", fontsize=6.5,
                         color="white" if abs(v - 0.5) > 0.3 else "black")
    fig.colorbar(im, ax=ax2, fraction=0.03, pad=0.02)
    fig.suptitle("Expansion strategies compared head to head (20,000 weight and score draws)", fontsize=11)
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "expansion_compare.png", dpi=150)
    plt.close(fig)


def fmt_pct(x: float) -> str:
    return "<1%" if 0 < x < 0.005 else f"{x * 100:.0f}%"


def write_doc(out: pd.DataFrame, h2h: pd.DataFrame, why: pd.DataFrame, sc: pd.DataFrame,
              ov: pd.DataFrame | None = None) -> None:
    if not DOC.exists():
        return
    text = DOC.read_text()
    if BEGIN not in text or END not in text:
        print("doc has no AUTO markers for the comparison; skipped doc update")
        return
    crit = list(CRITERIA)
    lines = [BEGIN, ""]
    lines.append("Scores (1-5, 5 = best) with base weights in the header. Weak-link = weighted geometric "
                 "mean; additive = weighted mean; long-run = weak-link without the Dec 15 time-to-proof "
                 "criterion. P(first) and P(top 3) come from 20,000 draws of weights around the base and "
                 "±1 score noise; \"any weights\" draws weights uniformly. They measure robustness to the "
                 "team's scoring, not odds of commercial success.")
    lines.append("")
    hdr = ["#", "Strategy"] + [f"{LABELS[c]} ({CRITERIA[c]:.2f})" for c in crit] + \
          ["Weak-link", "Additive", "P(first)", "P(top 3)", "P(top 3), any weights", "Long-run rank"]
    lines.append("| " + " | ".join(hdr) + " |")
    lines.append("|" + "---|" * len(hdr))
    for i, r in out.iterrows():
        cells = [str(i + 1), r["strategy"]] + [f"{r[c]:.0f}" for c in crit] + [
            f"**{r['weak_link']:.2f}**", f"{r['additive']:.2f}", fmt_pct(r["p_first_weak_link"]),
            fmt_pct(r["p_top3_weak_link"]), fmt_pct(r["p_top3_weak_link_anyweights"]),
            str(int(r["rank_longrun"]))]
        lines.append("| " + " | ".join(cells) + " |")
    a = out.attrs
    lines.append("")
    lines.append(f"One of the top four ranks first in {fmt_pct(a['p_first_from_top4'])} of draws; all three "
                 f"top slots come from the top four in {fmt_pct(a['p_top3_all_from_top4'])}.")
    lines.append("")
    top = out["key"].tolist()[:6]
    lines.append("Head to head among the top six: the chance the row strategy outscores the column "
                 "strategy (weak-link).")
    lines.append("")
    names = dict(zip(out["key"], out["strategy"]))
    lines.append("| Row beats column | " + " | ".join(f"vs #{i + 1}" for i in range(len(top))) + " |")
    lines.append("|" + "---|" * (len(top) + 1))
    for a in top:
        cells = [f"#{top.index(a) + 1} {names[a]}"] + ["–" if a == b else fmt_pct(h2h.at[a, b]) for b in top]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"Why each strategy trails the leader ({out.iloc[0]['strategy']}): the largest weighted "
                 "gaps, and where it beats the leader.")
    lines.append("")
    lines.append("| Strategy | Loses most on | Beats the leader on |")
    lines.append("|---|---|---|")
    for _, r in why.iloc[1:].iterrows():
        lines.append(f"| {r['strategy']} | {r['loses_most_on'] or '–'} | {r['beats_leader_on'] or '–'} |")
    lines.append("")
    if ov is not None:
        names = dict(zip(out["key"], out["strategy"]))
        lines.append("Bias check (data-neutral view): the ranking without the time-to-proof criterion and with "
                     "the frame-matched overrides in [expansion_strategy_overrides.csv]"
                     "(../../data/processed/expansion_strategy_overrides.csv).")
        lines.append("")
        lines.append("| Override | Score | Reason |")
        lines.append("|---|---|---|")
        for _, o in ov.iterrows():
            base = int(sc.loc[sc["key"] == o["key"], o["criterion"]].iloc[0])
            lines.append(f"| {names[o['key']]}: {LABELS[o['criterion']]} | {base} → {int(o['value'])} | {o['reason']} |")
        lines.append("")
        nn = out.sort_values("rank_neutral")
        lines.append("| Data-neutral rank | Strategy | Main rank | Weak-link (neutral) | P(first) | P(top 3) |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in nn.iterrows():
            lines.append(f"| {int(r['rank_neutral'])} | {r['strategy']} | {int(r['rank_weak_link'])} | "
                         f"{r['weak_link_neutral']:.2f} | {fmt_pct(r['p_first_neutral'])} | {fmt_pct(r['p_top3_neutral'])} |")
        lines.append("")
    lines.append("Full matrix: [expansion_compare_h2h.csv](../../data/processed/expansion_compare_h2h.csv); "
                 "scores and justifications: [expansion_strategy_scores.csv](../../data/processed/expansion_strategy_scores.csv); "
                 "figure: [expansion_compare.png](../figures/expansion_compare.png).")
    lines.append("")
    lines.append(END)
    a, rest = text.split(BEGIN, 1)
    _, b = rest.split(END, 1)
    DOC.write_text(a + "\n".join(lines) + b)
    print("updated doc 25 AUTO block")


if __name__ == "__main__":
    main()
