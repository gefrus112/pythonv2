"use strict";

const assert = require("assert");

const gradient = { addColorStop() {} };
const context = {
  fillRect() {}, strokeRect() {}, beginPath() {}, closePath() {}, moveTo() {}, lineTo() {},
  arc() {}, ellipse() {}, fill() {}, stroke() {}, save() {}, restore() {}, translate() {},
  rotate() {}, scale() {}, setLineDash() {}, fillText() {}, drawImage() {},
  createLinearGradient() { return gradient; },
};
const listeners = {};
const canvas = {
  width: 0, height: 0, tabIndex: -1,
  getContext() { return context; },
  addEventListener(name, callback) { listeners[name] = callback; },
  getBoundingClientRect() { return { left: 0, top: 0, width: 800, height: 450 }; },
  focus() { global.document.activeElement = canvas; },
};
const ui = {
  "arcade-status": { textContent: "" },
  "arcade-title": { textContent: "" },
  "arcade-description": { textContent: "" },
  "arcade-badge": { textContent: "" },
  "arcade-controls": { textContent: "" },
};

global.Image = function Image() { this.complete = false; this.src = ""; };
global.requestAnimationFrame = (callback) => { global.__arcadeFrame = callback; return 1; };
global.document = {
  activeElement: null,
  getElementById(id) { return id === "arcade-canvas" ? canvas : (ui[id] || null); },
  querySelectorAll() { return []; },
};
global.window = {
  addEventListener() {},
  setTimeout(callback) { callback(); },
};

require("../arcade.js");
const arcade = global.window.PocketArcadeGame;
assert(arcade, "Pocket Arcade should initialize");
assert.strictEqual(canvas.width, 800);
assert.strictEqual(canvas.height, 450);

const modes = [
  "neon-blaster", "asteroid-drift", "target-blitz", "skybound",
  "turbo-trail", "snake-byte", "orb-breaker",
];
for (const mode of modes) {
  arcade.select(mode, false);
  arcade.update(0.016);
  arcade.draw();
  assert.strictEqual(arcade.mode, mode);
  assert(ui["arcade-status"].textContent.length > 0, mode + " should publish HUD status");
}
assert.strictEqual(Object.keys(arcade.configs).length, 7);
console.log("Pocket Arcade smoke OK: " + modes.length + " game modes rendered");
