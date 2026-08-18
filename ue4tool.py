#!/usr/bin/env python3
"""Friendly UE4 Termux helper for authorized projects.

The tool supports PAK unpacking, PAK repacking, and Lua injection. Running
`tool` without a subcommand opens a guided menu.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
from urllib import request as urlrequest
from urllib import error as urlerror
from urllib.parse import urlparse

APP_NAME = "tool"
DOWNLOAD_DIR = Path("/sdcard/Download")
REPORT_ENDPOINT_ENV = "UE4TOOL_REPORT_ENDPOINT"


class ToolError(RuntimeError):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def fail(message: str, code: int = 2) -> None:
    raise ToolError(message, code)


def sanitize_diagnostic_text(text: str) -> str:
    text = re.sub(r"--aes-key(?:=|\s+)[^\s]+", "--aes-key <redacted>", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(aes[_ -]?key\s*[:=]\s*)[^\s,;]+", r"\1<redacted>", text)
    text = re.sub(r"(?:/|~/?)[^\s,;]+", "<path>", text)
    return text


def write_diagnostic(command: str, error: str, code: int) -> Path:
    report_dir = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP_NAME
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"error-{int(time.time())}.json"
    payload = {
        "tool": APP_NAME,
        "command": command,
        "error": sanitize_diagnostic_text(error),
        "exit_code": code,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "termux": bool(os.environ.get("PREFIX")),
        "privacy": "No PAK contents, Lua source, AES keys, or full file paths are stored.",
    }
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return report


def report_consent_file() -> Path:
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / "ue4tool" / "report_consent"


def reporting_consent() -> bool:
    """Read or request the user's one-time permission for anonymous reporting."""
    consent_path = report_consent_file()
    try:
        saved = consent_path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        saved = ""

    if saved in {"yes", "no"}:
        return saved == "yes"

    try:
        answer = input("Send anonymous bug report? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    consent = "yes" if answer in {"y", "yes"} else "no"
    try:
        consent_path.parent.mkdir(parents=True, exist_ok=True)
        consent_path.write_text(consent + "\n", encoding="utf-8")
    except OSError:
        return False
    return consent == "yes"


def tool_version() -> str:
    project = Path(__file__).resolve().parent
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if revision.returncode == 0 and revision.stdout.strip():
            return f"git-{revision.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _send_report(report_path: Path) -> bool:
    """Send only the sanitized diagnostic allowlist after explicit user consent."""
    if os.environ.get("TOOL_NO_REPORT") == "1":
        return False

    endpoint = os.environ.get(REPORT_ENDPOINT_ENV, "").strip()
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    if not reporting_consent():
        return False

    try:
        local_report = json.loads(report_path.read_text(encoding="utf-8"))
        payload = {
            "operation": local_report["command"],
            "error_message": local_report["error"],
            "tool_version": tool_version(),
            "exit_code": int(local_report["exit_code"]),
            "platform": "Termux Android" if local_report.get("termux") else sys.platform,
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urlrequest.Request(
            endpoint,
            data=encoded,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(request, timeout=5) as response:
            if response.status not in {200, 201, 202}:
                return False
        print("Anonymous diagnostic report sent.", file=sys.stderr)
        return True
    except (KeyError, OSError, ValueError, urlerror.URLError):
        print("Anonymous diagnostic report could not be sent.", file=sys.stderr)
        return False


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
        fail("repak was not found. Run bash install-termux.sh, then try again")
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
    display_command = [binary]
    if aes_key:
        display_command += ["--aes-key", "<redacted>"]
    display_command += args
    print("$ " + " ".join(subprocess.list2cmdline([part]) for part in display_command))
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
    print(f"[1/1] Unpacking {pak.name}...")
    command = ["unpack", str(pak), "--output", str(output), "--strip-prefix", args.strip_prefix, "--force"]
    if args.quiet:
        command.append("--quiet")
    run_repak(repak_binary(args.repak), args.aes_key, command)
    print(f"Done. Files extracted to: {output}")


def pak_repack(args: argparse.Namespace) -> None:
    source = require_dir(Path(args.source), "source directory")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"[1/1] Repacking {source}...")
    command = ["pack", str(source), str(output), "--version", args.version, "--mount-point", args.mount_point]
    if args.compression:
        command += ["--compression", args.compression]
    if args.quiet:
        command.append("--quiet")
    run_repak(repak_binary(args.repak), None, command)
    print(f"Done. PAK created at: {output}")


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


def lua_inject(args: argparse.Namespace) -> None:
    pak = require_file(Path(args.pak), "PAK")
    source = Path(args.lua_source).expanduser()
    if not source.is_file() and not source.is_dir():
        fail(f"Lua source not found: {source}")
    output_value = args.output_flag or args.output
    output = Path(output_value).expanduser() if output_value else pak.with_name(pak.stem + ".lua.pak")
    if output.resolve() == pak.resolve():
        if not args.in_place:
            fail("refusing to overwrite the original PAK; add --in-place to confirm direct replacement")
        print("Warning: in-place mode will replace the original PAK without creating a backup.", file=sys.stderr)

    binary = repak_binary(args.repak)
    with tempfile.TemporaryDirectory(prefix="tool-") as temp_name:
        staging = Path(temp_name) / "pak-files"
        print("[1/3] Unpacking source PAK...")
        unpack_cmd = ["unpack", str(pak), "--output", str(staging), "--strip-prefix", args.strip_prefix, "--force", "--quiet"]
        run_repak(binary, args.aes_key, unpack_cmd)
        print("[2/3] Copying Lua files...")
        count = copy_lua_files(source, staging, args.target_prefix, args.target_file)
        print(f"      Lua files selected: {count}")
        print("[3/3] Creating output PAK...")
        pack_cmd = ["pack", str(staging), str(output), "--version", args.version, "--mount-point", args.mount_point]
        if args.compression:
            pack_cmd += ["--compression", args.compression]
        run_repak(binary, None, pack_cmd)
    print(f"Done. Injected {count} Lua file(s) into: {output}")
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
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Friendly UE4 PAK unpack, repack, and Lua inject tool for Termux")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("unpack", help="extract a UE4 PAK; usage: tool unpack game.pak [folder]")
    p.add_argument("pak")
    p.add_argument("output", nargs="?", help="output directory; default: PAK filename without extension")
    p.add_argument("--out", "-o", dest="output_flag", help="same as the optional output path")
    p.add_argument("--strip-prefix", default="../../../")
    p.add_argument("--quiet", action="store_true")
    add_repak_common(p, aes=True)
    p.set_defaults(func=pak_unpack)

    p = sub.add_parser("repack", help="create a PAK; usage: tool repack folder new.pak")
    p.add_argument("source", help="unpacked PAK directory")
    p.add_argument("output", help="new PAK path")
    add_pack_options(p)
    add_repak_common(p)
    p.set_defaults(func=pak_repack)

    p = sub.add_parser("inject", help="inject Lua; usage: tool inject game.pak lua-folder [new.pak]")
    p.add_argument("pak")
    p.add_argument("lua_source", help="one Lua file or a directory containing Lua files")
    p.add_argument("output", nargs="?", help="new PAK path; default: <input>.lua.pak")
    p.add_argument("--output", "-o", dest="output_flag", help="same as the optional output path")
    p.add_argument("--in-place", action="store_true", help="replace the input directly without creating a backup")
    p.add_argument("--target-prefix", default="Script", help="directory inside the PAK for injected Lua files")
    p.add_argument("--target-file", help="target filename for one Lua source file")
    p.add_argument("--strip-prefix", default="../../../")
    p.add_argument("--mount-point", default="../../../")
    p.add_argument("--version", default="v8b")
    p.add_argument("--compression", choices=["zlib", "gzip", "zstd", "lz4", "oodle"])
    add_repak_common(p, aes=True)
    p.set_defaults(func=lua_inject)

    return parser


def storage_dir() -> Path:
    if DOWNLOAD_DIR.is_dir():
        return DOWNLOAD_DIR
    return Path.cwd()


def choose_path(label: str, suffix: str | None = None, directory: bool = False) -> Path:
    base = storage_dir()
    candidates = []
    if base.is_dir():
        candidates = sorted(
            p for p in base.iterdir()
            if (p.is_dir() if directory else p.is_file())
            and (suffix is None or p.suffix.lower() == suffix.lower())
        )
    if candidates:
        print(f"\n{label} (default folder: {base})")
        for index, candidate in enumerate(candidates, 1):
            print(f"  {index}) {candidate.name}")
        answer = input("Number select karein ya full path likhein: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return candidates[int(answer) - 1]
        if answer:
            return Path(answer).expanduser()
    return Path(input(f"{label} ka full path likhein: ").strip()).expanduser()


def ask_default(prompt: str, default: str) -> str:
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def dependency_status() -> bool:
    print("\nDependency check:")
    print(f"  Python: {sys.version.split()[0]} OK")
    git_ok = shutil.which("git") is not None
    repak_ok = shutil.which(os.environ.get("REPAK_BIN", "repak")) is not None
    print(f"  Git: {'OK' if git_ok else 'missing'}")
    print(f"  repak: {'OK' if repak_ok else 'missing'}")
    if not repak_ok:
        print("\nrepak missing hai. Pehle ye command run karein:")
        print("  bash ~/ue4-termux-tool/install-termux.sh")
        return False
    return True


def make_interactive_args(command: str) -> argparse.Namespace:
    if command == "unpack":
        pak = choose_path("PAK file", ".pak")
        output = ask_default("Output folder", str(pak.with_suffix("")))
        return argparse.Namespace(
            pak=str(pak), output=output, output_flag=None, strip_prefix="../../../",
            quiet=False, repak=None, aes_key=None,
        )
    if command == "repack":
        source = choose_path("Unpacked PAK folder", directory=True)
        output = ask_default("Output PAK", str(source.with_name(source.name + ".pak")))
        return argparse.Namespace(
            source=str(source), output=output, version="v8b", compression=None,
            mount_point="../../../", quiet=False, repak=None,
        )
    pak = choose_path("PAK file", ".pak")
    default_lua = storage_dir() / "lua"
    lua_source = ask_default("Lua folder or file", str(default_lua))
    output = ask_default("Output PAK", str(pak.with_name(pak.stem + ".lua.pak")))
    target_prefix = ask_default("PAK Lua folder", "Script")
    return argparse.Namespace(
        pak=str(pak), lua_source=lua_source, output=output, output_flag=None,
        in_place=False, target_prefix=target_prefix, target_file=None,
        strip_prefix="../../../", mount_point="../../../", version="v8b",
        compression=None, repak=None, aes_key=None,
    )


def update_project() -> bool:
    project = Path(__file__).resolve().parent
    script = project / "update-termux.sh"
    if not script.is_file():
        print(f"Update script not found at {script}. Re-clone the public repository first.")
        return False
    print("Updating tool...")
    result = subprocess.run(["bash", str(script)], cwd=project, check=False)
    if result.returncode != 0:
        print("Update failed. You can retry with: bash ~/ue4-termux-tool/update-termux.sh")
        return False
    return True


def execute_with_recovery(command: str, handler, args: argparse.Namespace) -> bool:
    try:
        handler(args)
        return True
    except ToolError as exc:
        report = write_diagnostic(command, str(exc), exc.code)
        print(f"{APP_NAME}: error: {sanitize_diagnostic_text(str(exc))}", file=sys.stderr)
        print(f"Diagnostic saved locally: {report}", file=sys.stderr)
        _send_report(report)
        if os.environ.get("TOOL_NO_AUTO_RETRY") == "1":
            return False
        print("Trying one tool update and retry...")
        if not update_project():
            return False
        try:
            handler(args)
            print("Retry successful after update.")
            return True
        except ToolError as retry_exc:
            retry_report = write_diagnostic(command, str(retry_exc), retry_exc.code)
            print(f"Retry failed: {sanitize_diagnostic_text(str(retry_exc))}", file=sys.stderr)
            print(f"New diagnostic saved locally: {retry_report}", file=sys.stderr)
            return False


def start_background_update() -> None:
    """Start one detached update check without delaying the interactive menu."""
    if os.environ.get("TOOL_NO_AUTO_UPDATE") == "1":
        return
    project = Path(__file__).resolve().parent
    update_script = project / "update-termux.sh"
    if not (project / ".git").is_dir() or not update_script.is_file() or shutil.which("git") is None:
        return
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache.mkdir(parents=True, exist_ok=True)
    lock = cache / "tool-update.lock"
    log = cache / "tool-update.log"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        try:
            if time.time() - lock.stat().st_mtime > 3600:
                lock.unlink()
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            else:
                return
        except (FileNotFoundError, OSError):
            return
    command = (
        f"bash {shlex.quote(str(update_script))} > {shlex.quote(str(log))} 2>&1; "
        f"rm -f {shlex.quote(str(lock))}"
    )
    try:
        subprocess.Popen(
            ["bash", "-c", command],
            cwd=project,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("[update] Background update check started.")
    except OSError:
        try:
            lock.unlink()
        except OSError:
            pass


def interactive_menu() -> None:
    print("\n========================================")
    print("        UE4 TERMUX TOOL")
    print("========================================")
    print("1) PAK Unpack")
    print("2) PAK Repack")
    print("3) Lua Inject")
    print("4) Update Tool")
    print("0) Exit")
    choice = input("\nOption select karein: ").strip()
    if choice == "0":
        print("Bye.")
        return
    if choice == "4":
        update_project()
        return
    command = {"1": "unpack", "2": "repack", "3": "inject"}.get(choice)
    if not command:
        print("Invalid option.")
        return
    if not dependency_status():
        return
    try:
        args = make_interactive_args(command)
        execute_with_recovery(command, {"unpack": pak_unpack, "repack": pak_repack, "inject": lua_inject}[command], args)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        if sys.stdin.isatty():
            start_background_update()
            interactive_menu()
        else:
            parser.print_help()
        return 0
    try:
        ok = execute_with_recovery(args.command, args.func, args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
