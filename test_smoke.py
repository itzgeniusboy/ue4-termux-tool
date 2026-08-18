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

    fake_luac = base / "luac5.3"
    fake_luac.write_text("""#!/usr/bin/env python3
import pathlib, sys
args = sys.argv[1:]
if args == ['-v']:
    print('Lua 5.3')
elif args and args[0] == '-p':
    source = pathlib.Path(args[1]).read_text()
    if 'syntax_error' in source:
        print(f'{args[1]}:1: syntax error', file=sys.stderr)
        raise SystemExit(1)
elif args and args[0] == '-o':
    output = pathlib.Path(args[1]); source = pathlib.Path(args[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b'\\x1bLua' + source.read_bytes())
else:
    raise SystemExit(2)
""", encoding="utf-8")
    fake_luac.chmod(0o755)
    report = base / "reports/validate.json"
    subprocess.run([
        sys.executable, str(TOOL), "lua-validate", str(lua),
        "--luac", str(fake_luac), "--report", str(report)
    ], check=True)
    assert report.exists()

    compiled = base / "compiled"
    subprocess.run([
        sys.executable, str(TOOL), "lua-compile", str(lua),
        "--out", str(compiled), "--luac", str(fake_luac)
    ], check=True)
    assert (compiled / "MyMod/init.lua").read_bytes().startswith(b"\x1bLua")

    archive = base / "compiled.zip"
    subprocess.run([sys.executable, str(TOOL), "lua-zip", str(compiled), str(archive)], check=True)
    with zipfile.ZipFile(archive) as zf:
        assert "MyMod/init.lua" in zf.namelist()

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
    output.write_text('packed\\n' + '\\n'.join(sorted(p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file())) )
elif args and args[0] == 'hash-list':
    print('0000  Existing/file.txt')
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

    result = subprocess.run([
        sys.executable, str(TOOL), "pak-hash", str(pak), "--repak", str(fake_repak)
    ], check=True, capture_output=True, text=True)
    assert "Existing/file.txt" in result.stdout

print("smoke-tests-ok")
