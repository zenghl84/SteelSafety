"""The original monitoring dashboard, isolated from the steel model interface."""
from datetime import datetime
from html import escape
from pathlib import Path
import streamlit as st
from .monitoring_data import POINT_IDS, WORKBOOK_NAME, load_monitoring_data, format_value


def _workbook_path():
    # Use the user's workbook beside the project when available; otherwise the bundled copy.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / WORKBOOK_NAME
        if candidate.is_file():
            return candidate
    return Path(__file__).resolve().parent / "data" / WORKBOOK_NAME


@st.cache_data(show_spinner=False)
def read_workbook(path: str, modified_ns: int, size: int, schema_version: int):
    return load_monitoring_data(Path(path))


def render_dashboard():
    css = Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.container(key="aegis_dashboard"):
        _render_contents()


def _render_contents():
    workbook_path = _workbook_path()
    try:
        stat = workbook_path.stat()
        dataset = read_workbook(str(workbook_path), stat.st_mtime_ns, stat.st_size, 3)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"无法读取应用数据表：{exc}")
        return

    points = dataset["points"]
    latest_day = max(point["date"] for point in points.values())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(f"""
    <div class="hero">
      <div class="brand"><b>AEGIS-X</b><span class="brand-cn">｜大跨钢结构安全智能体</span></div>
      <div class="subtitle">结构应变监测 · 十测点数据看板 · 温度监测</div>
      <div class="hero-time">应用数据 · 历史快照<br>{now}</div>
    </div>
    """, unsafe_allow_html=True)
    missing = [point for point in POINT_IDS if point not in points]
    missing_text = "、".join(missing) if missing else "无"
    st.markdown(f"""
    <div class="realtime-strip">
      <span><i class="realtime-dot realtime-off"></i><b>最新检测日 / 真实应变中位数对应记录</b></span>
      <span>最新检测日期：<b>{latest_day:%Y-%m-%d}</b></span>
      <span>已有测点：<b>{len(points)} / {len(POINT_IDS)}</b></span>
      <span>历史记录：<b>{dataset['record_count']}</b> 条</span>
      <span>缺失测点：<b>{escape(missing_text)}</b></span>
      <span>数据源：{escape(workbook_path.name)}</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("各测点选取最新检测日真实应变最接近中位数的一次测量；同等接近时取较晚一次。三个数据项目均来自该次测量。")

    metrics = {
        "真实应变": ("corrected_strain", "corrected_strain_unit"),
        "温度": ("temperature", "temperature_unit"),
        "应变变化值": ("strain", "strain_unit"),
    }
    for row_start in (0, 5):
        cols = st.columns(5)
        for index, col in enumerate(cols, row_start):
            with col:
                point = POINT_IDS[index]
                metric = st.selectbox(
                    f"{point} 显示项目", list(metrics), index=0,
                    format_func=lambda name, point_id=point: f"{point_id}|{name}",
                    key=f"aegis_structural_metric_{point}",
                    label_visibility="collapsed",
                )
                selection = points.get(point)
                row = selection["record"] if selection else None
                if row is None:
                    missing_reason = (
                        f"{selection['date']:%Y-%m-%d} 无有效真实应变，无法选取记录"
                        if selection else "应用数据表未提供此测点"
                    )
                    st.markdown(f"""
    <div class="metric-card">
     <div class="m-label">{escape(point)} · {escape(metric)}</div>
     <div class="m-value">—</div>
     <div class="m-foot warn">暂无数据</div>
     <div class="m-foot" style="color:#7fa9bb">{escape(missing_reason)}</div>
    </div>
    """, unsafe_allow_html=True)
                    continue
                value_key, unit_key = metrics[metric]
                value = format_value(row[value_key])
                unit = row[unit_key] if row[value_key] is not None else ""
                detail = (
                    "该项目暂无数据" if row[value_key] is None
                    else "温度修正后应变" if metric == "真实应变"
                    else metric
                )
                st.markdown(f"""
    <div class="metric-card">
     <div class="m-label">{escape(point)} · {escape(metric)}</div>
     <div class="m-value">{value} {escape(unit)}</div>
     <div class="m-foot" style="color:#7fa9bb">{escape(detail)}</div>
     <div class="m-foot" style="color:#7fa9bb">{escape(row['location'])} · {escape(row['sensor_id'])}</div>
     <div class="m-foot" style="color:#7fa9bb">{row['timestamp']:%Y-%m-%d %H:%M:%S}</div>
    </div>
    """, unsafe_allow_html=True)
