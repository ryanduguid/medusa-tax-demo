"""Medusa cart extraction.

Medusa is open-source headless commerce. Its docs note the built-in tax calc
"will not work for the US or other countries with varying rates within the same
region" — and it exposes a clean tax-provider seam. This reads carts (the shape a
tax provider receives) and normalizes each to the facts the rate lookup needs,
including the flat region rate Medusa would otherwise apply (for contrast).
"""

from __future__ import annotations

import json


def extract(source: str) -> list[dict]:
    with open(source) as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def normalize(cart: dict) -> dict:
    addr = cart.get("shipping_address") or {}
    items = cart.get("items") or []
    subtotal = sum(float(i.get("unit_price", 0)) * int(i.get("quantity", 1)) for i in items)
    return {
        "id": cart.get("id", ""),
        "state": (addr.get("province") or "").upper(),
        "city": addr.get("city", ""),
        "subtotal": subtotal,
        "currency": (cart.get("currency_code") or "usd").upper(),
        "medusa_region_rate": float(cart.get("medusa_region_rate", 0)),
    }
