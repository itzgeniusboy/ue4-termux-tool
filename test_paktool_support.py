from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

from paktool_support import OperationLog, ToolError, create_manifest, pak_info, verify_manifest, refuse_existing_output

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "paktool_support.py"

with tempfile.TemporaryDirectory(prefix="paktool_support-power-test-") as tmp:
    base = Path(tmp)
    files = base / "files"
    (files / "nested").mkdir(parents=True)
    (files / "nested/data.txt").write_text("power test\n", encoding="utf-8")

    manifest = create_manifest(files)
    assert manifest.name == ".paktool-manifest.json"
    ok, issues = verify_manifest(files)
    assert ok and not issues

    (files / "nested/data.txt").write_text("tampered\n", encoding="utf-8")
    ok, issues = verify_manifest(files)
    assert not ok
    assert ("CHANGED", "nested/data.txt") in issues

    output = base / "existing.pak"
    output.write_text("keep", encoding="utf-8")
    try:
        refuse_existing_output(output, overwrite=False)
    except ToolError:
        pass
    else:
        raise AssertionError("overwrite protection did not reject an existing output")

    pak = base / "sample.pak"
    pak.write_bytes(b"sample pak bytes")
    export = base / "pak-info.json"
    pak_info(type("Args", (), {"pak": str(pak), "export": str(export)})())
    metadata = json.loads(export.read_text(encoding="utf-8"))
    assert metadata["name"] == "sample.pak"
    assert metadata["size"] == len(b"sample pak bytes")
    assert len(metadata["sha256"]) == 64

    fake_repak = base / "repak"
    fake_repak.write_text(
        """#!/usr/bin/env python3
import pathlib
import sys
args = sys.argv[1:]
if args and args[0] == 'unpack':
    out = pathlib.Path(args[args.index('--output') + 1])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'file.txt').write_text('unpacked', encoding='utf-8')
elif args and args[0] == 'pack':
    source = pathlib.Path(args[1]); output = pathlib.Path(args[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('packed', encoding='utf-8')
else:
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_repak.chmod(fake_repak.stat().st_mode | stat.S_IXUSR)
    pak_dir = base / "paks"
    pak_dir.mkdir()
    (pak_dir / "one.pak").write_bytes(b"one")
    (pak_dir / "two.pak").write_bytes(b"two")
    batch_out = base / "batch-out"
    env = os.environ.copy()
    env["PAKTOOL_NO_AUTO_RETRY"] = "1"
    env["PAKTOOL_NO_REPORT"] = "1"
    subprocess.run(
        [sys.executable, str(TOOL), "batch-unpack", str(pak_dir), str(batch_out), "--repak", str(fake_repak)],
        check=True,
        env=env,
    )
    assert (batch_out / "one" / "file.txt").exists()
    assert (batch_out / "two" / "file.txt").exists()

    failing_repak = base / "failing-repak"
    failing_repak.write_text(
        "#!/usr/bin/env python3\nimport sys\nprint('synthetic repak failure: invalid PAK index', file=sys.stderr)\nsys.exit(1)\n",
        encoding="utf-8",
    )
    failing_repak.chmod(failing_repak.stat().st_mode | stat.S_IXUSR)
    failed = subprocess.run(
        [sys.executable, str(TOOL), "unpack", str(pak_dir / "one.pak"), str(base / "failed-out"), "--repak", str(failing_repak)],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 1
    assert "synthetic repak failure: invalid PAK index" in failed.stderr

    previous_state = os.environ.get("XDG_STATE_HOME")
    os.environ["XDG_STATE_HOME"] = str(base / "state")
    operation_log = OperationLog("logging-test", type("Args", (), {"aes_key": "super-secret", "source": str(pak)})())
    assert operation_log.path is not None
    operation_log.event("sample_failure", stderr="aes_key=super-secret")
    log_path = operation_log.path
    operation_log.close()
    log_text = log_path.read_text(encoding="utf-8")
    assert "super-secret" not in log_text
    assert "<redacted>" in log_text
    listed = subprocess.run(
        [sys.executable, str(TOOL), "logs", "--limit", "2", "--tail", "2"],
        check=True,
        env={**env, "XDG_STATE_HOME": str(base / "state")},
        capture_output=True,
        text=True,
    )
    assert str(log_path) in listed.stdout
    if previous_state is None:
        os.environ.pop("XDG_STATE_HOME", None)
    else:
        os.environ["XDG_STATE_HOME"] = previous_state

print("power-feature-tests-ok")
