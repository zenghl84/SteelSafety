"""A source checkout must work without optional local fonts and PDF originals."""
import json
from pathlib import Path
import tempfile
import unittest

from core.resources import font_styles, load_knowledge_catalog


class OptionalResourceTests(unittest.TestCase):
    def test_missing_font_subsets_fall_back_to_system_fonts(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(font_styles(Path(directory)), "")

    def test_missing_original_retains_metadata_without_an_active_link(self):
        catalog = [
            {"title": "Absent original", "url": "/app/static/knowledge/missing.pdf"},
            {"title": "Installed original", "url": "/app/static/knowledge/local%20copy.pdf"},
            {"title": "External source", "url": "https://example.org/source"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            knowledge = root / "static/knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "local copy.pdf").write_bytes(b"%PDF-local-fixture")
            path = knowledge / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            result = load_knowledge_catalog(root)
            self.assertFalse(result[0]["available"])
            self.assertEqual(result[0]["title"], "Absent original")
            self.assertIn("未安装", result[0]["availability_note"])
            self.assertTrue(result[1]["available"])
            self.assertEqual(result[2], catalog[2])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), catalog)


if __name__ == "__main__":
    unittest.main()
