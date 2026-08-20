#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="https://github.com/itzgeniusboy/pak-unpacker-termux.git"
INSTALL_DIR="${PAKTOOL_DIR:-$HOME/pak-unpacker-termux}"
BIN_DIR="$PREFIX/bin"

pkg update -y
pkg install -y python python-pip git
# Termux owns the python-pip package; never replace or upgrade pip itself.
python -m pip install --no-cache-dir rich pytz gmalg pycryptodome zstandard

if [ ! -d "$INSTALL_DIR/.git" ]; then
  rm -rf "$INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" reset --hard origin/main
fi

cat > "$BIN_DIR/tool" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python "$INSTALL_DIR/paktool.py" "\$@"
EOF
chmod +x "$BIN_DIR/tool" "$INSTALL_DIR/paktool.py"
cp "$INSTALL_DIR/paktool-opencode.sh" "$BIN_DIR/paktool-opencode"
chmod +x "$BIN_DIR/paktool-opencode" "$INSTALL_DIR/paktool-opencode.sh" "$INSTALL_DIR/opencode-setup.sh" "$INSTALL_DIR/paktool_ui.py"
mkdir -p "$HOME/storage/shared/Paktool/PAK" "$HOME/storage/shared/Paktool/EDIT" "$HOME/storage/shared/Paktool/UNPACKED" "$HOME/storage/shared/Paktool/MODDED"

echo "Installed successfully. Try: tool --help"
echo "OpenCode launcher: paktool-opencode"
echo "PAK workspace: $HOME/storage/shared/Paktool/"
