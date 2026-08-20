# Paktool

Paktool is a Termux-based Unreal Engine 4 PAK interoperability utility for authorized offline projects. It combines a native Tencent/UE PAK parser with optional `repak` compatibility workflows, Lua 5.1 compilation and injection, verification, structured local logs, and a neon terminal interface.

Use Paktool only with project files that you own or are explicitly authorized to modify. It is not designed to bypass DRM, defeat anti-cheat, recover unknown encryption keys, or modify third-party online-game clients.

## One-command setup

Run this command in Termux:

```bash
printf '\033[2J\033[H\033[1;35mPaktool\033[0m\nStarting first-time setup in the background...\n' && curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/ue4-termux-tool/main/bootstrap.sh | bash
```

The launcher opens immediately. Minimum Termux packages and the Paktool source are prepared first; Python packages, Lua 5.1, Rust, and the optional `repak` compatibility binary continue through the background setup worker. Official package managers and `pip`/Cargo are used; binaries are not downloaded from arbitrary URLs.

After setup, the normal command is:

```bash
tool
```

The launcher synchronizes `origin/main` before opening the latest Paktool UI. Set `PAKTOOL_NO_UPDATE=1` to skip that synchronization for one launch. Set `PAKTOOL_NO_SETUP=1` to skip background dependency setup. Use `PAKTOOL_PLAIN=1` or `NO_COLOR=1` for plain output.

## SD-card workspace

Paktool creates this workspace automatically when the command starts:

| Directory | Purpose |
|---|---|
| `/sdcard/Paktool/PAK/` | Source `.pak` files |
| `/sdcard/Paktool/EDIT/` | Modified `.lua` and `.luac` files |
| `/sdcard/Paktool/UNPACKED/` | Extracted PAK contents |
| `/sdcard/Paktool/MODDED/` | Repacked PAK outputs |

If Android storage access has not been enabled, run `termux-setup-storage` once and then start `tool` again.

## Beginner menu

The interactive menu is intentionally limited to four digit-only choices:

```text
1. UNPACK PAK
2. REPACK PAK (Full)
3. LUA INJECT (Only Lua files, no full rebuild)
4. EXIT
SELECT (1-4):
```

`UNPACK PAK` scans `/sdcard/Paktool/PAK/`, extracts the selected file into `/sdcard/Paktool/UNPACKED/<pak-name>/`, and leaves the editable workspace at `/sdcard/Paktool/EDIT/`. `REPACK PAK (Full)` uses all files in `EDIT/` and writes `MODDED_<source-name>.pak` into `MODDED/`. `LUA INJECT` copies only `.lua` and `.luac` files from `EDIT/`, targets `Content/Lua/Mods` by default, and creates a verified output in `MODDED/`.

## Developer commands

The same `tool` executable retains advanced command-line workflows for maintainers and authorized project developers:

```bash
tool --help
tool info <input.pak>
tool unpack <input.pak> <output-directory>
tool repack <source.pak> <edited-directory> <output.pak> --full --verify
tool delete <source.pak> <pak-path> [more-paths...] <output.pak>
tool lua-pipeline --help
tool auto --help
tool profile --help
tool doctor --help
tool diff --help
tool build --help
tool setup-status
tool update-status
tool logs --tail 30
```

The native backend supports UE/Tencent PAK versions 7 through 12+, path-safety checks, AES/SM4/SIMPLE handling, ZLIB/ZSTD and optional Oodle support, parallel I/O with a safe single-threaded fallback, Lua 5.1 compiler detection, optional Lua decompilation, full repacking, patch mode, explicit deletion of selected logical PAK entries, and post-repack verification. The configured SM4 derivation secrets are intended only for authorized project files. Exact support depends on the source PAK and available local dependencies.

## Delete selected files
The delete operation never overwrites the source PAK by default. First inspect logical paths with `tool info game.pak`, then create a new verified PAK:

```bash
tool delete game.pak Content/Example.uasset cleaned.pak
# A unique basename may also be used:
tool delete game.pak Example.uasset cleaned.pak
```

If two entries share the same basename, use the full logical path. Add `--overwrite` only when you intentionally want to replace an existing output. The source PAK is left unchanged.

## Logging and diagnostics

Structured JSONL operation logs are stored under `~/.local/state/paktool/logs/`. Setup state and setup output are stored under `~/.local/state/paktool/`. Diagnostics are local and sanitized; Paktool does not include Telegram uploaders, telemetry, tracking, license servers, device fingerprints, or automatic remote bug reporting.

If a PAK operation fails, first inspect the local log, confirm that the input PAK is intact, verify the authorized project key when encryption is enabled, and check that the required local dependencies are available. For an empty-output `repak` failure, the diagnostic also reports version and executable context where available.

## Repository

[itzgeniusboy/ue4-termux-tool](https://github.com/itzgeniusboy/ue4-termux-tool)

The repository can be renamed manually through GitHub settings if desired. Until that is done, setup scripts must continue to use the current repository URL above.
