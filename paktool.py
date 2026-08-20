#!/usr/bin/env python3
"""Simple UE4 PAK utility for Termux.

Use only with PAK/OBB files that you own or are authorized to modify.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath

# The parser core contains the configured SM4 derivation secrets and UE4 serialization.
from paktool_core import TencentPakFile, repack_pak_file_full


def fail(message: str, code: int = 2) -> None:
    print(f"paktool: {message}", file=sys.stderr)
    raise SystemExit(code)


def require_file(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_file():
        fail(f"PAK file not found: {path}")
    return path


def require_dir(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_dir():
        fail(f"directory not found: {path}")
    return path


def open_pak(path: Path, is_od: bool = False) -> tuple[TencentPakFile, bool]:
    attempts = []
    for mode in ([True] if is_od else [False, True]):
        try:
            return TencentPakFile(path, is_od=mode), mode
        except Exception as exc:
            attempts.append(f"is_od={mode}: {type(exc).__name__}: {exc}")
    fail("could not parse PAK; " + "; ".join(attempts), 1)


def logical_entries(pak: TencentPakFile) -> list[dict]:
    rows = []
    for directory, files in pak._index.items():
        for name, entry in files.items():
            path = (PurePosixPath(str(directory).replace("\\", "/")) / name).as_posix()
            rows.append({
                "path": path,
                "size": entry.uncompressed_size,
                "stored": entry.size,
                "compression": pak._get_method_str(entry.compression_method, False),
                "encryption": pak._get_method_str(entry.encryption_method, True) if entry.encrypted else "NONE",
            })
    return sorted(rows, key=lambda row: row["path"].lower())


def normalize_path(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        fail(f"unsafe PAK path: {value}")
    normalized = path.as_posix().lstrip("./")
    if not normalized or normalized == ".":
        fail(f"invalid PAK path: {value}")
    return normalized


def refuse_output(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        fail(f"output already exists: {path}; use --overwrite if intentional")
    if path.exists() and path.is_dir():
        fail(f"output must be a file path, not a directory: {path}")


def info_command(args: argparse.Namespace) -> None:
    source = require_file(args.pak)
    pak, is_od = open_pak(source, args.is_od)
    rows = logical_entries(pak)
    print(f"PAK: {source}")
    print(f"Version: {pak._pak_info.version}")
    print(f"Parser: {'OD' if is_od else 'standard'}")
    print(f"Mount point: {pak._mount_point}")
    print(f"Entries: {len(rows)}")
    for row in rows:
        print(f"{row['path']}\t{row['size']} bytes\t{row['compression']}\t{row['encryption']}")


def unpack_command(args: argparse.Namespace) -> None:
    source = require_file(args.pak)
    output = Path(args.output).expanduser() if args.output else source.with_name(source.stem + "-unpacked")
    if output.exists() and not output.is_dir():
        fail(f"output is not a directory: {output}")
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        fail(f"output directory is not empty: {output}; use --overwrite if intentional")
    output.mkdir(parents=True, exist_ok=True)
    pak, is_od = open_pak(source, args.is_od)
    pak.dump(output, workers=max(1, args.workers))
    print(f"Unpacked {len(logical_entries(pak))} file(s) to {output}")
    print(f"Parser: {'OD' if is_od else 'standard'}")


def repack_command(args: argparse.Namespace) -> None:
    source = require_file(args.source_pak)
    edited = require_dir(args.edited_dir)
    output = Path(args.output).expanduser()
    refuse_output(output, args.overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    pak, is_od = open_pak(source, args.is_od)
    count = repack_pak_file_full(pak, edited, output, workers=max(1, args.workers))
    if count <= 0 or not output.is_file():
        fail("no files were repacked")
    verified, verified_od = open_pak(output, args.is_od)
    print(f"Repacked {count} file(s) to {output}")
    print(f"Verified: {len(logical_entries(verified))} entries; parser={'OD' if verified_od else 'standard'}")


def delete_command(args: argparse.Namespace) -> None:
    source = require_file(args.source_pak)
    output = Path(args.output).expanduser()
    refuse_output(output, args.overwrite)
    requested = [normalize_path(value) for value in args.paths]
    if len({value.lower() for value in requested}) != len(requested):
        fail("duplicate delete paths were supplied")
    pak, is_od = open_pak(source, args.is_od)
    rows = logical_entries(pak)
    available = {row["path"]: row["path"] for row in rows}
    lower_available = {key.lower(): value for key, value in available.items()}
    resolved = []
    for value in requested:
        match = lower_available.get(value.lower())
        if match is None:
            basename_matches = [path for path in available.values() if path.lower().endswith("/" + value.lower())]
            if len(basename_matches) == 1:
                match = basename_matches[0]
            elif len(basename_matches) > 1:
                fail(f"ambiguous filename '{value}'; use its full logical path")
        if match is None:
            fail(f"PAK entry not found: {value}")
        resolved.append(match)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="paktool-delete-") as temp_dir:
        empty_edit = Path(temp_dir) / "empty-edit"
        empty_edit.mkdir()
        count = repack_pak_file_full(
            pak,
            empty_edit,
            output,
            workers=max(1, args.workers),
            delete_paths=set(resolved),
        )
    if count <= 0 or not output.is_file():
        fail("no entries were deleted")
    verified, verified_od = open_pak(output, args.is_od)
    remaining = {row["path"].lower() for row in logical_entries(verified)}
    still_present = [path for path in resolved if path.lower() in remaining]
    if still_present:
        output.unlink(missing_ok=True)
        fail("verification failed; deleted entries remain: " + ", ".join(still_present), 1)
    print(f"Deleted {len(resolved)} file(s)")
    print(f"Verified output: {output}; parser={'OD' if verified_od else 'standard'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool", description="Simple UE4 PAK tool for Termux")
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", aliases=["list"], help="list PAK entries")
    info.add_argument("pak")
    info.add_argument("--is-od", action="store_true")
    info.set_defaults(func=info_command)

    unpack = sub.add_parser("unpack", help="extract a PAK")
    unpack.add_argument("pak")
    unpack.add_argument("output", nargs="?")
    unpack.add_argument("--overwrite", action="store_true")
    unpack.add_argument("--workers", type=int, default=4)
    unpack.add_argument("--is-od", action="store_true")
    unpack.set_defaults(func=unpack_command)

    repack = sub.add_parser("repack", help="repack edited files into a new PAK")
    repack.add_argument("source_pak")
    repack.add_argument("edited_dir")
    repack.add_argument("output")
    repack.add_argument("--overwrite", action="store_true")
    repack.add_argument("--workers", type=int, default=4)
    repack.add_argument("--is-od", action="store_true")
    repack.set_defaults(func=repack_command)

    delete = sub.add_parser("delete", help="delete selected logical entries into a new PAK")
    delete.add_argument("source_pak")
    delete.add_argument("paths", nargs="+")
    delete.add_argument("output")
    delete.add_argument("--overwrite", action="store_true")
    delete.add_argument("--workers", type=int, default=4)
    delete.add_argument("--is-od", action="store_true")
    delete.set_defaults(func=delete_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except SystemExit:
        raise
    except Exception as exc:
        print(f"paktool: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

