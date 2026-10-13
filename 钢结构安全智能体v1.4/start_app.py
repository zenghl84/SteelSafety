"""Start the local dashboard and open the browser after the server is ready."""
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


ROOT = Path(__file__).resolve().parent


def available_port():
    for port in range(8501, 8521):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("8501 至 8520 端口均被占用，请关闭旧的程序窗口后重试。")


def main():
    port = available_port()
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
