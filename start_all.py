"""Launcher script for tennisBOT (backend + frontend)."""
import os
import subprocess
import sys
import time


def start_servers() -> None:
    print("====================================")
    print(" Avvio del TennisBot Ecosystem...")
    print("====================================")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(base_dir, "web")
    api_port = os.environ.get("TENNISBOT_API_PORT", "9090")
    print(f"=> Avviando API Server (FastAPI) su porta {api_port}...")
    api_env = os.environ.copy()
    api_env["TENNISBOT_API_PORT"] = api_port
    api_process = subprocess.Popen(
        [sys.executable, "api_server.py"],
        cwd=base_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=api_env,
    )
    time.sleep(2)
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    print("=> Avviando Web UI (Next.js) su porta 3000...")
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
        print("\n Tutto avviato con successo!")
        print(" Accedi alla Web UI qui: http://localhost:3000")
        print(f" FastAPI Server gira qui: http://localhost:{api_port}")
        print(f" API Docs: http://localhost:{api_port}/docs")
        print("\nPremere Ctrl+C per fermare tutti i server.\n")
        api_process.wait()
        web_process.wait()
    except KeyboardInterrupt:
        print("\n Spegnimento servers...")
        api_process.terminate()
        web_process.terminate()
        sys.exit(0)


if __name__ == "__main__":
    start_servers()
