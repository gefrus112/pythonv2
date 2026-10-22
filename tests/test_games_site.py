"""Website arcade, game-source, and refreshed-brand smoke tests."""

import re
import subprocess
import unittest
from pathlib import Path

from pyv2.interpreter import run_capture

ROOT = Path(__file__).resolve().parent.parent


class GamesSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "games.html").read_text(encoding="utf-8")

    def test_ten_game_cards_and_direct_targets(self):
        cards = re.findall(r'class="arcade-card(?: [^"]*)?"', self.html)
        self.assertEqual(len(cards), 10)
        for target in ("byte-beast", "comet-hopper", "comet-circuit", "pocket-arcade"):
            self.assertIn(f'id="{target}"', self.html)
            self.assertIn(f'href="#{target}"', self.html)

    def test_python_v2_arcade_manifest(self):
        match = re.search(
            r'<script id="arcade-manifest" type="text/pyv2">([\s\S]*?)</script>',
            self.html,
        )
        self.assertIsNotNone(match)
        output, error = run_capture(match.group(1))
        self.assertIsNone(error)
        lines = output.splitlines()
        self.assertEqual(len(lines), 7)
        self.assertTrue(all(line.count("|") == 2 for line in lines))

    def test_every_page_uses_uncached_v2_logo(self):
        for page in ROOT.glob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn('src="logo.svg"', text, page.name)
            self.assertNotIn('href="favicon.svg"', text, page.name)
            self.assertIn("favicon-v2.svg", text, page.name)

    def test_playground_has_dual_runtime_terminals_and_workshop(self):
        playground = (ROOT / "playground.html").read_text(encoding="utf-8")
        for required in (
            'data-runtime="pyv2"', 'data-runtime="classic"', 'id="play-output"',
            'id="play-errors"', 'id="command-input"', 'id="site-preview"',
            'id="site-html-source"', 'id="copy-website-html"',
            'data-site-view="preview"', 'data-site-view="html"',
            'data-preview-size="mobile"', 'data-preview-size="desktop"',
            'src="classic-python.js"', 'src="playground.js"',
        ):
            self.assertIn(required, playground)
        for page in ROOT.glob("*.html"):
            self.assertIn('href="playground.html"', page.read_text(encoding="utf-8"), page.name)

    def test_portfolio_starter_emits_projects_games_and_profile(self):
        script = (ROOT / "playground.js").read_text(encoding="utf-8")
        match = re.search(
            r'"website-v2": \{[\s\S]*?source: `([\s\S]*?)`,\n    \},',
            script,
        )
        self.assertIsNotNone(match)
        output, error = run_capture(match.group(1))
        self.assertIsNone(error)
        lines = output.splitlines()
        self.assertTrue(lines[0].startswith("PROFILE|"))
        self.assertEqual(sum(line.startswith("PROJECT|") for line in lines), 3)
        self.assertEqual(sum(line.startswith("GAME|") for line in lines), 3)
        self.assertGreaterEqual(sum(line.startswith("SKILL|") for line in lines), 6)
        self.assertIn("PythonV2PortfolioTemplate", script)

    def test_classic_python_compatibility_smoke(self):
        completed = subprocess.run(
            ["node", str(ROOT / "tests" / "classic_python_smoke.js")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Classic compatibility smoke OK", completed.stdout)

    def test_all_pocket_games_render_headlessly(self):
        completed = subprocess.run(
            ["node", str(ROOT / "tests" / "arcade_smoke.js")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("7 game modes rendered", completed.stdout)


if __name__ == "__main__":
    unittest.main()
