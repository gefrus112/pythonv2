"""Production app runtime and Windows build-tool tests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pyv2.builder import (
    BuildError,
    KIT_MARKER,
    build_native_windows,
    check_app,
    create_windows_project,
    executable_name,
    load_app_config,
    prepare_windows_build,
)
from pyv2.interpreter import run_capture
from pyv2.runtime import AppRuntime


ROOT = Path(__file__).resolve().parents[1]


class TestAppRuntime(unittest.TestCase):
    def test_json_round_trip(self):
        source = '''data = {name: "Ada", enabled: true, scores: [2, 4, 8]}
text = json_encode(data)
copy = json_decode(text)
print(text)
print(copy.name, copy.scores[2])'''
        output, error = run_capture(source)
        self.assertIsNone(error)
        self.assertEqual(output, '{"name":"Ada","enabled":true,"scores":[2,4,8]}\nAda 8')
        _, error = run_capture('json_decode("NaN")')
        self.assertIn("ValueError: json_decode()", error)
        _, error = run_capture('json_encode({1: "numeric key"})')
        self.assertIn("JSON map keys must be strings", error)
        _, error = run_capture("json_encode(9007199254740992)")
        self.assertIn("safe range", error)
        _, error = run_capture('json_decode("9007199254740992")')
        self.assertIn("safe range", error)

    def test_sandboxed_files_arguments_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "assets"
            assets.mkdir()
            (assets / "welcome.txt").write_text("hello asset", encoding="utf-8")
            runtime = AppRuntime(
                app_name="Comet Notes", app_version="2.3.1", app_id="comet-notes",
                data_root=root / "data", asset_root=assets, argv=["--save", "Ada"],
            )
            source = '''make_dir("notes")
write_text("notes/user.json", json_encode({name: args()[1]}))
append_text("notes/log.txt", "saved\\n")
print(json_decode(read_text("notes/user.json")).name)
print(read_asset("welcome.txt"))
print(file_exists("notes/log.txt"), asset_exists("welcome.txt"))
print(list_dir("notes"))
print(app_info().name, app_info().version)'''
            output, error = run_capture(source, app_runtime=runtime)
            self.assertIsNone(error)
            self.assertEqual(
                output,
                'Ada\nhello asset\ntrue true\n["log.txt", "user.json"]\nComet Notes 2.3.1',
            )
            self.assertEqual((root / "data/notes/log.txt").read_text(), "saved\n")

    def test_file_sandbox_rejects_traversal_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = AppRuntime(data_root=Path(tmp) / "data")
            for path in ("../escape.txt", str(Path(tmp).resolve() / "absolute.txt")):
                _, error = run_capture(f'write_text({json.dumps(path)}, "no")', app_runtime=runtime)
                self.assertIn("CapabilityError", error)
            self.assertFalse((Path(tmp) / "escape.txt").exists())
            limited = AppRuntime(data_root=Path(tmp) / "limited", max_text_bytes=5)
            output, error = run_capture('write_text("x.txt", "12345")\nappend_text("x.txt", "6")',
                                        app_runtime=limited)
            self.assertIn("would exceed", error)
            self.assertEqual((Path(tmp) / "limited/x.txt").read_text(), "12345")

    def test_file_services_require_an_explicit_host_capability(self):
        _, error = run_capture('write_text("x.txt", "no")')
        self.assertIn("CapabilityError", error)
        output, error = run_capture("print(len(args()), app_info().platform)")
        self.assertIsNone(error)
        self.assertEqual(output, "0 embedded")

    def test_ui_callbacks_are_explicit(self):
        messages = []
        runtime = AppRuntime(
            data_root=Path.cwd(),
            message_handler=lambda title, text: messages.append((title, text)),
            ask_handler=lambda title, prompt, default: default + "!",
        )
        output, error = run_capture(
            'ui_message("Ready", "Safe app")\nprint(ui_ask("Name", "Who?", "Ada"))',
            app_runtime=runtime,
        )
        self.assertIsNone(error)
        self.assertEqual(output, "Ada!")
        self.assertEqual(messages, [("Ready", "Safe app")])


class TestWindowsBuilder(unittest.TestCase):
    def test_windows_reserved_and_unsafe_names_are_sanitized(self):
        self.assertEqual(executable_name("My / Great:* App"), "My-Great-App")
        self.assertEqual(executable_name("CON"), "app-con")

    def test_create_validate_and_run_console_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_windows_project(tmp, "Comet Tasks")
            config = check_app(project)
            self.assertEqual(config.executable_name, "Comet-Tasks")
            self.assertTrue(config.console)
            self.assertTrue((project / ".github/workflows/windows-exe.yml").is_file())
            runtime = AppRuntime(data_root=project / ".pyv2-data", argv=["--add", "Ship EXE"])
            output, error = run_capture((project / "main.pyv2").read_text(), app_runtime=runtime)
            self.assertIsNone(error)
            self.assertEqual(output, "Added: Ship EXE")
            saved = json.loads((project / ".pyv2-data/tasks.json").read_text())
            self.assertEqual(saved, [{"title": "Ship EXE", "done": False}])

    def test_windowed_project_uses_dialog_apis(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_windows_project(tmp, "Hello Window", windowed=True)
            config = check_app(project)
            self.assertFalse(config.console)
            source = (project / "main.pyv2").read_text()
            self.assertIn("ui_ask", source)
            self.assertIn("ui_message", source)

    def test_build_kit_is_reproducible_and_inspectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_windows_project(tmp, "Comet Tasks")
            result = prepare_windows_build(project, Path(tmp) / "kit")
            expected = {
                KIT_MARKER, "BUILDING.md", "app.spec", "build.bat", "build.ps1",
                "launcher.py", "manifest.json", "pyv2app.json", "source.pyv2",
                "version_info.txt", "assets", "runtime",
            }
            self.assertEqual({path.name for path in result.kit_dir.iterdir()}, expected)
            compile((result.kit_dir / "launcher.py").read_text(), "launcher.py", "exec")
            manifest = json.loads(result.manifest.read_text())
            self.assertEqual(manifest["app"]["executable"], "Comet-Tasks.exe")
            source_hash = hashlib.sha256((project / "main.pyv2").read_bytes()).hexdigest()
            self.assertEqual(manifest["source_sha256"], source_hash)
            self.assertIn("pathex=['runtime']", (result.kit_dir / "app.spec").read_text())
            self.assertTrue((result.kit_dir / "runtime/pyv2/interpreter.py").is_file())
            self.assertIn("runtime/pyv2/interpreter.py", manifest["files"])
            self.assertIn("dist\\Comet-Tasks.exe", (result.kit_dir / "BUILDING.md").read_text())

    def test_build_refuses_to_replace_unmanaged_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_windows_project(tmp, "Safe Build")
            output = Path(tmp) / "important"
            output.mkdir()
            (output / "keep.txt").write_text("do not delete")
            with self.assertRaisesRegex(BuildError, "refusing to replace"):
                prepare_windows_build(project, output)
            self.assertEqual((output / "keep.txt").read_text(), "do not delete")

    def test_config_rejects_escape_and_broken_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "app"
            project.mkdir()
            (root / "outside.pyv2").write_text('print("no")')
            (project / "pyv2app.json").write_text(json.dumps({"entry": "../outside.pyv2", "name": "Unsafe"}))
            with self.assertRaisesRegex(BuildError, "escapes"):
                load_app_config(project)
            (project / "main.pyv2").write_text("if true print(1)")
            (project / "pyv2app.json").write_text(json.dumps({"entry": "main.pyv2", "name": "Broken"}))
            with self.assertRaisesRegex(BuildError, "SyntaxError"):
                load_app_config(project)
            (project / "main.pyv2").write_text('print("ok")')
            (project / "pyv2app.json").write_text(json.dumps({
                "entry": "main.pyv2", "name": "Unknown", "mystery": True,
            }))
            with self.assertRaisesRegex(BuildError, "unknown pyv2app.json field"):
                load_app_config(project)

    @unittest.skipIf(os.name == "nt", "symlink creation is privilege-dependent on Windows")
    def test_assets_reject_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_windows_project(root, "Linked Assets")
            outside = root / "secret.txt"
            outside.write_text("do not bundle")
            (project / "assets/secret-link.txt").symlink_to(outside)
            with self.assertRaisesRegex(BuildError, "symbolic links"):
                load_app_config(project)

    @unittest.skipIf(os.name == "nt", "non-Windows honesty check")
    def test_native_build_reports_cross_compile_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_windows_project(tmp, "Honest Build")
            result = prepare_windows_build(project)
            with self.assertRaisesRegex(BuildError, "require Windows"):
                build_native_windows(result)

    def test_cli_new_check_build_and_doctor(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands = [
                [sys.executable, "-m", "pyv2", "new", "windows-app", "CLI App", "-d", tmp],
                [sys.executable, "-m", "pyv2", "check", str(Path(tmp) / "CLI-App")],
                [sys.executable, "-m", "pyv2", "build", str(Path(tmp) / "CLI-App"),
                 "--output", str(Path(tmp) / "kit")],
                [sys.executable, "-m", "pyv2", "doctor", "--json"],
            ]
            for command in commands:
                completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            doctor = json.loads(completed.stdout)
            self.assertTrue(doctor["can_create_windows_kit"])


if __name__ == "__main__":
    unittest.main()
