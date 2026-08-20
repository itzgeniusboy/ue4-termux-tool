from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paktool_support import ToolError, run_repak, sanitize_diagnostic_text, start_background_update

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "paktool_support.py"
NATIVE_TOOL = ROOT / "paktool.py"
source_text = TOOL.read_text(encoding="utf-8")
assert "def backup_file" not in source_text
assert "start_background_update" in source_text
assert "paktool-update.lock" in source_text
assert 'APP_NAME = "paktool"' in source_text
assert "_send_report" not in source_text
assert "urlopen" not in source_text
sanitized = sanitize_diagnostic_text("--aes-key SECRET /sdcard/private/game.pak")
assert "SECRET" not in sanitized
assert "/sdcard/private/game.pak" not in sanitized
for script in ("setup.sh", "update-termux.sh", "install-termux.sh", "bootstrap.sh"):
    subprocess.run(["bash", "-n", str(ROOT / script)], check=True)

installer_text = (ROOT / "install-termux.sh").read_text(encoding="utf-8")
assert 'CARGO_BIN_DIR="${CARGO_HOME:-$HOME/.cargo}/bin"' in installer_text
assert 'ln -sf "$REPAK_CARGO_BIN" "$BIN_DIR/repak"' in installer_text
assert 'export PATH="$BIN_DIR:$CARGO_BIN_DIR:$PATH"' in installer_text
assert installer_text.count('cat > "$BIN_DIR/paktool"') == 1
assert 'Error: tool command was not installed.' not in installer_text

assert "DEFAULT_UPDATE_INTERVAL_SECONDS = 6 * 60 * 60" in source_text
assert "paktool-update.last-success" in source_text
assert 'source.rglob("*.lua")' in source_text
assert "shutil.copyfile(lua_file, destination)" in source_text

timings: dict[str, float] = {}
with tempfile.TemporaryDirectory(prefix="paktool-update-cache-test-") as update_cache:
    cache_dir = Path(update_cache)
    (cache_dir / "paktool-update.last-success").touch()
    started = time.perf_counter()
    with patch.dict(os.environ, {"XDG_CACHE_HOME": update_cache}, clear=False), patch("paktool_support.subprocess.Popen") as update_process:
        start_background_update()
    timings["background_update_throttled"] = time.perf_counter() - started
    update_process.assert_not_called()

with tempfile.TemporaryDirectory(prefix="paktool-support-test-") as tmp:
    base = Path(tmp)
    source = base / "unpacked"
    (source / "Existing").mkdir(parents=True)
    (source / "Existing/file.txt").write_text("existing", encoding="utf-8")
    lua = base / "lua"
    (lua / "MyMod").mkdir(parents=True)
    (lua / "MyMod/init.lua").write_text("print('ok')\n", encoding="utf-8")
    (lua / "MyMod/player.lua").write_text("return {}\n", encoding="utf-8")

    fake_repak = base / "repak"
    fake_repak.write_text("""#!/usr/bin/env python3
import pathlib, sys
args = sys.argv[1:]
if args and args[0] == 'unpack':
    out = pathlib.Path(args[args.index('--output') + 1])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'Existing/file.txt').parent.mkdir(parents=True, exist_ok=True)
    (out / 'Existing/file.txt').write_text('existing')
elif args and args[0] == 'pack':
    source = pathlib.Path(args[1]); output = pathlib.Path(args[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('packed\\n' + '\\n'.join(sorted(p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file())), encoding='utf-8')
else:
    raise SystemExit(2)
""", encoding="utf-8")
    fake_repak.chmod(0o755)

    input_pak = base / "input.pak"
    input_pak.write_text("placeholder", encoding="utf-8")
    unpacked = base / "unpacked-from-pak"
    started = time.perf_counter()
    subprocess.run([sys.executable, str(TOOL), "unpack", str(input_pak), str(unpacked), "--repak", str(fake_repak)], check=True)
    timings["unpack"] = time.perf_counter() - started
    assert (unpacked / "Existing/file.txt").read_text(encoding="utf-8") == "existing"

    repacked = base / "repacked.pak"
    started = time.perf_counter()
    subprocess.run([sys.executable, str(TOOL), "repack", str(source), str(repacked), "--version", "v7", "--repak", str(fake_repak)], check=True)
    timings["repack"] = time.perf_counter() - started
    assert repacked.exists()
    assert "Existing/file.txt" in repacked.read_text(encoding="utf-8")

    injected = base / "injected.pak"
    started = time.perf_counter()
    subprocess.run([sys.executable, str(TOOL), "inject", str(input_pak), str(lua), str(injected), "--repak", str(fake_repak), "--target-prefix", "Script", "--version", "v7"], check=True)
    timings["inject"] = time.perf_counter() - started
    text = injected.read_text(encoding="utf-8")
    assert "Script/MyMod/init.lua" in text
    assert "Script/MyMod/player.lua" in text


def test_repak_empty_output_failure_diagnostic() -> None:
    with tempfile.TemporaryDirectory(prefix="paktool-empty-repak-test-") as empty_repak_tmp:
        empty_repak = Path(empty_repak_tmp) / "repak"
        empty_repak.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        empty_repak.chmod(0o755)
        mocked_results = [
            subprocess.CompletedProcess([str(empty_repak)], 1, stdout="", stderr=""),
            subprocess.CompletedProcess([str(empty_repak), "--version"], 0, stdout="repak 1.0\n", stderr=""),
        ]
        with patch("paktool_support.subprocess.run", side_effect=mocked_results) as mocked_run:
            try:
                run_repak(str(empty_repak), None, ["unpack", "input.pak"])
            except ToolError as exc:
                empty_failure = str(exc)
            else:
                raise AssertionError("run_repak should fail for a non-zero empty-output result")
        assert "repak --version: repak 1.0" in empty_failure
        assert "repak produced no output — this usually means" in empty_failure
        assert "Try: repak --version to confirm the binary works" in empty_failure
        assert mocked_run.call_args_list[1].kwargs["timeout"] == 5
        assert "/tmp/" not in sanitize_diagnostic_text(empty_failure)


test_repak_empty_output_failure_diagnostic()

with tempfile.TemporaryDirectory(prefix="paktool-local-diagnostic-test-") as diagnostic_tmp:
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = diagnostic_tmp
    env["PAKTOOL_NO_AUTO_RETRY"] = "1"
    failed = subprocess.run([sys.executable, str(NATIVE_TOOL), "unpack", "/sdcard/private/missing.pak"], check=False, capture_output=True, text=True, env=env)
    assert failed.returncode != 0
    reports = list((Path(diagnostic_tmp) / "paktool").glob("error-*.json"))
    assert reports
    report_data = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report_data["command"] == "unpack"
    assert "PAK contents" in report_data["privacy"]
    assert report_data["context"]["stage"] == "validate_source"
    assert "error_type" in report_data["context"]
    assert "Diagnostic report:" in failed.stderr

with tempfile.TemporaryDirectory(prefix="paktool-corrupt-unpack-test-") as corrupt_tmp:
    corrupt_root = Path(corrupt_tmp)
    corrupt_pak = corrupt_root / "corrupt.pak"
    corrupt_pak.write_bytes(b"not-a-valid-ue4-pak")
    corrupt_output = corrupt_root / "unpacked"
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(corrupt_root / "state")
    env["PAKTOOL_NO_AUTO_RETRY"] = "1"
    failed = subprocess.run(
        [sys.executable, str(NATIVE_TOOL), "unpack", str(corrupt_pak), str(corrupt_output)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert failed.returncode != 0
    reports = list((corrupt_root / "state" / "paktool").glob("error-*.json"))
    assert reports
    corrupt_report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert corrupt_report["context"]["stage"] == "open_parser"
    assert corrupt_report["context"]["error_type"] == "SystemExit"
    assert "PAK format was not recognized" in corrupt_report["error"]
    assert str(corrupt_root) not in json.dumps(corrupt_report)
    operation_logs = list((corrupt_root / "state" / "paktool" / "logs").glob("operation-*.jsonl"))
    assert operation_logs
    operation_text = "\n".join(path.read_text(encoding="utf-8") for path in operation_logs)
    assert "unpack_parser_attempt_failed" in operation_text
    assert "unpack_parser_failed" in operation_text

started = time.perf_counter()
help_result = subprocess.run([sys.executable, str(TOOL), "--help"], check=True, capture_output=True, text=True)
timings["startup_help"] = time.perf_counter() - started
assert "unpack" in help_result.stdout
assert "repack" in help_result.stdout
assert "inject" in help_result.stdout
for label, elapsed in timings.items():
    print(f"benchmark_{label}_seconds={elapsed:.3f}")
print("focused-smoke-tests-ok")

if __name__ == "__main__":
    pass
