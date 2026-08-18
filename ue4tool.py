#!/usr/bin/env python3
"""Focused UE4 Termux helper for authorized projects.

Supported workflows are intentionally limited to PAK unpacking, PAK repacking,
and Lua file injection. UE4 PAK binary work is delegated to repak.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

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


def safe_destination(root: Path, relative: str | PurePosixPath) -> Path:
    """Prevent injected paths from escaping the temporary PAK staging folder."""
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


def pak_unpack(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    output_value = args.output_flag or args.output
    output = Path(output_value).expanduser() if output_value else pak.with_suffix("")
    command = ["unpack", str(pak), "--output", str(output), "--strip-prefix", args.strip_prefix, "--force"]
    if args.quiet:
        command.append("--quiet")
    run_repak(repak_binary(args.repak), args.aes_key, command)
    print(f"Unpacked PAK to {output}")


def pak_repack(args: argparse.Namespace) -> None:
    source = require_dir(Path(args.source), "source directory")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["pack", str(source), str(output), "--version", args.version, "--mount-point", args.mount_point]
    if args.compression:
        command += ["--compression", args.compression]
    if args.quiet:
        command.append("--quiet")
    run_repak(repak_binary(args.repak), None, command)
    print(f"Repacked {source} to {output}")


def copy_lua_files(source: Path, staging: Path, target_prefix: str, target_file: str | None) -> int:
    target_prefix = target_prefix.strip("/\\")
    if target_file:
        if source.is_dir():
            fail("--target-file can only be used with one Lua source file")
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
    import datetime as dt
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + f".bak.{stamp}")
    shutil.copy2(path, backup)
    return backup


def lua_inject(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    source = Path(args.lua_source).expanduser()
    if not source.is_file() and not source.is_dir():
        fail(f"Lua source not found: {source}")
    output_value = args.output_flag or args.output
    output = Path(output_value).expanduser() if output_value else pak.with_name(pak.stem + ".lua.pak")
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
        print("Note: repak can read with the supplied key, but this tool does not create encrypted output.", file=sys.stderr)


def add_repak_common(parser: argparse.ArgumentParser, *, aes: bool = False) -> None:
    parser.add_argument("--repak", help="repak executable path; default: PATH or REPAK_BIN")
    if aes:
        parser.add_argument("--aes-key", help="owner-supplied UE4 AES key for reading an encrypted PAK")


def add_pack_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--version", default="v8b", help="repak version, for example v7, v8a, v8b, v9, or v11")
    parser.add_argument("--compression", choices=["zlib", "gzip", "zstd", "lz4", "oodle"])
    parser.add_argument("--mount-point", default="../../../")
    parser.add_argument("--quiet", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Focused UE4 PAK unpack, repack, and Lua inject tool for Termux")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("unpack", help="extract a UE4 PAK; usage: ue4tool unpack game.pak [folder]")
    p.add_argument("pak")
    p.add_argument("output", nargs="?", help="output directory; default: PAK filename without extension")
    p.add_argument("--out", "-o", dest="output_flag", help="same as the optional output path")
    p.add_argument("--strip-prefix", default="../../../")
    p.add_argument("--quiet", action="store_true")
    add_repak_common(p, aes=True)
    p.set_defaults(func=pak_unpack)

    p = sub.add_parser("repack", help="create a PAK; usage: ue4tool repack folder new.pak")
    p.add_argument("source", help="unpacked PAK directory")
    p.add_argument("output", help="new PAK path")
    add_pack_options(p)
    add_repak_common(p)
    p.set_defaults(func=pak_repack)

    p = sub.add_parser("inject", help="inject Lua; usage: ue4tool inject game.pak lua-folder [new.pak]")
    p.add_argument("pak")
    p.add_argument("lua_source", help="one Lua file or a directory containing Lua files")
    p.add_argument("output", nargs="?", help="new PAK path; default: <input>.lua.pak")
    p.add_argument("--output", "-o", dest="output_flag", help="same as the optional output path")
    p.add_argument("--in-place", action="store_true", help="allow replacing the input after creating a backup")
    p.add_argument("--target-prefix", default="Script", help="directory inside the PAK for injected Lua files")
    p.add_argument("--target-file", help="target filename for one Lua source file")
    p.add_argument("--strip-prefix", default="../../../")
    p.add_argument("--mount-point", default="../../../")
    p.add_argument("--version", default="v8b")
    p.add_argument("--compression", choices=["zlib", "gzip", "zstd", "lz4", "oodle"])
    add_repak_common(p, aes=True)
    p.set_defaults(func=lua_inject)

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
