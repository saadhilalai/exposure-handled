// Automatic quality, so the page stays smooth on ordinary computers, not just fast ones.
// Three levels (high, medium, low). A first guess comes from the graphics chip, CPU cores and memory; then the
// real frame rate decides. When frames run long, the render resolution comes down a little at a time; if that
// isn't enough, the level steps down. It never steps back up within a visit (no flip-flopping).

export const LEVELS = {
  //          3D pixel ratio · depth of field · glow · agents · picture pixel ratio · blur taps
  high:   { pr3d: 1.5,  dof: true,  bloom: true,  agents: 380, prSim: 1.25, taps: 64, msaa: 4 },
  medium: { pr3d: 1.0,  dof: false, bloom: true,  agents: 220, prSim: 1.0,  taps: 40, msaa: 4 },
  low:    { pr3d: 0.75, dof: false, bloom: false, agents: 110, prSim: 0.7,  taps: 24, msaa: 0 },
};
const ORDER = ["high", "medium", "low"];
// Testing only: ?gpuload=N renders N times the pixels, to act like a graphics chip N times weaker than this one.
export const GPU_LOAD = Math.max(1, +(/[?&]gpuload=([\d.]+)/.exec(location.search) || [0, 1])[1]);
const SLOW_MS = 21;          // a frame longer than this on average = below ~48 fps
const VERY_SLOW_MS = 40;     // under ~25 fps: skip the small steps, drop a whole level at once
const CRAWL_MS = 66;         // under ~15 fps: straight to the lowest level
const FAST_MS = 15.5;        // comfortably at 60
const WINDOW_MS = 1000;      // judge over this long
const MIN_SCALE = { high: 0.7, medium: 0.7, low: 0.45 }, STEP_DOWN = 0.85, STEP_UP = 1.06;

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
    get settings() { return { ...LEVELS[q.level], load: GPU_LOAD }; },
    onChange(fn) { q.listeners.add(fn); fn(q); return () => q.listeners.delete(fn); },
    set(level) { if (level !== q.level) { q.level = level; q.scale = 1; q.listeners.forEach((fn) => fn(q)); } },
  };
  q.startLevel = q.level;
  const fixed = /[?&]quality=/.test(location.search);
  // Watch every frame (cheap): judge only while something heavy is on screen.
  let last = performance.now(), acc = 0, n = 0, t0 = last, fastFor = 0, grace = performance.now() + 1000;
  (function tick(now) {
    const dt = now - last; last = now;
    if (dt < 250) { acc += dt; n++; }                 // ignore pauses (tab hidden, Mac asleep)
    if (now - t0 >= WINDOW_MS && n) {
      const avg = acc / n;
      q.frameMs = avg; q.fps = Math.round(1000 / avg);
      if (!fixed && q.busy() && now > grace) {
        const lower = ORDER.indexOf(q.level) < ORDER.length - 1;
        if (avg > CRAWL_MS && lower) {
          fastFor = 0; q.set("low"); grace = now + 600;
        } else if (avg > VERY_SLOW_MS && lower) {
          fastFor = 0; q.set(ORDER[ORDER.indexOf(q.level) + 1]); grace = now + 600;
        } else if (avg > SLOW_MS) {
          fastFor = 0;
          const min = MIN_SCALE[q.level];
          // the cost goes with the pixel count (scale squared), so one step lands near 60 fps
          if (q.scale > min + 1e-3) { q.scale = Math.max(min, q.scale * Math.min(STEP_DOWN, 0.95 * Math.sqrt(16.7 / avg))); q.listeners.forEach((fn) => fn(q)); }
          else if (lower) { q.set(ORDER[ORDER.indexOf(q.level) + 1]); grace = now + 1500; }
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
