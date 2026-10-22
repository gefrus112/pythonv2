"use strict";

const assert = require("assert");
global.Pyv2 = require("../pyv2.js");
require("../classic-python.js");

const source = `def greet(name):
    if name == "Ada":
        return f"Hello, {name}!"
    else:
        return "Hello!"

values = []
for value in range(1, 5):
    values.append(value * value)
print(greet("Ada"))
print(sorted(values), True, False, None)`;

const result = global.ClassicPython.runCapture(source);
assert.strictEqual(result.error, null, result.error);
assert.strictEqual(result.output, "Hello, Ada!\n[1, 4, 9, 16] true false nil");
assert(result.translated.includes("fn greet(name):"));
assert(result.translated.includes("values.push"));
assert(result.translated.includes("end"));

const unsupported = global.ClassicPython.runCapture("import os\nprint(os.name)");
assert(unsupported.error.includes("not available in Classic compatibility mode"));
console.log("Classic compatibility smoke OK");
