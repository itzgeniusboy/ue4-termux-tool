# PakForge 1.3.6 — Optional Oodle Compression Support

## Scope

PakForge 1.3.6 recognizes `CM_OODLE = 3` in the native Tencent/UE PAK backend. Oodle support is optional and uses only a user-provided licensed `oodle2.dll`; PakForge does not download, bundle, or redistribute the proprietary runtime.

## Exact implementation locations

| File | Location | Change |
|---|---|---|
| `pakforge_core.py` | Compression constants | Adds `CM_OODLE = 3` and includes it in `SUPPORTED_COMPRESSION_METHODS`. |
| `pakforge_core.py` | `OodleCodec` | Discovers `PAKFORGE_OODLE_DLL`, `SOURCE/oodle2.dll`, the repository-local DLL, or a system library; binds `OodleLZ_Decompress` and `OodleLZ_Compress` through `ctypes`. |
| `pakforge_core.py` | `PakCompression.decompress_block()` | Decodes Oodle blocks using the entry's expected uncompressed block size. |
| `pakforge_core.py` | `TencentPakFile._write_to_disk()` | Supplies the correct logical raw size for each Oodle block during extraction. |
| `pakforge_core.py` | `_best_compress()` | Encodes edited blocks through `OodleLZ_Compress` when the runtime is available. |
| `pakforge_core.py` | `effective_repack_compression_method()` | Switches newly encoded edited Oodle entries to ZSTD when the runtime is unavailable and updates entry metadata. Existing untouched payloads remain byte-for-byte copied. |
| `pakforge.py` | inventory/capability display | Existing compression reporting now labels method `3` as `OODLE` through the backend method formatter. |
| `README.md` | native compression section | Documents DLL placement, environment variable, no-download behavior, extraction requirements, and repack fallback. |
| `test_pakforge.py` | compression regression assertions | Verifies the constant and missing-DLL ZSTD fallback without invoking a package manager or loading a DLL. |

## DLL setup

```bash
export PAKFORGE_OODLE_DLL="$HOME/path/to/oodle2.dll"
pakforge info input.pak
pakforge unpack input.pak output-directory
```

On Windows, `ctypes.WinDLL` is used when available. On other platforms, PakForge attempts the normal `ctypes.CDLL` loader. Termux/Android generally will not load a Windows PE DLL; in that environment the safe behavior is to preserve untouched Oodle payloads and use ZSTD for newly edited compressed entries when the DLL is unavailable.

## Fallback behavior

An existing Oodle entry cannot be decoded as ZSTD because its compressed bytes use a different codec. Therefore extraction of an Oodle-compressed entry without a valid runtime fails with an explicit instruction to provide `oodle2.dll`. For repacking an edited Oodle entry, PakForge selects ZSTD and serializes the updated compression method, block table, and sizes. ZLIB, ZSTD, ZSTD dictionary, encryption, hashes, and deterministic serializer ordering remain unchanged.

## Validation

The final working tree passed:

```text
python3 -m py_compile pakforge.py pakforge_core.py test_pakforge.py
PAKFORGE_OODLE_DLL=/definitely/missing/oodle2.dll focused CM_OODLE fallback check
python3 test_pakforge.py
python3 test_power_features.py
python3 test_theme.py
python3 test_smoke.py
bash test_launcher.sh
git diff --check
```

Release version: **PakForge 1.3.6**.
