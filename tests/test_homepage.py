"""Exercise the complete relocated dashboard with its actual v1.8 project data."""
import hashlib
import json
from pathlib import Path
import re
import unittest

from core.home import build_homepage


ROOT = Path(__file__).resolve().parents[1]


class HomepageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = build_homepage()
        match = re.search(
            r'<script id="payload" type="application/json">(.*?)</script>',
            cls.html,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError("The assembled dashboard is missing its data payload")
        cls.payload = json.loads(match.group(1))

    def test_page_embeds_all_modules_without_template_placeholders(self):
        for placeholder in (
            "__ASSESSMENT__", "__ALERTS__", "__STYLE__", "__PROJECT_FRONT__",
            "__PAYLOAD__", "__RUNTIME__",
        ):
            self.assertNotIn(placeholder, self.html)
        for module in ("monitor-workspace", "assessment-workspace", "alerts-workspace",
                       "knowledge-workspace", "model-frame"):
            self.assertIn(f'id="{module}"', self.html)

    def test_model_bytes_and_cs19_snapshot_still_match(self):
        digest = hashlib.sha256((ROOT / "data/model.mgt").read_bytes()).hexdigest()
        self.assertEqual(self.payload["stress"]["model_sha256"], digest)
        self.assertTrue(self.payload["stress_values"])

    def test_relocated_page_keeps_scores_faults_and_risk_sources(self):
        summary = self.payload["assessment"]["snapshots"]["confirmed"]["summary"]
        self.assertAlmostEqual(summary["mean_score"], 82.4207803617571)
        self.assertAlmostEqual(summary["valid_mean_score"], 92.72337790697674)
        self.assertEqual(summary["fault_sensor_ids"], ["S1"])
        risks = self.payload["alerts"]["snapshots"]["confirmed"]["items"]
        self.assertEqual([risk["id"] for risk in risks], ["S1", "S2"])
        history = self.payload["history"]
        self.assertEqual(set(history), {"S1", "S2", "S3", "S5", "S6", "S7", "S8", "S9", "S10"})
        self.assertEqual(self.payload["record_count"], sum(map(len, history.values())))


if __name__ == "__main__":
    unittest.main()
