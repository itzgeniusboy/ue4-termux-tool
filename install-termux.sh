#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
BIN_DIR="$PREFIX_DIR/bin"

printf '%s\n' "[1/4] Updating Termux packages..."
pkg update -y
printf '%s\n' "[2/4] Installing Python, unzip, and Rust..."
pkg install -y python unzip rust

printf '%s\n' "[3/4] Installing repak from its upstream repository..."
# repak_cli exposes the executable named `repak`.
cargo install --git https://github.com/trumank/repak --locked --bin repak --no-default-features

printf '%s\n' "[4/4] Installing ue4tool command..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/ue4tool" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$SCRIPT_DIR/ue4tool.py" "\$@"
EOF
chmod 0755 "$BIN_DIR/ue4tool"

printf '%s\n' "Done. If Termux cannot read /sdcard, run: termux-setup-storage"
printf '%s\n' "Try: ue4tool --help"
printf '%s\n' "If repak is not found, ensure $PREFIX_DIR/bin is in PATH."
