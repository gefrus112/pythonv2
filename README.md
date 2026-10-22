# Python v2 🐍→🐍²

**I remade Python, but better.**

Python v2 is a programming language that lets you work quickly and integrate
systems more effectively — same energy as the original snake, without the
paper cuts. No indentation errors. Real closures. F-strings that just work.
A ternary that reads left to right. And it runs **right in your browser**.

```python
# hello.pyv2
fn greet(name):
    if name == "":
        return "Hello, stranger!"
    end
    return f"Hello, {name}!"
end

numbers = [2, 4, 6, 8]
product = 1
for number in numbers:
    product = product * number
end

print(greet("World"))
print(f"The product is: {product}")
```

```console
$ python3 -m pyv2 hello.pyv2
Hello, World!
The product is: 384
```

## ✨ What makes it better

| Old Python | Python v2 |
|---|---|
| `def foo():` + invisible whitespace | `fn foo():` … `end` |
| `TabError: inconsistent use of tabs and spaces` | No such thing. Ever. |
| `nonlocal` scavenger hunts | closures just work |
| `"n=" + str(n)` | `"n=" + n` |
| `x if ok else y` (backwards) | `ok ? x : y` |
| `assert` is a keyword with moods | `assert(cond, msg)` is a function |
| trailing commas *sometimes* | trailing commas & multi-line everything |
| one runtime | two parity-tested runtimes — CLI **and** browser |

## 🚀 Quick start

```console
$ git clone https://github.com/gefrus112/pythonv2
$ cd pythonv2

# run a program
$ python3 -m pyv2 examples/fib.pyv2

# drop into the REPL
$ python3 -m pyv2

# run the terminal raycaster (yes, really)
$ python3 -m pyv2 examples/terminal_raycast.pyv2
```

No dependencies. No install step. Python 3.10+ for the reference runtime.

## 🌐 The website

The website lives at the **repo root** (so GitHub Pages serves it directly
at [gefrus112.github.io/pythonv2](https://gefrus112.github.io/pythonv2/)) —
styled after python.org, then pushed further:

* a **runnable playground** in the hero (the real interpreter,
  `pyv2.js`, running in your browser — press the yellow `>_` badge)
* a **Downloads page** (`download.html`) — install the language on
  macOS / Linux / Windows / any editor
* a **tutorial** (`tutorial.html`) — 10 runnable lessons, sandbox included
* a **CPU-rendered game**: a software raycaster that computes all
  57,600 pixels per frame on the CPU into a plain framebuffer —
  no WebGL, no shaders, no GPU calls
* the custom **two-snake icon** (`logo.svg`, `favicon.svg`) —
  one red snake, one blue snake, interlocked
* a full **documentation site** (`docs.html`) with install guides for
  every setup

Serve it locally:

```console
$ python3 -m http.server 8000
# → http://localhost:8000
```

**GitHub Pages** serves the same files from the repo root — push to `main`
and the live site updates at https://gefrus112.github.io/pythonv2/

## 🧑‍💻 Editor setup

Full guides live in [`docs.html`](docs.html) and [`download.html`](download.html) — VS Code, dev
containers / GitHub Codespaces, desktop terminals, and any other editor.
The short version:

| Where | How |
|---|---|
| **Desktop** | `python3 -m pyv2 file.pyv2` — nothing to install |
| **VS Code** | open the repo, hit `Ctrl+Shift+B`; syntax highlighting from `editors/vscode` |
| **Dev containers / Codespaces** | open in container via `.devcontainer/devcontainer.json` — everything preinstalled |
| **Any editor** | associate `*.pyv2`, run `python3 -m pyv2 $file` |

## 🧪 Tests

```console
$ python3 -m unittest discover -s tests -t .
```

64 tests: 63 unit tests over the reference interpreter **plus** a parity
suite that runs 20 programs (including error paths) through both the Python
and JavaScript runtimes and demands byte-identical output.

## 📦 Repo layout

```
pyv2/            reference interpreter (lexer, parser, tree-walking VM, CLI)
index.html       home website (GitHub Pages serves this) — playground, CPU raycaster
download.html    install the language: desktop, VS Code, dev containers, any editor
docs.html        documentation: install guides + language quick reference
tutorial.html    the tutorial: 10 runnable lessons + browser sandbox
pyv2.js          the twin runtime in JavaScript (playground + tutorial)
game.js          software raycaster (pure CPU rendering)
logo.svg         the two-snake icon (red & blue) — favicon.svg too
editors/vscode/  VS Code extension: .pyv2 syntax highlighting + snippets
.vscode/         tasks to run / test .pyv2 files with Ctrl+Shift+B
.devcontainer/   dev container + Codespaces config
examples/        hello, fib, fizzbuzz, terminal_raycast
tests/           unit tests + cross-runtime parity harness
docs/LANGUAGE.md full language reference & grammar
```

## 📖 Docs

The full language reference lives at
[docs/LANGUAGE.md](docs/LANGUAGE.md) — values, operators, scope rules,
builtins, methods, error kinds and the EBNF grammar. Spoiler: it fits on
one page, because the language was designed to.

## 📜 License

MIT — see [LICENSE](LICENSE). Not affiliated with the PSF (yet).
Made with stubborn optimism and zero GPU calls.
