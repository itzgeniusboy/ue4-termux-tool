from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ue4tool import _send_report, sanitize_diagnostic_text

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "ue4tool.py"

source_text = TOOL.read_text(encoding="utf-8")
assert "def backup_file" not in source_text
assert "start_background_update" in source_text
assert "tool-update.lock" in source_text
assert 'APP_NAME = "tool"' in source_text
sanitized = sanitize_diagnostic_text("--aes-key SECRET /sdcard/private/game.pak")
assert "SECRET" not in sanitized
assert "/sdcard/private/game.pak" not in sanitized
for script in ("setup.sh", "update-termux.sh", "install-termux.sh"):
    subprocess.run(["bash", "-n", str(ROOT / script)], check=True)

with tempfile.TemporaryDirectory(prefix="ue4tool-test-") as tmp:
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
    subprocess.run([
        sys.executable, str(TOOL), "unpack", str(input_pak), str(unpacked), "--repak", str(fake_repak)
    ], check=True)
    assert (unpacked / "Existing/file.txt").read_text(encoding="utf-8") == "existing"

    repacked = base / "repacked.pak"
    subprocess.run([
        sys.executable, str(TOOL), "repack", str(source), str(repacked),
        "--version", "v7", "--repak", str(fake_repak)
    ], check=True)
    assert repacked.exists()
    assert "Existing/file.txt" in repacked.read_text(encoding="utf-8")

    injected = base / "injected.pak"
    subprocess.run([
        sys.executable, str(TOOL), "inject", str(input_pak), str(lua), str(injected), "--repak", str(fake_repak),
        "--target-prefix", "Script", "--version", "v7"
    ], check=True)
    text = injected.read_text(encoding="utf-8")
    assert "Script/MyMod/init.lua" in text
    assert "Script/MyMod/player.lua" in text

with tempfile.TemporaryDirectory(prefix="tool-report-test-") as report_tmp:
    report_env = os.environ.copy()
    report_env["XDG_STATE_HOME"] = report_tmp
    report_env["TOOL_NO_AUTO_RETRY"] = "1"
    failed = subprocess.run(
        [sys.executable, str(TOOL), "unpack", "/sdcard/private/missing.pak"],
        check=False,
        capture_output=True,
        text=True,
        env=report_env,
    )
    assert failed.returncode != 0
    reports = list((Path(report_tmp) / "tool").glob("error-*.json"))
    assert reports
    report_data = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report_data["command"] == "unpack"
    assert "PAK contents" in report_data["privacy"]

    no_report_env = {
        "TOOL_NO_REPORT": "1",
        "UE4TOOL_REPORT_ENDPOINT": "https://relay.example/api/report",
    }
    with patch.dict(os.environ, no_report_env, clear=False), patch("ue4tool.urlrequest.urlopen") as blocked_send:
        assert _send_report(reports[0]) is False
        blocked_send.assert_not_called()

    with tempfile.TemporaryDirectory(prefix="tool-consent-test-") as consent_tmp:
        fake_response = MagicMock()
        fake_response.__enter__.return_value.status = 202
        send_env = {
            "TOOL_NO_REPORT": "0",
            "UE4TOOL_REPORT_ENDPOINT": "https://relay.example/api/report",
            "XDG_CONFIG_HOME": consent_tmp,
        }
        with patch.dict(os.environ, send_env, clear=False), patch("builtins.input", return_value="y"), patch("ue4tool.urlrequest.urlopen", return_value=fake_response) as sent:
            assert _send_report(reports[0]) is True
            outgoing = json.loads(sent.call_args.args[0].data.decode("utf-8"))
            assert set(outgoing) == {"operation", "error_message", "tool_version", "exit_code", "platform"}
            assert "/sdcard/private/missing.pak" not in outgoing["error_message"]
        assert (Path(consent_tmp) / "ue4tool" / "report_consent").read_text(encoding="utf-8").strip() == "yes"

help_result = subprocess.run([sys.executable, str(TOOL), "--help"], check=True, capture_output=True, text=True)
assert "unpack" in help_result.stdout
assert "repack" in help_result.stdout
assert "inject" in help_result.stdout
print("focused-smoke-tests-ok")
