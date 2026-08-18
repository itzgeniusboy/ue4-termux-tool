# UE4 Termux Tool

A beginner-friendly Python CLI for authorized Unreal Engine 4 projects on Termux. It intentionally provides only three core workflows: **PAK unpack**, **PAK repack**, and **Lua inject**.

The project delegates UE4 PAK parsing and writing to [repak](https://github.com/trumank/repak). It does not bypass DRM, defeat anti-cheat, recover unknown encryption keys, or modify third-party online games. Use it only with your own project files or with explicit permission.

## Core commands

| Command | Purpose |
|---|---|
| `unpack` | Extract a UE4 `.pak` through `repak`. |
| `repack` | Create a new UE4 `.pak` from an unpacked directory. |
| `inject` | Unpack a PAK, copy Lua files into it, and create a new PAK. |

## Fast setup for new Termux users

Install Termux from a trusted source such as [F-Droid](https://f-droid.org/packages/com.termux/) or the [official Termux project](https://github.com/termux/termux-app). Open Termux and run this one command:

```bash
curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/ue4-termux-tool/main/setup.sh | bash
```

The public repository does not require GitHub login. The setup script updates Termux packages, installs Git/Python/unzip/Rust, requests storage permission, clones the repository, builds `repak`, and installs `ue4tool`.

If `curl` is not installed, run:

```bash
pkg install -y curl
curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/ue4-termux-tool/main/setup.sh | bash
```

For a more cautious setup, download and inspect the script before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/ue4-termux-tool/main/setup.sh -o setup.sh
less setup.sh
bash setup.sh
```

The first installation may take several minutes because Rust builds `repak`. Do not close Termux while it is building.

## Manual setup

If you prefer to run each step yourself:

```bash
pkg update -y
pkg upgrade -y
pkg install -y git python unzip rust curl
termux-setup-storage
cd ~
git clone https://github.com/itzgeniusboy/ue4-termux-tool.git
cd ue4-termux-tool
chmod +x install-termux.sh ue4tool.py update-termux.sh
bash install-termux.sh
```

The public clone works without GitHub login:

```bash
git clone https://github.com/itzgeniusboy/ue4-termux-tool.git
```

## Interactive menu — easiest method

After setup, run:

```bash
ue4tool
```

The menu provides:

```text
1) PAK Unpack
2) PAK Repack
3) Lua Inject
4) Update Tool
0) Exit
```

The menu checks whether `repak` is installed, searches `/sdcard/Download/` for `.pak` files, asks for the required folders, and applies simple defaults. For Lua injection, the default Lua folder is `/sdcard/Download/lua`, the default PAK destination is `Script/`, and the output filename is generated automatically.

If the menu cannot find a file, enter its full path when prompted. Storage permission is enabled by running:

```bash
termux-setup-storage
```

## Simple command-line use

The shortest command forms are:

```bash
ue4tool unpack input.pak unpacked-folder
ue4tool repack unpacked-folder output.pak
ue4tool inject input.pak lua-folder output.pak
```

Files in the Android Download folder use paths like `/sdcard/Download/game.pak`.

### 1. PAK unpack

```bash
ue4tool unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked
```

If the output folder is omitted, the tool uses the PAK filename without its extension:

```bash
ue4tool unpack /sdcard/Download/game.pak
```

For an encrypted PAK from your own project, pass its known AES key:

```bash
ue4tool unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked \
  --aes-key YOUR_PROJECT_AES_KEY
```

### 2. PAK repack

After editing the unpacked directory:

```bash
ue4tool repack /sdcard/Download/game-unpacked /sdcard/Download/game-repacked.pak
```

The default PAK version is `v8b`. Select the exact version used by your UE4 project when needed:

```bash
ue4tool repack /sdcard/Download/game-unpacked /sdcard/Download/game-repacked.pak \
  --version v8b
```

Optional compression:

```bash
ue4tool repack /sdcard/Download/game-unpacked /sdcard/Download/game-repacked.pak \
  --version v8b --compression zlib
```

### 3. Lua inject

Inject a Lua file or a folder containing `.lua` files:

```bash
ue4tool inject /sdcard/Download/game.pak \
  /sdcard/Download/lua \
  /sdcard/Download/game-with-lua.pak
```

Lua files go into `Script/` by default. To select another PAK folder:

```bash
ue4tool inject game.pak lua-folder injected.pak \
  --target-prefix MyScripts
```

For a single Lua file with a specific target filename:

```bash
ue4tool inject game.pak init.lua injected.pak \
  --target-prefix Script --target-file init.lua
```

For an encrypted source PAK from your own project:

```bash
ue4tool inject encrypted-project.pak lua-folder project-with-lua.pak \
  --aes-key YOUR_PROJECT_AES_KEY
```

The tool reads the source PAK, copies Lua files into temporary staging, and creates a new output PAK. It does not create encrypted output.

## No automatic backup files

As requested, this tool does **not** create backup files. By default it refuses to overwrite the input PAK, which is the safer option:

```bash
ue4tool inject game.pak lua-folder game-with-lua.pak
```

If you deliberately want to replace the original PAK, use `--in-place`. This replaces the original directly and creates **no backup**:

```bash
ue4tool inject game.pak lua-folder game.pak --in-place
```

Always keep your own copy if the original file is important.

## Useful options

| Option | Used by | Purpose |
|---|---|---|
| `--version VERSION` | `repack`, `inject` | UE4 PAK version passed to `repak`; default is `v8b`. |
| `--compression TYPE` | `repack`, `inject` | Optional `zlib`, `gzip`, `zstd`, `lz4`, or `oodle` compression. |
| `--mount-point PATH` | `repack`, `inject` | PAK mount point; default is `../../../`. |
| `--aes-key KEY` | `unpack`, `inject` | Read an encrypted PAK with your known project key. |
| `--target-prefix PATH` | `inject` | Destination directory inside the PAK; default is `Script`. |
| `--in-place` | `inject` | Directly replace input without creating a backup. |
| `--repak PATH` | All commands | Use a specific `repak` executable. |

View all options:

```bash
ue4tool --help
ue4tool unpack --help
ue4tool repack --help
ue4tool inject --help
```

## Update the tool

From Termux, use the update script:

```bash
bash ~/ue4-termux-tool/update-termux.sh
```

Or open `ue4tool`, select option `4`, and let the menu update the project. The update pulls the public repository and rebuilds the installed `repak` binary when needed.

## Troubleshooting

If `ue4tool` is not found, restart Termux or run:

```bash
export PATH="$PREFIX/bin:$PATH"
ue4tool --help
```

If `repak` is missing:

```bash
bash ~/ue4-termux-tool/install-termux.sh
```

If storage paths do not work:

```bash
termux-setup-storage
ls -lh /sdcard/Download
```

If PAK unpacking fails, confirm that the PAK is not corrupted, that the exact project AES key is correct when encryption is enabled, and that the PAK version is supported by the installed `repak`. If a generated PAK is not readable by your own UE4 build, retry using the version, mount point, and compression settings used by that project.

## Repository

[https://github.com/itzgeniusboy/ue4-termux-tool](https://github.com/itzgeniusboy/ue4-termux-tool)
