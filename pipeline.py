#!/usr/bin/env python3
"""Compare simplified cart JSON with bundled illustrative rates."""

import argparse
from pathlib import Path
import sys

import medusa_client
import tax_provider
from oa_client import OAClient
from reporting import configure_output, safe_text

STATUS = {"ok": "✅", "warn": "⚠️", "incomplete": "⚠️"}


def run(source: str, oa: OAClient) -> bool:
    carts = medusa_client.extract(source)
    plan = oa.start("Compare illustrative US sales-tax rates", "US")
    if not isinstance(plan, dict):
        raise ValueError("start must return an object")
    skills = plan.get("skills_to_load", [])
    if not isinstance(skills, list) or any(not isinstance(slug, str) for slug in skills):
        raise ValueError("skills_to_load must be an array of names")
    slug = skills[0] if skills else None
    skill = oa.get_skill(slug) if slug else {}
    complete = True
    for index, cart in enumerate(carts, 1):
        try:
            c = medusa_client.normalize(cart)
            v = tax_provider.check(c, skill)
        except ValueError as error:
            print(f"\nCart {index}: invalid input: {safe_text(error)}")
            complete = False
            continue
        print(f"\n🛒  cart {safe_text(c['id'])} → {safe_text(c['city'] or 'unknown city')}, {safe_text(c['state'] or 'unknown state')}")
        trust = ("unverified sample rules" if v["provenance"] == "sample"
                 else "provider metadata; not independently verified")
        print(f"    OpenAccountants → {safe_text(v.get('oa_skill_name') or 'sales-tax rates')} ({trust})")
        for label, rate_key, tax_key in (("Medusa flat", "medusa_rate", "medusa_tax"),
                                         ("Illustrative", "oa_rate", "oa_tax")):
            rate_text = "unknown" if v[rate_key] is None else f"{v[rate_key]:.4%}"
            tax_text = "unknown" if v[tax_key] is None else f"USD {v[tax_key]:,.2f}"
            print(f"    {label}: {rate_text} ({tax_text})")
        print(f"    {STATUS[v['status']]} {safe_text(v['headline'])}")
        print(f"       {safe_text(v['detail'])}")
        complete = complete and v["complete"]
    return complete


def main(argv: list[str]) -> int:
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=str(Path(__file__).parent / "samples/carts.json"))
    parser.add_argument("--live", action="store_true", help="use the unverified live adapter")
    args = parser.parse_args(argv[1:])
    oa = OAClient() if args.live else OAClient(token=None)
    if args.live and not oa.live:
        parser.error("--live requires OA_MCP_TOKEN")
    mode = "LIVE ADAPTER (unverified)" if oa.live else "BUNDLED ILLUSTRATIVE RULES"
    print(f"Medusa → OpenAccountants · rate-comparison demo [{mode}]")
    try:
        complete = run(args.source, oa)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Comparison failed: {safe_text(error)}", file=sys.stderr)
        return 2
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
