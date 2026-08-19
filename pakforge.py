#!/usr/bin/env python3
"""PakForge: a Termux PAK parser and repacking utility.

This adapter exposes the bundled parser through a stable CLI while keeping the
repository's existing ``tool``/repak commands available separately.
Use only with PAK files and project assets you own or are authorized to modify.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path, PurePath

try:
    from pakforge_core import (
        TencentPakFile,
        dump_unpacking_log,
        main_menu,
        repack_pak_file_full,
        repack_pak_file_with_block_display,
    )
except ImportError as exc:
    raise SystemExit(
        "PakForge dependencies are missing. Run: "
        "python3 -m pip install rich pytz gmalg pycryptodome zstandard"
    ) from exc

APP_NAME = "PakForge"
VERSION = "1.0.0"
MANIFEST_NAME = ".pakforge-manifest.json"


def require_file(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    return path


def require_dir(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_dir():
        raise SystemExit(f"{label} not found: {path}")
    return path


def refuse_existing(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise SystemExit(f"Output already exists: {path}. Use --overwrite only after keeping a backup.")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def regular_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != MANIFEST_NAME:
            yield path


def create_manifest(directory: Path, output: Path | None = None) -> Path:
    directory = require_dir(directory, "Directory").resolve()
    output = output or directory / MANIFEST_NAME
    payload = {
        "format": 1,
        "tool": APP_NAME,
        "version": VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [
            {
                "path": path.relative_to(directory).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in regular_files(directory)
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def verify_manifest(directory: Path, manifest: Path | None = None) -> tuple[bool, list[tuple[str, str]]]:
    directory = require_dir(directory, "Directory").resolve()
    manifest = manifest or directory / MANIFEST_NAME
    if not manifest.is_file():
        raise SystemExit(f"Manifest not found: {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    expected = {item["path"]: item for item in payload.get("files", [])}
    issues: list[tuple[str, str]] = []
    for relative, item in expected.items():
        candidate = (directory / Path(*PurePath(relative).parts)).resolve()
        if directory not in candidate.parents and candidate != directory:
            issues.append(("UNSAFE", relative))
        elif not candidate.is_file():
            issues.append(("MISSING", relative))
        elif candidate.stat().st_size != item["size"] or sha256_file(candidate) != item["sha256"]:
            issues.append(("CHANGED", relative))
    for path in regular_files(directory):
        relative = path.relative_to(directory).as_posix()
        if relative not in expected:
            issues.append(("EXTRA", relative))
    return not issues, issues


def manifest_command(args: argparse.Namespace) -> None:
    print(f"Manifest created: {create_manifest(Path(args.directory), Path(args.output) if args.output else None)}")


def verify_command(args: argparse.Namespace) -> None:
    ok, issues = verify_manifest(Path(args.directory), Path(args.manifest) if args.manifest else None)
    if ok:
        print("Manifest verification passed.")
        return
    for status, relative in issues:
        print(f"{status}: {relative}")
    raise SystemExit(2)


def inventory(pak: TencentPakFile) -> list[dict]:
    rows = []
    for directory, files in pak._index.items():
        for name, entry in files.items():
            rows.append({
                "path": (PurePath(directory) / name).as_posix(),
                "size": entry.uncompressed_size,
                "stored_size": entry.size,
                "compression": pak._get_method_str(entry.compression_method, False),
                "encryption": pak._get_method_str(entry.encryption_method, True) if entry.encrypted else "NONE",
                "blocks": len(entry.compressed_blocks),
            })
    return sorted(rows, key=lambda item: item["path"].lower())


def info_command(args: argparse.Namespace) -> None:
    pak_path = require_file(args.pak, "PAK")
    pak = TencentPakFile(pak_path, is_od=args.is_od)
    rows = inventory(pak)
    payload = {
        "tool": APP_NAME,
        "version": VERSION,
        "pak": str(pak_path),
        "pak_version": pak._pak_info.version,
        "mount_point": str(pak._mount_point),
        "entries": rows,
    }
    print(f"PAK: {pak_path}")
    print(f"Version: {pak._pak_info.version}")
    print(f"Mount point: {pak._mount_point}")
    print(f"Entries: {len(rows)}")
    print(f"Logical size: {sum(row['size'] for row in rows):,} bytes")
    if args.export:
        export = Path(args.export).expanduser()
        export.parent.mkdir(parents=True, exist_ok=True)
        export.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Inventory exported: {export}")


def unpack_command(args: argparse.Namespace) -> None:
    pak_path = require_file(args.pak, "PAK")
    output = Path(args.output).expanduser() if args.output else pak_path.with_name(pak_path.stem + "-unpacked")
    if output.exists() and not output.is_dir():
        raise SystemExit(f"Output path exists as a file: {output}")
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise SystemExit(f"Output directory is not empty: {output}. Use --overwrite only after keeping a backup.")
    pak = TencentPakFile(pak_path, is_od=args.is_od)
    pak.dump(output)
    log_path = output / f"Debug_{pak_path.stem}.log"
    dump_unpacking_log(pak, log_path)
    print(f"Extracted to: {output}")
    print(f"Debug log: {log_path}")
    print(f"Manifest: {create_manifest(output)}")


def batch_command(args: argparse.Namespace) -> None:
    source = require_dir(args.pak_dir, "PAK directory")
    output_root = Path(args.output_dir).expanduser()
    pak_files = sorted(source.glob("*.pak"))
    if not pak_files:
        raise SystemExit(f"No .pak files found in: {source}")
    completed = 0
    for pak in pak_files:
        target = output_root / pak.stem
        if target.exists() and any(target.iterdir()) and not args.overwrite:
            print(f"Skipped existing output: {target}")
            continue
        child = argparse.Namespace(pak=str(pak), output=str(target), is_od=args.is_od, overwrite=args.overwrite)
        try:
            unpack_command(child)
            completed += 1
        except Exception as exc:
            print(f"Skipped {pak.name}: {exc}", file=sys.stderr)
    print(f"Batch complete: {completed}/{len(pak_files)} PAK(s) unpacked.")


def repack_command(args: argparse.Namespace) -> None:
    source_pak = require_file(args.source_pak, "Source PAK")
    edited = require_dir(args.edited_dir, "Edited directory")
    output = Path(args.output).expanduser()
    refuse_existing(output, args.overwrite)
    pak = TencentPakFile(source_pak, is_od=args.is_od)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.full:
        count = repack_pak_file_full(pak, edited, output)
    else:
        count = repack_pak_file_with_block_display(pak, edited, output)
    if count <= 0:
        raise SystemExit("No files were repacked.")
    print(f"Repacked {count} file(s) to: {output}")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="pakforge", description="PakForge Termux PAK parser and repacking utility")
    cli.add_argument("--version", action="version", version=f"PakForge {VERSION}")
    sub = cli.add_subparsers(dest="command")
    sub.add_parser("menu", help="open the original interactive PAK menu")

    info = sub.add_parser("info", help="inspect entries, compression, encryption, and sizes")
    info.add_argument("pak")
    info.add_argument("--export")
    info.add_argument("--is-od", action="store_true")
    info.set_defaults(func=info_command)

    unpack = sub.add_parser("unpack", help="extract a Tencent/UE PAK")
    unpack.add_argument("pak")
    unpack.add_argument("output", nargs="?")
    unpack.add_argument("--overwrite", action="store_true")
    unpack.add_argument("--is-od", action="store_true")
    unpack.set_defaults(func=unpack_command)

    batch = sub.add_parser("batch-unpack", help="extract every .pak in a directory")
    batch.add_argument("pak_dir")
    batch.add_argument("output_dir")
    batch.add_argument("--overwrite", action="store_true")
    batch.add_argument("--is-od", action="store_true")
    batch.set_defaults(func=batch_command)

    repack = sub.add_parser("repack", help="repack edited files using a source PAK")
    repack.add_argument("source_pak")
    repack.add_argument("edited_dir")
    repack.add_argument("output")
    repack.add_argument("--full", action="store_true")
    repack.add_argument("--overwrite", action="store_true")
    repack.add_argument("--is-od", action="store_true")
    repack.set_defaults(func=repack_command)

    manifest = sub.add_parser("manifest", help="create a SHA-256 manifest")
    manifest.add_argument("directory")
    manifest.add_argument("--output")
    manifest.set_defaults(func=manifest_command)

    verify = sub.add_parser("verify", help="verify a directory against its manifest")
    verify.add_argument("directory")
    verify.add_argument("--manifest")
    verify.set_defaults(func=verify_command)
    return cli


def main() -> int:
    args = parser().parse_args()
    if args.command in (None, "menu"):
        main_menu()
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
