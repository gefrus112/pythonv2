"""Safe Windows executable project and build tooling for Python v2.

PyInstaller cannot cross-compile a Windows PE executable from macOS or Linux.
This module therefore has two honest stages:

* every platform can validate an app and create a reproducible Windows build kit;
* Windows can turn that kit into a real one-file ``.exe`` with ``--native``.

Generated projects also include a GitHub Actions Windows workflow, so developers
on any operating system can produce the executable on a Windows runner.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from .parser import ParseError, parse


CONFIG_NAME = "pyv2app.json"
KIT_MARKER = ".pyv2-windows-build-kit"
MAX_ASSET_BYTES = 100 * 1024 * 1024
SOURCE_REPOSITORY = "https://github.com/gefrus112/pythonv2.git@main"


class BuildError(ValueError):
    """A clear configuration, validation, or native-build failure."""


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    entry: Path
    name: str
    executable_name: str
    app_id: str
    version: str
    description: str
    publisher: str
    console: bool
    icon: Path | None
    assets: tuple[Path, ...]


@dataclass(frozen=True)
class BuildResult:
    config: AppConfig
    kit_dir: Path
    manifest: Path
    executable: Path | None = None


def executable_name(name: str) -> str:
    """Return a Windows-safe executable stem."""
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", " ".join(str(name).split()))
    cleaned = re.sub(r"[ .]+", "-", cleaned).strip("-._")
    if cleaned.upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        cleaned = "app-" + cleaned.lower()
    return (cleaned or "python-v2-app")[:64]


def application_id(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (value or "python-v2-app")[:80]


def _inside(root: Path, raw: str | Path, label: str, *, must_exist: bool = True) -> Path:
    requested = Path(raw)
    if requested.is_absolute():
        raise BuildError(f"{label} must be a relative path inside the project")
    target = (root / requested).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise BuildError(f"{label} escapes the project directory") from exc
    if must_exist and not target.exists():
        raise BuildError(f"{label} does not exist: {raw}")
    return target


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BuildError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BuildError(f"invalid {CONFIG_NAME} at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"{CONFIG_NAME} must contain a JSON object")
    return value


def load_app_config(
    target: str | Path,
    *,
    name: str | None = None,
    icon: str | Path | None = None,
    console: bool | None = None,
) -> AppConfig:
    """Load and strictly validate a source file or app project."""
    requested = Path(target).expanduser().resolve()
    if requested.is_dir():
        root = requested
        config_path = root / CONFIG_NAME
        raw = _read_json(config_path) if config_path.is_file() else {}
        entry_name = raw.get("entry", "main.pyv2")
    elif requested.is_file():
        root = requested.parent
        config_path = root / CONFIG_NAME
        raw = _read_json(config_path) if config_path.is_file() else {}
        entry_name = requested.name
    else:
        raise BuildError(f"app source or project not found: {target}")

    allowed_fields = {"name", "id", "entry", "version", "description", "publisher",
                      "console", "icon", "assets"}
    unknown = sorted(set(raw) - allowed_fields)
    if unknown:
        raise BuildError(f"unknown {CONFIG_NAME} field(s): {', '.join(unknown)}")

    if not isinstance(entry_name, str) or not entry_name.strip():
        raise BuildError("entry must be a non-empty relative path")
    entry = _inside(root, entry_name, "entry")
    if not entry.is_file() or entry.suffix.lower() != ".pyv2":
        raise BuildError("entry must be an existing .pyv2 file")

    app_name = name if name is not None else raw.get("name", entry.stem.replace("_", " ").title())
    if not isinstance(app_name, str) or not app_name.strip():
        raise BuildError("name must be a non-empty string")
    app_name = " ".join(app_name.split())
    if len(app_name) > 80:
        raise BuildError("name must be 80 characters or fewer")

    version = raw.get("version", "1.0.0")
    if not isinstance(version, str) or not re.fullmatch(r"\d{1,5}(?:\.\d{1,5}){0,3}", version):
        raise BuildError("version must contain one to four numeric parts, such as 1.0.0")
    description = raw.get("description", f"A Windows app built with Python v2")
    publisher = raw.get("publisher", "Python v2 developer")
    if not isinstance(description, str) or len(description) > 240:
        raise BuildError("description must be a string of 240 characters or fewer")
    if not isinstance(publisher, str) or len(publisher) > 120:
        raise BuildError("publisher must be a string of 120 characters or fewer")

    config_console = raw.get("console", True) if console is None else console
    if not isinstance(config_console, bool):
        raise BuildError("console must be true or false")

    icon_name = icon if icon is not None else raw.get("icon")
    icon_path = None
    if icon_name:
        if not isinstance(icon_name, (str, Path)):
            raise BuildError("icon must be a relative .ico path")
        icon_path = _inside(root, icon_name, "icon")
        if not icon_path.is_file() or icon_path.suffix.lower() != ".ico":
            raise BuildError("Windows app icons must be existing .ico files")

    raw_assets = raw.get("assets", ["assets"] if (root / "assets").is_dir() else [])
    if not isinstance(raw_assets, list) or not all(isinstance(item, str) for item in raw_assets):
        raise BuildError("assets must be a list of relative file or directory paths")
    assets: list[Path] = []
    total_size = 0
    for item in raw_assets:
        asset = _inside(root, item, "asset")
        entries = [asset] if asset.is_file() else list(asset.rglob("*"))
        if any(path.is_symlink() for path in entries):
            raise BuildError(f"asset trees cannot contain symbolic links: {item}")
        files = [path for path in entries if path.is_file()]
        for path in files:
            try:
                path.resolve().relative_to(root)
            except ValueError as exc:
                raise BuildError(f"asset escapes the project directory: {path}") from exc
        total_size += sum(path.stat().st_size for path in files)
        if total_size > MAX_ASSET_BYTES:
            raise BuildError("assets exceed the 100 MB build safety limit")
        assets.append(asset)

    raw_id = raw.get("id", app_name)
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise BuildError("id must be a non-empty string")

    source = entry.read_text(encoding="utf-8")
    try:
        parse(source)
    except ParseError as exc:
        raise BuildError(f"SyntaxError in {entry.name} at line {exc.line}: {exc.message}") from exc

    return AppConfig(
        project_root=root,
        entry=entry,
        name=app_name,
        executable_name=executable_name(app_name),
        app_id=application_id(raw_id),
        version=version,
        description=description,
        publisher=publisher,
        console=config_console,
        icon=icon_path,
        assets=tuple(assets),
    )


def check_app(target: str | Path) -> AppConfig:
    """Validate syntax, metadata, paths, icon, and bundled asset limits."""
    return load_app_config(target)


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    values = [int(part) for part in version.split(".")]
    return tuple((values + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def _launcher_source(config: AppConfig, source: str) -> str:
    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    metadata = {
        "name": config.name,
        "version": config.version,
        "id": config.app_id,
        "console": config.console,
    }
    return f'''# Generated by Python v2 Sudbury Build Tools. Do not edit by hand.
from __future__ import annotations
import base64
import os
from pathlib import Path
import sys

from pyv2.interpreter import Interpreter, Pyv2Error
from pyv2.parser import ParseError
from pyv2.runtime import AppRuntime

APP = {metadata!r}
SOURCE = base64.b64decode({encoded!r}).decode("utf-8")


def _asset_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets"


def _data_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    return base / "PythonV2Apps" / APP["id"]


def _message(title: str, text: str) -> None:
    from tkinter import messagebox
    messagebox.showinfo(title, text)


def _ask(title: str, prompt: str, default: str) -> str | None:
    from tkinter import simpledialog
    return simpledialog.askstring(title, prompt, initialvalue=default)


def main() -> int:
    output = []
    runtime = AppRuntime(
        app_name=APP["name"], app_version=APP["version"], app_id=APP["id"],
        data_root=_data_root(), asset_root=_asset_root() if _asset_root().is_dir() else None,
        argv=sys.argv[1:], message_handler=_message, ask_handler=_ask,
    )
    writer = print if APP["console"] else output.append
    reader = input if APP["console"] else (lambda prompt="": _ask(APP["name"], prompt, "") or "")
    try:
        Interpreter(output=writer, read_input=reader, app_runtime=runtime).run(SOURCE)
    except ParseError as exc:
        message = f"SyntaxError: {{exc.message}} at line {{exc.line}}"
    except Pyv2Error as exc:
        message = exc.format()
    except Exception as exc:
        message = f"HostError: {{exc}}"
    else:
        if output:
            _message(APP["name"], "\\n".join(output))
        return 0
    if APP["console"]:
        print(message, file=sys.stderr)
    else:
        from tkinter import messagebox
        messagebox.showerror(APP["name"], message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _version_file(config: AppConfig) -> str:
    version = _version_tuple(config.version)
    version_text = ", ".join(str(value) for value in version)
    dotted = ".".join(str(value) for value in version)
    # Values use repr and validated bounded strings, avoiding executable code injection.
    return f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers=({version_text}), prodvers=({version_text}), mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', {config.publisher!r}),
    StringStruct('FileDescription', {config.description!r}),
    StringStruct('FileVersion', {dotted!r}),
    StringStruct('InternalName', {config.executable_name!r}),
    StringStruct('OriginalFilename', {config.executable_name + '.exe'!r}),
    StringStruct('ProductName', {config.name!r}),
    StringStruct('ProductVersion', {dotted!r})
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
'''


def _spec_file(config: AppConfig, has_assets: bool, has_icon: bool) -> str:
    console = "True" if config.console else "False"
    icon = repr("app.ico") if has_icon else "None"
    asset_code = "datas = [('assets', 'assets')]" if has_assets else "datas = []"
    return f'''# Reproducible PyInstaller recipe generated by Python v2.
{asset_code}
a = Analysis(['launcher.py'], pathex=['runtime'], binaries=[], datas=datas,
             hiddenimports=[], hookspath=[], hooksconfig={{}},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name={config.executable_name!r},
          debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
          console={console}, icon={icon}, version='version_info.txt')
'''


def _batch_file(config: AppConfig) -> str:
    return f'''@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Build {config.executable_name}
echo [1/4] Checking Python...
where py >nul 2>nul || (echo Python 3.10+ is required.& exit /b 1)
if not exist ".builder\\Scripts\\python.exe" py -3 -m venv .builder
call ".builder\\Scripts\\activate.bat"
echo [2/4] Installing PyInstaller in the local build environment...
python -m pip install --upgrade pip pyinstaller
if errorlevel 1 exit /b 1
echo [3/4] Validating source with the bundled Python v2 runtime...
set "PYTHONPATH=%CD%\\runtime"
python -c "from pathlib import Path; from pyv2.parser import parse; parse(Path('source.pyv2').read_text(encoding='utf-8'))"
if errorlevel 1 exit /b 1
echo [4/4] Creating the Windows executable...
python -m PyInstaller --clean --noconfirm --distpath dist --workpath .work app.spec
if errorlevel 1 exit /b 1
echo.
echo SUCCESS: %CD%\\dist\\{config.executable_name}.exe
exit /b 0
'''


def _powershell_file(config: AppConfig) -> str:
    return f'''$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".builder\\Scripts\\python.exe")) {{ py -3 -m venv .builder }}
& ".builder\\Scripts\\python.exe" -m pip install --upgrade pip pyinstaller
$env:PYTHONPATH = Join-Path $PSScriptRoot "runtime"
& ".builder\\Scripts\\python.exe" -c "from pathlib import Path; from pyv2.parser import parse; parse(Path('source.pyv2').read_text(encoding='utf-8'))"
& ".builder\\Scripts\\python.exe" -m PyInstaller --clean --noconfirm --distpath dist --workpath .work app.spec
Write-Host "Built $PSScriptRoot\\dist\\{config.executable_name}.exe" -ForegroundColor Green
'''


def _building_guide(config: AppConfig) -> str:
    mode = "console" if config.console else "windowed"
    return f'''# Build {config.name} for Windows

This is a readable, reproducible Python v2 Windows build kit. The app source is
`source.pyv2`; `launcher.py` embeds that exact source; `app.spec` creates a
single-file **{mode}** executable named `{config.executable_name}.exe`.

## On Windows

1. Install Python 3.10 or newer from python.org and select **Add Python to PATH**.
2. Double-click `build.bat` (or run `powershell -File build.ps1`).
3. Find the executable in `dist\\{config.executable_name}.exe`.

The first build installs only PyInstaller into the local `.builder` virtual
environment. The exact Python v2 runtime used to make this kit is vendored under
`runtime/` and covered by `manifest.json`. No administrator access is required.
Review the two build scripts before running them; no mystery launcher is included.

## Data safety

The packaged app can only use Python v2 file functions inside
`%LOCALAPPDATA%\\PythonV2Apps\\{config.app_id}`. Bundled `assets/` are read-only.
Absolute paths, traversal, and symlink escapes are rejected by the runtime.

## Building from macOS or Linux

PyInstaller does not cross-compile Windows PE files. Commit the generated app
project and use its Windows GitHub Actions workflow, or copy this kit to a
Windows machine. This limitation is reported rather than pretending a non-Windows
file is an `.exe`.
'''


def _copy_runtime(destination: Path) -> None:
    """Vendor the exact pure-Python runtime used to prepare this kit."""
    source = Path(__file__).resolve().parent
    target = destination / "runtime" / "pyv2"
    target.mkdir(parents=True, exist_ok=True)
    for module in sorted(source.glob("*.py")):
        shutil.copy2(module, target / module.name)


def _copy_assets(config: AppConfig, destination: Path) -> bool:
    if not config.assets:
        return False
    root = destination / "assets"
    root.mkdir(parents=True, exist_ok=True)
    for asset in config.assets:
        relative = asset.relative_to(config.project_root)
        # A configured top-level assets directory maps to the executable's
        # assets root rather than producing assets/assets.
        if relative.as_posix() == "assets":
            target = root
        elif relative.parts and relative.parts[0] == "assets":
            target = root.joinpath(*relative.parts[1:])
        else:
            target = root / relative
        if asset.is_dir():
            shutil.copytree(asset, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, target)
    return True


def _hash_manifest(directory: Path, config: AppConfig) -> Path:
    files: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", KIT_MARKER}:
            files[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "format": 1,
        "builder": "Python v2 Sudbury Build Tools",
        "app": {"name": config.name, "id": config.app_id, "version": config.version,
                "executable": config.executable_name + ".exe", "console": config.console},
        "source_sha256": hashlib.sha256(config.entry.read_bytes()).hexdigest(),
        "files": files,
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def prepare_windows_build(
    target: str | Path,
    output: str | Path | None = None,
    *,
    name: str | None = None,
    icon: str | Path | None = None,
    console: bool | None = None,
) -> BuildResult:
    """Validate an app and create a Windows build kit on any platform."""
    config = load_app_config(target, name=name, icon=icon, console=console)
    kit = (Path(output).expanduser() if output else
           config.project_root / "build" / "windows").resolve()
    if kit.exists() and any(kit.iterdir()):
        if not (kit / KIT_MARKER).is_file():
            raise BuildError(f"refusing to replace non-build directory: {kit}")
        for child in kit.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    kit.mkdir(parents=True, exist_ok=True)
    (kit / KIT_MARKER).write_text("Python v2 Windows build kit\n", encoding="utf-8")

    source = config.entry.read_text(encoding="utf-8")
    (kit / "source.pyv2").write_text(source, encoding="utf-8")
    (kit / "launcher.py").write_text(_launcher_source(config, source), encoding="utf-8")
    _copy_runtime(kit)
    has_assets = _copy_assets(config, kit)
    has_icon = config.icon is not None
    if config.icon:
        shutil.copy2(config.icon, kit / "app.ico")
    (kit / "version_info.txt").write_text(_version_file(config), encoding="utf-8")
    (kit / "app.spec").write_text(_spec_file(config, has_assets, has_icon), encoding="utf-8")
    (kit / "build.bat").write_text(_batch_file(config), encoding="utf-8", newline="\r\n")
    (kit / "build.ps1").write_text(_powershell_file(config), encoding="utf-8")
    (kit / "BUILDING.md").write_text(_building_guide(config), encoding="utf-8")
    config_copy = {
        "name": config.name, "id": config.app_id, "entry": "source.pyv2",
        "version": config.version, "description": config.description,
        "publisher": config.publisher, "console": config.console,
        "assets": ["assets"] if has_assets else [],
    }
    (kit / CONFIG_NAME).write_text(json.dumps(config_copy, indent=2) + "\n", encoding="utf-8")
    manifest = _hash_manifest(kit, config)
    return BuildResult(config=config, kit_dir=kit, manifest=manifest)


def build_native_windows(result: BuildResult, *, python: str | None = None) -> BuildResult:
    """Build the kit as a real Windows executable using local PyInstaller."""
    if os.name != "nt":
        raise BuildError(
            "native Windows .exe builds require Windows; use the generated build.bat "
            "or GitHub Actions workflow from macOS/Linux"
        )
    if importlib.util.find_spec("PyInstaller") is None:
        raise BuildError(
            "PyInstaller is not installed; run 'py -m pip install pyinstaller' "
            "or double-click the generated build.bat"
        )
    executable = python or sys.executable
    command = [
        executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        "--distpath", "dist", "--workpath", ".work", "app.spec",
    ]
    completed = subprocess.run(command, cwd=result.kit_dir, text=True, capture_output=True)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise BuildError(f"PyInstaller failed ({completed.returncode}): {detail[-2000:]}")
    exe = result.kit_dir / "dist" / f"{result.config.executable_name}.exe"
    if not exe.is_file():
        raise BuildError(f"PyInstaller finished but did not create {exe}")
    return BuildResult(result.config, result.kit_dir, result.manifest, exe)


def _starter_source(name: str, windowed: bool) -> str:
    safe_name = name.replace("\\", "\\\\").replace('"', '\\"')
    if windowed:
        return f'''# {safe_name} — a windowed Python v2 app
info = app_info()
user = ui_ask(info.name, "What is your name?", "Developer")
if user != nil:
    visits = 1
    if file_exists("visits.json"):
        saved = json_decode(read_text("visits.json"))
        visits = saved.visits + 1
    end
    write_text("visits.json", json_encode({{visits: visits}}))
    ui_message("Welcome", f"Hello, {{user}}! This is visit {{visits}}.")
end
'''
    return f'''# {safe_name} — a production-ready Python v2 console app
info = app_info()
commands = args()
tasks = []
if file_exists("tasks.json"):
    tasks = json_decode(read_text("tasks.json"))
end

if len(commands) >= 2 and commands[0] == "--add":
    tasks.push({{title: commands[1], done: false}})
    write_text("tasks.json", json_encode(tasks))
    print("Added:", commands[1])
elif len(commands) >= 1 and commands[0] == "--list":
    if len(tasks) == 0:
        print("No tasks yet.")
    end
    for task in tasks:
        print(task.done ? "[x]" : "[ ]", task.title)
    end
else:
    print(info.name, "v" + info.version)
    print("Usage:")
    print(" ", info.id + ".exe --add task-name")
    print(" ", info.id + ".exe --list")
end
'''


def _project_readme(name: str, windowed: bool) -> str:
    mode = "windowed" if windowed else "console"
    return f'''# {name}

A {mode} Windows application powered by Python v2.

## Develop

```console
pyv2 check main.pyv2
pyv2 main.pyv2 --list
```

Relative file functions are sandboxed under `.pyv2-data` while developing and
under `%LOCALAPPDATA%\\PythonV2Apps` in the packaged application.

## Build a real Windows EXE

On Windows, run `build-windows.bat`. On any platform, run `pyv2 build .` to
create an inspectable build kit. The included GitHub Actions workflow can build
the `.exe` on a Windows runner when you push this project to GitHub.
'''


WINDOWS_WORKFLOW = f'''name: Build Windows EXE
on:
  workflow_dispatch:
  push:
    tags: ["v*"]
permissions:
  contents: read
jobs:
  windows-exe:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Python v2 and PyInstaller
        run: python -m pip install pyinstaller "git+{SOURCE_REPOSITORY}"
      - name: Validate app
        run: pyv2 check .
      - name: Build integrity-tracked executable
        run: pyv2 build . --native --output build/windows
      - uses: actions/upload-artifact@v4
        with:
          name: windows-executable
          path: build/windows/dist/*.exe
          if-no-files-found: error
'''


def create_windows_project(
    parent: str | Path,
    name: str,
    *,
    windowed: bool = False,
) -> Path:
    """Create a complete Windows app project without overwriting existing files."""
    app_name = " ".join(name.strip().split()) or "My Python v2 App"
    project = Path(parent).expanduser().resolve() / executable_name(app_name)
    project.mkdir(parents=True, exist_ok=True)
    files = {
        "main.pyv2": _starter_source(app_name, windowed),
        CONFIG_NAME: json.dumps({
            "name": app_name,
            "id": application_id(app_name),
            "entry": "main.pyv2",
            "version": "1.0.0",
            "description": f"{app_name}, built with Python v2",
            "publisher": "Your name",
            "console": not windowed,
            "assets": ["assets"],
        }, indent=2) + "\n",
        "README.md": _project_readme(app_name, windowed),
        "assets/README.md": "Place bundled read-only app assets in this folder.\n",
        ".github/workflows/windows-exe.yml": WINDOWS_WORKFLOW,
        ".gitignore": ".pyv2-data/\nbuild/\n.builder/\n__pycache__/\n",
        "build-windows.bat": f'''@echo off
setlocal
py -m pip install --user pyinstaller "git+{SOURCE_REPOSITORY}"
if errorlevel 1 exit /b 1
py -m pyv2 check . || exit /b 1
py -m pyv2 build . --native --output build\\windows
''',
        ".vscode/settings.json": json.dumps({"files.associations": {"*.pyv2": "pythonv2"}}, indent=2) + "\n",
        ".vscode/tasks.json": json.dumps({
            "version": "2.0.0",
            "tasks": [
                {"label": "Python v2: Check app", "type": "shell", "command": "pyv2 check .", "problemMatcher": []},
                {"label": "Python v2: Build Windows kit", "type": "shell", "command": "pyv2 build .", "problemMatcher": []},
            ],
        }, indent=2) + "\n",
    }
    for relative, content in files.items():
        path = project / relative
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return project
