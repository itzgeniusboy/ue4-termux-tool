# PakForge 1.3.2 — Automatic Lua 5.1 Dependency Resolver

PakForge now resolves the optional Lua 5.1 compiler dependency when the user runs `pakforge lua-pipeline --compile-lua`.

## Implementation locations

The repository uses a flat layout rather than the requested nested paths:

| Function or area | File | Purpose |
|---|---|---|
| `_find_lua51_compiler` | `pakforge.py` | Side-effect-free `shutil.which()` detection for configured `luac5.1`, `luac5.1`, and `luac51`. |
| `find_lua51_compiler` | `pakforge.py` | Existing non-installing detection API, with explicit opt-in generic `luac` fallback preserved. |
| `_manual_lua51_instruction` | `pakforge.py` | Creates platform-specific manual recovery instructions. |
| `ensure_lua51_installed` | `pakforge.py` | Detects `pkg`, `apt`, or `pacman`; runs only the official package manager with fixed argument arrays; verifies the compiler afterward. |
| `lua_pipeline_command` | `pakforge.py` | Calls `ensure_lua51_installed()` immediately before source compilation when `--compile-lua` is active. |
| `compile_lua_sources` | `pakforge.py` | Accepts the resolved compiler path and compiles source files into temporary staging. |
| Regression tests | `test_pakforge.py` | Tests compiler priority, Termux command selection, successful verification, and unknown-host graceful failure. |

## Exact package commands

| Detected command | Package command |
|---|---|
| `pkg` | `pkg install lua51 -y` |
| `apt` as root | `apt install lua5.1 -y` |
| `apt` as non-root with `sudo` | `sudo apt install lua5.1 -y` |
| `pacman` as root | `pacman -S lua51 --noconfirm` |
| `pacman` as non-root with `sudo` | `sudo pacman -S lua51 --noconfirm` |

The command is executed in the foreground with inherited terminal input/output. This is deliberate: the user sees the package manager output and can answer a required sudo prompt. No shell string, raw URL, remote binary, or hidden background process is used.

## Exact call site

Inside `lua_pipeline_command`, the call is made only when compilation was explicitly requested:

```python
if staging is not None:
    # Resolve or install Lua 5.1 before creating bytecode staging.
    compiler = ensure_lua51_installed()
    pack_root, _ = compile_lua_sources(
        lua_root,
        lua_files,
        Path(staging.name),
        compiler=compiler,
    )
    report["lua_compiler"] = compiler
```

`--dry-run` returns before this section, so planning a build does not install packages.

## Graceful fallback

If no supported package manager exists, `sudo` is unavailable when needed, the package command cannot start, or installation exits unsuccessfully, PakForge prints a manual command and exits with status `2`. A generic `luac` executable remains available only through the existing explicit environment override `PAKFORGE_ALLOW_NON51_LUAC=1`.

## Validation

The following checks passed after the final source changes:

```text
python3 -m py_compile pakforge.py test_pakforge.py
python3 test_pakforge.py
python3 test_power_features.py
python3 test_theme.py
python3 test_smoke.py
bash test_launcher.sh
git diff --check
```

The version is now `PakForge 1.3.2`.
