#!/usr/bin/env python3
"""OpenCode-style interactive launcher for the Termux UE4 PAK tool."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAKTOOL = ROOT / "paktool.py"
SETUP_LOG = Path(os.environ.get("PAKTOOL_SETUP_LOG", Path.home() / ".cache/pak-unpacker-termux/setup.log"))

RESET = "\033[0m"
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"


def clear() -> None:
    if os.environ.get("TERM", "") != "dumb":
        print("\033[2J\033[H", end="")


def run_tool(arguments: list[str]) -> None:
    command = [sys.executable, str(PAKTOOL), *arguments]
    print(f"\n{DIM}$ tool {' '.join(arguments)}{RESET}\n")
    result = subprocess.run(command)
    print()
    if result.returncode != 0:
        print(f"{RED}Command failed with exit code {result.returncode}.{RESET}")
    input("Press Enter to return to the menu...")


def ask_path(prompt: str) -> str:
    return input(f"{CYAN}{prompt}{RESET} ").strip()


def ask_mode() -> list[str]:
    answer = input(f"{CYAN}Tencent/OBB mode? [y/N]{RESET} ").strip().lower()
    return ["--is-od"] if answer in {"y", "yes"} else []


def open_auth() -> None:
    url = "https://opencode.ai/auth"
    print(f"\n{BLUE}OpenCode authentication{RESET}")
    print("1. Browser mein ye link open karein:")
    print(f"   {url}")
    if shutil.which("termux-open-url"):
        answer = input(f"\n{CYAN}Link browser mein open karna hai? [Y/n]{RESET} ").strip().lower()
        if answer not in {"n", "no"}:
            subprocess.Popen(["termux-open-url", url])
            print(f"{GREEN}Browser open kar diya gaya.{RESET}")
    print("\n2. Auth complete karke OpenCode mein provider/API key configure karein.")
    print("3. Actual OpenCode TUI mein `/connect` type karein, provider select karein, aur key paste karein.")
    print(f"\n{DIM}API key is launcher mein read ya log nahi hoti; OpenCode apni local auth file use karta hai.{RESET}")
    input("\nPress Enter to return to the menu...")


def launch_opencode() -> None:
    opencode = shutil.which("opencode")
    if not opencode:
        print(f"{YELLOW}Actual OpenCode command abhi install nahi hai.{RESET}")
        print("Menu se 'OpenCode setup status' check karein ya launcher dobara run karein.")
        input("Press Enter to return to the menu...")
        return
    print(f"{DIM}Starting actual OpenCode. TUI mein /connect type karke provider/API key set karein.{RESET}\n")
    result = subprocess.run([opencode])
    if result.returncode != 0:
        print(f"{YELLOW}Native OpenCode is device par run nahi ho saka. PAK UI available rahegi.{RESET}")
        input("Press Enter to return to the menu...")


def show_status() -> None:
    opencode = shutil.which("opencode")
    if opencode:
        try:
            result = subprocess.run([opencode, "--version"], capture_output=True, text=True, timeout=8)
            if result.returncode == 0:
                native = f"{GREEN}available ({result.stdout.strip() or 'version unknown'}){RESET}"
            else:
                native = f"{YELLOW}installed but runtime check failed{RESET}"
        except Exception:
            native = f"{YELLOW}installed but runtime check failed{RESET}"
    else:
        native = f"{DIM}not installed; built-in PAK UI is available{RESET}"
    setup = f"{GREEN}log: {SETUP_LOG}{RESET}" if SETUP_LOG.exists() else f"{DIM}setup log not created{RESET}"
    print(f"{DIM}OpenCode: {native} | Background setup: {setup}{RESET}")


def menu() -> None:
    if os.environ.get("PAKTOOL_AUTO_AUTH") == "1":
        open_auth()
    while True:
        clear()
        print(f"{CYAN}╭──────────────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│  {BLUE}OpenCode{RESET}  {GREEN}PAK-UNPACKER-TERMUX{CYAN}                 │{RESET}")
        print(f"{CYAN}│  UE4 PAK / OBB assistant                     │{RESET}")
        print(f"{CYAN}╰──────────────────────────────────────────────╯{RESET}\n")
        show_status()
        print("\n  1  Inspect / list PAK")
        print("  2  Unpack PAK")
        print("  3  Repack edited folder")
        print("  4  Delete entries and create a new PAK")
        print("  5  Open OpenCode auth link")
        print("  6  Launch actual OpenCode TUI")
        print("  0  Exit")
        choice = input(f"\n{CYAN}Select action ›{RESET} ").strip()

        if choice == "0":
            return
        if choice == "1":
            run_tool(["info", ask_path("PAK path:") , *ask_mode()])
        elif choice == "2":
            pak = ask_path("Source PAK path:")
            output = ask_path("Output folder [optional]:")
            args = ["unpack", pak] + ([output] if output else []) + ["--overwrite", *ask_mode()]
            run_tool(args)
        elif choice == "3":
            source = ask_path("Original PAK path:")
            edited = ask_path("Edited folder path:")
            output = ask_path("New output PAK path:")
            run_tool(["repack", source, edited, output, *ask_mode()])
        elif choice == "4":
            source = ask_path("Original PAK path:")
            paths = ask_path("Logical PAK paths to delete (comma separated):")
            output = ask_path("New cleaned PAK path:")
            selected = [item.strip() for item in paths.split(",") if item.strip()]
            if not selected:
                print(f"{RED}At least one PAK path is required.{RESET}")
                input("Press Enter to continue...")
            else:
                run_tool(["delete", source, *selected, output, *ask_mode()])
        elif choice == "5":
            open_auth()
        elif choice == "6":
            launch_opencode()
        else:
            print(f"{YELLOW}Unknown selection.{RESET}")
            input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nCancelled.")
