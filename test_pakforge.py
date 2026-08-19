#!/usr/bin/env python3
"""Fast tests for PakForge's wrapper workflows without requiring a real PAK file."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pakforge

ROOT = Path(__file__).resolve().parent
PAKFORGE = ROOT / "pakforge.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PAKFORGE), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> None:
    assert pakforge.normalize_target_prefix("Content\\\\Lua\\\\Mods") == "Content/Lua/Mods"
    assert pakforge.normalize_target_prefix("/Content/Lua/Mods/") == "Content/Lua/Mods"
    try:
        pakforge.normalize_target_prefix("Content/../Config")
    except SystemExit:
        pass
    else:
        raise AssertionError("path traversal was accepted")

    parsed = pakforge.parser().parse_args([
        "repack", "source.pak", "edited", "output.pak", "--target-prefix", "Content/Lua"
    ])
    assert parsed.target_prefix == "Content/Lua"

    version = run("--version")
    assert version.returncode == 0
    assert version.stdout.strip() == "PakForge 1.1.0"

    with tempfile.TemporaryDirectory(prefix="pakforge-test-") as raw:
        root = Path(raw)
        (root / "nested").mkdir()
        sample = root / "nested" / "sample.txt"
        sample.write_text("pakforge-test\n", encoding="utf-8")

        created = run("manifest", str(root))
        assert created.returncode == 0, created.stderr
        manifest = root / ".pakforge-manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["tool"] == "PakForge"
        assert payload["files"][0]["sha256"] == hashlib.sha256(sample.read_bytes()).hexdigest()

        verified = run("verify", str(root))
        assert verified.returncode == 0, verified.stderr

        sample.write_text("tampered\n", encoding="utf-8")
        tampered = run("verify", str(root))
        assert tampered.returncode == 2
        assert "CHANGED" in tampered.stdout

        invalid = root / "invalid.pak"
        invalid.write_bytes(b"not-a-valid-pak")
        state = root / "state"
        failure = subprocess.run(
            [sys.executable, str(PAKFORGE), "info", str(invalid)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={**os.environ, "XDG_STATE_HOME": str(state)},
            check=False,
        )
        assert failure.returncode == 1
        assert "Operation log saved locally:" in failure.stderr
        native_logs = list((state / "pakforge" / "logs").glob("operation-*.jsonl"))
        assert native_logs
        native_log = native_logs[0].read_text(encoding="utf-8")
        assert "unexpected_exception" in native_log
        assert "unpack_from" in native_log

    print("pakforge-tests-ok")


if __name__ == "__main__":
    main()
