# UE4 Termux Tool

**UE4 Termux Tool** is a Python command-line wrapper for an authorized Unreal Engine 4 project. It handles ZIP-compatible OBB files directly and delegates Unreal Engine `.pak` parsing and writing to the Rust `repak` CLI. The wrapper does not reimplement the UE4 binary format, which keeps the Python layer small and makes the actual PAK compatibility come from `repak`.

Android expansion files are opaque binary blobs and may use any format; ZIP is common but is not guaranteed by Android.[^1] Therefore, the OBB commands intentionally refuse unknown/custom OBB formats instead of pretending that every `.obb` is a ZIP archive. The PAK backend supports a wide range of UE4 versions, but exact support depends on the project’s features and whether the PAK is encrypted or compressed.[^2]

> **Authorized-use notice:** Use this only with your own UE4 project or files for which you have explicit modding permission. The tool does not retrieve AES keys, bypass DRM, defeat anti-cheat, or create encrypted PAK output. An owner-supplied AES key is accepted only for reading an encrypted PAK through `repak`.

## Installation on Termux

Copy this folder to the phone, open Termux in the folder, and run:

```bash
termux-setup-storage
pkg install git -y
bash install-termux.sh
```

The installer installs Python, Rust, and `repak`, then places the wrapper at `$PREFIX/bin/ue4tool`. Building `repak` from source can take time and storage on a phone. If you already have a compatible `repak` binary, skip the Rust build and either put it on `PATH` or pass `--repak /absolute/path/to/repak`.

Use shared storage paths such as `/sdcard/Download/project.obb` or `/sdcard/Android/obb/com.example.game/main.1.com.example.game.obb`. Android documents the usual OBB location as `<shared-storage>/Android/obb/<package-name>/`.[^1]

## Commands

| Command | Purpose |
|---|---|
| `obb-list` | List entries in a ZIP-compatible OBB. |
| `obb-unpack` | Extract a ZIP-compatible OBB to a separate directory. |
| `pak-info` | Show PAK version, mount point, encryption, compression, and entry count. |
| `pak-list` | List files inside a PAK. |
| `pak-unpack` | Extract a PAK through `repak`. |
| `pak-pack` | Create a PAK from a directory. |
| `lua-inject` | Unpack a PAK, copy `.lua` files into a target directory, and repack a new PAK. |

### OBB workflow

```bash
ue4tool obb-list /sdcard/Download/main.1.com.example.game.obb
ue4tool obb-unpack /sdcard/Download/main.1.com.example.game.obb \
  --out /sdcard/Download/main-extracted
```

The original OBB is never deleted. Extraction refuses path-traversal members such as `../file` and requires `--force` before overwriting files.

If the OBB contains PAK files, locate them with:

```bash
find /sdcard/Download/main-extracted -type f -iname '*.pak' -print
```

### PAK workflow

```bash
ue4tool pak-info /sdcard/Download/main-extracted/Project/Content/Paks/pakchunk0-WindowsNoEditor.pak
ue4tool pak-list /sdcard/Download/main-extracted/Project/Content/Paks/pakchunk0-WindowsNoEditor.pak
ue4tool pak-unpack /sdcard/Download/main-extracted/Project/Content/Paks/pakchunk0-WindowsNoEditor.pak \
  --out /sdcard/Download/pakchunk0-files
```

For packing, use the PAK version required by your own UE4 build. `repak` names versions as `v7`, `v8a`, `v8b`, `v9`, and `v11`; do not blindly use the default if your project requires another version.

```bash
ue4tool pak-pack /sdcard/Download/pakchunk0-files \
  /sdcard/Download/pakchunk0-custom.pak \
  --version v7 \
  --mount-point '../../../'
```

The upstream `repak` CLI documents `info`, `list`, `unpack`, and `pack` commands. Its documentation also states that writing does not currently support encrypted output and has limitations around compression.[^2]

### Lua injection workflow

Place your Lua files in a directory, keeping their relative structure:

```text
lua/
└── MyMod/
    ├── init.lua
    └── player.lua
```

Inject them into a new PAK:

```bash
ue4tool lua-inject original.pak lua/ \
  --output project-lua.pak \
  --target-prefix Script \
  --version v7 \
  --mount-point '../../../'
```

This produces paths such as `Script/MyMod/init.lua`. For a single Lua file:

```bash
ue4tool lua-inject original.pak init.lua \
  --output project-lua.pak \
  --target-prefix Script/MyMod \
  --target-file init.lua \
  --version v7
```

The injection command unpacks to a temporary directory, copies only `.lua` files, and repacks to the output path. It does not modify the source PAK unless `--in-place` is explicitly used. When in-place mode is used, a timestamped `.bak` backup is created first. Because a PAK is repacked, select the correct version and mount point for your project; for production builds, test the result in a disposable copy before replacing the original asset package.

## Encrypted PAKs

If your own project uses an AES-encrypted PAK and you already know the 256-bit key, pass it to read operations:

```bash
ue4tool pak-info encrypted.pak --aes-key 001122...ffeedd
ue4tool pak-unpack encrypted.pak --out encrypted-files --aes-key 001122...ffeedd
```

The wrapper passes the key to `repak`; it does not discover or crack keys. The output created by `pak-pack` and `lua-inject` is not encrypted by this tool. For a project that requires encrypted output, use the matching official Unreal build pipeline and its own packaging configuration.

## Troubleshooting

| Problem | Fix |
|---|---|
| `repak was not found` | Run `bash install-termux.sh`, or pass `--repak /path/to/repak`. |
| `this OBB is not ZIP-compatible` | The OBB is custom/opaque; use the code in your own project that understands that container. |
| PAK version or compression error | Check `pak-info`, choose the matching `--version`, and use the official UE4 packaging tool if your project uses an unsupported feature. |
| Permission denied under `/sdcard` | Run `termux-setup-storage`, then use `/sdcard/...` paths. |
| Output is not accepted by the game | Verify mount point, PAK version, compression, asset dependencies, and whether your game expects signed/encrypted packages. |

## Files

| File | Description |
|---|---|
| `ue4tool.py` | Main Python CLI; standard library only. |
| `install-termux.sh` | Termux setup and installation script. |
| `README.md` | Usage and troubleshooting guide. |

## References

[^1]: [Android Developers — APK Expansion Files](https://developer.android.com/google/play/expansion-files)
[^2]: [trumank/repak — Unreal Engine `.pak` library and CLI](https://github.com/trumank/repak)
