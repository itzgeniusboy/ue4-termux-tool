from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "ue4tool.py"

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

print("focused-smoke-tests-ok")
