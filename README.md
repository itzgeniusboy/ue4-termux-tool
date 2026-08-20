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
paktool
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

If Android storage access has not been enabled, run `termux-setup-storage` once and then start `paktool` again.

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

The same `paktool` executable retains advanced command-line workflows for maintainers and authorized project developers:

```bash
paktool --help
paktool info <input.pak>
paktool unpack <input.pak> <output-directory>
paktool repack <input-directory> <output.pak>
paktool lua-pipeline --help
paktool auto --help
paktool profile --help
paktool doctor --help
paktool diff --help
paktool build --help
paktool setup-status
paktool update-status
paktool logs --tail 30
```

The native backend supports UE/Tencent PAK versions 7 through 12+, path-safety checks, AES/SM4/SIMPLE handling when the authorized key is supplied, ZLIB/ZSTD and optional Oodle support, parallel I/O with a safe single-threaded fallback, Lua 5.1 compiler detection, optional Lua decompilation, full repacking, patch mode, and post-repack verification. Exact support depends on the source PAK and available local dependencies.

## Logging and diagnostics

Structured JSONL operation logs are stored under `~/.local/state/paktool/logs/`. Setup state and setup output are stored under `~/.local/state/paktool/`. Diagnostics are local and sanitized; Paktool does not include Telegram uploaders, telemetry, tracking, license servers, device fingerprints, or automatic remote bug reporting.

If a PAK operation fails, first inspect the local log, confirm that the input PAK is intact, verify the authorized project key when encryption is enabled, and check that the required local dependencies are available. For an empty-output `repak` failure, the diagnostic also reports version and executable context where available.

## Repository

[itzgeniusboy/ue4-termux-tool](https://github.com/itzgeniusboy/ue4-termux-tool)

The repository can be renamed manually through GitHub settings if desired. Until that is done, setup scripts must continue to use the current repository URL above.
