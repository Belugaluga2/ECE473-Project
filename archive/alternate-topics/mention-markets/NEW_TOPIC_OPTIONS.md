# New topic options: three more presentable prediction-market projects (2026-11-10)

We have permission to switch topics. This doc brainstorms the three strongest options and plans each one through the 2026-11-17 slides and the 2026-12-15 paper. All three have **data that works today**: every count below came from a live API call on 2026-11-10 (`scripts/experiments/topic_feasibility.py`, under 5 minutes, needs internet).

| | A. "Say the word" | B. "Copy the whale" | C. "Was that a suit?" |
|---|---|---|---|
| One line | A market maker for Kalshi mention markets ("Will Powell say *recession*?") | Does copying top Polymarket wallets make money once you account for lag, slippage and luck? | Do LLMs resolve disputed markets by the facts or by the vote? |
| Course topic | 1a, a market maker built for one domain | 2b copy trading (+5a trader behaviour) | 2b LLMs as market resolvers (+2a, is resolution risk priced?) |
| Hook for the room | Class bets on what a speaker will say | "Should you copy the guy who made $22M?" | Show the photo, class votes "suit or not?" |
| Data verified | 465 mention series; Trump alone: 7,368 settled strikes, 261M contracts; hourly bid/ask kept even for archived markets | Wallet trades and an all-time PnL leaderboard on Polymarket data-api v2 | Dispute history on every Polymarket market; 40 of the 400 highest-volume closed markets were disputed |
| Reuse of our code | High: `kalshi.py` client (live + historical tiers), bid/ask pricing, fee model, holdout discipline | Low: new venue, new data model | Low: new venue; no pricing code needed |
| Hardest part | Transcript corpus and word-counting rules | Data volume; avoiding survivorship bias | Hand-labelling ground truth; evidence leakage |
| Evaluation | Brier/log loss, calibration, market-maker PnL and tail loss vs baselines | Out-of-sample skill vs a luck baseline; copy PnL vs lag; capacity | Agreement with fact vs with vote; risk-coverage curve; inter-annotator agreement |
| **Verdict** | **Recommended** | Strong backup (most "story") | Funniest, but most manual labour |

**Recommendation: A.** It has the best mix of fun, a clean evaluation and reuse of what we built. B and C are good, but each starts from zero code and has a slow manual step (wallet universe construction, hand labelling) that is risky with the slides one week out.

## Numbers table

| Number | Value | Source |
|---|---|---|
| Kalshi series in category "Mentions" | 465 | `GET /series?category=Mentions`, 2026-11-10 |
| KXTRUMPMENTION settled strikes / events / contracts | 7,368 / 258 / 261,140,816 (2025-04-02 to 2026-11-09; 43% settled yes) | `topic_feasibility.py` (live + historical `/markets`) |
| KXTRUMPSAY settled strikes / events / contracts | 1,813 / 62 / 87,508,780 (2025-08-08 to 2026-11-10; 54% yes) | same |
| KXFEDMENTION settled strikes / events / contracts | 592 / 15 / 21,036,384 (2025-01-30 to 2026-10-28; 35% yes) | same |
| KXPOWELLMENTION | 182 / 7 / 2,323,982 (30% yes) | same |
| KXSNFMENTION (Sunday Night Football) | 311 / 13 / 6,261,540 (47% yes) | same |
| KXEARNINGSMENTIONJPM (one of many earnings series) | 77 / 5 / 740,751 | same |
| Archived market keeps hourly bid/ask candles | yes: KXFEDMENTION-26JAN-EGG has 1,022 hourly candles with `yes_bid` / `yes_ask` | `/historical/markets/{ticker}/candlesticks` |
| Polymarket all-time PnL rank 1 | Theo4: $22.05M PnL on $43.0M volume | `data-api.polymarket.com/v2/leaderboard?time_period=all` |
| Polymarket ranks 2-5 | swisstony $18.5M PnL on $1.85B volume; Fredi9999 $16.6M; RN1 $13.4M; kch123 $11.4M | same |
| Wallet trade history available | yes: first 500-row page for Theo4 goes back to 2024-10-15; full depth of pagination **unverified** | `data-api.polymarket.com/v2/trades?user=` |
| Disputed share of top-volume closed markets | 40 of 400 (the API returned 400 rows for offsets 0-1999) | `gamma-api.polymarket.com/markets`, `umaResolutionStatuses` contains "disputed" |
| "Will Zelenskyy wear a suit before July?" | $242.2M volume, disputed 5 times | same |
| Other big disputed markets | MicroStrategy sells BTC by May 31 2026 ($375.8M, 2 disputes); US forces enter Iran by Apr 30 ($269.0M, 2) | same |

Old Polymarket endpoints (`data-api` v1, `lb-api`) are retired and return an error. Use v2.

---

## A. "Say the word": a market maker for mention markets (recommended)

**Question.** Kalshi lists hundreds of contracts on whether a speaker says a word: Trump speeches and interviews, Fed press conferences, earnings calls, Sunday Night Football commentary. Are they priced well? Can a model built for this domain (speaker, event type, recent news) beat the market's own price, and can a market maker quoting around that model earn the spread without blowing up on the tail?

**Why it presents well.**
- Opening slide: three real strikes and their results. Fed mentions: "Good Afternoon" settled **yes** (January 2025), "Egg" settled **no** (January 2026). Trump "Tomahawk" (Nov 2026) settled yes. Ask the room for odds, then reveal the market's odds and ours.
- Live demo: our quotes next to Kalshi's for the next scheduled speech.
- Everyone understands the payoff, and settlement is a transcript, so no basis risk to explain.

**Data.**
- Markets: settled strikes for every mention series, live + historical tiers, through `KalshiClient.list_all_markets`. Prices from hourly candles (bid/ask/close/volume) and `/trades` for finer timing around the event start.
- Settlement rules: each series' rulebook text (what counts as a mention: plurals, possessives, compound words, who must say it). These rules are a finding in their own right.
- Transcripts (sources still to confirm): Fed press-conference transcripts on federalreserve.gov; earnings-call transcripts; Trump speeches (White House, C-SPAN, Roll Call Factba.se); NFL broadcast captions are the hardest, so skip SNF at first.
- Scope to start: Trump (~258 events) + Fed/Powell (~22 events) + 5-10 high-volume earnings series. That is enough events for a leave-one-event-out holdout.

**Method.**
1. **Forecaster.** Per (speaker, word): mention count as Poisson / negative binomial with rate ∝ expected duration. Features: the speaker's historical rate for the word, event type (rally / press conference / interview / earnings call), whether the word appears in that week's news, and the duration market where it exists (KXTRUMPMENTIONDURATION). Price the "N+ times" ladder from the same count distribution. Optional add-on: an LLM shown only evidence dated before the event.
2. **Baselines.** (i) the market mid 1 h and 24 h before the event, (ii) the historical base rate, (iii) a zero-shot LLM, (iv) a general-purpose forecast that ignores speaker and event type.
3. **Market maker.** Quote bid/ask around the model price with an inventory skew (Avellaneda-Stoikov style), only before the event starts; pull all quotes at start (live speech = fast information, adverse selection). Fill model: our bid fills if a trade prints at or below it in that hour (conservative). Fees from our existing Kalshi fee code.
4. **Correlation risk.** Strikes within one event co-move (if Trump talks about Iran, "Iran", "Tomahawk", "missile" all fire). Measure that correlation and size inventory per event, not per strike.

**Evaluation.** Brier, log loss, calibration curve and sharpness, out of sample (leave one event out; plus a time split: fit before 2026-06, test after). Market maker: PnL per event, spread captured vs adverse selection, worst event, inventory at start. Report where the market is biased (e.g., overpricing rare words: a longshot bias), with confidence intervals.

**Theory hook.** No-arbitrage across the count ladder (P(≥1) ≥ P(≥3) ≥ P(≥5)), and a bound on the market maker's worst-case loss per event when strikes are correlated through a shared topic factor.

**Team split (suggested; swap freely).** Jack: Kalshi pull, candles, fill model and market-maker backtest (extends `kalshi.py`, `pricing.py`). Evan: transcript corpus, settlement-rule parser, word counter, checked against Kalshi results. Maya: forecaster, baselines, calibration and holdout.

**Schedule.**
| When | Goal |
|---|---|
| 11/11-11/12 | Finish Milestone II on PRF as planned (no change). Pull all mention markets + candles into `data/processed/mentions/`. |
| 11/13-11/15 | Fed + Trump transcripts for ~50 events; base-rate model; first Brier vs market-mid comparison and one calibration plot. |
| 11/16-11/17 | Slides: 2 slides on the PRF result and why we pivoted, then the mention-market hook, data, first calibration plot, plan. |
| 11/18-11/30 | Full forecaster with features, LLM add-on, ladder pricing; market-maker backtest. |
| 12/01-12/08 | Correlation and tail-risk analysis, robustness (by speaker, by time period), theory section. |
| 12/09-12/15 | Paper. |

**Risks and how we'd know early.**
- Transcripts for Trump events are hard to get in bulk → fall back to Fed + earnings calls (official transcripts, clean). Decide by 11/14.
- Hourly candles are too coarse before the event → use `/trades` for the last few hours.
- The market is already well calibrated → that's a publishable null; the market-maker spread result still stands.

---

## B. "Copy the whale": does copy trading survive lag, slippage and luck?

**Question.** Polymarket shows every wallet's trades. If you had copied the top wallets, would you have made money after a realistic delay and slippage, and do the "skilled" wallets beat a luck baseline out of sample? When a wallet knows it is being copied, does it change behaviour (split orders, trade later)?

**Why it presents well.** The leaderboard is a story: Theo4 made $22M (the 2024 election whale); swisstony made $18.5M on $1.85B of volume, which is market-maker behaviour, not betting. Slide: "If you'd copied Theo with a 1-hour lag, you'd have made ___." Demo: a follow-the-whale dashboard on live wallets.

**Data.** `data-api.polymarket.com/v2/trades?user=` (per-wallet trades), `v2/leaderboard`, gamma `/markets` for outcomes, CLOB price history for the price at copy time (endpoint to confirm).

**Method.**
1. **Universe without survivorship bias.** Build the wallet set from all trades in a window, not from today's leaderboard, which only lists the winners.
2. **Skill persistence.** Rank wallets on period 1 (e.g., before 2025-07) by PnL and by entry-price Brier; test on period 2. Luck baseline: simulated wallets with the same trade count and entry prices, with outcomes drawn at the entry price.
3. **Copy simulation.** Enter at the price after a 1 min / 1 h / 1 day lag, with slippage from order-book depth; report net PnL vs lag and the capacity curve (PnL as copied capital grows).
4. **Game.** Leader-follower (Stackelberg / signalling) model: a leader with a private signal chooses order splitting and timing knowing followers copy with a lag. Comparative statics to test: does order size per trade fall after a wallet gets popular?

**Evaluation.** Out-of-sample skill vs the luck baseline, copy PnL after costs by lag, capacity, and the comparative-statics test.

**Team split.** Jack: data pipeline and storage. Maya: skill persistence and luck baseline. Evan: copy simulator and the game model.

**Schedule.** 11/13-11/15 pull trades for the top ~500 wallets plus a random sample; 11/16-11/17 slides with first persistence result; 11/18-12/05 copy simulator, capacity, game; 12/06-12/15 paper.

**Risks.** Data volume and API pagination limits (unverified); many top wallets may be market makers or insiders, so we need to classify wallets first; the ethics of insider-trading wallets deserve a paragraph.

---

## C. "Was that a suit?": LLMs as resolvers of disputed markets

**Question.** When a Polymarket market is disputed, the UMA token-holder vote decides. Does the vote match the facts? Can off-the-shelf LLMs (a) spot ambiguous questions before they're disputed, and (b) resolve them correctly afterwards, measured against facts we label ourselves, not just against the vote? Secondary: is dispute risk visible in prices (spread, late price drift) before it happens?

**Why it presents well.** The Zelensky-suit market had $242M of volume and was disputed five times. Slide: the photo; the room votes; then show what UMA decided and what each LLM said. Other cases are high-stakes (Iran, a government shutdown, MicroStrategy selling Bitcoin).

**Data.** gamma `/markets`: `umaResolutionStatuses` (proposed / disputed history), `resolutionSource`, `umaBond`, rules text, outcome. 10% of the highest-volume closed markets were disputed, so a full scan should yield several hundred disputed markets plus matched undisputed controls.

**Method.**
1. **Benchmark.** About 150-200 disputed markets + matched controls. All three of us label each disputed one from evidence frozen at the resolution date (news archives, Wayback snapshots). Report inter-annotator agreement (Fleiss' kappa) and keep the disagreements as an "irreducibly ambiguous" class.
2. **Models.** 2-3 frontier models + 1-2 open models, each with and without retrieval over the frozen evidence. Prefer markets that resolved after each model's training cutoff to avoid leakage.
3. **Ex-ante task.** From the question text and rules alone, predict whether the market will be disputed.
4. **Selective resolution.** Each model abstains below a confidence threshold; plot the risk-coverage curve.

**Evaluation.** Agreement with vote vs agreement with fact, calibration, abstention coverage, by category (politics, crypto, sports, geopolitics), and ex-ante dispute AUC vs chance.

**Team split.** All three label (the bottleneck). Jack: data scan and evidence freezing. Maya: model runs and selective-prediction curves. Evan: ex-ante classifier and the price test.

**Schedule.** 11/13-11/15 full dispute scan and labelling guide; 11/16-11/17 slides with the case studies and first LLM-vs-vote numbers on ~30 markets; 11/18-12/05 finish labelling, all models, risk-coverage; 12/06-12/15 paper.

**Risks.** Labelling time (budget ~10 h per person); API cost for model runs; leakage if models already know the outcome.

---

## Decision and what to do this week

1. Agree on A, B or C at the next team meeting (by 11/12, alongside the Milestone II submission). If A, Jack can start the Kalshi pull on 11/11 since it reuses `kalshi.py`.
2. Milestone II (11/12) stays on the PRF Companion; it is done and should not change.
3. The 11/17 slides tell the arc: the question we started with → Milestone I "no" and why (cost, geography, liquidity) → the pivot → the new topic with first results. The failed replication is a strength there, not something to hide.
4. If we pivot, `docs/FINAL_PROJECT_PROPOSAL.md` (the "insure before you know" plan) becomes the fallback, not the plan; update `AGENTS.md` and `00_OVERVIEW.md` once the team decides.
