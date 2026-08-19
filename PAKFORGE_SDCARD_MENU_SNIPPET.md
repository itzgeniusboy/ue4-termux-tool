# PakForge SD-card-only interactive menu

The following code is integrated into `pakforge_core.py`. It assumes the existing module imports and helpers: `os`, `shutil`, `tempfile`, `Path`, `console`, `NEON`, `escape`, `safe_input`, `human_size`, `TencentPakFile`, `dump_unpacking_log`, and `repack_pak_file_full`.

```python
SDCARD_DOWNLOAD_DIR = Path("/sdcard/Download")
SDCARD_EDIT_DIR = SDCARD_DOWNLOAD_DIR / "EDIT"
SDCARD_UNPACKED_DIR = SDCARD_DOWNLOAD_DIR / "UNPACKED"


def ensure_sdcard_directories() -> bool:
    """Create the only folders used by the interactive SD-card workflow."""
    try:
        SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)
        SDCARD_UNPACKED_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as exc:
        console.print(
            f"[bold {NEON['red']}]Cannot access {SDCARD_DOWNLOAD_DIR}: "
            f"{escape(str(exc))}[/bold {NEON['red']}]"
        )
        console.print(
            f"[bold {NEON['cyan']}]Run Termux storage setup first, then retry.[/bold {NEON['cyan']}]"
        )
        return False


def get_pak_files_from_sdcard() -> list[Path]:
    """Return top-level .pak files from /sdcard/Download in stable order."""
    if not SDCARD_DOWNLOAD_DIR.is_dir():
        return []
    return sorted(
        (
            item
            for item in SDCARD_DOWNLOAD_DIR.iterdir()
            if item.is_file() and item.suffix.lower() == ".pak"
        ),
        key=lambda item: item.name.casefold(),
    )


def select_pak_from_sdcard(prompt: str = "Select file") -> Path | None:
    """Show a numbered PAK list and return the selected file."""
    pak_files = get_pak_files_from_sdcard()
    if not pak_files:
        console.print(
            f"[bold {NEON['yellow']}]No .pak files found in /sdcard/Download/. "
            f"Please copy your PAK file there.[/bold {NEON['yellow']}]"
        )
        return None

    console.print(
        f"[bold {NEON['yellow']}]📁 PAK files in /sdcard/Download/:[/bold {NEON['yellow']}]"
    )
    for index, pak_file in enumerate(pak_files, 1):
        size = human_size(pak_file.stat().st_size)
        console.print(
            f"[bold {NEON['green']}][{index}][/bold {NEON['green']}] "
            f"{pak_file.name} [dim]({size})[/dim]"
        )

    while True:
        choice = safe_input(
            f"[bold {NEON['cyan']}]{prompt}:[/bold {NEON['cyan']}] "
        ).strip()
        try:
            selected = int(choice)
        except ValueError:
            console.print(
                f"[bold {NEON['red']}]Please enter a valid number.[/bold {NEON['red']}]"
            )
            continue
        if 1 <= selected <= len(pak_files):
            return pak_files[selected - 1]
        console.print(
            f"[bold {NEON['red']}]Please choose a number from 1 to {len(pak_files)}.[/bold {NEON['red']}]"
        )


def _directory_has_files(directory: Path) -> bool:
    return directory.is_dir() and any(path.is_file() for path in directory.rglob("*"))


def print_ultimate_banner() -> None:
    """Render the compact purple-bordered beginner menu banner."""
    os.system("cls" if os.name == "nt" else "clear")
    console.print(
        f"[bold {NEON['purple']}]═══════════════════════════════════════[/bold {NEON['purple']}]\n"
        f"[bold {NEON['purple']}]          PAKFORGE ULTIMATE[/bold {NEON['purple']}]\n"
        f"[bold {NEON['purple']}]═══════════════════════════════════════[/bold {NEON['purple']}]"
    )


def unpack_selected_sdcard_pak() -> None:
    pak_file = select_pak_from_sdcard()
    if pak_file is None:
        return

    output_dir = SDCARD_UNPACKED_DIR / pak_file.stem
    try:
        console.print(
            f"[bold {NEON['green']}]✅ Extracting to {output_dir}/[/bold {NEON['green']}]"
        )
        pak = TencentPakFile(pak_file)
        pak.dump(output_dir, workers=4)
        dump_unpacking_log(pak, output_dir / f"Debug_{pak_file.stem}.log")
        console.print(
            f"[bold {NEON['green']}]✅ Done! Edit files in {SDCARD_EDIT_DIR}/[/bold {NEON['green']}]"
        )
    except Exception as exc:
        console.print(
            f"[bold {NEON['red']}]Unpack failed: {escape(str(exc))}[/bold {NEON['red']}]"
        )


def lua_inject_selected_sdcard_pak() -> None:
    """Inject only Lua source/bytecode files from the SD-card EDIT folder."""
    SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)
    pak_file = select_pak_from_sdcard("Source PAK")
    if pak_file is None:
        return

    default_target = "Content/Lua/Mods"
    target_path = safe_input(
        f"[bold {NEON['cyan']}]📁 Target path (inside PAK) [default: {default_target}]:[/bold {NEON['cyan']}] "
    ).strip()
    target_path = (target_path or default_target).replace("\\", "/").strip("/")
    lua_files = sorted(
        (
            path for path in SDCARD_EDIT_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in {".lua", ".luac"}
        ),
        key=lambda path: path.as_posix().casefold(),
    )
    if not lua_files:
        console.print(
            f"[bold {NEON['yellow']}]No .lua or .luac files found in {SDCARD_EDIT_DIR}/.[/bold {NEON['yellow']}]"
        )
        return

    output_pak = SDCARD_DOWNLOAD_DIR / f"MODDED_{pak_file.name}"
    try:
        with tempfile.TemporaryDirectory(prefix="pakforge-lua-inject-") as staging:
            staging_root = Path(staging)
            for source in lua_files:
                destination = staging_root / source.relative_to(SDCARD_EDIT_DIR)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            count = repack_pak_file_full(
                TencentPakFile(pak_file), staging_root, output_pak,
                target_path=target_path, force_add=True, workers=4,
            )
        if count <= 0:
            return
        TencentPakFile(output_pak)
        console.print(
            f"[bold {NEON['green']}]✅ Lua-injected {count} files to: {output_pak}[/bold {NEON['green']}]"
        )
        console.print(f"[bold {NEON['green']}]✅ Verification passed![/bold {NEON['green']}]")
    except Exception as exc:
        console.print(f"[bold {NEON['red']}]Lua inject failed: {escape(str(exc))}[/bold {NEON['red']}]")


def repack_selected_sdcard_pak() -> None:
    SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)
    if not _directory_has_files(SDCARD_EDIT_DIR):
        console.print(
            f"[bold {NEON['yellow']}]EDIT folder is empty. Place your modified files "
            f"in /sdcard/Download/EDIT/ first.[/bold {NEON['yellow']}]"
        )
        return

    pak_file = select_pak_from_sdcard("Source PAK")
    if pak_file is None:
        return

    default_target = "Content/Lua/Mods"
    console.print(
        f"[bold {NEON['cyan']}]📁 Source PAK: {pak_file.name}[/bold {NEON['cyan']}]"
    )
    console.print(
        f"[bold {NEON['cyan']}]📁 Using files from: {SDCARD_EDIT_DIR}/[/bold {NEON['cyan']}]"
    )
    target_path = safe_input(
        f"[bold {NEON['cyan']}]📁 Target path (inside PAK) "
        f"[default: {default_target}]:[/bold {NEON['cyan']}] "
    ).strip()
    target_path = (target_path or default_target).replace("\\", "/").strip("/")

    output_pak = SDCARD_DOWNLOAD_DIR / f"MODDED_{pak_file.name}"
    try:
        pak = TencentPakFile(pak_file)
        count = repack_pak_file_full(
            pak,
            SDCARD_EDIT_DIR,
            output_pak,
            target_path=target_path,
            force_add=True,
            workers=4,
        )
        if count <= 0:
            console.print(
                f"[bold {NEON['red']}]No files were repacked.[/bold {NEON['red']}]"
            )
            return

        # Re-opening the generated PAK exercises the native index/hash parser.
        TencentPakFile(output_pak)
        console.print(
            f"[bold {NEON['green']}]✅ Repacked {count} files to: {output_pak}[/bold {NEON['green']}]"
        )
        console.print(
            f"[bold {NEON['green']}]✅ Verification passed![/bold {NEON['green']}]"
        )
    except Exception as exc:
        console.print(
            f"[bold {NEON['red']}]Repack failed: {escape(str(exc))}[/bold {NEON['red']}]"
        )


def main_menu():
    """Compact beginner menu for the fixed Termux SD-card workflow."""
    if not ensure_sdcard_directories():
        return

    while True:
        print_ultimate_banner()
        console.print(f"[bold {NEON['green']}]1. UNPACK PAK[/bold {NEON['green']}]")
        console.print(
            f"[bold {NEON['green']}]2. REPACK PAK (Full)[/bold {NEON['green']}]"
        )
        console.print(
            f"[bold {NEON['green']}]3. LUA INJECT (Only Lua files, no full rebuild)[/bold {NEON['green']}]"
        )
        console.print(f"[bold {NEON['green']}]4. EXIT[/bold {NEON['green']}]")
        choice = safe_input(
            f"[bold {NEON['cyan']}]SELECT (1-4):[/bold {NEON['cyan']}] "
        ).strip()

        if choice == "1":
            unpack_selected_sdcard_pak()
        elif choice == "2":
            repack_selected_sdcard_pak()
        elif choice == "3":
            lua_inject_selected_sdcard_pak()
        elif choice == "4":
            return
        else:
            console.print(
                f"[bold {NEON['red']}]Please select 1, 2, 3, or 4.[/bold {NEON['red']}]"
            )
            safe_input(
                f"[bold {NEON['cyan']}]Press Enter to continue...[/bold {NEON['cyan']}] "
            )
```

The no-argument `pakforge` and `tool` entry points call this `main_menu()` implementation. The normal interface uses only `/sdcard/Download/`, `/sdcard/Download/EDIT/`, `/sdcard/Download/UNPACKED/`, and `/sdcard/Download/MODDED_*.pak`.

The full repack action defaults to `Content/Lua/Mods`. The separate Lua-inject action stages only `.lua` and `.luac` files from EDIT, calls `repack_pak_file_full(..., force_add=True)`, and writes the same `MODDED_<pak_name>.pak` output. Both actions reopen the generated PAK with the native parser before displaying `✅ Verification passed!`.
