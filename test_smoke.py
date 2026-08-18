from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "ue4tool.py"

with tempfile.TemporaryDirectory(prefix="ue4tool-test-") as tmp:
    base = Path(tmp)
    obb = base / "main.1.example.obb"
    with zipfile.ZipFile(obb, "w") as zf:
        zf.writestr("Project/Content/Paks/game.pak", b"fake pak")
        zf.writestr("Project/Content/readme.txt", b"ok")
    out = base / "obb-out"
    subprocess.run([sys.executable, str(TOOL), "obb-unpack", str(obb), "--out", str(out)], check=True)
    assert (out / "Project/Content/Paks/game.pak").read_bytes() == b"fake pak"

    lua = base / "lua"
    (lua / "MyMod").mkdir(parents=True)
    (lua / "MyMod/init.lua").write_text("print('ok')\n", encoding="utf-8")
    (lua / "MyMod/player.lua").write_text("return {}\n", encoding="utf-8")

    fake_repak = base / "repak"
    fake_repak.write_text("""#!/usr/bin/env python3
import pathlib, shutil, sys
args = sys.argv[1:]
if args and args[0] == 'unpack':
    out = pathlib.Path(args[args.index('--output') + 1])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'Existing/file.txt').parent.mkdir(parents=True, exist_ok=True)
    (out / 'Existing/file.txt').write_text('existing')
elif args and args[0] == 'pack':
    source = pathlib.Path(args[1]); output = pathlib.Path(args[2])
    output.write_text('packed\\n' + '\\n'.join(sorted(p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file())))
else:
    print('fake repak: ' + ' '.join(args))
""", encoding="utf-8")
    fake_repak.chmod(0o755)
    pak = base / "input.pak"
    pak.write_text("placeholder")
    injected = base / "injected.pak"
    subprocess.run([
        sys.executable, str(TOOL), "lua-inject", str(pak), str(lua),
        "--output", str(injected), "--repak", str(fake_repak),
        "--target-prefix", "Script", "--version", "v7"
    ], check=True)
    text = injected.read_text(encoding="utf-8")
    assert "Script/MyMod/init.lua" in text
    assert "Script/MyMod/player.lua" in text

print("smoke-tests-ok")
