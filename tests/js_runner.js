#!/usr/bin/env node
/*
 * Parity helper: read Python v2 source on stdin, run it with the JS runtime,
 * print JSON {output, error}. Used by tests/test_parity.py.
 */
const fs = require("fs");
const Pyv2 = require(__dirname + "/../site/pyv2.js");

const source = fs.readFileSync(0, "utf8");
const result = Pyv2.runCapture(source);
process.stdout.write(JSON.stringify(result));
