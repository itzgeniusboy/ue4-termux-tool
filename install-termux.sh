#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
BIN_DIR="$PREFIX_DIR/bin"
CARGO_BIN_DIR="${CARGO_HOME:-$HOME/.cargo}/bin"
REPAK_CARGO_BIN="$CARGO_BIN_DIR/repak"

if [ "${SKIP_PACKAGES:-0}" = "1" ]; then
  printf '%s\n' "[1/5] Required Termux packages already prepared."
else
  printf '%s\n' "[1/5] Preparing Termux packages..."
  pkg update -y
  pkg install -y python python-pip unzip rust
fi

if command -v repak >/dev/null 2>&1; then
  printf '%s\n' "[2/5] repak is already installed."
else
  printf '%s\n' "[2/5] Installing repak from its upstream repository..."
  cargo install --git https://github.com/trumank/repak --locked --bin repak --no-default-features
fi

# Cargo installs executables in ~/.cargo/bin, which is not always present in
# an existing Termux shell PATH. Put a stable shim in $PREFIX/bin so `tool`
# and future Termux sessions can always find the binary.
if [ ! -x "$REPAK_CARGO_BIN" ]; then
  printf '%s\n' "Error: repak was installed but not found at $REPAK_CARGO_BIN." >&2
  exit 1
fi
mkdir -p "$BIN_DIR"
ln -sf "$REPAK_CARGO_BIN" "$BIN_DIR/repak"
export PATH="$BIN_DIR:$CARGO_BIN_DIR:$PATH"

printf '%s\n' "[3/5] Installing PakForge Python dependencies..."
python3 -m pip install --upgrade rich pytz gmalg pycryptodome zstandard

printf '%s\n' "[4/5] Installing tool commands..."
rm -f "$BIN_DIR/ue4tool" "$BIN_DIR/pakforge"
cat > "$BIN_DIR/tool" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$SCRIPT_DIR/ue4tool.py" "\$@"
EOF
cat > "$BIN_DIR/pakforge" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$SCRIPT_DIR/pakforge.py" "\$@"
EOF
chmod 0755 "$BIN_DIR/tool" "$BIN_DIR/pakforge"

printf '%s\n' "[5/5] Verifying installation..."
command -v repak >/dev/null 2>&1 || { printf '%s\n' "Error: repak is not available in PATH." >&2; exit 1; }
command -v "$BIN_DIR/tool" >/dev/null 2>&1 || { printf '%s\n' "Error: tool command was not installed." >&2; exit 1; }
command -v "$BIN_DIR/pakforge" >/dev/null 2>&1 || { printf '%s\n' "Error: pakforge command was not installed." >&2; exit 1; }
printf '%s\n' "Done. Run: pakforge"
