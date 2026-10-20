"""Streamlit entry point for the SteelSafety v1.8 dashboard."""
from pathlib import Path

import streamlit as st

from core.home import build_homepage


st.set_page_config(
    page_title="钢结构安全性能评估智能体平台",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown("""<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f5f9fd;margin:0;overflow:hidden}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],footer{display:none!important}
[data-testid="stMainBlockContainer"]{padding:0!important;margin:0!important;max-width:none!important;min-width:0!important;width:100%!important}
[data-testid="stVerticalBlock"]{gap:0!important}
[data-testid="stElementContainer"]:has(iframe){width:100%!important;margin:0!important;padding:0!important}
iframe{display:block;border:0;width:100%!important}
[data-testid="stElementContainer"]:has(iframe),[data-testid="stElementContainer"]:has(iframe)>div{height:100dvh!important}
[data-testid="stElementContainer"] iframe{height:100dvh!important}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def page(stamps):
    """Invalidate the assembled page when code, data or optional resources change."""
    return build_homepage()


root = Path(__file__).resolve().parent
files = []
for directory in ("core", "data", "assets/home", "assets/viewer", "static/knowledge"):
    files.extend(path for path in (root / directory).glob("*") if path.is_file())
stamps = tuple((str(path), path.stat().st_mtime_ns) for path in sorted(files))
st.iframe(page(stamps), height=941)
