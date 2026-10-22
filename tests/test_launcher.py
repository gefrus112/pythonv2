"""Tests for Python v2 Launcher project generation (headless-safe)."""

from pathlib import Path
import json
import tempfile
import unittest

from pyv2.interpreter import Interpreter
from pyv2.launcher import (
    SettingsStore,
    WorkspaceFileService,
    create_project,
    detect_editors,
    packaged_assets,
    safe_name,
)
from pyv2.parser import parse


class TestLauncherProjects(unittest.TestCase):
    def test_safe_name(self):
        self.assertEqual(safe_name(" My Cool Site! "), "My-Cool-Site")
        self.assertEqual(safe_name("***"), "python-v2-project")
        with tempfile.TemporaryDirectory() as tmp:
            quoted = create_project(tmp, 'Ada "Web" <Lab>', "website")
            parse((quoted / "app.pyv2").read_text())
            self.assertIn("&lt;Lab&gt;", (quoted / "index.html").read_text())

    def test_create_cli_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(tmp, "Hello CLI", "cli")
            self.assertEqual(project.name, "Hello-CLI")
            source = (project / "main.pyv2").read_text()
            parse(source)
            self.assertIn("pyv2 main.pyv2", (project / "README.md").read_text())

    def test_create_website_includes_offline_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(tmp, "Launch Site", "website")
            expected = {"index.html", "app.pyv2", "runner.js", "pyv2.js", "README.md", ".vscode"}
            self.assertEqual({p.name for p in project.iterdir()}, expected)
            self.assertTrue((project / ".vscode/tasks.json").exists())
            self.assertEqual(json.loads((project / ".vscode/tasks.json").read_text())["version"], "2.0.0")
            self.assertGreater((project / "pyv2.js").stat().st_size, 30_000)
            self.assertIn('script src="pyv2.js"', (project / "index.html").read_text())
            parse((project / "app.pyv2").read_text())

    def test_website_template_is_portfolio_and_game_showcase(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(tmp, "Alex Portfolio", "website")
            source = (project / "app.pyv2").read_text()
            output = []
            Interpreter(output=output.append).run(source)
            self.assertTrue(output[0].startswith("PROFILE|Alex Portfolio|"))
            self.assertEqual(sum(line.startswith("PROJECT|") for line in output), 2)
            self.assertEqual(sum(line.startswith("GAME|") for line in output), 2)
            page = (project / "index.html").read_text()
            self.assertIn('id="projects"', page)
            self.assertIn('id="game-grid"', page)
            self.assertIn('id="contact"', page)

    def test_existing_files_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(tmp, "Safe", "cli")
            source = project / "main.pyv2"
            source.write_text("print(99)\n")
            create_project(tmp, "Safe", "cli")
            self.assertEqual(source.read_text(), "print(99)\n")

    def test_game_project_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(tmp, "Arena", "game")
            output = []
            actions = iter(["attack", "attack", "attack"])
            Interpreter(output=output.append, read_input=lambda _prompt="": next(actions)).run(
                (project / "game.pyv2").read_text()
            )
            self.assertIn("YOU WIN", output)

    def test_unknown_project_kind_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                create_project(tmp, "Nope", "spaceship")

    def test_workspace_file_service_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WorkspaceFileService(tmp)
            service.create_folder("src")
            path = service.write_text("src/main.pyv2", "print(42)\n")
            self.assertEqual(path.read_text(), "print(42)\n")
            self.assertEqual(service.read_text("src/main.pyv2"), "print(42)\n")
            entries = {entry["path"]: entry for entry in service.list_entries()}
            self.assertTrue(entries["src"]["directory"])
            self.assertEqual(entries["src/main.pyv2"]["size"], 10)
            renamed = service.rename("src/main.pyv2", "src/app.pyv2")
            self.assertEqual(renamed.name, "app.pyv2")
            service.delete("src/app.pyv2")
            service.delete("src")
            self.assertEqual(service.list_entries(), [])

    def test_workspace_file_service_blocks_escape_and_recursive_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WorkspaceFileService(tmp)
            with self.assertRaises(ValueError):
                service.write_text("../escape.txt", "no")
            with self.assertRaises(ValueError):
                service.read_text(Path(tmp).parent / "outside.txt")
            service.write_text("folder/file.txt", "safe")
            with self.assertRaises(OSError):
                service.delete("folder")

    def test_settings_store_roundtrip_and_invalid_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore(path)
            saved = store.load()
            saved.update({"workspace": str(Path(tmp) / "work"), "editor": "Zed", "font_size": 15, "autosave": True})
            store.save(saved)
            self.assertEqual(store.load()["editor"], "Zed")
            self.assertEqual(store.load()["font_size"], 15)
            path.write_text("{not valid json")
            self.assertEqual(store.load()["editor"], "Auto detect")

    def test_connected_editor_detection(self):
        found = detect_editors(lambda command: f"/tools/{command}" if command in {"code", "zed"} else None)
        connected = {entry["name"] for entry in found if entry["connected"]}
        self.assertEqual(connected, {"VS Code", "Zed"})
        self.assertEqual(len(found), 5)

    def test_packaged_pyhope_assets(self):
        assets = packaged_assets()
        self.assertEqual(len(assets), 8)
        self.assertIn("comet-pilot.svg", assets)
        self.assertIn("race-car.svg", assets)


if __name__ == "__main__":
    unittest.main()
