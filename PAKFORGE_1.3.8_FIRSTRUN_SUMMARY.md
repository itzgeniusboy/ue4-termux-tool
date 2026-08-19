# PakForge 1.3.8 — Immediate-Start First-Run UX

PakForge 1.3.8 improves the first-run experience for Termux users. The `pakforge` command now opens immediately instead of blocking on dependency installation. A transparent setup worker runs separately and records its progress so the user can continue interacting with the tool while dependencies are prepared.

## User-visible behavior

The generated Termux launcher starts `pakforge_setup.py --background` with `nohup` unless setup is already complete or the user sets `PAKFORGE_NO_SETUP=1`. The launcher then starts the normal PakForge CLI. If core Python dependencies are not available yet, it falls back to the dependency-light `pakforge_first_run.py` screen. That screen reports setup progress, supports retry with Enter, and exits with `q` without terminating the shell or force-closing the application.

When setup is ready, the first-run screen transfers control to `pakforge.py`. If setup fails, it displays the recorded failure and points the user to the setup status and log locations instead of hiding the error.

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
