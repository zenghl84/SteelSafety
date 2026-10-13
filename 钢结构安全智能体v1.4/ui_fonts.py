"""Shared fonts for interface text and chart labels."""
from pathlib import Path


# The CSS font uses Times New Roman for Latin ranges and YaHei for Chinese.
FONT_FAMILY = "Steel Interface, Times New Roman, Microsoft YaHei, serif"


def apply_ui_fonts():
    import streamlit as st

    css = Path(__file__).with_name("ui_fonts.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
