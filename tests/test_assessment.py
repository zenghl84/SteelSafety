"""Business checks for reviewed scores, missing data and source separation."""
import copy
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import unittest

from core.assessment import (
    build_assessment, evaluate_point, stress_score, summarize, validate_config,
)
from core.model import parse

ROOT = Path(__file__).resolve().parents[1]


class ScoreTests(unittest.TestCase):
    def test_reviewed_interpolation_and_boundaries(self):
        for ratio, expected in [(0, 100), (.5, 100), (.7, 80),
                                (.9, 60), (.95, 30), (1, 0), (2.2, 0)]:
            with self.subTest(ratio=ratio):
                self.assertAlmostEqual(stress_score(ratio), expected)
        for invalid in (None, float("nan"), float("inf"), -1, True):
            self.assertIsNone(stress_score(invalid))

    def test_sign_is_preserved_before_normalizing(self):
        cfg = {"sensor_id": "S2", "initial_mpa": -171, "reference_mpa": 215}
        row = evaluate_point(cfg, 7.4271)
        self.assertAlmostEqual(row["total_mpa"], -163.5729)
        self.assertAlmostEqual(row["score"], 73.9195813953)
        self.assertEqual(row["status"], "关注")

    def test_zero_score_is_kept_as_an_over_limit_value(self):
        cfg = {"sensor_id": "S1", "initial_mpa": -179, "reference_mpa": 215}
        row = evaluate_point(cfg, -292.7882)
        result = summarize([row])
        self.assertEqual(row["score"], 0)
        self.assertEqual(result["control_score"], 0)
        self.assertEqual(result["over_limit_count"], 1)
        self.assertEqual(result["status"], "异常待核验")

    def test_damaged_sensor_is_not_an_active_stress_alarm(self):
        cfg = {"sensor_id": "S1", "initial_mpa": -179, "reference_mpa": 215,
               "sensor_status": "damaged", "status_reported_by": "用户标记"}
        row = evaluate_point(cfg, -292.7882)
        self.assertAlmostEqual(row["total_mpa"], -471.7882)
        self.assertIsNone(row["score"])
        self.assertEqual(row["reference_score"], 0)
        self.assertEqual(row["status"], "传感器损坏")
        result = summarize([row])
        self.assertEqual(result["fault_count"], 1)
        self.assertEqual(result["over_limit_count"], 0)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["valid_count"], 0)
        self.assertIsNone(result["valid_mean_score"])

    def test_other_sensor_stress_alarm_survives_a_damaged_sensor(self):
        faulty = evaluate_point({"sensor_id": "S1", "initial_mpa": -179,
                                 "reference_mpa": 215, "sensor_status": "damaged"},
                                -292.7882)
        alarm = evaluate_point({"sensor_id": "S5", "initial_mpa": 130,
                                "reference_mpa": 215}, 200)
        result = summarize([faulty, alarm])
        self.assertEqual(result["status"], "异常待核验")
        self.assertEqual(result["over_limit_count"], 1)
        self.assertEqual(result["fault_sensor_ids"], ["S1"])

    def test_missing_values_are_not_scored_or_imputed(self):
        cfg = {"sensor_id": "S7", "initial_mpa": 26.1, "reference_mpa": 215}
        for delta in (None, float("nan"), float("inf")):
            row = evaluate_point(cfg, delta)
            result = summarize([row])
            self.assertIsNone(row["score"])
            self.assertIsNone(result["control_score"])
            self.assertEqual(result["missing_count"], 1)

    def test_missing_point_blocks_group_control_but_keeps_other_alarms(self):
        bad = evaluate_point({"sensor_id": "S1", "initial_mpa": -179,
                              "reference_mpa": 215}, -292.7882)
        missing = evaluate_point({"sensor_id": "S7", "initial_mpa": 26.1,
                                  "reference_mpa": 215}, None)
        result = summarize([bad, missing])
        self.assertIsNone(result["control_score"])
        self.assertEqual(result["provisional_min"], 0)
        self.assertEqual(result["status"], "异常待核验")
        self.assertEqual(result["missing_count"], 1)


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "data/assessment_config.json").read_text(encoding="utf-8"))
        cls.model = parse((ROOT / "data/model.mgt").read_bytes())
        with (ROOT / "data/sensor_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
            cls.mapping = list(csv.DictReader(f))

    def build(self, history):
        return build_assessment(ROOT, {"history": history}, self.model, self.mapping)

    def test_confirmed_nine_point_snapshot_includes_surface_sensors(self):
        result = self.build({})
        data = result["snapshots"]["confirmed"]
        self.assertEqual(len(data["rows"]), 9)
        expected = {"S1": 0, "S2": 73.9, "S3": 94.9, "S5": 86.0,
                    "S6": 87.0, "S7": 100, "S8": 100, "S9": 100, "S10": 100}
        for row in data["rows"]:
            self.assertEqual(round(row["reference_score"], 1), expected[row["sensor_id"]])
            if row["sensor_id"] == "S1":
                self.assertIsNone(row["score"])
                self.assertEqual(row["status"], "传感器损坏")
            else:
                self.assertEqual(round(row["score"], 1), expected[row["sensor_id"]])
        self.assertAlmostEqual(data["summary"]["mean_score"], 82.4207803617571)
        self.assertAlmostEqual(data["summary"]["valid_mean_score"], 92.72337790697674)
        self.assertEqual(data["summary"]["control_sensor_ids"], ["S2"])
        self.assertEqual(data["summary"]["valid_count"], 8)
        self.assertEqual(data["summary"]["fault_sensor_ids"], ["S1"])
        self.assertEqual(data["summary"]["over_limit_count"], 0)
        self.assertTrue(data["summary"]["reference_mean_includes_faults"])
        self.assertEqual(result["device_status"]["S1"]["reported_by"], "用户标记")
        json.dumps(result, allow_nan=False)

    def test_latest_record_is_converted_without_changing_confirmed_source(self):
        now = datetime(2026, 10, 16, 23, 17, 26)
        result = self.build({"S7": [
            {"timestamp": now - timedelta(hours=1), "corrected_strain": 100,
             "corrected_strain_unit": "με"},
            {"timestamp": now, "corrected_strain": 10, "corrected_strain_unit": "με"},
        ]})
        latest = {p["sensor_id"]: p for p in result["snapshots"]["monitoring"]["rows"]}
        self.assertAlmostEqual(latest["S7"]["delta_mpa"], 2.06)
        self.assertAlmostEqual(latest["S7"]["total_mpa"], 28.16)
        confirmed = {p["sensor_id"]: p for p in result["snapshots"]["confirmed"]["rows"]}
        self.assertAlmostEqual(confirmed["S7"]["total_mpa"], 30.8726)

    def test_latest_empty_record_does_not_fall_back_to_older_measurement(self):
        now = datetime(2026, 10, 16, 23, 17, 26)
        result = self.build({"S8": [
            {"timestamp": now - timedelta(hours=1), "corrected_strain": 10,
             "corrected_strain_unit": "με"},
            {"timestamp": now, "corrected_strain": None, "corrected_strain_unit": "με"},
        ]})
        latest = {p["sensor_id"]: p for p in result["snapshots"]["monitoring"]["rows"]}
        self.assertEqual(latest["S8"]["timestamp"], now.isoformat())
        self.assertIsNone(latest["S8"]["score"])

    def test_unconfirmed_strain_units_are_not_converted(self):
        now = datetime(2026, 10, 16)
        result = self.build({"S7": [
            {"timestamp": now, "corrected_strain": 1, "corrected_strain_unit": "m/m"}
        ]})
        row = next(p for p in result["snapshots"]["monitoring"]["rows"] if p["sensor_id"] == "S7")
        self.assertIsNone(row["score"])
        self.assertIn("单位未确认", row["reason"])

    def test_material_and_endpoint_mismatches_are_rejected(self):
        mapping = {r["sensor_id"]: dict(r) for r in self.mapping}
        mapping["S7"]["position"] = 1
        with self.assertRaisesRegex(ValueError, "端映射不一致"):
            validate_config(self.config, self.model, mapping)
        model = copy.deepcopy(self.model)
        model["materials"][model["elements"][4540]["material"]] = "Q355B-1"
        with self.assertRaisesRegex(ValueError, "钢材牌号不一致"):
            validate_config(self.config, model, {r["sensor_id"]: r for r in self.mapping})


if __name__ == "__main__":
    unittest.main()
