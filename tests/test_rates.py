import copy
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from unittest.mock import patch

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"

import medusa_client
import pipeline
import tax_provider
from oa_client import OAClient


class RateTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.socket = patch("socket.create_connection", side_effect=AssertionError("Network forbidden"))
        self.socket.start()
        self.addCleanup(self.socket.stop)
        self.skill = copy.deepcopy(OAClient(token=None).get_skill("us-sales-tax-rates"))
        self.cart = {"id": "test", "state": "IL", "city": "Chicago",
                     "subtotal": Decimal("200"), "currency": "USD",
                     "medusa_region_rate": Decimal("0.0625")}

    def test_unknown_destination_is_incomplete(self):
        for state, city in (("XX", "Unknown"), ("AK", "Unknown"), ("CA", "Unknown"), ("IL", "")):
            with self.subTest(state=state, city=city):
                result = tax_provider.check({**self.cart, "state": state, "city": city}, self.skill)
                self.assertFalse(result["complete"])
                self.assertIsNone(result["oa_rate"])
                self.assertIsNone(result["oa_tax"])

    def test_nexus_metadata_does_not_change_rate(self):
        for nexus in (None, [], ["TX"], ["IL"]):
            with self.subTest(nexus=nexus):
                self.skill["rules"]["nexus_states"] = nexus
                self.assertEqual(tax_provider.check(self.cart, self.skill)["oa_rate"], Decimal("0.1025"))

    def test_region_comparisons_and_known_zero(self):
        for rate, delta in (("0.0625", "8.00"), ("0.1025", "0.00"), ("0.12", "-3.50")):
            with self.subTest(rate=rate):
                result = tax_provider.check({**self.cart, "medusa_region_rate": Decimal(rate)}, self.skill)
                self.assertTrue(result["complete"])
                self.assertEqual(result["delta"], Decimal(delta))
        result = tax_provider.check({**self.cart, "state": "OR", "city": "Portland"}, self.skill)
        self.assertTrue(result["complete"])
        self.assertEqual(result["oa_rate"], Decimal(0))

    def test_small_rate_difference_is_visible(self):
        result = tax_provider.check({**self.cart, "subtotal": Decimal("100000"),
                                     "medusa_region_rate": Decimal("0.1024")}, self.skill)
        self.assertEqual(result["delta"], Decimal("10.00"))
        self.assertNotEqual(result["status"], "ok")

    def test_difference_ignores_the_callers_decimal_precision(self):
        with localcontext() as context:
            context.prec = 2
            result = tax_provider.check({**self.cart, "subtotal": "123.45"}, self.skill)
        self.assertEqual(result["oa_tax"], Decimal("12.65"))
        self.assertEqual(result["medusa_tax"], Decimal("7.72"))
        self.assertEqual(result["delta"], Decimal("4.93"))

    def test_missing_values_are_not_zero(self):
        for key in ("subtotal", "medusa_region_rate", "currency"):
            with self.subTest(key=key):
                result = tax_provider.check({**self.cart, key: None}, self.skill)
                self.assertFalse(result["complete"])
        raw = {"items": [{"unit_price": "2"}], "currency_code": "usd"}
        self.assertIsNone(medusa_client.normalize(raw)["subtotal"])
        self.assertIsNone(medusa_client.normalize(raw)["medusa_region_rate"])

    def test_invalid_numbers_and_unknown_schema(self):
        for value in (True, "NaN", "Infinity", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tax_provider.check({**self.cart, "subtotal": value}, self.skill)
        self.skill["rules"]["schema"] = "unknown"
        result = tax_provider.check(self.cart, self.skill)
        self.assertFalse(result["complete"])

    def test_decimal_rounding_and_equal_rounded_amounts(self):
        self.skill["rules"]["combined_rates"]["IL/Chicago"] = "0.005"
        result = tax_provider.check({**self.cart, "subtotal": "1", "medusa_region_rate": "0"}, self.skill)
        self.assertEqual(result["oa_tax"], Decimal("0.01"))
        self.skill["rules"]["combined_rates"]["IL/Chicago"] = "0.004"
        result = tax_provider.check({**self.cart, "subtotal": "1", "medusa_region_rate": "0.003"}, self.skill)
        self.assertNotEqual(result["status"], "ok")
        self.assertIn("same rounded amount", result["detail"])

    def test_zero_inputs_do_not_complete_unknown_coverage(self):
        result = tax_provider.check({**self.cart, "state": "XX", "subtotal": 0,
                                     "medusa_region_rate": 0}, self.skill)
        self.assertFalse(result["complete"])
        self.assertEqual(result["medusa_tax"], Decimal(0))
        self.assertIsNone(result["oa_tax"])

    def test_cart_validation_and_explicit_empty_items(self):
        for item in ({"quantity": True, "unit_price": 1},
                     {"quantity": "1.5", "unit_price": 1},
                     {"quantity": 1, "unit_price": "NaN"}):
            with self.subTest(item=item), self.assertRaises(ValueError):
                medusa_client.normalize({"items": [item]})
        self.assertEqual(medusa_client.normalize({"items": []})["subtotal"], Decimal(0))
        self.assertIsNone(medusa_client.normalize({})["subtotal"])

    def test_whole_quantity_with_trailing_zeros(self):
        cart = {"items": [{"quantity": "2.000000", "unit_price": "0.100000"}]}
        self.assertEqual(medusa_client.normalize(cart)["subtotal"], Decimal("0.2"))

    def test_unknown_rule_fields_and_units(self):
        for key, value in (("rate_unit", "percent"), ("exemption_policy", "all")):
            with self.subTest(key=key):
                skill = copy.deepcopy(self.skill)
                skill["rules"][key] = value
                self.assertFalse(tax_provider.check(self.cart, skill)["complete"])

    def test_reported_metadata_is_not_attestation(self):
        oa = OAClient(token="synthetic-test-token")
        reported = {**self.skill, "tier": 1, "verifier": "Example reviewer", "provenance": "verified"}
        with patch.object(oa, "_call", return_value=reported):
            skill = oa.get_skill("us-sales-tax-rates")
        result = tax_provider.check(self.cart, skill)
        self.assertEqual(result["provenance"], "provider-reported")
        self.assertEqual(result["reported_metadata"]["verifier"], "Example reviewer")
        self.assertIsNone(self.skill["verifier"])

    def test_pipeline_renders_unknown_values_and_keeps_other_rows(self):
        rows = [{"id": "unknown", "items": [], "currency_code": "usd", "medusa_region_rate": 0},
                {"id": "invalid", "items": [{"unit_price": True, "quantity": 1}]},
                {"id": "valid", "items": [], "currency_code": "usd", "medusa_region_rate": "0.0825",
                 "shipping_address": {"province": "TX", "city": "Austin"}}]
        output = io.StringIO()
        with patch.object(medusa_client, "extract", return_value=rows), contextlib.redirect_stdout(output):
            complete = pipeline.run("unused.json", OAClient(token=None))
        self.assertFalse(complete)
        self.assertIn("unknown", output.getvalue())
        self.assertIn("invalid input", output.getvalue())
        self.assertIn("cart valid", output.getvalue())
        self.assertIn("unverified sample rules", output.getvalue())
        self.assertNotIn("signed off", output.getvalue())

    def test_cli_returns_nonzero_for_incomplete_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "incomplete.json"
            source.write_text(json.dumps({"items": []}), encoding="utf-8")
            result = subprocess.run([sys.executable, "-X", "utf8", str(Path(pipeline.__file__)), str(source)],
                                    capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Comparison incomplete", result.stdout)

    def test_live_failure_does_not_fall_back_to_samples(self):
        oa = OAClient(token="synthetic-test-token")
        with patch.object(oa, "_call", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                oa.get_skill("us-sales-tax-rates")

    def test_default_cli_selects_offline_mode_explicitly(self):
        with patch.object(pipeline, "OAClient", return_value=OAClient(token=None)) as constructor:
            with patch.object(pipeline, "run", return_value=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pipeline.main(["pipeline.py"]), 0)
        constructor.assert_called_once_with(token=None)


if __name__ == "__main__":
    unittest.main()
