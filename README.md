# UE4 Termux Tool

A beginner-friendly Termux toolkit for authorized Unreal Engine 4 projects. **PakForge** is the primary Tencent/UE PAK parser and repacking utility bundled in this repository. The original `tool` command remains available as a repak-based compatibility wrapper for standard UE4 workflows.

PakForge supports direct PAK inspection, extraction, block-aware repacking, batch extraction, SHA-256 manifests, developer profiles, preflight checks, asset diffs, and reproducible build reports. The project does not bypass DRM, defeat anti-cheat, recover unknown encryption keys, or modify third-party online games. Use it only with your own project files or with explicit permission.

## Core commands

| Command | Purpose |
|---|---|
| `pakforge` | Primary direct PAK parser command. |
| `pakforge info` | Inspect PAK version, mount point, entries, compression, encryption, and sizes. |
| `pakforge unpack` | Extract a Tencent/UE PAK and create a debug log plus manifest. |
| `pakforge repack` | Repack edited files, including force-add under a target PAK directory. |
| `pakforge batch-unpack` | Extract every `.pak` file in a directory. |
| `pakforge manifest` | Create a SHA-256 manifest for an unpacked or edited directory. |
| `pakforge verify` | Detect missing, changed, or extra files against a manifest. |
| `pakforge profile` | Save and reuse project-specific PAK/Lua build settings. |
| `pakforge doctor` | Preflight-check a PAK, dependencies, parser mode, and storage. |
| `pakforge diff` | Compare two asset directories and create a JSON change report. |
| `pakforge build` | Run a profile-driven preflight, Lua build, backup, and verification workflow. |
| `pakforge auto` | Run the offline unpack, Lua decompile, edit, Lua 5.1 compile, repack, and verify loop in one command. |
| `tool logs` | List structured operation logs and show the latest log tail. |
| `tool unpack/repack/inject` | Existing repak-based compatibility workflows. |

## Neon terminal theme

PakForge uses a neon terminal presentation inspired by the supplied reference: a dark layout with purple and blue borders, cyan prompts, magenta section titles, green success states, and compact workflow panels. The interactive banner and selectors are designed for Termux screens while keeping the command output readable.

To force plain output for logs, screen readers, or terminals that do not support color, run:

```bash
PAKFORGE_PLAIN=1 pakforge
```

The standard `NO_COLOR=1` environment variable is also respected.

## First-time setup for new Termux users

Install Termux from a trusted source such as [F-Droid](https://f-droid.org/packages/com.termux/) or the [official Termux project](https://github.com/termux/termux-app). Open Termux and enter these commands **one by one**:

**Step 1 — update Termux:**

```bash
pkg update -y
```

**Step 2 — install the downloader:**

```bash
pkg install -y curl
```

**Step 3 — allow phone storage access:**

```bash
termux-setup-storage
```

Press **Allow** when Android asks for permission.

**Step 4 — first-time install with one command:**

```bash
printf '\033[2J\033[H\033[1;35mPakForge\033[0m\nStarting first-time setup in the background...\n' && curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/ue4-termux-tool/main/bootstrap.sh | bash
```

The public repository does not require GitHub login. This single command immediately shows the PakForge Launcher screen, while a background bootstrap prepares the minimum Termux prerequisites, downloads PakForge, and creates both `pakforge` and `tool` commands. The screen shows an animated bar with a stage-estimate percentage, remaining percentage, current stage, elapsed time, and an ETA estimate when enough timing data exists. Long-running package, repository, and launcher commands emit heartbeat updates while they are active, so the current stage does not remain visually frozen. It also reports measured local bytes available; exact total MB/GB and ETA are shown as unavailable or calculating when Termux's package manager does not expose them, rather than displaying invented numbers. As soon as the launcher is ready, the screen hands off to PakForge; the optional Python parser dependencies, Lua 5.1 compiler, and `repak` compatibility binary continue installing in the background. Keep Termux available while setup finishes and inspect the same live data with `pakforge setup-status`.

**Step 5 — open PakForge:**

```bash
pakforge
```

The original repak wrapper remains available as `tool`. If you use the manual installer path, run `pakforge` after the launcher is created; the same command can be run again later to repair or refresh the installation.

## Manual setup

If you prefer to run each step yourself:

```bash
pkg update -y
pkg upgrade -y
pkg install -y git python python-pip unzip rust curl
termux-setup-storage
cd ~
git clone https://github.com/itzgeniusboy/ue4-termux-tool.git
cd ue4-termux-tool
chmod +x bootstrap.sh install-termux.sh ue4tool.py pakforge.py pakforge_setup.py pakforge_first_run.py update-termux.sh
PAKFORGE_DEFER_SETUP=1 SKIP_PACKAGES=1 bash install-termux.sh
pakforge
```

The public clone works without GitHub login:

```bash
git clone https://github.com/itzgeniusboy/ue4-termux-tool.git
```

## Interactive menu — easiest method

After setup, run this single command:

```bash
pakforge
```

The command opens the PakForge Launcher immediately. During the very first bootstrap, the launcher remains visible while the minimum Termux runtime and repository are prepared, with an animated stage-estimate percentage bar, remaining percentage, current stage, elapsed time, ETA when measurable, heartbeat counter, last-update timestamp, and download-size fields when the underlying operation reports them. Heartbeat updates are emitted during long-running commands, and the screen uses a reduced-flicker redraw. If Python modules, Lua 5.1, or the optional `repak` compatibility binary are missing, a transparent setup worker starts in the background using official package managers and fixed `pip`/Cargo commands. The setup output is stored at `~/.local/state/pakforge/setup.log`, and status is available with `pakforge setup-status`. If an earlier bootstrap died without cleanup, the next run detects and removes its stale lock; a live bootstrap lock is left untouched. The first-run screen lets you press Enter to refresh, `s` to view full JSON status, or `q` to exit; once setup reaches `ready`, the original PakForge command continues automatically. Use `PAKFORGE_NO_SETUP=1 pakforge` to disable automatic dependency setup. Background update checks remain separate in `~/.local/state/pakforge/update.log`; disable them with `PAKFORGE_NO_UPDATE=1 pakforge`. The compatibility command `tool` remains available for repak-based workflows.

The menu provides:

```text
1) PAK Unpack
2) PAK Repack
3) Lua Inject
4) Update Tool
5) PAK Info / SHA-256
6) Create SHA-256 Manifest
7) Verify SHA-256 Manifest
8) Batch Unpack All PAKs
0) Exit
```

The PakForge menu searches `/sdcard/Download/` for `.pak` files, shows parser-specific metadata, extracts with progress, creates debug logs and manifests, and supports the original PAK/EDIT/RESULT folder workflow. Its background update runs separately, so opening the menu does not wait for a download. The `tool` menu continues to check `repak` and supports Lua injection.

If the menu cannot find a file, enter its full path when prompted. Storage permission is enabled by running:

```bash
termux-setup-storage
```

## PakForge command-line use

```bash
# Inspect PAK entries, compression, encryption, logical sizes, index encryption, and ZSTD dictionary usage.
pakforge info /sdcard/Download/game.pak --export /sdcard/Download/game-info.json

# Extract with a debug log and SHA-256 manifest (4 workers by default).
pakforge unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked

# Use one worker for low-memory devices, or increase it for fast storage.
pakforge unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked --workers 2

# Repack edited files using the source PAK template.
pakforge repack /sdcard/Download/game.pak \
  /sdcard/Download/game-unpacked /sdcard/Download/game-result.pak --full --workers 4

# Add or update files under a specific directory inside the PAK.
pakforge repack /sdcard/Download/game.pak \
  /sdcard/Download/my-files /sdcard/Download/game-result.pak \
  --target-prefix Content/Lua/Mods

# Fast strict in-place patch: replace only existing files whose encoded payload fits.
pakforge repack /sdcard/Download/game.pak \
  /sdcard/Download/changed-files /sdcard/Download/game-patched.pak \
  --patch --verify

# Process multiple PAK files.
pakforge batch-unpack /sdcard/Download/paks /sdcard/Download/unpacked

# Optionally create readable .lua siblings for extracted .luac files.
pakforge unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked --decompile-lua
pakforge batch-unpack /sdcard/Download/paks /sdcard/Download/unpacked --decompile-lua

# Run the complete offline unpack -> decompile -> edit -> compile -> repack -> verify loop.
pakforge auto \
  --pak /sdcard/Download/base.pak \
  --edit-dir /sdcard/Download/my_lua_edits \
  --output /sdcard/Download/modded.pak \
  --target-prefix Content/Lua \
  --workers 4

# Omit --edit-dir to pause in the temporary extracted tree for interactive edits.
# The default report is modded.pak.auto-report.json; use --report to choose another path.

# Create and verify an edited-directory manifest.
pakforge manifest /sdcard/Download/game-unpacked
pakforge verify /sdcard/Download/game-unpacked
```

The `--target-prefix` value must be a relative PAK directory; parent traversal is rejected. PakForge refuses to replace an existing output by default. Use `--overwrite` only after keeping a separate copy of important data. The `--is-od` option is available for OD/custom PAK handling. The original `tool` command remains available for repak-based `unpack`, `repack`, `inject`, `info`, `batch-unpack`, `manifest`, and `verify` workflows.

The native `unpack` and `repack` commands accept `--workers N` (default `4`). Extraction uses atomic per-file replacement and updates the progress display from the coordinator thread. Repack stages edited input files concurrently, then keeps payload serialization single-threaded so offsets, hashes, and index order remain deterministic. If the Termux runtime cannot create a worker pool, PakForge falls back to single-threaded processing. Set `--workers 1` for the most conservative memory profile.

`pakforge repack --patch` is a strict fast path: it copies the original PAK, replaces only changed existing paths, and preserves the original file size, payload offsets, index bytes, and footer. Uncompressed replacements must fit their original allocated slot; compressed replacements must fit every original physical compression block. Patch mode refuses new files, path remapping, `--target-prefix`, and `--full`, rather than silently rebuilding the archive. Use `--verify` to reopen the patched PAK after the in-place writes.

Native PAK entries with compression method `CM_OODLE` (`3`) are supported through an optional, user-supplied Oodle2 runtime. PakForge checks `PAKFORGE_OODLE_DLL`, `SOURCE/oodle2.dll`, the repository directory, and the system library path, then calls `OodleLZ_Decompress` and `OodleLZ_Compress` through `ctypes`. PakForge does not download or bundle the proprietary DLL. Existing Oodle entries require the DLL to unpack; when an edited Oodle entry is repacked without the DLL, newly encoded blocks are written as ZSTD and the entry metadata is updated accordingly. Other compression methods are unchanged.

The optional `--decompile-lua` flag searches for `unluac_patched.jar` in the repository `SOURCE` directory, beside `pakforge.py`, or the system `PATH`. Java must also be available. Each extracted `.luac` remains unchanged; PakForge writes the decompiler output as a `.lua` sibling. For Tencent-style bytecode, the first 34 bytes are preserved and the remaining bytes are nibble-swapped only when byte index 33 is greater than 2, using a temporary staging copy. Decompilation is limited to 30 seconds per file. If the JAR, Java, or a valid decompilation result is unavailable, PakForge keeps the raw `.luac` and continues unpacking.

The `auto` command is intended for authorized offline/test projects. It creates a temporary extraction workspace, decompiles available Lua bytecode, compares the supplied edit directory against the decompiled baseline, compiles only changed `.lua` files with Lua 5.1, injects the resulting `.luac` files below `--target-prefix`, reopens the output PAK for structural verification, and writes a JSON report. Temporary files are removed on success or failure. If `--edit-dir` is omitted, the command pauses for an interactive edit; CI/CD runs should always provide it. Existing output files are refused unless `--overwrite` is explicitly supplied.

## Structured bug logs

Every command run through the native `pakforge` CLI or legacy `tool` wrapper creates an append-only JSONL operation log containing the operation name, execution steps, repak command summary, stdout/stderr, exit code, retry result, Python/Termux context, and traceback when an unexpected exception occurs. AES keys, tokens, passwords, and other secret-like arguments are redacted. The detailed log stays local; only the existing sanitized diagnostic report is eligible for the optional anonymous relay.

Show recent logs from the legacy wrapper:

```bash
tool logs
```

Show recent logs from the native parser:

```bash
pakforge logs --tail 20
```

Legacy-wrapper logs are stored under `~/.local/state/tool/logs/`; native PakForge logs are stored under `~/.local/state/pakforge/logs/`. When an operation fails, the terminal prints the exact operation-log path, so the real failing step, exception type, source line, and subprocess output can be identified instead of relying on a generic exit code.

## Simple command-line use

The shortest command forms are:

### Adaptive format detection

PakForge can try the standard and OD parser modes automatically, then report the detected PAK version, mount point, compression, encryption, ZSTD dictionary state, and supported workflows:

```bash
pakforge detect /sdcard/Download/game.pak
pakforge detect /sdcard/Download/game.pak --json
```

### One-command Lua pipeline

The Lua pipeline performs detection, Lua file discovery, target-prefix mapping, repack, and post-repack verification. Use `--compile-lua` when the edited directory contains Lua source and the target offline project expects Lua 5.1 bytecode. PakForge checks `luac5.1` and then `luac51`; if neither exists, it transparently runs the official package manager in the foreground (`pkg install lua51 -y`, `sudo apt install lua5.1 -y`, or `sudo pacman -S lua51 --noconfirm`) and prints the exact command. No raw URL or downloaded binary is used. Use `--dry-run` to generate a plan without writing an output PAK:

```bash
pakforge lua-pipeline \
  --pak /sdcard/Download/game.pak \
  --lua-dir /sdcard/Download/MyLua \
  --target-prefix Content/Lua/Mods \
  --output /sdcard/Download/game-lua.pak \
  --overwrite \
  --compile-lua \
  --verify
```

If the output should only be planned first:

```bash
pakforge lua-pipeline \
  --pak /sdcard/Download/game.pak \
  --lua-dir /sdcard/Download/MyLua \
  --target-prefix Content/Lua/Mods \
  --output /sdcard/Download/game-lua.pak \
  --dry-run
```

The pipeline automatically reports when the PAK is invalid or unsupported and writes a JSON report after a verified repack. Use `--is-od` when the project is known to require OD parsing. Add `--backup` when replacing an existing output so PakForge can restore it if repacking or verification fails. For a normal edited directory, `pakforge repack ... --verify` reopens the output and validates its index, offsets, mount point, and entry metadata.

## Developer build workflow

Profiles keep project-specific paths and parser settings out of long command lines. Create one profile, review it, and reuse it for repeatable debug or release builds:

```bash
pakforge profile init debug \
  --pak /sdcard/Download/game.pak \
  --lua-dir /sdcard/Download/MyLua \
  --output /sdcard/Download/game-debug.pak \
  --target-prefix Content/Lua/Mods

pakforge profile list
pakforge profile show debug
```

Run a preflight check before building. It reports parser mode, PAK readability, dependencies, available storage, and supported capabilities:

```bash
pakforge doctor /sdcard/Download/game.pak
pakforge doctor /sdcard/Download/game.pak --json
```

Compare two unpacked asset trees before deciding what to package:

```bash
pakforge diff /sdcard/Download/old-assets /sdcard/Download/new-assets
pakforge diff /sdcard/Download/old-assets /sdcard/Download/new-assets --output /sdcard/Download/asset-diff.json
```

Run the repeatable developer build. It performs preflight, Lua discovery, target-prefix injection, verification, timestamped backup when replacing an output, rollback on failure, and a JSON build report:

```bash
pakforge build --profile debug --overwrite
```

Use a dry run to create the plan and report without writing the output PAK:

```bash
pakforge build --profile debug --dry-run
```

The shortest command forms are:

```bash
tool unpack input.pak unpacked-folder
tool repack unpacked-folder output.pak
tool inject input.pak lua-folder output.pak
```

Files in the Android Download folder use paths like `/sdcard/Download/game.pak`.

### 1. PAK unpack

```bash
tool unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked
```

If the output folder is omitted, the tool uses the PAK filename without its extension:

```bash
tool unpack /sdcard/Download/game.pak
```

For an encrypted PAK from your own project, pass its known AES key:

```bash
tool unpack /sdcard/Download/game.pak /sdcard/Download/game-unpacked \
  --aes-key YOUR_PROJECT_AES_KEY
```

### 2. PAK repack

After editing the unpacked directory:

```bash
tool repack /sdcard/Download/game-unpacked /sdcard/Download/game-repacked.pak
```

The default PAK version is `v8b`. Select the exact version used by your UE4 project when needed:

```bash
tool repack /sdcard/Download/game-unpacked /sdcard/Download/game-repacked.pak \
  --version v8b
```

Optional compression:

```bash
tool repack /sdcard/Download/game-unpacked /sdcard/Download/game-repacked.pak \
  --version v8b --compression zlib
```

### 3. Lua inject

Inject a Lua file or a folder containing `.lua` files:

```bash
tool inject /sdcard/Download/game.pak \
  /sdcard/Download/lua \
  /sdcard/Download/game-with-lua.pak
```

Lua files go into `Script/` by default. To select another PAK folder:

```bash
tool inject game.pak lua-folder injected.pak \
  --target-prefix MyScripts
```

For a single Lua file with a specific target filename:

```bash
tool inject game.pak init.lua injected.pak \
  --target-prefix Script --target-file init.lua
```

For an encrypted source PAK from your own project:

```bash
tool inject encrypted-project.pak lua-folder project-with-lua.pak \
  --aes-key YOUR_PROJECT_AES_KEY
```

The tool reads the source PAK, copies Lua files into temporary staging, and creates a new output PAK. It does not create encrypted output.

## Backup behavior

Native PakForge developer builds remain conservative by default: they refuse to replace an existing output unless `--overwrite` is supplied. When replacing an output, `pakforge build` enables a timestamped backup by default and restores it if repacking or post-build verification fails. Use `--no-backup` only when the project workflow already manages its own artifacts.

The legacy `tool` wrapper retains its existing no-automatic-backup behavior. If you deliberately use `tool inject --in-place`, keep your own copy of important project files.

## Useful options

| Option | Used by | Purpose |
|---|---|---|
| `--version VERSION` | `repack`, `inject` | UE4 PAK version passed to `repak`; default is `v8b`. |
| `--compression TYPE` | `repack`, `inject` | Optional `zlib`, `gzip`, `zstd`, `lz4`, or `oodle` compression. |
| `--mount-point PATH` | `repack`, `inject` | PAK mount point; default is `../../../`. |
| `--aes-key KEY` | `unpack`, `inject` | Read an encrypted PAK with your known project key. |
| `--target-prefix PATH` | `inject` | Destination directory inside the PAK; default is `Script`. |
| `--in-place` | `inject` | Directly replace input without creating a backup. |
| `--repak PATH` | PAK commands | Use a specific `repak` executable. |
| `--overwrite` | `unpack`, `repack`, `inject`, `batch-unpack` | Explicitly allow replacing an existing output. |
| `--workers N` | `unpack`, `repack`, `batch-unpack` | Bound parallel extraction/input staging; default `4`, use `1` for single-threaded mode. |
| `--export PATH` | `info` | Export safe PAK metadata as JSON. |
| `--output PATH` | `manifest` | Choose a custom manifest path. |
| `--manifest PATH` | `verify` | Verify against a manifest stored elsewhere. |

View all options:

```bash
tool --help
tool unpack --help
tool repack --help
tool inject --help
```

## Update the tool

Opening `tool` automatically checks for updates in the background. You can also select option `4` for a foreground update, or run this command manually:

```bash
bash ~/ue4-termux-tool/update-termux.sh
```

The update script pulls the public repository and rebuilds the installed `repak` binary only when the repository changed.

## Troubleshooting

If `tool` is not found, restart Termux or run:

```bash
export PATH="$PREFIX/bin:$PATH"
tool --help
```

If `repak` is missing:

```bash
export PATH="$HOME/.cargo/bin:$PREFIX/bin:$PATH"
bash ~/ue4-termux-tool/install-termux.sh
repak --help
```

The installer now creates a stable `$PREFIX/bin/repak` link after Cargo builds `repak`, so the command remains available after Termux is restarted.

### Performance notes

The `tool` menu stays responsive because background update checks run at most once every six hours after a successful check. You can use `TOOL_UPDATE_INTERVAL_SECONDS` to choose a longer or shorter interval for your own device, or temporarily skip background checks with `TOOL_NO_AUTO_UPDATE=1 tool`.

`inject` is naturally slower than `unpack` and `repack`: it must unpack the source PAK into temporary staging, copy selected Lua files, then build a new PAK. This tool does not create backup files.

If storage paths do not work:

```bash
termux-setup-storage
ls -lh /sdcard/Download
```

If PAK unpacking fails, confirm that the PAK is not corrupted, that the exact project AES key is correct when encryption is enabled, and that the PAK version is supported by the installed `repak`. If a generated PAK is not readable by your own UE4 build, retry using the version, mount point, and compression settings used by that project.

## Automatic bug recovery

When `tool unpack`, `tool repack`, or `tool inject` encounters a handled error, it saves a small diagnostic report locally, checks for a newer public version, and retries the same operation once. This can automatically recover bugs that have already been fixed and published.

Reports are stored in:

```text
~/.local/state/tool/error-<timestamp>.json
```

The local report contains only the operation name, sanitized error text, exit code, Python version, platform, and Termux status. It does **not** contain PAK contents, Lua source, AES keys, or full file paths. To disable the automatic retry for one command:

```bash
TOOL_NO_AUTO_RETRY=1 tool unpack game.pak
```

> Installation errors, including a missing `repak` PATH entry, do not send a Telegram report. Reporting begins only when a supported `tool unpack`, `tool repack`, or `tool inject` operation reaches a handled failure. This prevents package-install logs and storage setup output from being forwarded.

### Optional anonymous relay

The public release is connected to the HTTPS relay at `https://ue4bugrelay-vlych7sk.manus.space/api/report`. On the first handled failure, the tool asks:

```text
Send anonymous bug report? [y/N]
```

Answering `y` saves the choice in `~/.config/ue4tool/report_consent`. The tool then sends **only** the operation, sanitized error message, tool version, exit code, and platform. It never sends AES keys, PAK contents, Lua source, or full local paths. A report is sent over HTTPS and the server independently checks the same privacy rules before forwarding any diagnostic.

New non-duplicate diagnostics are added to the bot-managed GitHub triage file: [`.ue4-bug-relay/unresolved-reports.md`](https://github.com/itzgeniusboy/ue4-termux-tool/blob/main/.ue4-bug-relay/unresolved-reports.md). This is a short sanitized queue for the project owner and maintainer; it is not a raw crash dump. When a fix is made and tested, the corresponding handled entry is removed from that file.

To permanently suppress relay reporting for one command, even when consent was given earlier, run:

```bash
TOOL_NO_REPORT=1 tool unpack game.pak
```

Advanced maintainers can override the HTTPS relay address with `UE4TOOL_REPORT_ENDPOINT`. Do not set it to an untrusted URL.

## Repository

[https://github.com/itzgeniusboy/ue4-termux-tool](https://github.com/itzgeniusboy/ue4-termux-tool)
