import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from http.client import IncompleteRead
from unittest.mock import patch

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"

import pipeline
from oa_client import OAClient

SAMPLE = Path(pipeline.__file__).parent / "samples/carts.json"


class ReportingTests(unittest.TestCase):
    def test_default_cli_survives_a_non_unicode_output_encoding(self):
        environment = {"PYTHONIOENCODING": "cp1252", "OA_MCP_TOKEN": "", "OA_MCP_URL": "https://example.invalid"}
        if os.name == "nt":
            environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        result = subprocess.run(
            [sys.executable, str(Path(pipeline.__file__))],
            env=environment,
            capture_output=True, text=True, encoding="cp1252", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unverified sample rules", result.stdout)

    def test_record_text_is_visible_data_not_terminal_controls(self):
        row = json.loads(SAMPLE.read_text(encoding="utf-8"))[0]
        changed = copy.deepcopy(row)
        changed["id"] = "Line 1\x1b[2J\nLine 2"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "control.json"
            source.write_text(json.dumps([row, changed]), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                pipeline.run(str(source), OAClient(token=None))
        text = output.getvalue()
        self.assertNotIn("\x1b", text)
        self.assertIn("\\x1b", text)
        self.assertIn("\\n", text)
        self.assertEqual(text.count("unverified sample rules"), 2)

    def test_provider_text_is_escaped(self):
        oa = OAClient(token=None)
        slug = oa.start("example", "US")["skills_to_load"][0]
        skill = oa.get_skill(slug)
        skill["name"] = "Provider\x1b[2J\rname"
        output = io.StringIO()
        with patch.object(oa, "get_skill", return_value=skill), contextlib.redirect_stdout(output):
            pipeline.run(str(SAMPLE), oa)
        self.assertNotIn("\x1b", output.getvalue())
        self.assertNotIn("\r", output.getvalue())
        self.assertIn("\\x1b", output.getvalue())

    def test_truncated_live_response_returns_a_controlled_failure(self):
        oa = OAClient(token="synthetic-test-token")
        output, error = io.StringIO(), io.StringIO()
        with patch.object(pipeline, "OAClient", return_value=oa):
            with patch("urllib.request.urlopen", side_effect=IncompleteRead(b"{", 100)):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    result = pipeline.main(["pipeline.py", "--live", str(SAMPLE)])
        self.assertEqual(result, 2)
        self.assertIn("HTTP response", error.getvalue())
        self.assertNotIn("unverified sample rules", output.getvalue())


if __name__ == "__main__":
    unittest.main()
