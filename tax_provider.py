"""Compare a supplied region rate with an explicitly covered illustrative rate.

The comparison assumes the entire subtotal is taxable. It does not determine
product taxability, nexus, exemptions, collection duties or a complete tax bill.
"""

from decimal import Decimal, ROUND_HALF_UP, localcontext

from values import number, rate


def rate_for(cart: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    if (not isinstance(rules, dict) or rules.get("schema") != "illustrative-rates-v1"
            or rules.get("rate_unit") != "fraction"):
        return {"oa_rate": None, "why": "unsupported rule schema or rate units"}
    allowed = {"schema", "rate_unit", "snapshot", "combined_rates", "state_base",
               "nexus_states", "no_tax_states", "sources", "description"}
    if rules.keys() - allowed:
        return {"oa_rate": None, "why": "unsupported rule fields"}
    combined = rules.get("combined_rates", {})
    if not isinstance(combined, dict):
        raise ValueError("combined_rates must map destinations to fractional rates")
    state, city = cart.get("state"), cart.get("city")
    key = f"{state}/{city}"
    if state and city and key in combined:
        result = rate(combined[key], f"rate for {key}")
        if result is not None:
            return {"oa_rate": result, "why": f"{key} illustrative destination rate"}
    return {"oa_rate": None, "why": "destination rate is not covered by the loaded sample"}


def check(cart: dict, oa_skill: dict) -> dict:
    r = rate_for(cart, oa_skill)
    sample_rate = r["oa_rate"]
    region_rate = rate(cart.get("medusa_region_rate"), "medusa_region_rate")
    subtotal = number(cart.get("subtotal"), "subtotal")
    currency = cart.get("currency")
    base = {
        "oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
        "provenance": oa_skill.get("provenance", "unverified"),
        "reported_metadata": {key: oa_skill.get(key) for key in ("tier", "verifier", "source")},
        "oa_rate": sample_rate, "medusa_rate": region_rate, "why": r["why"],
        "oa_tax": None, "medusa_tax": None, "delta": None, "complete": False,
    }
    with localcontext() as context:
        context.prec = 50
        if currency == "USD" and subtotal is not None:
            for key, value in (("oa_tax", sample_rate), ("medusa_tax", region_rate)):
                if value is not None:
                    base[key] = (subtotal * value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if base["oa_tax"] is not None and base["medusa_tax"] is not None:
            base["delta"] = base["oa_tax"] - base["medusa_tax"]
    missing = []
    if sample_rate is None:
        missing.append(r["why"])
    if region_rate is None:
        missing.append("region rate is missing")
    if subtotal is None:
        missing.append("subtotal is missing")
    if currency != "USD":
        missing.append("only explicit USD inputs are supported")
    if missing:
        return {**base, "status": "incomplete", "headline": "Comparison incomplete",
                "detail": "; ".join(missing) + ". No collection obligation is determined."}
    delta = base["delta"]
    relation = "matches" if sample_rate == region_rate else (
        "is lower than" if region_rate < sample_rate else "is higher than")
    detail = f"Illustrative tax difference: USD {delta:,.2f}. Assumes the entire subtotal is taxable."
    if sample_rate != region_rate and delta == 0:
        detail += " The rates differ but give the same rounded amount."
    return {**base, "complete": True, "delta": delta,
            "status": "ok" if sample_rate == region_rate else "warn",
            "headline": f"Region rate {relation} the illustrative rate ({sample_rate:.2%})",
            "detail": detail}
