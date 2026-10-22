"""Python v2 Launcher — dependency-free desktop workspace.

The workspace uses tkinter from the Python standard library. It can edit and
run .pyv2 files, manage a safe local workspace, export packaged PyHope assets,
connect installed code editors, create projects, preview generated websites,
and open the PyHope games and documentation. No Electron or pygame required.
"""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser

from . import __version__
from .interpreter import Interpreter, Pyv2Error
from .parser import ParseError

APP_TITLE = f"Python v2 + PyHope {__version__} — Sudbury Workspace"
SITE_URL = "https://gefrus112.github.io/pythonv2/"
GAMES_URL = SITE_URL + "games.html"
DOCS_URL = SITE_URL + "docs.html"
GUIDE_URL = SITE_URL + "guide.html"
PLAYGROUND_URL = SITE_URL + "playground.html"
YOUTUBE_URL = "https://www.youtube.com/@CubeCometYT"

EDITOR_COMMANDS = {
    "VS Code": "code",
    "VSCodium": "codium",
    "Zed": "zed",
    "Sublime Text": "subl",
    "PyCharm": "charm",
}

ASSET_DESCRIPTIONS = {
    "comet-hero.svg": ("Comet Kid", "Animated platform hero"),
    "comet-pilot.svg": ("Comet Pilot", "Neon shooter character"),
    "drone.svg": ("Null Drone", "Flying shooter enemy"),
    "monster.svg": ("Byte Beast", "Raycaster monster"),
    "slime.svg": ("Null Slime", "Platform enemy"),
    "race-car.svg": ("Comet Racer", "Top-down racing car"),
    "blaster.svg": ("Comet Blaster", "Original sci-fi weapon"),
    "coin.svg": ("Hope Bit", "Animated collectible"),
}


WEB_APP_SOURCE = '''# app.pyv2 — this program builds the text on your website
site_name = "{name}"
tagline = "Built with Python v2 — the snake, but better."
features = [
    "No indentation wars",
    "Runs in the browser",
    "Powered by the Python v2 runtime",
]

print(site_name)
print(tagline)
for feature in features:
    print(feature)
end
'''

WEB_INDEX = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{name} — built with Python v2</title>
  <style>
    *{{box-sizing:border-box}} body{{margin:0;min-height:100vh;display:grid;place-items:center;
    font:16px system-ui;color:#eef6ff;background:linear-gradient(135deg,#182b40,#2f6fbd)}}
    main{{width:min(760px,92vw);padding:48px;border:1px solid #ffffff30;border-radius:24px;
    background:#152536dd;box-shadow:0 30px 80px #07101c88}} h1{{font-size:clamp(40px,8vw,72px);
    margin:0;color:#ffd343}} #tagline{{font-size:20px;color:#bdd6e9}} li{{margin:10px 0}}
    .brand{{font-weight:800;color:#65cbe4}} pre{{padding:16px;border-radius:10px;background:#0e1925;color:#dcecff}}
  </style>
</head>
<body><main><div class="brand">PYTHON V2 WEBSITE</div><h1 id="title">Loading…</h1>
<p id="tagline"></p><ul id="features"></ul><pre id="console">Running app.pyv2…</pre></main>
<script src="pyv2.js"></script><script src="runner.js"></script></body>
</html>
'''

WEB_RUNNER = '''fetch("app.pyv2")
  .then((response) => response.text())
  .then((source) => {
    const result = Pyv2.runCapture(source);
    const consoleEl = document.getElementById("console");
    if (result.error) {
      consoleEl.textContent = result.error;
      consoleEl.style.color = "#ff8d87";
      return;
    }
    const lines = result.output.split("\\n");
    document.getElementById("title").textContent = lines.shift() || "Python v2 website";
    document.getElementById("tagline").textContent = lines.shift() || "";
    document.getElementById("features").innerHTML = lines.map(
      (line) => "<li>" + line.replace(/[&<>]/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;"})[ch]) + "</li>"
    ).join("");
    consoleEl.textContent = "✓ app.pyv2 ran successfully";
  })
  .catch((error) => { document.getElementById("console").textContent = "Preview error: " + error; });
'''

CLI_SOURCE = '''# main.pyv2 — {name}
fn greet(name):
    return f"Hello, {name}!"
end

print(greet("World"))
print("Edit this file, then press Run in the Python v2 Launcher.")
'''

VSCODE_SETTINGS = '''{
  "files.associations": {"*.pyv2": "pyv2"},
  "editor.tabSize": 4,
  "editor.insertSpaces": true
}
'''

VSCODE_TASKS = '''{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run current Python v2 file",
      "type": "shell",
      "command": "python3",
      "args": ["-m", "pyv2", "${file}"],
      "options": {"cwd": "${workspaceFolder}"},
      "group": {"kind": "build", "isDefault": true},
      "problemMatcher": []
    },
    {
      "label": "Preview website",
      "type": "shell",
      "command": "python3",
      "args": ["-m", "http.server", "8000", "--bind", "0.0.0.0"],
      "options": {"cwd": "${workspaceFolder}"},
      "isBackground": true,
      "problemMatcher": []
    }
  ]
}
'''

GAME_SOURCE = '''# game.pyv2 — {name}
# A tiny complete terminal game. Expand it with PyHope when you are ready.
player_hp = 20
enemy = {{name: "Byte Beast", hp: 12, damage: 3}}
print("=== {name} ===")

while player_hp > 0 and enemy.hp > 0:
    print(f"You: {{player_hp}} HP | {{enemy.name}}: {{enemy.hp}} HP")
    action = input("attack or heal? ").trim().lower()
    if action == "attack":
        enemy.hp -= 5
        print("Comet Blaster: 5 damage!")
    elif action == "heal":
        player_hp = min(20, player_hp + 4)
        print("+4 HP")
    else:
        print("Try: attack or heal")
        continue
    end
    if enemy.hp > 0:
        player_hp -= enemy.damage
    end
end
print(player_hp > 0 ? "YOU WIN" : "GAME OVER")
'''


def safe_name(name: str) -> str:
    """Return a filesystem-safe project name while preserving readable words."""
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", name.strip())
    cleaned = re.sub(r"\s+", "-", cleaned).strip("-_")
    return cleaned or "python-v2-project"


def _runtime_bytes() -> bytes:
    return resources.files("pyv2").joinpath("assets/pyv2.js").read_bytes()


def create_project(parent: str | Path, name: str, kind: str) -> Path:
    """Create a Python v2 project and return its directory.

    Kinds: ``website``, ``cli``, and ``game``. Existing files are never
    overwritten, which makes the launcher safe to use around real projects.
    """
    display_name = " ".join(name.strip().split()) or "My Python v2 Project"
    target = Path(parent).expanduser().resolve() / safe_name(display_name)
    target.mkdir(parents=True, exist_ok=True)
    kind = kind.lower()
    source_name = display_name.replace("\\", "\\\\").replace('"', '\\"')

    if kind == "website":
        files: dict[str, str | bytes] = {
            "app.pyv2": WEB_APP_SOURCE.format(name=source_name),
            "index.html": WEB_INDEX.format(name=html.escape(display_name, quote=True)),
            "runner.js": WEB_RUNNER,
            "pyv2.js": _runtime_bytes(),
            "README.md": (
                f"# {display_name}\n\nA website powered by Python v2.\n\n"
                "Edit `app.pyv2`, then use **Preview Website** in the launcher.\n"
            ),
        }
    elif kind == "game":
        files = {
            "game.pyv2": GAME_SOURCE.format(name=source_name),
            "README.md": (
                f"# {display_name}\n\nRun with `pyv2 game.pyv2`. "
                "See the PyHope guide for sprites, maps and ray casting.\n"
            ),
        }
    elif kind == "cli":
        files = {
            "main.pyv2": CLI_SOURCE.format(name=source_name),
            "README.md": f"# {display_name}\n\nRun with `pyv2 main.pyv2`.\n",
        }
    else:
        raise ValueError(f"unknown project kind: {kind}")

    # Every generated project opens cleanly in VS Code and runs the current
    # .pyv2 file with Ctrl+Shift+B.
    files[".vscode/settings.json"] = VSCODE_SETTINGS
    files[".vscode/tasks.json"] = VSCODE_TASKS

    for filename, content in files.items():
        path = target / filename
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return target


class WorkspaceFileService:
    """Small, safe file service used by the desktop workspace.

    Every path is resolved beneath ``root``. Writes are atomic and UTF-8 text
    only; traversal and symlink escapes are rejected before touching a file.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str | Path) -> Path:
        relative = Path(relative)
        if relative.is_absolute():
            raise ValueError("workspace paths must be relative")
        target = (self.root / relative).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes the workspace") from exc
        return target

    def list_entries(self) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for path in sorted(self.root.rglob("*"), key=lambda item: (not item.is_dir(), str(item).lower())):
            if any(part.startswith(".") and part != ".vscode" for part in path.relative_to(self.root).parts):
                continue
            entries.append({
                "path": path.relative_to(self.root).as_posix(),
                "directory": path.is_dir(),
                "size": 0 if path.is_dir() else path.stat().st_size,
            })
        return entries

    def read_text(self, relative: str | Path, max_bytes: int = 2_000_000) -> str:
        path = self.resolve(relative)
        if not path.is_file():
            raise FileNotFoundError(str(relative))
        if path.stat().st_size > max_bytes:
            raise ValueError("file is too large for the built-in editor")
        return path.read_text(encoding="utf-8")

    def write_text(self, relative: str | Path, content: str) -> Path:
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        return path

    def create_folder(self, relative: str | Path) -> Path:
        path = self.resolve(relative)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def rename(self, old: str | Path, new: str | Path) -> Path:
        source, target = self.resolve(old), self.resolve(new)
        if not source.exists():
            raise FileNotFoundError(str(old))
        if target.exists():
            raise FileExistsError(str(new))
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return target

    def delete(self, relative: str | Path) -> None:
        path = self.resolve(relative)
        if not path.exists():
            raise FileNotFoundError(str(relative))
        if path.is_dir():
            path.rmdir()  # intentionally refuses non-empty recursive deletion
        else:
            path.unlink()


class SettingsStore:
    DEFAULTS = {
        "workspace": str(Path.home() / "PythonV2Workspace"),
        "editor": "Auto detect",
        "font_size": 12,
        "autosave": False,
    }

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or (Path.home() / ".pythonv2" / "settings.json")).expanduser()

    def load(self) -> dict[str, object]:
        settings = dict(self.DEFAULTS)
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update({key: loaded[key] for key in settings.keys() & loaded.keys()})
        except (OSError, ValueError, TypeError):
            pass
        return settings

    def save(self, settings: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        clean = dict(self.DEFAULTS)
        clean.update({key: settings[key] for key in clean.keys() & settings.keys()})
        self.path.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")


def detect_editors(which=shutil.which) -> list[dict[str, object]]:
    """Return all supported external editors and whether they are connected."""
    found = []
    for name, command in EDITOR_COMMANDS.items():
        path = which(command)
        found.append({"name": name, "command": command, "path": path, "connected": bool(path)})
    return found


def packaged_assets() -> list[str]:
    root = resources.files("pyhope").joinpath("assets")
    try:
        return sorted(item.name for item in root.iterdir() if item.name.endswith(".svg"))
    except (FileNotFoundError, NotADirectoryError):
        return []


class Launcher:
    BG = "#111c27"
    PANEL = "#182838"
    PANEL_2 = "#20364a"
    BLUE = "#2f6fbd"
    BLUE_LIGHT = "#5fc4dc"
    RED = "#d64541"
    YELLOW = "#ffd343"
    TEXT = "#edf5fb"
    MUTED = "#9db4c7"

    def __init__(self, root, tk, ttk, dialogs):
        self.root, self.tk, self.ttk = root, tk, ttk
        self.filedialog, self.messagebox, self.simpledialog = dialogs
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.file_service = WorkspaceFileService(str(self.settings["workspace"]))
        self.current_file: Path | None = None
        self.current_project: Path | None = None
        self.workspace_selection: str | None = None
        self.workspace_list = None
        self.workspace_editor = None
        self.servers: list[ThreadingHTTPServer] = []
        self.nav_buttons = {}
        self.editor = None
        self.output = None

        root.title(APP_TITLE)
        root.geometry("1180x760")
        root.minsize(900, 620)
        root.configure(bg=self.BG)
        self._configure_styles()
        self._build_shell()
        self.show_home()
        self._bind_shortcuts()

    def _configure_styles(self):
        style = self.ttk.Style()
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass
        style.configure("App.TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Title.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 25, "bold"))
        style.configure("Sub.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 11))
        style.configure("CardTitle.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI", 14, "bold"))
        style.configure("CardText.TLabel", background=self.PANEL, foreground=self.MUTED, font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(15, 10), background=self.YELLOW, foreground="#17222d")
        style.map("Accent.TButton", background=[("active", "#ffe173")])
        style.configure("Blue.TButton", font=("Segoe UI", 10, "bold"), padding=(13, 9), background=self.BLUE, foreground="white")
        style.map("Blue.TButton", background=[("active", "#4385c6")])
        style.configure("Dark.TButton", font=("Segoe UI", 10), padding=(12, 9), background=self.PANEL_2, foreground=self.TEXT)
        style.map("Dark.TButton", background=[("active", "#2a4861")])
        style.configure("TCombobox", padding=7)

    def _build_shell(self):
        self.header = self.tk.Frame(self.root, bg=self.PANEL, height=80)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self._draw_logo(self.header)
        title_box = self.tk.Frame(self.header, bg=self.PANEL)
        title_box.pack(side="left", pady=16)
        self.tk.Label(title_box, text="PYTHON V2 + PYHOPE", bg=self.PANEL, fg=self.TEXT,
                      font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.tk.Label(title_box, text="1.1 SUDBURY • CREATIVE WORKSPACE", bg=self.PANEL,
                      fg=self.YELLOW, font=("Consolas", 9, "bold")).pack(anchor="w")
        self.tk.Button(self.header, text="DONATION • COMING SOON", state="disabled",
                       disabledforeground="#6d7d8b", bg="#273746", relief="flat",
                       padx=16, pady=8).pack(side="right", padx=22, pady=21)
        self.tk.Button(self.header, text="▶ SUBSCRIBE @CubeCometYT", command=lambda: webbrowser.open(YOUTUBE_URL),
                       bg="#ff0033", fg="white", activebackground="#df002c", activeforeground="white",
                       font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                       padx=16, pady=8).pack(side="right", pady=21)

        body = self.tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True)
        self.sidebar = self.tk.Frame(body, bg="#0d1720", width=205)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.content = self.tk.Frame(body, bg=self.BG)
        self.content.pack(side="left", fill="both", expand=True)

        nav = [
            ("⌂  Home", self.show_home),
            (">_  Code Studio", self.show_editor),
            ("▤  Files", self.show_files),
            ("＋  New Project", self.show_projects),
            ("◆  Assets", self.show_assets),
            ("▦  Games & GPU", self.show_games),
            ("↗  Connected Editors", self.show_editors),
            ("⚙  Settings", self.show_settings),
            ("?  Docs & Learn", self.show_docs),
        ]
        for label, command in nav:
            button = self.tk.Button(self.sidebar, text=label, command=partial(self._navigate, label, command),
                                    anchor="w", bg="#0d1720", fg=self.MUTED,
                                    activebackground=self.PANEL_2, activeforeground="white",
                                    bd=0, relief="flat", padx=20, pady=10,
                                    font=("Segoe UI", 10), cursor="hand2")
            button.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[label] = button
        self.tk.Label(self.sidebar, text="PYV2 1.1.0 • PYHOPE\nFILES • ASSETS • EDITORS",
                      justify="left", bg="#0d1720", fg="#5e7688",
                      font=("Consolas", 8)).pack(side="bottom", anchor="w", padx=22, pady=22)

        self.status = self.tk.Label(self.root, text="Ready", anchor="w", bg="#0a1219", fg=self.MUTED,
                                    padx=12, pady=5, font=("Consolas", 9))
        self.status.pack(fill="x", side="bottom")

    def _draw_logo(self, parent):
        canvas = self.tk.Canvas(parent, width=66, height=60, bg=self.PANEL, highlightthickness=0)
        canvas.pack(side="left", padx=(18, 12), pady=9)
        canvas.create_rectangle(9, 8, 43, 30, fill=self.BLUE, outline="#6ba4d3", width=2)
        canvas.create_rectangle(4, 20, 28, 45, fill=self.BLUE, outline="#6ba4d3", width=2)
        canvas.create_oval(14, 13, 20, 19, fill="white", outline="")
        canvas.create_rectangle(23, 29, 57, 51, fill=self.RED, outline="#ed7770", width=2)
        canvas.create_rectangle(38, 16, 62, 41, fill=self.RED, outline="#ed7770", width=2)
        canvas.create_oval(46, 41, 52, 47, fill="white", outline="")

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda _e: self.open_file())
        self.root.bind("<Control-s>", lambda _e: self.save_file())
        self.root.bind("<Control-Return>", lambda _e: self.run_editor())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _navigate(self, active, command):
        for label, button in self.nav_buttons.items():
            selected = label == active
            button.configure(bg=self.PANEL_2 if selected else "#0d1720",
                             fg=self.YELLOW if selected else self.MUTED)
        command()

    def _clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _page_head(self, title, subtitle):
        self.tk.Label(self.content, text=title, bg=self.BG, fg=self.TEXT,
                      font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=32, pady=(28, 3))
        self.tk.Label(self.content, text=subtitle, bg=self.BG, fg=self.MUTED,
                      font=("Segoe UI", 11), wraplength=800, justify="left").pack(anchor="w", padx=32, pady=(0, 20))

    def _card(self, parent, title, text, button, command, color=None):
        frame = self.tk.Frame(parent, bg=self.PANEL, highlightbackground="#2e4559", highlightthickness=1)
        self.tk.Frame(frame, bg=color or self.BLUE, height=5).pack(fill="x")
        self.tk.Label(frame, text=title, bg=self.PANEL, fg=self.TEXT,
                      font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18, pady=(17, 6))
        self.tk.Label(frame, text=text, bg=self.PANEL, fg=self.MUTED,
                      font=("Segoe UI", 10), justify="left", wraplength=250).pack(anchor="w", padx=18)
        self.ttk.Button(frame, text=button, command=command, style="Blue.TButton").pack(anchor="w", padx=18, pady=18)
        return frame

    def show_home(self):
        self._clear()
        self._page_head("Python v2 + PyHope Home", "Code, managed files, offline assets, projects, games, editor connections, and settings in one lightweight workspace.")
        hero = self.tk.Frame(self.content, bg="#203d59", highlightbackground=self.BLUE_LIGHT, highlightthickness=1)
        hero.pack(fill="x", padx=32, pady=(0, 22))
        self.tk.Label(hero, text="PYTHON V2 1.1 • SUDBURY", bg="#203d59", fg=self.YELLOW,
                      font=("Consolas", 10, "bold")).pack(anchor="w", padx=24, pady=(20, 5))
        self.tk.Label(hero, text="The snake, but better — now with its own app.", bg="#203d59", fg="white",
                      font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=24)
        self.tk.Label(hero, text="Edit .pyv2 • manage files • export assets • connect editors • build websites and games",
                      bg="#203d59", fg="#c9deee", font=("Segoe UI", 10)).pack(anchor="w", padx=24, pady=(5, 20))

        grid = self.tk.Frame(self.content, bg=self.BG)
        grid.pack(fill="both", expand=True, padx=32)
        for column in range(3):
            grid.columnconfigure(column, weight=1, uniform="cards")
        cards = [
            ("Code Studio", "Edit and run .pyv2 programs with a built-in output console.", "Open editor", self.show_editor, self.BLUE),
            ("Workspace Files", "Create, read, save, rename, and safely delete files inside your own workspace.", "Manage files", self.show_files, "#44a36f"),
            ("Website Builder", "Create a complete browser project generated by Python v2.", "New website", self.show_projects, self.RED),
            ("Asset Library", "Export eight packaged CC0 PyHope characters, enemies, weapons, cars, and coins.", "Browse assets", self.show_assets, "#8f2c52"),
            ("PyHope Arcade", "Open 10 shooters, platformers, racers, and the 9.4M GPU lab.", "Play games", self.show_games, "#7655b7"),
            ("Connected Editors", "Detect VS Code, VSCodium, Zed, Sublime Text, and PyCharm.", "Check editors", self.show_editors, self.YELLOW),
        ]
        for index, args in enumerate(cards):
            row, col = divmod(index, 3)
            card = self._card(grid, *args)
            card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 7, 0 if col == 2 else 7), pady=7)

    def show_editor(self):
        self._clear()
        top = self.tk.Frame(self.content, bg=self.BG)
        top.pack(fill="x", padx=24, pady=(20, 10))
        self.tk.Label(top, text="Code Studio", bg=self.BG, fg=self.TEXT,
                      font=("Segoe UI", 21, "bold")).pack(side="left")
        for text, command, style in [
            ("Open", self.open_file, "Dark.TButton"), ("Save", self.save_file, "Dark.TButton"),
            ("▶ Run  Ctrl+Enter", self.run_editor, "Accent.TButton")]:
            self.ttk.Button(top, text=text, command=command, style=style).pack(side="right", padx=4)
        panes = self.tk.PanedWindow(self.content, orient="vertical", bg=self.BG, sashwidth=6,
                                   sashrelief="flat", bd=0)
        panes.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        editor_frame = self.tk.Frame(panes, bg=self.PANEL)
        self.editor = self.tk.Text(editor_frame, bg="#101a24", fg="#e5edf4", insertbackground=self.YELLOW,
                                   selectbackground=self.BLUE, relief="flat", padx=16, pady=14,
                                   undo=True, font=("Consolas", int(self.settings.get("font_size", 12))), wrap="none")
        self.editor.pack(fill="both", expand=True)
        if self.current_file and self.current_file.exists():
            self.editor.insert("1.0", self.current_file.read_text(encoding="utf-8"))
        else:
            self.editor.insert("1.0", CLI_SOURCE.format(name="My Python v2 App"))
        out_frame = self.tk.Frame(panes, bg="#0c151e")
        self.output = self.tk.Text(out_frame, height=8, bg="#0c151e", fg="#9fe3b9", relief="flat",
                                   padx=16, pady=12, state="disabled", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True)
        panes.add(editor_frame, minsize=260)
        panes.add(out_frame, minsize=100)

    def open_file(self):
        path = self.filedialog.askopenfilename(title="Open Python v2 file", filetypes=[("Python v2", "*.pyv2"), ("All files", "*.*")])
        if not path:
            return
        self.current_file = Path(path)
        if self.editor is None or not self.editor.winfo_exists():
            self.show_editor()
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.current_file.read_text(encoding="utf-8"))
        self._set_status("Opened " + str(self.current_file))

    def save_file(self):
        if self.editor is None or not self.editor.winfo_exists():
            return
        if not self.current_file:
            path = self.filedialog.asksaveasfilename(title="Save Python v2 file", defaultextension=".pyv2",
                                                     filetypes=[("Python v2", "*.pyv2")])
            if not path:
                return
            self.current_file = Path(path)
        self.current_file.write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
        self._set_status("Saved " + str(self.current_file))

    def run_editor(self):
        if self.editor is None or not self.editor.winfo_exists():
            return
        if self.settings.get("autosave") and self.current_file:
            self.current_file.write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
            self._set_status("Autosaved " + str(self.current_file))
        lines = []
        interp = Interpreter(output=lines.append, read_input=lambda prompt="": self.simpledialog.askstring("Python v2 input", prompt) or "")
        try:
            interp.run(self.editor.get("1.0", "end-1c"))
            text, error = "\n".join(lines), False
        except (Pyv2Error, ParseError) as exc:
            formatted = exc.format() if hasattr(exc, "format") else str(exc)
            text = ("\n".join(lines) + "\n" if lines else "") + formatted
            error = True
        except Exception as exc:  # keep the editor alive even for host-level bugs
            text, error = "Launcher error: " + str(exc), True
        self.output.configure(state="normal", fg="#ff8d87" if error else "#9fe3b9")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text or "✓ Program finished (no output)")
        self.output.configure(state="disabled")
        self._set_status("Run finished" if not error else "Run finished with an error")

    # ------------------------------------------------------------------
    # Built-in workspace file service
    # ------------------------------------------------------------------
    def show_files(self):
        self._clear()
        self._page_head("Files", "Your own local file service. Every operation stays inside the configured workspace, and saves are atomic.")
        toolbar = self.tk.Frame(self.content, bg=self.BG)
        toolbar.pack(fill="x", padx=32, pady=(0, 12))
        self.tk.Label(toolbar, text=str(self.file_service.root), bg=self.BG, fg=self.BLUE_LIGHT,
                      font=("Consolas", 9)).pack(side="left")
        self.ttk.Button(toolbar, text="Change workspace", command=self._change_workspace,
                        style="Dark.TButton").pack(side="right")
        self.ttk.Button(toolbar, text="New folder", command=self._new_workspace_folder,
                        style="Dark.TButton").pack(side="right", padx=5)
        self.ttk.Button(toolbar, text="New file", command=self._new_workspace_file,
                        style="Accent.TButton").pack(side="right", padx=5)

        split = self.tk.PanedWindow(self.content, orient="horizontal", bg=self.BG, sashwidth=6, bd=0)
        split.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        left = self.tk.Frame(split, bg=self.PANEL)
        self.workspace_list = self.tk.Listbox(left, bg="#0d1720", fg=self.TEXT,
                                              selectbackground=self.BLUE, selectforeground="white",
                                              relief="flat", font=("Consolas", 10), activestyle="none")
        self.workspace_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.workspace_list.bind("<<ListboxSelect>>", self._select_workspace_entry)
        split.add(left, minsize=260)

        right = self.tk.Frame(split, bg=self.PANEL)
        head = self.tk.Frame(right, bg=self.PANEL)
        head.pack(fill="x", padx=14, pady=(12, 7))
        self.workspace_file_label = self.tk.Label(head, text="Select a text file", bg=self.PANEL,
                                                  fg=self.MUTED, font=("Consolas", 10))
        self.workspace_file_label.pack(side="left")
        self.ttk.Button(head, text="Open in Code Studio", command=self._open_workspace_in_studio,
                        style="Dark.TButton").pack(side="right")
        self.ttk.Button(head, text="Delete", command=self._delete_workspace_entry,
                        style="Dark.TButton").pack(side="right", padx=4)
        self.ttk.Button(head, text="Rename", command=self._rename_workspace_entry,
                        style="Dark.TButton").pack(side="right", padx=4)
        self.ttk.Button(head, text="Save", command=self._save_workspace_file,
                        style="Blue.TButton").pack(side="right", padx=4)
        self.workspace_editor = self.tk.Text(right, bg="#0e1822", fg="#e5edf4", insertbackground=self.YELLOW,
                                             selectbackground=self.BLUE, relief="flat", padx=16, pady=14,
                                             undo=True, font=("Consolas", int(self.settings.get("font_size", 12))), wrap="none")
        self.workspace_editor.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        split.add(right, minsize=430)
        self._refresh_workspace_files()

    def _refresh_workspace_files(self, select: str | None = None):
        if self.workspace_list is None or not self.workspace_list.winfo_exists():
            return
        self.workspace_entries = self.file_service.list_entries()
        self.workspace_list.delete(0, "end")
        selected_index = None
        for index, entry in enumerate(self.workspace_entries):
            marker = "▸ " if entry["directory"] else "  "
            suffix = "/" if entry["directory"] else f"  ({entry['size']} B)"
            self.workspace_list.insert("end", marker + str(entry["path"]) + suffix)
            if select == entry["path"]:
                selected_index = index
        if selected_index is not None:
            self.workspace_list.selection_set(selected_index)
            self.workspace_list.see(selected_index)
            self._select_workspace_entry()

    def _select_workspace_entry(self, _event=None):
        selected = self.workspace_list.curselection() if self.workspace_list else ()
        if not selected:
            return
        entry = self.workspace_entries[selected[0]]
        self.workspace_selection = str(entry["path"])
        self.workspace_file_label.configure(text=self.workspace_selection)
        self.workspace_editor.configure(state="normal")
        self.workspace_editor.delete("1.0", "end")
        if entry["directory"]:
            self.workspace_editor.insert("1.0", "Folder: " + self.workspace_selection + "\n\nCreate or select a file to edit its contents.")
            self.workspace_editor.configure(state="disabled")
        else:
            self.workspace_editor.configure(state="normal")
            try:
                self.workspace_editor.insert("1.0", self.file_service.read_text(self.workspace_selection))
            except (UnicodeDecodeError, ValueError) as exc:
                self.workspace_editor.insert("1.0", "Preview unavailable: " + str(exc))
                self.workspace_editor.configure(state="disabled")

    def _new_workspace_file(self):
        name = self.simpledialog.askstring("New workspace file", "Relative name (for example: src/main.pyv2)")
        if not name:
            return
        try:
            path = self.file_service.resolve(name)
            if path.exists():
                raise FileExistsError(name)
            starter = CLI_SOURCE.format(name=path.stem) if path.suffix == ".pyv2" else ""
            self.file_service.write_text(name, starter)
            self._refresh_workspace_files(Path(name).as_posix())
            self._set_status("Created workspace file " + name)
        except Exception as exc:
            self.messagebox.showerror("Could not create file", str(exc))

    def _new_workspace_folder(self):
        name = self.simpledialog.askstring("New workspace folder", "Relative folder name")
        if not name:
            return
        try:
            self.file_service.create_folder(name)
            self._refresh_workspace_files(Path(name).as_posix())
            self._set_status("Created workspace folder " + name)
        except Exception as exc:
            self.messagebox.showerror("Could not create folder", str(exc))

    def _save_workspace_file(self):
        if not self.workspace_selection or self.workspace_editor is None:
            return
        try:
            if self.file_service.resolve(self.workspace_selection).is_dir():
                return
            self.file_service.write_text(self.workspace_selection, self.workspace_editor.get("1.0", "end-1c"))
            self._refresh_workspace_files(self.workspace_selection)
            self._set_status("Saved " + self.workspace_selection)
        except Exception as exc:
            self.messagebox.showerror("Could not save file", str(exc))

    def _rename_workspace_entry(self):
        if not self.workspace_selection:
            return
        new = self.simpledialog.askstring("Rename workspace entry", "New relative path", initialvalue=self.workspace_selection)
        if not new or new == self.workspace_selection:
            return
        try:
            self.file_service.rename(self.workspace_selection, new)
            self.workspace_selection = Path(new).as_posix()
            self._refresh_workspace_files(self.workspace_selection)
            self._set_status("Renamed to " + self.workspace_selection)
        except Exception as exc:
            self.messagebox.showerror("Could not rename", str(exc))

    def _delete_workspace_entry(self):
        if not self.workspace_selection:
            return
        if not self.messagebox.askyesno("Delete workspace entry", f"Delete {self.workspace_selection}?\n\nNon-empty folders are always protected."):
            return
        try:
            self.file_service.delete(self.workspace_selection)
            self.workspace_selection = None
            self._refresh_workspace_files()
            self.workspace_editor.configure(state="normal")
            self.workspace_editor.delete("1.0", "end")
            self._set_status("Workspace entry deleted")
        except Exception as exc:
            self.messagebox.showerror("Could not delete", str(exc))

    def _open_workspace_in_studio(self):
        if not self.workspace_selection:
            return
        path = self.file_service.resolve(self.workspace_selection)
        if not path.is_file():
            return
        self.current_file = path
        self.show_editor()

    def _change_workspace(self):
        chosen = self.filedialog.askdirectory(title="Choose Python v2 workspace")
        if not chosen:
            return
        self.settings["workspace"] = chosen
        self.settings_store.save(self.settings)
        self.file_service = WorkspaceFileService(chosen)
        self.workspace_selection = None
        self.show_files()
        self._set_status("Workspace changed to " + chosen)

    # ------------------------------------------------------------------
    # Offline PyHope assets
    # ------------------------------------------------------------------
    def show_assets(self):
        self._clear()
        self._page_head("Assets", "Eight original CC0 sprites ship inside PyHope. Export them into any game without downloading a third-party pack.")
        actions = self.tk.Frame(self.content, bg=self.BG)
        actions.pack(fill="x", padx=32, pady=(0, 10))
        self.ttk.Button(actions, text="Open animated web gallery", style="Accent.TButton",
                        command=lambda: webbrowser.open(GAMES_URL + "#sprites")).pack(side="left")
        self.tk.Label(actions, text="CC0 • commercial use allowed • SVG • original artwork",
                      bg=self.BG, fg=self.MUTED, font=("Consolas", 9)).pack(side="left", padx=15)
        grid = self.tk.Frame(self.content, bg=self.BG)
        grid.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        for column in range(2):
            grid.columnconfigure(column, weight=1)
        for index, asset in enumerate(packaged_assets()):
            title, description = ASSET_DESCRIPTIONS.get(asset, (Path(asset).stem.replace("-", " ").title(), "PyHope CC0 asset"))
            card = self._card(grid, title, description + "\n" + asset, "Export SVG",
                              lambda name=asset: self._export_asset(name), [self.BLUE, self.RED, "#44a36f", "#8f2c52"][index % 4])
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=7, pady=7)

    def _export_asset(self, name: str):
        target = self.filedialog.asksaveasfilename(title="Export PyHope asset", initialfile=name,
                                                   defaultextension=".svg", filetypes=[("SVG image", "*.svg")])
        if not target:
            return
        try:
            data = resources.files("pyhope").joinpath("assets", name).read_bytes()
            Path(target).write_bytes(data)
            self._set_status("Exported " + name + " to " + target)
        except Exception as exc:
            self.messagebox.showerror("Could not export asset", str(exc))

    # ------------------------------------------------------------------
    # Connected editors and settings
    # ------------------------------------------------------------------
    def show_editors(self):
        self._clear()
        self._page_head("Connected Editors", "Use the built-in Code Studio or open your workspace in a detected desktop editor. Detection uses PATH only—no accounts or tokens.")
        grid = self.tk.Frame(self.content, bg=self.BG)
        grid.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)
        built_in = self._card(grid, "Python v2 Code Studio", "CONNECTED • Built in\nRun .pyv2 files without another application.",
                              "Open Code Studio", self.show_editor, "#44a36f")
        built_in.grid(row=0, column=0, sticky="nsew", padx=7, pady=7)
        playground = self._card(grid, "Browser Playground", "CONNECTED • Web\nPython v2, Classic compatibility, commands, errors, and templates.",
                                "Open Playground", lambda: webbrowser.open(PLAYGROUND_URL), self.BLUE)
        playground.grid(row=0, column=1, sticky="nsew", padx=7, pady=7)
        for index, editor in enumerate(detect_editors(), start=2):
            connected = bool(editor["connected"])
            text = ("CONNECTED • " + str(editor["path"])) if connected else ("NOT FOUND • install the '" + str(editor["command"]) + "' PATH command")
            command = (lambda item=editor: self._open_external_editor(item)) if connected else (lambda: None)
            card = self._card(grid, str(editor["name"]), text, "Open workspace" if connected else "Not connected",
                              command, "#44a36f" if connected else "#52697b")
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=7, pady=7)

    def _open_external_editor(self, editor: dict[str, object]):
        target = self.current_project or self.file_service.root
        try:
            subprocess.Popen([str(editor["path"]), str(target)])
            self.settings["editor"] = str(editor["name"])
            self.settings_store.save(self.settings)
            self._set_status(f"Opened {target} in {editor['name']}")
        except OSError as exc:
            self.messagebox.showerror("Could not open editor", str(exc))

    def show_settings(self):
        self._clear()
        self._page_head("Settings", "Configure your workspace, preferred connected editor, Code Studio size, and autosave behavior.")
        form = self.tk.Frame(self.content, bg=self.PANEL, padx=26, pady=26)
        form.pack(fill="x", padx=32)
        workspace = self.tk.StringVar(value=str(self.settings["workspace"]))
        editor = self.tk.StringVar(value=str(self.settings["editor"]))
        font_size = self.tk.StringVar(value=str(self.settings["font_size"]))
        autosave = self.tk.BooleanVar(value=bool(self.settings["autosave"]))
        self.tk.Label(form, text="Workspace folder", bg=self.PANEL, fg=self.TEXT).grid(row=0, column=0, sticky="w", pady=9)
        workspace_entry = self.tk.Entry(form, textvariable=workspace, bg="#0f1b26", fg=self.TEXT,
                                        insertbackground=self.YELLOW, relief="flat", font=("Segoe UI", 10))
        workspace_entry.grid(row=0, column=1, sticky="ew", padx=12, ipady=8)
        self.ttk.Button(form, text="Browse", style="Dark.TButton",
                        command=lambda: self._browse_variable(workspace)).grid(row=0, column=2)
        self.tk.Label(form, text="Preferred editor", bg=self.PANEL, fg=self.TEXT).grid(row=1, column=0, sticky="w", pady=9)
        editor_box = self.ttk.Combobox(form, textvariable=editor, state="readonly",
                                       values=["Auto detect"] + list(EDITOR_COMMANDS), font=("Segoe UI", 10))
        editor_box.grid(row=1, column=1, sticky="ew", padx=12)
        self.tk.Label(form, text="Code font size", bg=self.PANEL, fg=self.TEXT).grid(row=2, column=0, sticky="w", pady=9)
        size_box = self.ttk.Combobox(form, textvariable=font_size, state="readonly",
                                     values=[str(value) for value in range(9, 21)], width=8)
        size_box.grid(row=2, column=1, sticky="w", padx=12)
        self.tk.Checkbutton(form, text="Autosave the current file before Run", variable=autosave,
                            bg=self.PANEL, fg=self.TEXT, selectcolor="#0f1b26", activebackground=self.PANEL,
                            activeforeground=self.TEXT).grid(row=3, column=1, sticky="w", padx=12, pady=9)
        form.columnconfigure(1, weight=1)
        self.ttk.Button(form, text="Save Settings", style="Accent.TButton",
                        command=lambda: self._save_settings(workspace.get(), editor.get(), font_size.get(), autosave.get())).grid(row=4, column=1, sticky="w", padx=12, pady=(18, 0))
        self.tk.Label(self.content, text="Settings are stored locally in ~/.pythonv2/settings.json. No account, cloud sync, telemetry, or credentials are used.",
                      bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10), wraplength=780,
                      justify="left").pack(anchor="w", padx=32, pady=18)

    def _browse_variable(self, variable):
        chosen = self.filedialog.askdirectory(title="Choose Python v2 workspace")
        if chosen:
            variable.set(chosen)

    def _save_settings(self, workspace: str, editor: str, font_size: str, autosave: bool):
        try:
            size = int(font_size)
            if not 9 <= size <= 20:
                raise ValueError("font size must be between 9 and 20")
            service = WorkspaceFileService(workspace)
            self.settings.update({"workspace": str(service.root), "editor": editor,
                                  "font_size": size, "autosave": bool(autosave)})
            self.settings_store.save(self.settings)
            self.file_service = service
            self._set_status("Settings saved")
            self.messagebox.showinfo("Settings saved", "Workspace settings were saved locally.")
        except Exception as exc:
            self.messagebox.showerror("Could not save settings", str(exc))

    def show_projects(self):
        self._clear()
        self._page_head("New Project", "Start a website, command-line app, or Python v2 game. Existing files are never overwritten.")
        form = self.tk.Frame(self.content, bg=self.PANEL, padx=24, pady=24)
        form.pack(fill="x", padx=32)
        self.tk.Label(form, text="Project name", bg=self.PANEL, fg=self.TEXT).grid(row=0, column=0, sticky="w", pady=7)
        name = self.tk.Entry(form, bg="#0f1b26", fg=self.TEXT, insertbackground=self.YELLOW, relief="flat", font=("Segoe UI", 11))
        name.insert(0, "My Python v2 Project")
        name.grid(row=0, column=1, sticky="ew", padx=12, pady=7, ipady=8)
        self.tk.Label(form, text="Location", bg=self.PANEL, fg=self.TEXT).grid(row=1, column=0, sticky="w", pady=7)
        location = self.tk.Entry(form, bg="#0f1b26", fg=self.TEXT, insertbackground=self.YELLOW, relief="flat", font=("Segoe UI", 11))
        location.insert(0, str(Path.home() / "PythonV2Projects"))
        location.grid(row=1, column=1, sticky="ew", padx=12, pady=7, ipady=8)
        self.ttk.Button(form, text="Browse", style="Dark.TButton",
                        command=lambda: self._browse_into(location)).grid(row=1, column=2)
        self.tk.Label(form, text="Project type", bg=self.PANEL, fg=self.TEXT).grid(row=2, column=0, sticky="w", pady=7)
        kind = self.ttk.Combobox(form, state="readonly", values=["Website", "CLI app", "Game"], font=("Segoe UI", 10))
        kind.set("Website")
        kind.grid(row=2, column=1, sticky="ew", padx=12, pady=7)
        form.columnconfigure(1, weight=1)
        self.ttk.Button(form, text="Create Project", style="Accent.TButton",
                        command=lambda: self._create_from_form(location.get(), name.get(), kind.get())).grid(row=3, column=1, sticky="w", padx=12, pady=(18, 0))
        self.ttk.Button(form, text="Open current project in VS Code", style="Dark.TButton",
                        command=self.open_in_vscode).grid(row=3, column=2, sticky="w", pady=(18, 0))
        info = self.tk.Frame(self.content, bg=self.BG)
        info.pack(fill="x", padx=32, pady=22)
        descriptions = [
            ("Website", "app.pyv2 generates the page content. Includes the browser runtime and a local preview."),
            ("CLI app", "A clean main.pyv2 starter that runs with pyv2 main.pyv2."),
            ("Game", "A complete terminal battle game ready to expand with PyHope sprites and maps."),
        ]
        for i, (title, text) in enumerate(descriptions):
            card = self._card(info, title, text, "Choose " + title, lambda value=title: kind.set(value), [self.BLUE, self.RED, "#44a36f"][i])
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0 if i == 2 else 6))

    def _browse_into(self, entry):
        chosen = self.filedialog.askdirectory(title="Choose project folder")
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, chosen)

    def _create_from_form(self, location, name, label):
        kind = {"Website": "website", "CLI app": "cli", "Game": "game"}.get(label, "website")
        try:
            project = create_project(location, name, kind)
        except Exception as exc:
            self.messagebox.showerror("Could not create project", str(exc))
            return
        self.current_project = project
        candidate = project / ("app.pyv2" if kind == "website" else "game.pyv2" if kind == "game" else "main.pyv2")
        self.current_file = candidate
        self._set_status("Created " + str(project))
        if kind == "website":
            if self.messagebox.askyesno("Website created", "Open a local preview now?"):
                self.preview_website(project)
        else:
            self.show_editor()

    def open_in_vscode(self):
        project = self.current_project
        if not project:
            chosen = self.filedialog.askdirectory(title="Choose a project to open in VS Code")
            if not chosen:
                return
            project = Path(chosen)
        code = shutil.which("code")
        if not code:
            self.messagebox.showinfo(
                "VS Code command not found",
                "Install VS Code's 'code' command in PATH, then try again.\n\n"
                "The project already contains .vscode tasks and settings."
            )
            return
        subprocess.Popen([code, str(project)])
        self._set_status("Opened in VS Code: " + str(project))

    def preview_website(self, project: Path | None = None):
        project = Path(project or self.current_project or "")
        if not project or not (project / "index.html").exists():
            chosen = self.filedialog.askdirectory(title="Choose a Python v2 website project")
            if not chosen:
                return
            project = Path(chosen)
        handler = partial(SimpleHTTPRequestHandler, directory=str(project))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/"
        webbrowser.open(url)
        self._set_status("Previewing " + str(project) + " at " + url)

    def show_games(self):
        self._clear()
        self._page_head("10 Games & GPU", "Play four shooters, two platformers, two racers, Snake Byte, Orb Breaker, and the opt-in 9,437,184-pixel GPU lab.")
        grid = self.tk.Frame(self.content, bg=self.BG)
        grid.pack(fill="both", expand=True, padx=32)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)
        games = [
            ("Byte Beast Arena", "CPU raycaster with CC0 monsters, blaster, HP, kills, fog and mini-map.", "Play arena", GAMES_URL + "#byte-beast", self.RED),
            ("Comet Hopper", "Original platform game. Python v2 generates the level; PyHope renders it.", "Play platformer", GAMES_URL + "#comet-hopper", self.BLUE),
            ("Comet Circuit", "Top-down racing with a Python v2 track, AI drivers, road grip, laps and best times.", "Race now", GAMES_URL + "#comet-circuit", "#8f2c52"),
            ("Pocket Arcade", "Seven more games: Neon Blaster, Asteroid Drift, Target Blitz, Skybound, Turbo Trail, Snake Byte and Orb Breaker.", "Choose a game", GAMES_URL + "#pocket-arcade", "#7655b7"),
            ("9M GPU Lab", "4096×2304 = 9,437,184 real shader pixels. GPU memory is used efficiently; RAM is still required.", "Open GPU lab", GAMES_URL + "#gpu", "#44a36f"),
            ("Free Sprite Pack", "Original public-domain hero, monsters, weapon and coin. Safe to remix and publish.", "Browse sprites", GAMES_URL + "#sprites", self.YELLOW),
        ]
        for i, (title, text, button, url, color) in enumerate(games):
            card = self._card(grid, title, text, button, lambda target=url: webbrowser.open(target), color)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=7, pady=7)

    def show_docs(self):
        self._clear()
        self._page_head("Docs & Learning", "Everything from your first print to closures, websites, PyHope sprites, DDA rays and GPU rendering.")
        grid = self.tk.Frame(self.content, bg=self.BG)
        grid.pack(fill="both", expand=True, padx=32)
        links = [
            ("Dual-runtime Playground", "Run Python v2 or Classic compatibility with commands and an error terminal.", "Open Playground", PLAYGROUND_URL, self.YELLOW),
            ("10-lesson Tutorial", "Runnable examples in the browser.", "Start tutorial", SITE_URL + "tutorial.html", self.BLUE),
            ("50-topic Field Guide", "Searchable language and engine recipes.", "Read 50 guides", GUIDE_URL, self.RED),
            ("Language Reference", "Syntax, semantics, builtins and editor setup.", "Open docs", DOCS_URL, "#44a36f"),
            ("Install Video at 1K", "Subscribe to Cube Comet. Full install walkthrough releases at 1,000 subscribers.", "Subscribe", YOUTUBE_URL, "#ff0033"),
        ]
        for i, (title, text, button, url, color) in enumerate(links):
            card = self._card(grid, title, text, button, lambda target=url: webbrowser.open(target), color)
            card.pack(fill="x", pady=7)

    def _set_status(self, text):
        self.status.configure(text=text)

    def close(self):
        for server in self.servers:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        self.root.destroy()


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError:
        print("Python v2 Launcher needs tkinter (usually packaged with Python).", file=sys.stderr)
        print("Language and PyHope CLIs still work: pyv2 / pyhope --demo", file=sys.stderr)
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Python v2 Launcher could not open a desktop window: {exc}", file=sys.stderr)
        return 1
    Launcher(root, tk, ttk, (filedialog, messagebox, simpledialog))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
