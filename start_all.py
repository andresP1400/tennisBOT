"""Launcher script for tennisBOT (backend + frontend)."""

import logging
import os
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("start_all")


def start_servers() -> None:
    log.info("=" * 36)
    log.info(" Avvio del TennisBot Ecosystem...")
    log.info("=" * 36)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base_dir, "backend", "src")
    web_dir = os.path.join(base_dir, "frontend")
    api_port = os.environ.get("TENNISBOT_API_PORT", "9090")
    log.info("Avviando API Server (FastAPI) su porta %s...", api_port)
    api_env = os.environ.copy()
    api_env["TENNISBOT_API_PORT"] = api_port
    api_process = subprocess.Popen(
        [sys.executable, "api_server.py"],
        cwd=src_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=api_env,
    )
    time.sleep(2)
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    log.info("Avviando Web UI (Next.js) su porta 3000...")
    web_env = os.environ.copy()
    web_env["BACKEND_URL"] = f"http://localhost:{api_port}"
    web_env["NEXT_PUBLIC_API_URL"] = f"http://localhost:{api_port}"
    web_process = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=web_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=web_env,
    )
    try:
        log.info("Tutto avviato con successo!")
        log.info("Accedi alla Web UI qui: http://localhost:3000")
        log.info("FastAPI Server gira qui: http://localhost:%s", api_port)
        log.info("API Docs: http://localhost:%s/docs", api_port)
        log.info("Premere Ctrl+C per fermare tutti i server.")
        api_process.wait()
        web_process.wait()
    except KeyboardInterrupt:
        log.info("Spegnimento servers...")
        api_process.terminate()
        web_process.terminate()
        sys.exit(0)


if __name__ == "__main__":
    start_servers()
