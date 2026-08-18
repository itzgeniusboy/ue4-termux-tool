#!/usr/bin/env python3
"""UE4 Termux Tool: safe OBB, Unreal Engine PAK, and standard Lua helper.

This program delegates UE4 PAK parsing/writing to the repak CLI and uses an
owner-installed Lua 5.3 compiler for optional source validation/compilation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

APP_NAME = "ue4tool"


def fail(message: str, code: int = 2) -> None:
    print(f"{APP_NAME}: error: {message}", file=sys.stderr)
    raise SystemExit(code)


def require_file(path: Path, label: str) -> Path:
    path = path.expanduser()
    if not path.is_file():
        fail(f"{label} not found or is not a regular file: {path}")
    return path


def require_dir(path: Path, label: str) -> Path:
    path = path.expanduser()
    if not path.is_dir():
        fail(f"{label} not found or is not a directory: {path}")
    return path


def safe_member_path(name: str) -> PurePosixPath:
    """Validate a ZIP member path before writing it to the filesystem."""
    if not name or "\x00" in name:
        fail("archive contains an empty or NUL-containing member name")
    normalized = name.replace("\\", "/")
    p = PurePosixPath(normalized)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts):
        fail(f"refusing unsafe archive path: {name!r}")
    return p


def safe_destination(root: Path, relative: str | PurePosixPath) -> Path:
    rel = PurePosixPath(str(relative).replace("\\", "/"))
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        fail(f"refusing unsafe relative path: {relative!s}")
    root = root.resolve()
    destination = (root / Path(*rel.parts)).resolve()
    try:
        destination.relative_to(root)
    except ValueError:
        fail(f"destination escapes output directory: {relative!s}")
    return destination


def zip_is_obb(path: Path) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def obb_list(path: Path) -> None:
    require_file(path, "OBB")
    if not zip_is_obb(path):
        fail("this OBB is not ZIP-compatible; Android OBB files may use a custom/opaque format")
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        print(f"{len(infos)} entries in {path}")
        for info in infos:
            marker = "/" if info.is_dir() else ""
            print(f"{info.file_size:>12}  {info.filename}{marker}")


def obb_unpack(path: Path, output: Path, force: bool) -> None:
    require_file(path, "OBB")
    if not zip_is_obb(path):
        fail("this OBB is not ZIP-compatible; no generic unpacking is possible")
    output = output.expanduser()
    if output.exists() and any(output.iterdir()) and not force:
        fail(f"output directory is not empty: {output} (use --force to overwrite)")
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            rel = safe_member_path(info.filename)
            destination = safe_destination(output, rel)
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not force:
                fail(f"file already exists: {destination} (use --force to overwrite)")
            with zf.open(info, "r") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    print(f"Extracted {count} files to {output}")


def repak_binary(explicit: str | None) -> str:
    candidate = explicit or os.environ.get("REPAK_BIN") or "repak"
    if os.path.sep not in candidate and shutil.which(candidate) is None:
        fail("repak was not found. Run ./install-termux.sh, or pass --repak /path/to/repak")
    if os.path.sep in candidate and not Path(candidate).expanduser().is_file():
        fail(f"repak executable not found: {candidate}")
    return str(Path(candidate).expanduser()) if os.path.sep in candidate else candidate


def repak_command(binary: str, aes_key: str | None, args: list[str]) -> list[str]:
    command = [binary]
    if aes_key:
        command += ["--aes-key", aes_key]
    return command + args


def run_repak(binary: str, aes_key: str | None, args: list[str]) -> None:
    command = repak_command(binary, aes_key, args)
    print("$ " + " ".join(subprocess.list2cmdline([part]) for part in command))
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        fail(f"could not execute repak: {exc}")
    if completed.returncode != 0:
        fail(f"repak failed with exit code {completed.returncode}", completed.returncode)


def pak_info(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    run_repak(repak_binary(args.repak), args.aes_key, ["info", str(pak)])


def pak_list(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    command = ["list", str(pak), "--strip-prefix", args.strip_prefix]
    run_repak(repak_binary(args.repak), args.aes_key, command)


def pak_hash(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    command = ["hash-list", str(pak), "--strip-prefix", args.strip_prefix]
    run_repak(repak_binary(args.repak), args.aes_key, command)


def pak_unpack(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    output = Path(args.output).expanduser() if args.output else pak.with_suffix("")
    command = ["unpack", str(pak), "--output", str(output), "--strip-prefix", args.strip_prefix, "--force"]
    if args.quiet:
        command.append("--quiet")
    run_repak(repak_binary(args.repak), args.aes_key, command)
    print(f"Unpacked PAK to {output}")


def pak_pack(args: argparse.Namespace) -> None:
    source = require_dir(Path(args.source), "source directory")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["pack", str(source), str(output), "--version", args.version, "--mount-point", args.mount_point]
    if args.compression:
        command += ["--compression", args.compression]
    if args.quiet:
        command.append("--quiet")
    run_repak(repak_binary(args.repak), None, command)
    print(f"Packed {source} to {output}")


def copy_lua_files(source: Path, staging: Path, target_prefix: str, target_file: str | None) -> int:
    target_prefix = target_prefix.strip("/\\")
    if target_file:
        if source.is_dir():
            fail("--target-file can only be used when the Lua source is a single file")
        if source.suffix.lower() != ".lua":
            fail("Lua source file must use the .lua extension")
        relative = PurePosixPath(target_file.replace("\\", "/"))
        if target_prefix:
            relative = PurePosixPath(target_prefix) / relative
        destination = safe_destination(staging, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return 1

    if source.is_file():
        if source.suffix.lower() != ".lua":
            fail("Lua source file must use the .lua extension")
        relative = PurePosixPath(target_prefix) / source.name if target_prefix else PurePosixPath(source.name)
        destination = safe_destination(staging, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return 1

    files = [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".lua"]
    if not files:
        fail(f"no .lua files found under {source}")
    count = 0
    for lua_file in files:
        relative_source = lua_file.relative_to(source)
        relative = PurePosixPath(target_prefix) / PurePosixPath(relative_source.as_posix()) if target_prefix else PurePosixPath(relative_source.as_posix())
        destination = safe_destination(staging, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lua_file, destination)
        count += 1
    return count


def backup_file(path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + f".bak.{stamp}")
    shutil.copy2(path, backup)
    return backup


def lua_inject(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    source = Path(args.lua_source).expanduser()
    if not source.is_file() and not source.is_dir():
        fail(f"Lua source not found: {source}")
    output = Path(args.output).expanduser() if args.output else pak.with_name(pak.stem + ".lua.pak")
    if output.resolve() == pak.resolve():
        if not args.in_place:
            fail("refusing to overwrite the original PAK; choose --output or add --in-place")
        backup = backup_file(pak)
        print(f"Backup created: {backup}")

    binary = repak_binary(args.repak)
    with tempfile.TemporaryDirectory(prefix="ue4tool-") as temp_name:
        staging = Path(temp_name) / "pak-files"
        unpack_cmd = ["unpack", str(pak), "--output", str(staging), "--strip-prefix", args.strip_prefix, "--force", "--quiet"]
        run_repak(binary, args.aes_key, unpack_cmd)
        count = copy_lua_files(source, staging, args.target_prefix, args.target_file)
        pack_cmd = ["pack", str(staging), str(output), "--version", args.version, "--mount-point", args.mount_point]
        if args.compression:
            pack_cmd += ["--compression", args.compression]
        run_repak(binary, None, pack_cmd)
    print(f"Injected {count} Lua file(s) into {output}")
    if args.aes_key:
        print("Note: repak can read with the supplied key, but repak-created output is not encrypted by this tool.", file=sys.stderr)


# ---------- Standard Lua 5.3 batch helpers ----------

def find_luac(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("LUAC_BIN"):
        candidates.append(os.environ["LUAC_BIN"])
    candidates += ["luac5.3", "luac", "/data/data/com.termux/files/usr/bin/luac5.3", "/usr/bin/luac5.3"]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved = candidate if os.path.sep in candidate else shutil.which(candidate)
        if not resolved:
            continue
        try:
            probe = subprocess.run([resolved, "-v"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        version = (probe.stdout + probe.stderr).strip()
        if "5.3" in version:
            return resolved
    fail("Lua 5.3 compiler not found. Install it with `pkg install lua53`, or pass --luac /path/to/luac5.3")


def lua_files(source: Path) -> list[tuple[Path, PurePosixPath]]:
    if source.is_file():
        if source.suffix.lower() != ".lua":
            fail(f"Lua source must use .lua extension: {source}")
        return [(source, PurePosixPath(source.name))]
    source = require_dir(source, "Lua source directory")
    result: list[tuple[Path, PurePosixPath]] = []
    for path in sorted(source.rglob("*.lua")):
        if path.is_file():
            result.append((path, PurePosixPath(path.relative_to(source).as_posix())))
    if not result:
        fail(f"no .lua files found under {source}")
    return result


def bytecode_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x1bLua"
    except OSError:
        return False


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{size}B"


def save_lua_report(report_path: Path | None, mode: str, entries: list[dict[str, object]], started: float) -> None:
    if report_path is None:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    success = sum(1 for item in entries if item["status"] == "ok")
    report = {
        "tool": APP_NAME,
        "mode": mode,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - started, 3),
        "summary": {"total": len(entries), "success": success, "failed": len(entries) - success},
        "files": entries,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Report written to {report_path}")


def run_lua_batch(args: argparse.Namespace, compile_mode: bool) -> None:
    source = Path(args.source).expanduser()
    files = lua_files(source)
    compiler = find_luac(args.luac)
    output_root = Path(args.out).expanduser() if compile_mode else None
    if compile_mode:
        output_root.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report).expanduser() if args.report else None
    started = time.time()
    entries: list[dict[str, object]] = []

    for path, relative in files:
        started_file = time.time()
        item: dict[str, object] = {
            "file": relative.as_posix(),
            "input_bytes": path.stat().st_size,
            "status": "failed",
        }
        if bytecode_file(path):
            item.update({"status": "skipped", "reason": "already Lua bytecode", "elapsed_seconds": round(time.time() - started_file, 3)})
            entries.append(item)
            print(f"SKIP  {relative} (already bytecode)")
            continue

        try:
            if compile_mode:
                assert output_root is not None
                destination = safe_destination(output_root, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and not args.force:
                    raise FileExistsError(f"output exists: {destination}; use --force")
                command = [compiler, "-o", str(destination), str(path)]
            else:
                destination = None
                command = [compiler, "-p", str(path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                message = (result.stderr or result.stdout).strip().splitlines()
                raise RuntimeError(" ".join(message)[-500:] or f"compiler exit {result.returncode}")
            item["status"] = "ok"
            if destination is not None:
                item["output"] = destination.as_posix()
                item["output_bytes"] = destination.stat().st_size
            print(f"OK    {relative}" + (f" -> {destination}" if destination else ""))
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            item["error"] = str(exc)
            print(f"FAIL  {relative}: {exc}", file=sys.stderr)
        item["elapsed_seconds"] = round(time.time() - started_file, 3)
        entries.append(item)

    save_lua_report(report_path, "compile" if compile_mode else "validate", entries, started)
    success = sum(1 for item in entries if item["status"] == "ok")
    failed = sum(1 for item in entries if item["status"] == "failed")
    skipped = sum(1 for item in entries if item["status"] == "skipped")
    print(f"Summary: {success} OK, {failed} failed, {skipped} skipped, {len(entries)} total")
    if failed:
        raise SystemExit(1)


def lua_validate(args: argparse.Namespace) -> None:
    run_lua_batch(args, compile_mode=False)


def lua_compile(args: argparse.Namespace) -> None:
    run_lua_batch(args, compile_mode=True)


def lua_zip(args: argparse.Namespace) -> None:
    source = require_dir(Path(args.source).expanduser(), "Lua source directory")
    output = Path(args.output).expanduser()
    files = [p for p in sorted(source.rglob("*")) if p.is_file()]
    if not files:
        fail(f"source directory is empty: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = safe_member_path(path.relative_to(source).as_posix())
            archive.write(path, relative.as_posix())
    print(f"Packaged {len(files)} files into {output} ({format_bytes(output.stat().st_size)})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Authorized UE4 OBB/PAK/Lua helper for Termux")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("obb-list", help="list a ZIP-compatible OBB")
    p.add_argument("obb")
    p.set_defaults(func=lambda a: obb_list(Path(a.obb).expanduser()))

    p = sub.add_parser("obb-unpack", help="extract a ZIP-compatible OBB")
    p.add_argument("obb")
    p.add_argument("--out", "-o", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=lambda a: obb_unpack(Path(a.obb).expanduser(), Path(a.out).expanduser(), a.force))

    def add_pak_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repak", help="repak executable path; default: PATH or REPAK_BIN")
        p.add_argument("--aes-key", help="owner-supplied UE4 AES key for reading an encrypted PAK")

    p = sub.add_parser("pak-info", help="show PAK metadata")
    p.add_argument("pak"); add_pak_common(p); p.set_defaults(func=pak_info)

    p = sub.add_parser("pak-list", help="list files in a PAK")
    p.add_argument("pak"); p.add_argument("--strip-prefix", default="../../../"); add_pak_common(p); p.set_defaults(func=pak_list)

    p = sub.add_parser("pak-hash", help="print SHA-256 hashes for files in a PAK")
    p.add_argument("pak"); p.add_argument("--strip-prefix", default="../../../"); add_pak_common(p); p.set_defaults(func=pak_hash)

    p = sub.add_parser("pak-unpack", help="extract a PAK")
    p.add_argument("pak"); p.add_argument("--out", "-o"); p.add_argument("--strip-prefix", default="../../../"); p.add_argument("--quiet", action="store_true"); add_pak_common(p); p.set_defaults(func=pak_unpack)

    p = sub.add_parser("pak-pack", help="pack a directory into a PAK")
    p.add_argument("source"); p.add_argument("output"); p.add_argument("--version", default="v8b", help="repak version, e.g. v7, v8a, v8b, v9, v11"); p.add_argument("--compression", choices=["zlib", "gzip", "zstd", "lz4", "oodle"]); p.add_argument("--mount-point", default="../../../"); p.add_argument("--quiet", action="store_true"); p.add_argument("--repak"); p.set_defaults(func=pak_pack)

    p = sub.add_parser("lua-inject", help="unpack a PAK, copy Lua files, and repack it")
    p.add_argument("pak"); p.add_argument("lua_source", help="Lua file or directory containing .lua files"); p.add_argument("--output", "-o"); p.add_argument("--in-place", action="store_true", help="allow --output to equal the input after creating a backup"); p.add_argument("--target-prefix", default="Script", help="directory inside the PAK for injected Lua files"); p.add_argument("--target-file", help="target filename for a single Lua source file"); p.add_argument("--strip-prefix", default="../../../"); p.add_argument("--mount-point", default="../../../"); p.add_argument("--version", default="v8b"); p.add_argument("--compression", choices=["zlib", "gzip", "zstd", "lz4", "oodle"]); add_pak_common(p); p.set_defaults(func=lua_inject)

    def add_lua_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("source", help="Lua file or directory")
        p.add_argument("--luac", help="path to a Lua 5.3 compiler; default: LUAC_BIN, PATH")
        p.add_argument("--report", help="write a JSON operation report")

    p = sub.add_parser("lua-validate", help="syntax-check Lua 5.3 source files")
    add_lua_common(p); p.set_defaults(func=lua_validate)

    p = sub.add_parser("lua-compile", help="compile Lua 5.3 source files to bytecode")
    add_lua_common(p); p.add_argument("--out", "-o", required=True, help="output directory"); p.add_argument("--force", action="store_true"); p.set_defaults(func=lua_compile)

    p = sub.add_parser("lua-zip", help="ZIP a Lua output directory")
    p.add_argument("source"); p.add_argument("output"); p.set_defaults(func=lua_zip)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
