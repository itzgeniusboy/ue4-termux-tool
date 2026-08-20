#!/data/data/com.termux/files/usr/bin/bash
set -u

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PREFIX
export PATH="$PREFIX/bin:/system/bin:/system/xbin:${PATH:-}"
PKG="$PREFIX/bin/pkg"
PYTHON="$PREFIX/bin/python"
PIP="$PREFIX/bin/python -m pip"
REPO_URL="https://github.com/itzgeniusboy/pak-unpacker-termux.git"
INSTALL_DIR="${PAKTOOL_DIR:-$HOME/pak-unpacker-termux}"
BIN_DIR="$PREFIX/bin"

say() { printf '%s\n' "[pak-unpacker] $*"; }
fail() {
  printf '\n[pak-unpacker] ERROR: %s\n' "$*" >&2
  exit 1
}

[ -x "$PKG" ] || fail "Termux pkg was not found. Run bootstrap.sh from the official Termux app."

say "Installing Python runtime packages..."
"$PKG" install -y python python-pip git || fail "Could not install Python, pip, or git."
[ -x "$PYTHON" ] || fail "Python was not installed correctly."

# Termux owns python-pip. Never replace or upgrade pip itself.
if ! $PIP install --no-cache-dir rich pytz gmalg pycryptodome zstandard; then
  fail "Python dependencies failed. Do not run pip upgrade in Termux; check the mirror with termux-change-repo and rerun the installer."
fi

say "Copying Paktool files..."
if [ ! -d "$INSTALL_DIR/.git" ]; then
  rm -rf "$INSTALL_DIR"
  "$PREFIX/bin/git" clone "$REPO_URL" "$INSTALL_DIR" || fail "Could not download the Paktool files."
else
  "$PREFIX/bin/git" -C "$INSTALL_DIR" fetch origin || true
  "$PREFIX/bin/git" -C "$INSTALL_DIR" reset --hard origin/main || true
fi

cat > "$BIN_DIR/tool" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$PREFIX/bin:/system/bin:/system/xbin:\${PATH:-}"
exec "$PYTHON" "$INSTALL_DIR/paktool.py" "\$@"
EOF
chmod +x "$BIN_DIR/tool" "$INSTALL_DIR/paktool.py"

cp "$INSTALL_DIR/paktool-opencode.sh" "$BIN_DIR/paktool-opencode"
chmod +x "$BIN_DIR/paktool-opencode" "$INSTALL_DIR/paktool-opencode.sh" "$INSTALL_DIR/opencode-setup.sh" "$INSTALL_DIR/paktool_ui.py"
mkdir -p "$HOME/storage/shared/Paktool/PAK" "$HOME/storage/shared/Paktool/EDIT" "$HOME/storage/shared/Paktool/UNPACKED" "$HOME/storage/shared/Paktool/MODDED"

say "Installation complete."
say "Command: $BIN_DIR/paktool-opencode"
say "The OpenCode-style interface will now start automatically when bootstrap.sh is used."
