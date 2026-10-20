"""Check KPI evidence, failed-device exclusion and demo/assessment separation."""
import copy
import csv
import json
from pathlib import Path
import unittest

from core.assessment import build_assessment
from core.key_indicators import (
    build_key_indicators, demonstration_indicators, source_markdown,
)
from core.model import parse

ROOT = Path(__file__).resolve().parents[1]


class KeyIndicatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = parse((ROOT / "data/model.mgt").read_bytes())
        with (ROOT / "data/sensor_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
            cls.mapping = list(csv.DictReader(f))
        cls.assessment = build_assessment(ROOT, {"history": {}}, cls.model, cls.mapping)
        cls.config = json.loads((ROOT / "data/key_indicators_config.json").read_text(encoding="utf-8"))
        cls.bundle = build_key_indicators(ROOT, cls.assessment)

    def rows(self, mode, source="confirmed"):
        return {r["id"]: r for r in self.bundle["by_source"][source][mode]}

    def test_maximum_uses_eight_valid_points_excluding_s1(self):
        row = self.rows("observed")["stress"]
        self.assertAlmostEqual(row["value"], 163.5729 / 215)
        self.assertEqual(round(row["value"], 3), .761)
        self.assertIn("S2", row["calculation"])
        self.assertIn("S1", row["note"])
        self.assertEqual(row["kind"], "computed")

    def test_risks_are_review_items_not_damage_counts(self):
        row = self.rows("observed")["risk"]
        self.assertEqual(row["value"], 2)
        self.assertEqual([i["sensor_id"] for i in row["risk_items"]], ["S1", "S2"])
        self.assertEqual(row["risk_items"][0]["type"], "设备故障")
        self.assertEqual(row["unit"], "项")

    def test_unsupported_observed_values_remain_unassessed(self):
        rows = self.rows("observed")
        for key in ["deflection", "fatigue", "corrosion", "life"]:
            self.assertIsNone(rows[key]["value"])
            self.assertEqual(rows[key]["kind"], "missing")
            self.assertTrue(rows[key]["required"])

    def test_demo_values_are_calculated_and_explicitly_labeled(self):
        rows = self.rows("demo")
        for key, value in {"deflection": 18.6, "fatigue": .12, "corrosion": 1, "life": 40}.items():
            with self.subTest(key=key):
                self.assertAlmostEqual(rows[key]["value"], value)
                self.assertEqual(rows[key]["kind"], "demo")
                self.assertIn("演示", rows[key]["source"])
        self.assertEqual(rows["stress"]["kind"], "computed")
        self.assertEqual(rows["risk"]["kind"], "computed")

    def test_demo_does_not_change_score_or_original_evidence(self):
        before = json.dumps(self.assessment, sort_keys=True)
        build_key_indicators(ROOT, self.assessment)
        self.assertEqual(json.dumps(self.assessment, sort_keys=True), before)
        self.assertAlmostEqual(self.assessment["snapshots"]["confirmed"]["summary"]["mean_score"], 82.4207803617571)
        self.assertIsNone(self.rows("observed")["fatigue"]["value"])

    def test_missing_monitoring_does_not_become_zero_stress(self):
        rows = self.rows("observed", source="monitoring")
        self.assertIsNone(rows["stress"]["value"])
        self.assertEqual(rows["risk"]["value"], 9)

    def test_invalid_demo_assumptions_are_rejected(self):
        observed = self.bundle["by_source"]["confirmed"]["observed"]
        for group, field, value in [
            ("fatigue", "assumed_cycles_to_failure", 0),
            ("corrosion", "remaining_thickness_mm", 7),
            ("life", "assumed_elapsed_years", 60),
        ]:
            scenario = copy.deepcopy(self.config["scenario"])
            scenario[group][field] = value
            with self.subTest(group=group), self.assertRaises(ValueError):
                demonstration_indicators(observed, scenario)

    def test_source_export_distinguishes_assumptions_from_standards(self):
        report = source_markdown(self.bundle)
        self.assertIn("18.6", report)
        self.assertIn("0.120", report)
        self.assertIn("40年", report)
        self.assertIn("不是规范腐蚀分级", report)
        self.assertIn("gf.cabr-fire.com", report)
        json.dumps(self.bundle, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
