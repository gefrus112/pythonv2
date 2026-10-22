/*
 * game.js — a Wolfenstein-style raycasting engine with a hard rule:
 * EVERY pixel is computed on the CPU into an ImageData framebuffer.
 * No WebGL, no GPU draws, no CSS tricks. 320x180 pixels of pure software
 * rendering, then let the browser scale it up like a CRT.
 */
(function (global) {
  "use strict";

  // ---------- config ----------
  const W = 320, H = 180;           // internal framebuffer (57,600 pixels)
  const TEX = 64;                   // texture size (TEX x TEX)

  // 24x24 maze. '.' open, '1'-'4' wall textures.
  const MAP_STR = [
    "444444444444444444444444",
    "4..........2...........4",
    "4..........2...........4",
    "4..1111....2....3333...4",
    "4..1..1..........3.....4",
    "4..1..1....2.....3.....4",
    "4..1111....2.....3333..4",
    "4..........2...........4",
    "4....44....2......2....4",
    "4....4.....2......2....4",
    "4....44....2......2....4",
    "4..........2......2....4",
    "4444444.2222......2....4",
    "4..........2......2....4",
    "4..3333....2..11111....4",
    "4..3..3.........1......4",
    "4..3..3....2....1......4",
    "4..3333....2....1......4",
    "4..........2....11111..4",
    "4....222...2...........4",
    "4....2.............44..4",
    "4....222...2222....4...4",
    "4......................4",
    "444444444444444444444444",
  ];
  const MAP_H = MAP_STR.length;
  const MAP_W = MAP_STR[0].length;

  function mapAt(x, y) {
    if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return "1";
    return MAP_STR[y][x];
  }

  // ---------- deterministic noise ----------
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------- procedural textures (all CPU-side) ----------
  function makeTextures() {
    const textures = [];
    for (let t = 0; t < 4; t++) {
      textures.push(new Uint8Array(TEX * TEX * 3));
    }
    const rnd = mulberry32(1337);

    const put = (tex, x, y, r, g, b) => {
      const i = (y * TEX + x) * 3;
      tex[i] = r; tex[i + 1] = g; tex[i + 2] = b;
    };

    // tex 0: warm brick
    for (let y = 0; y < TEX; y++) {
      for (let x = 0; x < TEX; x++) {
        const row = Math.floor(y / 8);
        const offset = (row % 2) * 8;
        const bx = (x + offset) % 16, by = y % 8;
        const mortar = by === 0 || bx === 0;
        const n = rnd() * 18;
        if (mortar) put(textures[0], x, y, 74 + n, 48 + n, 38 + n);
        else put(textures[0], x, y, 150 + n, 82 + n, 58 + n);
      }
    }

    // tex 1: blue tech panel
    for (let y = 0; y < TEX; y++) {
      for (let x = 0; x < TEX; x++) {
        const n = rnd() * 12;
        const line = x % 16 === 0 || y % 16 === 0;
        const bolt = (x % 16 === 2 || x % 16 === 14) && (y % 16 === 2 || y % 16 === 14);
        if (bolt) put(textures[1], x, y, 255, 211, 67);
        else if (line) put(textures[1], x, y, 18 + n, 40 + n, 62 + n);
        else put(textures[1], x, y, 40 + n, 86 + n, 122 + n);
      }
    }

    // tex 2: pale stone
    for (let y = 0; y < TEX; y++) {
      for (let x = 0; x < TEX; x++) {
        const n = rnd() * 26;
        const crack = (x * 7 + y * 3) % 37 === 0;
        if (crack) put(textures[2], x, y, 120 + n, 112 + n, 96 + n);
        else put(textures[2], x, y, 186 + n, 176 + n, 150 + n);
      }
    }

    // tex 3: navy wall with a pixel-art "2" (the version wall)
    const glyph = [
      "................",
      "................",
      "..##########....",
      ".##........##...",
      "##..........##..",
      "##..........##..",
      "##..........##..",
      "...........##...",
      "..........##....",
      ".........##.....",
      "........##......",
      ".......##.......",
      "......##........",
      ".....##.........",
      "....############",
      "....############",
    ];
    for (let y = 0; y < TEX; y++) {
      for (let x = 0; x < TEX; x++) {
        const n = rnd() * 10;
        const gx = Math.floor(x / 4), gy = Math.floor(y / 4);
        const on = glyph[gy] && glyph[gy][gx] === "#";
        const border = x < 3 || y < 3 || x >= TEX - 3 || y >= TEX - 3;
        if (on) put(textures[3], x, y, 255, 211, 67);
        else if (border) put(textures[3], x, y, 16 + n, 30 + n, 48 + n);
        else put(textures[3], x, y, 30 + n, 58 + n, 88 + n);
      }
    }
    return textures;
  }

  // ---------- precomputed sky / floor gradient rows ----------
  function makeRowColors() {
    const rows = new Uint8Array(H * 3);
    for (let y = 0; y < H; y++) {
      const t = y / (H - 1);
      let r, g, b;
      if (t < 0.5) {
        // sky: deep dusk -> pale horizon
        const k = t / 0.5;
        r = 24 + k * 96; g = 42 + k * 118; b = 78 + k * 132;
      } else {
        // floor: dark stone -> mid stone
        const k = (t - 0.5) / 0.5;
        r = 78 - k * 34; g = 70 - k * 32; b = 58 - k * 26;
      }
      rows[y * 3] = r; rows[y * 3 + 1] = g; rows[y * 3 + 2] = b;
    }
    return rows;
  }

  // ---------- engine ----------
  function CpuGame(canvas, hud) {
    this.canvas = canvas;
    this.hud = hud || {};
    canvas.width = W;
    canvas.height = H;
    this.ctx = canvas.getContext("2d");
    this.image = this.ctx.createImageData(W, H);
    this.buf = new Uint32Array(this.image.data.buffer);
    this.textures = makeTextures();
    this.rowColors = makeRowColors();

    // player state
    this.px = 6.0; this.py = 2.0;
    this.dirX = 0; this.dirY = 1;          // facing south
    this.planeX = -0.66; this.planeY = 0;  // camera plane (FOV ~66°)
    this.keys = new Set();
    this.lastInput = 0;
    this.running = false;
    this.frames = 0;
    this.fps = 0;
    this.fpsTimer = 0;
    this.lastT = 0;

    this._onKeyDown = (e) => {
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].includes(e.key)) {
        if (document.activeElement === this.canvas || this.canvas.hasAttribute("data-focused")) {
          e.preventDefault();
        }
      }
      this.keys.add(e.code);
      this.lastInput = performance.now();
    };
    this._onKeyUp = (e) => this.keys.delete(e.code);
    this._onBlur = () => this.keys.clear();
    this._onClick = () => {
      this.canvas.setAttribute("data-focused", "1");
      this.canvas.focus();
      this.lastInput = performance.now();
    };
  }

  CpuGame.prototype.attach = function () {
    window.addEventListener("keydown", this._onKeyDown);
    window.addEventListener("keyup", this._onKeyUp);
    window.addEventListener("blur", this._onBlur);
    this.canvas.addEventListener("click", this._onClick);
    this.canvas.setAttribute("tabindex", "0");
  };

  CpuGame.prototype.start = function () {
    if (this.running) return;
    this.running = true;
    this.lastT = performance.now();
    const loop = (t) => {
      if (!this.running) return;
      const dt = Math.min((t - this.lastT) / 1000, 0.1);
      this.lastT = t;
      this.step(dt);
      this.render();
      this.frames++;
      this.fpsTimer += dt;
      if (this.fpsTimer >= 0.5) {
        this.fps = Math.round(this.frames / this.fpsTimer);
        this.frames = 0;
        this.fpsTimer = 0;
        if (this.hud.fps) this.hud.fps.textContent = this.fps + " FPS";
      }
      if (this.hud.pos) {
        this.hud.pos.textContent = "x " + this.px.toFixed(1) + "  y " + this.py.toFixed(1);
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  };

  CpuGame.prototype.stop = function () { this.running = false; };

  CpuGame.prototype.step = function (dt) {
    const speed = (this.keys.has("ShiftLeft") || this.keys.has("ShiftRight")) ? 5.2 : 3.2;
    const rot = 2.4 * dt;
    const k = this.keys;

    let moving = false;
    if (k.has("KeyW") || k.has("ArrowUp")) { this.tryMove(this.dirX * speed * dt, this.dirY * speed * dt); moving = true; }
    if (k.has("KeyS") || k.has("ArrowDown")) { this.tryMove(-this.dirX * speed * dt, -this.dirY * speed * dt); moving = true; }
    if (k.has("KeyA")) { this.tryMove(this.dirY * speed * dt, -this.dirX * speed * dt); moving = true; }
    if (k.has("KeyD")) { this.tryMove(-this.dirY * speed * dt, this.dirX * speed * dt); moving = true; }
    if (k.has("ArrowLeft") || k.has("KeyQ")) { this.rotate(-rot); moving = true; }
    if (k.has("ArrowRight") || k.has("KeyE")) { this.rotate(rot); moving = true; }

    // idle demo spin so the window is never static
    if (!moving && performance.now() - this.lastInput > 4000) {
      this.rotate(0.18 * dt);
    }
  };

  CpuGame.prototype.rotate = function (angle) {
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const ndx = this.dirX * cos - this.dirY * sin;
    const ndy = this.dirX * sin + this.dirY * cos;
    const npx = this.planeX * cos - this.planeY * sin;
    const npy = this.planeX * sin + this.planeY * cos;
    this.dirX = ndx; this.dirY = ndy;
    this.planeX = npx; this.planeY = npy;
  };

  CpuGame.prototype.tryMove = function (dx, dy) {
    const margin = 0.22;
    const nx = this.px + dx, ny = this.py + dy;
    if (mapAt(Math.floor(nx + Math.sign(dx) * margin), Math.floor(this.py)) === ".") this.px = nx;
    if (mapAt(Math.floor(this.px), Math.floor(ny + Math.sign(dy) * margin)) === ".") this.py = ny;
  };

  CpuGame.prototype.render = function () {
    const data32 = this.buf;
    const rows = this.rowColors;

    // sky + floor gradient (still CPU: one row of pixels at a time)
    for (let y = 0; y < H; y++) {
      const r = rows[y * 3], g = rows[y * 3 + 1], b = rows[y * 3 + 2];
      const color = 0xff000000 | (b << 16) | (g << 8) | r;
      const base = y * W;
      for (let x = 0; x < W; x++) data32[base + x] = color;
    }

    for (let x = 0; x < W; x++) {
      const cameraX = (2 * x) / W - 1;
      const rayDirX = this.dirX + this.planeX * cameraX;
      const rayDirY = this.dirY + this.planeY * cameraX;

      let mapX = Math.floor(this.px);
      let mapY = Math.floor(this.py);

      const deltaDistX = rayDirX === 0 ? 1e30 : Math.abs(1 / rayDirX);
      const deltaDistY = rayDirY === 0 ? 1e30 : Math.abs(1 / rayDirY);

      let stepX, stepY, sideDistX, sideDistY;
      if (rayDirX < 0) { stepX = -1; sideDistX = (this.px - mapX) * deltaDistX; }
      else { stepX = 1; sideDistX = (mapX + 1 - this.px) * deltaDistX; }
      if (rayDirY < 0) { stepY = -1; sideDistY = (this.py - mapY) * deltaDistY; }
      else { stepY = 1; sideDistY = (mapY + 1 - this.py) * deltaDistY; }

      let hit = 0, side = 0, tile = "1";
      while (hit === 0) {
        if (sideDistX < sideDistY) {
          sideDistX += deltaDistX; mapX += stepX; side = 0;
        } else {
          sideDistY += deltaDistY; mapY += stepY; side = 1;
        }
        tile = mapAt(mapX, mapY);
        if (tile !== ".") hit = 1;
      }

      const perpWallDist = side === 0
        ? (mapX - this.px + (1 - stepX) / 2) / rayDirX
        : (mapY - this.py + (1 - stepY) / 2) / rayDirY;

      const lineHeight = Math.floor(H / perpWallDist);
      let drawStart = Math.floor(-lineHeight / 2 + H / 2);
      let drawEnd = Math.floor(lineHeight / 2 + H / 2);
      const texStart = drawStart;
      if (drawStart < 0) drawStart = 0;
      if (drawEnd >= H) drawEnd = H - 1;

      // texture X
      let wallX = side === 0 ? this.py + perpWallDist * rayDirY : this.px + perpWallDist * rayDirX;
      wallX -= Math.floor(wallX);
      let texX = Math.floor(wallX * TEX);
      if ((side === 0 && rayDirX > 0) || (side === 1 && rayDirY < 0)) texX = TEX - texX - 1;

      const tex = this.textures[(parseInt(tile, 10) || 1) - 1];

      // fog: blend toward the wall's row color as distance grows
      const fog = 1 / (1 + perpWallDist * perpWallDist * 0.045);
      const sideShade = side === 1 ? 0.72 : 1.0;

      const texStep = TEX / lineHeight;
      let texPos = (drawStart - texStart) * texStep;

      for (let y = drawStart; y <= drawEnd; y++) {
        const texY = Math.floor(texPos) & (TEX - 1);
        texPos += texStep;
        const ti = (texY * TEX + texX) * 3;
        const r = tex[ti] * fog * sideShade;
        const g = tex[ti + 1] * fog * sideShade;
        const b = tex[ti + 2] * fog * sideShade;
        data32[y * W + x] = 0xff000000 | (Math.min(255, b) << 16) | (Math.min(255, g) << 8) | Math.min(255, r);
      }
    }

    this.drawMinimap(data32);
    this.ctx.putImageData(this.image, 0, 0);
  };

  CpuGame.prototype.drawMinimap = function (data32) {
    const cell = 3;
    const ox = W - MAP_W * cell - 6;
    const oy = 6;
    // backdrop
    for (let y = 0; y < MAP_H * cell + 4; y++) {
      for (let x = 0; x < MAP_W * cell + 4; x++) {
        const px = ox - 2 + x, py = oy - 2 + y;
        if (px < 0 || py < 0 || px >= W || py >= H) continue;
        data32[py * W + px] = 0xff000000 | (24 << 16) | (28 << 8) | 32;
      }
    }
    for (let my = 0; my < MAP_H; my++) {
      for (let mx = 0; mx < MAP_W; mx++) {
        const t = MAP_STR[my][mx];
        const color = t === "." ? 0xff000000 | (52 << 16) | (60 << 8) | 70
          : t === "4" ? 0xff000000 | (160 << 16) | (120 << 8) | 60
            : t === "3" ? 0xff000000 | (190 << 16) | (120 << 8) | 255
              : 0xff000000 | (110 << 16) | (125 << 8) | 140;
        for (let y = 0; y < cell; y++) {
          for (let x = 0; x < cell; x++) {
            data32[(oy + my * cell + y) * W + (ox + mx * cell + x)] = color;
          }
        }
      }
    }
    // player dot + heading
    const ppx = ox + Math.floor(this.px * cell);
    const ppy = oy + Math.floor(this.py * cell);
    for (let y = -1; y <= 1; y++) {
      for (let x = -1; x <= 1; x++) {
        const i = (ppy + y) * W + (ppx + x);
        data32[i] = 0xff000000 | (67 << 16) | (211 << 8) | 255;
      }
    }
    const hx = ppx + Math.round(this.dirX * 4);
    const hy = ppy + Math.round(this.dirY * 4);
    data32[hy * W + hx] = 0xff000000 | (67 << 16) | (211 << 8) | 255;
  };

  global.CpuGame = CpuGame;
})(typeof globalThis !== "undefined" ? globalThis : this);
