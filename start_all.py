"""Private launcher with readiness checks, child supervision, and clean shutdown."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from types import FrameType
from urllib.error import URLError
from urllib.request import urlopen

log = logging.getLogger("start_all")
ROOT = Path(__file__).resolve().parent


def check_ports() -> None:
    """Never reuse or terminate an unrelated process occupying an application port."""
    for port in (9090, 3000):
        with socket.socket() as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(
                    f"Port {port} is occupied; stop your existing instance first"
                )


def prepare_frontend(production: bool) -> list[str]:
    """Standalone deployments need their static assets beside the generated server."""
    web = ROOT / "frontend"
    if not production:
        return [
            "npm.cmd" if os.name == "nt" else "npm",
            "run",
            "dev",
            "--",
            "--hostname",
            "127.0.0.1",
        ]
    standalone = web / ".next" / "standalone"
    if (
        not (standalone / "server.js").is_file()
        or not (web / ".next" / "static").is_dir()
    ):
        raise RuntimeError(
            "Missing production build; run npm ci and npm run build in frontend first"
        )
    for source, destination in (
        (web / "public", standalone / "public"),
        (web / ".next" / "static", standalone / ".next" / "static"),
    ):
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
    return ["node", str(standalone / "server.js")]


def wait_ready(process: subprocess.Popen[bytes], url: str, timeout: float = 60) -> None:
    """An open port alone does not establish a usable backend or dashboard."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Service exited with code {process.returncode} before readiness"
            )
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Service did not become ready within {timeout:g} seconds")


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate only the launched service group, including development subprocesses."""
    if os.name == "nt" and process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def supervise(processes: list[subprocess.Popen[bytes]]) -> None:
    """A frontend crash must stop the sibling backend rather than claim success."""
    while True:
        for process in processes:
            result = process.poll()
            if result is not None:
                raise RuntimeError(
                    f"Application service {process.pid} exited with code {result}"
                )
        time.sleep(0.5)


def service_commands(frontend_command: list[str]) -> list[tuple[list[str], Path, str]]:
    """Both build-time proxy routing and private service ports must agree."""
    return [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api_server:app",
                "--app-dir",
                "backend/src",
                "--host",
                "127.0.0.1",
                "--port",
                "9090",
            ],
            ROOT,
            "http://127.0.0.1:9090/api/health",
        ),
        (frontend_command, ROOT / "frontend", "http://127.0.0.1:3000/dashboard"),
    ]


def start_servers(production: bool = False) -> None:
    """Keep the poller alive until interrupted; preserve all data when stopping."""
    if os.environ.get("TENNISBOT_API_PORT", "9090") != "9090":
        raise RuntimeError(
            "This launcher uses backend port 9090 to match the dashboard build"
        )
    check_ports()
    commands = service_commands(prepare_frontend(production))
    environment = os.environ.copy()
    environment.update(HOSTNAME="127.0.0.1", PORT="3000", TENNISBOT_API_PORT="9090")
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command, directory, url in commands:
            process = subprocess.Popen(
                command,
                cwd=directory,
                env=environment,
                start_new_session=os.name != "nt",
            )
            processes.append(process)
            wait_ready(process, url)
        log.info("Dashboard ready on this machine at http://127.0.0.1:3000/dashboard")
        log.info(
            "Leave this terminal running for prediction polling and automatic settlement"
        )
        supervise(processes)
    finally:
        for process in reversed(processes):
            stop_process(process)


def request_stop(signum: int, frame: FrameType | None) -> None:
    """SIGTERM and Ctrl-C both run child cleanup."""
    raise KeyboardInterrupt


def main() -> int:
    """The production flag uses the already built standalone dashboard."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    signal.signal(signal.SIGTERM, request_stop)
    try:
        start_servers(arguments.production)
    except KeyboardInterrupt:
        log.info("TennisBOT stopped; recorded predictions and outcomes are retained")
    except (OSError, RuntimeError) as error:
        log.error("Startup/runtime failure: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
