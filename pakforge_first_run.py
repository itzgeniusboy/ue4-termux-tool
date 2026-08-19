#!/usr/bin/env python3
"""Dependency-light first-run screen for PakForge."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "pakforge"
STATUS_FILE = STATE_DIR / "setup-status.json"
LOG_FILE = STATE_DIR / "setup.log"


def read_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "starting"}


def show_status() -> None:
    status = read_status()
    print("\nPakForge first-run setup")
    print("========================")
    print(f"Status: {status.get('state', 'starting')}")
    print(f"Log:    {LOG_FILE}")
    if status.get("error"):
        print(f"Error:  {status['error']}")
    print("\nBackground setup is continuing with official package managers.")
    print("Press Enter to check again, `s` to show status, or `q` to exit.")


def main(argv: list[str]) -> int:
    if "--script" not in argv:
        print(f"Setup is still running. Check: pakforge setup-status")
        return 2
    script_index = argv.index("--script")
    script = Path(argv[script_index + 1]).resolve()
    original_args = argv[script_index + 2:]
    while True:
        status = read_status()
        if status.get("state") == "ready":
            os.execv(sys.executable, [sys.executable, str(script), *original_args])
        show_status()
        try:
            choice = input("PakForge> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 2
        if choice == "q":
            return 2
        if choice == "s":
            print(json.dumps(read_status(), indent=2))
        else:
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

