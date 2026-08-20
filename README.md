# pak-unpacker-termux

A simple **Termux command-line utility for authorized Unreal Engine 4 PAK/OBB files**. It supports PAK information/listing, unpacking, repacking, and deleting selected logical entries into a new PAK. The original source PAK is preserved unless `--overwrite` is explicitly supplied.

Use this tool only with files that you own or are authorized to modify. It is not intended to bypass DRM, anti-cheat, access controls, or unknown encryption.

## Complete Termux installation

Run each command separately and wait for the Termux prompt to return before running the next command.

### 1. Enable storage access

```bash
termux-setup-storage
```

When Termux shows:

```text
Do you want to continue? (y/n)
```

Type only `y`, then press Enter. Do not paste the next command into that prompt.

### 2. Install required Termux packages

```bash
pkg update -y
pkg upgrade -y
pkg install -y git python python-pip curl
```

If Termux reports a mirror problem, select a mirror and rerun the package commands:

```bash
termux-change-repo
```

Choose a working **Main repository** mirror, then run:

```bash
pkg update -y
pkg upgrade -y
pkg install -y git python python-pip curl
```

### 3. Install Paktool

```bash
curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/pak-unpacker-termux/main/bootstrap.sh | bash
```

The installer installs the required Python libraries but does **not** upgrade or replace Termux's protected `python-pip` package.

### 4. Activate and test the command

```bash
export PATH="$HOME/.local/bin:$HOME/bin:$PREFIX/bin:$PATH"
hash -r
tool --help
```

If `tool` is still not found, restart Termux and run:

```bash
export PATH="$HOME/.local/bin:$HOME/bin:$PREFIX/bin:$PATH"
hash -r
tool --help
```

You can also test the program directly:

```bash
python "$HOME/pak-unpacker-termux/paktool.py" --help
```

## Storage workspace

The installer creates the following folders:

| Folder | Purpose |
|---|---|
| `~/storage/shared/Paktool/PAK/` | Source PAK files |
| `~/storage/shared/Paktool/EDIT/` | Edited files used for repacking |
| `~/storage/shared/Paktool/UNPACKED/` | Extracted PAK contents |
| `~/storage/shared/Paktool/MODDED/` | New repacked or cleaned PAK files |

Android's `/sdcard/Download/` path is also available as `~/storage/downloads/` after `termux-setup-storage`.

## Test with a real UE4 PAK

A sample file must be a valid UE4/Tencent PAK. Renaming a text file, ZIP file, or random file to `.pak` will not work. Place an authorized sample at `/sdcard/Download/sample.pak` and confirm it exists:

```bash
ls -lh /sdcard/Download/
ls -lh /sdcard/Download/sample.pak
```

### Inspect PAK contents

```bash
tool info /sdcard/Download/sample.pak
```

The command prints the PAK version, parser type, mount point, entry count, logical path, size, compression, and encryption metadata.

For a Tencent/OBB variant, use:

```bash
tool info /sdcard/Download/sample.pak --is-od
```

### Unpack

```bash
mkdir -p /sdcard/Paktool/UNPACKED/sample
tool unpack \
  /sdcard/Download/sample.pak \
  /sdcard/Paktool/UNPACKED/sample \
  --overwrite
```

For an OBB/Tencent variant:

```bash
tool unpack \
  /sdcard/Download/sample.pak \
  /sdcard/Paktool/UNPACKED/sample \
  --overwrite \
  --is-od
```

Check the extracted files:

```bash
find /sdcard/Paktool/UNPACKED/sample -type f | head -50
du -sh /sdcard/Paktool/UNPACKED/sample
```

### Prepare an edited directory

Make a working copy of the extracted directory:

```bash
rm -rf /sdcard/Paktool/EDIT/sample
gcp -r /sdcard/Paktool/UNPACKED/sample /sdcard/Paktool/EDIT/sample
mkdir -p /sdcard/Paktool/MODDED
```

Edit only files that you own or are authorized to modify. The repacker matches edited files by their logical PAK path or filename.

### Repack

```bash
tool repack \
  /sdcard/Download/sample.pak \
  /sdcard/Paktool/EDIT/sample \
  /sdcard/Paktool/MODDED/sample-repacked.pak
```

For an OBB/Tencent variant:

```bash
tool repack \
  /sdcard/Download/sample.pak \
  /sdcard/Paktool/EDIT/sample \
  /sdcard/Paktool/MODDED/sample-repacked.pak \
  --is-od
```

Verify the output:

```bash
ls -lh /sdcard/Paktool/MODDED/sample-repacked.pak
tool info /sdcard/Paktool/MODDED/sample-repacked.pak
sha256sum /sdcard/Download/sample.pak
sha256sum /sdcard/Paktool/MODDED/sample-repacked.pak
```

The hashes normally differ because repacking creates a new PAK. The important checks are that repacking completes and `tool info` can parse the new output.

### Delete selected entries

First find the exact logical path:

```bash
tool info /sdcard/Download/sample.pak
```

Then create a new PAK without the selected entry:

```bash
tool delete \
  /sdcard/Download/sample.pak \
  Content/Example.uasset \
  /sdcard/Paktool/MODDED/sample-cleaned.pak
```

Delete multiple entries in one operation:

```bash
tool delete \
  /sdcard/Download/sample.pak \
  Content/A.uasset \
  Content/B.uexp \
  /sdcard/Paktool/MODDED/sample-cleaned.pak
```

A unique basename can be supplied:

```bash
tool delete \
  /sdcard/Download/sample.pak \
  Example.uasset \
  /sdcard/Paktool/MODDED/sample-cleaned.pak
```

If the same basename exists in multiple folders, use the full logical path. The delete command verifies that selected entries are absent from the output PAK. The original PAK is not overwritten by default.

For an OBB/Tencent variant:

```bash
tool delete \
  /sdcard/Download/sample.pak \
  Content/Example.uasset \
  /sdcard/Paktool/MODDED/sample-cleaned.pak \
  --is-od
```

## SM4 configuration

The native UE4 parser includes the supplied project-specific derivation values under these names:

```text
SM4_SECRET_4
SM4_SECRET_2
SM4_SECRET_NEW[0..14]
```

The values are used internally for supported encrypted PAK metadata and are not printed by the CLI. Keep the repository private if these keys are not intended for public distribution.

## Troubleshooting

If the earlier installer stopped with:

```text
ERROR: Installing pip is forbidden, this will break the python-pip package (termux).
```

Run the corrected bootstrap again. Do not run `pip install --upgrade pip` in Termux:

```bash
curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/pak-unpacker-termux/main/bootstrap.sh | bash
export PATH="$HOME/.local/bin:$HOME/bin:$PREFIX/bin:$PATH"
hash -r
tool --help
```

If `tool` is still unavailable, check the installation directory:

```bash
ls -l "$HOME/pak-unpacker-termux/paktool.py"
python "$HOME/pak-unpacker-termux/paktool.py" --help
```

If storage access fails, run `termux-setup-storage` again and grant the Android permission. If a PAK cannot be parsed, confirm that it is a supported UE4/Tencent PAK, try the correct `--is-od` mode, and use only the authorized project keys configured in the parser.
