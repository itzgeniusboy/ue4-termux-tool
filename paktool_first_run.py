#!/usr/bin/env python3
"""Dependency-light first-run screen for Paktool."""
from __future__ import annotations

import json
import os
import select
import sys
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "paktool"
STATUS_FILE = STATE_DIR / "setup-status.json"
LOG_FILE = STATE_DIR / "setup.log"
SPINNER = "|/-\\"


def read_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "state": "starting",
            "stage": "Starting setup",
            "percent": 0,
            "remaining_percent": 100,
            "stage_index": 0,
            "stage_total": 4,
        }


def _number(status: dict, name: str, fallback: int) -> int:
    try:
        return max(0, min(100, int(status.get(name, fallback))))
    except (TypeError, ValueError):
        return fallback


def progress_bar(percent: int, width: int = 28) -> str:
    filled = percent * width // 100
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def format_seconds(value: object) -> str:
    if value in (None, "", "null", "unknown"):
        return "calculating"
    try:
        total = max(0, int(value))
    except (TypeError, ValueError):
        return "calculating"
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_bytes(value: object) -> str:
    if value in (None, "", "null", "unknown"):
        return "unavailable"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while amount >= 1024 and index < len(units) - 1:
        amount /= 1024
        index += 1
    return f"{amount:.2f} {units[index]}"


def show_status(status: dict, tick: int = 0) -> None:
    percent = _number(status, "percent", 0)
    remaining = _number(status, "remaining_percent", 100 - percent)
    stage = str(status.get("stage", "Starting setup"))
    state = str(status.get("state", "starting"))
    stage_index = status.get("stage_index", 0)
    stage_total = status.get("stage_total", 4)
    elapsed = status.get("elapsed_seconds", 0)
    eta = status.get("eta_seconds")
    downloaded = status.get("downloaded_bytes")
    download_total = status.get("download_total_bytes")
    updated_at = status.get("updated_at", status.get("updated", "calculating"))
    heartbeat = status.get("heartbeat_count", tick)
    spinner = SPINNER[tick % len(SPINNER)]
    plain = os.environ.get("PAKTOOL_PLAIN") == "1" or os.environ.get("NO_COLOR") == "1"
    if plain:
        clear = ""
        accent = ""
        reset = ""
    else:
        clear = "\033[H\033[J"
        accent = "\033[1;36m"
        reset = "\033[0m"
    print(f"{clear}Paktool Launcher — OPEN")
    print("========================")
    print("Full Paktool menu is preparing automatically; no second command is needed.")
    print(f"{spinner} {percent:3d}% stage estimate  |  {remaining:3d}% remaining")
    print(f"{progress_bar(percent)}  {percent:3d}%")
    print(f"{accent}Stage {stage_index}/{stage_total}:{reset} {stage}")
    print(f"State: {state}")
    print(f"Heartbeat: #{heartbeat}  |  Last update: {updated_at}")
    print(f"Elapsed: {format_seconds(elapsed)}  |  ETA: {format_seconds(eta)}")
    print(f"Download: {format_bytes(downloaded)} / {format_bytes(download_total)}")
    print("Note: the percentage is a stage estimate; package managers may not expose exact byte totals.")
    print(f"Log:   {LOG_FILE}")
    if status.get("error"):
        print(f"Error: {status['error']}")
    print("\nSetup continues transparently with official package managers.")
    print("This launcher is active now; the full PAK/Lua menu will unlock automatically.")
    print("Press Enter to refresh, `s` for full status, or `q` to exit.")
    sys.stdout.flush()


def read_key(timeout: float = 0.5) -> str | None:
    """Read a key line without blocking progress animation when stdin is a TTY."""
    if not sys.stdin.isatty():
        time.sleep(timeout)
        return None
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
    except (OSError, ValueError):
        time.sleep(timeout)
        return None
    if not ready:
        return None
    try:
        return sys.stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


def main(argv: list[str]) -> int:
    if "--script" not in argv:
        print("Setup is still running. Check: tool setup-status")
        return 2
    script_index = argv.index("--script")
    if script_index + 1 >= len(argv):
        print("First-run screen requires a Paktool script path.", file=sys.stderr)
        return 2
    script = Path(argv[script_index + 1]).resolve()
    original_args = argv[script_index + 2:]
    tick = 0
    while True:
        status = read_status()
        if status.get("state") == "ready":
            os.execv(sys.executable, [sys.executable, str(script), *original_args])
        show_status(status, tick)
        choice = read_key(0.5)
        if choice == "q":
            print("\nPaktool setup continues in the background. Exiting screen.")
            return 2
        if choice == "s":
            print(json.dumps(read_status(), indent=2))
            time.sleep(0.5)
        tick += 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
