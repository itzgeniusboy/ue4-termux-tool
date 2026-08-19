#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PREFIX_DIR="$TMP/prefix"
CARGO_HOME_DIR="$TMP/cargo"
FAKE_BIN="$TMP/fake-bin"
mkdir -p "$PREFIX_DIR/bin" "$CARGO_HOME_DIR/bin" "$FAKE_BIN"
printf '#!/usr/bin/env bash\nexit 0\n' > "$CARGO_HOME_DIR/bin/repak"
chmod 0755 "$CARGO_HOME_DIR/bin/repak"
printf '#!/usr/bin/env bash\nexit 0\n' > "$FAKE_BIN/python3"
chmod 0755 "$FAKE_BIN/python3"
PATH="$FAKE_BIN:$CARGO_HOME_DIR/bin:$PATH" PREFIX="$PREFIX_DIR" CARGO_HOME="$CARGO_HOME_DIR" SKIP_PACKAGES=1 bash "$ROOT/install-termux.sh"
REAL_PATH="/usr/local/bin:/usr/bin:/bin"
PAKFORGE_NO_UPDATE=1 PATH="$PREFIX_DIR/bin:$REAL_PATH" bash "$PREFIX_DIR/bin/pakforge" --version | grep -Fx 'PakForge 1.3.2'
command -v "$PREFIX_DIR/bin/tool" >/dev/null
printf '%s\n' 'launcher-tests-ok'
