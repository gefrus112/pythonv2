"""Recursive-descent parser for Python v2.

Grammar (informal):
    program    := stmt*
    stmt       := simple | compound
    simple     := 'return' expr? | 'raise' expr | 'break' | 'continue' | assign | expr
    compound   := if | while | for | fn | try
    if         := 'if' expr ':' block ('elif' expr ':' block)* ('else' ':' block)? 'end'
    while      := 'while' expr ':' block 'end'
    for        := 'for' IDENT 'in' expr ':' block 'end'
    fn         := 'fn' IDENT '(' params ')' ':' block 'end'
    try        := 'try' ':' block ('catch' IDENT? ':' block)? ('finally' ':' block)? 'end'
    block      := stmt* until its compound terminator
    assign     := target ('=' | '+=' | '-=' | '*=' | '/=' | '%=') expr
    ternary    := or ('?' ternary ':' ternary)?
    or         := and ('or' and)*
    and        := not_ ('and' not_)*
    not_       := 'not' not_ | comparison
    comparison := add (('=='|'!='|'<'|'<='|'>'|'>='|'in') add)*
    add        := mul (('+'|'-') mul)*
    mul        := unary (('*'|'/'|'//'|'%') unary)*
    unary      := ('-'|'+') unary | power
    power      := postfix ('**' unary)?
    postfix    := primary ( '(' args ')' | '[' expr ']' | '.' IDENT )*
    primary    := NUMBER | STRING | FSTRING | 'true' | 'false' | 'nil'
                | IDENT | '(' ternary ')' | list | map | fnexpr
"""

from __future__ import annotations

from .lexer import Token, tokenize, LexError


class ParseError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.message = message
        self.line = line


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ---------- token helpers ----------
    def peek(self, offset: int = 0) -> Token:
        i = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[i]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != "EOF":
            self.pos += 1
        return tok

    def check(self, type_: str, value=None) -> bool:
        tok = self.peek()
        if tok.type != type_:
            return False
        return value is None or tok.value == value

    def match(self, type_: str, value=None) -> bool:
        if self.check(type_, value):
            self.advance()
            return True
        return False

    def expect(self, type_: str, value=None, what: str = "") -> Token:
        if self.check(type_, value):
            return self.advance()
        tok = self.peek()
        want = what or (value if value is not None else type_)
        got = tok.value if tok.type != "NEWLINE" else "end of line"
        if tok.type == "EOF":
            got = "end of file"
        raise ParseError(f"Expected {want!r} but found {got!r}", tok.line)

    def skip_newlines(self) -> None:
        while self.check("NEWLINE"):
            self.advance()

    # ---------- program ----------
    def parse_program(self) -> dict:
        body = self.parse_block_until(set())
        return {"t": "program", "body": body}

    def parse_block_until(self, stops: set) -> list[dict]:
        """Parse statements until a stop keyword (not consumed) or EOF."""
        body: list[dict] = []
        while True:
            self.skip_newlines()
            tok = self.peek()
            if tok.type == "EOF":
                break
            if tok.type == "KEYWORD" and tok.value in stops:
                break
            body.append(self.parse_stmt())
        return body

    # ---------- statements ----------
    def parse_stmt(self) -> dict:
        tok = self.peek()
        if tok.type == "KEYWORD":
            if tok.value == "if":
                return self.parse_if()
            if tok.value == "while":
                return self.parse_while()
            if tok.value == "for":
                return self.parse_for()
            if tok.value == "try":
                return self.parse_try()
            if tok.value == "fn":
                # fn name(...) is a statement; bare fn(...) is an expression.
                if self.peek(1).type == "IDENT":
                    return self.parse_fn()
            if tok.value == "return":
                self.advance()
                value = None
                if not (self.check("NEWLINE") or self.check("KEYWORD", "end")
                        or self.check("KEYWORD", "elif") or self.check("KEYWORD", "else")
                        or self.check("KEYWORD", "catch") or self.check("KEYWORD", "finally")
                        or self.check("EOF")):
                    value = self.parse_ternary()
                self.end_simple()
                return {"t": "return", "value": value, "line": tok.line}
            if tok.value == "raise":
                self.advance()
                if self.check("NEWLINE") or self.check("EOF"):
                    raise ParseError("raise needs an error value", tok.line)
                value = self.parse_ternary()
                self.end_simple()
                return {"t": "raise", "value": value, "line": tok.line}
            if tok.value == "break":
                self.advance()
                self.end_simple()
                return {"t": "break", "line": tok.line}
            if tok.value == "continue":
                self.advance()
                self.end_simple()
                return {"t": "continue", "line": tok.line}
            raise ParseError(f"Unexpected keyword {tok.value!r}", tok.line)

        expr = self.parse_ternary()
        tok = self.peek()
        if tok.type == "OP" and tok.value in ("=", "+=", "-=", "*=", "/=", "%="):
            if expr["t"] not in ("var", "index", "attr"):
                raise ParseError("Invalid assignment target", tok.line)
            self.advance()
            value = self.parse_ternary()
            self.end_simple()
            return {"t": "assign", "target": expr, "value": value,
                    "op": tok.value, "line": tok.line}
        self.end_simple()
        return {"t": "exprstmt", "expr": expr, "line": tok.line}

    def end_simple(self) -> None:
        if self.check("NEWLINE"):
            self.advance()
        elif self.check("EOF") or self.check("KEYWORD", "end") \
                or self.check("KEYWORD", "elif") or self.check("KEYWORD", "else") \
                or self.check("KEYWORD", "catch") or self.check("KEYWORD", "finally"):
            return
        else:
            tok = self.peek()
            raise ParseError(f"Unexpected {tok.value!r} after statement", tok.line)

    def end_compound(self) -> None:
        """After a block's 'end': consume a newline if present, else let the
        next statement start on the same line."""
        if self.check("NEWLINE"):
            self.advance()

    def parse_block(self, stops: set) -> list[dict]:
        """After ':' — optional newline, then statements until a stop keyword."""
        self.expect("OP", ":")
        self.skip_newlines()
        return self.parse_block_until(stops | {"end"})

    def parse_if(self) -> dict:
        line = self.advance().line  # 'if'
        arms = []
        cond = self.parse_ternary()
        body = self.parse_block({"elif", "else"})
        arms.append({"cond": cond, "body": body})
        else_body = None
        while self.check("KEYWORD", "elif"):
            self.advance()
            cond = self.parse_ternary()
            body = self.parse_block({"elif", "else"})
            arms.append({"cond": cond, "body": body})
        if self.check("KEYWORD", "else"):
            self.advance()
            else_body = self.parse_block(set())
        self.expect("KEYWORD", "end")
        self.end_compound()
        return {"t": "if", "arms": arms, "else": else_body, "line": line}

    def parse_while(self) -> dict:
        line = self.advance().line  # 'while'
        cond = self.parse_ternary()
        body = self.parse_block(set())
        self.expect("KEYWORD", "end")
        self.end_compound()
        return {"t": "while", "cond": cond, "body": body, "line": line}

    def parse_for(self) -> dict:
        line = self.advance().line  # 'for'
        name = self.expect("IDENT", what="loop variable").value
        self.expect("KEYWORD", "in")
        iterable = self.parse_ternary()
        body = self.parse_block(set())
        self.expect("KEYWORD", "end")
        self.end_compound()
        return {"t": "for", "name": name, "iter": iterable, "body": body, "line": line}

    def parse_try(self) -> dict:
        line = self.advance().line  # 'try'
        body = self.parse_block({"catch", "finally"})
        catch_name = None
        catch_body = None
        finally_body = None
        if self.check("KEYWORD", "catch"):
            self.advance()
            if self.check("IDENT"):
                catch_name = self.advance().value
            catch_body = self.parse_block({"finally"})
        if self.check("KEYWORD", "finally"):
            self.advance()
            finally_body = self.parse_block(set())
        if catch_body is None and finally_body is None:
            raise ParseError("try needs a catch or finally block", line)
        self.expect("KEYWORD", "end")
        self.end_compound()
        return {"t": "try", "body": body, "catch_name": catch_name,
                "catch": catch_body, "finally": finally_body, "line": line}

    def parse_fn(self) -> dict:
        line = self.advance().line  # 'fn'
        name = self.expect("IDENT", what="function name").value
        params = self.parse_params()
        body = self.parse_block(set())
        self.expect("KEYWORD", "end")
        self.end_compound()
        return {"t": "fn", "name": name, "params": params, "body": body, "line": line}

    def parse_params(self) -> list[str]:
        self.expect("OP", "(")
        self.skip_newlines()
        params: list[str] = []
        if not self.check("OP", ")"):
            while True:
                params.append(self.expect("IDENT", what="parameter name").value)
                if not self.match("OP", ","):
                    break
                self.skip_newlines()
                if self.check("OP", ")"):  # trailing comma
                    break
        self.skip_newlines()
        self.expect("OP", ")")
        return params

    # ---------- expressions ----------
    def parse_ternary(self) -> dict:
        cond = self.parse_or()
        if self.check("OP", "?"):
            self.advance()
            then = self.parse_ternary()
            self.expect("OP", ":")
            other = self.parse_ternary()
            return {"t": "ternary", "cond": cond, "then": then, "else": other}
        return cond

    def parse_or(self) -> dict:
        left = self.parse_and()
        while self.check("KEYWORD", "or"):
            line = self.advance().line
            right = self.parse_and()
            left = {"t": "bin", "op": "or", "l": left, "r": right, "line": line}
        return left

    def parse_and(self) -> dict:
        left = self.parse_not()
        while self.check("KEYWORD", "and"):
            line = self.advance().line
            right = self.parse_not()
            left = {"t": "bin", "op": "and", "l": left, "r": right, "line": line}
        return left

    def parse_not(self) -> dict:
        if self.check("KEYWORD", "not"):
            line = self.advance().line
            e = self.parse_not()
            return {"t": "un", "op": "not", "e": e, "line": line}
        return self.parse_comparison()

    def parse_comparison(self) -> dict:
        left = self.parse_add()
        while True:
            tok = self.peek()
            if tok.type == "OP" and tok.value in ("==", "!=", "<", "<=", ">", ">="):
                self.advance()
                right = self.parse_add()
                left = {"t": "bin", "op": tok.value, "l": left, "r": right, "line": tok.line}
            elif tok.type == "KEYWORD" and tok.value == "in":
                self.advance()
                right = self.parse_add()
                left = {"t": "bin", "op": "in", "l": left, "r": right, "line": tok.line}
            else:
                return left

    def parse_add(self) -> dict:
        left = self.parse_mul()
        while self.check("OP", "+") or self.check("OP", "-"):
            tok = self.advance()
            right = self.parse_mul()
            left = {"t": "bin", "op": tok.value, "l": left, "r": right, "line": tok.line}
        return left

    def parse_mul(self) -> dict:
        left = self.parse_unary()
        while self.check("OP", "*") or self.check("OP", "/") \
                or self.check("OP", "//") or self.check("OP", "%"):
            tok = self.advance()
            right = self.parse_unary()
            left = {"t": "bin", "op": tok.value, "l": left, "r": right, "line": tok.line}
        return left

    def parse_unary(self) -> dict:
        tok = self.peek()
        if tok.type == "OP" and tok.value in ("-", "+"):
            self.advance()
            e = self.parse_unary()
            return {"t": "un", "op": tok.value, "e": e, "line": tok.line}
        return self.parse_power()

    def parse_power(self) -> dict:
        base = self.parse_postfix()
        if self.check("OP", "**"):
            tok = self.advance()
            exp = self.parse_unary()  # right associative
            return {"t": "bin", "op": "**", "l": base, "r": exp, "line": tok.line}
        return base

    def parse_postfix(self) -> dict:
        e = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.type == "OP" and tok.value == "(":
                self.advance()
                self.skip_newlines()
                args = []
                if not self.check("OP", ")"):
                    while True:
                        args.append(self.parse_ternary())
                        if not self.match("OP", ","):
                            break
                        self.skip_newlines()
                        if self.check("OP", ")"):  # trailing comma
                            break
                self.skip_newlines()
                self.expect("OP", ")")
                e = {"t": "call", "callee": e, "args": args, "line": tok.line}
            elif tok.type == "OP" and tok.value == "[":
                self.advance()
                self.skip_newlines()
                idx = self.parse_ternary()
                self.skip_newlines()
                self.expect("OP", "]")
                e = {"t": "index", "obj": e, "idx": idx, "line": tok.line}
            elif tok.type == "OP" and tok.value == ".":
                self.advance()
                name = self.expect("IDENT", what="attribute name").value
                e = {"t": "attr", "obj": e, "name": name, "line": tok.line}
            else:
                return e

    def parse_primary(self) -> dict:
        tok = self.peek()
        if tok.type == "NUMBER":
            self.advance()
            return {"t": "num", "v": tok.value, "line": tok.line}
        if tok.type == "STRING":
            self.advance()
            return {"t": "str", "v": tok.value, "line": tok.line}
        if tok.type == "FSTRING":
            self.advance()
            return self.parse_fstring(str(tok.value), tok.line)
        if tok.type == "IDENT":
            self.advance()
            return {"t": "var", "name": tok.value, "line": tok.line}
        if tok.type == "KEYWORD":
            if tok.value == "true":
                self.advance()
                return {"t": "bool", "v": True, "line": tok.line}
            if tok.value == "false":
                self.advance()
                return {"t": "bool", "v": False, "line": tok.line}
            if tok.value == "nil":
                self.advance()
                return {"t": "nil", "line": tok.line}
            if tok.value == "fn":
                self.advance()
                params = self.parse_params()
                body = self.parse_block(set())
                self.expect("KEYWORD", "end")
                return {"t": "fnexpr", "params": params, "body": body, "line": tok.line}
        if tok.type == "OP":
            if tok.value == "(":
                self.advance()
                self.skip_newlines()
                e = self.parse_ternary()
                self.skip_newlines()
                self.expect("OP", ")")
                return e
            if tok.value == "[":
                self.advance()
                self.skip_newlines()
                items = []
                if not self.check("OP", "]"):
                    while True:
                        items.append(self.parse_ternary())
                        if not self.match("OP", ","):
                            break
                        self.skip_newlines()
                        if self.check("OP", "]"):  # trailing comma
                            break
                self.skip_newlines()
                self.expect("OP", "]")
                return {"t": "list", "items": items, "line": tok.line}
            if tok.value == "{":
                return self.parse_map()
        got = tok.value if tok.type != "NEWLINE" else "end of line"
        if tok.type == "EOF":
            got = "end of file"
        raise ParseError(f"Unexpected {got!r} in expression", tok.line)

    def parse_map(self) -> dict:
        tok = self.expect("OP", "{")
        self.skip_newlines()
        pairs = []
        if not self.check("OP", "}"):
            while True:
                # bare identifier key -> string key
                if self.check("IDENT") and self.peek(1).type == "OP" and self.peek(1).value == ":":
                    key = {"t": "str", "v": self.advance().value, "line": tok.line}
                    self.advance()  # ':'
                else:
                    key = self.parse_ternary()
                    self.expect("OP", ":")
                self.skip_newlines()
                value = self.parse_ternary()
                pairs.append((key, value))
                if not self.match("OP", ","):
                    break
                self.skip_newlines()
                if self.check("OP", "}"):  # trailing comma
                    break
        self.skip_newlines()
        self.expect("OP", "}")
        return {"t": "map", "pairs": pairs, "line": tok.line}

    # ---------- f-strings ----------
    def parse_fstring(self, raw: str, line: int) -> dict:
        parts = []
        buf = []
        i, n = 0, len(raw)
        while i < n:
            ch = raw[i]
            if ch == "{":
                if i + 1 < n and raw[i + 1] == "{":
                    buf.append("{")
                    i += 2
                    continue
                # find matching close brace with depth tracking
                depth = 1
                j = i + 1
                while j < n and depth > 0:
                    if raw[j] == "{":
                        depth += 1
                    elif raw[j] == "}":
                        depth -= 1
                    j += 1
                if depth != 0:
                    raise ParseError("Unmatched '{' in f-string", line)
                expr_src = raw[i + 1:j - 1]
                if not expr_src.strip():
                    raise ParseError("Empty expression in f-string", line)
                if buf:
                    parts.append({"t": "str", "v": "".join(buf), "line": line})
                    buf = []
                parts.append(self.parse_embedded(expr_src, line))
                i = j
                continue
            if ch == "}":
                if i + 1 < n and raw[i + 1] == "}":
                    buf.append("}")
                    i += 2
                    continue
                raise ParseError("Unmatched '}' in f-string", line)
            buf.append(ch)
            i += 1
        if buf:
            parts.append({"t": "str", "v": "".join(buf), "line": line})
        return {"t": "fstr", "parts": parts, "line": line}

    def parse_embedded(self, src: str, line: int) -> dict:
        try:
            sub = Parser(tokenize(src + "\n"))
            e = sub.parse_ternary()
            sub.skip_newlines()
            if not sub.check("EOF"):
                raise ParseError(f"Trailing input in f-string expression {{{src}}}", line)
            self._reline(e, line)
            return e
        except LexError as exc:
            raise ParseError(exc.message, line) from exc
        except ParseError as exc:
            raise ParseError(f"in f-string expression {{{src}}}: {exc.message}", line) from exc

    def _reline(self, node, line: int) -> None:
        """Stamp the f-string's real line number onto embedded AST nodes."""
        if isinstance(node, dict):
            if "line" in node:
                node["line"] = line
            for value in node.values():
                self._reline(value, line)
        elif isinstance(node, list):
            for item in node:
                self._reline(item, line)
        elif isinstance(node, tuple):
            for item in node:
                self._reline(item, line)


def parse(source: str) -> dict:
    try:
        tokens = tokenize(source)
    except LexError as exc:
        raise ParseError(exc.message, exc.line) from exc
    return Parser(tokens).parse_program()
