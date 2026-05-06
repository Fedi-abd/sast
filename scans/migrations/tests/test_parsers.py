from django.test import TestCase
from scans.tools.semgrep_parser import SemgrepParser

class SemgrepParserTests(TestCase):
    def test_parser_extracts_basic_fields(self):
        parser = SemgrepParser()
        raw = """
        {
            "results": [
                {
                    "check_id": "python.lang.correctness",
                    "path": "app.py",
                    "start": {"line": 42},
                    "extra": {
                        "message": "Example message",
                        "metadata": {"cwe": "CWE-79"}
                    }
                }
            ]
        }
        """
        results = parser.parse(raw)
        self.assertEqual(len(results), 1)
        f = results[0]
        self.assertEqual(f["rule_id"], "python.lang.correctness")
        self.assertEqual(f["file_path"], "app.py")
        self.assertEqual(f["line_number"], 42)
        self.assertEqual(f["cwe_id"], "CWE-79")