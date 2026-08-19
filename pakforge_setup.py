#!/usr/bin/env python3
"""Transparent first-run dependency setup for PakForge.

This helper intentionally uses only fixed-argument official package-manager,
pip, and cargo commands. It never downloads or executes an arbitrary URL.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "pakforge"
LOCK_DIR = STATE_DIR / "setup.lock"
STATUS_FILE = STATE_DIR / "setup-status.json"
LOG_FILE = STATE_DIR / "setup.log"

MODULES = {
    "rich": "rich",
    "pytz": "pytz",
    "gmalg": "gmalg",
    "pycryptodome": "Crypto",
    "zstandard": "zstandard",
}


def _status() -> dict:
    return {
        "python": sys.executable,
        "modules": {name: importlib.util.find_spec(module) is not None for name, module in MODULES.items()},
        "commands": {
            name: shutil.which(name) is not None
            for name in ("repak", "luac5.1", "luac51", "pkg", "apt", "pacman", "cargo")
        },
        "state": "ready" if all(importlib.util.find_spec(module) is not None for module in MODULES.values()) else "incomplete",
        "log": str(LOG_FILE),
    }


def _write_status(state: str, **extra: object) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = _status()
    payload.update({"state": state, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **extra})
    STATUS_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {message}\n")
        handle.flush()


def _run(label: str, command: list[str]) -> bool:
    _log(f"START {label}: {' '.join(command)}")
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=False)
    except OSError as exc:
        _log(f"ERROR {label}: {exc}")
        return False
    _log(f"END {label}: exit={result.returncode}")
    return result.returncode == 0


def _package_command() -> tuple[str, list[str]] | None:
    if shutil.which("pkg"):
        return "Termux pkg", ["pkg", "install", "-y", "python", "python-pip", "unzip", "rust", "lua51"]
    if shutil.which("apt"):
        prefix = [] if getattr(os, "geteuid", lambda: 1)() == 0 else ["sudo"]
        return "APT", prefix + ["apt", "install", "-y", "python3-pip", "unzip", "cargo", "lua5.1"]
    if shutil.which("pacman"):
        prefix = [] if getattr(os, "geteuid", lambda: 1)() == 0 else ["sudo"]
        return "pacman", prefix + ["pacman", "-S", "--noconfirm", "python-pip", "unzip", "rust", "lua51"]
    return None


def _link_repak() -> None:
    cargo_bin = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")) / "bin" / "repak"
    prefix = os.environ.get("PREFIX")
    if prefix and cargo_bin.is_file():
        target = Path(prefix) / "bin" / "repak"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.unlink(missing_ok=True)
            target.symlink_to(cargo_bin)
            _log(f"Linked repak to {target}")
        except OSError as exc:
            _log(f"WARN could not link repak: {exc}")


def perform_setup() -> int:
    _write_status("running")
    package = _package_command()
    if package is not None:
        _log(f"Using official package manager: {package[0]}")
        if not _run(package[0], package[1]):
            _log("WARN package-manager setup failed; continuing with direct dependency checks")
    else:
        _log("WARN no supported package manager detected")

    missing = [name for name, module in MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        pip_command = [sys.executable, "-m", "pip", "install", "--upgrade", "rich", "pytz", "gmalg", "pycryptodome", "zstandard"]
        if not _run("Python dependencies", pip_command):
            _write_status("failed", error="Python dependency installation failed", missing=missing)
            return 2

    if shutil.which("repak") is None and shutil.which("cargo") is not None:
        cargo_command = [
            "cargo", "install", "--git", "https://github.com/trumank/repak",
            "--locked", "--bin", "repak", "--no-default-features",
        ]
        if not _run("repak", cargo_command):
            _log("WARN repak installation failed; native PakForge commands remain available")
        _link_repak()

    final = _status()
    if not all(final["modules"].values()):
        _write_status("failed", error="Required Python modules are still missing", missing=final["modules"])
        return 2
    _write_status("ready", message="PakForge background setup completed")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--status"] or argv[:1] == ["status"]:
        print(json.dumps(_status() if not STATUS_FILE.exists() else json.loads(STATUS_FILE.read_text(encoding="utf-8")), indent=2))
        return 0
    if argv[:1] not in (["--background"], ["background"]):
        print(f"Setup log: {LOG_FILE}")
        print("Usage: pakforge setup-status")
        return 0
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        return 0
    try:
        return perform_setup()
    finally:
        shutil.rmtree(LOCK_DIR, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

