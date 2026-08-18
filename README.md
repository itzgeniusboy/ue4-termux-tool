# UE4 Termux Tool

A focused Python CLI for authorized Unreal Engine 4 projects on Termux. The tool intentionally provides only three workflows:

| Command | Purpose |
|---|---|
| `pak-unpack` | Extract a UE4 `.pak` through `repak`. |
| `pak-repack` | Create a new UE4 `.pak` from an unpacked directory. |
| `lua-inject` | Unpack a PAK, copy Lua files into it, and create a new PAK. |

The project delegates UE4 PAK parsing and writing to [repak](https://github.com/trumank/repak). It does not bypass DRM, defeat anti-cheat, decrypt unknown keys, or modify third-party online games. Use it only with files from your own project or with explicit permission.

## 1. Install Termux prerequisites

Install [Termux](https://termux.dev/) from a trusted source such as [F-Droid](https://f-droid.org/packages/com.termux/) or the official Termux project. Then run:

```bash
pkg update -y && pkg upgrade -y
pkg install -y git python unzip rust
termux-setup-storage
```

When Android asks for storage permission, select **Allow**. This allows access to paths such as `/sdcard/Download/`.

## 2. Clone the repository

Clone the private repository with GitHub access:

```bash
git clone https://github.com/itzgeniusboy/ue4-termux-tool.git
cd ue4-termux-tool
```

If the repository is private and Git asks for authentication, sign in to GitHub or clone through your configured Git credentials. The repository URL is:

```text
https://github.com/itzgeniusboy/ue4-termux-tool.git
```

## 3. Install the tool and repak

The installer builds the compatible `repak` binary and installs the Python command as `$PREFIX/bin/ue4tool`:

```bash
chmod +x install-termux.sh ue4tool.py
bash install-termux.sh
ue4tool --help
```

The first build can take several minutes and requires free storage. To use an existing `repak` binary instead, place it on `PATH` or set its path when running a command:

```bash
export REPAK_BIN="$HOME/bin/repak"
ue4tool --help
```

You can also pass the binary directly with `--repak /absolute/path/to/repak`.

## 4. PAK unpack

Put the UE4 PAK somewhere accessible, for example `/sdcard/Download/game.pak`. Extract it to a new directory:

```bash
ue4tool pak-unpack /sdcard/Download/game.pak \
  --out /sdcard/Download/game-unpacked
```

If `--out` is omitted, the tool creates a directory using the PAK filename without its extension:

```bash
ue4tool pak-unpack /sdcard/Download/game.pak
```

For a PAK with a known owner-supplied AES key, pass the key only for the read/unpack operation:

```bash
ue4tool pak-unpack /sdcard/Download/game.pak \
  --out /sdcard/Download/game-unpacked \
  --aes-key YOUR_PROJECT_AES_KEY
```

The tool does not guess or recover AES keys.

## 5. PAK repack

After editing the extracted directory, create a new PAK. Select the PAK version used by your UE4 project; `v8b` is only the default example and is not universal:

```bash
ue4tool pak-repack /sdcard/Download/game-unpacked \
  /sdcard/Download/game-repacked.pak \
  --version v8b \
  --mount-point ../../../
```

Compression is optional:

```bash
ue4tool pak-repack ./game-unpacked ./game-repacked.pak \
  --version v8b \
  --compression zlib \
  --mount-point ../../../
```

Supported compression values depend on the installed `repak` build and are `zlib`, `gzip`, `zstd`, `lz4`, and `oodle`. The installer uses the portable non-Oodle build. Test the generated PAK in a disposable development build before replacing any original asset.

## 6. Lua injection

Inject one Lua file or a directory containing `.lua` files. The default destination inside the PAK is `Script/`, and the default output is `<input-name>.lua.pak`:

```bash
ue4tool lua-inject /sdcard/Download/game.pak \
  /sdcard/Download/lua \
  --output /sdcard/Download/game-with-lua.pak \
  --target-prefix Script \
  --version v8b \
  --mount-point ../../../
```

For one Lua file with a specific target name:

```bash
ue4tool lua-inject ./game.pak ./init.lua \
  --output ./game-with-lua.pak \
  --target-prefix Script \
  --target-file init.lua \
  --version v8b
```

For an input PAK with a known project AES key:

```bash
ue4tool lua-inject ./encrypted-project.pak ./lua \
  --output ./project-with-lua.pak \
  --aes-key YOUR_PROJECT_AES_KEY \
  --version v8b
```

The command unpacks the input into a temporary directory, copies only `.lua` files, and repacks a new output PAK. The original PAK is not overwritten by default. To replace it deliberately, use `--in-place`; the tool creates a timestamped backup first:

```bash
ue4tool lua-inject ./game.pak ./lua \
  --output ./game.pak \
  --in-place \
  --version v8b
```

When an AES key is supplied, it is used to read the source PAK. This focused tool does not create encrypted output PAKs.

## 7. Basic command reference

```text
ue4tool --help
ue4tool pak-unpack --help
ue4tool pak-repack --help
ue4tool lua-inject --help
```

Common options are:

| Option | Used by | Meaning |
|---|---|---|
| `--repak PATH` | All three commands | Use a specific `repak` executable. |
| `--aes-key KEY` | `pak-unpack`, `lua-inject` | Read an encrypted PAK with your known project key. |
| `--version VERSION` | `pak-repack`, `lua-inject` | UE4 PAK version passed to `repak`. |
| `--mount-point PATH` | `pak-repack`, `lua-inject` | PAK mount point; commonly `../../../`. |
| `--compression TYPE` | `pak-repack`, `lua-inject` | Optional compression type. |
| `--strip-prefix PATH` | `pak-unpack`, `lua-inject` | Remove the specified prefix while unpacking. |
| `--quiet` | `pak-unpack`, `pak-repack` | Reduce `repak` terminal output. |
| `--in-place` | `lua-inject` | Allow replacement of the input after a backup is created. |

## 8. Updating the tool

From the cloned directory:

```bash
cd ~/ue4-termux-tool
git pull --ff-only
bash install-termux.sh
```

## Troubleshooting

If `ue4tool` is not found, restart the Termux shell or check that `$PREFIX/bin` is on `PATH`:

```bash
echo "$PATH"
command -v ue4tool
```

If `repak` is not found, rebuild it or pass its absolute path:

```bash
bash install-termux.sh
ue4tool pak-unpack ./game.pak --repak "$HOME/.cargo/bin/repak"
```

If unpacking fails, confirm that the PAK version is supported by the installed `repak`, that the PAK is not corrupted, and that the AES key is correct when encryption is enabled. If repacking produces a package that your own UE4 build cannot read, retry with the exact PAK version, mount point, and compression settings used by your project.

## License and authorized use

This repository is a utility for the user's own UE4 project assets. Keep backups, work on copies, and do not use it to bypass protection or interfere with services you do not control.
