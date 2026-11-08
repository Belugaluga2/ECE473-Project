"use strict";
(() => {
  const data = window.MAYA_DATA;
  const $ = id => document.getElementById(id);
  const money = x => new Intl.NumberFormat("en-US", {style:"currency", currency:"USD", maximumFractionDigits:0}).format(x);
  const percent = x => `${(100*x).toFixed(2)}%`;
  const labels = {local_continuous:"Local continuous primitives (invented)",local_ladders:"Local binary ladders (invented)",chicago_rain:"Chicago summer rain structure (unlisted)",chicago_rain_hypothetical_heat:"Chicago rain + invented summer heat"};
  function value() {
    const result = Number($("value").value);
    const valid = Number.isFinite(result) && result > 0 && result <= 1e9;
    $("inputError").textContent = valid ? "" : "Enter a positive illustrative value up to $1 billion.";
    return valid ? result : null;
  }
  function selectedCase() { return data.cases.find(x => x.fips === $("county").value && x.year === Number($("year").value)); }
  function populateYears() {
    const current = $("year").value;
    $("year").replaceChildren(...data.cases.filter(x => x.fips === $("county").value).sort((a,b)=>a.year-b.year).map(x => new Option(String(x.year),String(x.year))));
    if ([...$("year").options].some(x => x.value === current)) $("year").value = current;
  }
  function contextText(row) {
    const clues = [];
    if (row.wet_summer_clue) clues.push("June–July rainfall exceeded its earlier 90th percentile; excess summer rain is outside this drought-only rain trigger");
    if (row.august_dry_clue) clues.push("August rainfall was below its earlier 10th percentile, outside the policy window");
    if (row.august_hot_clue) clues.push("August heat exceeded its earlier 90th percentile, outside the policy window");
    return clues.length ? "Context clues: "+clues.join("; ")+". These do not establish causation." : "These weather flags do not establish why the crop shortfall occurred.";
  }
  function receipt() {
    const row = selectedCase(), spec = data.specs[row.fips], e = value();
    if (e === null) return null;
    const cents = Math.round(e*100), collateral = Math.ceil(cents*spec.maximum_payout_fraction);
    return {status:"browser illustration; no money transferred or source truth verified",county:row.county,fips:row.fips,year:row.year,
      spec_sha256:spec.spec_sha256,expected_value_cents:cents,payout_cents:Math.min(collateral,Math.round(cents*row.payout_fraction)),
      modeled_premium_cents:Math.round(cents*row.premium_fraction),required_mock_collateral_cents:collateral,
      note:"Use the Python CLI to validate daily observations and produce a weather-input hash."};
  }
  function historical() {
    const row = selectedCase(), e = value();
    if (!row || e === null) return;
    const spec = data.specs[row.fips];
    $("lossMoney").textContent = money(e*row.loss_fraction);
    $("payoutMoney").textContent = money(e*row.payout_fraction);
    $("premiumMoney").textContent = money(e*row.premium_fraction);
    $("caseNumbers").textContent = `${row.county}, ${row.year}: drought D = ${row.drought.toFixed(3)}, heat H = ${row.heat.toFixed(3)}. Shortfall ${percent(row.loss_fraction)}; payment ${percent(row.payout_fraction)} of expected crop value.`;
    $("reason").textContent = `${row.mechanical_reason}. ${contextText(row)}`;
    $("baselineRange").textContent = `Across four fixed earlier-only production forecasts, estimated shortfall ranges from ${percent(row.baseline_low)} to ${percent(row.baseline_high)}. No forecast was selected to improve the hedge score.`;
    $("weight").textContent = spec.coefficient.toFixed(6);
    $("countyFormula").textContent = `D = clip((${spec.rain_trigger_in.toFixed(4)} inches − June–July rain) / ${spec.rain_scale_in.toFixed(4)} inches, 0, 1). H = clip((June–July heat exposure − ${spec.heat_trigger_c_days.toFixed(4)} C-days) / ${spec.heat_scale_c_days.toFixed(4)} C-days, 0, 1). Climate parameters are frozen through ${spec.fit_end}.`;
    $("capText").textContent = `Maximum payment: ${percent(spec.maximum_payout_fraction)} of expected crop value, or ${money(e*spec.maximum_payout_fraction)} here. The modeled premium is ${percent(spec.modeled_premium_fraction)}. Mock collateral must cover the maximum; none is actually held.`;
    $("replicaRows").replaceChildren(...data.replicaPredictions.filter(x=>x.fips===row.fips && x.year===row.year).map(x=>{
      const summary = data.replicaSummary.find(y=>y.fips===row.fips && y.basis===x.basis), tr=document.createElement("tr");
      [labels[x.basis],money(e*x.replica_fraction),money(e*x.modeled_premium_fraction),summary.payoff_replication_he.toFixed(3)].forEach((text,i)=>{const td=document.createElement("td");td.textContent=text;if(i)td.className="num";tr.append(td);});return tr;
    }));
    $("boundText").textContent = `For the declared full severity domain, any separate additive approximation must miss at least one endpoint by at least ${percent(data.bound.additive_global_worst_case_error_lower_bound_fraction)} of expected crop value (${money(e*data.bound.additive_global_worst_case_error_lower_bound_fraction)} here).`;
  }
  function whatIf() {
    const e=value();if(e===null)return;
    const d=Number($("d").value),h=Number($("h").value),a=data.coefficientAudit.saved_coefficient,p=a*Math.min(d,h);
    $("dOut").textContent=d.toFixed(2);$("hOut").textContent=h.toFixed(2);
    $("whatMoney").textContent=money(e*p);$("whatText").textContent=`${percent(p)} of expected crop value. The smaller severity controls the payment; either input at zero makes payment zero.`;
    const canvas=$("surface"),ctx=canvas.getContext("2d"),margin=27,size=230,n=25;
    ctx.clearRect(0,0,280,280);ctx.font="12px system-ui";
    for(let i=0;i<n;i++)for(let j=0;j<n;j++){const z=Math.min(i/(n-1),j/(n-1));ctx.fillStyle=`rgb(${Math.round(239-202*z)},${Math.round(247-139*z)},${Math.round(242-163*z)})`;ctx.fillRect(margin+i*size/n,margin+(n-1-j)*size/n,size/n+1,size/n+1);}
    ctx.fillStyle="#405d53";ctx.fillText("0",margin-3,margin+size+17);ctx.fillText("D → 1",margin+size-35,margin+size+17);ctx.fillText("H",5,margin+6);ctx.fillText("1",12,margin+6);
    ctx.beginPath();ctx.arc(margin+d*size,margin+(1-h)*size,5,0,Math.PI*2);ctx.fillStyle="#b66d1d";ctx.fill();ctx.strokeStyle="white";ctx.lineWidth=2;ctx.stroke();
  }
  function render() { historical();whatIf(); }
  for(const [fips,spec] of Object.entries(data.specs)) $("county").add(new Option(`${spec.county}, ${spec.state}`,fips));
  populateYears();$("year").value="2012";
  $("county").addEventListener("change",()=>{populateYears();render();});$("year").addEventListener("change",historical);$("value").addEventListener("input",render);
  $("d").addEventListener("input",whatIf);$("h").addEventListener("input",whatIf);
  function explore(row){$("county").value=row.fips;populateYears();$("year").value=String(row.year);render();$("history").scrollIntoView({behavior:"smooth"});}
  $("showMiss").addEventListener("click",()=>explore(data.topMisses.find(x=>x.year!==2012)));
  $("missRows").replaceChildren(...data.topMisses.map(row=>{const tr=document.createElement("tr");[`${row.county} ${row.year}`,percent(row.loss_fraction),percent(row.payout_fraction),row.mechanical_reason].forEach((text,i)=>{const td=document.createElement("td");td.textContent=text;if(i===1||i===2)td.className="num";tr.append(td);});const cell=document.createElement("td"),button=document.createElement("button");button.textContent="Explore";button.className="secondary";button.setAttribute("aria-label",`Explore ${row.county} ${row.year}`);button.addEventListener("click",()=>explore(row));cell.append(button);tr.append(cell);return tr;}));
  const a=data.coefficientAudit;
  $("budgetEquation").textContent=`a = 0.01 / (1.10 × ${a.mean_training_min_D_H.toFixed(8)}) = ${a.saved_coefficient.toFixed(8)}`;
  $("trainingText").textContent=`1% is the chosen modeled premium. 1.10 includes a 10% loading. The mean min(D,H) comes from ${a.training_rows} development county-years, ${a.training_years[0]}–${a.training_years.at(-1)}. This is pooled pricing, not a verified county-specific quote.`;
  const evidence=data.summary.find(x=>x.family==="weakest_link" && x.sensitivity==="all");
  $("evidenceText").textContent=`On ${evidence.years} common later years and ${evidence.counties} reserved counties, the selected policy's HE was ${evidence.he_gross.toFixed(3)} and premium-inclusive squared-error reduction was ${evidence.net_error_skill.toFixed(3)}. Its conditional interval includes no improvement. Neither score means profit or the share of losses reimbursed.`;
  const time=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",dateStyle:"medium",timeStyle:"short"}).format(new Date(data.market.checked_utc));
  $("marketText").textContent=`Public snapshot: ${time} Eastern. Open events: ${Object.values(data.market.events).flat().join(", ")}. November prices cannot price an unlisted pre-season summer portfolio. Current Chicago rain and heat also use different stations and settlement sources from our gridded county rule.`;
  $("downloadReceipt").addEventListener("click",()=>{const r=receipt();if(!r)return;const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:"application/json"})),link=document.createElement("a");link.href=url;link.download=`maya-illustrative-receipt-${r.fips}-${r.year}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  render();
  // Browser-only smoke checks, deliberately activated by a test URL, not normal use.
  if(new URLSearchParams(location.search).has("selftest")){
    try{const assert=(x,m)=>{if(!x)throw new Error(m);};assert($("county").options.length===3,"county count");assert($("year").options.length===11,"common year count");assert($("missRows").children.length===9,"miss count");
      $("d").value="0";$("h").value="1";whatIf();assert($("whatMoney").textContent===money(0),"AND zero payment");
      $("d").value="1";$("h").value="1";whatIf();assert($("whatMoney").textContent===money(100000*a.saved_coefficient),"cap payment");
      $("county").value="19169";populateYears();$("year").value="2013";historical();assert($("reason").textContent.includes("smaller severity is weak"),"selected case explanation");assert($("replicaRows").children.length===4,"replica rows");
      $("value").value="200000";render();assert(receipt().expected_value_cents===20000000,"notional update");assert(receipt().payout_cents<=receipt().required_mock_collateral_cents,"collateral cap");
      $("value").value="-1";render();assert($("inputError").textContent.length>0,"invalid value guard");
      $("value").value="100000";$("d").value="0.6";$("h").value="0.3";render();
      document.body.dataset.viewport=String(innerWidth);document.body.dataset.layout=String(document.documentElement.scrollWidth);
      assert(document.documentElement.scrollWidth<=innerWidth+2,`page overflows: ${document.documentElement.scrollWidth} > ${innerWidth}`);
      document.body.dataset.selftest="passed";$("testResult").textContent="All browser smoke checks passed";
    }catch(error){document.body.dataset.selftest="failed";$("testResult").textContent=error.stack;}
  }
})();
