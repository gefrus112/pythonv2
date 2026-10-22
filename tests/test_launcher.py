"""Tests for Python v2 Launcher project generation (headless-safe)."""

from pathlib import Path
import json
import tempfile
import unittest

from pyv2.interpreter import Interpreter
from pyv2.launcher import create_project, safe_name
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


if __name__ == "__main__":
    unittest.main()
