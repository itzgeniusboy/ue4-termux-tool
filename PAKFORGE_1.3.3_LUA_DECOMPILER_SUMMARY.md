# PakForge 1.3.3 — Optional Lua Bytecode Decompiler

PakForge now supports an opt-in Lua decompilation step after native PAK extraction.

## Exact implementation locations

The repository uses a flat CLI layout, so the changes are in `pakforge.py` rather than nested `pakforge/` modules.

| Function or area | Location | Behavior |
|---|---|---|
| `find_unluac_decompiler()` | `pakforge.py` | Searches `PAKFORGE_UNLUAC_JAR`, `SOURCE/unluac_patched.jar`, a JAR beside `pakforge.py`, and PATH. It never downloads a binary. |
| `normalize_tencent_lua_bytecode()` | `pakforge.py` | Preserves the first 34 bytes and nibble-swaps only the remaining bytes when byte index 33 is greater than 2. |
| `_decompile_luac_file()` | `pakforge.py` | Uses a temporary normalized `.luac`, invokes `java -jar <jar> <temp-input>`, writes a `.lua` sibling, and enforces a 30-second timeout. |
| `decompile_extracted_lua()` | `pakforge.py` | Scans extracted output, decompiles each `.luac`, and keeps raw files on missing dependencies or failures. |
| `unpack_command()` | `pakforge.py` | Calls the optional decompiler after `pak.dump(output)` and before logging/manifest output. |
| CLI parser | `pakforge.py` | Adds `unpack --decompile-lua` and `batch-unpack --decompile-lua`. |
| Regression coverage | `test_pakforge.py` | Covers nibble handling, temporary input preservation, Java invocation, `.lua` sibling output, and missing-JAR fallback. |

## Usage

```bash
pakforge unpack input.pak output-directory --decompile-lua
pakforge batch-unpack paks-directory output-directory --decompile-lua
```

The flag is opt-in. Ordinary unpacking remains unchanged. The extracted `.luac` file is never overwritten. If unluac, Java, or a successful conversion is unavailable, the raw bytecode remains in place and the unpack operation continues.

## Safety and compatibility behavior

The Java invocation uses a fixed argument list and does not use shell execution, shell redirection, or remote URLs. Output is captured directly into the sibling `.lua` file. Temporary normalized input is deleted in a `finally` block. A timeout removes any partial `.lua` output and reports a warning.

For Tencent-style bytecode, nibble normalization is applied only to the temporary decompiler input. The original extracted bytes are preserved for round-trip inspection and later repacking.

## Validation

The final release is expected to pass Python syntax checks, `test_pakforge.py`, `test_power_features.py`, `test_theme.py`, `test_smoke.py`, `test_launcher.sh`, and `git diff --check`. The version is `PakForge 1.3.3`.
