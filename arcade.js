/*
 * Pocket Arcade — seven compact Canvas games for the Python v2 Games tab.
 * Original code and shapes only; no third-party game art or runtime.
 */
(function (global) {
  "use strict";

  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const hit = (a, b, radius) => Math.hypot(a.x - b.x, a.y - b.y) < radius;

  function PocketArcade(canvas, ui) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.ui = ui || {};
    this.width = 800;
    this.height = 450;
    canvas.width = this.width;
    canvas.height = this.height;
    canvas.tabIndex = 0;
    this.keys = new Set();
    this.pointer = { x: 400, y: 225 };
    this.last = performance.now();
    this.mode = "neon-blaster";
    this.state = {};
    this.particles = [];
    this.images = {};
    this.configs = {
      "neon-blaster": {
        title: "Neon Blaster", number: "04", genre: "WAVE SHOOTER",
        description: "Pilot the Comet, weave through Null Drones, and stream blue energy through an endless neon attack wave.",
        controls: "WASD / arrows move • Space or click fires • R restarts",
      },
      "asteroid-drift": {
        title: "Asteroid Drift", number: "05", genre: "SPACE SHOOTER",
        description: "Drift through a moving asteroid field. Break rocks before they cross your flight line and protect all three shields.",
        controls: "A D / arrows steer • W S move • Space fires • R restarts",
      },
      "target-blitz": {
        title: "Target Blitz", number: "06", genre: "PRECISION SHOOTER",
        description: "A fast mouse-and-touch shooting gallery. Hit moving targets, build a combo, and beat the 30-second clock.",
        controls: "Mouse / touch aim • click targets • R restarts the clock",
      },
      skybound: {
        title: "Skybound", number: "07", genre: "ARCADE PLATFORMER",
        description: "Comet Kid auto-jumps through a shifting sky tower. Land cleanly, climb forever, and do not fall below the clouds.",
        controls: "A D / arrows steer in air • R restarts",
      },
      "turbo-trail": {
        title: "Turbo Trail", number: "08", genre: "ENDLESS RACING",
        description: "Change lanes through an endless sunset highway. Thread the traffic as the road gets faster every second.",
        controls: "A D / arrows change lane • R restarts",
      },
      "snake-byte": {
        title: "Snake Byte", number: "09", genre: "GRID ARCADE",
        description: "Guide the green code snake through a circuit board, collect Hope Bits, and avoid your growing byte trail.",
        controls: "Arrow keys or WASD turn • R restarts",
      },
      "orb-breaker": {
        title: "Orb Breaker", number: "10", genre: "BRICK BREAKER",
        description: "Bounce the energy orb through a wall of compiler blocks. Clear every brick without losing all three cores.",
        controls: "A D / arrows move paddle • Space launches • R restarts",
      },
    };
    this.loadManifest();
    this.loadImages();
    this.bind();
    this.select(this.mode, false);
  }

  PocketArcade.prototype.loadManifest = function () {
    const script = document.getElementById("arcade-manifest");
    if (!script || typeof global.Pyv2 === "undefined") return;
    const result = global.Pyv2.runCapture(script.textContent);
    if (result.error) return;
    result.output.split("\n").forEach((line) => {
      const parts = line.split("|");
      if (parts.length >= 3 && this.configs[parts[0]]) {
        this.configs[parts[0]].title = parts[1];
        this.configs[parts[0]].genre = parts[2];
      }
    });
  };

  PocketArcade.prototype.loadImages = function () {
    const files = {
      pilot: "assets/sprites/comet-pilot.svg",
      drone: "assets/sprites/drone.svg",
      car: "assets/sprites/race-car.svg",
      hero: "assets/sprites/comet-hero.svg",
    };
    Object.entries(files).forEach(([name, src]) => {
      const image = new Image();
      image.src = src;
      this.images[name] = image;
    });
  };

  PocketArcade.prototype.bind = function () {
    this._down = (event) => {
      this.keys.add(event.code);
      const focused = document.activeElement === this.canvas;
      if (focused && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Space"].includes(event.code)) {
        event.preventDefault();
      }
      if (!focused) return;
      if (event.code === "KeyR") this.reset();
      if (this.mode === "snake-byte") this.turnSnake(event.code);
      if (event.code === "Space" && !event.repeat) {
        if (this.mode === "neon-blaster" || this.mode === "asteroid-drift") this.fire();
        if (this.mode === "orb-breaker") this.state.launched = true;
      }
    };
    this._up = (event) => this.keys.delete(event.code);
    window.addEventListener("keydown", this._down);
    window.addEventListener("keyup", this._up);
    window.addEventListener("blur", () => this.keys.clear());

    const point = (event) => {
      const rect = this.canvas.getBoundingClientRect();
      this.pointer.x = (event.clientX - rect.left) * this.width / rect.width;
      this.pointer.y = (event.clientY - rect.top) * this.height / rect.height;
    };
    this.canvas.addEventListener("pointermove", point);
    this.canvas.addEventListener("pointerdown", (event) => {
      point(event);
      this.canvas.focus();
      if (this.mode === "target-blitz") this.shootTarget();
      else if (this.mode === "neon-blaster" || this.mode === "asteroid-drift") this.fire();
      else if (this.mode === "orb-breaker") this.state.launched = true;
    });

    document.querySelectorAll("[data-pocket-game]").forEach((button) => {
      button.addEventListener("click", () => {
        this.select(button.dataset.pocketGame, true);
      });
    });
    const reset = document.getElementById("arcade-reset");
    if (reset) reset.addEventListener("click", () => { this.reset(); this.canvas.focus(); });
  };

  PocketArcade.prototype.select = function (mode, focus) {
    if (!this.configs[mode]) return;
    this.mode = mode;
    const config = this.configs[mode];
    document.querySelectorAll("[data-pocket-game]").forEach((button) => {
      const selected = button.dataset.pocketGame === mode;
      button.classList.toggle("active", selected);
      if (button.matches("button")) button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    if (this.ui.title) this.ui.title.textContent = config.title;
    if (this.ui.description) this.ui.description.textContent = config.description;
    if (this.ui.badge) this.ui.badge.textContent = "GAME " + config.number + " • " + config.genre;
    if (this.ui.controls) this.ui.controls.textContent = config.controls;
    this.reset();
    if (focus) {
      window.setTimeout(() => this.canvas.focus(), 250);
    }
  };

  PocketArcade.prototype.reset = function () {
    this.particles = [];
    const mode = this.mode;
    if (mode === "neon-blaster") {
      this.state = { player: { x: 400, y: 385 }, bullets: [], enemies: [], enemyBullets: [], spawn: 0, shot: 0, score: 0, lives: 3, time: 0, over: false };
    } else if (mode === "asteroid-drift") {
      this.state = { player: { x: 400, y: 365 }, bullets: [], rocks: [], shot: 0, spawn: 0, score: 0, lives: 3, time: 0, over: false };
      for (let i = 0; i < 7; i++) this.addRock(true);
    } else if (mode === "target-blitz") {
      this.state = { target: this.newTarget(), score: 0, combo: 0, bestCombo: 0, remaining: 30, flash: 0, shots: 0, hits: 0, over: false };
    } else if (mode === "skybound") {
      this.state = {
        player: { x: 380, y: 330, vx: 0, vy: -460 }, score: 0, over: false,
        platforms: [
          { x: 325, y: 408, w: 150 }, { x: 105, y: 335, w: 135 }, { x: 430, y: 263, w: 145 },
          { x: 215, y: 188, w: 125 }, { x: 545, y: 115, w: 135 }, { x: 330, y: 43, w: 120 },
        ],
      };
    } else if (mode === "turbo-trail") {
      this.state = { lane: 1, x: 400, traffic: [], spawn: .5, score: 0, speed: 230, lives: 3, time: 0, flash: 0, over: false };
    } else if (mode === "snake-byte") {
      this.state = { snake: [{ x: 8, y: 7 }, { x: 7, y: 7 }, { x: 6, y: 7 }], dir: { x: 1, y: 0 }, next: { x: 1, y: 0 }, food: { x: 18, y: 7 }, timer: 0, score: 0, over: false };
    } else if (mode === "orb-breaker") {
      const bricks = [];
      const colors = ["#d64541", "#ffd343", "#44a36f", "#70d6ff", "#2f6fbd"];
      for (let row = 0; row < 5; row++) for (let col = 0; col < 10; col++) {
        bricks.push({ x: 50 + col * 70, y: 55 + row * 27, w: 62, h: 18, color: colors[row], alive: true });
      }
      this.state = { paddle: 400, ball: { x: 400, y: 376, vx: 185, vy: -260 }, bricks, score: 0, lives: 3, launched: false, over: false, won: false };
    }
    this.updateStatus();
  };

  PocketArcade.prototype.addParticles = function (x, y, color, count) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 40 + Math.random() * 150;
      this.particles.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, life: .35 + Math.random() * .45, color });
    }
  };

  PocketArcade.prototype.updateParticles = function (dt) {
    this.particles.forEach((p) => { p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt; });
    this.particles = this.particles.filter((p) => p.life > 0);
  };

  PocketArcade.prototype.fire = function () {
    const s = this.state;
    if (!s || s.over || (s.shot || 0) > 0) return;
    const player = s.player;
    s.bullets.push({ x: player.x, y: player.y - 22 });
    s.shot = this.mode === "neon-blaster" ? .13 : .2;
    this.addParticles(player.x, player.y - 24, "#70d6ff", 4);
  };

  PocketArcade.prototype.addRock = function (initial) {
    const s = this.state;
    const radius = 18 + Math.random() * 24;
    s.rocks.push({
      x: 35 + Math.random() * 730,
      y: initial ? Math.random() * 360 - 180 : -radius,
      r: radius,
      vx: -35 + Math.random() * 70,
      vy: 65 + Math.random() * 95,
      spin: Math.random() * Math.PI,
    });
  };

  PocketArcade.prototype.newTarget = function () {
    const radius = 24 + Math.random() * 22;
    return {
      x: 90 + Math.random() * 620, y: 90 + Math.random() * 260, r: radius,
      vx: (Math.random() < .5 ? -1 : 1) * (65 + Math.random() * 85),
      vy: (Math.random() < .5 ? -1 : 1) * (35 + Math.random() * 65),
    };
  };

  PocketArcade.prototype.shootTarget = function () {
    const s = this.state;
    if (!s || s.over) return;
    s.shots++;
    const distance = Math.hypot(this.pointer.x - s.target.x, this.pointer.y - s.target.y);
    if (distance <= s.target.r) {
      s.combo++;
      s.bestCombo = Math.max(s.bestCombo, s.combo);
      s.score += 10 + Math.max(0, Math.round((s.target.r - distance) / 4)) + s.combo * 2;
      this.addParticles(s.target.x, s.target.y, "#ffd343", 18);
      s.target = this.newTarget();
      s.flash = .1;
    } else {
      s.combo = 0;
      s.score = Math.max(0, s.score - 2);
    }
  };

  PocketArcade.prototype.turnSnake = function (code) {
    const s = this.state;
    if (!s || !s.next) return;
    const turns = {
      ArrowLeft: { x: -1, y: 0 }, KeyA: { x: -1, y: 0 }, ArrowRight: { x: 1, y: 0 }, KeyD: { x: 1, y: 0 },
      ArrowUp: { x: 0, y: -1 }, KeyW: { x: 0, y: -1 }, ArrowDown: { x: 0, y: 1 }, KeyS: { x: 0, y: 1 },
    };
    const next = turns[code];
    if (next && !(next.x === -s.dir.x && next.y === -s.dir.y)) s.next = next;
  };

  PocketArcade.prototype.inputAxis = function () {
    return {
      x: (this.keys.has("ArrowRight") || this.keys.has("KeyD") ? 1 : 0) - (this.keys.has("ArrowLeft") || this.keys.has("KeyA") ? 1 : 0),
      y: (this.keys.has("ArrowDown") || this.keys.has("KeyS") ? 1 : 0) - (this.keys.has("ArrowUp") || this.keys.has("KeyW") ? 1 : 0),
    };
  };

  PocketArcade.prototype.update = function (dt) {
    this.updateParticles(dt);
    if (this.mode === "neon-blaster") this.updateNeon(dt);
    else if (this.mode === "asteroid-drift") this.updateAsteroids(dt);
    else if (this.mode === "target-blitz") this.updateTargets(dt);
    else if (this.mode === "skybound") this.updateSkybound(dt);
    else if (this.mode === "turbo-trail") this.updateTurbo(dt);
    else if (this.mode === "snake-byte") this.updateSnake(dt);
    else if (this.mode === "orb-breaker") this.updateBreaker(dt);
    this.updateStatus();
  };

  PocketArcade.prototype.updateNeon = function (dt) {
    const s = this.state;
    if (s.over) return;
    const input = this.inputAxis();
    s.player.x = clamp(s.player.x + input.x * 300 * dt, 28, 772);
    s.player.y = clamp(s.player.y + input.y * 270 * dt, 245, 418);
    s.time += dt; s.spawn -= dt; s.shot -= dt;
    if (this.keys.has("Space")) this.fire();
    if (s.spawn <= 0) {
      s.enemies.push({ x: 55 + Math.random() * 690, y: -28, vy: 85 + Math.random() * 60 + s.time * 1.2, phase: Math.random() * 6.28, hp: s.time > 25 ? 2 : 1 });
      s.spawn = Math.max(.27, .78 - s.time * .012);
    }
    s.bullets.forEach((b) => { b.y -= 520 * dt; });
    s.enemies.forEach((enemy) => { enemy.y += enemy.vy * dt; enemy.x += Math.sin(s.time * 3 + enemy.phase) * 38 * dt; });
    for (const bullet of s.bullets) for (const enemy of s.enemies) {
      if (!bullet.dead && !enemy.dead && hit(bullet, enemy, 25)) {
        bullet.dead = true; enemy.hp--;
        this.addParticles(bullet.x, bullet.y, "#ff8278", 8);
        if (enemy.hp <= 0) { enemy.dead = true; s.score += 25; this.addParticles(enemy.x, enemy.y, "#ffd343", 14); }
      }
    }
    for (const enemy of s.enemies) {
      if (!enemy.dead && (enemy.y > 470 || hit(enemy, s.player, 30))) {
        enemy.dead = true; s.lives--; this.addParticles(s.player.x, s.player.y, "#d64541", 18);
        if (s.lives <= 0) s.over = true;
      }
    }
    s.bullets = s.bullets.filter((b) => b.y > -20 && !b.dead);
    s.enemies = s.enemies.filter((e) => e.y < 490 && !e.dead);
  };

  PocketArcade.prototype.updateAsteroids = function (dt) {
    const s = this.state;
    if (s.over) return;
    const input = this.inputAxis();
    s.player.x = clamp(s.player.x + input.x * 260 * dt, 25, 775);
    s.player.y = clamp(s.player.y + input.y * 230 * dt, 220, 420);
    s.time += dt; s.spawn -= dt; s.shot -= dt;
    if (this.keys.has("Space")) this.fire();
    if (s.spawn <= 0) { this.addRock(false); s.spawn = Math.max(.45, 1.15 - s.time * .012); }
    s.bullets.forEach((b) => { b.y -= 500 * dt; });
    s.rocks.forEach((rock) => { rock.x += rock.vx * dt; rock.y += rock.vy * dt; rock.spin += dt; if (rock.x < -rock.r) rock.x = 800 + rock.r; if (rock.x > 800 + rock.r) rock.x = -rock.r; });
    for (const bullet of s.bullets) for (const rock of s.rocks) {
      if (!bullet.dead && !rock.dead && hit(bullet, rock, rock.r)) {
        bullet.dead = true; rock.r -= 13; s.score += 10; this.addParticles(bullet.x, bullet.y, "#9aabba", 8);
        if (rock.r < 16) { rock.dead = true; s.score += 20; }
      }
    }
    for (const rock of s.rocks) {
      if (!rock.dead && (rock.y - rock.r > 455 || hit(rock, s.player, rock.r + 16))) {
        rock.dead = true; s.lives--; this.addParticles(s.player.x, s.player.y, "#ff8278", 20);
        if (s.lives <= 0) s.over = true;
      }
    }
    s.bullets = s.bullets.filter((b) => b.y > -20 && !b.dead);
    s.rocks = s.rocks.filter((r) => !r.dead);
  };

  PocketArcade.prototype.updateTargets = function (dt) {
    const s = this.state;
    if (s.over) return;
    s.remaining = Math.max(0, s.remaining - dt); s.flash -= dt;
    const t = s.target; t.x += t.vx * dt; t.y += t.vy * dt;
    if (t.x < t.r + 15 || t.x > 785 - t.r) t.vx *= -1;
    if (t.y < t.r + 55 || t.y > 415 - t.r) t.vy *= -1;
    t.x = clamp(t.x, t.r + 15, 785 - t.r); t.y = clamp(t.y, t.r + 55, 415 - t.r);
    if (s.remaining <= 0) s.over = true;
  };

  PocketArcade.prototype.updateSkybound = function (dt) {
    const s = this.state;
    if (s.over) return;
    const p = s.player, input = this.inputAxis();
    p.vx += input.x * 760 * dt; p.vx *= Math.pow(.025, dt); p.vx = clamp(p.vx, -250, 250);
    const oldY = p.y; p.vy += 980 * dt; p.x += p.vx * dt; p.y += p.vy * dt;
    if (p.x < -18) p.x = 800; if (p.x > 818) p.x = 0;
    if (p.vy > 0) {
      for (const platform of s.platforms) {
        if (oldY + 26 <= platform.y && p.y + 26 >= platform.y && p.x + 15 > platform.x && p.x - 15 < platform.x + platform.w) {
          p.y = platform.y - 27; p.vy = -480; s.score += 10; this.addParticles(p.x, platform.y, "#fff", 6); break;
        }
      }
    }
    if (p.y < 150) {
      const shift = (150 - p.y) * .13; p.y += shift;
      s.platforms.forEach((platform) => { platform.y += shift; });
      s.score += shift * .12;
    }
    s.platforms.forEach((platform) => {
      if (platform.y > 470) {
        platform.y = -10;
        platform.x = 35 + Math.random() * 610;
        platform.w = 90 + Math.random() * 90;
      }
    });
    if (p.y > 500) s.over = true;
  };

  PocketArcade.prototype.updateTurbo = function (dt) {
    const s = this.state;
    if (s.over) return;
    const input = this.inputAxis();
    if (input.x && !s.laneLatch) { s.lane = clamp(s.lane + input.x, 0, 2); s.laneLatch = true; }
    if (!input.x) s.laneLatch = false;
    const lanes = [305, 400, 495];
    s.x += (lanes[s.lane] - s.x) * Math.min(1, dt * 12);
    s.time += dt; s.score += dt * s.speed / 8; s.speed = Math.min(480, 225 + s.time * 7); s.spawn -= dt; s.flash -= dt;
    if (s.spawn <= 0) {
      const lane = Math.floor(Math.random() * 3);
      s.traffic.push({ lane, x: lanes[lane], y: -70, color: ["#d64541", "#ffd343", "#44a36f"][Math.floor(Math.random() * 3)], passed: false });
      s.spawn = Math.max(.42, 1.05 - s.time * .012);
    }
    s.traffic.forEach((car) => {
      car.y += s.speed * dt;
      if (!car.hit && Math.abs(car.y - 365) < 48 && Math.abs(car.x - s.x) < 50) {
        car.hit = true; s.lives--; s.flash = .22; this.addParticles(s.x, 380, "#ffd343", 25);
        if (s.lives <= 0) s.over = true;
      }
      if (!car.passed && car.y > 430) { car.passed = true; s.score += 35; }
    });
    s.traffic = s.traffic.filter((car) => car.y < 540);
  };

  PocketArcade.prototype.updateSnake = function (dt) {
    const s = this.state;
    if (s.over) return;
    s.timer += dt;
    const interval = Math.max(.065, .14 - s.score * .002);
    if (s.timer < interval) return;
    s.timer -= interval; s.dir = s.next;
    const head = { x: s.snake[0].x + s.dir.x, y: s.snake[0].y + s.dir.y };
    const crashed = head.x < 0 || head.x >= 25 || head.y < 0 || head.y >= 14 || s.snake.some((cell) => cell.x === head.x && cell.y === head.y);
    if (crashed) { s.over = true; return; }
    s.snake.unshift(head);
    if (head.x === s.food.x && head.y === s.food.y) {
      s.score++;
      this.addParticles(16 + head.x * 32, 17 + head.y * 30, "#ffd343", 12);
      let safe = false;
      while (!safe) {
        s.food = { x: Math.floor(Math.random() * 25), y: Math.floor(Math.random() * 14) };
        safe = !s.snake.some((cell) => cell.x === s.food.x && cell.y === s.food.y);
      }
    } else s.snake.pop();
  };

  PocketArcade.prototype.updateBreaker = function (dt) {
    const s = this.state;
    if (s.over) return;
    const input = this.inputAxis();
    s.paddle = clamp(s.paddle + input.x * 390 * dt, 70, 730);
    const ball = s.ball;
    if (!s.launched) { ball.x = s.paddle; ball.y = 380; return; }
    ball.x += ball.vx * dt; ball.y += ball.vy * dt;
    if (ball.x < 12 || ball.x > 788) { ball.vx *= -1; ball.x = clamp(ball.x, 12, 788); }
    if (ball.y < 35) { ball.vy = Math.abs(ball.vy); }
    if (ball.vy > 0 && ball.y > 390 && ball.y < 415 && Math.abs(ball.x - s.paddle) < 66) {
      ball.y = 389; ball.vy = -Math.abs(ball.vy); ball.vx += (ball.x - s.paddle) * 3.4; ball.vx = clamp(ball.vx, -370, 370);
    }
    for (const brick of s.bricks) {
      if (brick.alive && ball.x > brick.x && ball.x < brick.x + brick.w && ball.y > brick.y && ball.y < brick.y + brick.h) {
        brick.alive = false; ball.vy *= -1; s.score += 10; this.addParticles(ball.x, ball.y, brick.color, 8); break;
      }
    }
    if (ball.y > 470) {
      s.lives--; s.launched = false; ball.vx = 185 * (Math.random() < .5 ? -1 : 1); ball.vy = -260;
      if (s.lives <= 0) s.over = true;
    }
    if (s.bricks.every((brick) => !brick.alive)) { s.over = true; s.won = true; }
  };

  PocketArcade.prototype.updateStatus = function () {
    const s = this.state;
    if (!this.ui.status || !s) return;
    let text = "";
    if (this.mode === "neon-blaster" || this.mode === "asteroid-drift") text = "SCORE " + Math.floor(s.score) + " • SHIELDS " + s.lives;
    else if (this.mode === "target-blitz") text = "SCORE " + s.score + " • COMBO x" + s.combo + " • " + s.remaining.toFixed(1) + "s";
    else if (this.mode === "skybound") text = "HEIGHT " + Math.floor(s.score) + " • AUTO-JUMP ACTIVE";
    else if (this.mode === "turbo-trail") text = "DISTANCE " + Math.floor(s.score) + "m • " + Math.floor(s.speed) + " KM/H • CORES " + s.lives;
    else if (this.mode === "snake-byte") text = "HOPE BITS " + s.score + " • LENGTH " + s.snake.length;
    else if (this.mode === "orb-breaker") text = "SCORE " + s.score + " • BRICKS " + s.bricks.filter((b) => b.alive).length + " • CORES " + s.lives;
    if (s.over) text += " • GAME OVER — PRESS R";
    this.ui.status.textContent = text;
  };

  PocketArcade.prototype.drawBackdrop = function (top, bottom) {
    const ctx = this.ctx;
    const gradient = ctx.createLinearGradient(0, 0, 0, this.height);
    gradient.addColorStop(0, top); gradient.addColorStop(1, bottom);
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, this.width, this.height);
    ctx.fillStyle = "rgba(255,255,255,.65)";
    for (let i = 0; i < 45; i++) {
      const x = (i * 97 + 31) % 800, y = (i * 53 + 19) % 430;
      ctx.fillRect(x, y, i % 5 === 0 ? 2 : 1, i % 5 === 0 ? 2 : 1);
    }
  };

  PocketArcade.prototype.drawShip = function (x, y, color) {
    const ctx = this.ctx;
    ctx.save(); ctx.translate(x, y);
    ctx.fillStyle = color; ctx.strokeStyle = "#70d6ff"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(0, -27); ctx.lineTo(22, 22); ctx.lineTo(0, 13); ctx.lineTo(-22, 22); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#dff8ff"; ctx.beginPath(); ctx.arc(0, -4, 6, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#ffd343"; ctx.beginPath(); ctx.moveTo(-8, 20); ctx.lineTo(0, 37 + Math.random() * 7); ctx.lineTo(8, 20); ctx.fill();
    ctx.restore();
  };

  PocketArcade.prototype.draw = function () {
    if (this.mode === "neon-blaster") this.drawNeon();
    else if (this.mode === "asteroid-drift") this.drawAsteroids();
    else if (this.mode === "target-blitz") this.drawTargets();
    else if (this.mode === "skybound") this.drawSkybound();
    else if (this.mode === "turbo-trail") this.drawTurbo();
    else if (this.mode === "snake-byte") this.drawSnake();
    else if (this.mode === "orb-breaker") this.drawBreaker();
    this.drawParticles();
    if (this.state.over) this.drawGameOver();
  };

  PocketArcade.prototype.drawNeon = function () {
    const ctx = this.ctx, s = this.state;
    this.drawBackdrop("#080d1b", "#18284b");
    ctx.strokeStyle = "rgba(112,214,255,.15)"; ctx.lineWidth = 1;
    for (let x = 0; x < 800; x += 50) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 450); ctx.stroke(); }
    s.bullets.forEach((b) => { ctx.fillStyle = "#70d6ff"; ctx.shadowColor = "#70d6ff"; ctx.shadowBlur = 12; ctx.fillRect(b.x - 3, b.y - 14, 6, 24); ctx.shadowBlur = 0; });
    s.enemies.forEach((e) => {
      if (this.images.drone.complete) ctx.drawImage(this.images.drone, e.x - 28, e.y - 28, 56, 56);
      else { ctx.fillStyle = "#d64541"; ctx.fillRect(e.x - 20, e.y - 16, 40, 32); }
    });
    this.drawShip(s.player.x, s.player.y, "#2f6fbd");
  };

  PocketArcade.prototype.drawAsteroids = function () {
    const ctx = this.ctx, s = this.state;
    this.drawBackdrop("#070b16", "#151c31");
    s.rocks.forEach((rock) => {
      ctx.save(); ctx.translate(rock.x, rock.y); ctx.rotate(rock.spin);
      ctx.fillStyle = "#526172"; ctx.strokeStyle = "#9aabba"; ctx.lineWidth = 3;
      ctx.beginPath();
      for (let i = 0; i < 9; i++) {
        const angle = i / 9 * Math.PI * 2, radius = rock.r * (.78 + ((i * 7) % 4) * .07);
        const x = Math.cos(angle) * radius, y = Math.sin(angle) * radius;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#394757"; ctx.beginPath(); ctx.arc(-rock.r * .2, -rock.r * .18, rock.r * .2, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    });
    s.bullets.forEach((b) => { ctx.fillStyle = "#ffd343"; ctx.fillRect(b.x - 2, b.y - 12, 4, 20); });
    this.drawShip(s.player.x, s.player.y, "#8f2c52");
  };

  PocketArcade.prototype.drawTargets = function () {
    const ctx = this.ctx, s = this.state, t = s.target;
    const gradient = ctx.createLinearGradient(0, 0, 0, 450); gradient.addColorStop(0, "#173652"); gradient.addColorStop(1, "#0c1722");
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, 800, 450);
    ctx.fillStyle = "rgba(255,255,255,.04)";
    for (let x = 0; x < 800; x += 80) for (let y = 50; y < 450; y += 80) ctx.fillRect(x + 8, y + 8, 64, 64);
    for (let ring = 1; ring >= 0; ring--) {
      ctx.fillStyle = ring ? "#f4efe1" : "#d64541"; ctx.beginPath(); ctx.arc(t.x, t.y, t.r * (ring ? 1 : .58), 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = "#ffd343"; ctx.beginPath(); ctx.arc(t.x, t.y, t.r * .22, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#70d6ff"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(this.pointer.x, this.pointer.y, 18, 0, Math.PI * 2); ctx.moveTo(this.pointer.x - 29, this.pointer.y); ctx.lineTo(this.pointer.x + 29, this.pointer.y); ctx.moveTo(this.pointer.x, this.pointer.y - 29); ctx.lineTo(this.pointer.x, this.pointer.y + 29); ctx.stroke();
    if (s.flash > 0) { ctx.fillStyle = "rgba(255,211,67,.2)"; ctx.fillRect(0, 0, 800, 450); }
  };

  PocketArcade.prototype.drawSkybound = function () {
    const ctx = this.ctx, s = this.state;
    const sky = ctx.createLinearGradient(0, 0, 0, 450); sky.addColorStop(0, "#285d91"); sky.addColorStop(1, "#c8eaff"); ctx.fillStyle = sky; ctx.fillRect(0, 0, 800, 450);
    ctx.fillStyle = "rgba(255,255,255,.65)";
    for (let i = 0; i < 7; i++) { const x = (i * 137 + 25) % 820, y = (i * 71 + 30) % 420; ctx.beginPath(); ctx.ellipse(x, y, 43, 13, 0, 0, Math.PI * 2); ctx.fill(); }
    s.platforms.forEach((p) => { ctx.fillStyle = "#172f43"; ctx.fillRect(p.x, p.y, p.w, 14); ctx.fillStyle = "#70d6ff"; ctx.fillRect(p.x + 3, p.y, p.w - 6, 4); });
    const p = s.player;
    if (this.images.hero.complete) ctx.drawImage(this.images.hero, p.x - 22, p.y - 24, 44, 44);
    else { ctx.fillStyle = "#d64541"; ctx.fillRect(p.x - 16, p.y - 24, 32, 42); }
  };

  PocketArcade.prototype.drawTurbo = function () {
    const ctx = this.ctx, s = this.state;
    const sky = ctx.createLinearGradient(0, 0, 0, 450); sky.addColorStop(0, "#5d3e74"); sky.addColorStop(.55, "#f07f62"); sky.addColorStop(1, "#182837"); ctx.fillStyle = sky; ctx.fillRect(0, 0, 800, 450);
    ctx.fillStyle = "#ffd343"; ctx.beginPath(); ctx.arc(400, 125, 55, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#183448"; ctx.beginPath(); ctx.moveTo(180, 450); ctx.lineTo(340, 165); ctx.lineTo(460, 165); ctx.lineTo(620, 450); ctx.fill();
    ctx.fillStyle = "#343d49"; ctx.beginPath(); ctx.moveTo(230, 450); ctx.lineTo(350, 165); ctx.lineTo(450, 165); ctx.lineTo(570, 450); ctx.fill();
    const offset = (s.time * s.speed) % 80;
    ctx.strokeStyle = "#ffd343"; ctx.lineWidth = 6; ctx.setLineDash([34, 46]); ctx.lineDashOffset = offset;
    for (const x of [352, 448]) { ctx.beginPath(); ctx.moveTo(400 + (x - 400) * .2, 165); ctx.lineTo(x, 450); ctx.stroke(); }
    ctx.setLineDash([]);
    s.traffic.forEach((car) => this.drawCar(ctx, car.x, car.y, car.color, .76));
    this.drawCar(ctx, s.x, 382, "#2f6fbd", 1);
    if (s.flash > 0) { ctx.fillStyle = "rgba(214,69,65,.35)"; ctx.fillRect(0, 0, 800, 450); }
  };

  PocketArcade.prototype.drawCar = function (ctx, x, y, color, scale) {
    ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
    ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.fillRect(-29, -38, 63, 83);
    ctx.fillStyle = color; ctx.fillRect(-28, -40, 56, 78);
    ctx.fillStyle = "#132334"; ctx.fillRect(-19, -28, 38, 27);
    ctx.fillStyle = "#70d6ff"; ctx.fillRect(-15, -24, 30, 9);
    ctx.fillStyle = "#ffd343"; ctx.fillRect(-22, 26, 12, 7); ctx.fillRect(10, 26, 12, 7);
    ctx.fillStyle = "#111"; ctx.fillRect(-34, -27, 7, 21); ctx.fillRect(27, -27, 7, 21); ctx.fillRect(-34, 15, 7, 21); ctx.fillRect(27, 15, 7, 21);
    ctx.restore();
  };

  PocketArcade.prototype.drawSnake = function () {
    const ctx = this.ctx, s = this.state, cellW = 32, cellH = 30;
    ctx.fillStyle = "#0d1c28"; ctx.fillRect(0, 0, 800, 450);
    ctx.strokeStyle = "#1d3546"; ctx.lineWidth = 1;
    for (let x = 0; x <= 800; x += cellW) { ctx.beginPath(); ctx.moveTo(x, 15); ctx.lineTo(x, 435); ctx.stroke(); }
    for (let y = 15; y <= 435; y += cellH) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(800, y); ctx.stroke(); }
    s.snake.forEach((cell, index) => {
      ctx.fillStyle = index === 0 ? "#70e39d" : index % 2 ? "#44a36f" : "#367f59";
      ctx.fillRect(cell.x * cellW + 3, cell.y * cellH + 18, cellW - 6, cellH - 6);
      if (index === 0) { ctx.fillStyle = "#102334"; ctx.fillRect(cell.x * cellW + 19, cell.y * cellH + 23, 4, 4); }
    });
    const pulse = 4 + Math.sin(performance.now() / 120) * 2;
    ctx.fillStyle = "#ffd343"; ctx.beginPath(); ctx.arc(s.food.x * cellW + 16, s.food.y * cellH + 30, 8 + pulse, 0, Math.PI * 2); ctx.fill();
  };

  PocketArcade.prototype.drawBreaker = function () {
    const ctx = this.ctx, s = this.state;
    this.drawBackdrop("#10192b", "#1c3150");
    s.bricks.forEach((brick) => {
      if (!brick.alive) return;
      ctx.fillStyle = brick.color; ctx.fillRect(brick.x, brick.y, brick.w, brick.h);
      ctx.fillStyle = "rgba(255,255,255,.25)"; ctx.fillRect(brick.x + 3, brick.y + 3, brick.w - 6, 3);
    });
    ctx.fillStyle = "#2f6fbd"; ctx.shadowColor = "#70d6ff"; ctx.shadowBlur = 12; ctx.fillRect(s.paddle - 65, 403, 130, 15); ctx.shadowBlur = 0;
    ctx.fillStyle = "#fff"; ctx.shadowColor = "#70d6ff"; ctx.shadowBlur = 15; ctx.beginPath(); ctx.arc(s.ball.x, s.ball.y, 10, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
    if (!s.launched) { ctx.fillStyle = "#fff"; ctx.font = "700 16px sans-serif"; ctx.textAlign = "center"; ctx.fillText("PRESS SPACE OR CLICK TO LAUNCH", 400, 355); }
  };

  PocketArcade.prototype.drawParticles = function () {
    const ctx = this.ctx;
    this.particles.forEach((p) => { ctx.globalAlpha = clamp(p.life * 2, 0, 1); ctx.fillStyle = p.color; ctx.fillRect(p.x - 2, p.y - 2, 5, 5); });
    ctx.globalAlpha = 1;
  };

  PocketArcade.prototype.drawGameOver = function () {
    const ctx = this.ctx, won = this.state.won;
    ctx.fillStyle = "rgba(8,15,24,.78)"; ctx.fillRect(165, 135, 470, 175);
    ctx.strokeStyle = won ? "#70d6ff" : "#d64541"; ctx.lineWidth = 3; ctx.strokeRect(165, 135, 470, 175);
    ctx.fillStyle = "#ffd343"; ctx.font = "900 36px sans-serif"; ctx.textAlign = "center"; ctx.fillText(won ? "ARCADE CLEAR!" : "GAME OVER", 400, 205);
    ctx.fillStyle = "#fff"; ctx.font = "18px sans-serif"; ctx.fillText("Press R or Restart to play again", 400, 253); ctx.textAlign = "left";
  };

  PocketArcade.prototype.start = function () {
    this.visible = true;
    if ("IntersectionObserver" in global) {
      const visibility = new global.IntersectionObserver((entries) => {
        entries.forEach((entry) => { this.visible = entry.isIntersecting; });
      }, { rootMargin: "180px 0px" });
      visibility.observe(this.canvas);
    }
    const loop = (time) => {
      const dt = Math.min(.04, (time - this.last) / 1000 || 0);
      this.last = time;
      if (this.visible) { this.update(dt); this.draw(); }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  };

  const canvas = document.getElementById("arcade-canvas");
  if (canvas) {
    const arcade = new PocketArcade(canvas, {
      status: document.getElementById("arcade-status"),
      title: document.getElementById("arcade-title"),
      description: document.getElementById("arcade-description"),
      badge: document.getElementById("arcade-badge"),
      controls: document.getElementById("arcade-controls"),
    });
    arcade.start();
    global.PocketArcadeGame = arcade;
  }
  global.PocketArcade = PocketArcade;
})(typeof window !== "undefined" ? window : globalThis);
