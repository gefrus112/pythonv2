/* Shared site polish: reveal-on-scroll, progress bar, back-to-top, count-up. */
(function () {
  "use strict";

  const root = document.documentElement;
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let progress = document.getElementById("scroll-progress");
  if (!progress) {
    progress = document.createElement("div");
    progress.id = "scroll-progress";
    progress.className = "scroll-progress";
    progress.setAttribute("aria-hidden", "true");
    document.body.prepend(progress);
  }

  const topButton = document.createElement("button");
  topButton.type = "button";
  topButton.className = "back-to-top";
  topButton.setAttribute("aria-label", "Back to top");
  topButton.title = "Back to top";
  topButton.textContent = "↑";
  document.body.appendChild(topButton);
  topButton.addEventListener("click", () => window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }));

  function onScroll() {
    const max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    const ratio = Math.max(0, Math.min(1, scrollY / max));
    progress.style.transform = "scaleX(" + ratio + ")";
    topButton.classList.toggle("show", scrollY > 600);
    const nav = document.querySelector(".mainnav");
    if (nav) nav.classList.toggle("nav-scrolled", scrollY > 95);
    root.style.setProperty("--scroll-y", scrollY + "px");
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  onScroll();

  const candidates = document.querySelectorAll([
    ".section-inner > h2", ".section-inner > .lede", ".card", ".doc-card",
    ".news-card", ".start-box", ".game-title-row", ".game-stage",
    ".sprite-card", ".doc-section-inner > h2", ".steps", ".ref-table",
    ".youtube-callout", ".youtube-bottom", ".source-split", ".benchmark-note",
    ".launcher-showcase",
  ].join(","));

  if (reduceMotion || !("IntersectionObserver" in window)) {
    candidates.forEach((element) => element.classList.add("revealed"));
  } else {
    root.classList.add("has-reveal");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("revealed");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -9%", threshold: 0.08 });
    candidates.forEach((element, index) => {
      element.classList.add("reveal-item");
      element.style.setProperty("--reveal-delay", (index % 4) * 55 + "ms");
      observer.observe(element);
    });
  }

  // Animate explicitly marked integer counters once; screen readers still see
  // their final value in the data-count attribute.
  const counters = document.querySelectorAll("[data-count]");
  const countObserver = !reduceMotion && "IntersectionObserver" in window
    ? new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const node = entry.target;
          const target = Number(node.dataset.count);
          const suffix = node.dataset.suffix || "";
          const start = performance.now();
          const tick = (now) => {
            const t = Math.min(1, (now - start) / 900);
            const eased = 1 - Math.pow(1 - t, 3);
            node.textContent = Math.round(target * eased).toLocaleString() + suffix;
            if (t < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          observer.unobserve(node);
        });
      }, { threshold: 0.5 })
    : null;
  counters.forEach((node) => {
    if (countObserver) countObserver.observe(node);
    else node.textContent = Number(node.dataset.count).toLocaleString() + (node.dataset.suffix || "");
  });

  const year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
