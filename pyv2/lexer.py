"""Lexer for Python v2 (.pyv2) source code."""

from __future__ import annotations

from dataclasses import dataclass

KEYWORDS = {
    "fn", "if", "elif", "else", "while", "for", "in",
    "return", "break", "continue", "and", "or", "not",
    "true", "false", "nil", "end",
}

# Longest-first so "**" beats "*", "//" beats "/", etc.
OPERATORS = [
    "**", "//", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
    "->", "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]",
    "{", "}", ",", ":", ".", "?",
]


@dataclass
class Token:
    type: str   # NUMBER, STRING, FSTRING, IDENT, KEYWORD, OP, NEWLINE, EOF
    value: object
    line: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.type}, {self.value!r}, line={self.line})"


class LexError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.message = message
        self.line = line


class Lexer:
    def __init__(self, source: str):
        self.src = source.replace("\r\n", "\n").replace("\r", "\n")
        self.pos = 0
        self.line = 1
        self.n = len(self.src)

    # ---------- helpers ----------
    def _peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.src[i] if i < self.n else ""

    def _advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        return ch

    def _skip_trivia(self) -> None:
        """Skip spaces, tabs and comments. Newlines are significant."""
        while self.pos < self.n:
            ch = self._peek()
            if ch in " \t":
                self.pos += 1
            elif ch == "#":
                while self.pos < self.n and self._peek() != "\n":
                    self.pos += 1
            else:
                break

    # ---------- string scanning ----------
    def _read_string(self, quote: str, is_fstring: bool, line: int) -> str:
        """Read the raw body of a string literal (quotes excluded)."""
        body = []
        while True:
            if self.pos >= self.n:
                raise LexError("Unterminated string literal", line)
            ch = self._advance()
            if ch == "\n":
                raise LexError("Unterminated string literal (newline in string)", line)
            if ch == "\\":
                if self.pos >= self.n:
                    raise LexError("Unterminated string literal", line)
                esc = self._advance()
                mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                           "'": "'", '"': '"', "0": "\0"}
                if esc == "u":
                    hexpart = ""
                    while len(hexpart) < 4 and self.pos < self.n:
                        hexpart += self._advance()
                    try:
                        body.append(chr(int(hexpart, 16)))
                    except ValueError:
                        raise LexError(f"Invalid unicode escape \\u{hexpart}", line)
                elif esc in mapping:
                    body.append(mapping[esc])
                else:
                    raise LexError(f"Unknown escape sequence \\{esc}", line)
                continue
            if ch == quote:
                return "".join(body)
            body.append(ch)

    # ---------- main ----------
    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_trivia()
            if self.pos >= self.n:
                break
            ch = self._peek()
            line = self.line

            if ch == "\n":
                self._advance()
                self.line += 1
                if tokens and tokens[-1].type != "NEWLINE":
                    tokens.append(Token("NEWLINE", "\n", line))
                continue

            # f-strings
            if ch in "fF" and self._peek(1) in "\"'":
                self._advance()
                quote = self._advance()
                raw = self._read_string(quote, True, line)
                tokens.append(Token("FSTRING", raw, line))
                continue

            # strings
            if ch in "\"'":
                self._advance()
                raw = self._read_string(ch, False, line)
                tokens.append(Token("STRING", raw, line))
                continue

            # numbers
            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                start = self.pos
                while self.pos < self.n and (self._peek().isdigit() or self._peek() == "."):
                    self._advance()
                if self.pos < self.n and self._peek() in "eE":
                    nxt = self._peek(1)
                    if nxt.isdigit() or (nxt in "+-" and self._peek(2).isdigit()):
                        self._advance()  # e/E
                        if self._peek() in "+-":
                            self._advance()
                        while self.pos < self.n and self._peek().isdigit():
                            self._advance()
                text = self.src[start:self.pos]
                try:
                    value: object = int(text) if ("." not in text and "e" not in text and "E" not in text) else float(text)
                except ValueError:
                    raise LexError(f"Invalid number literal '{text}'", line)
                tokens.append(Token("NUMBER", value, line))
                continue

            # identifiers / keywords
            if ch.isalpha() or ch == "_":
                start = self.pos
                while self.pos < self.n and (self._peek().isalnum() or self._peek() == "_"):
                    self._advance()
                word = self.src[start:self.pos]
                if word in KEYWORDS:
                    tokens.append(Token("KEYWORD", word, line))
                else:
                    tokens.append(Token("IDENT", word, line))
                continue

            # operators
            for op in OPERATORS:
                if self.src.startswith(op, self.pos):
                    self.pos += len(op)
                    tokens.append(Token("OP", op, line))
                    break
            else:
                raise LexError(f"Unexpected character {ch!r}", line)

        if tokens and tokens[-1].type != "NEWLINE":
            tokens.append(Token("NEWLINE", "\n", self.line))
        tokens.append(Token("EOF", None, self.line))
        return tokens


def tokenize(source: str) -> list[Token]:
    return Lexer(source).tokenize()
