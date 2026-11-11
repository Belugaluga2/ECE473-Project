# Can a sports bet insure a player's injury? Feasibility note (2026-11-11)

**Status: candidate topic, not a team decision.** The proposed hook is excellent for a broad audience: "If a basketball star is hurt, can someone buy NO on 30+ points as insurance?" The literal player self-hedge fails the trading rules. For an eligible, independent party with a real financial exposure, the question becomes a testable project about whether player props track that loss. We have **not** run a historical sports backtest or established that such a hedge works.

## The exposure and the trade

Insurance starts with a financial loss, not a missed scoring target. An NBA player's missed game does not automatically mean lost salary: the [NBA–NBPA collective bargaining agreement](https://imgix.cosmicjs.com/25da5eb0-15eb-11ee-b5b3-fbd321202bdf-Final-2023-NBA-Collective-Bargaining-Agreement-6-28-23.pdf) has contract-dependent compensation protection and disability benefits. A player would have to identify a genuinely unprotected bonus, endorsement payment, or future income exposure. For a clean public study, use a **hypothetical sponsor's contractual loss from a star's injury-related absence**, or another documented commercial exposure, and say exactly when that loss occurs. Sponsor eligibility depends on exchange rules and access to nonpublic information.

The player cannot execute the example hedge. [Kalshi's NBA points market](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk) excludes current players, coaches, league and team staff, owners, certain family members, and holders of material nonpublic information. The [NBA's Porter enforcement release](https://pr.nba.com/jontay-porter-ban/) describes a player disclosing his health status, limiting his minutes to influence an underperformance prop, and betting on NBA games. Having an agent or associate place the bet would not solve the integrity problem.

For a **standard** NO-on-30+ points contract, the payoff depends on points and participation, not on a diagnosis:

| What happens | Contract treatment | Fit with an injury loss |
|---|---|---|
| Player never enters the game | Settles at an exchange-determined fair price | No guaranteed injury payment; settlement may differ from entry price |
| Player enters, is injured, finishes below 30 | NO pays $1 per contract | Pays for this subset of injuries |
| Player stays healthy, finishes below 30 | NO pays $1 per contract | False claim |
| Player reaches 30, with or without an injury | NO pays $0 | Can miss an injury loss |

The first three settlement statements follow [Kalshi's standard market rules](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk); the last follows the 30+ binary payoff. Kalshi also lists a [protected points version](https://kalshi.com/markets/kxnbaptsprot/nba-player-points-protected/kxnbaptsprot-26nov11clenyk) that can settle at a pregame fair price if a player participates in the first half but does not return after halftime without reaching the target. That protection protects a bettor from some injury-related settlement risk; it removes another would-be insurance payout.

The standard market displayed **89¢ to buy NO** on Karl-Anthony Towns scoring 30+ before the November 11, 2026 Cleveland–New York game ([market page](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk)). At that displayed price, 100 contracts would cost $89 and net only $11 if he entered and stayed below 30, versus an $89 loss if he scored 30+. This excludes [fees](https://kalshi.com/fee-schedule) and says nothing about executable depth. It is a quote snapshot, not a backtest or the price used in the separate hypothetical model below.

## A reproducible, explicitly hypothetical calculation

The companion [four-state calculator](../../scripts/experiments/sports_injury_feasibility.py) makes the basis risk concrete. These probabilities are **assumptions, not player estimates**; they do not describe Towns or the quoted game:

| State | Assumed probability | Injury loss | Standard NO net payoff per $1 contract |
|---|---:|---:|---:|
| Injury-caused did not play (DNP) | 5% | $100 | $0 in the model |
| Entered, injured, below 30 | 3% | $100 | $1 minus entry price |
| Healthy, below 30 | 30% | $0 | $1 minus entry price |
| Healthy, at least 30 | 62% | $0 | Minus entry price |

The DNP net payoff of zero **assumes** Kalshi's fair-price settlement equals the entry price; the actual exchange-determined value need not. Every modeled in-game injury ends below 30, an assumption favorable to this hedge. Prices are actuarially fair in the model, with no spread, fee, or depth limit. The assumed $100 loss is only a scale for the example.

Let L be the injury loss and X the net NO payoff per contract. The variance-minimizing quantity is Cov(L,X) / Var(X), and modeled hedge effectiveness is Cov(L,X) squared / [Var(L) Var(X)]. With the assumptions above, the fair NO price is **34.74¢**, the best position is **9.09 contracts per $100 loss**, and it cuts loss variance by only **2.42%**. To net the full $100 in the in-game injury state instead requires **153.23 contracts** and **$53.23 upfront** at the fair model price; that same position pays when the player is healthy but under 30, while the DNP state has zero net payoff. If DNP counterfactually paid as an ordinary UNDER, modeled hedge effectiveness would rise to **14.19%**. Neither number is an out-of-sample estimate.

Run the calculation with:

    .venv/bin/python scripts/experiments/sports_injury_feasibility.py

## Why a purpose-built injury market is not an easy fix

The [CFTC's June 2026 proposed rule](https://www.cftc.gov/media/14151/NPRM_PredictionMarkets060926/download) preliminarily distinguishes aggregate game and player statistics from contracts settling solely on a named player's injury. It flags the latter for harm incentives, private medical information, and difficult verification. This is a **proposal**, not an enacted categorical ban or a safe harbor for any particular points contract. In an [April 2026 filing](https://comments.cftc.gov/Handlers/PdfHandler.ashx?id=35929), major player unions asked the CFTC to prohibit injury and "under" contracts; that is their requested policy, not current law. A design study can compare a synthetic injury-linked payoff, but should not present it as a listable product. The [legal roadmap](sports_kalshi_legal_roadmap.md) maps the separate rules for players, teams, treating providers, health insurers, and any platform selling a real policy.

Timing matters too. The [NBA injury-report process](https://official.nba.com/nba-injury-report-2026-27-season) begins before game day and updates continuously. The sampled [Towns market](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk) opened on game day, not weeks ahead. A pregame prop can reprice after public injury news; buying after the news does not insure the already-known loss. A player with no listed market is unhedgeable by that prop, and those games must stay in its evaluation denominator.

## A sports project that could work

**Question:** Can an eligible, independent sponsor or broadcaster hedge a documented star-absence loss with publicly traded sports contracts, and how much coverage error comes from DNP settlement, healthy underperformance, timing, spread, and depth?

1. Define a contract-based or clearly hypothetical dollar loss and an **ex-ante** decision time. Use a fixed rule for player, strike, and trade size based only on information then available.
2. Join standard and protected Kalshi player-points markets, pregame quotes, order books, settlement, [NBA injury reports](https://official.nba.com/nba-injury-report-2026-27-season), and official game box scores. Audit data permissions and manually verify a sample of in-game injury labels. Record games with no market or no fill.
3. Compare NO-on-30+, a lower points threshold, an aggregate team outcome, and a conventional private-insurance benchmark. Keep any injury-only contract **synthetic**. Include actual DNP fair settlements, fees, bid–ask spread, and capacity.
4. Train the selection and sizing rule on earlier games and report **out-of-sample** hedge effectiveness on later games, plus the share of injury losses missed, false payouts on healthy games, cost, and worst game. Use confidence intervals clustered by player.

For the November 17 presentation, the payoff table gives an audience participation reveal: the room guesses which of four games pays the "insurance," then sees the actual rule. A first empirical chart is possible if the data join works in time; the model's 2.42% must never be presented as that chart. The final paper can test whether any existing aggregate sports contract hedges a genuine commercial exposure better than the points prop. The result may still be negative; the contribution is an auditable boundary between a bet and insurance.

## Numbers and claims ledger

| Claim or value | Source and status |
|---|---|
| November 11, 2026 Towns 30+ NO displayed at 89¢; $1 binary payoff; DNP fair-price settlement | [Kalshi standard NBA points market](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk), indexed quote retrieved 2026-11-11; exact quote time unavailable, moving price, no depth verification |
| 100 contracts at 89¢: $89 entry cost, $11 net if NO wins, $89 loss if YES wins | Arithmetic from the displayed quote and $1 binary settlement; fees excluded |
| Protected first-half exit can trigger pregame fair-price settlement | [Kalshi protected NBA points market](https://kalshi.com/markets/kxnbaptsprot/nba-player-points-protected/kxnbaptsprot-26nov11clenyk), observed 2026-11-11 |
| 5%, 3%, 30%, 62% state probabilities; $100 hypothetical loss | Explicit assumptions in [the calculator](../../scripts/experiments/sports_injury_feasibility.py), not observations |
| Fair model NO price 34.74¢; optimal 9.09 contracts; 2.42% modeled variance reduction; full-claim 153.23 contracts at $53.23; counterfactual DNP-under 14.19% | Output of [the calculator](../../scripts/experiments/sports_injury_feasibility.py); fair-price-equals-entry, zero trading costs, all in-game injuries below target |
| Player and insider trading restrictions | [Kalshi market rules](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk), [NBA enforcement](https://pr.nba.com/jontay-porter-ban/) |
| Compensation protection and disability benefits are contract-dependent | [2023 NBA–NBPA agreement](https://imgix.cosmicjs.com/25da5eb0-15eb-11ee-b5b3-fbd321202bdf-Final-2023-NBA-Collective-Bargaining-Agreement-6-28-23.pdf), Articles II and IV |
| Injury-only public-interest concerns are preliminary; unions seek an under/injury prohibition | [CFTC proposed rule](https://www.cftc.gov/media/14151/NPRM_PredictionMarkets060926/download), pp. 113–119; [player-union comment](https://comments.cftc.gov/Handlers/PdfHandler.ashx?id=35929), p. 2 |
| NBA injury reports begin before game day and are updated | [NBA official injury-report process](https://official.nba.com/nba-injury-report-2026-27-season) |
| Sampled Towns market opened on game day | [Kalshi standard NBA points market](https://kalshi.com/markets/kxnbapts/nba-player-points/kxnbapts-26nov11clenyk), observed 2026-11-11; one example only |
| November 17 presentation date | Project deadline in [AGENTS.md](../../AGENTS.md) |
