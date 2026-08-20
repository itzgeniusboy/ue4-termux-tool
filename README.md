# pak-unpacker-termux

A small **Termux command-line utility for authorized Unreal Engine 4 PAK/OBB files**. It supports listing entries, unpacking, repacking, and deleting selected logical entries into a new PAK. The original source PAK is not overwritten unless `--overwrite` is explicitly supplied.

Use this only with files that you own or are authorized to modify. It is not intended to bypass DRM, anti-cheat, access controls, or unknown encryption.

## Install in Termux

Enable Android storage once if needed:

```bash
termux-setup-storage
```

When Termux asks `Do you want to continue? (y/n)`, type only `y` and press Enter. After the prompt finishes, run the bootstrap command separately:

```bash
curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/pak-unpacker-termux/main/bootstrap.sh | bash
```

Then reopen Termux or run:

```bash
export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
hash -r
tool --help
```

The default workspace is:

| Folder | Purpose |
|---|---|
| `~/storage/shared/Paktool/PAK/` | Source PAK files |
| `~/storage/shared/Paktool/UNPACKED/` | Extracted files |
| `~/storage/shared/Paktool/MODDED/` | New repacked/deleted-output PAK files |

## Commands

List files and metadata:

```bash
tool info /sdcard/Download/game.pak
# alias:
tool list /sdcard/Download/game.pak
```

Unpack a PAK:

```bash
tool unpack /sdcard/Download/game.pak /sdcard/Paktool/UNPACKED/game --overwrite
```

Repack an edited folder into a new PAK:

```bash
tool repack \
  /sdcard/Download/game.pak \
  /sdcard/Paktool/EDIT \
  /sdcard/Paktool/MODDED/game-repacked.pak
```

Delete selected entries and create a verified new PAK:

```bash
tool delete \
  /sdcard/Download/game.pak \
  Content/Example.uasset \
  /sdcard/Paktool/MODDED/game-cleaned.pak
```

Multiple entries can be supplied before the output path:

```bash
tool delete game.pak Content/A.uasset Content/B.uexp cleaned.pak
```

A unique basename can be used, but if the same filename exists in multiple folders, provide the full logical path. The delete command verifies that the selected entries are absent from the new PAK.

For an OBB/Tencent variant, add `--is-od` to the relevant command:

```bash
tool info game.pak --is-od
tool unpack game.pak unpacked --is-od
```

## SM4 configuration

The native parser includes the supplied project-specific derivation values:

```text
SM4_SECRET_4
SM4_SECRET_2
SM4_SECRET_NEW[0..14]
```

The values are used internally for supported UE4 encrypted PAK metadata and are not printed by the CLI. Keep the repository private if these keys are not intended for public distribution.

## Troubleshooting

If `tool` is not found after installation, run `hash -r` or restart Termux. If storage access fails, run `termux-setup-storage` and grant the Android permission. If a PAK cannot be parsed, confirm that it is a supported UE4/Tencent PAK and that the correct `--is-od` mode and authorized project keys are being used.
