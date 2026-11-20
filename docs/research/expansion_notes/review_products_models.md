# Independent review: alternative product mechanisms and business models

Reviewer avenue: ways to deliver weather protection other than "customer buys exchange-listed contracts" or "classic parametric insurance". I researched this first, then compared it with the six existing notes in this folder. Current as of 2026-11-19.

Method note: about 30 searches and fetches. I opened only the Fortune (Blanket) and Tokio Marine HCC pages in full. Every other figure comes from search-result extracts of the linked page, so quote them with that caveat or open the page first. Dates are flagged where the evidence is old.

---

## Top 5 additions

1. **Pay-at-harvest premium timing beats price cuts by a wide margin.** In a Kenyan RCT, take-up was 5% when the premium was paid upfront and 72% when it was deducted at harvest; a 30% price cut raised take-up only to about 6% (Casaburi & Willis, AER 2018). The notes list "upfront cash" as a barrier but don't have this evidence. Kalshi needs full collateral at purchase, so the most effective demand lever available to the team is a third party (lender, co-op, hay buyer) that fronts the premium and nets it from later sales. **Add to the final report.**
2. **The lender or co-op as wholesale buyer (meso-level cover and risk-contingent credit).** Lenders and co-ops already buy index cover on their loan books: CLIMBS (Philippines), JCCUL/Howden/Munich Re (Jamaica), One Acre Fund/Global Parametrics (Zambia, Malawi), and La Positiva's El Niño cover sold to a Peruvian MFI. Kenyan RCTs find that loans with a drought offset are taken up more than plain loans, though the size of the effect varies across reports. This is the cleanest fit for Kalshi: one sophisticated account, and a portfolio that averages out farm-level basis risk. The notes mention bundling with credit only in passing. **Add.**
3. **Weather-contingent promotions and rebates, where the liability is the index.** Retailers (jewelers, furniture stores, auto dealers) offer "refund if it snows X inches on day D" and insure it through contingency carriers (Tokio Marine HCC, BUA; minimum premium $250, older pricing 1.5-5.5% of promoted sales). US seed firms have run drought rebates (Monsanto cotton 2006-07, Syngenta Weather Protection Program c. 2020). If the promotion is written on a Kalshi settlement station, the retailer's liability matches the contract exactly, so there is no basis risk. Holiday wet/snow promotions also sit on the opposite side, in the same months, from the companion's Nov-Feb dry protection. No existing note covers this. **Add.**
4. **Kalshi-side "advisor" competition, and SaaS as the low-capital business model.** An external AI tool, Blanket (live Aug 2026), already maps a small business's described risk to Kalshi markets and logs "near misses" as demand signals. That is close to the team's `advisor.py`. Insurer-facing structuring SaaS already exists (CelsiusPro white-label, Riskwolf usage-priced API, Arbol's broker platform). The notes discuss risk-taking models (MGA, dealer, market maker) but not "sell the pricing and structuring engine and take no risk". **Add, as positioning and a differentiation check.**
5. **The federal route to subsidy: an RMA 508(h) or index-based weather plan submission.** The team's own finding is that Kalshi costs about 1.8x subsidized PRF. The only way to close that gap is to put a design on federal paper. FCIC accepts private 508(h) products, has a separate rule track for index-based weather plans (2016), and can advance 50% of expected R&D costs after an approved concept proposal. I found no weather 508(h) approval in the 2025 board minutes, so this would be slow and uncertain. **Add as a "long path" option in the roadmap.**

---

## Idea-by-idea findings

### A. Premium timing: pay at harvest or deferred premium (new)

**What it is.** The premium is deducted from sale proceeds at harvest, with interest, instead of paid upfront. This needs an interlinked counterparty that pays the farmer later: a contract buyer, co-op, processor or lender.

**Evidence**
- In a contract-farming RCT with 605 Kenyan farmers, take-up was 5% when paid upfront and 72% when paid at harvest (premium plus 1% per month interest). A 30% discount raised upfront take-up to about 6%, not significantly different. A cash transfer equal to the premium added 20 pp. The poorest farmers increased demand most. — [Casaburi & Willis, AER 2018](https://www.aeaweb.org/doi/10.1257/aer.20171526); [working paper](https://www.atai-research.org/wp-content/uploads/2017/08/aer.20171526.pdf). The experiment ran about 2014-15 (unverified). A further result, that pre-committing a month ahead adds 21 pp, appears in the working paper; check the published version before quoting it.

**Why it matters here.** It shows that "farmers won't pay" (uninsured_farmers.md, Q5) is partly about when they pay, not how much. Kalshi can't defer premium, but a hay buyer, feedlot, co-op or lender can buy the contracts and recover the cost at sale. The team's companion would then be sold to that intermediary rather than to the rancher. Legally, if the intermediary hedges its own receivable or supply risk on Kalshi, no insurance license is needed (inference). If it passes protection on to farmers as a promise, it likely becomes insurance; see market_maker_model.md Q5 on the insurable-interest safe harbor.

**Gaps.** No US evidence. Whether US ranchers have the same liquidity constraint at PRF purchase time is untested. PRF premiums are billed after the coverage period starts, which may already capture some of this effect (from my knowledge of PRF billing, unverified here).

**Verdict: worth adding.** One paragraph in the "demand barriers" section, plus a design implication: sell to the intermediary.

### B. Meso-level cover and risk-contingent credit (stronger than the existing notes)

**What it is.** The policyholder is the aggregator (bank, MFI, co-op, input lender), not the farmer. The payout either protects the loan book or is passed through as automatic loan relief. In risk-contingent credit (RCC), loan payments are offset when a drought index triggers.

**Evidence**
- The World Bank describes "meso" insurance as an aggregator such as a bank formally buying cover, paying premium and receiving payouts. — [Financial Protection Forum factsheet, 2021](https://www.financialprotectionforum.org/sites/default/files/Factsheet07_Draft03_Agriculture_30Nov2021.pdf)
- CLIMBS Weather Protect (Philippines) guarantees co-ops' loan portfolios with a rainfall or wind trigger, reinsured with Global Parametrics' help. — [ICMIF](https://www.icmif.org/weather-protection-insurance-for-farmers-in-the-philippines/); [Artemis](https://www.artemis.bm/news/new-parametric-extreme-weather-microinsurance-product-in-the-philippines/) (2010s; date unverified)
- Jamaica: a parametric hurricane cover protects the credit union league (JCCUL, about 100,000 smallholder borrowers) against non-repayment. — [Intelligent Insurer](https://www.intelligentinsurer.com/news/munich-re-howden-skyline-tie-up-to-develop-new-parametric-hurricane-cover-29176)
- Global Parametrics' Natural Disaster Fund supplies risk capacity for One Acre Fund's loan portfolio in Zambia and Malawi (2024). — [Reinsurance News](https://www.reinsurancene.ws/global-parametrics-and-one-acre-fund-deliver-parametric-solution-for-zambia-and-malawi-farmers/)
- Peru (about 2010-11, old): La Positiva's ENSO Business Interruption Index Insurance pays on sea-surface temperature, before the floods, and was sold to an MFI to protect its credit portfolio. It was described as the first regulated "forecast" insurance. Its current status is unknown. — [GlobalAgRisk/UNDP briefing](https://www.eird.org/plataforma-2011/docs/16demarzo/RRD-sector-privado-16-de-marzo/GlobalAgRisk_UNDP_ProjectBriefing.pdf)
- Kenya RCC RCTs (IFPRI), where satellite drought-index triggers offset loan payments:
  - Dec 2024 DP 2303 (about 1,053 smallholders): fertilizer adoption up to 14% higher at the extensive margin and over 100% at the intensive margin; no significant productivity effect. — [IDEAS/RePEc](https://ideas.repec.org/p/fpr/ifprid/2303.html)
  - Reported uptake effects conflict: 3ie reports 80% RCC versus 20% traditional loan uptake ([3ie brief, 2025](https://www.3ieimpact.org/sites/default/files/2025-07/TW13.1028-IE-brief.pdf)); the 2017 pilot reports 40% versus 30% ([IFPRI 2017](https://ifpri.org/wp-content/uploads/2019/07/fly_2017_rcc_v3_web.pdf)); a 2023 IFPRI paper reports "up to 4%" more uptake (via search summary). Quote the range, not one number.
  - Ghana (2010, old): loans that forgave 50% if crop prices fell had high uptake in all arms and little effect from the indemnity. — [FinDev Gateway](https://findevgateway.org/paper/2010/01/crop-price-indemnified-loans-farmers-pilot-experiment-rural-ghana)
- Pula sells only through partners (over 100: banks, governments, input firms). Embedded in national input-subsidy programs it reports 1M+ farmers in Zambia (FISP) and 700k in Ethiopia (Dec 2024). Kenya launched fertilizer-subsidy-linked insurance for about 250k farmers in 2025. These figures are company and government reported. — [AgFunder](https://agfundernews.com/pula-qa-how-is-breaking-through-crop-insurance-barriers-to-protect-africas-farmers); [Pula on insured loans](https://medium.com/pula-advisors/insurance-bundled-with-loans-maximising-smallholder-farmer-uptake-of-insured-loans-8a76885309e2); [HapaKenya, Jul 2025](https://hapakenya.com/2025/07/21/kenya-launches-initiative-to-insure-farmers-through-its-fertilizer-subsidy-program)
- Sovereign analogue: climate-resilient debt clauses pause debt service for 1-2 years after a defined disaster. AfDB, EBRD, IDB, UKEF and the World Bank have adopted them. One estimate puts the cost at 10-25 bp on commercial bonds. — [Climate Policy Initiative](https://www.climatepolicyinitiative.org/toolkit-instrument/climate-resilient-debt-clauses/)

**Why it matters here.**
- A US ag lender, Farm Credit association or hay co-op is likely an eligible contract participant (ECP). It can hold Kalshi positions sized to its book, which avoids retail onboarding.
- Pooling many borrowers' farms against a few stations averages out farm-level basis risk; the residual is regional. This links to netting_quant.md §5, which found that pooling across stations beats same-station netting.
- The companion's holdout HE (0.61) is a farm-level figure. A portfolio-level HE for a lender's book across the 11 sample farms would be easy to compute with the existing code and is likely higher (inference, untested).
- A "drought-flex" loan, where the next payment drops when the companion's index pays, needs no insurance license if the lender only changes its own loan terms (inference; lending-law review needed).

**Gaps.** No US lender doing this with exchange contracts was found. US lenders typically require federal crop insurance as collateral support instead (training knowledge, unverified).

**Verdict: worth adding.** It is a distribution model and a new HE metric (portfolio HE).

### C. Weather-contingent promotions, rebates and input guarantees (new)

**What it is.** A business promises customers a refund or rebate if a defined weather event happens, and backs the promise with contingency insurance. The weather trigger is part of the marketing contract, so the business's liability is the index itself.

**Evidence**
- Tokio Marine HCC sells weather promotion insurance for rain, snow and min/max temperature. Typical buyers are jewelry, furniture and electronics stores and auto dealers; the example is a full refund if it snows a set amount on Christmas Day. The page does not state the data source, pricing or limits. — [TMHCC (page opened)](https://www.tmhcc.com/en-us/products/contingency/weather-promotions)
- BUA's weather-promotion policy reimburses the retailer's customer refunds; minimum premium starts at $250. — [BUA via CompleteMarkets](https://completemarkets.com/company/bua/weather-insurance-for-promotions/)
- Premiums of about 1.5-5.5% of promoted sales were quoted by a provider around 2010. This is old, and the source attribution comes from a search summary, so treat it as unverified. — [CNN Money, Dec 2010](https://money.cnn.com/2010/12/30/smallbusiness/snow_jewelry_full_refunds/)
- Measurement disputes are the failure mode. A Coeur d'Alene jeweler's snow promotion (about $500k) was first denied when the insurer's weather vendor measured below the threshold, then approved after the vendor revised to above 3 inches (2020). — [KREM](https://www.krem.com/article/news/local/coeur-dalene-jewelers-500k-snowfall-promotion-payout-approved-by-insurance/293-320eecff-b282-4ebd-9cad-a233269c203c); [Spokesman-Review](https://www.spokesman.com/stories/2020/feb/10/cda-jewelry-shop-wins-snowfall-dispute-says-custom); [JCK](https://www.jckonline.com/editorial-article/insurer-nixes-payouts-for-jewelers-snow-promotion/)
- Ag-input versions (mostly old):
  - Monsanto's cotton drought relief refunded 100% of the technology fee when yield was under 150 lb lint/acre (TX, OK, KS, NM; 2006-07). — [Farm Progress, 2007](https://www.farmprogress.com/cotton/drought-relief-program-available-for-southwest-cotton-growers)
  - Syngenta ran a US Weather Protection Program for corn and soy, and Bayer runs FieldView-based outcome pricing; companies say these supplement federal crop insurance. — [DTN, May 2020](https://www.dtnpf.com/agriculture/web/ag/news/article/2020/05/01/safe-bet)
  - A seed company (West Gaines Seed) bought Arbol county-yield index cover on its own revenue, so the input firm is the hedger. — [Arbol case study](https://www.arbol.io/case-studies/west-gaines-seed-inc)

**Why it matters here.**
- **No basis risk by construction.** If the promotion says "measured at [Kalshi's settlement station]", the retailer's refund liability equals a Kalshi payoff. The team's exotic-payoff engine (doc 23 replicating NO/YES portfolios) can build a threshold payout from strike bins. This is the one segment where the team's main weakness, station-to-farm distance, disappears.
- **The opposite side of the companion.** Holiday snow and rain promotions run Nov-Feb, the same months the companion buys dry-side protection, at metro stations Kalshi lists. That gives wet-side demand in the companion's months. Netting is partial: netting_quant.md found about 26% variance reduction for same-station put/call pairs.
- **Legal path.** A retailer hedging its own promotion on Kalshi is ordinary event-contract use. If AgriHedge itself backed retailers' promotions, it would be writing contingency insurance and would need a carrier (inference). Whether some states treat weather-contingent refunds as a lottery or sweepstakes was not checked (gap).
- **Input firms as hedgers.** A feed or seed supplier offering a "drought rebate" to ranchers, hedged on Kalshi, is the US analogue of ACRE's seed-bundled cover. It is a price term, not an insurance promise, which may avoid insurance regulation (inference; needs counsel).

**Gaps.** I found no market-size data for weather promotions, and no current (2024-26) pricing.

**Verdict: worth adding.** It is a short, concrete use case and possibly the best demo of "Kalshi without basis risk".

### D. Embedded checkout guarantees (B2B2C): updates to hospitality_venues.md

**Evidence (new or stronger)**
- Sensible Weather says it has sold more than 1M Weather Guarantees across 8,000+ partners (Aug 2025, High Winds launch). That is much larger than the 50k (2023) and 300k Campspot figures in the notes. — [Business Wire, Aug 2025](https://www.businesswire.com/news/home/20250825060512/en); Inntopia/Alterra ski partnership, Feb 2025 — [Business Wire](https://www.businesswire.com/news/home/20250212575830/en/Sensible-Weather-Announces-Partnership-With-Inntopia-Offering-Weather-Guarantees-at-Select-Alterra-Mountain-Company-Mountain-Destinations)
- A new competitor is not in the notes: **WeatherPromise** raised a $12.8M Series A (Jan 2026, led by Maveron). It lists Marriott, Expedia, JetBlue, Invia and HomeToGo as partners, and JetBlue Vacations bundled a Jamaica guarantee into packages in Mar 2026. — [PR Newswire, Jan 2026](https://tools.prnewswire.com/en-us/live/20823/release/20260113EN61932)
- POS: I found **no** Toast, Square or Clover embedded weather product. A Toast blog claims $3,000-6,000 lost per snow day for some restaurants (vendor content, unverified). — [search summary of Toast "On the Line" blog](https://pos.toasttab.com/blog/on-the-line/restaurant-pos-security)

**Why it matters.** Embedded guarantees are an established business, but consumer-facing, hourly and at single sites, unlike the team's monthly station indices. The open POS slot is a possible pitch: POS sales data plus Kalshi daily-rain contracts give a measured revenue-versus-rain relationship to size a hedge. But no partner exists, and the existing notes already found monthly contracts a poor fit for venues.

**Verdict: minor.** Update the Sensible numbers and add WeatherPromise. Mention the POS gap only as a gap.

### E. Pricing and structuring as SaaS, and the Blanket precedent (new)

**Evidence**
- **Blanket** (live the week of 2026-08-07) is built by an independent founder, not Kalshi. A user describes a business risk, an AI "reasoning engine" suggests yes/no Kalshi markets in about 30 seconds, and it shows "near misses" when no market fits, which Kalshi can use as demand signals. No money moves through Blanket; execution and KYC happen on Kalshi. Kalshi says its compliance team was not involved. Targets include bars, laundromats and regional restaurants. — [Fortune, 2026-08-07 (page opened)](https://fortune.com/2026/08/07/exclusive-kalshi-blanket-small-business-hedge-hypergamblification/)
- CelsiusPro offers a white-label platform that insurers use to price and settle parametric products, and ParameterPro 2.0 (Nov 2024) for brokers. — [CelsiusPro](https://www.celsiuspro.com/white-label-platform); [Artemis](https://www.artemis.bm/news/celsiuspro-launches-parameterpro-2-0-to-streamline-parametric-insurance-structuring)
- Riskwolf is an API for pricing, quoting and claims monitoring, billed by usage with fixed and variable components (2023). — [YourStory, Mar 2023](https://yourstory.com/2023/03/insurtech-platform-riskwolf-innovative-solution-revolutionizes-insurance-market)
- Arbol's broker-only platform lets brokers pick weather conditions and triggers and get instant premium indications. — [Arbol platform](https://www.arbol.io/solutions/platform)
- Already in the notes: WeatherBill's value ended up in data and distribution, not the risk book (market_maker_model.md Q2).

**Why it matters here.**
- The team's `advisor.py` + `design.py` combination overlaps with Blanket. The team's real differentiators are what Blanket (as described) lacks: out-of-sample HE, the station-to-farm basis-risk report, executable-depth checks against the saved book, and utility-optimal shapes. The final report should name Blanket and state these differences.
- A no-risk SaaS model sold to insurers, MGAs or lenders (for example "PRF Companion as a white-label for crop-insurance agents") avoids capital and insurance licensing. It still faces one legal question (below).

**Gaps / legal.** Giving tailored advice on trading CFTC-regulated contracts for pay may trigger Commodity Trading Advisor registration. I did not verify how CTA rules apply to DCM event contracts, and Fortune did not address it. This needs a check before any paid advisory product.

**Verdict: worth adding** (Blanket as a competitor; SaaS as a model).

### F. Government partnership paths (new specifics)

**Evidence**
- Under Section 508(h), private parties may submit policies, provisions or rates to FCIC. An approved concept proposal can get 50% of expected R&D costs advanced. Full submissions get five external reviews plus an RMA review. — [RMA private-sector page (legacy)](https://legacy.rma.usda.gov/fcic/privatesector.html); [submission checklist](https://www.rma.usda.gov/sites/default/files/board-meetings/submissionchecklist.pdf)
- A 2016 final rule set separate provisions for index-based weather plans of insurance. Under it, states regulate sale and service, and the weather index serves as a proxy for production loss. — [Federal Register rule, 2016](https://www.rma.usda.gov/sites/default/files/2024-05/2016-18743.ashx_.pdf)
- The May 2025 FCIC minutes show 508(h) actions for Livestock Risk Protection and camelina; I found no weather-index approval in 2025-26. — [FCIC minutes, May 2025](https://www.rma.usda.gov/sites/default/files/2025-08/FCIC%20Minutes-May%202025%20signed.pdf)
- **ARC Replica:** humanitarian agencies (WFP, Start Network) buy policies that mirror a government's ARC drought policy, so both pay on the same trigger. In Zimbabwe, WFP received $6.09M, the government $16.8M and Start Network $8.9M. Senegal (2019) paid $10.6M to Start and $12.5M to the government. Somalia (2025) paid Start $727,855. — [Artemis](https://www.artemis.bm/news/arc-sells-first-replica-parametric-policies-to-wfp-start-network/); [Reinsurance News, Zimbabwe](https://www.reinsurancene.ws/arc-makes-us32m-climate-insurance-payouts-to-assist-people-impacted-by-drought-in-zimbabwe/); [Reinsurance News, Somalia](https://www.reinsurancene.ws/start-network-receives-727k-arc-replica-insurance-payout-for-drought-relief-in-somalia/)
- Colombia's government contracted five parametric policies (drought and excess rain, municipal water-balance index, up to $20.14M) ahead of 2026 El Niño. — [Artemis, 2026](https://www.artemis.bm/news/colombia-secures-parametric-insurance-for-smallholder-farmers-assisted-by-idf-undp-bmz/)

**Why it matters here.**
- 508(h) is the only route to federal subsidy. It turns the team's 1.8x cost disadvantage into a design contribution: "drought-weighted interval rules for PRF" or "a companion endorsement".
- ARC Replica is a template for a "replica" layer: a co-op, county or NGO buys the same trigger as the farmers' PRF to fund local response. Kalshi could host that layer for US stations.

**Verdict: 508(h) worth adding** as a long-horizon option. **ARC Replica: minor** (a pattern to mention).

### G. Member mutuals and risk pools

**Evidence**
- Mexico's *fondos de aseguramiento* are farmer-owned mutual funds that insure only their members, under a dedicated law, with government premium subsidy. — [Ley de Fondos](https://mexico.justia.com/federales/leyes/ley-de-fondos-de-aseguramiento-agropecuario-y-rural); [UNFCCC](https://unfccc.int/documents/637336)
- Fondos held 63.8% of insured hectares in 2012 and 61.9% in Q2 2018 (old). — [SAGARPA 2012](https://www.gob.mx/cms/uploads/attachment/file/99741/4to._TRIMESTRE_2012_SUBSIDIO_A_LA_PRIMA.pdf); [Informe 2T2018](https://www.gob.mx/cms/uploads/attachment/file/347217/INFORME_2T2018_PAA.pdf)
- Breustedt & Larson (2006) examine how fondo rules limit moral hazard. — [AGRIS](https://agris.fao.org/search/en/providers/122444/records/647365f053aa8c89630ca50f)
- Peer-to-peer insurance (Teambrella): I found no current status. NAIC lists it as an example (2023); its own site said the model doesn't fit lines that require a standard policy. — [NAIC](https://content.naic.org/cipr_topics/topic_peertopeer_p2p_insurance.htm)

**Why it matters.** Fondos show that member pools can hold most of a country's insured farm area, but only with a legal form, subsidy and reinsurance. A US grazing association could self-pool members' idiosyncratic losses and lay off the regional drought layer on Kalshi, so the pool handles basis risk and the exchange handles the systemic tail. That split is the reverse of the team's current problem (inference). A US version would need a captive, a risk retention group or state mutual licensing; I found no US weather example.

**Verdict: minor.** One sentence noting that the pool absorbs basis risk while Kalshi takes the systemic layer.

### H. ILS, cat bonds and on-chain parametric: what happened

**Evidence**
- **Etherisc / Lemonade Crypto Climate Coalition:** about 7,000 Kenyan farmers in the Oct 2022-Jan 2023 season, with payouts on area-yield and weather data delivered on-chain through Chainlink, then a second cohort of about 7,000 on $1 policies. I found no 2024-26 scale figures. — [InsuranceNewsNet](https://insurancenewsnet.com/oarticle/nearly-7000-kenyan-farmers-protected-by-the-lemonade-crypto-climate-coalition); [Chainlink Today](https://chainlinktoday.com/additional-7000-kenyan-farmers-protected-by-etheriscs-chainlink-powered-parametric-crop-insurance)
- **Arbol:** "dRe" (2023) is a blockchain loss-calculation and claims platform on RiskStream, not a capital pool. Arbol's capital comes through a BMA-registered Bermuda collateralized insurer (Arbol Re) and traditional capacity ("$250M non-traditional capacity, targets $1bn"). In practice Arbol moved from on-chain contracts to licensed insurance paper. — [Artemis, dRe](https://www.artemis.bm/news/arbol-automates-parametric-reinsurance-triggers-using-a-blockchain/); [Artemis, Arbol Re](https://www.artemis.bm/news/arbol-sets-up-bermuda-collateralized-insurer-to-tap-capital-market-capacity/); [Artemis, capacity](https://www.artemis.bm/news/arbol-lines-up-250m-non-traditional-capacity-targets-1bn-next-year/)
- **Re Protocol** channels stablecoin capital into fully collateralized reinsurance through licensed reinsurers; it authorized about $134M of capacity for 1/1/2026. — [Insurance Business](https://www.insurancebusinessmag.com/reinsurance/news/breaking-news/blockchain-reinsurance-platform-re-boosts-capacity-for-2026-renewals-558209.aspx)
- **ILS:** Nephila's AuM is $7.9B (Jun 2026), down from about $11B when it launched Nephila Climate (2018). WFP is developing a $100M drought cat bond with the World Bank, which would be the first cat bond to cover drought directly; it was not yet issued as of the source. — [Artemis Nephila](https://www.artemis.bm/ils_fund_managers/nephila-capital/); [Artemis 2018](https://www.artemis.bm/news/2018/01/30/nephila-climate-launches-to-expand-ils-managers-role-in-weather-risks/); [Artemis WFP](https://www.artemis.bm/news/wfp-progresses-food-security-catastrophe-bond-plan-to-mobilise-100m-for-drought-resilience/)
- Nexus Mutual: I found no weather product (gap; not searched in depth).

**Why it matters.** On-chain parametric stayed small, and its survivors moved to regulated paper. Kalshi already supplies what the oracle was for: trusted settlement, now verified by The Weather Company (market_maker_model.md). Cat bonds and ILS funds are $100M-scale, sovereign or reinsurer deals, far beyond this team's scale. They matter only as the eventual backstop for an MGA, which the notes already cover.

**Verdict: not useful**, beyond one line: "on-chain added nothing Kalshi lacks; survivors moved to licensed paper".

---

## Comparison with the six existing notes

| Topic | Existing coverage | This review |
|---|---|---|
| Upfront-cash barrier | Named as a barrier (uninsured_farmers Q4) | **New:** Casaburi-Willis RCT, timing beats price (A) |
| Bundling with credit or inputs | One-line inference (uninsured_farmers Q5) | **Stronger:** meso cover examples, RCC RCTs with conflicting uptake, portfolio-HE idea (B) |
| Weather promotions and rebates | Not covered | **New:** zero-basis-risk use case on the opposite side of the companion (C) |
| Embedded guarantees | Sensible covered (hospitality) | **Update:** 1M+ guarantees and 8,000 partners; WeatherPromise; no POS product (D) |
| SaaS and Blanket | Not in these notes (Blanket is cited in docs/research/02) | **New:** competitor to `advisor.py`; CTA legal gap (E) |
| Government paths | Insurable-interest safe harbor, IB/FCM, MGA routes | **New:** 508(h)/index-weather rule, ARC Replica (F) |
| Mutuals | Not covered | Minor: fondos (G) |
| DeFi and ILS | Etherisc/ACRE briefly; ILS as backstop | Mostly confirms; adds Arbol's move to licensed paper (H) |

**Contradictions with the existing notes:** none directly. One tension: uninsured_farmers.md Q5 treats low take-up as mostly a price problem ("disappointingly low without large subsidies"). Casaburi-Willis shows that payment timing alone moves take-up from 5% to 72% with no subsidy. Both can be true, but the report shouldn't present subsidy as the only lever.

## Open gaps worth a follow-up
- CTA registration exposure for a paid Kalshi trade-recommendation tool.
- Whether weather-contingent consumer refunds face state lottery or sweepstakes rules.
- Any US ag lender or co-op hedging a loan book with exchange weather contracts (none found).
- A portfolio-level HE for the 11 sample farms treated as one lender's book (computable with existing `optimizer.py`; not run here).
