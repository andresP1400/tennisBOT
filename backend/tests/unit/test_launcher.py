"""Launcher failures must never leave a silently half-running application."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

_specification = importlib.util.spec_from_file_location(
    "start_all", Path(__file__).resolve().parents[3] / "start_all.py"
)
assert _specification is not None and _specification.loader is not None
launcher = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(launcher)


def test_missing_production_build_fails_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="Missing production build"):
        launcher.prepare_frontend(True)


def test_standalone_preparation_includes_assets_and_binds_development_privately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    web = tmp_path / "frontend"
    (web / ".next/standalone").mkdir(parents=True)
    (web / ".next/standalone/server.js").write_text("// fixture")
    (web / ".next/static").mkdir()
    (web / ".next/static/test.js").write_text("// fixture")
    (web / "public").mkdir()
    (web / "public/test.svg").write_text("<svg/>")
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    assert launcher.prepare_frontend(True)[0] == "node"
    assert (web / ".next/standalone/.next/static/test.js").is_file()
    assert (web / ".next/standalone/public/test.svg").is_file()
    assert launcher.prepare_frontend(False)[-2:] == ["--hostname", "127.0.0.1"]


def test_exited_child_fails_readiness_immediately() -> None:
    child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])
    child.wait(timeout=5)
    with pytest.raises(RuntimeError, match="code 7"):
        launcher.wait_ready(child, "http://127.0.0.1:1", timeout=1)


def test_frontend_startup_failure_cleans_up_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )
    monkeypatch.delenv("TENNISBOT_API_PORT", raising=False)
    monkeypatch.setattr(launcher, "check_ports", lambda: None)
    monkeypatch.setattr(
        launcher, "prepare_frontend", lambda production: ["missing-test-command"]
    )
    monkeypatch.setattr(launcher, "wait_ready", lambda *_: None)
    calls: list[tuple[object, ...]] = []

    def launch(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        calls.append(args)
        if len(calls) == 1:
            return child
        raise FileNotFoundError("test frontend executable missing")

    monkeypatch.setattr(launcher.subprocess, "Popen", launch)
    try:
        with pytest.raises(FileNotFoundError, match="frontend executable"):
            launcher.start_servers(True)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_supervision_detects_frontend_exit_instead_of_waiting_on_backend() -> None:
    child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(9)"])
    child.wait(timeout=5)
    with pytest.raises(RuntimeError, match="code 9"):
        launcher.supervise([child])
