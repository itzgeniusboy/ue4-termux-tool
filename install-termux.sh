#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
BIN_DIR="$PREFIX_DIR/bin"

if [ "${SKIP_PACKAGES:-0}" = "1" ]; then
  printf '%s\n' "[1/4] Required Termux packages already prepared."
else
  printf '%s\n' "[1/4] Preparing Termux packages..."
  pkg update -y
  pkg install -y python unzip rust
fi

if command -v repak >/dev/null 2>&1; then
  printf '%s\n' "[2/4] repak is already installed."
else
  printf '%s\n' "[2/4] Installing repak from its upstream repository..."
  cargo install --git https://github.com/trumank/repak --locked --bin repak --no-default-features
fi

printf '%s\n' "[3/4] Installing tool command..."
mkdir -p "$BIN_DIR"
rm -f "$BIN_DIR/ue4tool"
cat > "$BIN_DIR/tool" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$SCRIPT_DIR/ue4tool.py" "\$@"
EOF
chmod 0755 "$BIN_DIR/tool"

printf '%s\n' "[4/4] Verifying installation..."
command -v repak >/dev/null 2>&1 || { printf '%s\n' "Error: repak is not available in PATH." >&2; exit 1; }
command -v "$BIN_DIR/tool" >/dev/null 2>&1 || { printf '%s\n' "Error: tool command was not installed." >&2; exit 1; }
printf '%s\n' "Done. Run: tool"
