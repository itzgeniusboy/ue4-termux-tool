#!/usr/bin/env python3
"""Smoke tests for PakForge's neon terminal theme."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

assert set(("purple", "blue", "cyan", "green", "pink", "yellow", "red", "muted")) <= set(
    __import__("pakforge_core").NEON
)

result = subprocess.run(
    [sys.executable, "-c", "from pakforge_core import print_banner; print_banner()"],
    cwd=ROOT,
    env={**os.environ, "PAKFORGE_PLAIN": "1", "TERM": "dumb"},
    capture_output=True,
    text=True,
    check=True,
)
assert "PAK INSPECT" in result.stdout
assert "SYSTEM READY" in result.stdout

print("theme-tests-ok")

