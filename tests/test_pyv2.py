"""Tests for the Python v2 language (lexer, parser, interpreter)."""

import unittest

from pyv2.interpreter import run_capture, Interpreter, Pyv2Error
from pyv2.parser import parse, ParseError
from pyv2.lexer import tokenize, LexError


def run(src):
    out, err = run_capture(src)
    if err:
        raise AssertionError(f"program failed:\n{err}\n--- source ---\n{src}")
    return out


class TestLexer(unittest.TestCase):
    def test_tokens_basic(self):
        toks = tokenize('x = 1 + 2.5 # comment\n')
        types = [t.type for t in toks]
        self.assertEqual(types, ["IDENT", "OP", "NUMBER", "OP", "NUMBER", "NEWLINE", "EOF"])

    def test_string_escapes(self):
        toks = tokenize(r'"a\nb\t\\"')
        self.assertEqual(toks[0].value, 'a\nb\t\\')

    def test_fstring_raw(self):
        toks = tokenize('f"hi {name}"')
        self.assertEqual(toks[0].type, "FSTRING")
        self.assertEqual(toks[0].value, "hi {name}")

    def test_unterminated_string(self):
        with self.assertRaises(LexError):
            tokenize('"oops')

    def test_number_forms(self):
        toks = tokenize("1 2.5 1e3 1.5e-2")
        self.assertEqual([t.value for t in toks[:4]], [1, 2.5, 1000.0, 0.015])

    def test_keywords_vs_idents(self):
        toks = tokenize("fn end if foo")
        self.assertEqual([t.type for t in toks[:4]],
                         ["KEYWORD", "KEYWORD", "KEYWORD", "IDENT"])


class TestParser(unittest.TestCase):
    def test_assignment_and_expr(self):
        ast = parse("x = 1 + 2 * 3\n")
        node = ast["body"][0]
        self.assertEqual(node["t"], "assign")
        self.assertEqual(node["target"]["name"], "x")
        # precedence: 1 + (2 * 3)
        self.assertEqual(node["value"]["op"], "+")

    def test_power_right_assoc(self):
        ast = parse("x = 2 ** 3 ** 2\n")
        node = ast["body"][0]["value"]
        self.assertEqual(node["op"], "**")
        self.assertEqual(node["r"]["op"], "**")  # right associative

    def test_one_line_fn(self):
        ast = parse("fn sq(x): return x * x end\n")
        self.assertEqual(ast["body"][0]["t"], "fn")

    def test_chained_one_liners(self):
        self.assertEqual(run('if true: print(1) end print(2)'), "1\n2")
        self.assertEqual(run('fn f(x): return x * 2 end print(f(21))'), "42")
        self.assertEqual(run('while false: 1 end print("done")'), "done")

    def test_if_elif_else(self):
        src = """
        if a:
            1
        elif b:
            2
        else:
            3
        end
        """
        ast = parse(src)
        node = ast["body"][0]
        self.assertEqual(node["t"], "if")
        self.assertEqual(len(node["arms"]), 2)
        self.assertIsNotNone(node["else"])

    def test_try_catch_finally_and_raise_ast(self):
        ast = parse('try: raise "stop" catch error: print(error.kind) finally: print("done") end')
        node = ast["body"][0]
        self.assertEqual(node["t"], "try")
        self.assertEqual(node["catch_name"], "error")
        self.assertEqual(node["body"][0]["t"], "raise")
        self.assertIsNotNone(node["finally"])
        with self.assertRaisesRegex(ParseError, "catch or finally"):
            parse("try: print(1) end")

    def test_syntax_error_line(self):
        with self.assertRaises(ParseError) as cm:
            parse("x = = 3\n")
        self.assertEqual(cm.exception.line, 1)

    def test_map_bare_keys(self):
        ast = parse('m = {name: "x", 3: true}\n')
        pairs = ast["body"][0]["value"]["pairs"]
        self.assertEqual(pairs[0][0]["t"], "str")
        self.assertEqual(pairs[0][0]["v"], "name")
        self.assertEqual(pairs[1][0]["t"], "num")

    def test_ternary(self):
        ast = parse("x = a ? 1 : 2\n")
        self.assertEqual(ast["body"][0]["value"]["t"], "ternary")

    def test_fstring_parsing(self):
        ast = parse('s = f"a{x}b{{c}}"\n')
        node = ast["body"][0]["value"]
        self.assertEqual(node["t"], "fstr")
        kinds = [p["t"] for p in node["parts"]]
        self.assertEqual(kinds, ["str", "var", "str"])


class TestNumbers(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(run("print(1 + 2 * 3 - 4)"), "3")
        self.assertEqual(run("print(10 / 4)"), "2.5")
        self.assertEqual(run("print(10 // 4)"), "2")
        self.assertEqual(run("print(-7 // 2)"), "-4")   # floored
        self.assertEqual(run("print(-7 % 3)"), "2")     # Python-style modulo
        self.assertEqual(run("print(2 ** 10)"), "1024")
        self.assertEqual(run("print(2 ** 0.5)"), "1.4142135623730951")

    def test_whole_floats_print_clean(self):
        self.assertEqual(run("print(4 / 2)"), "2")
        self.assertEqual(run("print(2.0 * 3)"), "6")

    def test_number_display_edges(self):
        self.assertEqual(run("print(0.1 + 0.2)"), "0.30000000000000004")
        self.assertEqual(run("print(1e16)"), "1e+16")
        self.assertEqual(run("print(1.5e-7)"), "1.5e-7")

    def test_division_by_zero(self):
        with self.assertRaises(AssertionError) as cm:
            run("print(1 / 0)")
        self.assertIn("ZeroDivisionError", str(cm.exception))

    def test_unary_and_precedence(self):
        self.assertEqual(run("print(-2 ** 2)"), "-4")
        self.assertEqual(run("print((-2) ** 2)"), "4")


class TestStrings(unittest.TestCase):
    def test_concat_and_repeat(self):
        self.assertEqual(run('print("ab" + "cd")'), "abcd")
        self.assertEqual(run('print("ab" * 3)'), "ababab")
        self.assertEqual(run('print("n=" + 42)'), "n=42")

    def test_fstring(self):
        self.assertEqual(run('name = "Ada"\nprint(f"Hello, {name}!")'), "Hello, Ada!")
        self.assertEqual(run('print(f"{1 + 2} {2 ** 8}")'), "3 256")
        self.assertEqual(run('print(f"{{literal}}")'), "{literal}")

    def test_methods(self):
        self.assertEqual(run('print("Hi There".upper())'), "HI THERE")
        self.assertEqual(run('print("Hi There".lower())'), "hi there")
        self.assertEqual(run('print("  x  ".trim())'), "x")
        self.assertEqual(run('print("a,b,c".split(","))'), '["a", "b", "c"]')
        self.assertEqual(run('print("-".join(["a", "b"]))'), "a-b")
        self.assertEqual(run('print("hello".replace("l", "L"))'), "heLLo")
        self.assertEqual(run('print("hello".contains("ell"))'), "true")
        self.assertEqual(run('print("hello".starts_with("he"))'), "true")
        self.assertEqual(run('print("hello".slice(1, 3))'), "el")
        self.assertEqual(run('print("42".to_number() + 1)'), "43")
        self.assertEqual(run('print("ab".repeat(3))'), "ababab")
        self.assertEqual(run('print("a b".chars())'), '["a", " ", "b"]')


class TestControlFlow(unittest.TestCase):
    def test_if_elif_else(self):
        src = """
        fn grade(score):
            if score >= 90:
                return "A"
            elif score >= 80:
                return "B"
            else:
                return "C"
            end
        end
        print(grade(95), grade(85), grade(10))
        """
        self.assertEqual(run(src), "A B C")

    def test_while_break_continue(self):
        src = """
        i = 0
        total = 0
        while true:
            i += 1
            if i > 10:
                break
            end
            if i % 2 == 0:
                continue
            end
            total += i
        end
        print(total)
        """
        self.assertEqual(run(src), "25")

    def test_for_range(self):
        self.assertEqual(run("s = 0\nfor i in range(5): s += i end\nprint(s)"), "10")
        self.assertEqual(run("s = 0\nfor i in range(1, 11, 3): s += i end\nprint(s)"), "22")
        self.assertEqual(run("out = []\nfor i in range(3, 0, -1): out.push(i) end\nprint(out)"),
                         "[3, 2, 1]")

    def test_for_string_and_map(self):
        self.assertEqual(run('s = ""\nfor c in "abc": s += c + "." end\nprint(s)'), "a.b.c.")
        self.assertEqual(run('m = {a: 1, b: 2}\nfor k in m: print(k) end'), "a\nb")

    def test_nested_loops(self):
        src = """
        out = []
        for i in range(1, 4):
            for j in range(1, 4):
                out.push(i * j)
            end
        end
        print(out)
        """
        self.assertEqual(run(src), "[1, 2, 3, 2, 4, 6, 3, 6, 9]")

    def test_ternary(self):
        self.assertEqual(run('print(true ? "y" : "n")'), "y")
        self.assertEqual(run('print(false ? "y" : "n")'), "n")


class TestFunctions(unittest.TestCase):
    def test_recursion(self):
        src = """
        fn fact(n):
            if n <= 1:
                return 1
            end
            return n * fact(n - 1)
        end
        print(fact(10))
        """
        self.assertEqual(run(src), "3628800")

    def test_closures(self):
        src = """
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
        """
        self.assertEqual(run(src), "3")

    def test_fn_expression(self):
        self.assertEqual(run("sq = fn(x): return x * x end\nprint(sq(9))"), "81")

    def test_first_class(self):
        src = """
        fn apply(f, x):
            return f(x)
        end
        fn double(n):
            return n * 2
        end
        print(apply(double, 21))
        """
        self.assertEqual(run(src), "42")

    def test_arity_error(self):
        with self.assertRaises(AssertionError) as cm:
            run("fn f(a): return a end\nprint(f(1, 2))")
        self.assertIn("expects 1 argument", str(cm.exception))

    def test_default_return_nil(self):
        self.assertEqual(run("fn f(): 1 end\nprint(f())"), "nil")


class TestListsMaps(unittest.TestCase):
    def test_list_ops(self):
        self.assertEqual(run("xs = [1, 2]\nxs.push(3)\nprint(xs)"), "[1, 2, 3]")
        self.assertEqual(run("xs = [1, 2, 3]\nprint(xs.pop(), xs)"), "3 [1, 2]")
        self.assertEqual(run("xs = [3, 1, 2]\nprint(xs.sort())"), "[1, 2, 3]")
        self.assertEqual(run("xs = [1, 2, 3]\nprint(xs[-1], xs.slice(1))"), "3 [2, 3]")
        self.assertEqual(run("xs = [1, 2, 3]\nxs[0] = 9\nprint(xs)"), "[9, 2, 3]")
        self.assertEqual(run("xs = [1, 2, 3]\nxs[1] += 10\nprint(xs)"), "[1, 12, 3]")
        self.assertEqual(run("print([1, 2] + [3])"), "[1, 2, 3]")
        self.assertEqual(run("print([1, 2].index_of(2), [1, 2].contains(3))"), "1 false")
        self.assertEqual(run("print(len([1, 2, 3]))"), "3")

    def test_map_ops(self):
        self.assertEqual(run('m = {a: 1}\nm.b = 2\nm["c"] = 3\nprint(m)'),
                         '{"a": 1, "b": 2, "c": 3}')
        self.assertEqual(run('m = {a: 1}\nprint(m.a, m["a"], m.get("z", "none"))'),
                         "1 1 none")
        self.assertEqual(run('m = {a: 1}\nprint(m.keys(), m.values(), m.has("a"))'),
                         '["a"] [1] true')
        self.assertEqual(run('m = {a: 1}\nm.remove("a")\nprint(m)'), "{}")
        self.assertEqual(run('m = {1: "x"}\nprint(m[1.0])'), "x")  # numeric keys unify

    def test_deep_equality(self):
        self.assertEqual(run("print([1, [2]] == [1, [2]])"), "true")
        self.assertEqual(run("print({a: 1} == {a: 1})"), "true")
        self.assertEqual(run("print({a: 1} == {a: 2})"), "false")
        self.assertEqual(run("print(1 == 1.0, 1 == true, nil == nil)"), "true false true")

    def test_iteration_snapshot(self):
        src = """
        xs = [1, 2, 3]
        for x in xs:
            xs.push(x * 10)
        end
        print(xs)
        """
        self.assertEqual(run(src), "[1, 2, 3, 10, 20, 30]")


class TestTruthiness(unittest.TestCase):
    def test_python_style_truthiness(self):
        self.assertEqual(run("print(bool(0), bool(\"\"), bool([]), bool({}))"),
                         "false false false false")
        self.assertEqual(run("print(bool(nil), bool(false), bool(1), bool(\"x\"))"),
                         "false false true true")

    def test_and_or_short_circuit(self):
        self.assertEqual(run("print(nil or \"default\")"), "default")
        self.assertEqual(run("print(1 and 2)"), "2")
        self.assertEqual(run("print(0 and 2)"), "0")
        self.assertEqual(run('print("" or 0 or "fallback")'), "fallback")


class TestErrors(unittest.TestCase):
    def test_name_error(self):
        with self.assertRaises(AssertionError) as cm:
            run("print(nope)")
        self.assertIn("NameError", str(cm.exception))
        self.assertIn("line 1", str(cm.exception))

    def test_index_error(self):
        with self.assertRaises(AssertionError) as cm:
            run("xs = [1]\nprint(xs[5])")
        self.assertIn("IndexError", str(cm.exception))

    def test_type_error(self):
        with self.assertRaises(AssertionError) as cm:
            run('print("a" - 1)')
        self.assertIn("TypeError", str(cm.exception))

    def test_assert_builtin(self):
        with self.assertRaises(AssertionError) as cm:
            run('assert(false, "boom")')
        self.assertIn("AssertionError: boom", str(cm.exception))

    def test_error_in_function_reports_trace(self):
        src = """
        fn inner():
            return 1 / 0
        end
        fn outer():
            return inner()
        end
        outer()
        """
        with self.assertRaises(AssertionError) as cm:
            run(src)
        text = str(cm.exception)
        self.assertIn("ZeroDivisionError", text)
        self.assertIn("inner", text)
        self.assertIn("outer", text)

    def test_try_catch_finally_and_custom_raise(self):
        source = '''try:
    print(1 / 0)
catch error:
    print(error.kind, error.message, error.line)
finally:
    print("cleaned")
end
try: raise {kind: "ConfigError", message: "missing port"} catch issue: print(issue.kind, issue.message) end'''
        self.assertEqual(
            run(source),
            "ZeroDivisionError Division by zero 2\ncleaned\nConfigError missing port",
        )
        self.assertEqual(run('try: raise "ignored" catch: print("recovered") end'), "recovered")
        with self.assertRaises(AssertionError) as raised:
            run('raise "stop now"')
        self.assertIn("UserError: stop now", str(raised.exception))

    def test_finally_runs_for_return_and_break(self):
        source = '''fn guarded():
    try:
        return 7
    finally:
        print("return cleanup")
    end
end
print(guarded())
for i in range(3):
    try:
        break
    finally:
        print("loop cleanup")
    end
end'''
        self.assertEqual(run(source), "return cleanup\n7\nloop cleanup")

    def test_break_outside_loop_is_error(self):
        with self.assertRaises(AssertionError) as cm:
            run("break")
        self.assertIn("'break' outside of a loop", str(cm.exception))

    def test_int_requires_full_number(self):
        with self.assertRaises(AssertionError) as cm:
            run('print(int("7 apples"))')
        self.assertIn("ValueError", str(cm.exception))
        self.assertEqual(run('print(int("42 "), int("2.9"), int("1e3"))'), "42 2 1000")


class TestBuiltins(unittest.TestCase):
    def test_conversions(self):
        self.assertEqual(run('print(int("42"), float("2.5"), str(99))'), "42 2.5 99")
        self.assertEqual(run("print(int(3.9), int(-3.9))"), "3 -3")
        self.assertEqual(run('print(int("7"))'), "7")

    def test_math_helpers(self):
        self.assertEqual(run("print(abs(-5), min(3, 1, 2), max([3, 1, 2]))"), "5 1 3")
        self.assertEqual(run("print(floor(2.7), ceil(2.1), round(2.5), sqrt(9))"),
                         "2 3 3 3")

    def test_sort_and_join(self):
        self.assertEqual(run('print(sort([3, 1, 2]))'), "[1, 2, 3]")
        self.assertEqual(run('print(join(["a", "b"], "-"))'), "a-b")
        self.assertEqual(run('print(sort(["b", "a", "c"]))'), '["a", "b", "c"]')

    def test_type_name(self):
        self.assertEqual(run('print(type(1), type("a"), type([]), type({}), type(nil))'),
                         "number string list map nil")

    def test_clock(self):
        out = run("t = clock()\nprint(type(t))")
        self.assertEqual(out, "number")

    def test_range_len(self):
        self.assertEqual(run("print(len(range(10)), len(range(2, 10, 3)))"), "10 3")

    def test_sequence_helpers(self):
        source = '''print(sum(range(5)), sum([1, 2], 10))
print(enumerate(["a", "b"], 3))
print(zip([1, 2, 3], ["a", "b"]))
print(all([true, 1, "x"]), all([true, 0]), any([false, nil, 4]))'''
        self.assertEqual(
            run(source),
            '10 13\n[[3, "a"], [4, "b"]]\n[[1, "a"], [2, "b"]]\ntrue false true',
        )

    def test_chr_ord(self):
        self.assertEqual(run('print(chr(65), ord("A"))'), "A 65")


class TestSemantics(unittest.TestCase):
    def test_scoping_assign_walks_up(self):
        src = """
        n = 1
        fn bump():
            n += 1
        end
        bump()
        bump()
        print(n)
        """
        self.assertEqual(run(src), "3")

    def test_first_assignment_in_block_binds_outer(self):
        src = """
        if true:
            grade = "B"
        end
        print(grade)

        i = 0
        while i < 2:
            if i == 0:
                seen = []
            end
            seen.push(i)
            i += 1
        end
        print(seen)

        for x in [1]:
            total = x * 10
        end
        print(total)
        """
        self.assertEqual(run(src), 'B\n[0, 1]\n10')

    def test_fn_defined_in_block_is_visible_after(self):
        src = """
        if true:
            fn hello(): return "hi" end
        end
        print(hello())
        """
        self.assertEqual(run(src), "hi")

    def test_shadowing_in_block(self):
        src = """
        x = "outer"
        if true:
            x = "inner"
        end
        print(x)
        """
        self.assertEqual(run(src), "inner")

    def test_print_multiple_args(self):
        self.assertEqual(run('print("a", 1, true, nil)'), "a 1 true nil")

    def test_repr_vs_display(self):
        self.assertEqual(run('print(repr("hi"), repr([1, "a"]))'), '"hi" [1, "a"]')


class TestPrograms(unittest.TestCase):
    def test_fizzbuzz(self):
        src = """
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
        """
        out = run(src)
        self.assertEqual(out.splitlines()[0], "1")
        self.assertEqual(out.splitlines()[2], "Fizz")
        self.assertEqual(out.splitlines()[4], "Buzz")
        self.assertEqual(out.splitlines()[14], "FizzBuzz")

    def test_product_demo(self):
        src = """
        numbers = [2, 4, 6, 8]
        product = 1
        for number in numbers:
            product = product * number
        end
        print(f"The product is: {product}")
        """
        self.assertEqual(run(src), "The product is: 384")


if __name__ == "__main__":
    unittest.main()
