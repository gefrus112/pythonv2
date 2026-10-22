#!/usr/bin/env sh
set -eu

REPO_ZIP="https://github.com/gefrus112/pythonv2/archive/refs/heads/main.zip"
INSTALL_DIR="${PYTHONV2_HOME:-$HOME/.local/share/pythonv2}"
TMP_DIR="${TMPDIR:-/tmp}/pythonv2-install-$$"
ZIP_FILE="$TMP_DIR/pythonv2.zip"

printf '\n\033[1;34mPython v2 1.1 Sudbury + PyHope installer\033[0m\n'
printf 'Language + desktop Launcher + game engine. No pygame or Electron.\n\n'

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

echo "[4/4] Running checks and creating the Python v2 app..."
python3 -m pyv2 --version
python3 -m pyv2 doctor
python3 -m pyhope --check
python3 -c "from pyv2.launcher import safe_name; assert safe_name('Python v2') == 'Python-v2'"

case "$(uname -s)" in
  Darwin)
    APP_DIR="$HOME/Applications/Python v2 Sudbury.app"
    mkdir -p "$APP_DIR/Contents/MacOS"
    cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Python v2 Sudbury</string>
<key>CFBundleDisplayName</key><string>Python v2 Sudbury</string>
<key>CFBundleIdentifier</key><string>dev.pythonv2.launcher</string>
<key>CFBundleVersion</key><string>1.1.0</string>
<key>CFBundleShortVersionString</key><string>1.1</string>
<key>CFBundleExecutable</key><string>python-v2</string>
</dict></plist>
PLIST
    cat > "$APP_DIR/Contents/MacOS/python-v2" <<EOF
#!/bin/sh
exec "$(command -v python3)" -m pyv2.launcher
EOF
    chmod +x "$APP_DIR/Contents/MacOS/python-v2"
    printf 'Created app: %s\n' "$APP_DIR"
    ;;
  Linux)
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/python-v2-sudbury.desktop" <<EOF
[Desktop Entry]
Name=Python v2 Sudbury
Comment=Python v2 1.1 app launcher and PyHope game tools
Exec=$(command -v python3) -m pyv2.launcher
Terminal=false
Type=Application
Categories=Development;IDE;
EOF
    chmod +x "$DESKTOP_DIR/python-v2-sudbury.desktop"
    printf 'Created app menu entry: %s\n' "$DESKTOP_DIR/python-v2-sudbury.desktop"
    ;;
esac

printf '\n\033[1;32mSUCCESS! Python v2 1.1 + Launcher + PyHope are installed.\033[0m\n'
printf 'Open the app, or run: python3 -m pyv2.launcher\n'
printf 'CLI tools: pyv2 | pyhope --demo\n'
printf 'Install folder: %s\n\n' "$INSTALL_DIR"
