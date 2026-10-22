/*
 * Pyv2.js — the Python v2 language runtime, ported to JavaScript.
 * Mirrors pyv2/ (the reference implementation in Python) output-for-output.
 * Works in the browser (window.Pyv2) and in Node (module.exports).
 */
(function (global) {
  "use strict";

  // ------------------------------------------------------------------
  // Errors
  // ------------------------------------------------------------------
  class Pyv2Error extends Error {
    constructor(kind, message, line, trace) {
      super(kind + ": " + message);
      this.kind = kind;
      this.message2 = message;
      this.line = line;
      this.trace = trace || [];
    }
    format() {
      let out = this.kind + ": " + this.message2 + (this.line ? " at line " + this.line : "");
      for (const frame of this.trace) out += "\n  in " + frame;
      return out;
    }
  }
  class ParseError extends Error {
    constructor(message, line) {
      super(message);
      this.message2 = message;
      this.line = line;
    }
    format() {
      return "SyntaxError: " + this.message2 + " at line " + this.line;
    }
  }
  class ReturnSignal extends Error {
    constructor(value) { super("return"); this.value = value; }
  }
  class BreakSignal extends Error {}
  class ContinueSignal extends Error {}

  // ------------------------------------------------------------------
  // Lexer
  // ------------------------------------------------------------------
  const KEYWORDS = new Set([
    "fn", "if", "elif", "else", "while", "for", "in",
    "return", "break", "continue", "and", "or", "not",
    "true", "false", "nil", "end",
  ]);
  const OPERATORS = [
    "**", "//", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
    "->", "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]",
    "{", "}", ",", ":", ".", "?",
  ];

  function tokenize(src) {
    src = src.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const tokens = [];
    let pos = 0, line = 1;
    const n = src.length;

    const peek = (o) => (pos + (o || 0) < n ? src[pos + (o || 0)] : "");
    const push = (type, value, ln) => tokens.push({ type, value, line: ln });

    while (true) {
      // trivia: spaces / tabs / comments
      while (pos < n) {
        const ch = peek();
        if (ch === " " || ch === "\t") pos++;
        else if (ch === "#") { while (pos < n && peek() !== "\n") pos++; }
        else break;
      }
      if (pos >= n) break;
      const ch = peek();
      const ln = line;

      if (ch === "\n") {
        pos++; line++;
        if (tokens.length && tokens[tokens.length - 1].type !== "NEWLINE") push("NEWLINE", "\n", ln);
        continue;
      }

      // f-strings
      if ((ch === "f" || ch === "F") && (peek(1) === '"' || peek(1) === "'")) {
        pos++;
        const quote = src[pos++];
        push("FSTRING", readString(quote, ln), ln);
        continue;
      }
      // strings
      if (ch === '"' || ch === "'") {
        pos++;
        push("STRING", readString(ch, ln), ln);
        continue;
      }
      // numbers
      if (isDigit(ch) || (ch === "." && isDigit(peek(1)))) {
        const start = pos;
        while (pos < n && (isDigit(peek()) || peek() === ".")) pos++;
        if (pos < n && (peek() === "e" || peek() === "E")) {
          const nx = peek(1);
          if (isDigit(nx) || ((nx === "+" || nx === "-") && isDigit(peek(2)))) {
            pos++;
            if (peek() === "+" || peek() === "-") pos++;
            while (pos < n && isDigit(peek())) pos++;
          }
        }
        const text = src.slice(start, pos);
        const value = /[.eE]/.test(text) ? parseFloat(text) : parseInt(text, 10);
        if (Number.isNaN(value)) throw new ParseError("Invalid number literal '" + text + "'", ln);
        push("NUMBER", value, ln);
        continue;
      }
      // identifiers
      if (isAlpha(ch) || ch === "_") {
        const start = pos;
        while (pos < n && (isAlphaNum(peek()) || peek() === "_")) pos++;
        const word = src.slice(start, pos);
        push(KEYWORDS.has(word) ? "KEYWORD" : "IDENT", word, ln);
        continue;
      }
      // operators
      let matched = false;
      for (const op of OPERATORS) {
        if (src.startsWith(op, pos)) {
          pos += op.length;
          push("OP", op, ln);
          matched = true;
          break;
        }
      }
      if (!matched) throw new ParseError("Unexpected character " + JSON.stringify(ch), ln);
    }
    if (tokens.length && tokens[tokens.length - 1].type !== "NEWLINE") push("NEWLINE", "\n", line);
    push("EOF", null, line);
    return tokens;

    function readString(quote, ln) {
      let body = "";
      while (true) {
        if (pos >= n) throw new ParseError("Unterminated string literal", ln);
        const c = src[pos++];
        if (c === "\n") throw new ParseError("Unterminated string literal (newline in string)", ln);
        if (c === "\\") {
          if (pos >= n) throw new ParseError("Unterminated string literal", ln);
          const esc = src[pos++];
          const map = { n: "\n", t: "\t", r: "\r", "\\": "\\", "'": "'", '"': '"', "0": "\0" };
          if (esc === "u") {
            let hex = "";
            while (hex.length < 4 && pos < n) hex += src[pos++];
            body += String.fromCharCode(parseInt(hex, 16));
          } else if (esc in map) body += map[esc];
          else throw new ParseError("Unknown escape sequence \\" + esc, ln);
          continue;
        }
        if (c === quote) return body;
        body += c;
      }
    }
  }
  function isDigit(c) { return c >= "0" && c <= "9"; }
  function isAlpha(c) { return (c >= "a" && c <= "z") || (c >= "A" && c <= "Z"); }
  function isAlphaNum(c) { return isAlpha(c) || isDigit(c); }
  // full numeric literal for strict int()/float() conversion
  const NUM_RE = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

  // ------------------------------------------------------------------
  // Parser
  // ------------------------------------------------------------------
  function parse(src) {
    let tokens;
    try { tokens = tokenize(src); }
    catch (e) { if (e instanceof ParseError) throw e; throw new ParseError(String(e), 1); }
    let pos = 0;

    const peek = (o) => tokens[Math.min(pos + (o || 0), tokens.length - 1)];
    const advance = () => { const t = tokens[pos]; if (t.type !== "EOF") pos++; return t; };
    const check = (type, value) => {
      const t = peek();
      return t.type === type && (value === undefined || t.value === value);
    };
    const match = (type, value) => { if (check(type, value)) { advance(); return true; } return false; };
    const expect = (type, value, what) => {
      if (check(type, value)) return advance();
      const t = peek();
      let got = t.type === "NEWLINE" ? "end of line" : t.type === "EOF" ? "end of file" : t.value;
      throw new ParseError("Expected " + JSON.stringify(what || (value !== undefined ? value : type)) +
        " but found " + JSON.stringify(got), t.line);
    };
    const skipNewlines = () => { while (check("NEWLINE")) advance(); };

    function parseProgram() {
      return { t: "program", body: parseBlockUntil(new Set()) };
    }
    function parseBlockUntil(stops) {
      const body = [];
      while (true) {
        skipNewlines();
        const tok = peek();
        if (tok.type === "EOF") break;
        if (tok.type === "KEYWORD" && stops.has(tok.value)) break;
        body.push(parseStmt());
      }
      return body;
    }

    function parseStmt() {
      const tok = peek();
      if (tok.type === "KEYWORD") {
        if (tok.value === "if") return parseIf();
        if (tok.value === "while") return parseWhile();
        if (tok.value === "for") return parseFor();
        if (tok.value === "fn" && peek(1).type === "IDENT") return parseFn();
        if (tok.value === "return") {
          advance();
          let value = null;
          if (!(check("NEWLINE") || check("KEYWORD", "end") || check("KEYWORD", "elif") ||
                check("KEYWORD", "else") || check("EOF"))) {
            value = parseTernary();
          }
          endSimple();
          return { t: "return", value, line: tok.line };
        }
        if (tok.value === "break") { advance(); endSimple(); return { t: "break", line: tok.line }; }
        if (tok.value === "continue") { advance(); endSimple(); return { t: "continue", line: tok.line }; }
        throw new ParseError("Unexpected keyword " + JSON.stringify(tok.value), tok.line);
      }

      const expr = parseTernary();
      const next = peek();
      if (next.type === "OP" && ["=", "+=", "-=", "*=", "/=", "%="].includes(next.value)) {
        if (!["var", "index", "attr"].includes(expr.t)) {
          throw new ParseError("Invalid assignment target", next.line);
        }
        advance();
        const value = parseTernary();
        endSimple();
        return { t: "assign", target: expr, value, op: next.value, line: next.line };
      }
      endSimple();
      return { t: "exprstmt", expr, line: tok.line };
    }

    function endSimple() {
      if (check("NEWLINE")) advance();
      else if (check("EOF") || check("KEYWORD", "end") || check("KEYWORD", "elif") || check("KEYWORD", "else")) return;
      else {
        const tok = peek();
        throw new ParseError("Unexpected " + JSON.stringify(tok.value) + " after statement", tok.line);
      }
    }

    function endCompound() {
      // After a block's 'end': consume a newline if present, else the next
      // statement may start on the same line.
      if (check("NEWLINE")) advance();
    }

    function parseBlock(stops) {
      expect("OP", ":");
      skipNewlines();
      const s = new Set(stops); s.add("end");
      return parseBlockUntil(s);
    }

    function parseIf() {
      const line = advance().line;
      const arms = [];
      let cond = parseTernary();
      let body = parseBlock(new Set(["elif", "else"]));
      arms.push({ cond, body });
      let elseBody = null;
      while (check("KEYWORD", "elif")) {
        advance();
        cond = parseTernary();
        body = parseBlock(new Set(["elif", "else"]));
        arms.push({ cond, body });
      }
      if (check("KEYWORD", "else")) {
        advance();
        elseBody = parseBlock(new Set());
      }
      expect("KEYWORD", "end");
      endCompound();
      return { t: "if", arms, else: elseBody, line };
    }

    function parseWhile() {
      const line = advance().line;
      const cond = parseTernary();
      const body = parseBlock(new Set());
      expect("KEYWORD", "end");
      endCompound();
      return { t: "while", cond, body, line };
    }

    function parseFor() {
      const line = advance().line;
      const name = expect("IDENT", undefined, "loop variable").value;
      expect("KEYWORD", "in");
      const iter = parseTernary();
      const body = parseBlock(new Set());
      expect("KEYWORD", "end");
      endCompound();
      return { t: "for", name, iter, body, line };
    }

    function parseFn() {
      const line = advance().line;
      const name = expect("IDENT", undefined, "function name").value;
      const params = parseParams();
      const body = parseBlock(new Set());
      expect("KEYWORD", "end");
      endCompound();
      return { t: "fn", name, params, body, line };
    }

    function parseParams() {
      expect("OP", "(");
      skipNewlines();
      const params = [];
      if (!check("OP", ")")) {
        while (true) {
          params.push(expect("IDENT", undefined, "parameter name").value);
          if (!match("OP", ",")) break;
          skipNewlines();
          if (check("OP", ")")) break;
        }
      }
      skipNewlines();
      expect("OP", ")");
      return params;
    }

    function parseTernary() {
      const cond = parseOr();
      if (check("OP", "?")) {
        advance();
        const then = parseTernary();
        expect("OP", ":");
        const other = parseTernary();
        return { t: "ternary", cond, then, else: other };
      }
      return cond;
    }
    function parseOr() {
      let left = parseAnd();
      while (check("KEYWORD", "or")) {
        const line = advance().line;
        const right = parseAnd();
        left = { t: "bin", op: "or", l: left, r: right, line };
      }
      return left;
    }
    function parseAnd() {
      let left = parseNot();
      while (check("KEYWORD", "and")) {
        const line = advance().line;
        const right = parseNot();
        left = { t: "bin", op: "and", l: left, r: right, line };
      }
      return left;
    }
    function parseNot() {
      if (check("KEYWORD", "not")) {
        const line = advance().line;
        return { t: "un", op: "not", e: parseNot(), line };
      }
      return parseComparison();
    }
    function parseComparison() {
      let left = parseAdd();
      while (true) {
        const tok = peek();
        if (tok.type === "OP" && ["==", "!=", "<", "<=", ">", ">="].includes(tok.value)) {
          advance();
          const right = parseAdd();
          left = { t: "bin", op: tok.value, l: left, r: right, line: tok.line };
        } else if (tok.type === "KEYWORD" && tok.value === "in") {
          advance();
          const right = parseAdd();
          left = { t: "bin", op: "in", l: left, r: right, line: tok.line };
        } else return left;
      }
    }
    function parseAdd() {
      let left = parseMul();
      while (check("OP", "+") || check("OP", "-")) {
        const tok = advance();
        const right = parseMul();
        left = { t: "bin", op: tok.value, l: left, r: right, line: tok.line };
      }
      return left;
    }
    function parseMul() {
      let left = parseUnary();
      while (check("OP", "*") || check("OP", "/") || check("OP", "//") || check("OP", "%")) {
        const tok = advance();
        const right = parseUnary();
        left = { t: "bin", op: tok.value, l: left, r: right, line: tok.line };
      }
      return left;
    }
    function parseUnary() {
      const tok = peek();
      if (tok.type === "OP" && (tok.value === "-" || tok.value === "+")) {
        advance();
        return { t: "un", op: tok.value, e: parseUnary(), line: tok.line };
      }
      return parsePower();
    }
    function parsePower() {
      const base = parsePostfix();
      if (check("OP", "**")) {
        const tok = advance();
        return { t: "bin", op: "**", l: base, r: parseUnary(), line: tok.line };
      }
      return base;
    }
    function parsePostfix() {
      let e = parsePrimary();
      while (true) {
        const tok = peek();
        if (tok.type === "OP" && tok.value === "(") {
          advance();
          skipNewlines();
          const args = [];
          if (!check("OP", ")")) {
            while (true) {
              args.push(parseTernary());
              if (!match("OP", ",")) break;
              skipNewlines();
              if (check("OP", ")")) break;
            }
          }
          skipNewlines();
          expect("OP", ")");
          e = { t: "call", callee: e, args, line: tok.line };
        } else if (tok.type === "OP" && tok.value === "[") {
          advance();
          skipNewlines();
          const idx = parseTernary();
          skipNewlines();
          expect("OP", "]");
          e = { t: "index", obj: e, idx, line: tok.line };
        } else if (tok.type === "OP" && tok.value === ".") {
          advance();
          const name = expect("IDENT", undefined, "attribute name").value;
          e = { t: "attr", obj: e, name, line: tok.line };
        } else return e;
      }
    }

    function parsePrimary() {
      const tok = peek();
      if (tok.type === "NUMBER") { advance(); return { t: "num", v: tok.value, line: tok.line }; }
      if (tok.type === "STRING") { advance(); return { t: "str", v: tok.value, line: tok.line }; }
      if (tok.type === "FSTRING") { advance(); return parseFstring(String(tok.value), tok.line); }
      if (tok.type === "IDENT") { advance(); return { t: "var", name: tok.value, line: tok.line }; }
      if (tok.type === "KEYWORD") {
        if (tok.value === "true") { advance(); return { t: "bool", v: true, line: tok.line }; }
        if (tok.value === "false") { advance(); return { t: "bool", v: false, line: tok.line }; }
        if (tok.value === "nil") { advance(); return { t: "nil", line: tok.line }; }
        if (tok.value === "fn") {
          advance();
          const params = parseParams();
          const body = parseBlock(new Set());
          expect("KEYWORD", "end");
          return { t: "fnexpr", params, body, line: tok.line };
        }
      }
      if (tok.type === "OP") {
        if (tok.value === "(") {
          advance();
          skipNewlines();
          const e = parseTernary();
          skipNewlines();
          expect("OP", ")");
          return e;
        }
        if (tok.value === "[") {
          advance();
          skipNewlines();
          const items = [];
          if (!check("OP", "]")) {
            while (true) {
              items.push(parseTernary());
              if (!match("OP", ",")) break;
              skipNewlines();
              if (check("OP", "]")) break;
            }
          }
          skipNewlines();
          expect("OP", "]");
          return { t: "list", items, line: tok.line };
        }
        if (tok.value === "{") return parseMap();
      }
      const got = tok.type === "NEWLINE" ? "end of line" : tok.type === "EOF" ? "end of file" : tok.value;
      throw new ParseError("Unexpected " + JSON.stringify(got) + " in expression", tok.line);
    }

    function parseMap() {
      const tok = expect("OP", "{");
      skipNewlines();
      const pairs = [];
      if (!check("OP", "}")) {
        while (true) {
          let key;
          if (check("IDENT") && peek(1).type === "OP" && peek(1).value === ":") {
            key = { t: "str", v: advance().value, line: tok.line };
            advance(); // ':'
          } else {
            key = parseTernary();
            expect("OP", ":");
          }
          skipNewlines();
          const value = parseTernary();
          pairs.push([key, value]);
          if (!match("OP", ",")) break;
          skipNewlines();
          if (check("OP", "}")) break;
        }
      }
      skipNewlines();
      expect("OP", "}");
      return { t: "map", pairs, line: tok.line };
    }

    function parseFstring(raw, line) {
      const parts = [];
      let buf = [];
      let i = 0;
      const n = raw.length;
      while (i < n) {
        const ch = raw[i];
        if (ch === "{") {
          if (i + 1 < n && raw[i + 1] === "{") { buf.push("{"); i += 2; continue; }
          let depth = 1, j = i + 1;
          while (j < n && depth > 0) {
            if (raw[j] === "{") depth++;
            else if (raw[j] === "}") depth--;
            j++;
          }
          if (depth !== 0) throw new ParseError("Unmatched '{' in f-string", line);
          const exprSrc = raw.slice(i + 1, j - 1);
          if (!exprSrc.trim()) throw new ParseError("Empty expression in f-string", line);
          if (buf.length) { parts.push({ t: "str", v: buf.join(""), line }); buf = []; }
          parts.push(parseEmbedded(exprSrc, line));
          i = j;
          continue;
        }
        if (ch === "}") {
          if (i + 1 < n && raw[i + 1] === "}") { buf.push("}"); i += 2; continue; }
          throw new ParseError("Unmatched '}' in f-string", line);
        }
        buf.push(ch);
        i++;
      }
      if (buf.length) parts.push({ t: "str", v: buf.join(""), line });
      return { t: "fstr", parts, line };
    }

    function parseEmbedded(srcText, line) {
      try {
        const sub = parse(srcText + "\n");
        if (sub.body.length === 1 && sub.body[0].t === "exprstmt") {
          return reline(sub.body[0].expr, line);
        }
        throw new ParseError("Not an expression: " + srcText, line);
      } catch (e) {
        if (e instanceof ParseError && e.message2 === "Not an expression: " + srcText) throw e;
        if (e instanceof ParseError) throw new ParseError("in f-string expression {" + srcText + "}: " + e.message2, line);
        throw e;
      }
    }

    function reline(node, line) {
      // Stamp the f-string's real line number onto embedded AST nodes.
      if (Array.isArray(node)) {
        node.forEach((item) => reline(item, line));
      } else if (node && typeof node === "object") {
        if ("line" in node) node.line = line;
        Object.values(node).forEach((v) => reline(v, line));
      }
      return node;
    }

    return parseProgram();
  }

  // ------------------------------------------------------------------
  // Values
  // ------------------------------------------------------------------
  function formatNumber(v) {
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "bigint") v = Number(v);
    if (Number.isNaN(v)) return "nan";
    if (v === Infinity) return "inf";
    if (v === -Infinity) return "-inf";
    if (Number.isInteger(v) && Math.abs(v) < 1e15) return String(v);
    if (v !== 0 && (Math.abs(v) >= 1e15 || Math.abs(v) < 1e-4)) {
      let s = v.toExponential();
      const ei = s.indexOf("e");
      const mant = s.slice(0, ei);
      const exp = s.slice(ei + 1);
      const sign = exp.startsWith("-") ? "-" : "+";
      let digits = exp.replace(/^[+-]/, "").replace(/^0+/, "");
      if (!digits) digits = "0";
      return mant + "e" + sign + digits;
    }
    return String(v);
  }

  function escapeString(s) {
    let out = "";
    for (const ch of s) {
      if (ch === "\\") out += "\\\\";
      else if (ch === '"') out += '\\"';
      else if (ch === "\n") out += "\\n";
      else if (ch === "\t") out += "\\t";
      else if (ch === "\r") out += "\\r";
      else if (ch.charCodeAt(0) < 0x20) out += "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0");
      else out += ch;
    }
    return out;
  }

  function display(v) {
    if (v === null || v === undefined) return "nil";
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") return formatNumber(v);
    if (typeof v === "string") return v;
    return reprValue(v);
  }

  function reprValue(v) {
    if (typeof v === "string") return '"' + escapeString(v) + '"';
    if (v instanceof PyList) return "[" + v.items.map(reprValue).join(", ") + "]";
    if (v instanceof PyMap) {
      const parts = [];
      for (const [k, val] of v.entries()) parts.push(reprValue(k) + ": " + reprValue(val));
      return "{" + parts.join(", ") + "}";
    }
    if (v instanceof Fn) return "<fn " + v.name + ">";
    if (v instanceof Builtin) return "<builtin " + v.name + ">";
    if (v instanceof BoundMethod) return "<method " + v.name + ">";
    if (v instanceof RangeVal) return "<range " + v.start + ".." + v.stop + ">";
    return display(v);
  }

  function isTruthy(v) {
    if (v === null || v === undefined || v === false) return false;
    if (v === true) return true;
    if (typeof v === "number") return v !== 0;
    if (typeof v === "string") return v.length !== 0;
    if (v instanceof PyList) return v.items.length !== 0;
    if (v instanceof PyMap) return v.size !== 0;
    if (v instanceof RangeVal) return v.len() !== 0;
    return true;
  }

  function valuesEqual(a, b) {
    if (typeof a === "boolean" || typeof b === "boolean") {
      return typeof a === "boolean" && typeof b === "boolean" && a === b;
    }
    if (typeof a === "number" && typeof b === "number") return a === b;
    if (typeof a === "string" && typeof b === "string") return a === b;
    if (a === null || a === undefined || b === null || b === undefined) {
      return (a === null || a === undefined) && (b === null || b === undefined);
    }
    if (a instanceof PyList && b instanceof PyList) {
      return a.items.length === b.items.length &&
        a.items.every((x, i) => valuesEqual(x, b.items[i]));
    }
    if (a instanceof PyMap && b instanceof PyMap) {
      if (a.size !== b.size) return false;
      for (const [k, v] of a.entries()) {
        if (!b.has(k) || !valuesEqual(v, b.get(k))) return false;
      }
      return true;
    }
    return a === b;
  }

  // Collections
  class PyList {
    constructor(items) { this.items = items || []; }
  }
  class PyMap {
    constructor() { this.map = new Map(); }
    get size() { return this.map.size; }
    get(key, dflt) {
      if (this.map.has(key)) return this.map.get(key);
      return dflt === undefined ? null : dflt;
    }
    has(key) { return this.map.has(key); }
    set(key, value) { this.map.set(key, value); }
    delete(key) { const v = this.map.get(key); this.map.delete(key); return v === undefined ? null : v; }
    *entries() { yield* this.map.entries(); }
    keys() { return [...this.map.keys()]; }
    values() { return [...this.map.values()]; }
    clone() { const m = new PyMap(); for (const [k, v] of this.map) m.set(k, v); return m; }
  }
  class RangeVal {
    constructor(start, stop, step) { this.start = start; this.stop = stop; this.step = step; }
    len() {
      if (this.step > 0 && this.start < this.stop) return Math.floor((this.stop - this.start + this.step - 1) / this.step);
      if (this.step < 0 && this.start > this.stop) return Math.floor((this.start - this.stop - this.step - 1) / (-this.step));
      return 0;
    }
    values() {
      const out = [];
      if (this.step > 0) { for (let i = this.start; i < this.stop; i += this.step) out.push(i); }
      else if (this.step < 0) { for (let i = this.start; i > this.stop; i += this.step) out.push(i); }
      return out;
    }
  }
  class Fn {
    constructor(name, params, body, closure, line) {
      this.name = name; this.params = params; this.body = body;
      this.closure = closure; this.line = line;
    }
  }
  class Builtin {
    constructor(name, fn, arity) { this.name = name; this.fn = fn; this.arity = arity === undefined ? null : arity; }
  }
  class BoundMethod {
    constructor(value, name, fn) { this.value = value; this.name = name; this.fn = fn; }
  }

  function normalizeKey(key, interp, line) {
    if (typeof key === "boolean") return key;
    if (typeof key === "number") return key;
    if (typeof key === "string") return key;
    if (key === null || key === undefined) return null;
    throw interp.error("TypeError", "Map keys must be numbers, strings or bools, got " + typeName(key), line);
  }

  function typeName(v) {
    if (v === null || v === undefined) return "nil";
    if (typeof v === "boolean") return "bool";
    if (typeof v === "number") return "number";
    if (typeof v === "string") return "string";
    if (v instanceof PyList) return "list";
    if (v instanceof PyMap) return "map";
    if (v instanceof Fn || v instanceof Builtin || v instanceof BoundMethod) return "fn";
    if (v instanceof RangeVal) return "range";
    return "unknown";
  }

  function jsonToNative(value, seen) {
    if (value === null || typeof value === "boolean" || typeof value === "string") return value;
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw new Error("non-finite numbers are not valid JSON");
      if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
        throw new Error("integer exceeds the cross-runtime safe range");
      }
      return value;
    }
    const active = seen || new Set();
    if (value instanceof PyList) {
      if (active.has(value)) throw new Error("circular data is not valid JSON");
      active.add(value);
      const out = value.items.map((item) => jsonToNative(item, active));
      active.delete(value);
      return out;
    }
    if (value instanceof PyMap) {
      if (active.has(value)) throw new Error("circular data is not valid JSON");
      active.add(value);
      const out = {};
      for (const [key, item] of value.entries()) {
        if (typeof key !== "string") throw new Error("JSON map keys must be strings");
        out[key] = jsonToNative(item, active);
      }
      active.delete(value);
      return out;
    }
    throw new Error(typeName(value) + " is not valid JSON");
  }

  function nativeToJsonValue(value) {
    if (typeof value === "number" && Number.isInteger(value) && !Number.isSafeInteger(value)) {
      throw new Error("integer exceeds the cross-runtime safe range");
    }
    if (Array.isArray(value)) return new PyList(value.map(nativeToJsonValue));
    if (value !== null && typeof value === "object") {
      const result = new PyMap();
      Object.entries(value).forEach(([key, item]) => result.set(key, nativeToJsonValue(item)));
      return result;
    }
    return value;
  }

  // ------------------------------------------------------------------
  // Environments
  // ------------------------------------------------------------------
  class Env {
    constructor(parent, scopeRoot) {
      this.vars = new Map();
      this.parent = parent || null;
      this.scopeRoot = !!scopeRoot; // true for globals and function frames
    }
    get(name) {
      let env = this;
      while (env) { if (env.vars.has(name)) return env.vars.get(name); env = env.parent; }
      throw new KeyError(name);
    }
    has(name) {
      let env = this;
      while (env) { if (env.vars.has(name)) return true; env = env.parent; }
      return false;
    }
    setExisting(name, value) {
      let env = this;
      while (env) {
        if (env.vars.has(name)) { env.vars.set(name, value); return true; }
        env = env.parent;
      }
      return false;
    }
    define(name, value) { this.vars.set(name, value); }
    defineInRoot(name, value) {
      // First-time assignment binds in the nearest function scope (or
      // global), never inside if/while/for blocks.
      let env = this;
      while (env && !env.scopeRoot) env = env.parent;
      (env || this).vars.set(name, value);
    }
  }
  class KeyError extends Error {
    constructor(name) { super(name); this.name2 = name; }
  }

  // ------------------------------------------------------------------
  // Interpreter
  // ------------------------------------------------------------------
  class Interpreter {
    constructor(output) {
      this.globals = new Env(null, true);
      this.output = output || ((text) => { console.log(text); });
      this.trace = [];
      this.builtins = this.makeBuiltins();
    }

    error(kind, message, line) {
      return new Pyv2Error(kind, message, line, this.trace.slice());
    }

    run(source) {
      const program = parse(source);
      try {
        this.execBlock(program.body, this.globals);
      } catch (e) {
        if (e instanceof ReturnSignal) throw new Pyv2Error("RuntimeError", "'return' outside of a function", null);
        if (e instanceof BreakSignal) throw new Pyv2Error("RuntimeError", "'break' outside of a loop", null);
        if (e instanceof ContinueSignal) throw new Pyv2Error("RuntimeError", "'continue' outside of a loop", null);
        throw e;
      }
    }

    execBlock(body, env) {
      for (const stmt of body) this.execStmt(stmt, env);
    }

    execStmt(node, env) {
      switch (node.t) {
        case "exprstmt": this.evalExpr(node.expr, env); break;
        case "assign": this.execAssign(node, env); break;
        case "if": {
          for (const arm of node.arms) {
            if (isTruthy(this.evalExpr(arm.cond, env))) {
              this.execBlock(arm.body, new Env(env));
              return;
            }
          }
          if (node.else) this.execBlock(node.else, new Env(env));
          break;
        }
        case "while": {
          while (isTruthy(this.evalExpr(node.cond, env))) {
            try { this.execBlock(node.body, new Env(env)); }
            catch (e) { if (e instanceof BreakSignal) break; else if (e instanceof ContinueSignal) continue; throw e; }
          }
          break;
        }
        case "for": this.execFor(node, env); break;
        case "fn": {
          const fn = new Fn(node.name, node.params, node.body, env, node.line);
          if (!env.setExisting(node.name, fn)) env.defineInRoot(node.name, fn);
          break;
        }
        case "return":
          throw new ReturnSignal(node.value ? this.evalExpr(node.value, env) : null);
        case "break": throw new BreakSignal();
        case "continue": throw new ContinueSignal();
        default:
          throw this.error("RuntimeError", "Unknown statement " + node.t, node.line);
      }
    }

    execAssign(node, env) {
      const target = node.target;
      let value;
      if (node.op === "=") {
        value = this.evalExpr(node.value, env);
      } else {
        const old = this.evalExpr(target, env);
        value = this.binop(node.op[0], old, this.evalExpr(node.value, env), node.line);
      }
      if (target.t === "var") {
        if (!env.setExisting(target.name, value)) env.defineInRoot(target.name, value);
      } else if (target.t === "index") {
        const obj = this.evalExpr(target.obj, env);
        const idx = this.evalExpr(target.idx, env);
        this.setIndex(obj, idx, value, target.line);
      } else if (target.t === "attr") {
        const obj = this.evalExpr(target.obj, env);
        this.setAttr(obj, target.name, value, target.line);
      }
    }

    execFor(node, env) {
      const iterable = this.evalExpr(node.iter, env);
      let items;
      if (iterable instanceof PyList) items = iterable.items.slice();
      else if (typeof iterable === "string") items = Array.from(iterable); // [] for ""
      else if (iterable instanceof PyMap) items = iterable.keys();
      else if (iterable instanceof RangeVal) items = iterable.values();
      else throw this.error("TypeError", "Cannot iterate over " + typeName(iterable), node.line);
      for (const item of items) {
        const scope = new Env(env);
        scope.define(node.name, item);
        try { this.execBlock(node.body, scope); }
        catch (e) { if (e instanceof BreakSignal) break; else if (e instanceof ContinueSignal) continue; throw e; }
      }
    }

    evalExpr(node, env) {
      switch (node.t) {
        case "num": return node.v;
        case "str": return node.v;
        case "bool": return node.v;
        case "nil": return null;
        case "list": return new PyList(node.items.map((item) => this.evalExpr(item, env)));
        case "map": {
          const out = new PyMap();
          for (const [keyNode, valNode] of node.pairs) {
            const key = normalizeKey(this.evalExpr(keyNode, env), this, node.line);
            out.set(key, this.evalExpr(valNode, env));
          }
          return out;
        }
        case "fstr": {
          const parts = [];
          for (const part of node.parts) {
            parts.push(part.t === "str" ? part.v : display(this.evalExpr(part, env)));
          }
          return parts.join("");
        }
        case "var": {
          if (env.has(node.name)) return env.get(node.name);
          if (this.builtins.has(node.name)) return this.builtins.get(node.name);
          throw this.error("NameError", "Name '" + node.name + "' is not defined", node.line);
        }
        case "ternary":
          return this.evalExpr(isTruthy(this.evalExpr(node.cond, env)) ? node.then : node.else, env);
        case "bin":
          return this.evalBin(node, env);
        case "un": {
          const value = this.evalExpr(node.e, env);
          if (node.op === "not") return !isTruthy(value);
          if (node.op === "-") {
            if (typeof value !== "number" || typeof value === "boolean") {
              throw this.error("TypeError", "Cannot negate " + typeName(value), node.line);
            }
            return -value;
          }
          return value;
        }
        case "index":
          return this.getIndex(this.evalExpr(node.obj, env), this.evalExpr(node.idx, env), node.line);
        case "attr":
          return this.getAttr(this.evalExpr(node.obj, env), node.name, node.line);
        case "call": {
          const callee = this.evalExpr(node.callee, env);
          const args = node.args.map((a) => this.evalExpr(a, env));
          return this.callValue(callee, args, node.line);
        }
        case "fnexpr":
          return new Fn("<fn@" + node.line + ">", node.params, node.body, env, node.line);
        default:
          throw this.error("RuntimeError", "Unknown expression " + node.t, node.line);
      }
    }

    evalBin(node, env) {
      const op = node.op;
      if (op === "and") {
        const left = this.evalExpr(node.l, env);
        return isTruthy(left) ? this.evalExpr(node.r, env) : left;
      }
      if (op === "or") {
        const left = this.evalExpr(node.l, env);
        return isTruthy(left) ? left : this.evalExpr(node.r, env);
      }
      return this.binop(op, this.evalExpr(node.l, env), this.evalExpr(node.r, env), node.line);
    }

    binop(op, a, b, line) {
      switch (op) {
        case "==": return valuesEqual(a, b);
        case "!=": return !valuesEqual(a, b);
        case "in": return this.opIn(a, b, line);
        case "<": case "<=": case ">": case ">=": return this.compare(op, a, b, line);
        case "+":
          if (typeof a === "string" || typeof b === "string") {
            if (typeof a === "string" && typeof b === "string") return a + b;
            return display(a) + display(b);
          }
          if (a instanceof PyList && b instanceof PyList) return new PyList(a.items.concat(b.items));
          return this.numOp(op, a, b, line);
        case "*":
          if (typeof a === "string" && typeof b === "number") return b > 0 ? a.repeat(b) : "";
          if (typeof b === "string" && typeof a === "number") return a > 0 ? b.repeat(a) : "";
          if (a instanceof PyList && typeof b === "number") return b > 0 ? new PyList(Array(b).fill(null).reduce((acc) => acc.concat(a.items), [])) : new PyList([]);
          if (b instanceof PyList && typeof a === "number") return a > 0 ? new PyList(Array(a).fill(null).reduce((acc) => acc.concat(b.items), [])) : new PyList([]);
          return this.numOp(op, a, b, line);
        case "-": case "/": case "//": case "%": case "**":
          return this.numOp(op, a, b, line);
        default:
          throw this.error("RuntimeError", "Unknown operator " + op, line);
      }
    }

    numOp(op, a, b, line) {
      if (typeof a !== "number" || typeof b !== "number" || typeof a === "boolean" || typeof b === "boolean") {
        throw this.error("TypeError", "Operator '" + op + "' needs numbers, got " + typeName(a) + " and " + typeName(b), line);
      }
      switch (op) {
        case "+": return a + b;
        case "-": return a - b;
        case "*": return a * b;
        case "/":
          if (b === 0) throw this.error("ZeroDivisionError", "Division by zero", line);
          return a / b;
        case "//":
          if (b === 0) throw this.error("ZeroDivisionError", "Division by zero", line);
          return Math.floor(a / b);
        case "%": {
          if (b === 0) throw this.error("ZeroDivisionError", "Modulo by zero", line);
          let r = a % b;
          if (r !== 0 && (r < 0) !== (b < 0)) r += b;
          return r;
        }
        case "**": {
          const result = Math.pow(a, b);
          if (typeof result === "undefined" || Number.isNaN(result)) {
            throw this.error("OverflowError", "Result too large", line);
          }
          return result;
        }
        default:
          throw this.error("RuntimeError", "Unknown operator " + op, line);
      }
    }

    compare(op, a, b, line) {
      const ok = (typeof a === "number" && typeof b === "number") ||
                 (typeof a === "string" && typeof b === "string");
      if (!ok || typeof a === "boolean" || typeof b === "boolean") {
        throw this.error("TypeError", "Cannot compare " + typeName(a) + " and " + typeName(b), line);
      }
      if (op === "<") return a < b;
      if (op === "<=") return a <= b;
      if (op === ">") return a > b;
      return a >= b;
    }

    opIn(needle, haystack, line) {
      if (typeof haystack === "string") {
        return haystack.includes(typeof needle === "string" ? needle : display(needle));
      }
      if (haystack instanceof PyList) return haystack.items.some((item) => valuesEqual(needle, item));
      if (haystack instanceof PyMap) return haystack.has(normalizeKey(needle, this, line));
      if (haystack instanceof RangeVal) {
        return typeof needle === "number" && haystack.values().includes(needle);
      }
      throw this.error("TypeError", "'in' needs a list, map, string or range, got " + typeName(haystack), line);
    }

    getIndex(obj, idx, line) {
      if (obj instanceof PyList) {
        if (typeof idx !== "number") throw this.error("TypeError", "List index must be a number", line);
        let i = Math.trunc(idx);
        if (i < 0) i += obj.items.length;
        if (i < 0 || i >= obj.items.length) {
          throw this.error("IndexError", "List index " + Math.trunc(idx) + " out of range (len " + obj.items.length + ")", line);
        }
        return obj.items[i];
      }
      if (typeof obj === "string") {
        if (typeof idx !== "number") throw this.error("TypeError", "String index must be a number", line);
        let i = Math.trunc(idx);
        if (i < 0) i += obj.length;
        if (i < 0 || i >= obj.length) {
          throw this.error("IndexError", "String index " + Math.trunc(idx) + " out of range (len " + obj.length + ")", line);
        }
        return obj[i];
      }
      if (obj instanceof PyMap) return obj.get(normalizeKey(idx, this, line));
      throw this.error("TypeError", "Cannot index into " + typeName(obj), line);
    }

    setIndex(obj, idx, value, line) {
      if (obj instanceof PyList) {
        if (typeof idx !== "number") throw this.error("TypeError", "List index must be a number", line);
        let i = Math.trunc(idx);
        if (i < 0) i += obj.items.length;
        if (i < 0 || i >= obj.items.length) {
          throw this.error("IndexError", "List index " + Math.trunc(idx) + " out of range (len " + obj.items.length + ")", line);
        }
        obj.items[i] = value;
        return;
      }
      if (obj instanceof PyMap) {
        obj.set(normalizeKey(idx, this, line), value);
        return;
      }
      throw this.error("TypeError", "Cannot assign into " + typeName(obj), line);
    }

    getAttr(obj, name, line) {
      if (obj instanceof PyMap && obj.has(name)) return obj.get(name);
      const method = findMethod(obj, name);
      if (method) return new BoundMethod(obj, name, method);
      if (obj instanceof PyMap) throw this.error("KeyError", "Map has no key '" + name + "'", line);
      throw this.error("AttributeError", typeName(obj) + " has no attribute '" + name + "'", line);
    }

    setAttr(obj, name, value, line) {
      if (obj instanceof PyMap) { obj.set(name, value); return; }
      throw this.error("TypeError", "Cannot set attribute '" + name + "' on " + typeName(obj), line);
    }

    callValue(callee, args, line) {
      if (callee instanceof Fn) {
        if (args.length !== callee.params.length) {
          throw this.error("TypeError", "Function '" + callee.name + "' expects " + callee.params.length +
            " argument(s) but got " + args.length, line);
        }
        const callEnv = new Env(callee.closure, true);
        callee.params.forEach((p, i) => callEnv.define(p, args[i]));
        this.trace.push(callee.name + " (line " + callee.line + ")");
        try {
          this.execBlock(callee.body, callEnv);
        } catch (e) {
          if (e instanceof ReturnSignal) return e.value;
          throw e;
        } finally {
          this.trace.pop();
        }
        return null;
      }
      if (callee instanceof Builtin) {
        if (callee.arity !== null && args.length !== callee.arity) {
          throw this.error("TypeError", "'" + callee.name + "' expects " + callee.arity +
            " argument(s) but got " + args.length, line);
        }
        return callee.fn(this, args, line);
      }
      if (callee instanceof BoundMethod) return callee.fn(this, callee.value, args, line);
      throw this.error("TypeError", typeName(callee) + " is not callable", line);
    }

    makeBuiltins() {
      const table = new Map();
      const def = (name, fn, arity) => table.set(name, new Builtin(name, fn, arity));

      def("print", (interp, args) => { interp.output(args.map(display).join(" ")); return null; }, null);
      def("len", (interp, args, line) => {
        const v = args[0];
        if (typeof v === "string") return v.length;
        if (v instanceof PyList) return v.items.length;
        if (v instanceof PyMap) return v.size;
        if (v instanceof RangeVal) return v.len();
        throw interp.error("TypeError", "len() needs a string, list, map or range, got " + typeName(v), line);
      }, 1);
      def("range", (interp, args, line) => {
        const nums = args.map((a) => {
          if (typeof a !== "number") throw interp.error("TypeError", "range() needs numbers", line);
          if (!Number.isInteger(a)) throw interp.error("TypeError", "range() needs integer arguments", line);
          return a;
        });
        if (nums.length === 1) return new RangeVal(0, nums[0], 1);
        if (nums.length === 2) return new RangeVal(nums[0], nums[1], 1);
        if (nums.length === 3) {
          if (nums[2] === 0) throw interp.error("ValueError", "range() step must not be zero", line);
          return new RangeVal(nums[0], nums[1], nums[2]);
        }
        throw interp.error("TypeError", "range() takes 1 to 3 arguments", line);
      }, null);
      def("str", (interp, args) => display(args[0]), 1);
      def("repr", (interp, args) => reprValue(args[0]), 1);
      def("int", (interp, args, line) => {
        const v = args[0];
        if (typeof v === "boolean") return v ? 1 : 0;
        if (typeof v === "number") return Math.trunc(v);
        if (typeof v === "string") {
          const t = v.trim();
          if (NUM_RE.test(t)) return Math.trunc(parseFloat(t));
          throw interp.error("ValueError", "Cannot convert '" + v + "' to int", line);
        }
        throw interp.error("TypeError", "Cannot convert " + typeName(v) + " to int", line);
      }, 1);
      def("float", (interp, args, line) => {
        const v = args[0];
        if (typeof v === "boolean") return v ? 1 : 0;
        if (typeof v === "number") return v;
        if (typeof v === "string") {
          const t = v.trim();
          if (NUM_RE.test(t)) return parseFloat(t);
          throw interp.error("ValueError", "Cannot convert '" + v + "' to float", line);
        }
        throw interp.error("TypeError", "Cannot convert " + typeName(v) + " to float", line);
      }, 1);
      def("bool", (interp, args) => isTruthy(args[0]), 1);
      def("abs", (interp, args, line) => {
        const v = args[0];
        if (typeof v !== "number") throw interp.error("TypeError", "abs() needs a number", line);
        return Math.abs(v);
      }, 1);
      def("min", (interp, args, line) => extreme(interp, args, line, true), null);
      def("max", (interp, args, line) => extreme(interp, args, line, false), null);
      def("floor", (interp, args, line) => Math.floor(numArg(interp, args[0], "floor()", line)), 1);
      def("ceil", (interp, args, line) => Math.ceil(numArg(interp, args[0], "ceil()", line)), 1);
      def("round", (interp, args, line) => {
        const v = numArg(interp, args[0], "round()", line);
        const digits = args.length > 1 ? Math.trunc(numArg(interp, args[1], "round()", line)) : 0;
        const factor = Math.pow(10, digits);
        const scaled = v * factor;
        const rounded = scaled >= 0 ? Math.floor(scaled + 0.5) : -Math.floor(-scaled + 0.5);
        const result = rounded / factor;
        return digits <= 0 && Number.isInteger(result) ? result : result;
      }, null);
      def("sqrt", (interp, args, line) => {
        const v = numArg(interp, args[0], "sqrt()", line);
        if (v < 0) throw interp.error("ValueError", "sqrt() of negative number", line);
        return Math.sqrt(v);
      }, 1);
      def("pow", (interp, args, line) =>
        interp.numOp("**", numArg(interp, args[0], "pow()", line), numArg(interp, args[1], "pow()", line), line), 2);
      def("type", (interp, args) => typeName(args[0]), 1);
      def("push", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "push() needs a list", line);
        args[0].items.push(args[1]);
        return args[0];
      }, 2);
      def("pop", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "pop() needs a list", line);
        if (!args[0].items.length) throw interp.error("ValueError", "pop() from empty list", line);
        return args[0].items.pop();
      }, 1);
      def("insert", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "insert() needs a list", line);
        let idx = intArg(interp, args[1], "insert()", line);
        if (idx < 0) idx += args[0].items.length;
        idx = Math.max(0, Math.min(idx, args[0].items.length));
        args[0].items.splice(idx, 0, args[2]);
        return args[0];
      }, 3);
      def("remove", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "remove() needs a list", line);
        let idx = intArg(interp, args[1], "remove()", line);
        if (idx < 0) idx += args[0].items.length;
        if (idx < 0 || idx >= args[0].items.length) throw interp.error("IndexError", "remove() index out of range", line);
        return args[0].items.splice(idx, 1)[0];
      }, 2);
      def("keys", (interp, args, line) => {
        if (!(args[0] instanceof PyMap)) throw interp.error("TypeError", "keys() needs a map", line);
        return new PyList(args[0].keys());
      }, 1);
      def("values", (interp, args, line) => {
        if (!(args[0] instanceof PyMap)) throw interp.error("TypeError", "values() needs a map", line);
        return new PyList(args[0].values());
      }, 1);
      def("has", (interp, args, line) => {
        if (!(args[0] instanceof PyMap)) throw interp.error("TypeError", "has() needs a map", line);
        return args[0].has(normalizeKey(args[1], interp, line));
      }, 2);
      def("get", (interp, args, line) => {
        if (!(args[0] instanceof PyMap)) throw interp.error("TypeError", "get() needs a map", line);
        return args[0].get(normalizeKey(args[1], interp, line), args.length > 2 ? args[2] : null);
      }, null);
      def("sort", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "sort() needs a list", line);
        return new PyList(args[0].items.slice().sort(sortComparator));
      }, 1);
      def("sort_by", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "sort_by() needs a list", line);
        const keyed = args[0].items.map((item) => [interp.callValue(args[1], [item], line), item]);
        keyed.sort((x, y) => {
          const kx = x[0], ky = y[0];
          if (typeof kx === "number" && typeof ky === "number") return kx - ky;
          if (typeof kx === "string" && typeof ky === "string") return kx < ky ? -1 : kx > ky ? 1 : 0;
          return 0;
        });
        return new PyList(keyed.map((p) => p[1]));
      }, 2);
      def("join", (interp, args, line) => {
        if (!(args[0] instanceof PyList)) throw interp.error("TypeError", "join() needs a list", line);
        if (typeof args[1] !== "string") throw interp.error("TypeError", "join() separator must be a string", line);
        return args[0].items.map(display).join(args[1]);
      }, 2);
      def("assert", (interp, args, line) => {
        if (!isTruthy(args[0])) {
          const msg = args.length > 1 ? display(args[1]) : "assertion failed";
          throw interp.error("AssertionError", msg, line);
        }
        return null;
      }, null);
      def("clock", () => (typeof performance !== "undefined" ? performance.now() : Date.now()) / 1000, 0);
      def("input", (interp, args, line) => {
        throw interp.error("RuntimeError", "input() is not available in the browser playground", line);
      }, null);
      def("args", () => new PyList([]), 0);
      def("app_info", () => {
        const info = new PyMap();
        info.set("name", "Python v2 Program"); info.set("version", "1.0.0");
        info.set("id", "python-v2-program"); info.set("platform", "browser");
        info.set("data_dir", null); info.set("has_assets", false); info.set("max_text_bytes", 0);
        return info;
      }, 0);
      def("json_encode", (interp, args, line) => {
        try { return JSON.stringify(jsonToNative(args[0])); }
        catch (error) { throw interp.error("ValueError", "json_encode(): " + error.message, line); }
      }, 1);
      def("json_decode", (interp, args, line) => {
        if (typeof args[0] !== "string") throw interp.error("TypeError", "json_decode() needs a string", line);
        try { return nativeToJsonValue(JSON.parse(args[0])); }
        catch (error) { throw interp.error("ValueError", "json_decode(): invalid JSON", line); }
      }, 1);
      ["read_text", "write_text", "append_text", "file_exists", "make_dir", "list_dir",
       "delete_file", "read_asset", "asset_exists", "sleep_ms"].forEach((name) => {
        def(name, (interp, args, line) => {
          throw interp.error("CapabilityError", name + "() is available in desktop and CLI apps, not the browser", line);
        }, null);
      });
      def("ui_message", (interp, args, line) => {
        if (typeof args[0] !== "string" || typeof args[1] !== "string") {
          throw interp.error("TypeError", "ui_message() needs title and message strings", line);
        }
        if (typeof global.alert !== "function") throw interp.error("CapabilityError", "message dialogs are unavailable", line);
        global.alert(args[0] + "\n\n" + args[1]); return null;
      }, 2);
      def("ui_ask", (interp, args, line) => {
        if (typeof args[0] !== "string" || typeof args[1] !== "string") {
          throw interp.error("TypeError", "ui_ask() needs title and prompt strings", line);
        }
        if (typeof global.prompt !== "function") throw interp.error("CapabilityError", "input dialogs are unavailable", line);
        const answer = global.prompt(args[0] + "\n\n" + args[1], args.length > 2 ? display(args[2]) : "");
        return answer === null ? null : answer;
      }, null);
      def("chr", (interp, args, line) => String.fromCodePoint(intArg(interp, args[0], "chr()", line)), 1);
      def("ord", (interp, args, line) => {
        const s = args[0];
        if (typeof s !== "string" || s.length !== 1) {
          throw interp.error("TypeError", "ord() needs a single-character string", line);
        }
        return s.charCodeAt(0);
      }, 1);
      return table;
    }
  }

  function numArg(interp, v, who, line) {
    if (typeof v !== "number") throw interp.error("TypeError", who + " needs a number", line);
    return v;
  }
  function intArg(interp, v, who, line) {
    return Math.trunc(numArg(interp, v, who, line));
  }
  function extreme(interp, args, line, wantMin) {
    const items = args.length === 1 && args[0] instanceof PyList ? args[0].items : args;
    if (!items.length) throw interp.error("ValueError", (wantMin ? "min" : "max") + "() of empty sequence", line);
    let best = items[0];
    for (const item of items.slice(1)) {
      if (interp.binop(wantMin ? "<" : ">", item, best, line)) best = item;
    }
    return best;
  }
  function sortComparator(a, b) {
    const ka = sortKey(a), kb = sortKey(b);
    if (ka[0] !== kb[0]) return ka[0] - kb[0];
    if (typeof ka[1] === "number") return ka[1] - kb[1];
    return ka[1] < kb[1] ? -1 : ka[1] > kb[1] ? 1 : 0;
  }
  function sortKey(v) {
    if (typeof v === "number") return [0, v];
    if (typeof v === "string") return [1, v];
    return [2, display(v)];
  }

  // ------------------------------------------------------------------
  // Methods
  // ------------------------------------------------------------------
  function findMethod(obj, name) {
    if (typeof obj === "string") return stringMethods[name];
    if (obj instanceof PyList) return listMethods[name];
    if (obj instanceof PyMap) return mapMethods[name];
    return null;
  }

  function sliceOf(interp, seq, args, line) {
    const n = typeof seq === "string" ? seq.length : seq.items.length;
    let start = args.length ? intArg(interp, args[0], "slice()", line) : 0;
    let end = args.length > 1 ? intArg(interp, args[1], "slice()", line) : n;
    if (start < 0) start += n;
    if (end < 0) end += n;
    start = Math.max(0, Math.min(start, n));
    end = Math.max(start, Math.min(end, n));
    return typeof seq === "string" ? seq.slice(start, end) : new PyList(seq.items.slice(start, end));
  }

  function titleCase(s) {
    return s.toLowerCase().replace(/(^|[^a-z0-9])([a-z])/g, (m, a, b) => a + b.toUpperCase());
  }

  const stringMethods = {
    upper: (i, s) => s.toUpperCase(),
    lower: (i, s) => s.toLowerCase(),
    title: (i, s) => titleCase(s),
    trim: (i, s) => s.trim(),
    chars: (i, s) => new PyList(s.split("")),
    reverse: (i, s) => s.split("").reverse().join(""),
    lines: (i, s) => new PyList(s.split("\n")),
    count: (i, s, args) => {
      if (!args.length) return 0;
      const needle = display(args[0]);
      if (!needle) return 0;
      let c = 0, idx = 0;
      while ((idx = s.indexOf(needle, idx)) !== -1) { c++; idx += needle.length; }
      return c;
    },
    slice: (i, s, args, line) => sliceOf(i, s, args, line),
    to_number: (i, s) => {
      const t = s.trim();
      if (NUM_RE.test(t)) return parseFloat(t);
      return null;
    },
    repeat: (i, s, args, line) => {
      if (!args.length) throw i.error("TypeError", "repeat() needs a count", line);
      return s.repeat(Math.max(0, intArg(i, args[0], "repeat()", line)));
    },
    split: (i, s, args) => new PyList(s.split(args.length ? display(args[0]) : " ")),
    join: (i, s, args, line) => {
      if (!args.length || !(args[0] instanceof PyList)) throw i.error("TypeError", "join() needs a list", line);
      return args[0].items.map(display).join(s);
    },
    contains: (i, s, args) => s.includes(args.length ? display(args[0]) : ""),
    starts_with: (i, s, args) => s.startsWith(args.length ? display(args[0]) : ""),
    ends_with: (i, s, args) => s.endsWith(args.length ? display(args[0]) : ""),
    index_of: (i, s, args) => s.indexOf(args.length ? display(args[0]) : ""),
    replace: (i, s, args, line) => {
      if (args.length < 2) throw i.error("TypeError", "replace() needs two arguments", line);
      return s.split(display(args[0])).join(display(args[1]));
    },
    pad_left: (i, s, args, line) => {
      const width = args.length ? intArg(i, args[0], "pad_left()", line) : 0;
      const fill = args.length > 1 ? display(args[1]) : " ";
      const f = fill || " ";
      if (s.length >= width) return s;
      return f.repeat(Math.ceil((width - s.length) / f.length)).slice(0, width - s.length) + s;
    },
    pad_right: (i, s, args, line) => {
      const width = args.length ? intArg(i, args[0], "pad_right()", line) : 0;
      const fill = args.length > 1 ? display(args[1]) : " ";
      const f = fill || " ";
      if (s.length >= width) return s;
      return s + f.repeat(Math.ceil((width - s.length) / f.length)).slice(0, width - s.length);
    },
  };

  const listMethods = {
    push: (i, lst, args) => { lst.items.push(args[0]); return lst; },
    pop: (i, lst, args, line) => {
      if (!lst.items.length) throw i.error("ValueError", "pop() from empty list", line);
      return lst.items.pop();
    },
    insert: (i, lst, args, line) => {
      let idx = intArg(i, args[0], "insert()", line);
      if (idx < 0) idx += lst.items.length;
      lst.items.splice(Math.max(0, Math.min(idx, lst.items.length)), 0, args[1]);
      return lst;
    },
    index_of: (i, lst, args) => {
      for (let k = 0; k < lst.items.length; k++) if (valuesEqual(lst.items[k], args[0])) return k;
      return -1;
    },
    contains: (i, lst, args) => {
      for (const item of lst.items) if (valuesEqual(item, args[0])) return true;
      return false;
    },
    slice: (i, lst, args, line) => sliceOf(i, lst, args, line),
    join: (i, lst, args) => lst.items.map(display).join(args.length ? display(args[0]) : ""),
    reverse: (i, lst) => new PyList(lst.items.slice().reverse()),
    sort: (i, lst) => new PyList(lst.items.slice().sort(sortComparator)),
    first: (i, lst) => (lst.items.length ? lst.items[0] : null),
    last: (i, lst) => (lst.items.length ? lst.items[lst.items.length - 1] : null),
    clear: (i, lst) => { lst.items.length = 0; return lst; },
    len: (i, lst) => lst.items.length,
  };

  const mapMethods = {
    keys: (i, m) => new PyList(m.keys()),
    values: (i, m) => new PyList(m.values()),
    has: (i, m, args, line) => m.has(normalizeKey(args[0], i, line)),
    get: (i, m, args, line) => m.get(normalizeKey(args[0], i, line), args.length > 1 ? args[1] : null),
    remove: (i, m, args, line) => m.delete(normalizeKey(args[0], i, line)),
    merge: (i, m, args, line) => {
      if (!args.length || !(args[0] instanceof PyMap)) throw i.error("TypeError", "merge() needs a map", line);
      const out = m.clone();
      for (const [k, v] of args[0].entries()) out.set(k, v);
      return out;
    },
    len: (i, m) => m.size,
  };

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------
  function run(source, output) {
    const interp = new Interpreter(output);
    interp.run(source);
    return interp;
  }

  function runCapture(source) {
    const lines = [];
    try {
      run(source, (text) => lines.push(text));
      return { output: lines.join("\n"), error: null };
    } catch (e) {
      let msg;
      if (e instanceof Pyv2Error) msg = e.format();
      else if (e instanceof ParseError) msg = e.format();
      else if (e instanceof ReturnSignal) msg = "RuntimeError: 'return' outside of a function";
      else if (e instanceof BreakSignal || e instanceof ContinueSignal) msg = "RuntimeError: '" + (e instanceof BreakSignal ? "break" : "continue") + "' outside of a loop";
      else msg = "RuntimeError: " + (e && e.message ? e.message : String(e));
      return { output: lines.join("\n"), error: msg };
    }
  }

  const Pyv2 = {
    run, runCapture, tokenize, parse, Interpreter,
    formatNumber, display, reprValue, valuesEqual, isTruthy,
    PyList, PyMap, RangeVal, Pyv2Error, ParseError,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = Pyv2;
  global.Pyv2 = Pyv2;
})(typeof globalThis !== "undefined" ? globalThis : this);
