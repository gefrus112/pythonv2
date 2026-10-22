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
  const SPRITE_TEX = 32;            // original procedural monster sprites
  const PIXELS_PER_FRAME = W * H;

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

  // ---------- original public-domain-style procedural monster sprites ----------
  function makeMonsterSprite(kind) {
    const tex = new Uint32Array(SPRITE_TEX * SPRITE_TEX);
    const color = (r, g, b, a) => ((a === undefined ? 255 : a) << 24) | (b << 16) | (g << 8) | r;
    for (let y = 0; y < SPRITE_TEX; y++) {
      for (let x = 0; x < SPRITE_TEX; x++) {
        const nx = (x - 15.5) / 15.5, ny = (y - 16) / 15;
        let pixel = 0;
        if (kind === "slime") {
          const body = nx * nx + Math.pow(ny * 0.88, 2) < 0.76 && y > 6;
          const foot = y > 24 && y < 29 && x > 4 && x < 28;
          if (body || foot) pixel = color(68, 163, 111);
          if (body && y < 13 && x > 8 && x < 22) pixel = color(112, 217, 154);
          if (y >= 15 && y <= 19 && ((x >= 8 && x <= 11) || (x >= 20 && x <= 23))) pixel = color(255, 245, 192);
          if (y >= 17 && y <= 19 && (x === 10 || x === 22)) pixel = color(27, 39, 51);
          if (y === 23 && x >= 12 && x <= 19) pixel = color(27, 39, 51);
        } else {
          const body = nx * nx + Math.pow(ny * 0.9, 2) < 0.72 && y > 5;
          const horns = (y < 9 && ((x > 4 && x < 9 - y / 3) || (x > 23 + y / 3 && x < 28)));
          if (body || horns) pixel = color(214, 69, 65);
          if (body && y < 13 && x > 8 && x < 23) pixel = color(241, 106, 98);
          if (y >= 15 && y <= 19 && ((x >= 7 && x <= 11) || (x >= 20 && x <= 24))) pixel = color(255, 211, 67);
          if (y >= 17 && y <= 19 && (x === 10 || x === 21)) pixel = color(27, 39, 51);
          if (y === 23 && x >= 12 && x <= 19) pixel = color(27, 39, 51);
        }
        tex[y * SPRITE_TEX + x] = pixel;
      }
    }
    return tex;
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
    this.zBuffer = new Float32Array(W);
    this.spriteTextures = {
      beast: makeMonsterSprite("beast"),
      slime: makeMonsterSprite("slime"),
    };

    // Original CC0 monsters. No ripped commercial-game artwork.
    this.monsters = [
      { x: 8.5, y: 6.5, kind: "beast", health: 2, alive: true, flash: 0 },
      { x: 17.5, y: 4.5, kind: "slime", health: 1, alive: true, flash: 0 },
      { x: 13.5, y: 11.5, kind: "beast", health: 2, alive: true, flash: 0 },
      { x: 20.5, y: 18.5, kind: "slime", health: 1, alive: true, flash: 0 },
      { x: 7.5, y: 20.5, kind: "beast", health: 2, alive: true, flash: 0 },
    ];

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
    this.kills = 0;
    this.health = 100;
    this.pixelsRendered = 0;
    this.shotUntil = 0;
    this.hitUntil = 0;
    this.weaponBob = 0;

    this._onKeyDown = (e) => {
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].includes(e.key)) {
        if (document.activeElement === this.canvas || this.canvas.hasAttribute("data-focused")) {
          e.preventDefault();
        }
      }
      if ((e.code === "Space" || e.code === "KeyF") && !e.repeat &&
          (document.activeElement === this.canvas || this.canvas.hasAttribute("data-focused"))) {
        this.shoot();
      }
      this.keys.add(e.code);
      this.lastInput = performance.now();
    };
    this._onKeyUp = (e) => this.keys.delete(e.code);
    this._onBlur = () => this.keys.clear();
    this._onClick = () => {
      const alreadyFocused = this.canvas.hasAttribute("data-focused");
      this.canvas.setAttribute("data-focused", "1");
      this.canvas.focus();
      this.lastInput = performance.now();
      if (alreadyFocused) this.shoot();
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
      if (this.hud.kills) {
        const left = this.monsters.filter((m) => m.alive).length;
        this.hud.kills.textContent = "MONSTERS " + left + " • KILLS " + this.kills + " • HP " + this.health;
      }
      if (this.hud.pixels) {
        this.hud.pixels.textContent = this.pixelsRendered.toLocaleString() + " pixels rendered";
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

    if (moving) this.weaponBob += dt * 11;
    this.stepMonsters(dt);

    // idle demo spin so the window is never static
    if (!moving && performance.now() - this.lastInput > 4000) {
      this.rotate(0.18 * dt);
    }
  };

  CpuGame.prototype.stepMonsters = function (dt) {
    const now = performance.now();
    for (const monster of this.monsters) {
      if (!monster.alive) continue;
      if (monster.flash && now > monster.flash) monster.flash = 0;
      const dx = this.px - monster.x, dy = this.py - monster.y;
      const distance = Math.hypot(dx, dy);
      if (distance < 8 && distance > 1.1) {
        const speed = (monster.kind === "slime" ? 0.52 : 0.68) * dt;
        const nx = monster.x + (dx / distance) * speed;
        const ny = monster.y + (dy / distance) * speed;
        if (mapAt(Math.floor(nx), Math.floor(monster.y)) === ".") monster.x = nx;
        if (mapAt(Math.floor(monster.x), Math.floor(ny)) === ".") monster.y = ny;
      } else if (distance <= 1.1 && now > this.hitUntil) {
        this.health = Math.max(0, this.health - 8);
        this.hitUntil = now + 650;
        if (this.health === 0) {
          this.health = 100;
          this.px = 6.0; this.py = 2.0;
        }
      }
    }
  };

  CpuGame.prototype.shoot = function () {
    const now = performance.now();
    if (now < this.shotUntil - 40) return;
    this.shotUntil = now + 130;
    let best = null, bestDistance = Infinity;
    for (const monster of this.monsters) {
      if (!monster.alive) continue;
      const dx = monster.x - this.px, dy = monster.y - this.py;
      const distance = Math.hypot(dx, dy);
      const forward = dx * this.dirX + dy * this.dirY;
      if (forward <= 0) continue;
      const sideways = Math.abs(dx * this.dirY - dy * this.dirX);
      // generous crosshair cone; the center wall depth prevents wall shots.
      if (sideways / forward < 0.13 && distance < bestDistance &&
          (!this.zBuffer[W >> 1] || forward < this.zBuffer[W >> 1] + 0.2)) {
        best = monster;
        bestDistance = distance;
      }
    }
    if (best) {
      best.health--;
      best.flash = now + 100;
      if (best.health <= 0) {
        best.alive = false;
        this.kills++;
      }
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
      this.zBuffer[x] = perpWallDist;

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

    this.drawSprites(data32);
    this.drawWeapon(data32);
    this.drawCrosshair(data32);
    this.drawMinimap(data32);
    this.ctx.putImageData(this.image, 0, 0);
    this.pixelsRendered += PIXELS_PER_FRAME;
  };

  CpuGame.prototype.drawSprites = function (data32) {
    const ordered = this.monsters
      .filter((monster) => monster.alive)
      .map((monster) => ({ monster, dist: Math.pow(this.px - monster.x, 2) + Math.pow(this.py - monster.y, 2) }))
      .sort((a, b) => b.dist - a.dist);
    const invDet = 1 / (this.planeX * this.dirY - this.dirX * this.planeY);

    for (const entry of ordered) {
      const monster = entry.monster;
      const sx = monster.x - this.px, sy = monster.y - this.py;
      const transformX = invDet * (this.dirY * sx - this.dirX * sy);
      const transformY = invDet * (-this.planeY * sx + this.planeX * sy);
      if (transformY <= 0.05) continue;

      const screenX = Math.floor((W / 2) * (1 + transformX / transformY));
      const size = Math.abs(Math.floor(H / transformY));
      const startY = Math.max(0, Math.floor(H / 2 - size / 2));
      const endY = Math.min(H - 1, Math.floor(H / 2 + size / 2));
      const startX = Math.max(0, Math.floor(screenX - size / 2));
      const endX = Math.min(W - 1, Math.floor(screenX + size / 2));
      const texture = this.spriteTextures[monster.kind];

      for (let stripe = startX; stripe <= endX; stripe++) {
        if (transformY >= this.zBuffer[stripe]) continue;
        const texX = Math.max(0, Math.min(SPRITE_TEX - 1,
          Math.floor(((stripe - (screenX - size / 2)) / Math.max(1, size)) * SPRITE_TEX)));
        for (let y = startY; y <= endY; y++) {
          const texY = Math.max(0, Math.min(SPRITE_TEX - 1,
            Math.floor(((y - (H / 2 - size / 2)) / Math.max(1, size)) * SPRITE_TEX)));
          let pixel = texture[texY * SPRITE_TEX + texX];
          if ((pixel >>> 24) === 0) continue;
          if (monster.flash) pixel = 0xffffffff;
          const shade = Math.max(0.35, 1 / (1 + transformY * 0.08));
          const r = (pixel & 255) * shade;
          const g = ((pixel >>> 8) & 255) * shade;
          const b = ((pixel >>> 16) & 255) * shade;
          data32[y * W + stripe] = 0xff000000 | (b << 16) | (g << 8) | r;
        }
      }
    }
  };

  CpuGame.prototype.drawWeapon = function (data32) {
    const now = performance.now();
    const bobX = Math.round(Math.sin(this.weaponBob) * 2);
    const bobY = Math.round(Math.abs(Math.cos(this.weaponBob)) * 2);
    const ox = Math.floor(W / 2) - 31 + bobX;
    const oy = H - 42 + bobY;
    const putRect = (x, y, w, h, color) => {
      for (let py = Math.max(0, y); py < Math.min(H, y + h); py++) {
        for (let px = Math.max(0, x); px < Math.min(W, x + w); px++) data32[py * W + px] = color;
      }
    };
    putRect(ox + 4, oy + 10, 48, 22, 0xff1d2731);
    putRect(ox + 10, oy + 12, 45, 13, 0xffbd6f2f);
    putRect(ox + 14, oy + 14, 33, 5, 0xffdcc45f);
    putRect(ox + 19, oy + 30, 17, 12, 0xff3d3228);
    putRect(ox + 23, oy + 27, 11, 12, 0xff5f4933);
    putRect(ox + 28, oy + 30, 5, 5, 0xff413ed6);
    if (now < this.shotUntil) {
      putRect(ox + 54, oy + 10, 8, 11, 0xff43d3ff);
      putRect(ox + 62, oy + 13, 5, 5, 0xff67f2ff);
    }
  };

  CpuGame.prototype.drawCrosshair = function (data32) {
    const color = 0xff43d3ff;
    const cx = W >> 1, cy = H >> 1;
    for (let d = 3; d <= 7; d++) {
      data32[cy * W + cx - d] = color;
      data32[cy * W + cx + d] = color;
      data32[(cy - d) * W + cx] = color;
      data32[(cy + d) * W + cx] = color;
    }
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
    // monsters
    for (const monster of this.monsters) {
      if (!monster.alive) continue;
      const mx = ox + Math.floor(monster.x * cell);
      const my = oy + Math.floor(monster.y * cell);
      if (mx >= 0 && my >= 0 && mx < W && my < H) {
        data32[my * W + mx] = monster.kind === "slime" ? 0xff6fa344 : 0xff4145d6;
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
