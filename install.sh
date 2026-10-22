#!/usr/bin/env sh
set -eu

REPO_ZIP="https://github.com/gefrus112/pythonv2/archive/refs/heads/main.zip"
INSTALL_DIR="${PYTHONV2_HOME:-$HOME/.local/share/pythonv2}"
TMP_DIR="${TMPDIR:-/tmp}/pythonv2-install-$$"
ZIP_FILE="$TMP_DIR/pythonv2.zip"

printf '\n\033[1;34mPython v2 0.3 + PyHope installer\033[0m\n'
printf 'No pygame. No native libraries. Python 3.10+ only.\n\n'

command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 was not found. Install Python 3.10+ first." >&2
  exit 1
}

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("ERROR: Python 3.10+ is required; found " + sys.version.split()[0])
print("[1/4] Found Python", sys.version.split()[0])
PY

mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM

echo "[2/4] Downloading Python v2 from GitHub..."
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$REPO_ZIP" -o "$ZIP_FILE"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$REPO_ZIP" -O "$ZIP_FILE"
else
  echo "ERROR: curl or wget is required to download the release." >&2
  exit 1
fi

python3 - "$ZIP_FILE" "$TMP_DIR" <<'PY'
import pathlib, sys, zipfile
zip_path, target = map(pathlib.Path, sys.argv[1:])
with zipfile.ZipFile(zip_path) as archive:
    archive.extractall(target)
PY

rm -rf "$INSTALL_DIR"
mkdir -p "$(dirname "$INSTALL_DIR")"
mv "$TMP_DIR/pythonv2-main" "$INSTALL_DIR"

echo "[3/4] Installing pyv2 and PyHope for this user..."
python3 -m pip install --user --upgrade "$INSTALL_DIR"

echo "[4/4] Running engine checks..."
python3 -m pyv2 --version
python3 -m pyhope --check

printf '\n\033[1;32mSUCCESS! Python v2 + PyHope are installed.\033[0m\n'
printf 'Try: pyv2 | pyhope --demo\n'
printf 'If pyv2 is not on PATH, use: python3 -m pyv2\n'
printf 'Install folder: %s\n\n' "$INSTALL_DIR"
