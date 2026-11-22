"""Accounting and paired uncertainty for PRF-kept add-on diagnostics."""
from __future__ import annotations
import numpy as np
from agri_hedge.paper_evidence import paired_year_blocks


def keep_prf(prf, mixed_payout, mixed_premium, original_premium, retained_prf_share=0.8):
    """Recover the frozen market component and restore the original PRF policy.

    The earlier mixture spent 80% on PRF and at most 20% on market cover. Restore
    its missing 20% PRF without changing a single contract or coefficient.
    """
    cost = float(mixed_premium-retained_prf_share*original_premium)
    extra = (1-retained_prf_share)*original_premium
    if cost < -1e-6 or cost > extra+1e-6:
        raise ValueError('Component cost exceeds the frozen additional budget')
    component = np.asarray(mixed_payout,float)-retained_prf_share*np.asarray(prf,float)
    return dict(component=component, component_cost=max(0.0,cost),
                total_payout=np.asarray(prf,float)+component,
                total_premium=original_premium+max(0.0,cost),
                total_budget=original_premium+extra, cash_retained=extra-max(0.0,cost))


def addon_statistics(loss, prf, component, original_premium, component_cost, draws=2000, seed=473):
    """Compare fixed PRF + market cover with fixed PRF + retained extra cash.

    The same extra resources are available in both arms. Interest foregone is
    already included in the inherited market-cost convention and is not added
    to the cash benchmark a second time.
    """
    y,p,h=map(lambda a:np.asarray(a,float),(loss,prf,component))
    base_residual=y-p
    addon_residual=y-p-h
    baseline_net=y+original_premium-p
    addon_net=y+original_premium+component_cost-p-h
    base_short=np.maximum(baseline_net,0)
    new_short=np.maximum(addon_net,0)
    top=np.argsort(y)[-min(5,len(y)):]
    v=float(np.var(base_residual))
    gain=h-component_cost
    out=dict(n_years=len(y),component_cost=float(component_cost),mean_addon_payout=float(h.mean()),
             mean_net_gain_vs_cash=float(gain.mean()),
             residual_variance_reduction=1-float(np.var(addon_residual))/v if v>1e-12 else np.nan,
             baseline_worst5_shortfall=float(base_short[top].mean()),
             addon_worst5_shortfall=float(new_short[top].mean()),
             worst5_shortfall_reduction=float((base_short[top]-new_short[top]).mean()))
    if draws:
        ix=paired_year_blocks(len(y),draws=draws,seed=seed)
        vb=np.var(base_residual[ix],axis=1)
        va=np.var(addon_residual[ix],axis=1)
        reduction=np.divide(va,vb,out=np.full_like(va,np.nan),where=vb>1e-12)
        reduction=1-reduction
        out['variance_ci_low'],out['variance_ci_high']=np.nanquantile(reduction,[.025,.975])
        out['net_gain_ci_low'],out['net_gain_ci_high']=np.quantile(gain[ix].mean(axis=1),[.025,.975])
        rank=np.argsort(y[ix],axis=1)[:,-min(5,len(y)):]
        picked=np.take_along_axis(ix,rank,axis=1)
        tail=(base_short[picked]-new_short[picked]).mean(axis=1)
        out['shortfall_ci_low'],out['shortfall_ci_high']=np.quantile(tail,[.025,.975])
    if len(y)>5:
        keep=np.arange(len(y))!=int(np.argmax(y))
        top=np.flatnonzero(keep)[np.argsort(y[keep])[-5:]]
        out['shortfall_reduction_without_worst_year']=float((base_short[top]-new_short[top]).mean())
    return out


def required_depth_multiplier(desired, capacity):
    """Worst-leg scaling at fixed prices; absent useful offers cannot be scaled."""
    n,c=np.asarray(desired,float),np.asarray(capacity,float)
    used=n>0
    if not used.any():return 1.0,0
    missing=int(np.sum(used & (c<=0)))
    return (np.inf if missing else max(1.0,float(np.max(n[used]/c[used])))),missing
