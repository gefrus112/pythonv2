# Python v2 — Language Reference

**Python v2** is a from-scratch remake of Python: the same spirit, fewer sharp
edges. It ships with two runtimes that produce byte-identical output:

| Runtime | Location | Use |
|---|---|---|
| Reference interpreter | `pyv2/` (Python) | CLI, REPL, tests |
| Browser/Node twin | `site/pyv2.js` | Playground on the website |

File extension: `.pyv2` · CLI: `python3 -m pyv2` · Version: 0.2 "Sudbury"

---

## 1. Hello, world

```python
# hello.pyv2 — comments start with #
fn greet(name):
    if name == "":
        return "Hello, stranger!"
    end
    return f"Hello, {name}!"
end

for who in ["World", ""]:
    print(greet(who))
end
```

```console
$ python3 -m pyv2 hello.pyv2
Hello, World!
Hello, stranger!
```

## 2. Syntax at a glance

* **Statements** are separated by newlines. Blank lines are ignored.
* **Blocks** open after `:` and close with `end` (for `if`, `while`, `for`, `fn`).
  Indentation is cosmetic — tabs vs. spaces can never break your program.
* One-liners are fine: `fn sq(x): return x * x end`
* **Trailing commas** are allowed in lists, maps, calls and parameter lists,
  and brackets may span multiple lines.
* Comments: `# to end of line`.

### 2.1 Values

| Type | Literal | Notes |
|---|---|---|
| number | `1`, `2.5`, `1e-3` | 64-bit floats; whole numbers print without `.0` |
| string | `"hi"`, `'hi'`, `f"hi {x}"` | immutable, indexed `s[0]` |
| bool | `true`, `false` | |
| nil | `nil` | absence of a value |
| list | `[1, 2, 3]` | mutable, ordered |
| map | `{a: 1, "b": 2}` | bare keys become strings; any primitive key allowed |
| fn | `fn name(a): … end` | first-class, closes over its scope |
| range | `range(10)` | lazy, produced by the `range` builtin |

**Truthiness** (Python-style): `nil`, `false`, `0`, `""`, `[]`, `{}` are falsy.
Everything else is truthy.

### 2.2 Operators

| Kind | Operators |
|---|---|
| Arithmetic | `+ - * / // % **` (real division `/`, floored `//` and `%`, `**` right-assoc) |
| Comparison | `== != < <= > >=` |
| Logic | `and`, `or`, `not` (short-circuit; `and`/`or` return operands) |
| Membership | `x in list`, `k in map`, `sub in string`, `n in range(...)` |
| Ternary | `cond ? a : b` |
| Assignment | `= += -= *= /= %=` |
| Unary | `-`, `+` |

`+` joins strings and even coerces numbers: `"n=" + 42` → `n=42`.
`*` repeats strings and lists: `"ab" * 3` → `ababab`.

`==` is deep: `[1, [2]] == [1, [2]]` is `true`. Bools are not numbers
(`true != 1`), but `1 == 1.0` is `true`.

### 2.3 Variables & scope

Assignment finds the *nearest existing binding* up the scope chain and updates
it — so closures work the way you'd hope:

```python
fn make_counter():
    n = 0
    fn bump():
        n += 1        # updates make_counter's n — no nonlocal needed
        return n
    end
    return bump
end
```

If no binding exists, one is created in the current scope (function-local at
top level of a function, global at top level). Assignment never touches
builtins, so redefining `len` locally can't corrupt the runtime.

### 2.4 Control flow

```python
if score >= 90:
    return "A"
elif score >= 80:
    return "B"
else:
    return "C"
end

while running:
    step()
    if stuck:
        continue
    end
    if done:
        break
    end
end

for item in [1, 2, 3]:
    print(item)
end

for i in range(1, 10, 2):   # start, stop, step
    print(i)
end
```

`for` iterates lists (a snapshot — mutation during the loop is safe), strings
(characters), maps (keys) and ranges.

### 2.5 Functions

```python
fn add(a, b):
    return a + b
end

sq = fn(x): return x * x end   # anonymous function expression
print(add(1, 2), sq(9))
```

Functions are values. Arity is checked. Missing `return` yields `nil`.
Errors carry a call trace:

```
ZeroDivisionError: Division by zero at line 3
  in inner (line 2)
  in outer (line 5)
```

### 2.6 Strings & f-strings

```python
name = "Ada"
print(f"Hello, {name}! 2**8 = {2 ** 8}")
print(f"{{literal braces}} survive")
```

Anything inside `{…}` is a full expression. `{{` and `}}` produce literal braces.

### 2.7 Data structures

```python
xs = [3, 1, 2]
xs.push(4)          # → [3, 1, 2, 4]
xs.sort()           # → [1, 2, 3, 4]  (copy)
print(xs[0], xs[-1], xs.slice(1, 3))

hero = {
    name: "Ada",        # bare key → "name"
    scores: [10, 20],
}
print(hero.name, hero["name"])
print(hero.get("city", "unknown"))   # safe lookup with default
hero.scores.push(30)
```

## 3. Builtins

| Function | Description |
|---|---|
| `print(...)` | print values, space-separated |
| `len(x)` | length of string / list / map / range |
| `range(stop)` `range(a, b)` `range(a, b, step)` | integer range |
| `str(x)` `repr(x)` `int(x)` `float(x)` `bool(x)` | conversions |
| `abs(x)` `floor(x)` `ceil(x)` `round(x, digits)` `sqrt(x)` `pow(a, b)` | math |
| `min(...)` / `max(...)` | over arguments or one list |
| `type(x)` | `"number"`, `"string"`, `"list"`, `"map"`, `"fn"`, `"bool"`, `"nil"`, `"range"` |
| `push(list, x)` `pop(list)` `insert(list, i, x)` `remove(list, i)` | list mutation |
| `keys(map)` `values(map)` `has(map, k)` `get(map, k, default)` | map access |
| `sort(list)` `sort_by(list, fn)` `join(list, sep)` | helpers |
| `assert(cond, msg?)` | raise `AssertionError` when falsy |
| `chr(n)` `ord(char)` | character codes |
| `clock()` | seconds on the wall clock |
| `input(prompt?)` | read a line (CLI only; browser raises a friendly error) |

### 3.1 Methods

**Strings:** `upper lower title trim chars reverse lines count slice(a, b?)
to_number repeat(n) split(sep) join(list) contains starts_with ends_with
index_of replace(a, b) pad_left(w, fill?) pad_right(w, fill?)`

**Lists:** `push pop insert(i, x) index_of contains slice join(sep) reverse
sort first last clear len`

**Maps:** `keys values has get(k, default?) remove merge len`

Method names win over map keys on maps only when the key doesn't exist.

## 4. Errors

Errors are `Kind: message at line N` with an optional call trace:

`SyntaxError`, `NameError`, `TypeError`, `IndexError`, `KeyError`,
`ZeroDivisionError`, `ValueError`, `OverflowError`, `AssertionError`,
`AttributeError`, `RuntimeError`.

The CLI exits with status 1 on error; the playground prints the error in red
and keeps your code.

## 5. What's better than Python v1

| Python | Python v2 |
|---|---|
| `def` + significant whitespace | `fn` + `end` — no indentation errors, ever |
| `nonlocal` required for closure writes | assignment finds the binding, period |
| `"n=" + str(n)` | `"n=" + n` |
| `x if ok else y` (reads backwards) | `ok ? x : y` |
| `assert` is a statement | `assert()` is a function |
| trailing commas only *sometimes* | trailing commas everywhere |
| one runtime | two parity-tested runtimes, one in your browser |

## 6. Grammar (EBNF-ish)

```ebnf
program    := stmt*
stmt       := simple | compound
simple     := "return" expr? | "break" | "continue" | assign | expr
compound   := if | while | for | fn
if         := "if" expr ":" block ("elif" expr ":" block)* ("else" ":" block)? "end"
while      := "while" expr ":" block "end"
for        := "for" IDENT "in" expr ":" block "end"
fn         := "fn" IDENT "(" params ")" ":" block "end"
block      := stmt* until "end" / "elif" / "else"
assign     := target ("=" | "+=" | "-=" | "*=" | "/=" | "%=") expr
target     := IDENT | index | attr
ternary    := or ("?" ternary ":" ternary)?
or         := and ("or" and)*
and        := not_ ("and" not_)*
not_       := "not" not_ | comparison
comparison := add (("==" | "!=" | "<" | "<=" | ">" | ">=" | "in") add)*
add        := mul (("+" | "-") mul)*
mul        := unary (("*" | "/" | "//" | "%") unary)*
unary      := ("-" | "+") unary | power
power      := postfix ("**" unary)?
postfix    := primary ( "(" args ")" | "[" expr "]" | "." IDENT )*
primary    := NUMBER | STRING | FSTRING | "true" | "false" | "nil"
            | IDENT | "(" ternary ")" | list | map | fnexpr
list       := "[" (ternary ("," ternary)* ","?)? "]"
map        := "{" (pair ("," pair)* ","?)? "}"
pair       := (IDENT | ternary) ":" ternary
fnexpr     := "fn" "(" params ")" ":" block "end"
```

## 7. CLI

```console
$ python3 -m pyv2 script.pyv2     # run a file
$ python3 -m pyv2 -c 'print(42)'  # run a snippet
$ python3 -m pyv2                 # REPL (... continues blocks)
$ python3 -m pyv2 --version
```

## 8. Parity guarantee

`tests/test_pyv2.py` (61 unit tests) and `tests/test_parity.py` (20 shared
programs, including error paths) run every program through **both** runtimes
and compare outputs byte for byte. If the twins ever disagree, the test suite
fails. That's the deal.
