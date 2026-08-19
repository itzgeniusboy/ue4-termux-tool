# PakForge 1.3.4 — Bounded Parallel PAK I/O

PakForge 1.3.4 adds bounded worker control for large offline/test UE4 PAK workflows. The implementation parallelizes independent file extraction and edited-file input staging without concurrent writes to a shared PAK output buffer or output file handle.

## Exact implementation locations

| Location | Change |
|---|---|
| `pakforge_core.py:4` | Imports `ThreadPoolExecutor` and `as_completed`. |
| `pakforge_core.py:790` | `_write_to_disk()` now writes to a same-directory temporary file and uses `os.replace()` after the complete entry is written. |
| `pakforge_core.py:838` | `TencentPakFile.dump(out_path, workers=4)` extracts entries through a bounded pool; progress is updated only by the coordinator thread. |
| `pakforge_core.py:1071` | `_stage_repack_inputs(edited, workers=4)` reads edited source files concurrently while rebuilding the original mapping order. |
| `pakforge_core.py:1107` | `repack_pak_file_full(..., workers=4)` stages inputs in parallel, then serializes payloads and metadata sequentially for stable offsets and index order. |
| `pakforge_core.py:1631` | `repack_pak_file_with_block_display(..., workers=4)` stages source bytes in parallel but preserves its existing sequential shared-file writes. |
| `pakforge.py:761` | `unpack_command()` passes `--workers` to native extraction. |
| `pakforge.py:967-974` | `repack_command()` passes `--workers` to full and legacy repack modes. |
| `pakforge.py:1070`, `1083`, `1099` | Adds `--workers N` to `unpack`, `batch-unpack`, and `repack`; default is `4`. |
| `test_pakforge.py:47-77` | Covers parser flags, deterministic staging, and worker-pool fallback. |

## Usage

```bash
# Four extraction workers by default.
pakforge unpack input.pak output-directory

# Conservative mode for low-memory Termux devices.
pakforge unpack input.pak output-directory --workers 1

# Bounded parallel input staging; PAK serialization remains deterministic.
pakforge repack input.pak edited-directory output.pak --full --workers 4

# Batch extraction: worker count applies independently to each PAK.
pakforge batch-unpack paks-directory output-directory --workers 2
```

## Integrity and safety behavior

Extraction tasks read the immutable in-memory PAK buffer and write unique temporary files beside their final destinations. The final path is replaced only after the complete file is written, preventing partially written output files from appearing as successful extraction results. Progress updates and terminal output remain in the coordinator thread.

Repack workers only stage edited source bytes. The existing payload encoder, encryption, compression, offset calculation, hash calculation, index serialization, and footer serialization remain ordered and single-threaded. Therefore worker completion order cannot change binary output ordering, offsets, metadata, or hashes.

If a Termux runtime cannot create a `ThreadPoolExecutor`, PakForge prints a visible fallback message and performs the affected extraction or input staging sequentially. Use `--workers 1` to explicitly disable parallel work. File, compression, and decryption errors still propagate normally rather than being hidden as threading failures.

## Scope

This is a generic offline/test PAK I/O optimization for files the user owns or is authorized to modify. It does not add client-specific injection, anti-cheat bypass, DRM circumvention, tracking, telemetry, or secret-handling behavior.

## Validation

The release validation passed:

- `python3 test_pakforge.py`
- `python3 test_power_features.py`
- `python3 test_theme.py`
- `python3 test_smoke.py`
- `bash test_launcher.sh`
- Python syntax compilation for `pakforge.py`, `pakforge_core.py`, and `ue4tool.py`
- `git diff --check`
- CLI help checks confirming `--workers` appears on unpack and repack

PakForge version: `1.3.4`.
