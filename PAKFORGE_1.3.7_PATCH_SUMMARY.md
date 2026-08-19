# PakForge 1.3.7 — Strict In-Place PAK Patch Mode

## Scope

PakForge 1.3.7 adds `pakforge repack --patch` for authorized offline/test PAK workflows. The mode copies the source PAK and replaces only changed payload bytes in existing slots. It does not add files, change the entry table, move payloads, rebuild compression-block tables, or rewrite the archive footer.

## Usage

```bash
pakforge repack source.pak edited-directory output.pak --patch --verify
```

The edited directory must contain PAK-relative paths that already exist in the source archive. Patch mode refuses `--full`, `--target-prefix`, new paths, duplicate paths, source/output aliasing, changed uncompressed sizes, changed compressed block counts, and payloads that exceed their original physical slots. It never truncates an edited file or silently falls back to a full rebuild.

## Exact implementation locations

| File | Function/section | Purpose |
|---|---|---|
| `pakforge_core.py` | `_patch_entry_map()` | Builds exact normalized PAK-relative path mappings. |
| `pakforge_core.py` | `_patch_compressed_payload()` | Re-encodes each existing compression block and checks its original physical capacity. |
| `pakforge_core.py` | `repack_pak_file_patch()` | Copies the source PAK, writes changed payload slots atomically through a temporary output, and preserves file size and offsets. |
| `pakforge.py` | `repack_command()` | Routes `--patch` before full/legacy modes and rejects incompatible path-remapping options. |
| `pakforge.py` | `parser()` | Adds `repack --patch`. |
| `test_pakforge.py` | patch fixture | Verifies exact replacement, unchanged surrounding bytes, unchanged output size, and parser coverage. |
| `README.md` | repack examples and integrity notes | Documents usage and strict refusal behavior. |

## Integrity limitation

Patch mode intentionally preserves the original index bytes and footer because changing those structures can require rewriting the encrypted index and vendor-specific index signatures. Consequently, the source entry's stored content hash is not rewritten by this fast path. `--verify` validates that the output PAK remains structurally readable and retains its original index/footer layout; it is not a recalculation of vendor-specific per-entry signatures. Use the existing full rebuild path when updated entry metadata or a newly serialized index is required.

## Safety behavior

The output is first written to a same-directory temporary file and is atomically moved into place only after size and write checks succeed. The source PAK cannot be used as the output path. Missing files, oversize payloads, unsupported methods, unavailable Oodle runtime for changed Oodle entries, and worker-pool failures are surfaced clearly. Worker staging has a sequential fallback, but payload writes remain ordered.

## Validation

The release is validated with Python syntax compilation, focused patch-mode tests, complete PakForge regression/feature/theme/smoke suites, launcher checks, CLI help checks, and `git diff --check`.

Release version: **PakForge 1.3.7**.

This feature is generic offline/test PAK tooling only; it does not add live-client injection, anti-cheat bypass, DRM circumvention, key recovery, or proprietary runtime downloads.

## Example output

```text
Patch complete: 1 changed file(s); all original offsets, index bytes, and file size preserved.
```

If an edited file cannot fit, the command fails instead of producing a partial or silently incompatible archive.

---

## Patch mode implementation excerpt

The CLI route is:

```python
if getattr(args, "patch", False) and (args.full or target_prefix):
    raise SystemExit(
        "--patch cannot be combined with --full or --target-prefix; "
        "patch mode only replaces exact existing paths."
    )
if getattr(args, "patch", False):
    count = repack_pak_file_patch(
        pak,
        edited,
        output,
        workers=getattr(args, "workers", 4),
    )
```

The complete implementation is in `pakforge_core.py` and is included in the release commit.

---

## GitHub release

The patch is intended to be committed to the `main` branch after the final validation suite completes.

---

## Test command

```bash
python3 -m py_compile pakforge.py pakforge_core.py test_pakforge.py
python3 test_pakforge.py
python3 test_power_features.py
python3 test_theme.py
python3 test_smoke.py
bash test_launcher.sh
git diff --check
```

---

## Technical note

The patch writer keeps payload offsets and physical allocation sizes stable. For compressed entries, each logical chunk is compressed using the existing entry method, encrypted with the existing entry method when applicable, and zero-padded only within the original physical block slot. For uncompressed entries, the replacement must have the exact original logical size and must fit the original encrypted/plain allocation.

---

## Authorized use

Use this mode only with PAK files and project assets that you own or are authorized to modify.

---

## Release status

Pending final commit and remote synchronization.

---
