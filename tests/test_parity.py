"""Parity tests: Python and JS runtimes must produce identical output.

Run:  python3 -m unittest tests.test_parity
Requires node on PATH.
"""

import json
import subprocess
import unittest
from pathlib import Path

from pyv2.interpreter import run_capture

ROOT = Path(__file__).resolve().parent.parent
JS_RUNNER = ROOT / "tests" / "js_runner.js"

PROGRAMS = {
    "arith": 'print(1 + 2 * 3 - 4)\nprint(10 / 4, 10 // 4, -7 // 2, -7 % 3, 2 ** 10)\nprint(0.1 + 0.2)\nprint(1e16, 1.5e-7, 4 / 2)\nprint(-2 ** 2, 2 ** 3 ** 2)',
    "fstring": 'name = "Ada"\nprint(f"Hello, {name}! {1 + 2} {2 ** 8} {{lit}}")\nprint(f"{name.upper()} {name} {len(name)}")',
    "strings": 'print("Hi There".upper(), "Hi There".lower(), "Hi There".title())\nprint("  x  ".trim(), "a,b,c".split(","), "-".join(["a", "b"]))\nprint("hello".replace("l", "L"), "hello".contains("ell"), "hello".slice(1, 3))\nprint("42".to_number() + 1, "ab".repeat(3), "a b".chars())\nprint("hello".index_of("l"), "hello".index_of("z"), "hello".count("l"))',
    "lists": 'xs = [3, 1, 2]\nxs.push(4)\nprint(xs, xs.sort(), xs.slice(1), xs[-1])\nprint([1, 2] + [3], [1, 2] * 2, len([1, 2, 3]))\nprint(xs.index_of(1), xs.contains(9), xs.first(), xs.last())\nys = [1, 2, 3]\nys[1] += 10\nprint(ys, ys.reverse(), ys.join("-"))',
    "maps": 'm = {name: "Ada", age: 36}\nm.city = "London"\nprint(m.name, m["age"], m.keys(), m.values(), m.has("name"))\nprint(m.get("z", "none"), m.get("z"))\nprint({a: 1} == {a: 1}, {a: 1} == {a: 2}, m.len())\nn = m.merge({age: 37})\nprint(m.age, n.age)',
    "flow": '''
for i in range(1, 16):
    if i % 15 == 0:
        print("FizzBuzz")
    elif i % 3 == 0:
        print("Fizz")
    elif i % 5 == 0:
        print("Buzz")
    else:
        print(i)
    end
end
i = 0
while true:
    i += 1
    if i > 5:
        break
    end
    if i % 2 == 0:
        continue
    end
    print(f"odd {i}")
end
''',
    "functions": '''
fn fib(n):
    if n < 2:
        return n
    end
    return fib(n - 1) + fib(n - 2)
end
print(fib(12))

fn make_counter():
    n = 0
    fn bump():
        n += 1
        return n
    end
    return bump
end
c = make_counter()
c()
c()
print(c())

sq = fn(x): return x * x end
print(sq(7))
''',
    "truthy": 'print(bool(0), bool(""), bool([]), bool({}), bool(nil), bool(false))\nprint(nil or "default", 1 and 2, 0 and 2, "" or 0 or "fb")\nprint(1 == 1.0, 1 == true, nil == nil, [1, [2]] == [1, [2]])',
    "builtins": 'print(abs(-5), min(3, 1, 2), max([3, 1, 2]))\nprint(floor(2.7), ceil(2.1), round(2.5), round(-2.5), sqrt(9))\nprint(int("42"), int(3.9), int(-3.9), float("2.5"), str(99))\nprint(type(1), type("a"), type([]), type({}), type(nil))\nprint(chr(65), ord("A"), sort([3, 1, 2]), join(["a", "b"], "-"))\nprint(len(range(10)), len(range(2, 10, 3)), repr("hi"), repr([1, "a"]))',
    "json": 'data = {name: "Ada", active: true, scores: [1, 2.5, nil]}\nencoded = json_encode(data)\nprint(encoded)\ncopy = json_decode(encoded)\nprint(copy.name, copy.active, copy.scores)',
    "app_basics": 'print(args())\ninfo = app_info()\nprint(info.name, info.version, info.has_assets, info.data_dir)',
    "errors": 'print(nope)',
    "errors2": 'xs = [1]\nprint(xs[5])',
    "errors3": 'print("a" - 1)',
    "errors4": 'assert(false, "boom")',
    "errors5": '''
fn inner():
    return 1 / 0
end
fn outer():
    return inner()
end
outer()
''',
    "oneline": 'fn sq(x): return x * x end\nif true: print("yes") else: print("no") end\nprint(sq(5))',
    "ternary": 'print(true ? "y" : "n", false ? "y" : "n", 200 < 300 ? "ok" : "bad")',
    "iteration": '''
m = {a: 1, b: 2}
for k in m:
    print(k)
end
for c in "abc":
    print(c)
end
xs = [1, 2, 3]
for x in xs:
    xs.push(x * 10)
end
print(xs)
for i in range(3, 0, -1):
    print(i)
end
''',
    "multiline": '''
xs = [
    1,
    2,
    3,
]
m = {
    a: 1,
    b: 2,
}
print(
    xs,
    m,
)
''',
    "nesting": '''
fn build(n):
    out = []
    for i in range(n):
        row = []
        for j in range(n):
            row.push(i * j)
        end
        out.push(row)
    end
    return out
end
print(build(3))
''',
    "edges": '''
for c in "":
    print("never")
end
print("empty string iterates zero times")
print(int("42 "), int("2.9"), int("1e3"))
print("42x".to_number(), "2.5".to_number())
print(f"{''}", "sep")
print(0 - 0.0, round(-2.5), round(2.5, 1))
''',
    "break_top": "break",
    "chain": 'if true: print(1) end print(2)\nfn f(x): return x * 2 end print(f(21))\nwhile false: 1 end print("done")',
    "scopes": '''
if true:
    grade = "B"
end
print(grade)

i = 0
while i < 3:
    if i == 0:
        log = []
    end
    log.push(i * i)
    i += 1
end
print(log)

for x in [1, 2]:
    last = x * 10
end
print(last)

fn outer():
    if true:
        fn inner(): return 7 end
    end
    return inner()
end
print(outer())

# f-string runtime errors report the real source line
fn boom():
    return f"{missing_name}"
end
print(boom())
''',
}


def run_js(source: str):
    proc = subprocess.run(
        ["node", str(JS_RUNNER)],
        input=source, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


class TestParity(unittest.TestCase):
    def check(self, name):
        source = PROGRAMS[name]
        py_out, py_err = run_capture(source)
        js = run_js(source)
        js_out, js_err = js["output"], js["error"]
        self.assertEqual(py_out, js_out, f"[{name}] output mismatch")
        if py_err is None:
            self.assertIsNone(js_err, f"[{name}] JS raised but Python did not:\n{js_err}")
        else:
            self.assertIsNotNone(js_err, f"[{name}] Python raised but JS did not:\n{py_err}")
            # Compare kind + message + line, not the whole formatted trace.
            self.assertEqual(_core(py_err), _core(js_err), f"[{name}] error mismatch")

    def test_all_programs(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name)


def _core(err_text: str):
    """First line of an error: 'Kind: message at line N'."""
    return err_text.strip().splitlines()[0] if err_text else ""


if __name__ == "__main__":
    unittest.main()
