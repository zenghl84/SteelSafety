"""Shared white-background colours for application text and Plotly charts."""
from pathlib import Path

BACKGROUND = "#ffffff"
TEXT = "#172b4d"
MUTED = "#52657f"
BORDER = "#dbe4ee"
GRID = "#e6ecf2"
ACCENT = "#176ac4"
STEEL = "#36546e"


def apply_ui_theme():
    import streamlit as st
    css = Path(__file__).with_name("ui_theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def apply_chart_theme(figure):
    figure.update_layout(
        template="plotly_white", paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font_color=TEXT,
        hoverlabel=dict(bgcolor=BACKGROUND, bordercolor=BORDER, font_color=TEXT),
    )
    return figure


def scene_axis(title):
    return dict(title=title, color=TEXT, gridcolor=GRID,
                zerolinecolor=BORDER, showbackground=False)
