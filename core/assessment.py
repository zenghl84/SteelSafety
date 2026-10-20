"""CS18-referenced stress screening; project score mapping, not capacity certification."""
from decimal import Decimal
import json
from math import isfinite
from pathlib import Path


def finite_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def stress_score(ratio):
    """Interpolate the user-reviewed 50/70/90/100 percent score anchors."""
    r = finite_number(ratio)
    if r is None or r < 0:
        return None
    if r <= 0.5:
        return 100.0
    if r <= 0.9:
        return max(0.0, min(100.0, 150.0 - 100.0 * r))
    if r < 1.0:
        return max(0.0, 600.0 * (1.0 - r))
    return 0.0


def evaluate_point(config, delta_mpa, timestamp=None, reason=None):
    """Preserve sign before adding baseline; missing data never becomes zero."""
    row = {
        **config,
        "delta_mpa": finite_number(delta_mpa),
        "timestamp": timestamp,
        "total_mpa": None,
        "ratio": None,
        "score": None,
        "status": "缺少有效数据",
        "tone": "muted",
        "reason": reason or "",
    }
    def finish():
        # Keep the original numerical mapping for the requested historical mean.
        # A declared failed device is excluded from valid-measurement statistics.
        row["reference_score"] = row["score"]
        if config.get("sensor_status") == "damaged":
            row["calculation_note"] = row["reason"]
            row["score"] = None
            row["status"] = "传感器损坏"
            row["tone"] = "fault"
            row["reason"] = config.get(
                "sensor_status_note",
                "用户已标记传感器损坏；保留原始换算，不参与有效测点评分。",
            )
        return row

    initial = finite_number(config.get("initial_mpa"))
    reference = finite_number(config.get("reference_mpa"))
    if initial is None or reference is None or reference <= 0:
        row["reason"] = "初始应力或材料基准无效"
        return finish()
    if row["delta_mpa"] is None:
        row["reason"] = reason or "没有可用的应力增量，未补零"
        return finish()
    total = float(Decimal(str(initial)) + Decimal(str(row["delta_mpa"])))
    if not isfinite(total):
        row["reason"] = "应力叠加结果无效"
        return finish()
    ratio = abs(total) / reference
    row.update(total_mpa=total, ratio=ratio, score=stress_score(ratio))
    if ratio >= 1:
        row.update(
            status="超限待核验", tone="danger",
            reason="换算值达到或超过材料基准，需核查监测系统与结构实际状态。",
        )
    elif ratio > 0.9:
        row.update(status="预警", tone="warning")
    elif ratio > 0.7:
        row.update(status="关注", tone="attention")
    else:
        row.update(status="占用较低", tone="normal")
    return finish()


def summarize(rows):
    valid = [r for r in rows if r["score"] is not None]
    faults = [r for r in rows if r["tone"] == "fault"]
    missing = len(rows) - len(valid) - len(faults)
    reference = [r.get("reference_score", r["score"]) for r in rows
                 if r.get("reference_score", r["score"]) is not None]
    counts = {key: sum(r["tone"] == key for r in rows)
              for key in ("normal", "attention", "warning", "danger", "muted", "fault")}
    minimum = min((r["score"] for r in valid), default=None)
    control_ids = [r["sensor_id"] for r in valid
                   if abs(r["score"] - minimum) < 1e-9] if valid else []
    if counts["danger"]:
        status, tone = "异常待核验", "danger"
    elif faults:
        status, tone = "传感器损坏", "fault"
    elif missing:
        status, tone = "数据不完整", "muted"
    elif counts["warning"]:
        status, tone = "应力预警", "warning"
    elif counts["attention"]:
        status, tone = "应力关注", "attention"
    else:
        status, tone = "应力占用较低", "normal"
    return {
        "expected_count": len(rows),
        "valid_count": len(valid),
        "missing_count": missing,
        "fault_count": len(faults),
        "fault_sensor_ids": [r["sensor_id"] for r in faults],
        "reference_score_count": len(reference),
        "reference_mean_includes_faults": any(r.get("reference_score") is not None for r in faults),
        "over_limit_count": counts["danger"],
        "counts": counts,
        "mean_score": sum(reference) / len(reference) if reference else None,
        "valid_mean_score": sum(r["score"] for r in valid) / len(valid) if valid else None,
        "control_score": minimum if len(valid) == len(rows) else None,
        "provisional_min": minimum,
        "control_sensor_ids": control_ids,
        "status": status,
        "tone": tone,
    }


def validate_config(config, model, mapping):
    """Verify the reviewed table still refers to the model and sensor endpoints."""
    sensors = config["sensors"]
    if not sensors or len({r["sensor_id"] for r in sensors}) != len(sensors):
        raise ValueError("评分配置的测点为空或重复")
    if finite_number(config.get("elastic_modulus_mpa")) is None or config["elastic_modulus_mpa"] <= 0:
        raise ValueError("评分配置的弹性模量无效")
    for point in sensors:
        sid = point["sensor_id"]
        mapped = mapping.get(sid)
        element = model["elements"].get(point["element"])
        if mapped is None or element is None:
            raise ValueError(f"评分测点 {sid} 缺少单元或测点映射")
        if int(mapped["element"]) != point["element"]:
            raise ValueError(f"评分测点 {sid} 的单元映射不一致")
        if float(mapped["position"]) != (0.0 if point["end"] == "I" else 1.0):
            raise ValueError(f"评分测点 {sid} 的 I/J 端映射不一致")
        material = model["materials"].get(element["material"], "")
        if not material.startswith(point["material"]):
            raise ValueError(f"评分测点 {sid} 的模型钢材牌号不一致")
        if point["end"] not in ("I", "J") or point["reference_mpa"] <= 0:
            raise ValueError(f"评分测点 {sid} 的端部或材料基准无效")


def build_assessment(project_dir: Path, monitoring_data, model, mapping_rows):
    config = json.loads((project_dir / "data/assessment_config.json").read_text(encoding="utf-8"))
    validate_config(config, model, {r["sensor_id"]: r for r in mapping_rows})
    confirmed = [
        evaluate_point(p, p.get("confirmed_delta_mpa"),
                       config.get("confirmed_measurement_time"))
        for p in config["sensors"]
    ]
    monitoring = []
    for point in config["sensors"]:
        records = monitoring_data["history"].get(point["sensor_id"], [])
        # Keep the latest record even when empty. Do not silently reuse an older value.
        record = max(records, key=lambda r: r["timestamp"]) if records else None
        strain = finite_number(record.get("corrected_strain")) if record else None
        unit = str(record.get("corrected_strain_unit", "")).strip() if record else ""
        if strain is not None and unit not in ("με", "μɛ", "μe", "μE", "ue", "µε"):
            strain = None
            reason = "温补后应变单位未确认，暂不换算"
        else:
            reason = "最新记录缺少温补后应变，未补零" if record else "未接入该测点监测记录"
        delta = float(Decimal(str(strain)) *
                      Decimal(str(config["elastic_modulus_mpa"])) / Decimal("1000000")) if strain is not None else None
        timestamp = record["timestamp"].isoformat(timespec="seconds") if record else None
        row = evaluate_point(point, delta, timestamp, reason if delta is None else None)
        row["strain_ue"] = strain
        monitoring.append(row)
    times = [r["timestamp"] for r in monitoring if r["timestamp"]]
    return {
        "version": config["version"],
        "baseline_stage": config["baseline_stage"],
        "elastic_modulus_mpa": config["elastic_modulus_mpa"],
        "component_note": config["component_note"],
        "device_status": {
            p["sensor_id"]: {
                "status": p["sensor_status"],
                "label": p.get("sensor_status_label", "设备状态待核查"),
                "reported_by": p.get("status_reported_by", ""),
                "recorded_at": p.get("status_recorded_at", ""),
            }
            for p in config["sensors"] if p.get("sensor_status")
        },
        "default_source": "confirmed",
        "snapshots": {
            "confirmed": {
                "label": "已确认评分表",
                "source": config["confirmed_source"],
                "time_label": "原表未提供采样时刻",
                "rows": confirmed,
                "summary": summarize(confirmed),
            },
            "monitoring": {
                "label": "最新监测记录",
                "source": "工作簿各测点最新记录 · 温补后应变换算",
                "time_label": max(times).replace("T", " ") if times else "暂无有效记录",
                "rows": monitoring,
                "summary": summarize(monitoring),
            },
        },
    }
