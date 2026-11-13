# Presentation: how AgriHedge changed

The [PowerPoint](AgriHedge_Journey_2026-11-17.pptx) has 11 slides with speaker notes and editable charts. The [PDF](AgriHedge_Journey_2026-11-17.pdf) is the offline projection copy. Both tell one research story: **Can listed rain contracts add useful farm protection alongside PRF?**

## Ten-minute run of show

| Slide | Time | Speaker | Decision or handoff |
|---|---:|---|---|
| 1. Question | 0:00–0:20 | Jack | State the question and promise the sequence of tests. |
| 2. Original idea | 0:20–1:45 | Jack | PRF and Kalshi both depend on rain, so replacement looked plausible. |
| 3. First test | 1:45–2:35 | Jack | Replacement failed on cost, payout fit and fill. Hand off to Maya: why? |
| 4. Diagnosis | 2:35–3:35 | Maya | Distance, settlement source, month length and book depth explain the loss. |
| 5. Pivot | 3:35–4:25 | Maya | Keeping PRF and covering months farmers left unselected fit better. Hand off to Evan: what should the added contract pay? |
| 6. Payout design | 4:25–5:10 | Evan | Introduce linear and drought-weighted shapes. |
| 7. Modeled value | 5:10–6:00 | Evan | Show the utility result with its assumptions. |
| 8. Retest | 6:00–6:45 | Evan | Equal-premium comparison overturns the claimed liquidity advantage. Hand off to Jack: what does a real quote expose? |
| 9. Demo | 6:45–7:50 | Jack | Show the term sheet, price source and compare-shapes table. |
| 10. Method | 7:50–9:05 | Maya | Explain the holdout and the distinction between rain-payout fit and farm loss. |
| 11. Conclusion | 9:05–9:50 | Jack | Give the narrow answer and next tests. Leave a ten-second buffer. |

The goal occupies roughly the first two minutes, results and demo the next five, method about two, and the close about one. The slide notes contain speaking cues and transitions rather than text to read verbatim. Rehearse the handoffs and stop at 9:50; the course stops the talk at 10:00.

## Demo preflight

1. Run the project virtual environment's Python on scripts/run_app.py from the repo, then open http://localhost:8473/?demo=exotic.
2. Click **Design this contract**. Show the station-settled term sheet and the price-source label. The default future month can have no listed book, in which case the app marks the quote estimated.
3. Click **Compare every shape for this month** and show the same-premium column. Do not compare shape fill percentages at different premiums.
4. If the browser stalls, stay on slide 9. Its fill figure is from the saved November 2, 2026 book; it is not a current executable quote.

The Claude advisor path was exercised with a scripted fake client, not the live API. The rule-based advisor works in the demo, but it is outside the timed path.

## Numbers used in the slides

| Claim | Value | Source and scope |
|---|---:|---|
| Kalshi hedge cost relative to producer-paid PRF, per dollar of expected payout | about 1.8× | [Doc 09](../analysis/09_payout_comparison.md), 11 farms, historical pricing assumptions |
| Replacement payout fit after saved book depth | 0.18 | [Doc 16](../analysis/16_error_budget.md), pooled leave-one-year-out hedge effectiveness; 0.17 is after the added PRF-sized budget limit |
| Intended hedge fillable near fair value after rewards ended | 20% | [Doc 12](../analysis/12_post_rewards_liquidity.md), 11-farm aggregate, one saved snapshot |
| Selected error-budget stages: ideal, geography, settlement source, monthly contracts, book depth | 1.00, 0.65, 0.52, 0.33, 0.18 | [Doc 16](../analysis/16_error_budget.md), pooled leave-one-year-out fit; slide 4 omits the other stages |
| Companion vs copying PRF intervals; farms recommended | 0.61 vs 0.23; 9 of 11 | [Doc 21](../analysis/21_prf_companion.md), 2001–2025 holdout, medians over 10 farms with a companion pick; recommendation across 11 farms; rain-payout target |
| Modeled best-contract value captured by exponential, quadratic, linear | 93%, 90%, 67% | [Doc 24](../analysis/24_contract_design.md), 111 bought-cover farm-months of 132 candidates, best-sized shapes, risk aversion 2, wealth 2× monthly value, 20% price load |
| Same-premium fit at saved November 2 book depth: linear, layered, quadratic, exponential | 0.18, 0.16, 0.12, 0.11 | [Doc 24](../analysis/24_contract_design.md), 36 insured windows; none of the convex shapes beat linear in any window at equal premium |
| Dallas quadratic November contract: maximum payout, modeled fair premium, fill near fair value | $6,000; $1,205; 13% | [Doc 23](../analysis/23_exotic_payouts.md), saved November 2, 2026 order book |
| Data split for the contract-design holdout | 1951–2000 train; 2001–2025 test | [Doc 24](../analysis/24_contract_design.md) |

## Q&A guardrails

- **What does “fit” mean?** Hedge effectiveness is the fraction of variance in a defined payout target removed by the hedge. It does not measure the share of real farm loss insured.
- **Does PRF leave winter unavailable?** No. The representative farmers did not select those intervals. The loss model gives winter a small share of forage value, so the companion result is strongest as a rain-payout tracking result.
- **Why use a drought-weighted shape if linear has better equal-premium fit?** The two measures answer different questions. The convex shape gives higher value to the modeled risk-averse farmer at its best size; it does not improve fit per dollar at the saved book depth.
- **Can the issuer replicate the payout exactly?** A fully filled portfolio matches the station-settled term sheet on the listed strike bins. Missing legs leave exposure, and the farmer retains airport-to-farm basis risk.
- **Is the $1,205 Dallas contract executable?** It is a modeled fair premium for the full maximum payout. The saved book filled 13% near fair value. A current future-month quote may be estimated because no book exists yet.
- **What remains unproved?** Reduction of observed farm-income loss, farmer preferences for the payout shape, and enough market depth to place a useful order.

The separate [archive index](../../archive/README.md) identifies alternative topic research and unmerged exploratory branches. Those paths did not supply the deck's main result.
