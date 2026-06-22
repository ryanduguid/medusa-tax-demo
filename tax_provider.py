"""Compute the correct destination sales tax for a Medusa cart, and contrast it
with the flat region rate Medusa would otherwise apply.

The gap Medusa documents: a single region can't carry the right rate for every US
destination (state + county + city vary), and it doesn't know nexus. OpenAccountants
returns the destination-correct rate — including 0% in no-sales-tax states and 0%
where the seller has no nexus.

DELIBERATE SCOPE: rate lookup + nexus signal, not product taxability, exemptions,
or marketplace-facilitator rules. Production leans on the full OA skill + an agent
step; the named-CPA sign-off makes it relianceable.
"""

from __future__ import annotations


def rate_for(cart: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    combined = rules.get("combined_rates", {})
    state_base = rules.get("state_base", {})
    no_tax = rules.get("no_tax_states", [])
    nexus = rules.get("nexus_states", [])
    state, city = cart["state"], cart["city"]

    if state in no_tax:
        oa_rate, why = 0.0, f"{state} has no state sales tax"
    elif nexus and state not in nexus:
        oa_rate, why = 0.0, f"no nexus in {state} — no obligation to collect"
    else:
        oa_rate = combined.get(f"{state}/{city}", state_base.get(state, 0.0))
        why = f"{state}/{city} combined rate" if f"{state}/{city}" in combined else f"{state} state rate"
    return {"oa_rate": oa_rate, "why": why}


def check(cart: dict, oa_skill: dict) -> dict:
    base = {"oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
            "tier": oa_skill.get("tier"), "verifier": oa_skill.get("verifier")}
    r = rate_for(cart, oa_skill)
    oa_rate = r["oa_rate"]
    medusa = cart["medusa_region_rate"]
    sub = cart["subtotal"]
    oa_tax = round(oa_rate * sub, 2)
    medusa_tax = round(medusa * sub, 2)
    delta = round(oa_tax - medusa_tax, 2)
    cur = cart["currency"]

    common = {**base, "oa_rate": oa_rate, "medusa_rate": medusa, "oa_tax": oa_tax,
              "medusa_tax": medusa_tax, "why": r["why"]}

    if abs(oa_rate - medusa) < 0.0005:
        return {**common, "status": "ok",
                "headline": f"Correct — {oa_rate:.2%} ({r['why']})",
                "detail": f"Medusa and OpenAccountants agree: {cur} {oa_tax:,.2f} on {cur} {sub:,.0f}."}
    if oa_rate > medusa:
        return {**common, "status": "warn",
                "headline": f"Under-charging — Medusa {medusa:.2%}, correct {oa_rate:.2%}",
                "detail": f"{r['why']}. Medusa's flat region rate misses local tax — {cur} {delta:,.2f} short (your liability to remit)."}
    return {**common, "status": "warn",
            "headline": f"Over-charging — Medusa {medusa:.2%}, correct {oa_rate:.2%}",
            "detail": f"{r['why']}. Medusa's flat region rate over-collects — {cur} {-delta:,.2f} the customer shouldn't be charged."}
