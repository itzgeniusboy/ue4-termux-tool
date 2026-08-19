# PakForge 1.3.1 — Offline PAK Interoperability Merge

The safe offline/test PAK interoperability patch was committed and pushed to `main`.

- Repository: https://github.com/itzgeniusboy/ue4-termux-tool
- Commit: `980878e` — `Fix offline PAK metadata and Lua 5.1 pipeline`
- Previous commit: `70b4aae`
- Version: `PakForge 1.3.1`

## Actual file mapping

The requested paths `pakforge/core/tencent.py` and `pakforge/cli/lua_pipeline.py` do not exist in this repository. The equivalent implementation is in:

| Requested area | Actual PakForge file |
|---|---|
| Tencent/UE PAK parser and repack | `pakforge_core.py` |
| Native CLI and Lua pipeline | `pakforge.py` |
| Regression coverage | `test_pakforge.py` |
| Termux launcher smoke test | `test_launcher.sh` |
| User documentation | `README.md` |

## Exact modified locations

Line numbers refer to commit `980878e`; use the function names as stable anchors when applying manually because line numbers can shift.

| File | Functions/sections changed | Purpose |
|---|---|---|
| `pakforge_core.py` | `normalize_pak_path`, `calculate_tencent_hashes`, `validate_encryption_metadata` | Canonical paths, SHA1/CRC32 calculations, and strict encrypted-entry method validation. |
| `pakforge_core.py` | `TencentPakFile._verify_stem_hash`, `_construct_mount_point`, `_safe_mount_point_for_output` | Lowercase UTF-32LE stem CRC validation, exact mount-point preservation, and safe extraction. |
| `pakforge_core.py` | `_encode_entry_payload`, `_repack_uncompressed`, full `repack_pak_file_full` rebuild path | Correct logical versus physical encrypted sizes, recalculated compressed block tables, offsets, entry sizes, and raw-data hashes. |
| `pakforge_core.py` | `_pw_entry` and footer serialization in `repack_pak_file_full` | Compression/encryption metadata validation, index SHA1/size/offset updates, and output-file stem CRC update. |
| `pakforge.py` | `find_lua51_compiler`, `compile_lua_sources`, `lua_pipeline_command`, `repack_command` | `luac5.1` then `luac51` priority, optional compilation, and `--verify` output reopen. |
| `test_pakforge.py` | `main` assertions | Hash, CRC, mount-point, encryption-method, compiler-priority, and CLI flag tests. |
| `README.md` | Lua pipeline documentation | Documents `--compile-lua`, trusted compiler installation, and `repack --verify`. |

## Hash behavior

For edited entries, the backend now calculates:

```python
content_hash = SHA1(raw_uncompressed_data).digest()
content_org_hash = SHA1(raw_uncompressed_data).digest()  # returned for v12+
stem_hash = CRC32(path_stem.lower().encode("utf-32le"))
unk2 = SHA1(full_relative_path.lower().replace("\\\\", "/").encode("utf-8")).digest()
```

The actual Tencent entry `unk2` field is the 20-byte per-entry path hash. The v12+ `content_org_hash` parsed by this backend is a single 20-byte footer-wide vendor field, not a per-entry field. The serializer therefore preserves the source footer value rather than writing a misleading one-file SHA1 into a whole-PAK field. The per-entry raw-data SHA1 is always recalculated for edited entries.

## Lua compiler behavior

`--compile-lua` uses `PAKFORGE_LUAC51` when configured, then searches `luac5.1`, then `luac51`. A generic `luac` fallback is disabled by default because Lua bytecode versions are not interchangeable; it requires `PAKFORGE_ALLOW_NON51_LUAC=1`. PakForge does not auto-download executable binaries.

## Verification and safety

`pakforge repack ... --verify` reopens the output with the adaptive parser and validates the index hash, footer offsets, mount point, entries, and structural metadata. The Lua pipeline already performs post-repack verification and writes a JSON report. Intentional bytecode corruption is not present in the merged code.

The patch is limited to offline/test parser correctness and Termux-safe workflows. It does not add live-client-specific injection, anti-cheat bypass, DRM circumvention, tracking, telemetry, hardcoded secrets, or executable auto-downloads.

## Validation

All existing checks passed after the final changes:

```text
python3 test_pakforge.py       -> pakforge-tests-ok
python3 test_power_features.py -> power-feature-tests-ok
python3 test_theme.py          -> theme-tests-ok
python3 test_smoke.py          -> focused-smoke-tests-ok
bash test_launcher.sh         -> launcher-tests-ok
python3 -m py_compile pakforge_core.py pakforge.py test_pakforge.py -> passed
git diff --check -> passed
```
