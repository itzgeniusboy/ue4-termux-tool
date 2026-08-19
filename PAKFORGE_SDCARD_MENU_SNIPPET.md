# PakForge SD-card-only interactive menu

The following code is already integrated into `pakforge_core.py`. It assumes the existing module imports and helpers: `Path`, `console`, `NEON`, `escape`, `safe_input`, `human_size`, `TencentPakFile`, `dump_unpacking_log`, and `repack_pak_file_full`.

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
            f"[bold {NEON['red']}]Cannot access {SDCARD_DOWNLOAD_DIR}: {escape(str(exc))}[/bold {NEON['red']}]"
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


def select_pak_from_sdcard(prompt: str) -> Path | None:
    """Show a numbered PAK list and return the selected file."""
    pak_files = get_pak_files_from_sdcard()
    if not pak_files:
        console.print(
            "[bold #FFAA00]No .pak files found in /sdcard/Download/. "
            "Please copy your PAK file there.[/bold #FFAA00]"
        )
        return None

    console.print("[bold #00E5FF]PAK files in /sdcard/Download/[/bold #00E5FF]")
    for index, pak_file in enumerate(pak_files, 1):
        size = human_size(pak_file.stat().st_size)
        console.print(
            f"[bold #39FF14]{index}[/bold #39FF14]. {pak_file.name} [dim]({size})[/dim]"
        )

    while True:
        choice = safe_input(
            f"[bold #00E5FF]{prompt} (1-{len(pak_files)}):[/bold #00E5FF] "
        ).strip()
        try:
            selected = int(choice)
        except ValueError:
            console.print("[bold #FF0055]Please enter a valid number.[/bold #FF0055]")
            continue
        if 1 <= selected <= len(pak_files):
            return pak_files[selected - 1]
        console.print(
            f"[bold #FF0055]Please choose a number from 1 to {len(pak_files)}.[/bold #FF0055]"
        )


def _directory_has_files(directory: Path) -> bool:
    return directory.is_dir() and any(path.is_file() for path in directory.rglob("*"))


def unpack_selected_sdcard_pak() -> None:
    pak_file = select_pak_from_sdcard("Select PAK to unpack")
    if pak_file is None:
        return

    output_dir = SDCARD_UNPACKED_DIR / pak_file.stem
    try:
        console.print(f"[bold #00E5FF]Unpacking: {pak_file.name}[/bold #00E5FF]")
        pak = TencentPakFile(pak_file)
        pak.dump(output_dir, workers=4)
        dump_unpacking_log(pak, output_dir / f"Debug_{pak_file.stem}.log")
        console.print(f"[bold #39FF14]Unpacked files: {output_dir}[/bold #39FF14]")
    except Exception as exc:
        console.print(f"[bold #FF0055]Unpack failed: {escape(str(exc))}[/bold #FF0055]")


def repack_selected_sdcard_pak() -> None:
    SDCARD_EDIT_DIR.mkdir(parents=True, exist_ok=True)
    if not _directory_has_files(SDCARD_EDIT_DIR):
        console.print(
            "[bold #FFAA00]EDIT folder is empty. Place your modified .lua or .luac "
            "files in /sdcard/Download/EDIT/ first.[/bold #FFAA00]"
        )
        return

    pak_file = select_pak_from_sdcard("Select source PAK to repack")
    if pak_file is None:
        return

    target_path = safe_input(
        "[bold #00E5FF]Target path inside the PAK "
        "(example: Content/Lua/Mods):[/bold #00E5FF] "
    ).strip().replace("\\", "/").strip("/")
    if not target_path:
        console.print("[bold #FF0055]A target path is required.[/bold #FF0055]")
        return

    output_pak = SDCARD_DOWNLOAD_DIR / f"MODDED_{pak_file.name}"
    try:
        console.print(
            f"[bold #00E5FF]Repacking with Lua injection: {pak_file.name}[/bold #00E5FF]"
        )
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
            console.print("[bold #FF0055]No files were repacked.[/bold #FF0055]")
            return
        console.print(f"[bold #39FF14]Repacked {count} file(s).[/bold #39FF14]")
        console.print(f"[bold #39FF14]Output: {output_pak}[/bold #39FF14]")
    except Exception as exc:
        console.print(f"[bold #FF0055]Repack failed: {escape(str(exc))}[/bold #FF0055]")


def main_menu() -> None:
    """Simple SD-card-only menu for beginner-friendly PAK workflows."""
    if not ensure_sdcard_directories():
        return

    while True:
        console.print("\n[bold #00E5FF]1.[/bold #00E5FF] UNPACK PAK")
        console.print("[bold #00E5FF]2.[/bold #00E5FF] REPACK PAK (with Lua injection)")
        console.print("[bold #00E5FF]3.[/bold #00E5FF] EXIT")
        choice = safe_input(
            "[bold #00E5FF]Select an option (1-3):[/bold #00E5FF] "
        ).strip()

        if choice == "1":
            unpack_selected_sdcard_pak()
        elif choice == "2":
            repack_selected_sdcard_pak()
        elif choice == "3":
            console.print("[bold #39FF14]Goodbye.[/bold #39FF14]")
            return
        else:
            console.print("[bold #FF0055]Please select 1, 2, or 3.[/bold #FF0055]")

        safe_input("[bold #00E5FF]Press Enter to return to the menu...[/bold #00E5FF]")
```

The CLI no-argument and `menu` entry points now call this `main_menu()` implementation. The complete integrated source is `pakforge_core.py`.

The repack action intentionally asks for the target path inside the PAK because that path cannot be inferred safely for every project. All filesystem locations remain under `/sdcard/Download/`.
