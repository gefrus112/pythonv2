/*
 * main.js — site behavior: syntax-highlighted REPL panel, example pager,
 * playground runner, docs search, and the CPU raycaster boot.
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Syntax highlighting (text-preserving, for the REPL panel)
  // ------------------------------------------------------------------
  const TOKEN_RE = new RegExp(
    [
      "(#[^\\n]*)",                                                     // comment
      "(f?\"(?:\\\\.|[^\"\\\\\\n])*\"|f?'(?:\\\\.|[^'\\\\\\n])*')",     // strings / f-strings
      "\\b(\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?)\\b",                     // numbers
      "\\b(fn|if|elif|else|while|for|in|return|break|continue|and|or|not|true|false|nil|end)\\b",
      "([+\\-*/%<>=!]+|[()\\[\\]{},.:?])",                               // operators / punctuation
    ].join("|"),
    "g"
  );

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(src) {
    let out = "";
    let last = 0;
    TOKEN_RE.lastIndex = 0;
    let m;
    while ((m = TOKEN_RE.exec(src)) !== null) {
      out += escapeHtml(src.slice(last, m.index));
      const text = escapeHtml(m[0]);
      if (m[1]) out += '<span class="tok-com">' + text + "</span>";
      else if (m[2]) out += '<span class="tok-str">' + text + "</span>";
      else if (m[3]) out += '<span class="tok-num">' + text + "</span>";
      else if (m[4]) out += '<span class="tok-key">' + text + "</span>";
      else if (m[5]) out += '<span class="tok-pun">' + text + "</span>";
      else out += text;
      last = m.index + m[0].length;
    }
    out += escapeHtml(src.slice(last));
    return out;
  }

  // ------------------------------------------------------------------
  // Hero carousel (5 numbered pages, python.org style)
  // ------------------------------------------------------------------
  const slides = [
    {
      title: "All the Flow You'd Expect",
      desc: "Python v2 knows the usual control flow statements that other languages " +
            "speak — <code>if</code>, <code>for</code>, <code>while</code> and " +
            "<code>range</code> — with some of its own twists, of course.",
      link: "More control flow tools",
      href: "docs.html",
      code:
`# For loop on a list
numbers = [2, 4, 6, 8]
product = 1
for number in numbers:
    product = product * number
end
print(f"The product is: {product}")`,
    },
    {
      title: "Indentation Wars: Over",
      desc: "Blocks open with <code>:</code> and close with <code>end</code>. " +
            "Not one <code>TabError</code> has ever been raised in the history " +
            "of Python v2. Neither has a <code>nonlocal</code>.",
      link: "More about functions",
      href: "docs.html",
      code:
`# Closures just work — no nonlocal required
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
print(f"count = {c()}")`,
    },
    {
      title: "F-Strings, Solved Forever",
      desc: "Interpolate any expression with plain braces — and if you need a " +
            "literal brace, <code>{{this}}</code> is how you write it. " +
            "String concatenation with numbers is legal too.",
      link: "More string tools",
      href: "docs.html",
      code:
`name = "Python v2"
print(f"Hello, {name}!")
print(f"math works here: {2 ** 8}")
print(f"{{literal braces}} survive")
print("numbers join strings: " + 42)`,
    },
    {
      title: "Data Structures That Spark Joy",
      desc: "Lists with methods that actually help, maps with bare keys and dot " +
            "access, and safe lookups when you need them. " +
            "<code>get(key, default)</code> included.",
      link: "More about maps",
      href: "docs.html",
      code:
`hero = {
    name: "Ada",
    scores: [10, 20, 30],
}
hero.scores.push(40)

print(f"{hero.name}: {hero.scores}")
print("sorted:", hero.scores.sort())
print("best:", hero.scores[-1])
print("city:", hero.get("city", "unknown"))`,
    },
    {
      title: "Recursion Without Regret",
      desc: "First-class functions, real closures, and a ternary that reads the way " +
            "you think: <code>ok ? \"yes\" : \"no\"</code>. The classics, fixed.",
      link: "More language tools",
      href: "docs.html",
      code:
`fn fib(n):
    if n < 2:
        return n
    end
    return fib(n - 1) + fib(n - 2)
end

for i in range(10):
    label = i % 2 == 0 ? "even" : "odd"
    print(f"fib({i}) = {fib(i)}  ({label})")
end`,
    },
  ];

  const codeEl = document.getElementById("code");
  const highlightEl = document.getElementById("highlight");
  const outputEl = document.getElementById("output");
  const titleEl = document.getElementById("slide-title");
  const descEl = document.getElementById("slide-desc");
  const linkEl = document.getElementById("slide-link");
  const pagerEl = document.getElementById("slide-dots");
  let current = 0;
  let timer = null;

  function refreshHighlight() {
    const src = codeEl.value;
    highlightEl.innerHTML = highlight(src) + (src.endsWith("\n") ? " " : "");
    codeEl.style.height = "auto";
    codeEl.style.height = codeEl.scrollHeight + "px";
  }

  function showSlide(i) {
    current = (i + slides.length) % slides.length;
    const s = slides[current];
    titleEl.textContent = s.title;
    descEl.innerHTML = s.desc;
    linkEl.textContent = s.link;
    linkEl.href = s.href;
    codeEl.value = s.code;
    outputEl.textContent = "";
    outputEl.classList.remove("error");
    refreshHighlight();
    [...pagerEl.children].forEach((btn, k) => {
      btn.setAttribute("aria-selected", k === current ? "true" : "false");
    });
  }

  slides.forEach((s, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = String(i + 1);
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-label", "Example " + (i + 1) + ": " + s.title);
    btn.addEventListener("click", () => {
      showSlide(i);
      restartTimer();
    });
    pagerEl.appendChild(btn);
  });

  function restartTimer() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => showSlide(current + 1), 12000);
  }
  restartTimer();

  const panelEl = document.querySelector(".hero-code");
  panelEl.addEventListener("mouseenter", () => { if (timer) clearInterval(timer); });
  panelEl.addEventListener("mouseleave", restartTimer);

  codeEl.addEventListener("input", refreshHighlight);

  // ------------------------------------------------------------------
  // Playground runner
  // ------------------------------------------------------------------
  function runCode() {
    const source = codeEl.value;
    if (typeof Pyv2 === "undefined") {
      outputEl.textContent = "Error: interpreter failed to load.";
      outputEl.classList.add("error");
      return;
    }
    const result = Pyv2.runCapture(source);
    if (result.error) {
      outputEl.textContent = (result.output ? result.output + "\n" : "") + result.error;
      outputEl.classList.add("error");
    } else {
      outputEl.textContent = result.output;
      outputEl.classList.remove("error");
    }
  }

  document.getElementById("run-btn").addEventListener("click", runCode);
  codeEl.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      runCode();
    }
  });

  const sampleCode =
`# hello.pyv2
fn greet(name):
    if name == "":
        return "Hello, stranger!"
    end
    return f"Hello, {name}!"
end

for who in ["World", ""]:
    print(greet(who))
end`;
  document.getElementById("try-btn").addEventListener("click", () => {
    codeEl.value = sampleCode;
    refreshHighlight();
    runCode();
    document.getElementById("about").scrollIntoView({ behavior: "smooth" });
  });

  // ------------------------------------------------------------------
  // Docs quick-search (live filter here, full search on docs.html)
  // ------------------------------------------------------------------
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = searchInput.value.trim();
    window.location.href = "docs.html" + (q ? "?q=" + encodeURIComponent(q) : "");
  });
  searchInput.addEventListener("input", () => filterDocs(searchInput.value));

  function filterDocs(query) {
    const q = query.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll(".doc-card").forEach((card) => {
      const haystack = (card.textContent + " " + (card.dataset.tags || "")).toLowerCase();
      const match = !q || haystack.includes(q);
      card.classList.toggle("hidden", !match);
      if (match) shown++;
    });
    const grid = document.getElementById("docs-grid");
    if (!grid) return;
    let empty = document.getElementById("docs-empty");
    if (shown === 0 && q) {
      if (!empty) {
        empty = document.createElement("p");
        empty.id = "docs-empty";
        empty.style.color = "var(--muted)";
        empty.textContent = "No docs match “" + query + "” — press GO to search the full docs.";
        grid.parentNode.insertBefore(empty, grid.nextSibling);
      } else {
        empty.textContent = "No docs match “" + query + "” — press GO to search the full docs.";
      }
    } else if (empty) {
      empty.remove();
    }
  }

  // ------------------------------------------------------------------
  // Misc
  // ------------------------------------------------------------------
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  document.getElementById("social-btn").addEventListener("click", () => {
    document.getElementById("community").scrollIntoView({ behavior: "smooth" });
  });

  // ------------------------------------------------------------------
  // CPU-rendered game
  // ------------------------------------------------------------------
  const canvas = document.getElementById("game-canvas");
  if (canvas && typeof CpuGame !== "undefined") {
    const game = new CpuGame(canvas, {
      fps: document.getElementById("hud-fps"),
      pos: document.getElementById("hud-pos"),
      kills: document.getElementById("hud-kills"),
      pixels: document.getElementById("hud-pixels"),
    });
    game.attach();
    game.start();
  }

  // first slide on boot
  showSlide(0);
})();
