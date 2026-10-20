"""Load optional local documents and fonts without requiring them in a clone."""
import base64
import json
from pathlib import Path
from urllib.parse import unquote


def font_styles(assets: Path) -> str:
    """Use locally installed font subsets when available, otherwise system fonts."""
    styles = []
    for name, weight in (("yahei-regular.ttf", "400"), ("yahei-bold.ttf", "700")):
        path = assets / name
        if path.is_file():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            styles.append(
                "@font-face{font-family:'Microsoft YaHei';font-weight:"
                + weight + ";src:url(data:font/ttf;base64," + data + ") format('truetype');}"
            )
    return "".join(styles)


def load_knowledge_catalog(root: Path) -> list[dict]:
    """Keep source metadata visible when an optional local original is absent."""
    catalog = json.loads((root / "static/knowledge/catalog.json").read_text(encoding="utf-8"))
    prefix = "/app/static/"
    for entry in catalog:
        url = entry.get("url", "")
        if url.startswith(prefix):
            local_path = root / "static" / unquote(url[len(prefix):])
            entry["available"] = local_path.is_file()
            if not entry["available"]:
                entry["availability_note"] = "本地原文尚未安装；添加对应文件后重新启动程序。"
    return catalog
