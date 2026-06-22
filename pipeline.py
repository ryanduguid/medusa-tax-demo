#!/usr/bin/env python3
"""Medusa -> OpenAccountants tax-provider pipeline.

    python pipeline.py                  # bundled sample carts (mock mode)
    python pipeline.py samples/carts.json

The flow:
    Medusa carts -> OA MCP (start -> get_skill) -> destination rate -> verdict

This is OpenAccountants acting as a Medusa tax provider: it returns the
destination-correct rate where Medusa's flat region rate can't. Set OA_MCP_TOKEN
to use the live verified rates.
"""

from __future__ import annotations

import os
import sys

import medusa_client
import tax_provider
from oa_client import OAClient

STATUS = {"ok": "✅", "warn": "⚠️ "}


def run(source: str, oa: OAClient) -> None:
    carts = medusa_client.extract(source)
    plan = oa.start("Rate a cart for US sales tax", "US")
    slug = (plan.get("skills_to_load") or [None])[0]
    skill = oa.get_skill(slug) if slug else {}

    for cart in carts:
        c = medusa_client.normalize(cart)
        print(f"\n🛒  cart {c['id']} → {c['city']}, {c['state']} · {c['currency']} {c['subtotal']:,.0f}")
        v = tax_provider.check(c, skill)
        trust = f"tier {v.get('tier')}" + (f", signed off by {v['verifier']}" if v.get("verifier") else "")
        print(f"    OpenAccountants → {v.get('oa_skill_name') or 'sales-tax rates'}  ({trust})")
        print(f"    Medusa flat: {v['medusa_rate']:.2%} ({c['currency']} {v['medusa_tax']:,.2f})   ·   "
              f"OpenAccountants: {v['oa_rate']:.2%} ({c['currency']} {v['oa_tax']:,.2f})")
        print(f"    {STATUS.get(v['status'], '')} {v['headline']}")
        print(f"       {v['detail']}")


def main(argv: list[str]) -> int:
    oa = OAClient()
    mode = "LIVE" if oa.live else "MOCK (set OA_MCP_TOKEN to use the live verified rates)"
    print(f"Medusa → OpenAccountants · tax-provider demo  [{mode}]")
    here = os.path.dirname(os.path.abspath(__file__))
    source = argv[1] if len(argv) > 1 else os.path.join(here, "samples", "carts.json")
    run(source, oa)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
