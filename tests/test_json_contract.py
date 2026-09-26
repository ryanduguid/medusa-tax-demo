import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"

import pipeline
from oa_client import OAClient


class JsonContractTests(unittest.TestCase):
    def test_duplicate_provider_properties_fail_at_both_boundaries(self):
        skill = '{"rules":{},"rules":{"different":true}}'
        responses = [
            '{"jsonrpc":"2.0","id":1,"result":{"structuredContent":' + skill + '}}',
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": skill}]}}),
            '{"jsonrpc":"2.0","id":2,"id":1,"result":{"structuredContent":{}}}',
        ]
        for payload in responses:
            with self.subTest(payload=payload):
                with patch("urllib.request.urlopen", return_value=io.BytesIO(payload.encode("utf-8"))):
                    with self.assertRaisesRegex(ValueError, "duplicate JSON"):
                        OAClient(token="synthetic-test-token").get_skill("example")

    def test_duplicate_input_properties_are_never_silently_overwritten(self):
        for payload in ('{"period_sales":140000,"period_sales":0}',
                        '{"full_time_exclusive":true,"full_time_exclusive":false}',
                        '{"metadata":{"same":1,"same":2}}'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "duplicate.json"
                source.write_text(payload, encoding="utf-8")
                output, error = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    self.assertEqual(pipeline.main(["pipeline.py", str(source)]), 2)
                self.assertIn("duplicate JSON", error.getvalue())
                self.assertNotIn("unverified sample rules", output.getvalue())
