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
import os
import re
import sys
import time
import traceback
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
VERSION = "1.2.0"
MANIFEST_NAME = ".pakforge-manifest.json"


def native_log_directory() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "pakforge" / "logs"


class NativeOperationLog:
    """Local JSONL operation log for the native PakForge CLI."""

    def __init__(self, command: str, args: argparse.Namespace):
        self.path: Path | None = None
        self.handle = None
        try:
            root = native_log_directory()
            root.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            self.path = root / f"operation-{stamp}-{os.getpid()}.jsonl"
            self.handle = self.path.open("a", encoding="utf-8")
            arguments = {}
            for key, value in vars(args).items():
                if key == "func":
                    continue
                if re.search(r"(?:aes|api|access|auth|private|secret|token|password|key)", key, re.IGNORECASE):
                    arguments[key] = "<redacted>"
                else:
                    arguments[key] = str(value)
            self.event("operation_started", command=command, arguments=arguments, version=VERSION, python=sys.version.split()[0], termux=bool(os.environ.get("PREFIX")))
        except OSError:
            self.path = None
            self.handle = None

    def event(self, name: str, **fields: object) -> None:
        if self.handle is None:
            return
        text_fields = {}
        for key, value in fields.items():
            text = str(value)
            text = re.sub(r"(--aes-key(?:=|\s+))([^\s]+)", r"\1<redacted>", text, flags=re.IGNORECASE)
            text_fields[key] = text if len(text) <= 6000 else text[-6000:]
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": name, **text_fields}
        try:
            self.handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.handle.flush()
        except OSError:
            pass

    def close(self) -> None:
        if self.handle is not None:
            try:
                self.handle.close()
            except OSError:
                pass
            self.handle = None


def show_native_logs(args: argparse.Namespace) -> None:
    root = native_log_directory()
    logs = sorted(root.glob("operation-*.jsonl")) if root.is_dir() else []
    print(f"Log directory: {root}")
    if not logs:
        print("No operation logs found yet.")
        return
    for path in logs[-max(1, args.limit):]:
        print(path)
    if args.tail:
        latest = logs[-1]
        lines = latest.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"\n--- latest log: {latest} ---")
        print("\n".join(lines[-args.tail:]))


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


def open_pak_auto(path: Path, requested_od: bool = False) -> tuple[TencentPakFile, bool, list[dict]]:
    attempts: list[dict] = []
    modes = [True] if requested_od else [False, True]
    for is_od in modes:
        try:
            pak = TencentPakFile(path, is_od=is_od)
            return pak, is_od, attempts
        except Exception as exc:
            attempts.append({"is_od": is_od, "error": f"{type(exc).__name__}: {exc}"})
    details = "; ".join(f"is_od={item['is_od']}: {item['error']}" for item in attempts)
    raise SystemExit(f"PAK format was not recognized. Attempts: {details}")


def capability_payload(path: Path, pak: TencentPakFile, is_od: bool) -> dict:
    rows = inventory(pak)
    compression = {}
    encryption = {}
    for row in rows:
        compression[row["compression"]] = compression.get(row["compression"], 0) + 1
        encryption[row["encryption"]] = encryption.get(row["encryption"], 0) + 1
    return {
        "status": "supported",
        "pak": str(path),
        "parser_mode": "od" if is_od else "standard",
        "pak_version": pak._pak_info.version,
        "mount_point": str(pak._mount_point),
        "entries": len(rows),
        "compression": dict(sorted(compression.items())),
        "encryption": dict(sorted(encryption.items())),
        "index_encrypted": bool(pak._pak_info.index_encrypted),
        "zstd_dictionary": bool(getattr(pak, "_zstd_dict", None)),
        "capabilities": {
            "unpack": True,
            "repack": True,
            "lua_target_inject": True,
            "manifest": True,
            "post_repack_verify": True,
        },
    }


def detect_command(args: argparse.Namespace) -> None:
    path = require_file(args.pak, "PAK")
    try:
        pak, is_od, attempts = open_pak_auto(path, args.is_od)
        payload = capability_payload(path, pak, is_od)
        payload["attempts"] = attempts
    except SystemExit as exc:
        payload = {
            "status": "unsupported_or_invalid",
            "pak": str(path),
            "error": str(exc),
            "recommendations": [
                "Confirm the file is a complete PAK, not a split or downloaded partial file.",
                "Try the compatibility `tool info` command for standard repak-supported PAKs.",
                "If the PAK is encrypted, provide the known project key through the supported command option.",
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Status: {payload['status']}")
            print(f"PAK: {path}")
            print(f"Reason: {payload['error']}")
            print("Next checks:")
            for item in payload["recommendations"]:
                print(f"- {item}")
        raise SystemExit(2)
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(f"Status: {payload['status']}")
    print(f"Parser mode: {payload['parser_mode']}")
    print(f"PAK version: {payload['pak_version']}")
    print(f"Mount point: {payload['mount_point']}")
    print(f"Entries: {payload['entries']}")
    print("Compression: " + ", ".join(f"{name}={count}" for name, count in payload["compression"].items()))
    print("Encryption: " + ", ".join(f"{name}={count}" for name, count in payload["encryption"].items()))
    print(f"Index encrypted: {'yes' if payload['index_encrypted'] else 'no'}")
    print(f"ZSTD dictionary: {'yes' if payload['zstd_dictionary'] else 'no'}")
    print("Recommended workflow: lua-pipeline" if payload["capabilities"]["lua_target_inject"] else "Recommended workflow: inspect only")


def lua_pipeline_command(args: argparse.Namespace) -> None:
    source = require_file(args.pak, "Source PAK")
    lua_root = require_dir(args.lua_dir, "Lua directory")
    lua_files = sorted(path for path in lua_root.rglob("*.lua") if path.is_file())
    if not lua_files:
        raise SystemExit(f"No .lua files found in: {lua_root}")
    target_prefix = normalize_target_prefix(args.target_prefix or "Script")
    output = Path(args.output).expanduser()
    refuse_existing(output, args.overwrite)
    pak, is_od, attempts = open_pak_auto(source, args.is_od)
    report = {
        "tool": APP_NAME,
        "version": VERSION,
        "source_pak": str(source),
        "output_pak": str(output),
        "lua_directory": str(lua_root),
        "lua_files": [path.relative_to(lua_root).as_posix() for path in lua_files],
        "target_prefix": target_prefix,
        "parser_mode": "od" if is_od else "standard",
        "attempts": attempts,
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        report_path = Path(args.report).expanduser() if args.report else output.with_suffix(output.suffix + ".plan.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report["status"] = "planned"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Dry run: {len(lua_files)} Lua file(s) would be added under {target_prefix}")
        print(f"Plan: {report_path}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    count = repack_pak_file_full(pak, lua_root, output, target_path=target_prefix, force_add=True)
    if count <= 0:
        raise SystemExit("Lua pipeline produced no files.")
    verified = TencentPakFile(output, is_od=is_od)
    verified_paths = {row["path"] for row in inventory(verified)}
    expected = {f"{target_prefix}/{relative}" for relative in report["lua_files"]}
    missing = sorted(expected - verified_paths)
    if missing:
        raise SystemExit("Post-repack verification failed; missing Lua paths: " + ", ".join(missing[:10]))
    report["status"] = "verified"
    report["injected_count"] = count
    report["verified_count"] = len(expected)
    report_path = Path(args.report).expanduser() if args.report else output.with_suffix(output.suffix + ".lua-report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Lua pipeline complete: {count} file(s) added under {target_prefix}")
    print(f"Verified output: {output}")
    print(f"Report: {report_path}")


def info_command(args: argparse.Namespace) -> None:
    pak_path = require_file(args.pak, "PAK")
    pak, detected_od, _ = open_pak_auto(pak_path, args.is_od)
    rows = inventory(pak)
    compression = {}
    encryption = {}
    for row in rows:
        compression[row["compression"]] = compression.get(row["compression"], 0) + 1
        encryption[row["encryption"]] = encryption.get(row["encryption"], 0) + 1
    summary = {
        "compression": dict(sorted(compression.items())),
        "encryption": dict(sorted(encryption.items())),
        "encrypted_index": bool(pak._pak_info.index_encrypted),
        "zstd_dictionary": bool(getattr(pak, "_zstd_dict", None)),
    }
    payload = {
        "tool": APP_NAME,
        "version": VERSION,
        "pak": str(pak_path),
        "parser_mode": "od" if detected_od else "standard",
        "pak_version": pak._pak_info.version,
        "mount_point": str(pak._mount_point),
        "index_encrypted": summary["encrypted_index"],
        "zstd_dictionary": summary["zstd_dictionary"],
        "summary": summary,
        "entries": rows,
    }
    print(f"PAK: {pak_path}")
    print(f"Version: {pak._pak_info.version}")
    print(f"Mount point: {pak._mount_point}")
    print(f"Entries: {len(rows)}")
    print(f"Logical size: {sum(row['size'] for row in rows):,} bytes")
    print(f"Index encrypted: {'yes' if summary['encrypted_index'] else 'no'}")
    print(f"ZSTD dictionary: {'yes' if summary['zstd_dictionary'] else 'no'}")
    print("Compression: " + ", ".join(f"{name}={count}" for name, count in summary["compression"].items()))
    print("Encryption: " + ", ".join(f"{name}={count}" for name, count in summary["encryption"].items()))
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
    pak, _, _ = open_pak_auto(pak_path, args.is_od)
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


def normalize_target_prefix(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace('\\\\', '/').replace('\\', '/').strip('/')
    parts = [part for part in normalized.split('/') if part not in ('', '.')]
    if not parts or any(part == '..' for part in parts):
        raise SystemExit("Target prefix must be a relative PAK directory without '..'.")
    return '/'.join(parts)


def repack_command(args: argparse.Namespace) -> None:
    source_pak = require_file(args.source_pak, "Source PAK")
    edited = require_dir(args.edited_dir, "Edited directory")
    output = Path(args.output).expanduser()
    refuse_existing(output, args.overwrite)
    pak, _, _ = open_pak_auto(source_pak, args.is_od)
    output.parent.mkdir(parents=True, exist_ok=True)
    target_prefix = normalize_target_prefix(args.target_prefix)
    if target_prefix:
        count = repack_pak_file_full(pak, edited, output, target_path=target_prefix, force_add=True)
        print(f"Added/updated files under PAK path: {target_prefix}")
    elif args.full:
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

    detect = sub.add_parser("detect", help="detect PAK mode and report supported capabilities")
    detect.add_argument("pak")
    detect.add_argument("--json", action="store_true")
    detect.add_argument("--is-od", action="store_true")
    detect.set_defaults(func=detect_command)

    lua = sub.add_parser("lua-pipeline", help="detect, inject Lua files, repack, and verify")
    lua.add_argument("--pak", required=True)
    lua.add_argument("--lua-dir", required=True)
    lua.add_argument("--output", required=True)
    lua.add_argument("--target-prefix", default="Script")
    lua.add_argument("--report")
    lua.add_argument("--dry-run", action="store_true")
    lua.add_argument("--verify", action="store_true", help="verify the repacked PAK (verification is enabled by default)")
    lua.add_argument("--overwrite", action="store_true")
    lua.add_argument("--is-od", action="store_true")
    lua.set_defaults(func=lua_pipeline_command)

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
    repack.add_argument("--target-prefix", help="add edited files under this relative directory inside the PAK")
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

    logs = sub.add_parser("logs", help="list structured PakForge operation logs")
    logs.add_argument("--limit", type=int, default=10)
    logs.add_argument("--tail", type=int, default=0)
    logs.set_defaults(func=show_native_logs)
    return cli


def main() -> int:
    args = parser().parse_args()
    if args.command == "logs":
        args.func(args)
        return 0
    operation = NativeOperationLog(args.command or "menu", args)
    try:
        if args.command in (None, "menu"):
            operation.event("menu_started")
            main_menu()
            operation.event("operation_succeeded")
            return 0
        operation.event("handler_started", handler=getattr(args.func, "__name__", str(args.func)))
        args.func(args)
        operation.event("operation_succeeded")
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code:
            operation.event("operation_failed", exit_code=code, error=str(exc), traceback=traceback.format_exc())
            print(f"Operation log saved locally: {operation.path}", file=sys.stderr)
        raise
    except Exception as exc:
        operation.event("unexpected_exception", exit_code=1, error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
        print(f"{APP_NAME}: unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"Operation log saved locally: {operation.path}", file=sys.stderr)
        return 1
    finally:
        operation.event("operation_finished")
        operation.close()


if __name__ == "__main__":
    raise SystemExit(main())
