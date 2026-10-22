"""Python v2 — a programming language that lets you work quickly.

Python v2 is a from-scratch remake of Python that keeps everything great
(f-strings, for-loops, lists, maps) and fixes the rest (no more indentation
errors, real closures, `fn`/`end` blocks, a `?:` ternary).
"""

from .interpreter import Interpreter, Pyv2Error, run, run_capture
from .parser import parse, ParseError

__version__ = "0.2.0"
__all__ = ["Interpreter", "Pyv2Error", "run", "run_capture", "parse",
           "ParseError", "__version__"]
