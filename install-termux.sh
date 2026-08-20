#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="https://github.com/itzgeniusboy/pak-unpacker-termux.git"
INSTALL_DIR="${PAKTOOL_DIR:-$HOME/pak-unpacker-termux}"
BIN_DIR="$PREFIX/bin"

pkg update -y
pkg install -y python python-pip git
python -m pip install --upgrade pip
python -m pip install rich pytz gmalg pycryptodome zstandard

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
mkdir -p "$HOME/storage/shared/Paktool/PAK" "$HOME/storage/shared/Paktool/UNPACKED" "$HOME/storage/shared/Paktool/MODDED"

echo "Installed successfully. Try: tool --help"
echo "PAK workspace: $HOME/storage/shared/Paktool/"
