"""Risk details share the homepage review-item set and preserve source provenance."""
import copy

from .key_indicators import MATERIAL, MONITORING


def risk_detail(row, risk, snapshot, summary):
    category = {"设备故障": "equipment", "数据缺测": "data", "应力复核": "stress"}[risk["type"]]
    detail = {
        "id": row["sensor_id"], "sensor_id": row["sensor_id"],
        "category": category, "type": risk["type"], "tone": row["tone"],
        "element": row["element"], "end": row["end"], "material": row["material"],
        "component": row["component"], "row": copy.deepcopy(row),
        "source_label": snapshot["label"], "source": snapshot["source"],
        "measurement_time": row.get("timestamp") or "原表未提供采样时刻",
        "state": "待检修" if category == "equipment" else "待复核",
        "references": [MONITORING],
    }
    if category == "equipment":
        detail.update(
            title="传感器损坏", priority="优先检修",
            record_time=row.get("status_recorded_at") or "标记时间未提供",
            record_by=row.get("status_reported_by") or "记录来源未提供",
            brief="故障读数已退出有效受力判断，需恢复该位置监测。",
            trigger="设备状态由用户标记为“传感器损坏”；未通过应力数值自动诊断故障原因。",
            impact=f"该点当前有效评分留空；本组有效测点 {summary['valid_count']}/{summary['expected_count']}。对应构件的实际受力仍需其他可靠手段核验。",
            calculation="故障点不参与有效应力比最大值、有效均分及结构应力预警；原始记录继续保留。",
            metrics=[
                {"label": "设备状态", "value": "损坏", "unit": ""},
                {"label": "当前有效评分", "value": "—", "unit": ""},
                {"label": "本组有效覆盖", "value": f"{summary['valid_count']} / {summary['expected_count']}", "unit": "点"},
            ],
            score_note="首页平均参考分沿用原映射口径（保留故障点原映射值）；有效点均分单独剔除故障点。",
            actions=[
                "检查传感器、线缆、供电、采集通道与粘贴位置，记录检修结果。",
                "检修或更换后复核零点、温度补偿及 CS18 基准关系；用独立测量或可靠相邻测点交叉核验。",
                "由监测负责人确认数据恢复可信后，再更新设备状态并恢复有效评分。",
            ],
        )
    elif category == "data":
        detail.update(
            title="缺少有效数据", priority="补充数据", record_time="触发时刻未记录",
            record_by="当前数据检查", brief=row.get("reason") or "最新记录缺少有效应力增量。",
            trigger=row.get("reason") or "没有有效读数，未补零、未沿用较早读数。",
            impact="该测点受力状态暂时无法评分，需恢复有效记录并重新计算。",
            calculation="缺失数据保留为空，每个缺测点记一个待复核项。",
            metrics=[{"label": "数据状态", "value": "缺测", "unit": ""},
                     {"label": "当前有效评分", "value": "—", "unit": ""},
                     {"label": "材料基准", "value": f"{row['reference_mpa']:g}", "unit": "MPa"}],
            score_note="缺测不视为零应力或正常；补齐数据后重新判断。",
            actions=["检查采集通道、时间戳和工作簿记录。", "确认增量基准和量纲后补充有效数据，重新计算应力与评分。"],
        )
    else:
        ratio, total, f = row["ratio"], row["total_mpa"], row["reference_mpa"]
        if ratio >= 1:
            trigger = "材料应力比 r ≥ 100%，触发“超限待核验”。"
            priority = "优先核验"
        elif ratio > .9:
            trigger = "材料应力比 90% < r < 100%，触发“预警”。"
            priority = "重点复核"
        else:
            trigger = "材料应力比 70% < r ≤ 90%，触发“关注”。"
            priority = "持续关注"
        detail.update(
            title="应力" + row["status"], priority=priority,
            record_time="触发时刻未记录", record_by="当前评分规则计算",
            brief=f"应力比 {ratio:.2%}，测点参考评分 {row['score']:.1f} 分。",
            trigger=trigger + " 70%/90%/100% 为本项目暂定筛查分界。",
            impact="该点需结合荷载工况、温度修正与现场状况复核；材料应力比不能覆盖受压稳定、连接和全结构承载力验算。",
            calculation=f"σ = {row['initial_mpa']:g} + ({row['delta_mpa']:.4f}) = {total:.4f} MPa；r = |{total:.4f}| / {f:g} = {ratio:.2%}。",
            metrics=[{"label": "估计总应力", "value": f"{total:.4f}", "unit": "MPa"},
                     {"label": "材料应力比", "value": f"{100*ratio:.2f}", "unit": "%"},
                     {"label": "测点参考评分", "value": f"{row['score']:.1f}", "unit": "/ 100"}],
            score_note="应力正负号按原数据保留，占用比取绝对值；正式预警控制值需由项目监测方案核定。",
            thresholds=[{"label": "关注分界", "ratio": .7, "mpa": .7*f},
                        {"label": "预警分界", "ratio": .9, "mpa": .9*f},
                        {"label": "材料基准", "ratio": 1, "mpa": f}],
            actions=[
                "核对测点、单元端面、应力方向、CS18 安装基准及传感器零点。",
                "复核原始应变、温度补偿和同期荷载变化，结合可靠测点与结构模型交叉比对。",
                "安排对应杆件及连接的现场检查，由专业人员结合稳定与连接验算核定控制值和后续措施。",
            ],
            references=[MATERIAL, MONITORING],
        )
    return detail


def build_alerts(assessment, key_indicators):
    snapshots = {}
    for key, snapshot in assessment["snapshots"].items():
        risk = next(p for p in key_indicators["by_source"][key]["observed"] if p["id"] == "risk")
        rows = {r["sensor_id"]: r for r in snapshot["rows"]}
        items = [risk_detail(rows[r["sensor_id"]], r, snapshot, snapshot["summary"])
                 for r in risk["risk_items"]]
        counts = {c: sum(i["category"] == c for i in items) for c in ("equipment", "stress", "data")}
        snapshots[key] = {
            "label": snapshot["label"], "source": snapshot["source"], "time_label": snapshot["time_label"],
            "items": items, "counts": {"total": len(items), **counts},
            "valid_count": snapshot["summary"]["valid_count"],
            "expected_count": snapshot["summary"]["expected_count"],
            "note": "以下为当前所选数据快照的待处理复核项；设备标记日期、采样日期与首次触发日期分别记录。演示挠度、疲劳、腐蚀和寿命不生成本列表预警。",
        }
    return {"version": "risk-details-v1", "snapshots": snapshots}
