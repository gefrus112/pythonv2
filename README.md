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

`site/` is the home website — a modern re-imagining of python.org with:

* a **runnable playground** at the top of the page (the real interpreter,
  `site/pyv2.js`, running in your browser — press ▶ Run)
* a **CPU-rendered game**: a software raycaster that computes all
  57,600 pixels per frame on the CPU into a plain framebuffer —
  no WebGL, no shaders, no GPU calls
* the custom **hexagon prompt icon** (`site/logo.svg`, `site/favicon.svg`)

Serve it locally:

```console
$ python3 -m http.server 8000 --directory site
# → http://localhost:8000
```

## 🧪 Tests

```console
$ python3 -m unittest discover -s tests -t .
```

62 tests: 61 unit tests over the reference interpreter **plus** a parity
suite that runs 20 programs (including error paths) through both the Python
and JavaScript runtimes and demands byte-identical output.

## 📦 Repo layout

```
pyv2/            reference interpreter (lexer, parser, tree-walking VM, CLI)
site/            home website: playground, CPU raycaster, logo & favicon
  pyv2.js        the twin runtime in JavaScript
  game.js        software raycaster (pure CPU rendering)
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
