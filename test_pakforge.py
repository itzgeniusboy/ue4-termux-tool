#!/usr/bin/env python3
"""Fast tests for PakForge's wrapper workflows without requiring a real PAK file."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zlib
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pakforge
import pakforge_core
from pakforge_core import (
    TencentPakFile,
    calculate_tencent_hashes,
    validate_encryption_metadata,
)

ROOT = Path(__file__).resolve().parent
PAKFORGE = ROOT / "pakforge.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PAKFORGE), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> None:
    assert pakforge.normalize_target_prefix("Content\\\\Lua\\\\Mods") == "Content/Lua/Mods"
    assert pakforge.normalize_target_prefix("/Content/Lua/Mods/") == "Content/Lua/Mods"
    try:
        pakforge.normalize_target_prefix("Content/../Config")
    except SystemExit:
        pass
    else:
        raise AssertionError("path traversal was accepted")

    parsed = pakforge.parser().parse_args([
        "repack", "source.pak", "edited", "output.pak", "--target-prefix", "Content/Lua", "--verify"
    ])
    assert parsed.target_prefix == "Content/Lua"
    assert parsed.verify is True
    assert parsed.workers == 4
    unpack_parsed = pakforge.parser().parse_args(["unpack", "source.pak", "out", "--workers", "2"])
    assert unpack_parsed.workers == 2
    repack_parsed = pakforge.parser().parse_args(["repack", "source.pak", "edited", "out.pak", "--workers", "3"])
    assert repack_parsed.workers == 3
    with tempfile.TemporaryDirectory(prefix="pakforge-setup-status-") as setup_state:
        setup_env = os.environ.copy()
        setup_env["XDG_STATE_HOME"] = setup_state
        setup_status = subprocess.run(
            [sys.executable, str(ROOT / "pakforge_setup.py"), "--status"],
            cwd=ROOT,
            env=setup_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert setup_status.returncode == 0
        setup_payload = json.loads(setup_status.stdout)
        assert setup_payload["state"] in {"incomplete", "ready"}
        assert setup_payload["percent"] == 0
        assert setup_payload["remaining_percent"] == 100
        assert setup_payload["stage_total"] == 4
        assert setup_payload["heartbeat_count"] == 0
        assert setup_payload["updated_at"] is None
        assert setup_payload["downloaded_bytes"] is None
        assert setup_payload["download_total_bytes"] is None
    patch_parsed = pakforge.parser().parse_args(["repack", "source.pak", "edited", "out.pak", "--patch", "--verify"])
    assert patch_parsed.patch is True
    assert patch_parsed.verify is True

    with tempfile.TemporaryDirectory(prefix="pakforge-patch-") as patch_dir:
        patch_root = Path(patch_dir)
        source_pak = patch_root / "source.pak"
        edited_root = patch_root / "edited"
        output_pak = patch_root / "patched.pak"
        original = b"old-data"
        replacement = b"new-data"
        source_bytes = b"HEADER" + original + b"TAIL"
        source_pak.write_bytes(source_bytes)
        (edited_root / "Content").mkdir(parents=True)
        (edited_root / "Content" / "x.bin").write_bytes(replacement)
        entry = SimpleNamespace(
            offset=6,
            size=len(original),
            uncompressed_size=len(original),
            compression_method=pakforge_core.CM_NONE,
            compressed_blocks=[],
            compression_block_size=0,
            encrypted=False,
            encryption_method=0,
            content_hash=hashlib.sha1(original).digest(),
        )
        fake_pak = SimpleNamespace(
            _file_path=source_pak,
            _index={pakforge_core.PurePath("Content"): {"x.bin": entry}},
            _zstd_dict=None,
        )
        assert pakforge_core.repack_pak_file_patch(fake_pak, edited_root, output_pak, workers=2) == 1
        patched_bytes = output_pak.read_bytes()
        assert len(patched_bytes) == len(source_bytes)
        assert patched_bytes[:6] == source_bytes[:6]
        assert patched_bytes[6:14] == replacement
        assert patched_bytes[14:] == source_bytes[14:]
    assert pakforge_core.CM_OODLE == 3
    with patch.object(pakforge_core.OodleCodec, "available", return_value=False):
        assert pakforge_core.effective_repack_compression_method(pakforge_core.CM_OODLE) == pakforge_core.CM_ZSTD
    auto_parsed = pakforge.parser().parse_args([
        "auto", "--pak", "source.pak", "--edit-dir", "edits", "--output", "out.pak",
        "--target-prefix", "Content/Lua", "--workers", "2",
    ])
    assert auto_parsed.command == "auto"
    assert auto_parsed.target_prefix == "Content/Lua"
    assert auto_parsed.workers == 2

    with tempfile.TemporaryDirectory(prefix="pakforge-workers-") as staging_dir:
        root = Path(staging_dir)
        first = root / "first.bin"
        second = root / "second.bin"
        first.write_bytes(b"first-data")
        second.write_bytes(b"second-data")
        edited_inputs = {
            "Content/first.bin": (first, None),
            "Content/second.bin": (second, None),
        }
        staged = pakforge_core._stage_repack_inputs(edited_inputs, workers=2)
        assert list(staged) == list(edited_inputs)
        assert staged["Content/first.bin"] == b"first-data"
        assert staged["Content/second.bin"] == b"second-data"
        with patch.object(
            pakforge_core, "ThreadPoolExecutor", side_effect=RuntimeError("threads unavailable")
        ):
            fallback = pakforge_core._stage_repack_inputs(edited_inputs, workers=4)
        assert fallback == staged

    raw = b"offline-pakforge-fixture"
    hashes = calculate_tencent_hashes(raw, r"Content\Lua\MyMod.lua", 12)
    assert hashes["content_hash"] == hashlib.sha1(raw).digest()
    assert hashes["content_org_hash"] == hashlib.sha1(raw).digest()
    assert hashes["stem_hash"] == (zlib.crc32("mymod".encode("utf-32le")) & 0xFFFFFFFF)
    assert hashes["unk2"] == hashlib.sha1(b"content/lua/mymod.lua").digest()
    assert str(TencentPakFile._construct_mount_point("../../../Content/Lua")) == "../../../Content/Lua"
    assert str(TencentPakFile._safe_mount_point_for_output(TencentPakFile._construct_mount_point("../../../Content/Lua"))) == "Content/Lua"
    try:
        validate_encryption_metadata(True, 999, 12)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown encrypted-entry method was accepted")

    with tempfile.TemporaryDirectory(prefix="pakforge-luac-") as compiler_dir:
        compiler_root = Path(compiler_dir)
        for name in ("luac", "luac51", "luac5.1"):
            path = compiler_root / name
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        previous_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{compiler_root}:{previous_path}"
        try:
            assert Path(pakforge.find_lua51_compiler()).name == "luac5.1"
        finally:
            os.environ["PATH"] = previous_path

    with tempfile.TemporaryDirectory(prefix="pakforge-luac-install-") as compiler_dir:
        expected_compiler = str(Path(compiler_dir) / "luac5.1")
        with patch.object(
            pakforge,
            "_find_lua51_compiler",
            side_effect=[None, expected_compiler],
        ), patch.object(
            pakforge.shutil,
            "which",
            side_effect=lambda name: "/data/data/com.termux/files/usr/bin/pkg" if name == "pkg" else None,
        ), patch.object(
            pakforge.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["pkg"], 0),
        ) as package_run:
            assert pakforge.ensure_lua51_installed() == expected_compiler
            package_run.assert_called_once_with(["pkg", "install", "lua51", "-y"], check=False)

    for manager, expected_command in (
        ("apt", ["/usr/bin/sudo", "apt", "install", "lua5.1", "-y"]),
        ("pacman", ["/usr/bin/sudo", "pacman", "-S", "lua51", "--noconfirm"]),
    ):
        with tempfile.TemporaryDirectory(prefix=f"pakforge-{manager}-") as compiler_dir:
            expected_compiler = str(Path(compiler_dir) / "luac5.1")
            def fake_which(name: str, selected: str = manager) -> str | None:
                if name == selected:
                    return f"/usr/bin/{selected}"
                if name == "sudo":
                    return "/usr/bin/sudo"
                return None
            with patch.object(
                pakforge,
                "_find_lua51_compiler",
                side_effect=[None, expected_compiler],
            ), patch.object(pakforge.shutil, "which", side_effect=fake_which), patch.object(
                pakforge.os, "geteuid", return_value=1000
            ), patch.object(
                pakforge.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(expected_command, 0),
            ) as package_run:
                assert pakforge.ensure_lua51_installed() == expected_compiler
                package_run.assert_called_once_with(expected_command, check=False)

    with patch.object(pakforge, "_find_lua51_compiler", return_value=None), patch.object(
        pakforge.shutil, "which", return_value=None
    ):
        try:
            pakforge.ensure_lua51_installed()
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("unknown package-manager host did not fail gracefully")

    plain = bytes(range(40))
    assert pakforge.normalize_tencent_lua_bytecode(plain[:33] + b"\x02" + plain[34:]) == plain[:33] + b"\x02" + plain[34:]
    obfuscated = plain[:33] + b"\x03" + bytes((0xA5, 0x10, 0xF2))
    assert pakforge.normalize_tencent_lua_bytecode(obfuscated) == plain[:33] + b"\x03" + bytes((0x5A, 0x01, 0x2F))

    with tempfile.TemporaryDirectory(prefix="pakforge-unluac-") as decomp_root:
        root = Path(decomp_root)
        luac = root / "Content" / "Lua" / "demo.luac"
        luac.parent.mkdir(parents=True)
        luac.write_bytes(obfuscated)
        jar = root / "unluac_patched.jar"
        jar.write_bytes(b"test jar placeholder")
        with patch.object(pakforge.shutil, "which", return_value="/usr/bin/java") as java_which, patch.object(
            pakforge.subprocess,
            "run",
        ) as java_run:
            def fake_java(command, **kwargs):
                assert command[:3] == ["java", "-jar", str(jar)]
                assert Path(command[3]).read_bytes() == pakforge.normalize_tencent_lua_bytecode(obfuscated)
                kwargs["stdout"].write("-- decompiled source\n")
                return subprocess.CompletedProcess(command, 0, stderr="")
            java_run.side_effect = fake_java
            ok, output_path = pakforge._decompile_luac_file(luac, jar)
            assert ok is True
            assert Path(output_path).read_text(encoding="utf-8") == "-- decompiled source\n"
            assert luac.read_bytes() == obfuscated
            java_which.assert_called_once_with("java")

        with patch.object(pakforge, "find_unluac_decompiler", return_value=None):
            result = pakforge.decompile_extracted_lua(root)
            assert result == {"found": 1, "decompiled": 0, "fallback": 1}
            assert luac.is_file()

    with tempfile.TemporaryDirectory(prefix="pakforge-auto-test-") as auto_dir:
        root = Path(auto_dir)
        source_pak = root / "base.pak"
        source_pak.write_bytes(b"test-pak")
        edit_dir = root / "edits" / "Mods"
        edit_dir.mkdir(parents=True)
        (edit_dir / "ui.lua").write_text("return 2\\n", encoding="utf-8")
        output = root / "modded.pak"
        report_path = root / "auto-report.json"
        fake_pak = object()

        def fake_unpack(args):
            baseline = Path(args.output) / "Content" / "Lua" / "Mods" / "ui.lua"
            baseline.parent.mkdir(parents=True, exist_ok=True)
            baseline.write_text("return 1\\n", encoding="utf-8")

        def fake_compile(lua_root, lua_files, staging_root, compiler=None):
            compiled = Path(staging_root) / "lua51-bytecode" / "Mods" / "ui.lua"
            compiled.parent.mkdir(parents=True, exist_ok=True)
            compiled.write_bytes(b"lua51-bytecode")
            return compiled.parents[1], compiler

        def fake_repack(pak, edited_root, output_path, target_path=None, force_add=False, workers=4):
            assert target_path == "Content/Lua"
            assert force_add is True
            assert (Path(edited_root) / "Mods" / "ui.luac").read_bytes() == b"lua51-bytecode"
            output_path.write_bytes(b"verified-pak")
            return 1

        with patch.object(pakforge, "unpack_command", side_effect=fake_unpack), patch.object(
            pakforge, "decompile_extracted_lua", return_value={"found": 1, "decompiled": 1, "fallback": 0}
        ), patch.object(
            pakforge, "ensure_lua51_installed", return_value="/usr/bin/luac5.1"
        ), patch.object(
            pakforge, "compile_lua_sources", side_effect=fake_compile
        ), patch.object(
            pakforge, "repack_pak_file_full", side_effect=fake_repack
        ), patch.object(
            pakforge, "open_pak_auto", side_effect=[(fake_pak, False, None), (fake_pak, False, None)]
        ), patch.object(
            pakforge, "inventory", return_value=[{"path": "Content/Lua/Mods/ui.luac"}]
        ):
            pakforge.auto_command(
                argparse.Namespace(
                    pak=str(source_pak), edit_dir=str(edit_dir.parent), output=str(output),
                    target_prefix="Content/Lua", report=str(report_path), workers=2,
                    overwrite=False, is_od=False,
                )
            )
        auto_report = json.loads(report_path.read_text(encoding="utf-8"))
        assert auto_report["status"] == "verified"
        assert auto_report["modified_files"][0]["relative"] == "Mods/ui.lua"
        assert auto_report["replaced_files"][0]["pak_path"] == "Content/Lua/Mods/ui.luac"
        assert output.read_bytes() == b"verified-pak"

    cli_source = (ROOT / "pakforge.py").read_text(encoding="utf-8")
    assert "PAKFORGE CONTROL CENTER" in cli_source
    assert "Guided PAK workflow  •  auto unpack / repack" in cli_source
    assert 'menu.add_row("1", "Guided PAK workflow' in cli_source
    assert 'menu.add_row("01"' not in cli_source
    assert 'menu.add_row("0", "Exit")' in cli_source
    assert 'menu.add_row("00"' not in cli_source
    assert "pakforge_control_center()" in cli_source
    assert "def _menu_select_pak" in cli_source
    assert "def _menu_workspace" in cli_source
    assert "_menu_path" not in cli_source
    assert "Running selected workflow" in cli_source

    version = run("--version")
    assert version.returncode == 0
    assert version.stdout.strip() == "PakForge 1.3.8"

    with tempfile.TemporaryDirectory(prefix="pakforge-test-") as raw:
        root = Path(raw)
        (root / "nested").mkdir()
        sample = root / "nested" / "sample.txt"
        sample.write_text("pakforge-test\n", encoding="utf-8")

        created = run("manifest", str(root))
        assert created.returncode == 0, created.stderr
        manifest = root / ".pakforge-manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["tool"] == "PakForge"
        assert payload["files"][0]["sha256"] == hashlib.sha256(sample.read_bytes()).hexdigest()

        verified = run("verify", str(root))
        assert verified.returncode == 0, verified.stderr

        sample.write_text("tampered\n", encoding="utf-8")
        tampered = run("verify", str(root))
        assert tampered.returncode == 2
        assert "CHANGED" in tampered.stdout

        old_dir = root / "old-build"
        new_dir = root / "new-build"
        old_dir.mkdir()
        new_dir.mkdir()
        (old_dir / "keep.lua").write_text("return 1\n", encoding="utf-8")
        (old_dir / "removed.lua").write_text("return 2\n", encoding="utf-8")
        (new_dir / "keep.lua").write_text("return 3\n", encoding="utf-8")
        (new_dir / "added.lua").write_text("return 4\n", encoding="utf-8")
        diffed = run("diff", str(old_dir), str(new_dir), "--json")
        assert diffed.returncode == 0, diffed.stderr
        diff_payload = json.loads(diffed.stdout)
        assert diff_payload["summary"] == {"added": 1, "removed": 1, "changed": 1, "unchanged": 0}
        assert "added.lua" in diff_payload["added"]
        assert "removed.lua" in diff_payload["removed"]
        assert "keep.lua" in diff_payload["changed"]

        output = root / "existing.pak"
        output.write_bytes(b"old-output")
        backup = pakforge.backup_file(output)
        assert backup and backup.is_file()
        assert backup.read_bytes() == b"old-output"

        invalid = root / "invalid.pak"
        invalid.write_bytes(b"not-a-valid-pak")
        state = root / "state"
        failure = subprocess.run(
            [sys.executable, str(PAKFORGE), "info", str(invalid)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={**os.environ, "XDG_STATE_HOME": str(state)},
            check=False,
        )
        assert failure.returncode == 1
        assert "Operation log saved locally:" in failure.stderr
        native_logs = list((state / "pakforge" / "logs").glob("operation-*.jsonl"))
        assert native_logs
        native_log = max(native_logs, key=lambda path: path.stat().st_mtime).read_text(encoding="utf-8")
        assert "operation_failed" in native_log
        assert "PAK format was not recognized" in native_log

        detected = run("detect", str(invalid), "--json")
        assert detected.returncode == 2
        detection_payload = json.loads(detected.stdout)
        assert detection_payload["status"] == "unsupported_or_invalid"
        assert detection_payload["recommendations"]

        doctor = run("doctor", str(invalid), "--json")
        assert doctor.returncode == 2
        doctor_payload = json.loads(doctor.stdout)
        assert doctor_payload["status"] == "attention_required"
        assert doctor_payload["issues"]

        config_home = root / "config"
        profile_env = {**os.environ, "XDG_CONFIG_HOME": str(config_home)}
        profile = subprocess.run(
            [sys.executable, str(PAKFORGE), "profile", "init", "debug", "--pak", str(invalid), "--lua-dir", str(new_dir), "--output", str(root / "debug.pak")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=profile_env,
            check=False,
        )
        assert profile.returncode == 0, profile.stderr
        profile_payload = json.loads((config_home / "pakforge" / "profiles" / "debug.json").read_text(encoding="utf-8"))
        assert profile_payload["target_prefix"] == "Script"
        listed = subprocess.run(
            [sys.executable, str(PAKFORGE), "profile", "list"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=profile_env,
            check=False,
        )
        assert listed.returncode == 0
        assert "debug" in listed.stdout

    lua_help = run("lua-pipeline", "--help")
    assert lua_help.returncode == 0
    assert "--target-prefix" in lua_help.stdout
    assert "--dry-run" in lua_help.stdout
    assert "--verify" in lua_help.stdout

    print("pakforge-tests-ok")


if __name__ == "__main__":
    main()
