import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"
os.environ["DEEL_API_TOKEN"] = ""
os.environ["ETHERSCAN_API_KEY"] = ""


class CommandLineTests(unittest.TestCase):
    def test_invalid_and_empty_files_return_a_diagnostic_without_a_traceback(self):
        cases = [("[]", "at least one record"),
                 ('{"value":NaN}', "non-standard JSON"),
                 ('{"value":Infinity}', "non-standard JSON"),
                 ('{"value":-Infinity}', "non-standard JSON"),
                 ('{"value":1e999999999999999999999}', "invalid JSON decimal")]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.json"
            for payload, diagnostic in cases:
                with self.subTest(payload=payload):
                    source.write_text(payload, encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, "-X", "utf8", str(Path(__file__).resolve().parents[1] / "pipeline.py"), str(source)],
                        capture_output=True, text=True, encoding="utf-8", check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
