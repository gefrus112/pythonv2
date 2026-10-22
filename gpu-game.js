/*
 * gpu-game.js — PyHope GPU raycaster.
 *
 * Live mode renders at 1280×720. Benchmark mode asks WebGL2 for a single
 * 4096×2304 frame: 9,437,184 independently ray-cast pixels. It is opt-in so
 * phones and low-power laptops are not forced to allocate a 36 MB framebuffer.
 */
(function (global) {
  "use strict";

  const LIVE_W = 1280, LIVE_H = 720;
  const NINE_W = 4096, NINE_H = 2304; // 9,437,184 pixels

  const VERT = `#version 300 es
    precision highp float;
    const vec2 P[3] = vec2[3](vec2(-1.,-1.), vec2(3.,-1.), vec2(-1.,3.));
    void main() { gl_Position = vec4(P[gl_VertexID], 0., 1.); }
  `;

  const FRAG = `#version 300 es
    precision highp float;
    uniform vec2 uResolution;
    uniform vec2 uPosition;
    uniform float uYaw;
    uniform float uTime;
    out vec4 outColor;

    float tile(ivec2 p) {
      if (p.x < 0 || p.y < 0 || p.x >= 24 || p.y >= 24) return 1.;
      if (p.x == 0 || p.y == 0 || p.x == 23 || p.y == 23) return 4.;
      if (p.x == 11 && p.y > 0 && p.y < 19 && p.y != 7 && p.y != 15) return 2.;
      if (p.y == 12 && p.x > 1 && p.x < 11 && p.x != 7) return 3.;
      if (p.x > 14 && p.x < 21 && p.y == 6 && p.x != 18) return 1.;
      if (p.x == 17 && p.y > 9 && p.y < 20 && p.y != 14) return 2.;
      if (p.y == 20 && p.x > 3 && p.x < 16 && p.x != 8) return 3.;
      if (p.x == 5 && p.y > 2 && p.y < 9 && p.y != 6) return 1.;
      return 0.;
    }

    vec3 palette(float t, float side, float dist, float wallX) {
      vec3 c;
      if (t < 1.5) {
        float brick = step(.08, fract(wallX * 8. + floor(dist * 2.) * .5));
        c = mix(vec3(.25,.10,.08), vec3(.78,.25,.19), brick);
      } else if (t < 2.5) {
        c = vec3(.10,.34,.62) + .12 * step(.87, fract(wallX * 10.));
      } else if (t < 3.5) {
        c = vec3(.62,.55,.38) * (0.82 + 0.18 * sin(wallX * 75.));
      } else {
        c = mix(vec3(.08,.15,.24), vec3(1.,.78,.16), step(.76, fract(wallX * 4.)));
      }
      c *= side > .5 ? .68 : 1.;
      float fog = 1. / (1. + dist * dist * .018);
      return mix(vec3(.035,.055,.08), c, fog);
    }

    void main() {
      vec2 uv = (gl_FragCoord.xy * 2. - uResolution) / uResolution.y;
      float horizon = uv.y;
      float ca = cos(uYaw), sa = sin(uYaw);
      vec2 dir = vec2(ca, sa);
      vec2 plane = vec2(-sa, ca) * .72;
      vec2 ray = normalize(dir + plane * uv.x);
      ivec2 cell = ivec2(floor(uPosition));
      vec2 delta = abs(1. / max(abs(ray), vec2(.00001)));
      ivec2 stepDir = ivec2(sign(ray));
      vec2 sideDist = (mix(vec2(cell), vec2(cell + 1), step(vec2(0.), ray)) - uPosition) / ray;
      sideDist = abs(sideDist);

      float hitTile = 0.;
      float side = 0.;
      float dist = 30.;
      for (int i = 0; i < 32; i++) {
        if (sideDist.x < sideDist.y) {
          dist = sideDist.x; sideDist.x += delta.x; cell.x += stepDir.x; side = 0.;
        } else {
          dist = sideDist.y; sideDist.y += delta.y; cell.y += stepDir.y; side = 1.;
        }
        hitTile = tile(cell);
        if (hitTile > .5) break;
      }

      float wallHeight = 1. / max(.001, dist);
      vec3 sky = mix(vec3(.035,.075,.15), vec3(.38,.61,.76), clamp(1. - uv.y, 0., 1.));
      vec3 floorColor = mix(vec3(.05,.055,.06), vec3(.22,.20,.16), clamp(uv.y + .5, 0., 1.));
      vec3 color = uv.y > 0. ? sky : floorColor;

      if (abs(horizon) < wallHeight) {
        vec2 hit = uPosition + ray * dist;
        float wallX = side < .5 ? fract(hit.y) : fract(hit.x);
        color = palette(hitTile, side, dist, wallX);
        // emissive scan line — a tiny bit of comet-tech atmosphere
        color += .07 * vec3(.25,.75,1.) * (1. - smoothstep(0., .025, abs(fract((horizon / wallHeight + uTime * .08) * 12.) - .5)));
      }

      // compact crosshair; constant in screen pixels at all resolutions
      vec2 centerPx = abs(gl_FragCoord.xy - uResolution * .5);
      float crosshair = max(
        step(centerPx.x, 1.2) * step(4., centerPx.y) * step(centerPx.y, 13.),
        step(centerPx.y, 1.2) * step(4., centerPx.x) * step(centerPx.x, 13.)
      );
      color = mix(color, vec3(.26,.83,1.), crosshair);
      color = pow(color, vec3(.84));
      outColor = vec4(color, 1.);
    }
  `;

  function compile(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(message || "shader compilation failed");
    }
    return shader;
  }

  function GpuRaycaster(canvas, hud) {
    this.canvas = canvas;
    this.hud = hud || {};
    this.gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
      depth: false,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true,
    });
    this.running = false;
    this.keys = new Set();
    this.position = [6.0, 2.0];
    this.yaw = Math.PI / 2;
    this.last = 0;
    this.frames = 0;
    this.fpsTime = 0;
    this.mode = "live";
    this.error = null;

    if (!this.gl) {
      this.error = "WebGL2 is unavailable in this browser.";
      if (this.hud.status) this.hud.status.textContent = this.error;
      return;
    }

    try {
      const gl = this.gl;
      const program = gl.createProgram();
      gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERT));
      gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
      this.program = program;
      this.uniforms = {
        resolution: gl.getUniformLocation(program, "uResolution"),
        position: gl.getUniformLocation(program, "uPosition"),
        yaw: gl.getUniformLocation(program, "uYaw"),
        time: gl.getUniformLocation(program, "uTime"),
      };
      this.vao = gl.createVertexArray();
      gl.bindVertexArray(this.vao);
      this.resize(LIVE_W, LIVE_H);
    } catch (error) {
      this.error = "GPU engine failed: " + error.message;
      if (this.hud.status) this.hud.status.textContent = this.error;
    }

    this._down = (event) => {
      this.keys.add(event.code);
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(event.code) &&
          document.activeElement === canvas) event.preventDefault();
    };
    this._up = (event) => this.keys.delete(event.code);
    this._focus = () => canvas.focus();
  }

  GpuRaycaster.prototype.attach = function () {
    if (this.error) return;
    window.addEventListener("keydown", this._down);
    window.addEventListener("keyup", this._up);
    this.canvas.addEventListener("click", this._focus);
    this.canvas.tabIndex = 0;
  };

  GpuRaycaster.prototype.resize = function (width, height) {
    if (!this.gl) return;
    const max = this.gl.getParameter(this.gl.MAX_VIEWPORT_DIMS);
    if (width > max[0] || height > max[1]) throw new Error("GPU maximum viewport is " + max[0] + "×" + max[1]);
    this.canvas.width = width;
    this.canvas.height = height;
    this.gl.viewport(0, 0, width, height);
  };

  GpuRaycaster.prototype.update = function (dt) {
    const turn = 1.8 * dt;
    if (this.keys.has("ArrowLeft") || this.keys.has("KeyQ")) this.yaw -= turn;
    if (this.keys.has("ArrowRight") || this.keys.has("KeyE")) this.yaw += turn;
    const dirX = Math.cos(this.yaw), dirY = Math.sin(this.yaw);
    const rightX = -dirY, rightY = dirX;
    const speed = (this.keys.has("ShiftLeft") ? 4.2 : 2.4) * dt;
    let dx = 0, dy = 0;
    if (this.keys.has("KeyW") || this.keys.has("ArrowUp")) { dx += dirX * speed; dy += dirY * speed; }
    if (this.keys.has("KeyS") || this.keys.has("ArrowDown")) { dx -= dirX * speed; dy -= dirY * speed; }
    if (this.keys.has("KeyA")) { dx -= rightX * speed; dy -= rightY * speed; }
    if (this.keys.has("KeyD")) { dx += rightX * speed; dy += rightY * speed; }
    // The shader map's large outer box gives us safe simple collision here.
    this.position[0] = Math.max(1.2, Math.min(22.8, this.position[0] + dx));
    this.position[1] = Math.max(1.2, Math.min(22.8, this.position[1] + dy));
  };

  GpuRaycaster.prototype.draw = function (time) {
    if (this.error) return;
    const gl = this.gl;
    gl.useProgram(this.program);
    gl.bindVertexArray(this.vao);
    gl.uniform2f(this.uniforms.resolution, this.canvas.width, this.canvas.height);
    gl.uniform2f(this.uniforms.position, this.position[0], this.position[1]);
    gl.uniform1f(this.uniforms.yaw, this.yaw);
    gl.uniform1f(this.uniforms.time, time * 0.001);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };

  GpuRaycaster.prototype.start = function () {
    if (this.running || this.error) return;
    this.mode = "live";
    this.resize(LIVE_W, LIVE_H);
    this.running = true;
    this.last = performance.now();
    const loop = (time) => {
      if (!this.running) return;
      const dt = Math.min(0.05, (time - this.last) / 1000);
      this.last = time;
      this.update(dt);
      this.draw(time);
      this.frames++;
      this.fpsTime += dt;
      if (this.fpsTime >= 0.5) {
        const fps = Math.round(this.frames / this.fpsTime);
        if (this.hud.status) this.hud.status.textContent = "LIVE • 1280×720 • " + fps + " FPS";
        this.frames = 0;
        this.fpsTime = 0;
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  };

  GpuRaycaster.prototype.renderNineMillion = function () {
    if (this.error) return false;
    this.running = false;
    this.mode = "9m";
    try {
      this.resize(NINE_W, NINE_H);
      const start = performance.now();
      this.draw(start);
      this.gl.finish();
      const elapsed = Math.max(0.1, performance.now() - start);
      if (this.hud.status) {
        this.hud.status.textContent = "9,437,184 PIXELS • 4096×2304 • " + elapsed.toFixed(1) + " ms";
      }
      return true;
    } catch (error) {
      if (this.hud.status) this.hud.status.textContent = "9M mode unavailable: " + error.message;
      return false;
    }
  };

  GpuRaycaster.prototype.stop = function () { this.running = false; };

  GpuRaycaster.LIVE_PIXELS = LIVE_W * LIVE_H;
  GpuRaycaster.NINE_MILLION_PIXELS = NINE_W * NINE_H;
  global.GpuRaycaster = GpuRaycaster;
})(typeof globalThis !== "undefined" ? globalThis : this);
