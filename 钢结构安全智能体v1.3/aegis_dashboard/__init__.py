"""Shared overview and a measured snapshot tab with recent monitoring curves."""
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui_fonts import FONT_FAMILY
from .monitoring_data import (
    POINT_IDS, WORKBOOK_NAME, load_monitoring_data, format_value,
    select_recent_records,
)


def _workbook_path():
    # Keep this release tied to its packaged monitoring data.
    bundled = Path(__file__).resolve().parent / "data" / WORKBOOK_NAME
    if bundled.is_file():
        return bundled
    for parent in Path(__file__).resolve().parents:
        candidate = parent / WORKBOOK_NAME
        if candidate.is_file():
            return candidate
    return bundled


@st.cache_data(show_spinner=False)
def read_workbook(path: str, modified_ns: int, size: int, schema_version: int):
    return load_monitoring_data(Path(path))


def render_overview():
    css = Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.container(key="aegis_dashboard"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"""
    <div class="hero">
      <div class="brand"><b>AEGIS-X</b><span class="brand-cn">｜大跨钢结构安全智能体</span></div>
      <div class="subtitle">结构应变监测 · 十测点数据看板 · 温度监测</div>
      <div class="hero-time">系统总览 · v1.3<br>{now}</div>
    </div>
    """, unsafe_allow_html=True)


def render_snapshot(model_figure):
    with st.container(key="aegis_snapshot"):
        _render_snapshot_contents(model_figure)


def _render_snapshot_contents(model_figure):
    workbook_path = _workbook_path()
    try:
        stat = workbook_path.stat()
        dataset = read_workbook(str(workbook_path), stat.st_mtime_ns, stat.st_size, 5)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"无法读取应用数据表：{exc}")
        return

    points = dataset["points"]
    latest_day = max(point["date"] for point in points.values())
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

    if dataset["calculated_record_count"]:
        st.caption(
            "温度修正沿用原公式：修正后应变 = 应变变化值 + 0.2 ×（温度 − 基准温度）；"
            "各测点沿用原基准温度，单位为 με。"
        )

    st.plotly_chart(
        model_figure, width="stretch", key="snapshot_model_view",
        config={"displaylogo": False},
    )
    _render_point_cards(points)
    st.divider()
    _render_monitoring_curves(dataset)


def _curve_figure(title, unit, start, latest):
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        height=340, margin=dict(l=12, r=12, t=70, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=12, family=FONT_FAMILY),
        hoverlabel=dict(font=dict(family=FONT_FAMILY)),
        legend=dict(orientation="h", y=1.12, x=0),
        xaxis=dict(
            title="监测时间", range=[start, latest], tickformat="%m-%d<br>%H:%M",
            gridcolor="rgba(148,163,184,0.16)",
        ),
        yaxis=dict(title=unit, gridcolor="rgba(148,163,184,0.16)"),
        hovermode="x unified",
    )
    return fig


def _render_monitoring_curves(dataset):
    st.subheader("监测曲线")
    point = st.selectbox("监测测点", POINT_IDS, key="aegis_history_point")
    records = select_recent_records(dataset["history"].get(point, []), days=3)
    if not records:
        st.info(f"{point} 暂无实测历史数据，无法显示最近三天监测曲线。")
        return

    latest = records[-1]["timestamp"]
    start = datetime.combine(
        latest.date() - timedelta(days=2), datetime.min.time()
    )
    st.caption(
        f"{point} · {start:%Y-%m-%d} 至 {latest:%Y-%m-%d} · "
        f"{len(records)} 条记录 · 最新记录 {latest:%Y-%m-%d %H:%M:%S}。"
        "范围按该测点最新记录日及前两天确定。"
    )
    strain, temperature = st.columns([2, 1])
    with strain:
        fig = _curve_figure(f"{point} 应变监测曲线", "应变 / με", start, latest)
        for field, label, color in (
            ("corrected_strain", "真实应变", "#67e8f9"),
            ("strain", "应变变化值", "#fbbf24"),
        ):
            if any(row[field] is not None for row in records):
                fig.add_trace(go.Scatter(
                    x=[row["timestamp"] for row in records],
                    y=[row[field] for row in records],
                    mode="lines+markers", name=label, connectgaps=False,
                    line=dict(color=color, width=2), marker=dict(size=4),
                    hovertemplate="%{x|%m-%d %H:%M}<br>%{y:.4f} με<extra>%{fullData.name}</extra>",
                ))
        if fig.data:
            st.plotly_chart(
                fig, width="stretch", key="aegis_strain_history",
                config={"displaylogo": False},
            )
        else:
            st.info("最近三天的应变数据为空。")
    with temperature:
        if any(row["temperature"] is not None for row in records):
            fig = _curve_figure(
                f"{point} 温度监测曲线", "温度 / ℃", start, latest
            )
            fig.add_trace(go.Scatter(
                x=[row["timestamp"] for row in records],
                y=[row["temperature"] for row in records],
                mode="lines+markers", name="温度", connectgaps=False,
                line=dict(color="#a78bfa", width=2), marker=dict(size=4),
                hovertemplate="%{x|%m-%d %H:%M}<br>%{y:.3f} ℃<extra></extra>",
            ))
            st.plotly_chart(
                fig, width="stretch", key="aegis_temperature_history",
                config={"displaylogo": False},
            )
        else:
            st.info("最近三天的温度数据为空。")
    with st.expander("最近三天监测明细", expanded=False):
        detail = pd.DataFrame([{
            "时间": row["timestamp"],
            "真实应变 / με": row["corrected_strain"],
            "应变变化值 / με": row["strain"],
            "温度 / ℃": row["temperature"],
            "基准温度 / ℃": row["reference_temperature"],
            "修正来源": "按原公式计算" if row["correction_source"] == "calculated" else "数据表",
            "位置": row["location"],
            "传感器编号": row["sensor_id"],
        } for row in records])
        st.dataframe(detail, hide_index=True, width="stretch")


def _render_point_cards(points):
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
