/* Classic Python compatibility layer for the static browser Playground.
 *
 * This is intentionally honest: it translates a useful, documented subset of
 * classic Python syntax to the local Python v2 runtime. It is not CPython and
 * does not claim to provide imports, packages, native extensions, or eval.
 */
(function (global) {
  "use strict";

  const UNSUPPORTED = /^(import\b|from\b|class\b|try\s*:|except\b|finally\s*:|with\b|async\b|await\b|yield\b|global\b|nonlocal\b|match\b|case\b)/;

  function indentOf(line) {
    const prefix = (line.match(/^[ \t]*/) || [""])[0];
    return prefix.replace(/\t/g, "    ").length;
  }

  function mapTokens(line) {
    // Strings and comments are captured first and returned untouched.
    return line.replace(
      /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#.*$)|\b(True|False|None|sorted)\b|\.(strip|append)\b|\bis\s+not\b|\bis\b/g,
      (whole, protectedText, word, method) => {
        if (protectedText) return protectedText;
        if (word) return ({ True: "true", False: "false", None: "nil", sorted: "sort" })[word];
        if (method) return "." + ({ strip: "trim", append: "push" })[method];
        if (whole === "is not") return "!=";
        if (whole === "is") return "==";
        return whole;
      }
    );
  }

  function translate(source) {
    const lines = String(source).replace(/\r\n?/g, "\n").split("\n");
    const output = [];
    const blocks = [];

    lines.forEach((original, index) => {
      const trimmed = original.trim();
      if (!trimmed || trimmed.startsWith("#")) {
        output.push(original);
        return;
      }
      if (UNSUPPORTED.test(trimmed)) {
        throw new Error("line " + (index + 1) + ": " + trimmed.split(/[\s:(]/)[0] +
          " is not available in Classic compatibility mode; use local CPython for packages and full standard-library support");
      }

      const indent = indentOf(original);
      const branch = /^(elif\b|else\s*:)/.test(trimmed);
      while (blocks.length) {
        const top = blocks[blocks.length - 1];
        if (indent < top.indent || (indent === top.indent && !(branch && top.kind === "if"))) {
          output.push(" ".repeat(top.indent) + "end");
          blocks.pop();
        } else break;
      }

      let converted = mapTokens(trimmed);
      if (/^def\s+/.test(converted)) converted = converted.replace(/^def\s+/, "fn ");
      output.push(" ".repeat(indent) + converted);

      const match = converted.match(/^(fn|if|elif|else|for|while)\b.*:\s*(?:#.*)?$/);
      if (match && match[1] !== "elif" && match[1] !== "else") {
        blocks.push({ indent, kind: match[1] === "if" ? "if" : match[1] });
      }
    });

    while (blocks.length) {
      const block = blocks.pop();
      output.push(" ".repeat(block.indent) + "end");
    }
    return output.join("\n");
  }

  function runCapture(source) {
    if (!global.Pyv2) return { output: "", error: "RuntimeError: Python v2 runtime did not load", translated: "" };
    let translated;
    try {
      translated = translate(source);
    } catch (error) {
      return { output: "", error: "Classic compatibility error: " + error.message, translated: "" };
    }
    const result = global.Pyv2.runCapture(translated);
    return { output: result.output, error: result.error, translated };
  }

  global.ClassicPython = { translate, runCapture };
})(typeof window !== "undefined" ? window : globalThis);
