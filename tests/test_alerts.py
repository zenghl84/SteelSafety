"""Verify actionable risk provenance and agreement with homepage risk counts."""
import copy
import csv
import json
from pathlib import Path
import unittest

from core.alerts import build_alerts
from core.assessment import build_assessment, evaluate_point, summarize
from core.key_indicators import build_key_indicators
from core.model import parse

ROOT = Path(__file__).resolve().parents[1]


class AlertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model = parse((ROOT / "data/model.mgt").read_bytes())
        with (ROOT / "data/sensor_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
            mapping = list(csv.DictReader(f))
        cls.assessment = build_assessment(ROOT, {"history": {}}, model, mapping)
        cls.indicators = build_key_indicators(ROOT, cls.assessment)
        cls.alerts = build_alerts(cls.assessment, cls.indicators)

    def test_confirmed_risks_are_same_two_as_homepage(self):
        snapshot = self.alerts["snapshots"]["confirmed"]
        self.assertEqual([r["id"] for r in snapshot["items"]], ["S1", "S2"])
        self.assertEqual(snapshot["counts"], {"total": 2, "equipment": 1, "stress": 1, "data": 0})
        for key, source in self.alerts["snapshots"].items():
            risk = next(r for r in self.indicators["by_source"][key]["observed"] if r["id"] == "risk")
            self.assertEqual(source["counts"]["total"], risk["value"])
            self.assertEqual([r["id"] for r in source["items"]], [r["sensor_id"] for r in risk["risk_items"]])

    def test_failed_s1_has_device_provenance_and_no_stress_alarm(self):
        row = self.alerts["snapshots"]["confirmed"]["items"][0]
        self.assertEqual(row["category"], "equipment")
        self.assertEqual(row["record_by"], "用户标记")
        self.assertEqual(row["record_time"], "2026-10-18")
        self.assertEqual((row["element"], row["end"]), (11368, "J"))
        self.assertIsNone(row["row"]["score"])
        self.assertEqual(row["row"]["reference_score"], 0)
        self.assertNotIn("thresholds", row)
        self.assertIn("不参与", row["calculation"])

    def test_s2_calculation_and_project_thresholds(self):
        row = self.alerts["snapshots"]["confirmed"]["items"][1]
        self.assertEqual(row["category"], "stress")
        self.assertEqual((row["element"], row["end"]), (5545, "J"))
        self.assertEqual(row["metrics"][0]["value"], "-163.5729")
        self.assertEqual(row["metrics"][1]["value"], "76.08")
        self.assertEqual(row["metrics"][2]["value"], "73.9")
        self.assertIn("项目暂定", row["trigger"])
        for limit, expected in zip(row["thresholds"], [150.5, 193.5, 215]):
            self.assertAlmostEqual(limit["mpa"], expected)

    def test_unrecorded_measurement_and_trigger_times_stay_unknown(self):
        items = self.alerts["snapshots"]["confirmed"]["items"]
        self.assertEqual(items[0]["measurement_time"], "原表未提供采样时刻")
        self.assertEqual(items[1]["record_time"], "触发时刻未记录")
        self.assertEqual(items[1]["state"], "待复核")

    def test_missing_record_stays_unassessed_and_not_zero(self):
        snapshot = self.alerts["snapshots"]["monitoring"]
        self.assertEqual(snapshot["counts"], {"total": 9, "equipment": 1, "stress": 0, "data": 8})
        missing = snapshot["items"][1]
        self.assertEqual(missing["category"], "data")
        self.assertIsNone(missing["row"]["ratio"])
        self.assertEqual(missing["metrics"][1]["value"], "—")

    def test_boundary_and_over_limit_states_follow_existing_assessment(self):
        cfg = self.assessment["snapshots"]["confirmed"]["rows"][1]
        for ratio, count, title in [(.7, 0, None), (.9, 1, "应力关注"), (.95, 1, "应力预警"), (1, 1, "应力超限待核验")]:
            with self.subTest(ratio=ratio):
                row = evaluate_point(cfg, ratio * 215 - cfg["initial_mpa"])
                snapshot = {"label": "测试", "source": "测试记录", "time_label": "未提供", "rows": [row], "summary": summarize([row])}
                assessment = {"snapshots": {"confirmed": snapshot}}
                alerts = build_alerts(assessment, build_key_indicators(ROOT, assessment))["snapshots"]["confirmed"]
                self.assertEqual(alerts["counts"]["total"], count)
                if title:
                    self.assertEqual(alerts["items"][0]["title"], title)

    def test_demo_values_and_risk_views_do_not_mutate_assessment(self):
        before = copy.deepcopy(self.assessment)
        bundle = build_alerts(self.assessment, self.indicators)
        self.assertEqual(self.assessment, before)
        bundle["snapshots"]["confirmed"]["items"][0]["row"]["initial_mpa"] = 999
        self.assertEqual(self.assessment, before)
        for snapshot in self.alerts["snapshots"].values():
            for item in snapshot["items"]:
                self.assertGreaterEqual(len(item["actions"]), 2)
                self.assertTrue(item["references"])
                self.assertNotIn(item["category"], ("fatigue", "corrosion", "life", "deflection"))
        json.dumps(self.alerts, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
