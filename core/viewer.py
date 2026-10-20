"""Offline solid-steel viewer for the measured snapshot and digital twin only."""
from functools import lru_cache
from html import escape
import json
import math
from pathlib import Path
import re

import streamlit as st


ASSETS = Path(__file__).resolve().parents[1] / "assets" / "viewer"
HIDDEN_MATERIAL = "MAT-WIRE16-FC"


def hidden_material_ids(model):
    return {mid for mid, name in model["materials"].items()
            if name.strip().upper().replace("_", "-") == HIDDEN_MATERIAL}


@st.cache_data(show_spinner=False)
def pipe_sections(raw):
    """Read numerical circular-section dimensions from MGT in metres.

    Only explicit DBUSER/USER dimensions are accepted. Unsupported sections
    remain centre lines; a section label never substitutes for dimension data.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")
    blocks, key, pending = {}, "", ""
    for original in text.splitlines():
        line = original.split(";")[0].strip()
        if not line:
            continue
        if line.startswith("*"):
            key = line.split(",")[0].strip()
            blocks.setdefault(key, [])
            continue
        pending += line.rstrip("\\").strip() + " "
        if line.endswith("\\"):
            continue
        blocks.setdefault(key, []).append(pending.strip())
        pending = ""
    units = [part.strip() for part in blocks["*UNIT"][0].split(",")]
    scale = {"MM": .001, "CM": .01, "M": 1.}[units[1].upper()]
    sections = {}
    for row in blocks.get("*SECTION", []):
        parts = [part.strip() for part in row.split(",")]
        if len(parts) < 16 or parts[1] != "DBUSER" or parts[12] not in ("P", "SR") or parts[13] != "2":
            continue
        try:
            diameter = float(parts[14]) * scale
            wall = float(parts[15]) * scale if parts[12] == "P" else None
            if not math.isfinite(diameter) or diameter <= 0:
                continue
            if wall is not None and (not math.isfinite(wall) or not 0 < wall < diameter / 2):
                continue
            sections[int(parts[0])] = {"diameter_m": diameter, "wall_m": wall,
                                         "shape": "pipe" if wall is not None else "solid"}
        except ValueError:
            continue
    return sections


def build_scene(raw, model, visible, colorby, points, labels, details, selected,
                show_sensors, model_id, diameter_scale=2.0, show_joints=True):
    hidden = hidden_material_ids(model)
    members = [e for e in visible if e["material"] not in hidden]
    node_ids = sorted({e[n] for e in members for n in ("n1", "n2")})
    section_ids = sorted({e["section"] for e in members})
    dimensions = pipe_sections(raw)
    sections = {sid: {"name": model["sections"].get(sid, str(sid)), **dimensions.get(sid, {})}
                for sid in section_ids}
    ids = {e["id"] for e in members}
    return {
        "version": 1,
        "model_id": model_id,
        "nodes": {nid: model["nodes"][nid] for nid in node_ids},
        "members": [[e["id"], e["n1"], e["n2"], e["material"], e["section"], e["type"]]
                    for e in members],
        "sections": sections,
        "materials": {mid: model["materials"].get(mid, str(mid))
                      for mid in sorted({e["material"] for e in members})},
        "sensors": [{"position": point, "label": label, "detail": detail}
                    for point, label, detail in zip(points, labels, details)] if show_sensors else [],
        "selected": int(selected) if selected in ids else 0,
        "unsupported_members": sum(e["section"] not in dimensions for e in members),
        "options": {"colorby": colorby, "diameter_scale": float(diameter_scale),
                    "show_joints": bool(show_joints)},
    }


def script_json(value):
    """Prevent model/upload text from terminating an inline script tag."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "&", "\\u0026").replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


@lru_cache(maxsize=2)
def _bundles(stamp):
    return {name: (ASSETS / name).read_text(encoding="utf-8") for name in (
        "three.core.js", "three.module.js", "OrbitControls.js", "RoomEnvironment.js", "SiteEnvironment.js")}


def viewer_html(scene, key):
    files = [ASSETS / name for name in ("three.core.js", "three.module.js", "OrbitControls.js", "RoomEnvironment.js", "SiteEnvironment.js")]
    bundles = _bundles(tuple(path.stat().st_mtime_ns for path in files))
    template = (ASSETS / "viewer.html").read_text(encoding="utf-8")
    runtime = (ASSETS / "viewer.js").read_text(encoding="utf-8")
    values = {"__VIEW_KEY__": escape(key, quote=True), "__SCENE_DATA__": script_json(scene),
              "__BUNDLED_MODULES__": script_json(bundles), "__VIEWER_RUNTIME__": runtime}
    return re.sub(r"__(?:VIEW_KEY|SCENE_DATA|BUNDLED_MODULES|VIEWER_RUNTIME)__",
                  lambda match: values[match.group()], template)
