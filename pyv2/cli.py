"""Command line interface: python3 -m pyv2 [file | -c code]."""

from __future__ import annotations

import sys

from . import __version__
from .interpreter import Interpreter, Pyv2Error
from .parser import ParseError


BANNER = f"""Python v2 {__version__} (the snake, but better)
Type Py v2 code, then press Ctrl-D to run... no — every line runs immediately.
Builtins: print, len, range, str, int, float, list/map methods, f-strings.
"""

WELCOME = f"Python v2 {__version__} — type away, end blocks with 'end'. Ctrl-D to quit."


def _read_input(prompt: str = "") -> str:
    return input(prompt)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--version" in argv or "-V" in argv:
        print(f"Python v2 {__version__}")
        return 0

    if "--help" in argv or "-h" in argv:
        print("usage: python3 -m pyv2 [options] [script.pyv2]")
        print("       python3 -m pyv2 -c 'code'")
        print("       python3 -m pyv2            # start the REPL")
        print("options:")
        print("  -c CODE   run CODE and exit")
        print("  -V        print version")
        print("  -h        show this help")
        return 0

    if argv and argv[0] == "-c":
        source = argv[1] if len(argv) > 1 else ""
        return run_source(source, "<string>")

    if argv:
        path = argv[0]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                source = fh.read()
        except OSError as exc:
            print(f"pyv2: cannot open {path!r}: {exc.strerror}", file=sys.stderr)
            return 1
        return run_source(source, path)

    return repl()


def run_source(source: str, name: str) -> int:
    interp = Interpreter(output=_write, read_input=_read_input)
    try:
        interp.run(source)
        return 0
    except ParseError as exc:
        print(f"SyntaxError: {exc.message} at line {exc.line} ({name})",
              file=sys.stderr)
        return 1
    except Pyv2Error as exc:
        print(exc.format(), file=sys.stderr)
        return 1
    except RecursionError:
        print("RuntimeError: maximum recursion depth exceeded", file=sys.stderr)
        return 1


def repl() -> int:
    print(WELCOME)
    interp = Interpreter(output=_write, read_input=_read_input)
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
        # Keep reading while blocks are open (unbalanced 'end' count).
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
    return 0


def _open_blocks(source: str) -> int:
    """Rough count of open blocks for REPL continuation prompts."""
    from .lexer import tokenize, LexError
    try:
        tokens = tokenize(source + "\n")
    except LexError:
        return 0
    depth = 0
    for tok in tokens:
        if tok.type == "KEYWORD" and tok.value in ("if", "while", "for"):
            depth += 1
        elif tok.type == "KEYWORD" and tok.value == "fn":
            depth += 1
        elif tok.type == "KEYWORD" and tok.value == "end":
            depth -= 1
    return max(0, depth)


def _write(text: str) -> None:
    print(text)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
