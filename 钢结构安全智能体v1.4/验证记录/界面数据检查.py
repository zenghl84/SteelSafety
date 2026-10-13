"""Run from the v1.3 folder with the application's Python environment."""
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import json
import re
import warnings

import openpyxl
from streamlit.testing.v1 import AppTest

from ui_fonts import FONT_FAMILY

warnings.filterwarnings("ignore", message="Workbook contains no default style")
ROOT = Path(__file__).resolve().parents[1]
POINTS = tuple(f"S{i}" for i in range(1, 11))
baseline_report = json.loads((ROOT / "验证记录/原温度修正公式核对.json").read_text(encoding="utf-8"))
expected = {}
workbook = openpyxl.load_workbook(
    ROOT / "aegis_dashboard/data/商洛煤棚监测_应用数据.xlsx", read_only=True, data_only=True
)
for sheet in workbook:
    values = list(sheet.values)
    baseline = Decimal(str(baseline_report["points"][sheet.title]["reference_temperature_c"]))
    rows = []
    for values_row in values[1:]:
        row = dict(zip(values[0], values_row))
        rows.append({
            "time": datetime.fromisoformat(row["时间"]),
            "raw": float(row["应变变化值"]),
            "temperature": float(row["温度"]),
            "corrected": float(Decimal(row["应变变化值"]) + Decimal("0.2") * (Decimal(row["温度"]) - baseline)),
            "baseline": float(baseline),
        })
    expected[sheet.title] = sorted(rows, key=lambda row: row["time"])
workbook.close()

app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
assert not app.exception and not app.error
assert [tab.label for tab in app.tabs] == ["实测快照", "三维孪生", "安全预测与预警", "现场安全助手"]
assert [(metric.label, metric.value) for metric in app.metric] == [
    ("模型节点", "3102"), ("当前可见单元", "11919"), ("施工阶段", "17"),
    ("安全评估", "待评估"), ("计划内最大 |Δσ| / MPa", "1.3193"),
]
markdown = "\n".join(element.value for element in app.markdown)
assert "系统总览 · v1.3" in markdown
assert "2026-10-12" in markdown and "2322" in markdown
assert "商洛煤棚监测_应用数据.xlsx" in markdown
assert not any(header.value == "实测快照" for header in app.header)
assert not any(header.value == "实测快照" for header in app.subheader)
assert app.selectbox(key="aegis_history_point").options == list(POINTS)
assert "模型资料" in [expander.label for expander in app.sidebar.expander]
cards = [element.value for element in app.markdown if 'class="metric-card"' in element.value]
assert len(cards) == 10
for point in POINTS:
    assert app.selectbox(key=f"aegis_structural_metric_{point}").value == "真实应变"
    card = next(card for card in cards if f"{point} · 真实应变" in card)
    if point == "S4":
        assert "暂无数据" in card and "应用数据表未提供此测点" in card
    else:
        number = f"{expected[point][-1]['corrected']:.4f}".rstrip("0").rstrip(".")
        assert f'<div class="m-value">{number} με</div>' in card
        assert "2026-10-12 00:17:26" in card


def charts():
    return {element.proto.id.rsplit("-", 1)[-1]: json.loads(element.proto.spec)
            for element in app.get("plotly_chart")}


def model_views():
    scenes = {}
    for element in app.get("iframe"):
        html = element.proto.srcdoc
        key = re.search(r'data-view-key="([^"]+)"', html)
        if key:
            payload = html.split('<script id="steel-scene-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            scenes[key.group(1)] = json.loads(payload)
    return scenes


initial = charts()
initial_models = model_views()
assert initial_models["snapshot_model_view"] == initial_models["model_view"]
assert len(initial_models["model_view"]["members"]) == 11919
assert len(initial_models["model_view"]["sensors"]) == 9
report = {
    "tabs": [tab.label for tab in app.tabs],
    "default_cards": 10, "default_metric": "真实应变", "missing_point": "S4",
    "overview_version": "v1.3", "default_prediction_peak_mpa": 1.3193,
    "snapshot_and_twin_model_identical": True, "points": {},
}
for point in expected:
    app.selectbox(key="aegis_history_point").select(point).run()
    assert not app.exception and not app.error
    latest = expected[point][-1]["time"]
    start = datetime.combine(latest.date() - timedelta(days=2), datetime.min.time())
    recent = [row for row in expected[point] if start <= row["time"] <= latest]
    figures = charts()
    models = model_views()
    assert models["snapshot_model_view"] == models["model_view"]
    strain = figures["aegis_strain_history"]
    temperature = figures["aegis_temperature_history"]
    assert strain["layout"]["title"]["text"] == f"{point} 应变监测曲线"
    assert strain["layout"]["font"]["family"] == FONT_FAMILY
    assert temperature["layout"]["font"]["family"] == FONT_FAMILY
    assert [trace["name"] for trace in strain["data"]] == ["真实应变", "应变变化值"]
    for trace, field in ((strain["data"][0], "corrected"), (strain["data"][1], "raw"),
                         (temperature["data"][0], "temperature")):
        assert [datetime.fromisoformat(value) for value in trace["x"]] == [row["time"] for row in recent]
        assert trace["y"] == [row[field] for row in recent]
        assert len(trace["y"]) == 49
    detail = next(frame.value for frame in app.dataframe if "真实应变 / με" in frame.value.columns)
    assert detail["真实应变 / με"].tolist() == [row["corrected"] for row in recent]
    assert detail["基准温度 / ℃"].tolist() == [row["baseline"] for row in recent]
    assert set(detail["修正来源"]) == {"按原公式计算"}
    report["points"][point] = {"all_three_curves_match": True, "records_per_curve": 49, "details_match": True}

app.selectbox(key="aegis_structural_metric_S1").select("温度").run()
assert not app.exception
assert any('S1 · 温度' in m.value and '<div class="m-value">13.921 ℃</div>' in m.value for m in app.markdown)
app.selectbox(key="aegis_structural_metric_S1").select("应变变化值").run()
assert not app.exception
assert any('S1 · 应变变化值' in m.value and '<div class="m-value">-2570.145 με</div>' in m.value for m in app.markdown)
app.selectbox(key="aegis_structural_metric_S1").select("真实应变")
app.selectbox(key="aegis_history_point").select("S4").run()
assert not app.exception and not app.error
assert any("S4 暂无实测历史数据" in element.value for element in app.info)
assert "aegis_strain_history" not in charts() and "aegis_temperature_history" not in charts()
report.update({"card_metric_switching_checked": True, "S4_curves_show_missing_message": True, "exceptions": []})
(ROOT / "验证记录/界面数据检查.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
