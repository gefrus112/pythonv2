/* Dual-mode Python v2 Playground, command terminal, and website workshop. */
(function () {
  "use strict";

  const examples = {
    "hello-v2": {
      mode: "pyv2", file: "main.pyv2",
      source: `# Python v2 quick tour
fn greet(name):
    return f"Hello, {name}!"
end

scores = [12, 19, 27]
scores.push(34)

print(greet("Playground"))
print("scores:", scores)
print("best:", max(scores))

for score in scores:
    label = score >= 20 ? "level up" : "keep going"
    print(f"{score}: {label}")
end`,
    },
    "website-v2": {
      mode: "pyv2", file: "website.pyv2", website: true,
      source: `# This Python v2 program becomes the website preview.
site = {
    title: "Comet Creative",
    tagline: "A tiny website powered by Python v2 output.",
    features: [
        "Fast browser runtime",
        "No indentation wars",
        "Downloadable as real HTML",
    ],
}

print(site.title)
print(site.tagline)
for feature in site.features:
    print(feature)
end`,
    },
    "game-v2": {
      mode: "pyv2", file: "game-data.pyv2",
      source: `# Data a PyHope game can consume.
player = {name: "Comet Pilot", hp: 100, score: 0}
enemies = [
    {name: "Null Drone", hp: 3, points: 25},
    {name: "Byte Beast", hp: 6, points: 50},
]

fn hit(enemy, damage):
    enemy.hp -= damage
    if enemy.hp <= 0:
        player.score += enemy.points
        return f"{enemy.name} cleared!"
    end
    return f"{enemy.name}: {enemy.hp} HP"
end

print(hit(enemies[0], 3))
print(f"score = {player.score}")`,
    },
    "classic-tour": {
      mode: "classic", file: "classic.py",
      source: `# Classic Python compatibility tour
# Runs locally through the documented browser subset.
def greet(name):
    if name == "":
        return "Hello, stranger!"
    else:
        return f"Hello, {name}!"

numbers = []
for value in range(1, 6):
    numbers.append(value * value)

print(greet("Classic Python"))
print("squares:", sorted(numbers))
print("ready:", True, "missing:", None)`,
    },
    "error-lab": {
      mode: "pyv2", file: "broken.pyv2",
      source: `# Run this, read the Problems terminal, then fix line 7.
fn divide(total, count):
    return total / count
end

items = []
print("average:", divide(42, len(items)))`,
    },
  };

  const code = document.getElementById("play-code");
  if (!code) return;
  const lines = document.getElementById("play-lines");
  const output = document.getElementById("play-output");
  const errors = document.getElementById("play-errors");
  const problemCount = document.getElementById("problem-count");
  const exampleSelect = document.getElementById("play-example");
  const filename = document.getElementById("play-file");
  const position = document.getElementById("editor-position");
  const modeLabel = document.getElementById("editor-mode-label");
  const compatNotice = document.getElementById("compat-notice");
  const commandForm = document.getElementById("command-form");
  const commandInput = document.getElementById("command-input");
  const commandPrompt = document.getElementById("command-prompt");
  const preview = document.getElementById("site-preview");
  let mode = "pyv2";
  let commandHistory = [];
  let historyIndex = 0;
  let sessionSource = [];
  let sessionOutput = "";
  let websiteData = {
    title: "Comet Creative",
    tagline: "A tiny website powered by Python v2 output.",
    features: ["Fast browser runtime", "No indentation wars", "Downloadable as real HTML"],
  };

  function escapeHtml(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function setRuntime(next, resetSession) {
    mode = next === "classic" ? "classic" : "pyv2";
    document.querySelectorAll("[data-runtime]").forEach((button) => {
      const active = button.dataset.runtime === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    modeLabel.textContent = mode === "pyv2" ? "PYTHON V2" : "CLASSIC PYTHON • COMPAT";
    commandPrompt.textContent = mode === "pyv2" ? "v2>" : "py>";
    commandInput.placeholder = mode === "pyv2" ? 'Try: print("hello") or 6 * 7' : 'Try: print("hello") or 6 * 7';
    compatNotice.hidden = mode !== "classic";
    if (resetSession !== false) resetCommandSession(false);
  }

  function refreshEditor() {
    const count = Math.max(1, code.value.split("\n").length);
    lines.textContent = Array.from({ length: count }, (_, index) => index + 1).join("\n");
    const before = code.value.slice(0, code.selectionStart);
    const row = before.split("\n");
    position.textContent = "Ln " + row.length + ", Col " + (row[row.length - 1].length + 1);
    lines.scrollTop = code.scrollTop;
  }

  function setProblems(error) {
    if (error) {
      errors.textContent = error;
      errors.classList.add("has-error");
      problemCount.textContent = "1 error";
    } else {
      errors.textContent = "No problems detected.";
      errors.classList.remove("has-error");
      problemCount.textContent = "0 errors";
    }
  }

  function execute(source) {
    if (mode === "classic") return window.ClassicPython.runCapture(source);
    if (!window.Pyv2) return { output: "", error: "RuntimeError: Python v2 runtime failed to load" };
    return window.Pyv2.runCapture(source);
  }

  function previewHtml(data) {
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
      *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:36px;font:16px system-ui;color:#edf6ff;background:radial-gradient(circle at 80% 0,#315f92,#132538 62%)}
      main{width:min(680px,100%);padding:44px;border:1px solid #ffffff2b;border-radius:25px;background:#102131db;box-shadow:0 30px 70px #07101d88}.tag{color:#70d6ff;font-size:12px;font-weight:900;letter-spacing:.13em}h1{margin:8px 0 7px;color:#ffd343;font-size:clamp(38px,8vw,67px);line-height:1}.lead{color:#c5d9e8;font-size:19px}.grid{display:grid;gap:10px;margin-top:25px}.item{padding:13px 16px;border-left:4px solid #d64541;border-radius:7px;background:#ffffff0c}
    </style></head><body><main><div class="tag">BUILT WITH PYTHON V2</div><h1>${escapeHtml(data.title)}</h1><p class="lead">${escapeHtml(data.tagline)}</p><div class="grid">${data.features.map((item) => '<div class="item">' + escapeHtml(item) + '</div>').join("")}</div></main></body></html>`;
  }

  function updateWebsitePreview(resultOutput) {
    const values = resultOutput.split("\n").filter((line) => line.trim() !== "");
    if (values.length >= 2) {
      websiteData = { title: values[0], tagline: values[1], features: values.slice(2) };
    }
    preview.srcdoc = previewHtml(websiteData);
  }

  function runProgram() {
    const started = performance.now();
    const result = execute(code.value);
    const took = Math.max(.1, performance.now() - started).toFixed(1);
    if (result.error) {
      output.textContent = result.output || "Program stopped before producing output.";
      setProblems(result.error);
    } else {
      output.textContent = result.output || "✓ Program finished with no output.";
      output.textContent += "\n\n— finished in " + took + " ms • " + (mode === "pyv2" ? "Python v2" : "Classic compatibility");
      setProblems(null);
      if (examples[exampleSelect.value] && examples[exampleSelect.value].website) updateWebsitePreview(result.output);
    }
  }

  function loadExample(name, focus) {
    const example = examples[name] || examples["hello-v2"];
    exampleSelect.value = name in examples ? name : "hello-v2";
    code.value = example.source;
    filename.textContent = example.file;
    setRuntime(example.mode);
    refreshEditor();
    output.textContent = "Loaded " + example.file + ". Press Run when ready.";
    setProblems(null);
    if (example.website) updateWebsitePreview("Comet Creative\nA tiny website powered by Python v2 output.\nFast browser runtime\nNo indentation wars\nDownloadable as real HTML");
    if (focus) { code.focus(); code.setSelectionRange(0, 0); }
  }

  function download(filenameValue, content, type) {
    const blob = new Blob([content], { type: type || "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = filenameValue; document.body.appendChild(anchor); anchor.click(); anchor.remove();
    URL.revokeObjectURL(url);
  }

  function resetCommandSession(announce) {
    sessionSource = [];
    sessionOutput = "";
    if (announce !== false) output.textContent += "\n\nCommand session reset.";
  }

  function commandSource(raw) {
    const statement = /^(print\s*\(|assert\s*\(|return\b|break\b|continue\b|if\b|for\b|while\b|fn\b|def\b)/.test(raw) ||
      /^[A-Za-z_]\w*\s*=(?!=)/.test(raw) || /^(#|$)/.test(raw);
    return statement ? raw : "print(" + raw + ")";
  }

  function runCommand(raw) {
    const value = raw.trim();
    if (!value) return;
    if (value === ":clear") {
      output.textContent = "Terminal cleared."; setProblems(null); return;
    }
    if (value === ":reset") { resetCommandSession(true); setProblems(null); return; }
    if (value === ":help") {
      output.textContent += "\n\nCommands: :help, :clear, :reset, :mode pyv2, :mode classic\nExpressions are printed automatically. Successful assignments remain available in this command session.";
      return;
    }
    if (value.startsWith(":mode ")) {
      const requested = value.slice(6).trim();
      if (["pyv2", "classic"].includes(requested)) {
        setRuntime(requested); output.textContent += "\n\nSwitched command runtime to " + requested + ". Session reset.";
      } else setProblems("CommandError: choose :mode pyv2 or :mode classic");
      return;
    }

    const nextLine = commandSource(value);
    const candidate = sessionSource.concat(nextLine).join("\n");
    const result = execute(candidate);
    output.textContent += "\n\n" + commandPrompt.textContent + " " + value;
    if (result.error) {
      setProblems(result.error);
      output.textContent += "\nCommand failed; session was not changed.";
      return;
    }
    const delta = result.output.startsWith(sessionOutput) ? result.output.slice(sessionOutput.length).replace(/^\n/, "") : result.output;
    output.textContent += "\n" + (delta || "✓ stored");
    sessionSource.push(nextLine);
    sessionOutput = result.output;
    setProblems(null);
  }

  document.querySelectorAll("[data-runtime]").forEach((button) => {
    button.addEventListener("click", () => setRuntime(button.dataset.runtime));
  });
  exampleSelect.addEventListener("change", () => loadExample(exampleSelect.value, false));
  document.getElementById("play-run").addEventListener("click", runProgram);
  document.getElementById("play-reset").addEventListener("click", () => loadExample(exampleSelect.value, true));
  document.getElementById("play-download").addEventListener("click", () => download(filename.textContent, code.value));
  document.getElementById("terminal-clear").addEventListener("click", () => { output.textContent = "Terminals cleared."; setProblems(null); });
  document.getElementById("load-website-template").addEventListener("click", () => {
    loadExample("website-v2", true);
    document.getElementById("workspace").scrollIntoView({ behavior: "smooth" });
  });
  document.getElementById("download-website").addEventListener("click", () => download("python-v2-website.html", previewHtml(websiteData), "text/html;charset=utf-8"));

  code.addEventListener("input", refreshEditor);
  code.addEventListener("click", refreshEditor);
  code.addEventListener("keyup", refreshEditor);
  code.addEventListener("scroll", () => { lines.scrollTop = code.scrollTop; });
  code.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
      event.preventDefault();
      const start = code.selectionStart, end = code.selectionEnd;
      code.setRangeText("    ", start, end, "end"); refreshEditor();
    }
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); runProgram(); }
  });

  commandForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = commandInput.value;
    if (!value.trim()) return;
    commandHistory.push(value); historyIndex = commandHistory.length;
    runCommand(value); commandInput.value = "";
  });
  commandInput.addEventListener("keydown", (event) => {
    if (event.key === "ArrowUp" && commandHistory.length) {
      event.preventDefault(); historyIndex = Math.max(0, historyIndex - 1); commandInput.value = commandHistory[historyIndex] || "";
    } else if (event.key === "ArrowDown" && commandHistory.length) {
      event.preventDefault(); historyIndex = Math.min(commandHistory.length, historyIndex + 1); commandInput.value = commandHistory[historyIndex] || "";
    }
  });

  preview.srcdoc = previewHtml(websiteData);
  loadExample("hello-v2", false);
})();
