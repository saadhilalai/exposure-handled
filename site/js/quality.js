// Automatic quality, so the page stays smooth on ordinary computers, not just fast ones.
// Three levels (high, medium, low). A first guess comes from the graphics chip, CPU cores and memory; then the
// real frame rate decides. When frames run long, the render resolution comes down a little at a time; if that
// isn't enough, the level steps down. It never steps back up within a visit (no flip-flopping).

export const LEVELS = {
  //          3D pixel ratio · depth of field · glow · agents · picture pixel ratio · blur taps · rear-screen fps
  high:   { pr3d: 1.5,  dof: true,  bloom: true,  agents: 380, prSim: 1.25, taps: 64, lcdFps: 30, msaa: 4 },
  medium: { pr3d: 1.0,  dof: false, bloom: true,  agents: 220, prSim: 1.0,  taps: 40, lcdFps: 15, msaa: 4 },
  low:    { pr3d: 0.75, dof: false, bloom: false, agents: 110, prSim: 0.7,  taps: 24, lcdFps: 8,  msaa: 0 },
};
const ORDER = ["high", "medium", "low"];
const SLOW_MS = 21;          // a frame longer than this on average = below ~48 fps
const FAST_MS = 15.5;        // comfortably at 60
const WINDOW_MS = 1500;      // judge over this long
const MIN_SCALE = 0.7, STEP_DOWN = 0.85, STEP_UP = 1.06;

function guess() {
  const forced = /[?&]quality=(high|medium|low)\b/.exec(location.search);
  if (forced) return forced[1];
  let gpu = "";
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
    gpu = gl ? (ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : "none";
  } catch { gpu = "none"; }
  const cores = navigator.hardwareConcurrency || 4, mem = navigator.deviceMemory || 8;
  const phone = document.documentElement.classList.contains("low");
  if (gpu === "none" || /swiftshader|llvmpipe|software|basic render/i.test(gpu)) return "low";
  if (phone || cores <= 4 || mem <= 4 || /intel(?!.*(iris xe|arc))|mali|adreno|powervr|uhd|hd graphics/i.test(gpu)) return "medium";
  return "high";
}

export function createQuality() {
  const q = {
    level: guess(), scale: 1, fps: 0, frameMs: 16.7, listeners: new Set(), busy: () => true,
    get settings() { return LEVELS[q.level]; },
    onChange(fn) { q.listeners.add(fn); fn(q); return () => q.listeners.delete(fn); },
    set(level) { if (level !== q.level) { q.level = level; q.scale = 1; q.listeners.forEach((fn) => fn(q)); } },
  };
  q.startLevel = q.level;
  const fixed = /[?&]quality=/.test(location.search);
  // Watch every frame (cheap): judge only while something heavy is on screen.
  let last = performance.now(), acc = 0, n = 0, t0 = last, fastFor = 0, grace = performance.now() + 2500;
  (function tick(now) {
    const dt = now - last; last = now;
    if (dt < 250) { acc += dt; n++; }                 // ignore pauses (tab hidden, Mac asleep)
    if (now - t0 >= WINDOW_MS && n) {
      const avg = acc / n;
      q.frameMs = avg; q.fps = Math.round(1000 / avg);
      if (!fixed && q.busy() && now > grace) {
        if (avg > SLOW_MS) {
          fastFor = 0;
          if (q.scale > MIN_SCALE + 1e-3) { q.scale = Math.max(MIN_SCALE, q.scale * STEP_DOWN); q.listeners.forEach((fn) => fn(q)); }
          else if (ORDER.indexOf(q.level) < ORDER.length - 1) { q.set(ORDER[ORDER.indexOf(q.level) + 1]); grace = now + 2000; }
        } else if (avg < FAST_MS && q.scale < 1) {
          fastFor += now - t0;
          if (fastFor > 4000) { q.scale = Math.min(1, q.scale * STEP_UP); fastFor = 0; q.listeners.forEach((fn) => fn(q)); }
        }
      }
      acc = 0; n = 0; t0 = now;
    }
    requestAnimationFrame(tick);
  })(last);
  return q;
}
