"""Tree-walking interpreter for Python v2."""

from __future__ import annotations

import math
import time

from .parser import parse, ParseError


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class Pyv2Error(Exception):
    def __init__(self, kind: str, message: str, line: int | None = None,
                 trace: list[str] | None = None):
        self.kind = kind
        self.message = message
        self.line = line
        self.trace = trace or []
        super().__init__(self.format())

    def format(self) -> str:
        where = f" at line {self.line}" if self.line else ""
        out = f"{self.kind}: {self.message}{where}"
        for frame in self.trace:
            out += f"\n  in {frame}"
        return out


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


# --------------------------------------------------------------------------
# Value helpers
# --------------------------------------------------------------------------
def format_number(v) -> str:
    """Uniform number formatting shared with the JS runtime (site/pyv2.js)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        if abs(v) < 1e15:
            return str(v)
        v = float(v)  # huge ints display exactly like the JS runtime
    if v != v:
        return "nan"
    if v == math.inf:
        return "inf"
    if v == -math.inf:
        return "-inf"
    if float(v).is_integer() and abs(v) < 1e15:
        return str(int(v))
    if v != 0 and (abs(v) >= 1e15 or abs(v) < 1e-4):
        s = repr(float(v))
        if "e" in s:
            mant, exp = s.split("e")
            sign = "+" if not exp.startswith("-") else "-"
            digits = exp.lstrip("+-").lstrip("0") or "0"
            return f"{mant}e{sign}{digits}"
        return s
    return repr(float(v))


def display(value) -> str:
    """Human-facing rendering (print output)."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return format_number(value)
    if isinstance(value, str):
        return value
    return repr_value(value)


def escape_string(s: str) -> str:
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def repr_value(value) -> str:
    """Container-aware rendering (quoted strings)."""
    if isinstance(value, str):
        return f'"{escape_string(value)}"'
    if isinstance(value, list):
        return "[" + ", ".join(repr_value(v) for v in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{repr_value(k)}: {repr_value(v)}" for k, v in value.items())
        return "{" + items + "}"
    if isinstance(value, Fn):
        return f"<fn {value.name}>"
    if isinstance(value, Builtin):
        return f"<builtin {value.name}>"
    if isinstance(value, BoundMethod):
        return f"<method {value.name}>"
    if isinstance(value, RangeVal):
        return f"<range {value.start}..{value.stop}>"
    return display(value)


def is_truthy(value) -> bool:
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (str, list, dict, RangeVal)):
        return len(value) != 0
    return True


def values_equal(a, b) -> bool:
    # bools are not numbers (True != 1)
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if len(a) != len(b):
            return False
        for k, v in a.items():
            if k not in b or not values_equal(v, b[k]):
                return False
        return True
    return a is b


# --------------------------------------------------------------------------
# Callables
# --------------------------------------------------------------------------
class Fn:
    def __init__(self, name: str, params: list[str], body: list[dict], closure, line: int):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.line = line


class Builtin:
    def __init__(self, name: str, fn, arity: int | None = None):
        self.name = name
        self.fn = fn
        self.arity = arity  # None = variadic


class BoundMethod:
    def __init__(self, value, name: str, fn):
        self.value = value
        self.name = name
        self.fn = fn  # callable(interpreter, args, line) — args exclude self


class RangeVal:
    def __init__(self, start: int, stop: int, step: int):
        self.start = start
        self.stop = stop
        self.step = step

    def __len__(self):
        if self.step > 0 and self.start < self.stop:
            return (self.stop - self.start + self.step - 1) // self.step
        if self.step < 0 and self.start > self.stop:
            return (self.start - self.stop - self.step - 1) // (-self.step)
        return 0

    def values(self) -> list:
        out = []
        i = self.start
        if self.step > 0:
            while i < self.stop:
                out.append(i)
                i += self.step
        elif self.step < 0:
            while i > self.stop:
                out.append(i)
                i += self.step
        return out


# --------------------------------------------------------------------------
# Environments
# --------------------------------------------------------------------------
class Env:
    def __init__(self, parent=None):
        self.vars: dict = {}
        self.parent = parent

    def get(self, name: str):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise KeyError(name)

    def has(self, name: str) -> bool:
        env = self
        while env is not None:
            if name in env.vars:
                return True
            env = env.parent
        return False

    def set_existing(self, name: str, value) -> bool:
        """Set in the nearest scope that already defines name (Lua-style).
        Never writes into builtins. Returns True if an existing binding was
        updated."""
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return True
            env = env.parent
        return False

    def define(self, name: str, value) -> None:
        self.vars[name] = value


# --------------------------------------------------------------------------
# Interpreter
# --------------------------------------------------------------------------
class Interpreter:
    def __init__(self, output=None, read_input=None):
        self.globals = Env()
        self.output = output if output is not None else self._default_output
        self.read_input = read_input
        self.trace: list[str] = []
        self.builtins = self._make_builtins()

    @staticmethod
    def _default_output(text: str) -> None:
        print(text)

    # ---------- entry points ----------
    def run(self, source: str):
        program = parse(source)
        try:
            self.exec_block(program["body"], self.globals)
        except ReturnSignal:
            raise Pyv2Error("RuntimeError", "'return' outside of a function", None)
        except BreakSignal:
            raise Pyv2Error("RuntimeError", "'break' outside of a loop", None)
        except ContinueSignal:
            raise Pyv2Error("RuntimeError", "'continue' outside of a loop", None)
        return None

    # ---------- errors ----------
    def error(self, kind: str, message: str, line=None):
        return Pyv2Error(kind, message, line, list(self.trace))

    # ---------- statements ----------
    def exec_block(self, body: list[dict], env: Env) -> None:
        for stmt in body:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, node: dict, env: Env) -> None:
        t = node["t"]
        if t == "exprstmt":
            self.eval_expr(node["expr"], env)
        elif t == "assign":
            self.exec_assign(node, env)
        elif t == "if":
            for arm in node["arms"]:
                if is_truthy(self.eval_expr(arm["cond"], env)):
                    self.exec_block(arm["body"], Env(env))
                    return
            if node["else"] is not None:
                self.exec_block(node["else"], Env(env))
        elif t == "while":
            while is_truthy(self.eval_expr(node["cond"], env)):
                try:
                    self.exec_block(node["body"], Env(env))
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
        elif t == "for":
            self.exec_for(node, env)
        elif t == "fn":
            fn = Fn(node["name"], node["params"], node["body"], env, node["line"])
            if not env.set_existing(node["name"], fn):
                env.define(node["name"], fn)
        elif t == "return":
            value = self.eval_expr(node["value"], env) if node["value"] is not None else None
            raise ReturnSignal(value)
        elif t == "break":
            raise BreakSignal()
        elif t == "continue":
            raise ContinueSignal()
        else:  # pragma: no cover
            raise self.error("RuntimeError", f"Unknown statement {t}", node.get("line"))

    def exec_assign(self, node: dict, env: Env) -> None:
        target = node["target"]
        op = node["op"]
        if op == "=":
            value = self.eval_expr(node["value"], env)
        else:
            old = self.eval_expr(target, env)
            value = self.binop(op[0], old, self.eval_expr(node["value"], env),
                               node.get("line"))

        if target["t"] == "var":
            name = target["name"]
            if not env.set_existing(name, value):
                env.define(name, value)
        elif target["t"] == "index":
            obj = self.eval_expr(target["obj"], env)
            idx = self.eval_expr(target["idx"], env)
            self.set_index(obj, idx, value, target.get("line"))
        elif target["t"] == "attr":
            obj = self.eval_expr(target["obj"], env)
            self.set_attr(obj, target["name"], value, target.get("line"))

    def exec_for(self, node: dict, env: Env) -> None:
        iterable = self.eval_expr(node["iter"], env)
        name = node["name"]
        if isinstance(iterable, list):
            items = list(iterable)  # snapshot: mutation during loop is safe
        elif isinstance(iterable, str):
            items = list(iterable)
        elif isinstance(iterable, dict):
            items = list(iterable.keys())
        elif isinstance(iterable, RangeVal):
            items = iterable.values()
        else:
            raise self.error("TypeError",
                             f"Cannot iterate over {type_name(iterable)}",
                             node.get("line"))
        for item in items:
            scope = Env(env)
            scope.define(name, item)
            try:
                self.exec_block(node["body"], scope)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    # ---------- expressions ----------
    def eval_expr(self, node: dict, env: Env):
        t = node["t"]
        if t == "num":
            return node["v"]
        if t == "str":
            return node["v"]
        if t == "bool":
            return node["v"]
        if t == "nil":
            return None
        if t == "list":
            return [self.eval_expr(item, env) for item in node["items"]]
        if t == "map":
            out = {}
            for key_node, val_node in node["pairs"]:
                key = self.eval_expr(key_node, env)
                key = normalize_key(key, self, node.get("line"))
                out[key] = self.eval_expr(val_node, env)
            return out
        if t == "fstr":
            parts = []
            for part in node["parts"]:
                if part["t"] == "str":
                    parts.append(part["v"])
                else:
                    parts.append(display(self.eval_expr(part, env)))
            return "".join(parts)
        if t == "var":
            name = node["name"]
            try:
                return env.get(name)
            except KeyError:
                pass
            if name in self.builtins:
                return self.builtins[name]
            raise self.error("NameError", f"Name '{name}' is not defined", node.get("line"))
        if t == "ternary":
            cond = self.eval_expr(node["cond"], env)
            branch = node["then"] if is_truthy(cond) else node["else"]
            return self.eval_expr(branch, env)
        if t == "bin":
            return self.eval_bin(node, env)
        if t == "un":
            value = self.eval_expr(node["e"], env)
            if node["op"] == "not":
                return not is_truthy(value)
            if node["op"] == "-":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise self.error("TypeError",
                                     f"Cannot negate {type_name(value)}", node.get("line"))
                return -value
            return value
        if t == "index":
            obj = self.eval_expr(node["obj"], env)
            idx = self.eval_expr(node["idx"], env)
            return self.get_index(obj, idx, node.get("line"))
        if t == "attr":
            obj = self.eval_expr(node["obj"], env)
            return self.get_attr(obj, node["name"], node.get("line"))
        if t == "call":
            callee = self.eval_expr(node["callee"], env)
            args = [self.eval_expr(a, env) for a in node["args"]]
            return self.call_value(callee, args, node.get("line"))
        if t == "fnexpr":
            return Fn(f"<fn@{node.get('line')}>", node["params"], node["body"],
                      env, node.get("line"))
        raise self.error("RuntimeError", f"Unknown expression {t}", node.get("line"))

    def eval_bin(self, node: dict, env: Env):
        op = node["op"]
        line = node.get("line")
        if op == "and":
            left = self.eval_expr(node["l"], env)
            return self.eval_expr(node["r"], env) if is_truthy(left) else left
        if op == "or":
            left = self.eval_expr(node["l"], env)
            return left if is_truthy(left) else self.eval_expr(node["r"], env)
        left = self.eval_expr(node["l"], env)
        right = self.eval_expr(node["r"], env)
        return self.binop(op, left, right, line)

    def binop(self, op: str, a, b, line):
        if op == "==":
            return values_equal(a, b)
        if op == "!=":
            return not values_equal(a, b)
        if op == "in":
            return self.op_in(a, b, line)
        if op in ("<", "<=", ">", ">="):
            return self.compare(op, a, b, line)
        if op == "+":
            if isinstance(a, str) or isinstance(b, str):
                if isinstance(a, str) and isinstance(b, str):
                    return a + b
                return display(a) + display(b)
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            return self.num_op(op, a, b, line)
        if op == "*":
            if isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool):
                return a * b if b > 0 else ""
            if isinstance(b, str) and isinstance(a, int) and not isinstance(a, bool):
                return b * a if a > 0 else ""
            if isinstance(a, list) and isinstance(b, int) and not isinstance(b, bool):
                return a * b if b > 0 else []
            if isinstance(b, list) and isinstance(a, int) and not isinstance(a, bool):
                return b * a if a > 0 else []
            return self.num_op(op, a, b, line)
        if op in ("-", "/", "//", "%", "**"):
            return self.num_op(op, a, b, line)
        raise self.error("RuntimeError", f"Unknown operator {op}", line)

    def num_op(self, op: str, a, b, line):
        if isinstance(a, bool) or isinstance(b, bool) \
                or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise self.error("TypeError",
                             f"Operator '{op}' needs numbers, got {type_name(a)} and {type_name(b)}",
                             line)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise self.error("ZeroDivisionError", "Division by zero", line)
            return a / b
        if op == "//":
            if b == 0:
                raise self.error("ZeroDivisionError", "Division by zero", line)
            return math.floor(a / b) if not (isinstance(a, int) and isinstance(b, int)) \
                else a // b
        if op == "%":
            if b == 0:
                raise self.error("ZeroDivisionError", "Modulo by zero", line)
            if isinstance(a, int) and isinstance(b, int):
                return a % b  # Python-style floored modulo
            r = math.fmod(a, b)
            if r != 0 and ((r < 0) != (b < 0)):
                r += b
            return r
        if op == "**":
            try:
                result = a ** b
            except OverflowError:
                raise self.error("OverflowError", "Result too large", line)
            return result
        raise self.error("RuntimeError", f"Unknown operator {op}", line)

    def compare(self, op: str, a, b, line):
        if isinstance(a, bool) or isinstance(b, bool):
            ok = False
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
            ok = True
        elif isinstance(a, str) and isinstance(b, str):
            ok = True
        else:
            ok = False
        if not ok:
            raise self.error("TypeError",
                             f"Cannot compare {type_name(a)} and {type_name(b)}", line)
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        return a >= b

    def op_in(self, needle, haystack, line):
        if isinstance(haystack, str):
            return display(needle) in haystack if not isinstance(needle, str) \
                else needle in haystack
        if isinstance(haystack, list):
            return any(values_equal(needle, item) for item in haystack)
        if isinstance(haystack, dict):
            return normalize_key(needle, self, line) in haystack
        if isinstance(haystack, RangeVal):
            if not isinstance(needle, (int, float)) or isinstance(needle, bool):
                return False
            return needle in haystack.values()
        raise self.error("TypeError",
                         f"'in' needs a list, map, string or range, got {type_name(haystack)}",
                         line)

    # ---------- indexing / attributes ----------
    def get_index(self, obj, idx, line):
        if isinstance(obj, list):
            if isinstance(idx, bool) or not isinstance(idx, (int, float)):
                raise self.error("TypeError", "List index must be a number", line)
            i = int(idx)
            if i < 0:
                i += len(obj)
            if i < 0 or i >= len(obj):
                raise self.error("IndexError", f"List index {int(idx)} out of range (len {len(obj)})", line)
            return obj[i]
        if isinstance(obj, str):
            if isinstance(idx, bool) or not isinstance(idx, (int, float)):
                raise self.error("TypeError", "String index must be a number", line)
            i = int(idx)
            if i < 0:
                i += len(obj)
            if i < 0 or i >= len(obj):
                raise self.error("IndexError", f"String index {int(idx)} out of range (len {len(obj)})", line)
            return obj[i]
        if isinstance(obj, dict):
            key = normalize_key(idx, self, line)
            return obj.get(key, None)
        raise self.error("TypeError", f"Cannot index into {type_name(obj)}", line)

    def set_index(self, obj, idx, value, line):
        if isinstance(obj, list):
            if isinstance(idx, bool) or not isinstance(idx, (int, float)):
                raise self.error("TypeError", "List index must be a number", line)
            i = int(idx)
            if i < 0:
                i += len(obj)
            if i < 0 or i >= len(obj):
                raise self.error("IndexError", f"List index {int(idx)} out of range (len {len(obj)})", line)
            obj[i] = value
            return
        if isinstance(obj, dict):
            obj[normalize_key(idx, self, line)] = value
            return
        raise self.error("TypeError", f"Cannot assign into {type_name(obj)}", line)

    def get_attr(self, obj, name, line):
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        method = find_method(obj, name)
        if method is not None:
            return BoundMethod(obj, name, method)
        if isinstance(obj, dict):
            raise self.error("KeyError", f"Map has no key '{name}'", line)
        raise self.error("AttributeError",
                         f"{type_name(obj)} has no attribute '{name}'", line)

    def set_attr(self, obj, name, value, line):
        if isinstance(obj, dict):
            obj[name] = value
            return
        raise self.error("TypeError",
                         f"Cannot set attribute '{name}' on {type_name(obj)}", line)

    # ---------- calls ----------
    def call_value(self, callee, args, line):
        if isinstance(callee, Fn):
            if len(args) != len(callee.params):
                raise self.error("TypeError",
                                 f"Function '{callee.name}' expects {len(callee.params)} "
                                 f"argument(s) but got {len(args)}", line)
            call_env = Env(callee.closure)
            for param, arg in zip(callee.params, args):
                call_env.define(param, arg)
            self.trace.append(f"{callee.name} (line {callee.line})")
            try:
                self.exec_block(callee.body, call_env)
            except ReturnSignal as ret:
                return ret.value
            finally:
                self.trace.pop()
            return None
        if isinstance(callee, Builtin):
            if callee.arity is not None and len(args) != callee.arity:
                raise self.error("TypeError",
                                 f"'{callee.name}' expects {callee.arity} argument(s) "
                                 f"but got {len(args)}", line)
            return callee.fn(self, args, line)
        if isinstance(callee, BoundMethod):
            return callee.fn(self, callee.value, args, line)
        raise self.error("TypeError", f"{type_name(callee)} is not callable", line)

    # ---------- builtins ----------
    def _make_builtins(self) -> dict:
        def _print(interp, args, line):
            interp.output(" ".join(display(a) for a in args))
            return None

        def _len(interp, args, line):
            v = args[0]
            if isinstance(v, (str, list, dict, RangeVal)):
                return len(v)
            raise interp.error("TypeError", f"len() needs a string, list, map or range, got {type_name(v)}", line)

        def _range(interp, args, line):
            nums = []
            for a in args:
                if isinstance(a, bool) or not isinstance(a, (int, float)):
                    raise interp.error("TypeError", "range() needs numbers", line)
                if float(a) != int(a):
                    raise interp.error("TypeError", "range() needs integer arguments", line)
                nums.append(int(a))
            if len(nums) == 1:
                return RangeVal(0, nums[0], 1)
            if len(nums) == 2:
                return RangeVal(nums[0], nums[1], 1)
            if len(nums) == 3:
                if nums[2] == 0:
                    raise interp.error("ValueError", "range() step must not be zero", line)
                return RangeVal(nums[0], nums[1], nums[2])
            raise interp.error("TypeError", "range() takes 1 to 3 arguments", line)

        def _str(interp, args, line):
            return display(args[0])

        def _repr(interp, args, line):
            return repr_value(args[0])

        def _int(interp, args, line):
            v = args[0]
            if isinstance(v, bool):
                return 1 if v else 0
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, str):
                try:
                    return int(v.strip(), 10)
                except ValueError:
                    try:
                        return int(float(v.strip()))
                    except ValueError:
                        raise interp.error("ValueError", f"Cannot convert '{v}' to int", line)
            raise interp.error("TypeError", f"Cannot convert {type_name(v)} to int", line)

        def _float(interp, args, line):
            v = args[0]
            if isinstance(v, bool):
                return 1.0 if v else 0.0
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                try:
                    return float(v.strip())
                except ValueError:
                    raise interp.error("ValueError", f"Cannot convert '{v}' to float", line)
            raise interp.error("TypeError", f"Cannot convert {type_name(v)} to float", line)

        def _bool(interp, args, line):
            return is_truthy(args[0])

        def _abs(interp, args, line):
            v = args[0]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise interp.error("TypeError", "abs() needs a number", line)
            return abs(v)

        def _min(interp, args, line):
            items = args[0] if (len(args) == 1 and isinstance(args[0], list)) else args
            if not items:
                raise interp.error("ValueError", "min() of empty sequence", line)
            return _extreme(interp, items, line, min)

        def _max(interp, args, line):
            items = args[0] if (len(args) == 1 and isinstance(args[0], list)) else args
            if not items:
                raise interp.error("ValueError", "max() of empty sequence", line)
            return _extreme(interp, items, line, max)

        def _extreme(interp, items, line, pick):
            best = items[0]
            for item in items[1:]:
                if pick == min:
                    if interp.binop("<", item, best, line):
                        best = item
                else:
                    if interp.binop(">", item, best, line):
                        best = item
            return best

        def _floor(interp, args, line):
            v = _num_arg(interp, args[0], "floor()", line)
            return math.floor(v)

        def _ceil(interp, args, line):
            v = _num_arg(interp, args[0], "ceil()", line)
            return math.ceil(v)

        def _round(interp, args, line):
            v = _num_arg(interp, args[0], "round()", line)
            digits = int(_num_arg(interp, args[1], "round()", line)) if len(args) > 1 else 0
            factor = 10 ** digits
            scaled = v * factor
            # round half away from zero — identical in the JS runtime
            rounded = math.floor(scaled + 0.5) if scaled >= 0 else -math.floor(-scaled + 0.5)
            result = rounded / factor
            return int(result) if digits <= 0 and float(result).is_integer() else result

        def _sqrt(interp, args, line):
            v = _num_arg(interp, args[0], "sqrt()", line)
            if v < 0:
                raise interp.error("ValueError", "sqrt() of negative number", line)
            return math.sqrt(v)

        def _pow(interp, args, line):
            a = _num_arg(interp, args[0], "pow()", line)
            b = _num_arg(interp, args[1], "pow()", line)
            return interp.num_op("**", a, b, line)

        def _type(interp, args, line):
            return type_name(args[0])

        def _push(interp, args, line):
            lst, value = args
            if not isinstance(lst, list):
                raise interp.error("TypeError", "push() needs a list", line)
            lst.append(value)
            return lst

        def _pop(interp, args, line):
            lst = args[0]
            if not isinstance(lst, list):
                raise interp.error("TypeError", "pop() needs a list", line)
            if not lst:
                raise interp.error("ValueError", "pop() from empty list", line)
            return lst.pop()

        def _insert(interp, args, line):
            lst, i, value = args
            if not isinstance(lst, list):
                raise interp.error("TypeError", "insert() needs a list", line)
            idx = _int_arg(interp, i, "insert()", line)
            if idx < 0:
                idx += len(lst)
            idx = max(0, min(idx, len(lst)))
            lst.insert(idx, value)
            return lst

        def _remove(interp, args, line):
            lst, i = args
            if not isinstance(lst, list):
                raise interp.error("TypeError", "remove() needs a list", line)
            idx = _int_arg(interp, i, "remove()", line)
            if idx < 0:
                idx += len(lst)
            if idx < 0 or idx >= len(lst):
                raise interp.error("IndexError", "remove() index out of range", line)
            return lst.pop(idx)

        def _keys(interp, args, line):
            m = args[0]
            if not isinstance(m, dict):
                raise interp.error("TypeError", "keys() needs a map", line)
            return list(m.keys())

        def _values(interp, args, line):
            m = args[0]
            if not isinstance(m, dict):
                raise interp.error("TypeError", "values() needs a map", line)
            return list(m.values())

        def _has(interp, args, line):
            m, k = args
            if not isinstance(m, dict):
                raise interp.error("TypeError", "has() needs a map", line)
            return normalize_key(k, interp, line) in m

        def _get(interp, args, line):
            m, k = args
            default = args[2] if len(args) > 2 else None
            if not isinstance(m, dict):
                raise interp.error("TypeError", "get() needs a map", line)
            return m.get(normalize_key(k, interp, line), default)

        def _sort(interp, args, line):
            lst = args[0]
            if not isinstance(lst, list):
                raise interp.error("TypeError", "sort() needs a list", line)
            return sorted(lst, key=_sort_key_fn(line))

        def _sort_by(interp, args, line):
            lst, fnv = args
            if not isinstance(lst, list):
                raise interp.error("TypeError", "sort_by() needs a list", line)
            keyed = []
            for item in lst:
                keyed.append((interp.call_value(fnv, [item], line), item))
            keyed.sort(key=lambda pair: pair[0] if isinstance(pair[0], (int, float, str))
                       and not isinstance(pair[0], bool) else 0)
            return [item for _, item in keyed]

        def _join(interp, args, line):
            lst, sep = args
            if not isinstance(lst, list):
                raise interp.error("TypeError", "join() needs a list", line)
            if not isinstance(sep, str):
                raise interp.error("TypeError", "join() separator must be a string", line)
            return sep.join(display(x) for x in lst)

        def _assert(interp, args, line):
            if not is_truthy(args[0]):
                msg = display(args[1]) if len(args) > 1 else "assertion failed"
                raise interp.error("AssertionError", msg, line)
            return None

        def _clock(interp, args, line):
            return time.perf_counter()

        def _input(interp, args, line):
            prompt = display(args[0]) if args else ""
            if interp.read_input is None:
                raise interp.error("RuntimeError", "input() is not available here", line)
            return interp.read_input(prompt)

        def _chr(interp, args, line):
            n = _int_arg(interp, args[0], "chr()", line)
            return chr(n)

        def _ord(interp, args, line):
            s = args[0]
            if not isinstance(s, str) or len(s) != 1:
                raise interp.error("TypeError", "ord() needs a single-character string", line)
            return ord(s)

        def _num_arg(interp, v, who, line):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise interp.error("TypeError", f"{who} needs a number", line)
            return v

        def _int_arg(interp, v, who, line):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise interp.error("TypeError", f"{who} needs a number", line)
            return int(v)

        def _sort_key_fn(line):
            def key(v):
                return (0, v) if isinstance(v, (int, float)) and not isinstance(v, bool) \
                    else (1, v) if isinstance(v, str) else (2, display(v))
            return key

        table = {
            "print": Builtin("print", _print, None),
            "len": Builtin("len", _len, 1),
            "range": Builtin("range", _range, None),
            "str": Builtin("str", _str, 1),
            "repr": Builtin("repr", _repr, 1),
            "int": Builtin("int", _int, 1),
            "float": Builtin("float", _float, 1),
            "bool": Builtin("bool", _bool, 1),
            "abs": Builtin("abs", _abs, 1),
            "min": Builtin("min", _min, None),
            "max": Builtin("max", _max, None),
            "floor": Builtin("floor", _floor, 1),
            "ceil": Builtin("ceil", _ceil, 1),
            "round": Builtin("round", _round, None),
            "sqrt": Builtin("sqrt", _sqrt, 1),
            "pow": Builtin("pow", _pow, 2),
            "type": Builtin("type", _type, 1),
            "push": Builtin("push", _push, 2),
            "pop": Builtin("pop", _pop, 1),
            "insert": Builtin("insert", _insert, 3),
            "remove": Builtin("remove", _remove, 2),
            "keys": Builtin("keys", _keys, 1),
            "values": Builtin("values", _values, 1),
            "has": Builtin("has", _has, 2),
            "get": Builtin("get", _get, None),
            "sort": Builtin("sort", _sort, 1),
            "sort_by": Builtin("sort_by", _sort_by, 2),
            "join": Builtin("join", _join, 2),
            "assert": Builtin("assert", _assert, None),
            "clock": Builtin("clock", _clock, 0),
            "input": Builtin("input", _input, None),
            "chr": Builtin("chr", _chr, 1),
            "ord": Builtin("ord", _ord, 1),
        }
        return table


# --------------------------------------------------------------------------
# Methods on built-in types (obj.method(...) sugar)
# --------------------------------------------------------------------------
def find_method(obj, name: str):
    """Return fn(interp, self, args, line) for a method name, or None."""
    if isinstance(obj, str):
        return STRING_METHODS.get(name)
    if isinstance(obj, list):
        return LIST_METHODS.get(name)
    if isinstance(obj, dict):
        return MAP_METHODS.get(name)
    return None


def _need_int(interp, v, who, line):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise interp.error("TypeError", f"{who} needs a number", line)
    return int(v)


def _mk_sort_key(line):
    def key(v):
        if isinstance(v, bool):
            return (2, display(v))
        if isinstance(v, (int, float)):
            return (0, float(v))
        if isinstance(v, str):
            return (1, v)
        return (2, display(v))
    return key


# ---- string methods ----
def _s_split(interp, s, args, line):
    sep = display(args[0]) if args else " "
    return s.split(sep)


def _s_repeat(interp, s, args, line):
    if not args:
        raise interp.error("TypeError", "repeat() needs a count", line)
    return s * max(0, _need_int(interp, args[0], "repeat()", line))


def _s_join(interp, s, args, line):
    if not args or not isinstance(args[0], list):
        raise interp.error("TypeError", "join() needs a list", line)
    return s.join(display(x) for x in args[0])


def _s_replace(interp, s, args, line):
    if len(args) < 2:
        raise interp.error("TypeError", "replace() needs two arguments", line)
    return s.replace(display(args[0]), display(args[1]))


def _s_index_of(interp, s, args, line):
    return s.find(display(args[0])) if args else -1


def _s_contains(interp, s, args, line):
    return display(args[0]) in s if args else False


def _s_starts_with(interp, s, args, line):
    return s.startswith(display(args[0])) if args else False


def _s_ends_with(interp, s, args, line):
    return s.endswith(display(args[0])) if args else False


def _s_to_number(interp, s, args, line):
    return _str_to_number(interp, s, line)


def _s_pad_left(interp, s, args, line):
    width = _need_int(interp, args[0], "pad_left()", line) if args else 0
    fill = display(args[1]) if len(args) > 1 else " "
    return s.rjust(width, fill if fill else " ")


def _s_pad_right(interp, s, args, line):
    width = _need_int(interp, args[0], "pad_right()", line) if args else 0
    fill = display(args[1]) if len(args) > 1 else " "
    return s.ljust(width, fill if fill else " ")


STRING_METHODS = {
    "upper": lambda interp, s, args, line: s.upper(),
    "lower": lambda interp, s, args, line: s.lower(),
    "title": lambda interp, s, args, line: s.title(),
    "trim": lambda interp, s, args, line: s.strip(),
    "chars": lambda interp, s, args, line: list(s),
    "reverse": lambda interp, s, args, line: s[::-1],
    "lines": lambda interp, s, args, line: s.split("\n"),
    "count": lambda interp, s, args, line: s.count(display(args[0])) if args else 0,
    "slice": lambda interp, s, args, line: _slice(interp, s, args, line),
    "to_number": _s_to_number,
    "repeat": _s_repeat,
    "split": _s_split,
    "join": _s_join,
    "contains": _s_contains,
    "starts_with": _s_starts_with,
    "ends_with": _s_ends_with,
    "index_of": _s_index_of,
    "replace": _s_replace,
    "pad_left": _s_pad_left,
    "pad_right": _s_pad_right,
}

# ---- list methods ----
def _l_push(interp, lst, args, line):
    lst.append(args[0])
    return lst


def _l_pop(interp, lst, args, line):
    if not lst:
        raise interp.error("ValueError", "pop() from empty list", line)
    return lst.pop()


def _l_insert(interp, lst, args, line):
    idx = _need_int(interp, args[0], "insert()", line)
    if idx < 0:
        idx += len(lst)
    lst.insert(max(0, min(idx, len(lst))), args[1])
    return lst


def _l_index_of(interp, lst, args, line):
    return _list_index_of(lst, args[0])


def _l_contains(interp, lst, args, line):
    return _list_index_of(lst, args[0]) >= 0


def _l_join(interp, lst, args, line):
    sep = display(args[0]) if args else ""
    return sep.join(display(x) for x in lst)


def _l_clear(interp, lst, args, line):
    lst.clear()
    return lst


LIST_METHODS = {
    "push": _l_push,
    "pop": _l_pop,
    "insert": _l_insert,
    "index_of": _l_index_of,
    "contains": _l_contains,
    "slice": lambda interp, lst, args, line: _slice(interp, lst, args, line),
    "join": _l_join,
    "reverse": lambda interp, lst, args, line: list(reversed(lst)),
    "sort": lambda interp, lst, args, line: sorted(lst, key=_mk_sort_key(line)),
    "first": lambda interp, lst, args, line: lst[0] if lst else None,
    "last": lambda interp, lst, args, line: lst[-1] if lst else None,
    "clear": _l_clear,
    "len": lambda interp, lst, args, line: len(lst),
}

# ---- map methods ----
def _m_has(interp, m, args, line):
    return normalize_key(args[0], interp, line) in m


def _m_get(interp, m, args, line):
    default = args[1] if len(args) > 1 else None
    return m.get(normalize_key(args[0], interp, line), default)


def _m_remove(interp, m, args, line):
    return m.pop(normalize_key(args[0], interp, line), None)


def _m_merge(interp, m, args, line):
    if not args or not isinstance(args[0], dict):
        raise interp.error("TypeError", "merge() needs a map", line)
    out = dict(m)
    out.update(args[0])
    return out


MAP_METHODS = {
    "keys": lambda interp, m, args, line: list(m.keys()),
    "values": lambda interp, m, args, line: list(m.values()),
    "has": _m_has,
    "get": _m_get,
    "remove": _m_remove,
    "merge": _m_merge,
    "len": lambda interp, m, args, line: len(m),
}


def _list_index_of(lst, needle):
    for i, item in enumerate(lst):
        if values_equal(item, needle):
            return i
    return -1


def _slice(interp, seq, args, line):
    n = len(seq)
    start = _need_int(interp, args[0], "slice()", line) if args else 0
    end = _need_int(interp, args[1], "slice()", line) if len(args) > 1 else n
    if start < 0:
        start += n
    if end < 0:
        end += n
    start = max(0, min(start, n))
    end = max(start, min(end, n))
    return seq[start:end]


def _str_to_number(interp, s, line):
    text = s.strip()
    try:
        return int(text, 10)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return None


def normalize_key(key, interp, line):
    if isinstance(key, bool):
        return key
    if isinstance(key, (int, float)):
        # unify 1 and 1.0 as the same key
        f = float(key)
        return int(f) if f.is_integer() else f
    if isinstance(key, str):
        return key
    if key is None:
        return None
    raise interp.error("TypeError",
                       f"Map keys must be numbers, strings or bools, got {type_name(key)}",
                       line)


def type_name(value) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, Fn):
        return "fn"
    if isinstance(value, Builtin):
        return "fn"
    if isinstance(value, BoundMethod):
        return "fn"
    if isinstance(value, RangeVal):
        return "range"
    return "unknown"


# --------------------------------------------------------------------------
# Convenience
# --------------------------------------------------------------------------
def run(source: str, output=None, read_input=None):
    interp = Interpreter(output=output, read_input=read_input)
    interp.run(source)
    return interp


def run_capture(source: str):
    """Run source, returning (output_text, error_or_None)."""
    lines: list[str] = []

    def output(text: str) -> None:
        lines.append(text)

    try:
        run(source, output=output)
        return "\n".join(lines), None
    except Pyv2Error as exc:
        return "\n".join(lines), exc.format()
    except ParseError as exc:
        return "\n".join(lines), f"SyntaxError: {exc.message} at line {exc.line}"
