import ast
from pathlib import Path
import unittest


def bundled_skill():
    # Read only the literal fixture; do not initialise authenticated clients.
    tree = ast.parse(Path("oa_client.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_MOCK_SKILL" for t in node.targets):
            return next(iter(ast.literal_eval(node.value).values()))
    raise AssertionError("Missing bundled rule fixture")

import tax_provider


class LosAngelesRateTests(unittest.TestCase):
    def test_city_rate_and_tax(self):
        result = tax_provider.check({"state": "CA", "city": "Los Angeles", "subtotal": 1000,
            "medusa_region_rate": 0.0725, "currency": "USD"}, bundled_skill())
        self.assertEqual(result["oa_rate"], 0.0975)
        self.assertEqual(result["oa_tax"], 97.50)
        self.assertEqual(result["medusa_tax"], 72.50)

    def test_sample_city_and_amount(self):
        import json
        import medusa_client
        carts=json.loads(Path("samples/carts.json").read_text(encoding="utf-8"))
        cart=next(c for c in carts if c["shipping_address"]["city"] == "Los Angeles")
        result=tax_provider.check(medusa_client.normalize(cart), bundled_skill())
        self.assertEqual(result["oa_tax"], 48.75)
