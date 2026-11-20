# Logic review: argument and red team (doc 25, second pass)

Reviewer lens: argument logic and red team. Date: 2026-11-20. Scope: [doc 25](../../analysis/25_weather_hedging_expansion.md), `data/processed/expansion_strategy_scores.csv`, and the lens notes where needed to check a claim. No repo file other than this note was changed. No web search was used; every point below comes from the report's own evidence or from a recomputation of the head-to-head scores (same weights, weak-link score, 20,000 draws, Dirichlet(40 x base), ±1 noise at 0.2/0.6/0.2; my seed, so figures differ from the script's by about a point).

## Verdict

**Sound with fixes.** The direction (distribute and structure, do not hold risk; pairing is mostly diversification; price on ENSO and recent windows) follows from the evidence. Three things do not:

- the headline's two imperatives claim more than the ranking shows;
- several first-pass sentences survive that the second pass contradicts;
- the top four share one unexamined dependency (who sells the rancher's NO at Kalshi's depth), and three of the four carry a score that the report's own evidence argues against.

With the score changes I would make, the "cluster of four" loosens into one leader (lender-financed Companion) and a five-way pack that includes the on-exchange maker and consumer-embedded guarantees.

## Issues

### Blockers

**1. "The four together take the top three slots in almost every draw" is false.** Headline, line 20. The report's own P(top 3) column sums to 263% for the four, so they fill 2.6 of 3 slots on average. Recomputed, all three slots come from the four in about 66% of draws; consumer-embedded guarantees take a slot in 26%.
Fix: "the four fill the top three slots in about two thirds of draws, and 2.6 of the three slots on average; consumer-embedded guarantees are the usual intruder."

**2. "Every pairing strategy ranks in the bottom half" and "No strategy that pairs opposite weather hedgers makes the top half" are wrong on the report's own table.** Lines 14 and 444. There are 14 strategies, so ranks 1-7 are the top half. The on-exchange two-sided maker (#6) is a pairing strategy by the report's own description ("quote the farmer's NO and the wet buyer's YES"), and the city snow book is #7.
Fix (line 14): "No strategy that pairs opposite weather hedgers on its own balance sheet makes the top five." Fix (line 444): "Every own-book pairing strategy ranks seventh or lower: the city snow book (#7), solar (#10), and the south-central rain pairing (#13)."

**3. The headline's second imperative is not supported by the ranking.** Line 12: "Net weather on Kalshi itself, not on a book of your own." The strategy that does this is #6, has P(top 3) of 5%, and is labeled "watch this winter". A headline should not instruct what the body only proposes to test.
Fix: "Headline: sell through lenders and insurers, not to them. If weather is netted at all, net it on Kalshi, not on a book of your own; that is untested."

**4. The top-ranked strategies depend on liquidity that the report shows does not exist, and the comparison never scores it.** Line 294: rancher demand is about 330 times the post-rewards NO depth at its stations (fillable share 0.31%; 7.1% with rewards on). Yet `lender_finance` gets market size 3 on "ranchers $12-24M/yr", and the SaaS row inherits a book-level HE that assumes full fills. At saved depth the serviceable rancher premium is roughly $40k-$850k a year, not $12M. Someone must sell the NO. The wet side is 1:80, so that seller is a risk-taking maker, which is exactly the role the headline says to avoid. "Leave someone else holding the risk" needs a named someone.
Fix: add a sentence to the "What the comparison says" list: "Strategies #1 and #2 are capped by executable depth (doc 22). At the Nov 2 book, ranchers could fill 0.3% of modeled demand. They need a maker on the other side, so #6 or an outside capital provider is a precondition for #2, not an alternative to it." Either add an "executable depth" criterion or lower `lender_finance` market size to 2 with that justification.

**5. "Lenders profit through droughts / have nothing to hedge" is an inference stated as fact.** Lines 24, 59, 445, 545. The evidence is two national bank years and one association:
- 2011-12 coincided with record crop prices, rising land values and large crop-insurance indemnities. The lens note itself says losses were "mitigated by crop insurance" and that herds were sold into strong prices.
- The 2010 baseline (0.77%) is a post-financial-crisis peak, so "fell from 2010" overstates the drought effect.
- Capital Farm Credit is 80.7% real-estate secured; the result may not hold for production lenders, feed-store credit or hay buyers.
- The lens note also records what lenders do lose: volume (production book −13.5% in 2011) and repayment slippage two years later. That is a loss, just not a charge-off.

The honest reading is that the lender is already hedged because its borrowers' insurance is assigned to it. That supports the lender wanting the borrower hedged, which is the distribution thesis, but it is not "nothing to hedge".
Fix (line 24): "Ag lenders showed no drought spike in charge-offs in the three episodes checked, in part because borrowers' crop insurance is assigned to them and because 2011-12 crop prices and land values were high. Their drought cost is lost loan volume and later repayment slippage, not principal." Fix (line 445): replace "because lenders profit through droughts" with "because no drought charge-off spike was found in the episodes checked". Fix (line 545): replace "profits through droughts and has nothing to hedge" with "showed no drought losses large enough to hedge in the episodes checked".

### Should-fix

**6. "It doubles when a lender fronts it. That supports the lender-financed Companion" is circular.** Line 328, and line 183 ("$24M if a lender bundles it"). The doubling is the input `t0_embedded` = 0.45 against 0.20, anchored on Ghana fair-price take-up and Sensible attach claims (`run_weather_demand.py` line 90). It is not a result. The second pass's own Ethiopia finding (8% to 24%, high default) and its remark that the lever needs a financier who controls the sale both argue for a smaller multiplier with a US bank. There is a further problem the report does not raise: the Kenya effect works on liquidity-constrained, present-biased growers. A Texas rancher with an operating line can already borrow the premium. Deferred payment adds little for him.
Fix: "The model assumes embedded take-up of 0.45 against 0.20 standalone, so the $24M figure restates that assumption. It is not evidence for the lender channel."

**7. "Upper bound" is used for a central estimate.** Lines 29, 328, step 8. $12.1M is the model's central value; its P90 is $16.8M and the embedded central is $23.5M. The interval-share argument says the central value is biased high; it does not make it a bound. The 27% liability share also does not translate into 27% of ranchers: PRF requires at least two intervals with caps per interval, so a rancher can hold some winter weight and still have open winter months. Depth (issue 4) is the bound that actually binds.
Fix: "the $12.1M central estimate is biased high by an unknown amount" everywhere "upper bound" appears, and add "and is capped far lower by executable depth".

**8. "Collateral netting and 3.5% APY remove its capital problem" overreaches.** Line 447, also line 444 ("Kalshi already nets same-event pairs for free") and line 545. Netting lowers posted collateral to the pair's worst-case loss, which the report's own table puts at 2.68 per premium against a 95% capital need of 1.74. So the exchange still demands more than an insurer's economic capital. APY offsets the funding cost of collateral, not the risk of loss. Netting is opt-in and locked per subaccount (lens note line 153). And with demand 80:1 dry-heavy the maker is mostly unpaired, so netting applies to almost none of its book.
Fix: "Collateral netting and 3.5% APY reduce its funding cost on the paired part of the book. At an 80:1 dry-heavy mix that part is small, and the unpaired part is fully collateralized."

**9. "Capital is abundant" does not imply "netting has no value" for this business.** Lines 26, 444, 530. Reinsurance capital of $800B is not on Kalshi; nothing in the report shows a route for it to quote monthly rain. Capital is cheap for Nephila and scarce in the order book (line 294). The report uses the first fact to dismiss netting as a criterion and ignores the second. Excluding "netting value" from the head-to-head is defensible; the stated reason is not.
Fix: "Capital is abundant in reinsurance and scarce on Kalshi's rain books. The binding problem is getting the first to the second."

**10. Leftover first-pass claims.**
- Line 327: "The winter rain pairing (#3)". It is now #13. Fix: "(#13; first-pass #3)".
- Line 324: "The numbers support the revised ranking" refers to the first-pass ranking. Line 326 cites "the scoring matrix" for restaurants. Fix: point both at the head-to-head.
- Line 333 heading: "Scoring matrix: snow cities, lenders and promotions lead" contradicts the headline. Fix: "Segment scoring matrix (first pass; superseded for ranking)".
- Line 342 lender row: "Hedging evidence 3, Legal path 4, total 27" still stands in the table although the paragraph above says it should be 1. Edit the row or mark it struck.
- Delivery-model table, lines 368-374: "Wholesale to lenders... 21" still leads; SaaS has legal clarity 3 there and legal path 4 in the CSV; 508(h) has demand evidence 4 there and 3 in the CSV; LP quoting says "Weather not in program; incentives cut" and "Own book... is where netting capital savings actually live", both overtaken by the DIRECNET finding. Add a "first pass, superseded" note or delete the table.
- Line 148: "Whether Kalshi's prices already embed El Niño is testable from the saved candles and has not been tested." The second pass tested November (β −0.22). Fix: "was tested on the November book only (no detectable tilt)".
- Line 106: "In practice, the netting benefit lives on an insurer's or MGA's balance sheet" directly follows the paragraph saying same-event pairs net for any account. Fix: prefix with "For cross-station and cross-month pairs,".
- Next steps: step 3 duplicates step 1. Step 2 says "Then write doc 25", which is this document.
- Numbers table line 633: "Portfolio HE for a lender's 11-farm book: not computed, open test" contradicts line 678 (0.83 / 0.53 holdout). Delete line 633.
- Numbers table line 634 still frames construction, feedlots and promotions as "the wet-side buyers the report expects"; line 331 repeats it. The second pass names solar and AIPs instead.

**11. Dangling reference.** Line 524: "see section 'Logic reviews'". No such section exists. Add it or change to a link to this folder's `logic_review_*.md` notes.

**12. "All four share a structure... each sells to a buyer that already exists" (line 443).** No buyer has been spoken to for any of the four (step 7 is "if time allows"). Insurers, lenders, retailers and RMA exist; their demand for this product is unobserved. Fix: "each targets an existing institution; none has been asked."

**13. "Zero basis" for promotions hides a timing gap the report documents elsewhere.** Lines 30 and 150 say monthly markets open about a day before the month and daily markets list near the date at forecast-informed prices. A retailer announces "refund if it rains on day D" weeks ahead. Between announcement and listing the liability is unhedged, and once the market lists, the price already contains the forecast. The retailer therefore carries exactly the risk the hedge is meant to remove. Zero basis is true of settlement and false of the hedge as a whole. See score change below.

**14. 508(h) is described as "the only fix for the 1.8x subsidy gap" without saying what would be submitted.** Lines 18, 470. Subsidized PRF for Nov-Dec and Jan-Feb already exists, and Texas uses it heavily (27% of liability). The sample farmers' open winter months are an allocation choice under PRF's interval rules, not a product gap. A 508(h) product would also settle on RMA's grid index and be delivered by AIPs, so it uses no Kalshi contract. It is a different project, not an extension of this one.
Fix: state the concrete submission (for example, relaxing the per-interval cap or raising the productivity factor for drought-weighted months), and add "a 508(h) product would not use Kalshi contracts".

**15. SaaS for "PRF insurers" has nothing to structure on the PRF side.** Lines 15, 453. AIPs do not price or design PRF; FCIC sets rates and terms. An AIP's only lever is fund designation under the SRA, which the report says is already the cheaper route. What remains is hedging retained PRF loss on Kalshi, where depth is about 19,000 contracts against $1-24M retained. The MGA and parametric-carrier half of the row is the real customer.
Fix: rename to "Structuring and pricing software for parametric MGAs and carriers" and move AIPs to a one-line "also asked" note.

### Minor

**16.** The weak-link rationale ("one fatal flaw fails the business") is applied to `time_to_proof`, which is defined as "can be shown working by the Dec 15 paper". That is a course deadline, not a business flaw. It costs 508(h) its 1. Say so, or report the ranking without that criterion.

**17.** Score noise is clipped at 1 and 5, so a 1 can only move up and a 5 only down. This slightly flatters strategies with 1s (508(h), consumer-embedded). Note it under the method.

**18.** Line 20 says "Across 20,000 draws of weights and scores, each ranks first in 14-32%". Correct, but P(first) sums to 95% for the four, so say "one of the four ranks first in 95% of draws". That is the strong claim the evidence does support, and it should replace the false one in issue 1.

**19.** Line 32 reports β = −0.22 with a 90% CI of −0.42 to 0.18. The interval is not centered on the estimate, so say it is a bootstrap interval if it is one. "No detectable tilt" on one month with DFW's conditional wet-call ratio at 1.01 (line 146) and November at 0.95x (line 692) is a test with almost no power: in November there is little ENSO signal to price. Say that.

**20.** Line 549: "selling the wet side at roughly a third off". 1.35x means priced at 74% of fair, a quarter off. "A third off" would need 1.5x. Fix: "roughly a quarter off (more in December)".

## Scores I would change

"Reorders" means reorders the top four on the weak-link score.

| Strategy | Criterion | Now | Change to | Why | Effect alone |
|---|---|---|---|---|---|
| SaaS for PRF insurers and MGAs | demand_evidence | 3 | 2 | The cited evidence is against demand: AIPs "can cede to the cheaper Assigned Risk Fund" and cannot price PRF. No buyer observed. `lender_book` got a 1 on the same kind of argument. | 3.33 to 3.10; SaaS falls from #1 to a tie for #3 with promotions. **Reorders.** |
| SaaS | time_to_proof | 4 | 3 | The team can demo the engine by Dec 15, but not on an insurer's book data. | With the above: 2.99 |
| Promotions | hedge_quality | 5 | 3 | Issue 13: unhedgeable window before listing, forecast-informed price after, and daily rain books that "almost none" trade. A $500K promotion against about $3K of volume. | 3.10 to 2.88; falls to #5, below consumer-embedded (2.90). **Reorders.** |
| 508(h) | demand_evidence, market_size | 3, 4 | 2, 3 | Issue 14: the subsidized winter product exists; the report itself says the endorsement "adds less than the sample implies". | 3.19 to 2.86; falls to #5. **Reorders.** |
| 508(h) | capital_light | 4 | 3 | Actuarial submission cost comes before any 50% advance, which needs an approved concept proposal. | small |
| Lender-financed Companion | time_to_proof | 4 | 3 | Needs a lender partner and a counsel read; neither can happen by Dec 15. Only a mock can be shown. | 3.27 to 3.16; drops to #3 alone |
| Lender-financed Companion | market_size | 3 | 2 | Issue 4, depth. Optional if a depth criterion is added instead. | further drop |
| On-exchange maker | legal_path | 4 | 5 | Own-account trading on a DCM needs no registration (the report says so, line 494). It is the cleanest path of the 14 and is scored below 508(h). | 2.68 to 2.76 |
| On-exchange maker | market_size | 3 | 2 | "$1.1B/yr weather volume" is mostly daily temperature; monthly rain books are $3-10K. | offsets the above |
| Consumer-embedded | legal_path | 3 | 2 | Same structure as `restaurant_pos` (B2B2C, needs a licensed carrier), which gets 2; `snow_mga` and `solar_pair` get 2 for needing a carrier. | 2.90 to 2.74 |
| Restaurant POS | capital_light | 3 | 2 | Same reason in reverse: consumer-embedded gets 2 for the same carrier need. | none at top |
| Lender own book | legal_path | 2 | 3 | Own-account trading by an entity on a DCM. The obstacle is supervisory, not a registration; the lender-financed version (CTA/IB questions, lending against event contracts) is scored 3 and has more legal surface. | none at top |

Inconsistencies in how criteria are applied:
- **legal_path** is defined as "no insurer, swap-dealer, IB or CTA registration needed to start". By that definition the on-exchange maker and the lender's own book need none and should outrank lender-financed (CTA/IB question) and SaaS (CTA question, per the report's own delivery-model table, which gave SaaS a 3).
- **hedge_quality** mixes settlement basis (promotions 5) with out-of-sample HE (Companion 3) and ignores executable depth throughout.
- **demand_evidence** gives 3 to four strategies on very different grounds: an RCT in another continent (lender-financed), incumbents existing (promotions), a counter-argument (SaaS) and existing program size (508(h)).

Applying the changes for the top four, the maker's legal path and consumer-embedded's legal path together gives: lender-financed 3.16, SaaS 2.99, promotions 2.88, 508(h) 2.86, maker 2.76, consumer-embedded 2.74. P(first): 38% / 19% / 15% / 14% / 4% / 8%. All three top slots come from the four in 40% of draws, down from 66%. The cluster claim weakens to "lender-financed Companion leads a loose pack of six".

## Red team: the top four

**Software for PRF insurers and MGAs.** The named first customer cannot use the product. AIPs do not set PRF price or terms and already hold cheaper federal reinsurance (issue 15). The remaining customers (Demex, Vortex, Sensible, kWh Analytics) are the firms whose core competence is exactly this engine, backed by Nephila's modeling. The engine's listed differentiators are all specific to Kalshi stations and Kalshi depth, which these carriers do not use. Defensibility 2 is acknowledged, but the deeper problem is that the product's edge is Kalshi-specific and the customers are not on Kalshi.

**Lender-financed Companion.** Three understated failures:
1. *No one to trade against* (issue 4). The lender can front the premium, but the order does not fill.
2. *The lender has no reason to do it.* The report argues the lender loses nothing in droughts. Farm Credit earns commission on PRF; Kalshi pays none. A lender would be advancing operating credit into a prediction-market account for a product that earns it nothing and competes for attention with its own PRF desk. The lens note's own best financier, a hay buyer or auction barn, is not a lender and has not been approached.
3. *First-season experience.* This winter's dry payout is about 0.66x climatology. A pilot launched now most likely collects premium at sale from ranchers who received nothing. Index-insurance take-up falls after non-payout seasons. The report's advice to "show the El Niño-conditional expectation" amounts to telling the farmer not to buy this year.

Also: the Kenya mechanism does not transfer to borrowers who already have operating lines (issue 6), and Kalshi sells one month at a time, so the lender must fund four separate purchases at prices unknown in advance.

**USDA 508(h).** Beyond time: it uses no Kalshi contract and no airport station, so the team's data advantage does not carry over; it asks RMA to subsidize months it already subsidizes; submissions are judged on actuarial soundness with loss ratios the report puts at 1.11 for Texas winter intervals, which argues for raising winter rates, not expanding winter coverage; and the incumbent delivery system (AIPs and agents) has no reason to sponsor an outsider's submission while RMA's March 2026 memo shows it policing third-party arrangements around PRF. Legal path 5 measures clarity of process, not chance of approval.

**Zero-basis promotions.** The pre-listing gap (issue 13) is the main one. Second, depth: promotions need tens to hundreds of thousands of dollars on one day at one station. Third, the Coeur d'Alene dispute the report cites as the problem being solved was resolved in the retailer's favor by the existing insurance channel, so incumbents (TMHCC) already deliver this with pre-announced pricing months ahead. Fourth, unchecked lottery law is not a footnote for a purchase-plus-chance refund; it is the legal path, and it is scored the same 3 as strategies whose open question is a registration. Finally, "cleanest demonstration that the engine works" is not accurate: doc 23's engine replicates payoffs on monthly strike bins, and a one-day binary needs none of it.

## Steelman: the bottom half

**On-exchange two-sided quoting (#6) is underrated, and is misfiled as an alternative.** It is the enabling piece for #2. It has the cleanest legal path, it is the only strategy that addresses doc 22's liquidity limit, and its flow from a lender channel would be identifiable hedging flow rather than anonymous ENSO-timed flow, which lowers the adverse-selection risk that gives it pricing_risk 2. Its weakness is real: it holds risk, and at 80:1 it is a one-sided dry-protection seller, not a netted book. But the report's ranked combination should say "#2 requires #6 or an outside maker", not "watch #6".

**City snow book (#7) is undersold by forcing it onto an MGA.** The segment matrix's top two rows (plow contractors and salt suppliers, cities; both 30/40) have no capital-light strategy in the head-to-head. The low-snow side (per-push contractors, salt suppliers) is made of entities that can trade listed monthly snow contracts directly, with zero basis at the settlement airport. A "snow Companion" for contractors, sold through salt distributors or equipment lenders, is the same play as #2 in a market with better basis and no subsidized competitor. The report checked DIRECNET only on monthly rain; whether snow events carry it is unchecked and decides whether the maker logic extends. Only the city side needs insurance paper (public procurement).

**Solar pairing (#10)**: the report's judgment holds. Nine percent of variance removed is disqualifying on listed contracts. The steelman is not the pairing but the contract: see the new lens on contract design below.

**Consumer-embedded (#5)**: fairly placed, possibly generous (legal path, above). Its real use to the team is as a SaaS customer segment, which the report already implies.

**Missed combinations.**
1. *Companion flow plus a named maker.* A lender or buyer channel aggregates dry-side orders; a capital provider (a weather fund or MGA-backed account, or the team's paper maker) quotes against them in the same events, using the team's ENSO-conditional prices. This joins #2, #6 and the "capital is abundant" finding into one design, and it is the only version in which the abundant capital actually reaches the rancher.
2. *Hay seller as financier and opposite side.* The lens note calls hay sellers "the cleanest same-index wet-side loser", and the report says a hay buyer or auction barn fits the pay-later evidence better than a bank. A hay dealer who sells to ranchers gains in drought, controls a sale, and has a trading relationship. A hay supply contract with a rain-indexed price is the Companion delivered without Kalshi tickets by the rancher at all; the dealer lays off the residual on Kalshi as an entity. It appears in neither the 14 strategies nor the combinations.
3. *Snow Companion for contractors* (above).

## New lenses

**1. Change the contract, not the customer.** Every failure in the report traces to the listed menu: one month at a time, listed a day ahead, airport-settled, no day counts, no irradiance, thin. The report treats that menu as fixed while documenting that Kalshi lists 536 weather series, most of which never trade, including a Saskatchewan growing-season index. Kalshi is evidently willing to list. The team's research is a specification for three contracts: a Nov-Feb seasonal strip listed before PRF's December 1 close (fixes the ENSO lock-in problem at line 30); a contract settled on the NOAA CPC grid index RMA uses for PRF (removes station-to-farm basis, the project's original failure); a wet-day count (fixes the venue R² of 0.27). "Sell the contract design and the demand estimate to the exchange" is a fifteenth strategy with one customer, no registration, and direct use of docs 21-24. Its risk is that Kalshi lists and nobody trades, as with Saskatchewan, which is why it pairs with the maker and the channel.

**2. Free federal drought money on the rancher's side.** The report covers ad hoc aid ($40B) for crop farmers but never mentions the Livestock Forage Disaster Program in doc 25, though it appears elsewhere in the repo. LFP pays grazing losses at no premium when the Drought Monitor reaches set levels. For the Companion's exact customer it is a free, partly overlapping drought payout, and it is growing-season weighted, which may be part of why winter is where ranchers do buy PRF. Rancher willingness to pay (the 1.42x from doc 24's utility grid) is computed as if no such payment existed. This belongs in the demand model as a reduction in the loss being hedged, and in the political-economy reading of 508(h): Congress has shown it prefers to pay ranchers after droughts for free.

**3. The ENSO cycle is a launch-timing problem, not only a pricing problem.** The report treats +2.46 ONI as this winter's adverse-selection risk. Over a longer horizon it is a sequencing fact. Dry protection is least valuable now and most valuable in the La Niña that commonly follows a strong El Niño (dry puts pay 1.49x). The right plan is to paper-trade and build the channel in winter 2026-27 and sell in the first La Niña autumn, when the product pays and the first-season experience is good. That same season is when a climatology-priced Kalshi book would be too cheap for the rancher, so the seller of the NO is the one adversely selected. Demand and maker risk peak together; the report should say which side the team wants to be on in that year.

**4. Persistence: the rancher's loss is cumulative, the contract is monthly.** A dry December after a wet autumn costs little; the fourth dry month in a row forces hay purchases and herd liquidation. Monthly binaries bought one at a time cannot pay on a run, and each month's price after a dry month will already reflect the forecast. HE measured against a rain-index payout does not see this. A cumulative-deficit design (doc 23's replication engine could build one across months only if months were listed together, which returns to lens 1) is the product a drought actually calls for.

**5. The PRF agent, not the lender, is the existing channel.** Interval selection is advised by crop-insurance agents paid by commission. They already decide which months the rancher leaves open, they have the customer list, and they are the group that would oppose or sponsor anything touching PRF. The report names Farm Credit only in its role as an agent. Independent agents are untested as a channel and are the likeliest political opponents of a Kalshi-based add-on that pays them nothing; RMA's rebating memo is aimed at arrangements in their territory.

**6. Other parties on the opposite side of a dry Texas winter**, beyond those in the lens note (solar, cotton and pecan harvest, water utilities, hay sellers): feeder-cattle buyers and feedlots, who buy cheaply when drought forces herd sales (a price channel, not a mud channel, and much larger than the mud effect scored in the segment matrix); and oilfield and road contractors whose winter workdays are lost to rain. The first is the more important: the rancher's forced-sale loss is the stocker buyer's gain in the same auction barn that the report proposes as financier. That makes the auction barn a place where both sides already meet.
