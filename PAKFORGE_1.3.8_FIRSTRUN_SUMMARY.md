# PakForge 1.3.8 — Immediate-Start First-Run UX

PakForge 1.3.8 improves the first-run experience for Termux users. The `pakforge` command now opens immediately instead of blocking on dependency installation. The first-time bootstrap installs only the minimum curl, git, and Python runtime before handing off; Python packages, Lua 5.1, unzip, Rust, and repak are deferred to the background worker. A transparent setup worker runs separately and records its progress so the user can continue interacting with the tool while dependencies are prepared. The one-command `bootstrap.sh` path now displays a dependency-light first-run screen immediately, prepares the minimum Termux prerequisites and repository in the background, and hands off to the normal launcher as soon as it is ready; optional Python dependencies, Lua 5.1, and `repak` continue through the background worker.

## User-visible behavior

The generated Termux launcher starts `pakforge_setup.py --background` with `nohup` unless setup is already complete or the user sets `PAKFORGE_NO_SETUP=1`. The launcher then starts the normal PakForge CLI. If core Python dependencies are not available yet, it falls back to the dependency-light `pakforge_first_run.py` screen. The bootstrap command uses the same immediate screen while the minimum Termux runtime, repository checkout, and launcher are prepared. Both screens show an animated progress bar with a stage-estimate percentage, remaining percentage, and current stage. They also show elapsed time, a heartbeat counter, last-update timestamp, an ETA estimate when enough stage timing exists, and measured local bytes when available. Because Termux package managers do not consistently expose exact total download sizes, the UI explicitly displays `calculating` or `unavailable` instead of inventing MB/GB values. Setup status stores the same fields in JSON for scripts and diagnostics. Bootstrap locks include a PID when possible; a dead-PID lock is recovered immediately, while a lock without a PID is only treated as stale after a conservative timeout. The screen reports setup progress, supports retry with Enter, and exits with `q` without terminating the shell or force-closing the application.

When setup is ready, the first-run screen transfers control to `pakforge.py`. If setup fails, it displays the recorded failure and points the user to the setup status and log locations instead of hiding the error.

## Unified `tool` and `pakforge` launchers

The generated `tool` command now opens the same neon PakForge UI as `pakforge`, avoiding two different beginner experiences. The older repak-based wrapper remains available explicitly with `UE4TOOL_LEGACY=1 tool ...`.

## PAKFORGE ULTIMATE beginner menu

The normal neon interface is now a compact three-option menu with no submenus or typed CLI commands:

```text
═══════════════════════════════════════
          PAKFORGE ULTIMATE
═══════════════════════════════════════

1. UNPACK PAK
2. REPACK PAK (Lua Inject)
3. EXIT

SELECT (1-3):
```

All interactive filesystem operations use the Termux SD-card layout. PAK files are selected from `/sdcard/Download/`, extracted files are written to `/sdcard/Download/UNPACKED/<pak_name>/`, edits are read from `/sdcard/Download/EDIT/`, and the repacked result is written to `/sdcard/Download/MODDED_<pak_name>.pak`. If the EDIT folder is empty, the menu shows `EDIT folder is empty. Place your modified files in /sdcard/Download/EDIT/ first.`. Repack defaults to the target path `Content/Lua/Mods`; after writing the output, PakForge reopens it with the native parser and shows `✅ Verification passed!` only after that structural check succeeds. Advanced developer workflows remain available through CLI subcommands, while normal `pakforge` and `tool` launches open this same interface.

## Startup auto-update

Every normal `pakforge` or `tool` launch starts a non-blocking check of the public `origin/main` branch. Fast-forward updates are downloaded in the background and launcher scripts are regenerated for the next launch, so the current UI is never interrupted. Dirty worktrees are detected and skipped safely instead of being overwritten. Update state is available through `pakforge update-status`, with details in `~/.local/state/pakforge/update-status.json` and `~/.local/state/pakforge/update.log`. Use `PAKFORGE_NO_UPDATE=1 pakforge` only when the update check must be disabled for one launch.

## New command and opt-out

Use the following command to inspect current setup state, the last error, and paths to the setup log and lock:

```text
pakforge setup-status
```

To disable automatic background setup for a particular invocation or shell session, use:

```text
PAKFORGE_NO_SETUP=1 pakforge
```

The normal PakForge command remains available during setup. The setup worker is only a convenience for dependencies and does not alter PAK contents, Lua source, bytecode, encryption metadata, or patch data.

## State and logging

Setup state is stored under:

```text
~/.local/state/pakforge/setup-status.json
~/.local/state/pakforge/setup.log
~/.local/state/pakforge/setup.lock/
```

`XDG_STATE_HOME` is honored when configured. The lock directory prevents multiple background workers from running concurrently. The setup log contains timestamped command and result information, including failures, so a user can diagnose package-manager problems without rerunning the full installer.

## Dependency sources

The setup worker uses only official local package-manager commands and Python/Rust package installers. It does not download raw URL binaries. The supported system package-manager paths are:

| Environment | Commands used |
| :--- | :--- |
| Termux | `pkg install python python-pip unzip rust lua51 -y` |
| Debian/Ubuntu | `sudo apt-get update -y`, then `sudo apt-get install -y python3 python3-pip unzip cargo lua5.1` |
| Arch Linux | `sudo pacman -Sy --noconfirm`, then `sudo pacman -S --needed --noconfirm python python-pip unzip rust lua51` |

Python dependencies are installed with `python3 -m pip install --upgrade rich pytz pycryptodome gmalg zstandard`. The optional `repak` compatibility binary is installed through Cargo with `cargo install --locked --git https://github.com/trumank/repak repak-cli` when it is not already present. Existing installations are reused when possible.

## Files included in this release

| File | Purpose |
| :--- | :--- |
| `pakforge_setup.py` | Locked background dependency worker and `--status` reporter |
| `pakforge_first_run.py` | Dependency-light first-run progress screen and ready-state handoff |
| `install-termux.sh` | Generates the immediate-start launcher and setup-status shortcut |
| `bootstrap.sh` | Ensures the new helper scripts are executable during bootstrap |
| `pakforge.py` | Version 1.3.8 and CLI integration |
| `README.md` | User documentation for setup, status, logs, and opt-out |
| `test_pakforge.py` | Setup-status and version regression coverage |
| `test_launcher.sh` | Launcher-content and version smoke coverage |

## Validation

The release was checked with Python compilation, shell syntax checks, the PakForge regression suite, the power-feature suite, the theme suite, the smoke suite, the launcher test, and `git diff --check`.

PakForge remains a terminal tool with the existing neon theme, structured JSONL operation logs, Lua 5.1 priority, PAK verification, developer workflows, and legacy `tool` compatibility preserved.

Release version: **1.3.8**.
