"""Python v2 command line, app validator, and Windows executable builder."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from . import __version__
from .builder import (
    BuildError,
    build_native_windows,
    check_app,
    create_windows_project,
    prepare_windows_build,
)
from .interpreter import Interpreter, Pyv2Error
from .parser import ParseError
from .runtime import AppRuntime


BANNER = f"""Python v2 {__version__} (the snake, but better)
Builtins include collections, JSON, sandboxed app files, arguments, and native dialogs.
Build command: pyv2 build APP --native   New app: pyv2 new windows-app NAME
"""

WELCOME = f"Python v2 {__version__} — type away, end blocks with 'end'. Ctrl-D to quit."


def _read_input(prompt: str = "") -> str:
    return input(prompt)


def _dialog_message(title: str, message: str) -> None:
    from tkinter import messagebox
    messagebox.showinfo(title, message)


def _dialog_ask(title: str, prompt: str, default: str) -> str | None:
    from tkinter import simpledialog
    return simpledialog.askstring(title, prompt, initialvalue=default)


def _script_runtime(path: Path, app_args: list[str]) -> AppRuntime:
    root = path.resolve().parent
    name = path.stem.replace("_", " ").title()
    version = "1.0.0"
    app_id = path.stem.lower().replace("_", "-")
    config_path = root / "pyv2app.json"
    if config_path.is_file():
        try:
            config = check_app(root)
            name, version, app_id = config.name, config.version, config.app_id
        except BuildError:
            # Running a source file should still report language errors normally;
            # `pyv2 check .` is the strict metadata validation command.
            pass
    asset_root = root / "assets"
    return AppRuntime(
        app_name=name,
        app_version=version,
        app_id=app_id,
        data_root=root / ".pyv2-data",
        asset_root=asset_root if asset_root.is_dir() else None,
        argv=app_args,
        message_handler=_dialog_message,
        ask_handler=_dialog_ask,
    )


def _print_help() -> None:
    print(BANNER.rstrip())
    print("\nusage:")
    print("  pyv2 SCRIPT.pyv2 [app arguments]    run an application")
    print("  pyv2 -c CODE [app arguments]        run source text")
    print("  pyv2 check APP                      validate source and app metadata")
    print("  pyv2 new windows-app NAME           create a complete Windows app")
    print("  pyv2 build APP [--native]           create a kit or real Windows .exe")
    print("  pyv2 doctor                         inspect build readiness")
    print("  pyv2                                start the REPL")
    print("\nRun `pyv2 COMMAND --help` for command-specific options.")


def _check_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pyv2 check", description="Validate a Python v2 app before packaging.")
    parser.add_argument("app", help=".pyv2 source file or project containing pyv2app.json")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print machine-readable results")
    options = parser.parse_args(argv)
    try:
        config = check_app(options.app)
    except BuildError as exc:
        if options.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"check failed: {exc}", file=sys.stderr)
        return 1
    result = {
        "ok": True,
        "name": config.name,
        "id": config.app_id,
        "version": config.version,
        "entry": str(config.entry),
        "mode": "console" if config.console else "windowed",
        "assets": len(config.assets),
    }
    if options.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"[OK] {config.name} {config.version} is ready to build")
        print(f"  entry: {config.entry}")
        print(f"  mode:  {result['mode']} • assets: {result['assets']}")
    return 0


def _new_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pyv2 new", description="Create a production-ready Python v2 project.")
    subparsers = parser.add_subparsers(dest="kind", required=True)
    windows = subparsers.add_parser("windows-app", help="create a Windows EXE application project")
    windows.add_argument("name", help="display and project name")
    windows.add_argument("--directory", "-d", default=".", help="parent directory (default: current directory)")
    windows.add_argument("--windowed", action="store_true", help="use dialogs and hide the console window")
    options = parser.parse_args(argv)
    try:
        project = create_windows_project(options.directory, options.name, windowed=options.windowed)
    except (BuildError, OSError, ValueError) as exc:
        print(f"could not create app: {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Created {'windowed' if options.windowed else 'console'} Windows app: {project}")
    print(f"  check: pyv2 check {project}")
    print(f"  kit:   pyv2 build {project}")
    print("  exe:   run build-windows.bat on Windows or use the included GitHub workflow")
    return 0


def _build_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="pyv2 build",
        description="Create an inspectable Windows build kit or a real .exe on Windows.",
    )
    parser.add_argument("app", help=".pyv2 source file or app project")
    parser.add_argument("--output", "-o", help="build-kit directory (default: APP/build/windows)")
    parser.add_argument("--name", help="override the app and executable name")
    parser.add_argument("--icon", help="relative .ico file inside the project")
    parser.add_argument("--native", action="store_true", help="run PyInstaller now (requires Windows)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--console", action="store_true", help="build with a terminal window")
    mode.add_argument("--windowed", action="store_true", help="build without a terminal window")
    options = parser.parse_args(argv)
    console = True if options.console else False if options.windowed else None
    try:
        result = prepare_windows_build(
            options.app,
            options.output,
            name=options.name,
            icon=options.icon,
            console=console,
        )
        if options.native:
            result = build_native_windows(result)
    except (BuildError, OSError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Validated {result.config.name} {result.config.version}")
    print(f"[OK] Windows build kit: {result.kit_dir}")
    print(f"[OK] Integrity manifest: {result.manifest}")
    if result.executable:
        print(f"[OK] Windows executable: {result.executable}")
    elif os.name == "nt":
        print("Next: run the generated build.bat, or add --native after installing PyInstaller.")
    else:
        print("Next: build on Windows with build.bat or the generated GitHub Actions workflow.")
        print("PyInstaller cannot cross-compile a Windows .exe from this operating system.")
    return 0


def _doctor_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pyv2 doctor", description="Report Windows build readiness.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    options = parser.parse_args(argv)
    pyinstaller = importlib.util.find_spec("PyInstaller") is not None
    report = {
        "python_v2": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "windows": os.name == "nt",
        "pyinstaller": pyinstaller,
        "can_build_native_windows_exe": os.name == "nt" and pyinstaller,
        "can_create_windows_kit": True,
    }
    if options.as_json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"Python v2 {report['python_v2']} build doctor")
        print(f"  host:        {report['platform']}")
        print(f"  Python:      {report['python']}")
        print(f"  PyInstaller: {'ready' if pyinstaller else 'not installed'}")
        print("  build kit:   ready")
        if report["can_build_native_windows_exe"]:
            print("  Windows EXE: ready")
        elif os.name == "nt":
            print("  Windows EXE: install PyInstaller or use generated build.bat")
        else:
            print("  Windows EXE: use generated build.bat or GitHub Actions on Windows")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        return repl()
    if argv[0] in ("--version", "-V"):
        print(f"Python v2 {__version__}")
        return 0
    if argv[0] in ("--help", "-h", "help"):
        _print_help()
        return 0
    if argv[0] == "check":
        return _check_command(argv[1:])
    if argv[0] == "new":
        return _new_command(argv[1:])
    if argv[0] == "build":
        return _build_command(argv[1:])
    if argv[0] == "doctor":
        return _doctor_command(argv[1:])

    if argv[0] == "-c":
        source = argv[1] if len(argv) > 1 else ""
        local_assets = Path.cwd() / "assets"
        runtime = AppRuntime(data_root=Path.cwd() / ".pyv2-data",
                             asset_root=local_assets if local_assets.is_dir() else None,
                             argv=argv[2:], message_handler=_dialog_message, ask_handler=_dialog_ask)
        return run_source(source, "<string>", runtime)

    path = Path(argv[0]).expanduser()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"pyv2: cannot open {str(path)!r}: {exc.strerror}", file=sys.stderr)
        return 1
    return run_source(source, str(path), _script_runtime(path, argv[1:]))


def run_source(source: str, name: str, app_runtime: AppRuntime | None = None) -> int:
    interp = Interpreter(output=_write, read_input=_read_input, app_runtime=app_runtime)
    try:
        interp.run(source)
        return 0
    except ParseError as exc:
        print(f"SyntaxError: {exc.message} at line {exc.line} ({name})", file=sys.stderr)
        return 1
    except Pyv2Error as exc:
        print(exc.format(), file=sys.stderr)
        return 1
    except RecursionError:
        print("RuntimeError: maximum recursion depth exceeded", file=sys.stderr)
        return 1


def repl() -> int:
    print(WELCOME)
    local_assets = Path.cwd() / "assets"
    runtime = AppRuntime(data_root=Path.cwd() / ".pyv2-data",
                         asset_root=local_assets if local_assets.is_dir() else None,
                         message_handler=_dialog_message, ask_handler=_dialog_ask)
    interp = Interpreter(output=_write, read_input=_read_input, app_runtime=runtime)
    buffer: list[str] = []
    while True:
        try:
            prompt = "... " if buffer else ">>> "
            line = input(prompt)
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            buffer.clear()
            continue

        if line.strip() == "" and not buffer:
            continue
        if line.strip() in ("exit", "quit") and not buffer:
            return 0

        buffer.append(line)
        source = "\n".join(buffer)
        if _open_blocks(source) > 0:
            continue
        buffer.clear()
        try:
            interp.run(source)
        except ParseError as exc:
            print(f"SyntaxError: {exc.message} at line {exc.line}", file=sys.stderr)
        except Pyv2Error as exc:
            print(exc.format(), file=sys.stderr)
        except RecursionError:
            print("RuntimeError: maximum recursion depth exceeded", file=sys.stderr)


def _open_blocks(source: str) -> int:
    """Rough count of open blocks for REPL continuation prompts."""
    from .lexer import LexError, tokenize
    try:
        tokens = tokenize(source + "\n")
    except LexError:
        return 0
    depth = 0
    for tok in tokens:
        if tok.type == "KEYWORD" and tok.value in ("if", "while", "for", "fn", "try"):
            depth += 1
        elif tok.type == "KEYWORD" and tok.value == "end":
            depth -= 1
    return max(0, depth)


def _write(text: str) -> None:
    print(text)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
