# PakForge 1.3.5 — Offline Auto Workflow

## Scope

PakForge 1.3.5 adds an opt-in `pakforge auto` command for authorized offline and test UE4 projects. It chains the existing native unpacker, Lua decompiler, Lua 5.1 compiler, full repacker, and structural verification without adding game-client-specific logic.

## CLI

```bash
pakforge auto \
  --pak base.pak \
  --edit-dir ./my_lua_edits \
  --output modded.pak \
  --target-prefix Content/Lua \
  --workers 4
```

The command always verifies the newly written PAK by reopening it and checking that each changed compiled path is present. If `--edit-dir` is omitted, PakForge pauses after extraction/decompilation and asks the user to edit the temporary workspace before pressing Enter. CI/CD jobs should provide `--edit-dir`.

## Exact implementation locations

| File | Location | Change |
|---|---|---|
| `pakforge.py` | `_write_auto_report()` | Writes a newline-terminated JSON report. |
| `pakforge.py` | `_rename_compiled_lua_to_luac()` | Converts the existing compiler staging output to the `.luac` suffix expected by PAK assets. |
| `pakforge.py` | `auto_command()` | Chains unpack, decompile, edit discovery, Lua 5.1 compilation, target-prefix injection, repack, verification, reporting, and rollback. |
| `pakforge.py` | `parser()` | Adds the `auto` subcommand and its `--pak`, `--edit-dir`, `--output`, `--target-prefix`, `--report`, `--workers`, `--overwrite`, and `--is-od` options. |
| `pakforge_core.py` | `repack_pak_file_full()` | Preserves nested relative paths below the target prefix for compiled Lua overlays and new files. |
| `test_pakforge.py` | parser and auto workflow fixtures | Covers route parsing, nested paths, deterministic compiled staging, verification, and report output. |
| `README.md` | CLI usage and command reference | Documents the workflow, CI/CD behavior, report path, and rollback guarantees. |

## Report fields

The default report is written beside the output PAK as `<output>.auto-report.json`. It records the source PAK, edit directory, output, target prefix, worker count, decompile counts, compiler path, modified source hashes, replaced `.luac` paths, repack count, parser mode, and final status. Failed runs record the error and restore a pre-existing output when `--overwrite` created a backup.

## Safety and cleanup

The workflow uses `tempfile.TemporaryDirectory`, so the extracted workspace and compiler staging are removed on both success and failure. Existing output files are refused unless `--overwrite` is supplied. Repack is performed through the existing full-rebuild and verification paths; no shell commands or remote downloads are introduced by this feature.

## Validation

The following checks passed on the final working tree:

```text
python3 -m py_compile pakforge.py pakforge_core.py test_pakforge.py
python3 test_pakforge.py
python3 test_power_features.py
python3 test_theme.py
python3 test_smoke.py
bash test_launcher.sh
git diff --check
```

The release version is PakForge 1.3.5.
