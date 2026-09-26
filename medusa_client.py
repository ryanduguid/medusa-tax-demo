"""Read simplified cart JSON with USD unit prices and fractional region rates."""

import json
from decimal import Decimal, localcontext

from values import number, rate


def extract(source: str) -> list[dict]:
    with open(source, encoding="utf-8") as fh:
        data = json.load(fh, parse_float=Decimal)
    return data if isinstance(data, list) else [data]


def normalize(cart: dict) -> dict:
    if not isinstance(cart, dict):
        raise ValueError("each cart must be an object")
    addr = cart.get("shipping_address")
    if addr is None:
        addr = {}
    if not isinstance(addr, dict):
        raise ValueError("shipping_address must be an object")
    items = cart.get("items")
    subtotal = None
    if items is not None:
        if not isinstance(items, list):
            raise ValueError("items must be an array")
        with localcontext() as context:
            context.prec = 50
            total, missing = Decimal(0), False
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("each item must be an object")
                price = number(item.get("unit_price"), "unit_price")
                quantity = number(item.get("quantity"), "quantity")
                if quantity is not None and quantity != quantity.to_integral_value():
                    raise ValueError("quantity must be a whole number")
                if price is None or quantity is None:
                    missing = True
                else:
                    total += price * quantity.to_integral_value()
            if not missing:
                subtotal = number(total, "subtotal")
    state, city, currency = addr.get("province"), addr.get("city"), cart.get("currency_code")
    for field, value in (("province", state), ("city", city), ("currency_code", currency)):
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be text")
    return {
        "id": cart.get("id", ""), "state": state.upper() if state else None,
        "city": city, "subtotal": subtotal, "currency": currency.upper() if currency else None,
        "medusa_region_rate": rate(cart.get("medusa_region_rate"), "medusa_region_rate"),
    }
