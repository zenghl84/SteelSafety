"""Traceable KPI cards with computed evidence and explicitly separate demo assumptions."""
import copy
import json
from math import isfinite
from pathlib import Path

MATERIAL = {
    "title": "GB 55006—2021 第 3.0.3 条及条文说明表 2",
    "url": "https://gf.cabr-fire.com/m/article-39049.htm",
    "role": "材料强度设计值依据；不提供本项目统一监测报警阈值。",
}
MONITORING = {
    "title": "GB 50982—2014 第 3.4.5、3.4.7 条",
    "url": "https://gf.cabr-fire.com/m/article-55822.htm",
    "role": "监测限值结合工程条件确定；异常应检查。复核项计数是本平台规则。",
}
DEFLECTION = {
    "title": "GB 50017—2017 附录 B.1",
    "url": "https://gf.cabr-fire.com/m/article-34710.htm",
    "role": "挠度容许值的参考；不提供本项目实测挠度，未据此判定示例合格。",
}
FATIGUE = {
    "title": "GB 50017—2017 第 16.2 节及 16.2.3 条文说明",
    "url": "https://gf.cabr-fire.com/m/article-34694.htm",
    "role": "应力谱、连接类别和 S-N 参数；条文说明介绍 Miner 累积损伤。",
}
DURABILITY = {
    "title": "GB 55006—2021 第 2.0.1、2.0.4 条",
    "url": "https://gf.cabr-fire.com/m/article-39044.htm",
    "role": "设计工作年限与防腐维护原则；不提供本平台演示腐蚀分级和剩余寿命数值。",
}


def indicator(key, label, value=None, unit="", precision=1, **details):
    return {
        "id": key, "label": label, "value": value, "unit": unit,
        "precision": precision, "kind": "missing", "badge": "待评估",
        "tone": "muted", "source": "", "calculation": "", "note": "",
        "required": "", "references": [], **details,
    }


def observed_indicators(snapshot):
    valid = [r for r in snapshot["rows"]
             if r["score"] is not None and r["ratio"] is not None]
    maximum = max(valid, key=lambda r: r["ratio"], default=None)
    stress = indicator(
        "stress", "最大应力利用系数", precision=3,
        references=[MATERIAL],
        source=snapshot["label"] + "；data/assessment_config.json 与对应应力增量。",
        note="此处是有效测点材料应力比，不是全结构包络或含受压稳定、连接的规范验算利用系数。S1 损坏，已排除。",
        required="完整承载力利用系数需设计荷载组合、稳定与连接验算。",
    )
    if maximum:
        stress.update(
            value=maximum["ratio"], kind="computed", badge="有效点计算",
            tone=maximum["tone"],
            calculation=f"max(|σ|/f)；控制点 {maximum['sensor_id']}，E{maximum['element']} / {maximum['end']}："
                        f"|{maximum['total_mpa']:.4f}| / {maximum['reference_mpa']:g} = {maximum['ratio']:.6f}。",
        )
    else:
        stress["calculation"] = "没有可用的有效测点，未设置为 0。"
    risk_items = []
    for row in snapshot["rows"]:
        if row["tone"] == "fault":
            risk_items.append({"sensor_id": row["sensor_id"], "type": "设备故障",
                               "detail": "传感器损坏（用户标记）"})
        elif row["score"] is None:
            risk_items.append({"sensor_id": row["sensor_id"], "type": "数据缺测",
                               "detail": row.get("reason", "无有效数据")})
        elif row["tone"] in ("attention", "warning", "danger"):
            risk_items.append({"sensor_id": row["sensor_id"], "type": "应力复核",
                               "detail": f"{row['status']}，应力比 {100 * row['ratio']:.2f}%"})
    risk = indicator(
        "risk", "关键风险源", len(risk_items), "项", 0,
        kind="computed", badge="待复核项", tone="attention" if risk_items else "normal",
        source=snapshot["label"] + "；设备状态来自用户记录，应力等级来自现有评分规则。",
        calculation="每个故障、缺测或触发应力关注规则的测点计 1 项，同一点不重复。",
        note="此数量是待复核条目数，不是已确认的结构损伤处数。",
        references=[MONITORING], risk_items=risk_items,
    )
    return [
        stress,
        indicator("deflection", "最大挠度", unit="mm", precision=1,
                  source="现有 data 目录只有应力结果与应变工作簿，未接入节点位移/挠度结果。",
                  required="同工况节点竖向位移、支座参考及测量基准；应变不能直接替代全结构挠度。",
                  references=[DEFLECTION]),
        indicator("fatigue", "疲劳损伤指标", precision=3,
                  source="现有单次应力表及低频监测记录未建立项目疲劳应力谱。",
                  required="足够采样的应力历史、连接细节类别、S-N 曲线参数及累计循环次数。",
                  references=[FATIGUE]),
        indicator("corrosion", "腐蚀等级", unit="级", precision=0,
                  source="未提供本项目腐蚀检测或实测剩余壁厚报告。",
                  required="现场测厚、原始壁厚、涂层/锈蚀检查及适用的评定规则。",
                  references=[DURABILITY]),
        indicator("life", "剩余寿命", unit="年", precision=0,
                  source="未提供项目使用年限、完整服役历史及寿命评估结果。",
                  required="设计与投用档案、现状检测、荷载与退化预测及专业寿命评估。",
                  references=[DURABILITY]),
        risk,
    ]


def positive(value, name, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"演示参数 {name} 必须为有限数值")
    if value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"演示参数 {name} 超出有效范围")
    return value


def demonstration_indicators(observed, scenario):
    rows = copy.deepcopy(observed)
    by_id = {r["id"]: r for r in rows}
    d = scenario["deflection"]
    displacements = d["node_displacements_mm"]
    if not displacements or not all(isinstance(v, (int, float)) and isfinite(v) for v in displacements):
        raise ValueError("演示节点位移无效")
    reference = float(d["reference_displacement_mm"])
    if not isfinite(reference):
        raise ValueError("演示位移参考值无效")
    by_id["deflection"].update(
        value=max(abs(v-reference) for v in displacements), kind="demo",
        badge="演示值", tone="demo", source="本次演示场景假设，data/key_indicators_config.json。",
        calculation=f"虚拟节点竖向位移 {displacements} mm，参考值 {reference:g} mm；取相对位移绝对值最大值。",
        note=d["note"] + " 18.6 mm 不是规范给出的值，也不是模型求解结果。",
    )
    f = scenario["fatigue"]
    cycles = positive(f["cycles"], "已循环次数", allow_zero=True)
    capacity = positive(f["assumed_cycles_to_failure"], "假设容许循环次数")
    by_id["fatigue"].update(
        value=cycles/capacity, kind="demo", badge="演示值", tone="demo",
        source="本次单级循环演示场景假设，未从监测应力谱计算。",
        calculation=f"D = Σ(nᵢ/Nᵢ)；此示例取 n={cycles:g}、N={capacity:g}，D={cycles/capacity:.3f}。",
        note=f["note"] + " n、N 和 D 均非规范给定的项目数值。",
    )
    c = scenario["corrosion"]
    original = positive(c["initial_thickness_mm"], "原始壁厚")
    remaining = positive(c["remaining_thickness_mm"], "假设剩余壁厚", allow_zero=True)
    if remaining > original:
        raise ValueError("演示剩余壁厚不能大于原始壁厚")
    loss = (original-remaining)/original
    limits = c["display_grade_limits"]
    if len(limits) != 3 or sorted(limits) != limits or not all(0 < v < 1 for v in limits):
        raise ValueError("演示腐蚀分级边界无效")
    grade = 1 + sum(loss > limit + 1e-12 for limit in limits)
    by_id["corrosion"].update(
        value=grade, kind="demo", badge="演示分级", tone="demo",
        source="本平台演示分级及假设测厚，非现场检测结论。",
        calculation=f"假设原始壁厚 {original:g} mm、剩余 {remaining:g} mm；厚度损失率={loss*100:.2f}%，演示映射为 {grade} 级。",
        note=c["note"],
    )
    life = scenario["life"]
    design = positive(life["assumed_design_years"], "假设设计年限")
    elapsed = positive(life["assumed_elapsed_years"], "假设已使用年限", allow_zero=True)
    if elapsed > design:
        raise ValueError("演示已使用年限不能超过假设设计年限")
    by_id["life"].update(
        value=design-elapsed, kind="demo", badge="演示余量", tone="demo",
        source="本次演示假设：计划年限 50 年、已使用 10 年。",
        calculation=f"演示计划余量={design:g}−{elapsed:g}={design-elapsed:g} 年。",
        note=life["note"] + " 此值仅是计划年限差，不代表耐久或疲劳剩余寿命。",
    )
    return rows


def build_key_indicators(project_dir: Path, assessment):
    config = json.loads((project_dir / "data/key_indicators_config.json").read_text(encoding="utf-8"))
    modes = {}
    for key, snapshot in assessment["snapshots"].items():
        actual = observed_indicators(snapshot)
        modes[key] = {
            "observed": actual,
            "demo": demonstration_indicators(actual, config["scenario"]),
        }
    return {
        "version": config["version"], "default_mode": config["default_mode"],
        "authorization": config["demo_authorization"], "by_source": modes,
        "mode_note": "应力比和复核项按当前评分源计算；其余4项在演示模式中是假设参数，不参与健康评分。",
    }


def source_markdown(bundle, source="confirmed", mode="demo"):
    lines = ["# v1.8 关键指标设置与来源", "",
             "演示参数由用户选择启用。应力与复核项按现有数据计算；其余 4 项为显式演示假设，不参与 82.4 分的计算。", ""]
    for row in bundle["by_source"][source][mode]:
        value = "待评估" if row["value"] is None else f"{row['value']:.{row['precision']}f}{row['unit']}"
        lines += [f"## {row['label']}：{value}", "", f"- 类型：{row['badge']}。",
                  f"- 数据来源：{row['source']}", f"- 计算：{row['calculation'] or '缺少数据，未计算。'}",
                  f"- 说明：{row['note']}", f"- 正式评估需补充：{row['required'] or '按项目监测方案核定。'}"]
        for item in row.get("risk_items", []):
            lines.append(f"- 复核项：{item['sensor_id']} · {item['type']} · {item['detail']}。")
        for ref in row["references"]:
            lines.append(f"- 参考方法/原则：[{ref['title']}]({ref['url']})。{ref['role']}")
        lines.append("")
    return "\n".join(lines)
