#!/usr/bin/env bash
# Package the browser extension into a zip for Chrome/Edge store submission or
# manual "Load unpacked" distribution.
#
# Usage: scripts/package-extension.sh
# Output: dist/apartment-fit-extension.zip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/extension"
OUT_DIR="$ROOT/dist"
OUT="$OUT_DIR/apartment-fit-extension.zip"

mkdir -p "$OUT_DIR"
rm -f "$OUT"

cd "$SRC"
# Ship only runtime files; exclude tests and docs.
zip -r "$OUT" . \
  -x "*.test.cjs" -x "README.md" >/dev/null

echo ">> Packaged extension -> $OUT"
echo "   Load unpacked from ./extension, or upload the zip to the Chrome/Edge dashboard."
