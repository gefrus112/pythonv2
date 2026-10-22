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
      mode: "pyv2", file: "portfolio.pyv2", website: true,
      source: `# Hybrid personal profile + portfolio website.
# Edit this data, press Ctrl+Enter, then inspect Preview or HTML Code.
profile = {
    name: "Alex Comet",
    role: "Creative developer & game maker",
    tagline: "I turn curious ideas into playful, useful digital experiences.",
    bio: "I build expressive websites, lightweight tools, and original games. My work mixes clean engineering with colorful interaction.",
    location: "Massachusetts, USA",
    email: "hello@example.com",
    availability: "Available for select projects",
}

skills = ["Python v2", "PyHope", "Web design", "Canvas games", "Creative coding", "UI systems"]
stats = [
    {value: "10", label: "Playable games"},
    {value: "8", label: "Open assets"},
    {value: "112+", label: "Passing tests"},
]
projects = [
    {title: "Python v2", kind: "Language", description: "A friendlier Python remake with browser and desktop runtimes.", link: "https://github.com/gefrus112/pythonv2"},
    {title: "PyHope Arcade", kind: "Games", description: "Ten original shooters, platformers, racers, and arcade experiments.", link: "https://gefrus112.github.io/pythonv2/games.html"},
    {title: "Sudbury Studio", kind: "Desktop", description: "A lightweight workspace for code, files, assets, editors, and previews.", link: "https://gefrus112.github.io/pythonv2/download.html#app"},
]
games = [
    {title: "Neon Blaster", genre: "Wave shooter", description: "Pilot the Comet through a neon drone attack.", link: "https://gefrus112.github.io/pythonv2/games.html#pocket-arcade"},
    {title: "Comet Hopper", genre: "Platformer", description: "Collect Hope Bits across a Python v2-generated level.", link: "https://gefrus112.github.io/pythonv2/games.html#comet-hopper"},
    {title: "Comet Circuit", genre: "Racing", description: "Race AI drivers around a generated three-lap circuit.", link: "https://gefrus112.github.io/pythonv2/games.html#comet-circuit"},
]

print("PROFILE|" + profile.name + "|" + profile.role + "|" + profile.tagline)
print("ABOUT|" + profile.bio)
print("CONTACT|" + profile.location + "|" + profile.email + "|" + profile.availability)
for skill in skills:
    print("SKILL|" + skill)
end
for stat in stats:
    print("STAT|" + stat.value + "|" + stat.label)
end
for project in projects:
    print("PROJECT|" + project.title + "|" + project.kind + "|" + project.description + "|" + project.link)
end
for game in games:
    print("GAME|" + game.title + "|" + game.genre + "|" + game.description + "|" + game.link)
end`,
    },
    "app-v2": {
      mode: "pyv2", file: "comet-notes.pyv2",
      source: `# Production app data model — this part runs in browser and desktop.
# Download it, then use: pyv2 build comet-notes.pyv2
info = app_info()
settings = {
    app_name: "Comet Notes",
    version: "1.0.0",
    theme: "night",
    autosave: true,
}
notes = [
    {title: "Design the app", done: true},
    {title: "Build the Windows EXE", done: false},
]

encoded = json_encode({settings: settings, notes: notes})
restored = json_decode(encoded)
print(restored.settings.app_name, "v" + restored.settings.version)
for note in restored.notes:
    print(note.done ? "[x]" : "[ ]", note.title)
end
print("platform:", info.platform)
print("Next: download source, run 'pyv2 new windows-app', then 'pyv2 build'.")
# Desktop/EXE apps also get safe read_text, write_text, assets, args, and dialogs.`,
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
    "recovery-v2": {
      mode: "pyv2", file: "resilient-app.pyv2",
      source: `# Structured recovery keeps expected failures inside your app.
fn load_port(raw):
    if raw == "":
        raise {kind: "ConfigError", message: "port is required"}
    end
    return int(raw)
end

inputs = ["8080", "", "not-a-number"]
for raw in inputs:
    try:
        port = load_port(raw)
        print("ready on port", port)
    catch error:
        print(error.kind + ":", error.message, "at line", error.line)
    finally:
        print("checked input", repr(raw))
    end
end

print("total:", sum([2, 4, 6]))
print("numbered:", enumerate(["red", "blue"], 1))`,
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
  const previewPane = document.getElementById("site-render-pane");
  const htmlSource = document.querySelector("#site-html-source code");
  const htmlSourcePanel = document.getElementById("site-html-source");
  const syncStatus = document.getElementById("template-sync-status");
  let mode = "pyv2";
  let commandHistory = [];
  let historyIndex = 0;
  let sessionSource = [];
  let sessionOutput = "";
  let livePreviewTimer = null;
  let generatedWebsiteHtml = "";
  let websiteData = {
    name: "Alex Comet",
    role: "Creative developer & game maker",
    tagline: "I turn curious ideas into playful, useful digital experiences.",
    bio: "I build expressive websites, lightweight tools, and original games. My work mixes clean engineering with colorful interaction.",
    location: "Massachusetts, USA",
    email: "hello@example.com",
    availability: "Available for select projects",
    skills: ["Python v2", "PyHope", "Web design", "Canvas games", "Creative coding", "UI systems"],
    stats: [{ value: "10", label: "Playable games" }, { value: "8", label: "Open assets" }, { value: "112+", label: "Passing tests" }],
    projects: [
      { title: "Python v2", kind: "Language", description: "A friendlier Python remake with browser and desktop runtimes.", link: "https://github.com/gefrus112/pythonv2" },
      { title: "PyHope Arcade", kind: "Games", description: "Ten original shooters, platformers, racers, and arcade experiments.", link: "https://gefrus112.github.io/pythonv2/games.html" },
      { title: "Sudbury Studio", kind: "Desktop", description: "A lightweight workspace for code, files, assets, editors, and previews.", link: "https://gefrus112.github.io/pythonv2/download.html#app" },
    ],
    games: [
      { title: "Neon Blaster", genre: "Wave shooter", description: "Pilot the Comet through a neon drone attack.", link: "https://gefrus112.github.io/pythonv2/games.html#pocket-arcade" },
      { title: "Comet Hopper", genre: "Platformer", description: "Collect Hope Bits across a Python v2-generated level.", link: "https://gefrus112.github.io/pythonv2/games.html#comet-hopper" },
      { title: "Comet Circuit", genre: "Racing", description: "Race AI drivers around a generated three-lap circuit.", link: "https://gefrus112.github.io/pythonv2/games.html#comet-circuit" },
    ],
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

  function safeUrl(value) {
    const url = String(value || "").trim();
    return /^(https?:\/\/|mailto:|#|[./]?[A-Za-z0-9_-]+\.html(?:#[-\w]+)?)$/.test(url) ? escapeHtml(url) : "#";
  }

  function previewHtml(data) {
    const initials = data.name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "PV";
    const skills = data.skills.map((skill) => '<span class="skill">' + escapeHtml(skill) + '</span>').join("");
    const stats = data.stats.map((stat) => '<div class="stat"><strong>' + escapeHtml(stat.value) + '</strong><span>' + escapeHtml(stat.label) + '</span></div>').join("");
    const projects = data.projects.map((project, index) => `<article class="project p${index % 3}"><div class="project-top"><span>${escapeHtml(project.kind)}</span><b>0${index + 1}</b></div><h3>${escapeHtml(project.title)}</h3><p>${escapeHtml(project.description)}</p><a href="${safeUrl(project.link)}" target="_blank" rel="noopener">View project <i>↗</i></a></article>`).join("");
    const games = data.games.map((game, index) => `<a class="game" href="${safeUrl(game.link)}" target="_blank" rel="noopener"><span class="game-icon">${["✦", "▲", "◆"][index % 3]}</span><small>${escapeHtml(game.genre)}</small><h3>${escapeHtml(game.title)}</h3><p>${escapeHtml(game.description)}</p><b>Play now →</b></a>`).join("");
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="${escapeHtml(data.tagline)}">
  <title>${escapeHtml(data.name)} — ${escapeHtml(data.role)}</title>
  <style>
    :root{--ink:#122334;--muted:#627486;--paper:#f7f8f5;--night:#101d2a;--blue:#2f6fbd;--cyan:#70d6ff;--red:#d64541;--yellow:#ffd343;--line:#dce3e7}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:var(--ink);background:var(--paper);font:16px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}a{color:inherit;text-decoration:none}.wrap{width:min(1120px,calc(100% - 40px));margin:auto}.nav{position:sticky;z-index:10;top:0;border-bottom:1px solid #ffffff18;background:#101d2aee;backdrop-filter:blur(15px)}.nav .wrap{display:flex;align-items:center;gap:24px;min-height:68px}.brand{display:flex;align-items:center;gap:10px;margin-right:auto;color:#fff;font-weight:900}.brand i{display:grid;place-items:center;width:35px;height:35px;border-radius:11px;color:var(--night);background:linear-gradient(135deg,var(--cyan),var(--yellow));font-style:normal}.nav a:not(.brand){color:#b9cad7;font-size:13px;font-weight:750}.nav a:hover{color:#fff}.hero{position:relative;overflow:hidden;color:#fff;background:radial-gradient(700px 430px at 85% 8%,#2f6fbd88,transparent 64%),radial-gradient(440px 330px at 10% 95%,#d6454155,transparent 70%),var(--night)}.hero:after{content:"";position:absolute;inset:0;opacity:.12;background-image:linear-gradient(#ffffff22 1px,transparent 1px),linear-gradient(90deg,#ffffff22 1px,transparent 1px);background-size:46px 46px;mask-image:linear-gradient(to bottom,#000,transparent)}.hero-grid{position:relative;z-index:1;display:grid;grid-template-columns:1.35fr .65fr;gap:60px;align-items:center;min-height:650px;padding:88px 0}.available{display:inline-flex;align-items:center;gap:9px;padding:7px 11px;border:1px solid #ffffff2b;border-radius:99px;color:#c9d9e5;background:#ffffff0b;font-size:12px;font-weight:800}.available i{width:8px;height:8px;border-radius:50%;background:#54da84;box-shadow:0 0 12px #54da84}.kicker{margin:27px 0 7px;color:var(--cyan);font-size:12px;font-weight:900;letter-spacing:.15em;text-transform:uppercase}.hero h1{max-width:760px;margin:0;font-size:clamp(52px,8vw,92px);line-height:.92;letter-spacing:-.055em}.hero h1 em{color:var(--yellow);font-style:normal}.lead{max-width:700px;margin:25px 0;color:#c4d5e1;font-size:clamp(18px,2.3vw,23px)}.actions{display:flex;gap:11px;flex-wrap:wrap;margin-top:30px}.button{padding:13px 19px;border:1px solid #ffffff2e;border-radius:9px;color:#fff;background:#ffffff0b;font-weight:850}.button.primary{color:var(--night);border-color:var(--yellow);background:var(--yellow)}.profile-card{position:relative;padding:24px;border:1px solid #ffffff22;border-radius:28px;background:#ffffff0b;box-shadow:0 32px 70px #050c1488;transform:rotate(2deg)}.avatar{display:grid;place-items:center;aspect-ratio:1;border-radius:22px;color:#fff;background:linear-gradient(145deg,var(--blue),#8f2c52);font-size:clamp(64px,9vw,108px);font-weight:950;letter-spacing:-.08em}.profile-card p{margin:17px 0 0;color:#bcd0df}.profile-card strong{display:block;color:var(--yellow)}.stats{position:relative;z-index:2;display:grid;grid-template-columns:repeat(3,1fr);margin-top:-1px;border-bottom:1px solid var(--line);background:#fff}.stat{padding:28px;text-align:center;border-right:1px solid var(--line)}.stat:last-child{border:0}.stat strong{display:block;color:var(--blue);font-size:30px}.stat span{color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.section{padding:90px 0}.section.alt{background:#fff}.section-head{display:flex;align-items:end;justify-content:space-between;gap:30px;margin-bottom:34px}.eyebrow{color:var(--blue);font-size:11px;font-weight:950;letter-spacing:.15em;text-transform:uppercase}.section h2{max-width:700px;margin:5px 0 0;font-size:clamp(34px,5vw,54px);line-height:1;letter-spacing:-.035em}.about-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:70px}.about-copy{color:#44586a;font-size:20px}.skills{display:flex;align-content:flex-start;gap:9px;flex-wrap:wrap}.skill{padding:9px 13px;border:1px solid #cbd7df;border-radius:99px;color:#31516b;background:#fff;font-size:13px;font-weight:800}.project-grid,.game-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:17px}.project{min-height:285px;padding:25px;border:1px solid var(--line);border-radius:18px;background:var(--paper);transition:.25s}.project:hover,.game:hover{transform:translateY(-6px);box-shadow:0 18px 45px #172d3e1c}.project-top{display:flex;justify-content:space-between;color:var(--blue);font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.1em}.project-top b{color:#a9b6c0;font:900 22px ui-monospace}.project h3,.game h3{margin:45px 0 8px;font-size:24px}.project p,.game p{color:var(--muted)}.project a{display:inline-block;margin-top:15px;color:var(--blue);font-weight:900}.p0{border-top:5px solid var(--blue)}.p1{border-top:5px solid var(--red)}.p2{border-top:5px solid #44a36f}.games{color:#fff;background:var(--night)}.games .eyebrow{color:var(--yellow)}.game{position:relative;overflow:hidden;min-height:295px;padding:25px;border:1px solid #ffffff20;border-radius:18px;background:linear-gradient(145deg,#ffffff10,#ffffff05);transition:.25s}.game:after{content:"";position:absolute;right:-35px;bottom:-55px;width:140px;height:140px;border-radius:50%;background:var(--blue);filter:blur(8px);opacity:.2}.game-icon{display:grid;place-items:center;width:53px;height:53px;border-radius:14px;color:var(--night);background:var(--yellow);font-size:22px}.game small{display:block;margin-top:20px;color:var(--cyan);font-weight:900;text-transform:uppercase;letter-spacing:.1em}.game h3{margin:3px 0 7px}.game p{color:#b8cad8}.game b{position:absolute;z-index:1;bottom:23px;color:var(--yellow)}.contact{padding:90px 0}.contact-card{display:grid;grid-template-columns:1fr auto;gap:30px;align-items:center;padding:45px;border-radius:25px;color:#fff;background:linear-gradient(120deg,var(--blue),#234d76 55%,#8f2c52);box-shadow:0 25px 60px #183b5c33}.contact-card h2{margin:0 0 8px;font-size:clamp(31px,5vw,52px)}.contact-card p{margin:0;color:#d8e5ef}.contact-card .button{white-space:nowrap;background:#fff;color:var(--blue)}footer{padding:25px 0;color:#8093a3;border-top:1px solid var(--line);font-size:13px}footer .wrap{display:flex;justify-content:space-between;gap:20px}@media(max-width:800px){.hero-grid,.about-grid{grid-template-columns:1fr}.hero-grid{padding:65px 0}.profile-card{max-width:390px;transform:none}.project-grid,.game-grid{grid-template-columns:1fr}.section-head{display:block}.contact-card{grid-template-columns:1fr}.nav a:not(.brand){display:none}}@media(max-width:520px){.wrap{width:min(100% - 24px,1120px)}.hero h1{font-size:48px}.stats{grid-template-columns:1fr}.stat{border-right:0;border-bottom:1px solid var(--line)}.section{padding:65px 0}.contact-card{padding:28px}}@media(prefers-reduced-motion:no-preference){.hero-copy{animation:rise .7s ease both}.profile-card{animation:rise .8s .12s ease both}.project,.game{animation:rise .55s ease both}@keyframes rise{from{opacity:0;transform:translateY(22px)}}}
  </style>
</head>
<body>
  <nav class="nav"><div class="wrap"><a class="brand" href="#top"><i>${escapeHtml(initials)}</i>${escapeHtml(data.name)}</a><a href="#about">About</a><a href="#work">Work</a><a href="#games">Games</a><a href="#contact">Contact</a></div></nav>
  <header class="hero" id="top"><div class="wrap hero-grid"><div class="hero-copy"><span class="available"><i></i>${escapeHtml(data.availability)}</span><p class="kicker">${escapeHtml(data.role)}</p><h1>Hi, I’m <em>${escapeHtml(data.name)}</em>.</h1><p class="lead">${escapeHtml(data.tagline)}</p><div class="actions"><a class="button primary" href="#work">See my work</a><a class="button" href="#contact">Let’s talk</a></div></div><aside class="profile-card"><div class="avatar">${escapeHtml(initials)}</div><p><strong>${escapeHtml(data.location)}</strong>${escapeHtml(data.role)}</p></aside></div></header>
  <div class="stats">${stats}</div>
  <main>
    <section class="section" id="about"><div class="wrap"><div class="section-head"><div><span class="eyebrow">About me</span><h2>Design-minded code with a playful edge.</h2></div></div><div class="about-grid"><p class="about-copy">${escapeHtml(data.bio)}</p><div class="skills">${skills}</div></div></div></section>
    <section class="section alt" id="work"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Selected work</span><h2>Projects built to be useful and memorable.</h2></div><p>Personal work, open source, and creative experiments.</p></div><div class="project-grid">${projects}</div></div></section>
    <section class="section games" id="games"><div class="wrap"><div class="section-head"><div><span class="eyebrow">Playable work</span><h2>Games I designed and shipped.</h2></div><p>Built with Python v2 and the PyHope engine.</p></div><div class="game-grid">${games}</div></div></section>
    <section class="contact" id="contact"><div class="wrap"><div class="contact-card"><div><span class="eyebrow">Start a conversation</span><h2>Have a project in mind?</h2><p>${escapeHtml(data.availability)} • ${escapeHtml(data.location)}</p></div><a class="button" href="mailto:${escapeHtml(data.email)}">${escapeHtml(data.email)}</a></div></div></section>
  </main>
  <footer><div class="wrap"><span>© ${new Date().getFullYear()} ${escapeHtml(data.name)}</span><span>Built from a Python v2 starter template.</span></div></footer>
</body>
</html>`;
  }

  function parseWebsiteOutput(resultOutput) {
    const next = { ...websiteData, skills: [], stats: [], projects: [], games: [] };
    resultOutput.split("\n").filter(Boolean).forEach((line) => {
      const parts = line.split("|");
      const type = parts.shift();
      if (type === "PROFILE" && parts.length >= 3) [next.name, next.role, next.tagline] = parts;
      else if (type === "ABOUT") next.bio = parts.join("|");
      else if (type === "CONTACT" && parts.length >= 3) [next.location, next.email, next.availability] = parts;
      else if (type === "SKILL") next.skills.push(parts.join("|"));
      else if (type === "STAT" && parts.length >= 2) next.stats.push({ value: parts[0], label: parts.slice(1).join("|") });
      else if (type === "PROJECT" && parts.length >= 4) next.projects.push({ title: parts[0], kind: parts[1], description: parts[2], link: parts.slice(3).join("|") });
      else if (type === "GAME" && parts.length >= 4) next.games.push({ title: parts[0], genre: parts[1], description: parts[2], link: parts.slice(3).join("|") });
    });
    return next;
  }

  function updateWebsitePreview(resultOutput) {
    websiteData = parseWebsiteOutput(resultOutput);
    generatedWebsiteHtml = previewHtml(websiteData);
    preview.srcdoc = generatedWebsiteHtml;
    htmlSource.textContent = generatedWebsiteHtml;
    syncStatus.innerHTML = "<i></i> Preview synced • " + websiteData.projects.length + " projects • " + websiteData.games.length + " games";
  }

  function runProgram() {
    const started = performance.now();
    const result = execute(code.value);
    const took = Math.max(.1, performance.now() - started).toFixed(1);
    if (result.error) {
      output.textContent = result.output || "Program stopped before producing output.";
      setProblems(result.error);
      if (examples[exampleSelect.value] && examples[exampleSelect.value].website) {
        syncStatus.innerHTML = "<i class=\"sync-error\"></i> Preview paused • fix the Problems terminal";
      }
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
    if (example.website) {
      const result = execute(example.source);
      if (!result.error) updateWebsitePreview(result.output);
    }
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
  document.getElementById("download-website").addEventListener("click", () => download("personal-portfolio.html", generatedWebsiteHtml || previewHtml(websiteData), "text/html;charset=utf-8"));
  document.getElementById("copy-website-html").addEventListener("click", async () => {
    const text = generatedWebsiteHtml || previewHtml(websiteData);
    try {
      await navigator.clipboard.writeText(text);
      syncStatus.innerHTML = "<i></i> HTML copied to clipboard";
    } catch (_error) {
      const helper = document.createElement("textarea");
      helper.value = text; helper.style.position = "fixed"; helper.style.opacity = "0";
      document.body.appendChild(helper); helper.select(); document.execCommand("copy"); helper.remove();
      syncStatus.innerHTML = "<i></i> HTML copied to clipboard";
    }
  });
  document.querySelectorAll("[data-site-view]").forEach((button) => {
    button.addEventListener("click", () => {
      const showHtml = button.dataset.siteView === "html";
      previewPane.hidden = showHtml;
      htmlSourcePanel.hidden = !showHtml;
      document.querySelectorAll("[data-site-view]").forEach((item) => item.classList.toggle("active", item === button));
    });
  });
  document.querySelectorAll("[data-preview-size]").forEach((button) => {
    button.addEventListener("click", () => {
      previewPane.className = "site-render-pane preview-" + button.dataset.previewSize;
      document.querySelectorAll("[data-preview-size]").forEach((item) => item.classList.toggle("active", item === button));
    });
  });

  code.addEventListener("input", () => {
    refreshEditor();
    if (exampleSelect.value !== "website-v2" || mode !== "pyv2") return;
    clearTimeout(livePreviewTimer);
    syncStatus.innerHTML = "<i></i> Waiting for a valid edit…";
    livePreviewTimer = setTimeout(runProgram, 550);
  });
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

  generatedWebsiteHtml = previewHtml(websiteData);
  preview.srcdoc = generatedWebsiteHtml;
  htmlSource.textContent = generatedWebsiteHtml;
  loadExample("hello-v2", false);

  window.PythonV2PortfolioTemplate = { previewHtml, parseWebsiteOutput };
})();
