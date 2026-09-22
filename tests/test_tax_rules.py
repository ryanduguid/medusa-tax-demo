from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing oa_client only reads environment variables; it makes no requests.
from oa_client import _MOCK_SKILL


def bundled_skill():
    return next(iter(_MOCK_SKILL.values()))

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
        carts=json.loads(Path(ROOT, "samples/carts.json").read_text(encoding="utf-8"))
        cart=next(c for c in carts if c["shipping_address"]["city"] == "Los Angeles")
        result=tax_provider.check(medusa_client.normalize(cart), bundled_skill())
        self.assertEqual(result["oa_tax"], 48.75)
