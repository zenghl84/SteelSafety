"""Start the local dashboard and open the browser after the server is ready."""
import argparse
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


ROOT = Path(__file__).resolve().parent


def check_environment():
    """Report missing dependencies and entry resources before starting a server."""
    if sys.version_info < (3, 10):
        raise RuntimeError("需要 Python 3.10 或更高版本，推荐 Python 3.12。")
    versions = {}
    for name in ("streamlit", "pandas", "openpyxl"):
        try:
            module = import_module(name)
            versions[name] = version(name)
        except (ImportError, OSError) as error:
            raise RuntimeError(
                f"无法加载 {name}；请先运行 python -m pip install -r requirements.txt。"
            ) from error
        if name == "streamlit" and not callable(getattr(module, "iframe", None)):
            raise RuntimeError("Streamlit 版本不兼容，请按 requirements.txt 安装依赖。")
    required = (
        "app.py", "VERSION", ".streamlit/config.toml", "core/home.py", "core/resources.py",
        "assets/home/index.html", "assets/viewer/viewer.html", "data/model.mgt",
        "data/sensor_mapping.csv", "data/stress_cs19.json", "data/assessment_config.json",
        "data/key_indicators_config.json", "data/商洛煤棚监测_应用数据.xlsx",
        "static/knowledge/catalog.json",
    )
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError("项目文件不完整：" + "、".join(missing))
    return versions


def port_number(value):
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("端口必须在 1 至 65535 之间。")
    return port


def available_port(preferred=None):
    for port in ([preferred] if preferred is not None else range(8501, 8521)):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    if preferred is not None:
        raise RuntimeError(f"端口 {preferred} 不可用，请选择其他端口。")
    raise RuntimeError("8501 至 8520 端口均不可用，请关闭旧的程序窗口后重试。")


def main(argv=None):
    parser = argparse.ArgumentParser(description="启动 SteelSafety 钢结构安全智能体 v1.8")
    parser.add_argument("--check", action="store_true", help="检查依赖与入口资源后退出")
    parser.add_argument("--no-browser", action="store_true", help="启动服务但不自动打开浏览器")
    parser.add_argument("--port", type=port_number, help="指定端口，默认从 8501 至 8520 选择")
    args = parser.parse_args(argv)
    versions = check_environment()
    if args.check:
        print("环境检查通过：" + ", ".join(f"{name} {value}" for name, value in versions.items()))
        print(f"项目目录：{ROOT}")
        return 0
    port = available_port(args.port)
    url = f"http://127.0.0.1:{port}"
    log_path = ROOT / ".logs" / "streamlit.log"
    log_path.parent.mkdir(exist_ok=True)
    opener = build_opener(ProxyHandler({}))
    command = [
        sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
        "--server.address", "127.0.0.1", "--server.port", str(port),
        "--server.headless", "true",
    ]
    print("正在启动大跨钢结构安全智能体……", flush=True)
    print(f"运行日志：{log_path}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError("服务启动失败，请查看运行日志。")
                try:
                    with opener.open(url + "/_stcore/health", timeout=2) as response:
                        ready = response.status == 200
                except (URLError, OSError):
                    ready = False
                if ready:
                    print(f"程序已启动：{url}", flush=True)
                    print("请保留此窗口；关闭窗口或按 Ctrl+C 可停止程序。", flush=True)
                    if not args.no_browser:
                        webbrowser.open(url)
                    return server.wait()
                time.sleep(0.5)
            raise RuntimeError("服务启动超时，请查看运行日志。")
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("程序已停止。")
    except (OSError, RuntimeError) as error:
        print(f"启动失败：{error}", file=sys.stderr)
        sys.exit(1)
