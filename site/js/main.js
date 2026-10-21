// Camera Agent · project site v2. The page plays like a camera: a viewfinder where the AI takes over, a pull-back
// to the camera itself, an exploded view with the crew at work, then things to play with.
import { createSim, SCENES, ISOS, SHUTTERS, FNUMS, KELVINS } from "./sim.js";
import { $, $$, wait, clamp, motion, sound, toast, Dial, Feed, magnetic, lockFrame, grain, countUp, nearest } from "./ui.js";
import { solve, score, turn, fmt, RANGES } from "./ai.js";
import { createQuality } from "./quality.js";

const html = document.documentElement;
const low = html.classList.contains("low");
const mobile = () => innerWidth < 820;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
function kf(p, keys) {
  if (p <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [p1, v1] = keys[i];
    if (p <= p1) { const [p0, v0] = keys[i - 1]; const t = smooth(p0, p1, p); return v0 + (v1 - v0) * t; }
  }
  return keys[keys.length - 1][1];
}

let sim = null, cam3d = null, data = null;
const quality = createQuality();
quality.cpuMs = () => (cam3d ? cam3d.cpuMs : 0);
window.__quality = () => quality.level + " " + quality.scale.toFixed(2) + " cpu " + quality.cpuMs().toFixed(1);   // read by the speed tests
const views = {};
const prog = { hero: 0, inside: 0, try: 0, finale: 0 };

async function main() {
  grain();
  if (!window.gsap) await new Promise((r) => addEventListener("load", r, { once: true }));
  gsap.registerPlugin(ScrollTrigger);
  ScrollTrigger.config({ ignoreMobileResize: true });
  data = await fetch("data/site.json").then((r) => r.json()).catch(() => null);
  try { sim = createSim({ low }); } catch (e) { console.warn("simulator off:", e); }
  // No real graphics chip (software rendering): skip the 3D, and keep the camera pictures small and calm.
  const software = !sim || sim.software;
  if (software) { quality.set("low"); html.classList.add("no3d", "nogpu"); }
  quality.onChange(applyQuality);
  fpsMeter();
  nav(); toggles(); magnetic(); lockFrame(); eggs(); lineWrap();
  let heroReady = Promise.resolve();
  if (sim) { simLoop(); heroReady = hero(); }
  // build the 3D camera once the opening is over, or as soon as someone scrolls, whichever comes first
  await new Promise((res) => {
    if (!motion) return res();
    heroReady.then(res); setTimeout(res, 8000);
    for (const ev of ["wheel", "touchmove", "keydown", "scroll"]) addEventListener(ev, res, { once: true, passive: true });
  });
  if (!software) await load3D();
  heroPull();
  inside();
  if (sim) { tryIt(); game(); compare(); }
  real(); safety(); dash(); finale(); heads();
  if (/[?&]debug\b/.test(location.search)) window.__debug = { sim, cam3d, views };   // for testing only (?debug)
  await document.fonts.ready;
  ScrollTrigger.refresh();
}

// One quality level for everything heavy: the 3D camera and the camera pictures.
function applyQuality(q) {
  cam3d?.setQuality(q.settings, q.scale);
  sim?.setQuality(sim.software ? { prSim: 0.3, taps: 8 } : q.settings, sim?.software ? 1 : q.scale);
  if (sim?.software) for (const v of sim.views) v.fpsCap = 10;     // no graphics chip: small pictures, 10 a second
  views.hero?.refit?.();
}

// Nerd mode: frame rate and quality level, so anyone can check on their own computer.
function fpsMeter() {
  const el = $("#fps-meter");
  if (!el) return;
  setInterval(() => {
    if (!html.classList.contains("nerd-on")) return;
    const pct = quality.scale < 0.999 ? " · " + Math.round(quality.scale * 100) + "%" : "";
    el.textContent = `${quality.fps || "…"} fps · ${quality.level}${pct}${html.classList.contains("no3d") ? " · no 3D" : ""}`;
    el.classList.toggle("slow", quality.fps && quality.fps < 45);
  }, 500);
}

// wrap each headline line so it can rise out of its own mask
function lineWrap() { $$(".big .line, .huge .line, .hero-title .line").forEach((l) => (l.innerHTML = `<span class="in">${l.innerHTML}</span>`)); }

// ---------- the simulator's render loop: only views on screen are drawn ----------
function simLoop() {
  if (sim.software) { const view = sim.view; sim.view = (...a) => { const v = view(...a); v.fpsCap = 10; return v; }; }
  const io = new IntersectionObserver((es) => es.forEach((e) => { const v = e.target.__view; if (v) v.visible = e.isIntersecting; }), { rootMargin: "40px" });
  sim.observe = (v) => { v.canvas.__view = v; v.visible = false; io.observe(v.canvas); };
  (function loop(now) { sim.render(now); requestAnimationFrame(loop); })(performance.now());
}

// ---------- nav, toggles, easter eggs ----------
function nav() {
  const n = $("#nav");
  const upd = () => n.classList.toggle("solid", scrollY > 40);
  addEventListener("scroll", upd, { passive: true }); upd();
}
function toggles() {
  const s = $("#sound-toggle"), nb = $("#nerd-toggle");
  s.addEventListener("click", () => {
    const on = !sound.on;
    on ? sound.enable() : sound.disable();
    s.setAttribute("aria-pressed", on); if (on) { sound.beep(); }
    toast(on ? "Sound on" : "Sound off");
  });
  const setNerd = (on, quiet) => {
    html.classList.toggle("nerd-on", on); nb.setAttribute("aria-pressed", on);
    try { localStorage.setItem("nerd", on ? "1" : "0"); } catch {}
    if (!quiet) { toast(on ? "Nerd mode on" : "Nerd mode off"); sound.tick(); }
    requestAnimationFrame(() => ScrollTrigger.refresh());
  };
  nb.addEventListener("click", () => setNerd(!html.classList.contains("nerd-on")));
  try { if (localStorage.getItem("nerd") === "1") setNerd(true, true); } catch {}
  addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || /input|textarea/i.test(e.target.tagName)) return;
    if (e.key === "n" || e.key === "N") setNerd(!html.classList.contains("nerd-on"));
    if (e.key === "m" || e.key === "M") s.click();
  });
}
function eggs() {
  addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || /input|textarea/i.test(e.target.tagName)) return;
    if (e.key === "z" || e.key === "Z") {
      const on = html.classList.toggle("zebra"); if (sim) sim.fx.zebra = on;
      toast(on ? "Zebras on · 95%" : "Zebras off"); sound.beep();
    }
    if (e.key === "f" || e.key === "F") {
      const on = html.classList.toggle("fc"); if (sim) sim.fx.falseColor = on;
      toast(on ? "False color on" : "False color off"); sound.beep();
    }
  });
}

// ---------- shared: the AI turning dials, one detent at a time, while it talks ----------
async function runAI(view, sceneIdx, { feed, dials, tally, onSet, speed = 1 }) {
  const plan = solve(sim, sceneIdx, { ...view.a });
  tally?.classList.add("on");
  Object.values(dials || {}).forEach((d) => { d.ai(true); d.lock(true); });
  await feed.say(plan.assess, "", 420 / speed);
  for (const st of plan.steps) {
    await feed.say(st.msg, "", 260 / speed);
    await turn(st.key, st.from, st.to, (val, i) => {
      view.a[st.key] = val;
      if (dials?.[st.key]) dials[st.key].set(i, { source: "ai" }); else sound.tick();
      onSet?.(st.key, val);
    }, { speed });
    await wait(140 / speed);
  }
  await feed.say(plan.final.msg, plan.final.cls, 240 / speed);
  sound.click();
  Object.values(dials || {}).forEach((d) => { d.ai(false); d.lock(false); });
  setTimeout(() => tally?.classList.remove("on"), 1800);
  return plan;
}

function makeDials(parent, view, onUser, size) {
  parent.innerHTML = "";
  const conf = [["iso", "ISO", ISOS], ["shutter", "Shutter", SHUTTERS], ["fnum", "Iris", FNUMS], ["wb", "WB", KELVINS]];
  const out = {};
  conf.forEach(([k, label, list]) => {
    out[k] = Dial(parent, { key: k, label, values: list, format: fmt[k], index: nearest(list, view.a[k]), ok: RANGES[k], size,
      onChange: (val, i, src) => { view.a[k] = val; if (src === "user") onUser?.(k, val); } });
  });
  return out;
}

// luminance histogram of a picture, clipped bins in red
const histoTmp = document.createElement("canvas"); histoTmp.width = 64; histoTmp.height = 36;
const histoCtx = histoTmp.getContext("2d");    // GPU-side scale-down, then read back only 64 × 36 pixels
function histogram(src, ctx, w, h) {
  histoCtx.drawImage(src, 0, 0, 64, 36);
  const d = histoCtx.getImageData(0, 0, 64, 36).data, n = 40, bins = new Array(n).fill(0);
  for (let i = 0; i < d.length; i += 4) bins[Math.min(n - 1, Math.floor(((d[i] * 0.2126 + d[i + 1] * 0.7152 + d[i + 2] * 0.0722) / 256) * n))]++;
  const mx = Math.max(...bins.slice(1, n - 1), 1), bw = w / n;
  ctx.clearRect(0, 0, w, h);
  bins.forEach((b, i) => { ctx.fillStyle = i >= n - 2 ? "rgba(255,90,60,.95)" : "rgba(255,255,255,.72)"; const hh = Math.min(h - 2, (b / mx) * (h - 2)); ctx.fillRect(i * bw, h - hh, Math.max(1, bw - 1), hh); });
}

// the focus box sits on the reel, wherever the crop puts it
function placeAF(box, view) {
  const c = view.canvas, w = c.clientWidth, h = c.clientHeight;
  if (!w || !view.w) return;
  const win = sim.windowFor(view.w, view.h, view.zoom);
  const cx = ((-0.13 - win[0]) / win[2]) * w, cy = (1 - (0.085 - win[1]) / win[3]) * h;
  const s = ((0.19 * 2 * 1.16) / win[2]) * w;
  box.style.transform = `translate(${cx - s / 2}px, ${cy - s / 2}px)`; box.style.width = box.style.height = s + "px";
}

// ============ 1 · viewfinder: the AI takes over ============
function hero() {
  const canvas = $("#hero-canvas");
  const v = (views.hero = sim.view(canvas, { scene: HERO_SCENE }));
  sim.observe(v);
  // a fixed render size, so the picture doesn't reallocate while the frame shrinks into the camera
  let level = 1;
  const fit = () => { const d = Math.max(0.35, Math.min(devicePixelRatio || 1, quality.settings.prSim) * quality.scale) * Math.sqrt(quality.settings.load), cap = (low ? 900 : 1440) * level * Math.sqrt(quality.settings.load); let w = Math.round(innerWidth * d), h = Math.round(innerHeight * d); if (w > cap) { h = Math.round(h * cap / w); w = cap; } v.size = [w, h]; };
  v.refit = fit;
  fit(); addEventListener("resize", fit);
  v.setLevel = (l) => { if (l !== level) { level = l; fit(); } };
  Object.assign(v.a, { iso: 12800, shutter: 1 / 48, fnum: 2.8, wb: 6500 });
  const feed = Feed($("#hero-feed"), { max: 4 });
  const hud = { iso: $("#h-iso"), shutter: $("#h-sh"), fnum: $("#h-f"), wb: $("#h-wb") };
  const hf = { iso: (x) => x, shutter: (x) => "1/" + Math.round(1 / x), fnum: (x) => "F" + x, wb: (x) => Math.round(x) + "K" };
  const setHud = (k, val, flash) => {
    hud[k].textContent = hf[k](val);
    if (flash) { hud[k].classList.add("tick"); clearTimeout(hud[k]._t); hud[k]._t = setTimeout(() => hud[k].classList.remove("tick"), 240); }
  };
  Object.keys(hud).forEach((k) => setHud(k, v.a[k]));
  // timecode at 23.976
  const tc = $("#hero-tc"), t0 = performance.now(), p2 = (n) => String(n).padStart(2, "0");
  setInterval(() => {
    if (prog.hero > 0.15) return;                 // faded out: no need to keep rewriting it
    const f = Math.floor(((performance.now() - t0) / 1000) * 23.976);
    tc.textContent = `01:${p2(Math.floor(f / 1440) % 60)}:${p2(Math.floor(f / 24) % 60)}:${p2(f % 24)}`;
  }, 42);
  // meter, focus box, histogram
  const af = $("#hero-af"), needle = $("#h-meter .needle"), hc = $("#h-histo"), hx = hc.getContext("2d");
  let lastH = 0;
  v.onFrame = (view) => {
    placeAF(af, view);
    const m = sim.meter(HERO_SCENE, view.a, view.scene);
    needle.style.left = clamp((m.subject + 3) / 6, 0, 1) * 100 + "%";
    const now = performance.now();
    if (now - lastH > 320 && hc.offsetParent && prog.hero < 0.1) { lastH = now; histogram(view.canvas, hx, 120, 44); }
  };
  // title hidden until the AI is done
  const lines = $$("#hero-title .in");
  const reveal = () => motion ? gsap.fromTo(lines, { yPercent: 110 }, { yPercent: 0, duration: 1.3, ease: "expo.out", stagger: 0.12 }) : null;
  if (motion) gsap.set(lines, { yPercent: 110 });
  const intro = async () => {
    await wait(1100);
    await runAI(v, HERO_SCENE, { feed, tally: $("#ai-tally"), onSet: (k, val) => setHud(k, val, true), speed: 0.85 });
    af.classList.add("lock");
    reveal();
    await wait(1500);
    ready();
    await wait(1100);
    // keep the last line on a laptop; on a phone the chat would sit on the picture, so it all goes
    [...$("#hero-feed").children].slice(0, mobile() ? undefined : -1).forEach((li, i) => gsap.to(li, { opacity: 0, y: -8, duration: 0.5, delay: i * 0.06, ease: "power2.in" }));
  };
  let ready;
  const readyP = new Promise((r) => (ready = r));
  if (motion) intro();
  else {
    ready();
    const plan = solve(sim, HERO_SCENE, { ...v.a });
    Object.assign(v.a, plan.target); Object.keys(hud).forEach((k) => setHud(k, v.a[k]));
    feed.push(plan.final.msg, "done"); af.classList.add("lock");
  }
  return readyP;
}

// ============ the 3D camera ============
const HERO_SCENE = 1;   // tungsten: warm lamp, blue dusk window, string lights
const HERO_POSE = { yaw: Math.PI, pitch: 0.05, dist: 3.4, tx: -0.13, ty: -0.02, tz: -0.47, explode: 0, agents: 0, frameX: 0, frameY: 0, lift: 0, mode: "idle", focus: "lcd" };
async function load3D() {
  for (let attempt = 0; attempt < 2 && !cam3d; attempt++) {
    try {
      const m = await import("./camera3d.js" + (attempt ? "?retry" : ""));
      cam3d = m.createCamera3D($("#cam3d"), { low: low || attempt > 0 });
    } catch (e) { console.warn("3D off:", e); window.__3dError = String((e && e.stack) || e); cam3d = null; await wait(600); }
  }
  if (!cam3d) { html.classList.add("no3d"); return; }
  if (motion) setTimeout(() => { if (prog.hero < 0.05 && !cam3d.running) cam3d.warmup(); }, 350);
  Object.assign(cam3d.state, HERO_POSE); cam3d.settle();
  cam3d.setQuality(quality.settings, quality.scale);
  if (sim && views.hero) {
    const lv = (views.lcd = sim.view(cam3d.lcdCanvas, { scene: HERO_SCENE, size: [640, 360] }));
    lv.a = views.hero.a; lv.t0 = views.hero.t0; lv.visible = false;
    // The rear screen gets one still frame (copying a live picture between the two graphics contexts stalls a frame).
    lv.onFrame = () => { cam3d.lcdChanged(); lv.visible = false; lv.snapped = true; };
  }
  if (!motion) {
    // still picture of the exploded camera behind the "inside" beats
    Object.assign(cam3d.state, { yaw: 0.85, pitch: 0.25, dist: 10.5, explode: 1, agents: 1, tx: 0, ty: 0.15, tz: 0.9, frameX: mobile() ? 0 : 0.22 });
    cam3d.settle();
    const io = new IntersectionObserver(([e]) => { $("#cam3d").style.opacity = e.isIntersecting ? 0.55 : 0; if (e.isIntersecting) cam3d.renderOnce(); });
    io.observe($("#inside"));
  }
}
function vis3D() {
  if (!cam3d || !motion) return;
  const o = prog.finale > 0 ? smooth(0, 0.18, prog.finale)
    : prog.try > 0 ? 1 - smooth(0, 1, prog.try)
    : prog.inside > 0 ? 1
    : smooth(0.3, 0.6, prog.hero);
  $("#cam3d").style.opacity = o;
  $(".cam3d-shade").style.opacity = prog.inside > 0.12 && prog.try === 0 ? smooth(0.12, 0.2, prog.inside) : 0;
  if (o > 0.005) cam3d.start(); else cam3d.stop();
  // one still frame for the rear screen, taken just before the viewfinder lands on it
  if (views.lcd && !views.lcd.snapped && prog.hero > 0.45) views.lcd.visible = true;
  if (views.lcd && prog.hero < 0.2) views.lcd.snapped = false;
}

// ============ pull back from the viewfinder to the camera's own screen ============
function heroPull() {
  if (!motion) return;
  const vf = $("#vf"), fade = [$(".vf-hud"), $("#hero-feed"), $(".scroll-cue")], title = $("#hero-title");
  ScrollTrigger.create({
    trigger: ".hero", start: "top top", end: "bottom bottom", scrub: true,
    onUpdate: (s) => {
      const p = (prog.hero = s.progress);
      fade.forEach((el) => (el.style.opacity = 1 - smooth(0, 0.12, p)));
      title.style.transform = `translateY(${-p * 160}px)`; title.style.opacity = 1 - smooth(0.02, 0.22, p);
      if (cam3d) {
        Object.assign(cam3d.state, HERO_POSE); cam3d.settle();
        cam3d.resize();
        const r = cam3d.lcdRect(), W = innerWidth, H = innerHeight;
        const e = smooth(0.1, 0.88, p);
        vf.style.left = r.left * e + "px"; vf.style.top = r.top * e + "px";
        vf.style.width = W + (r.width - W) * e + "px"; vf.style.height = H + (r.height - H) * e + "px";
        vf.style.borderRadius = 2 + 8 * e + "px";
        vf.style.opacity = 1 - smooth(0.86, 0.97, p);
        if (views.hero) { views.hero.setLevel(e < 0.25 ? 1 : e < 0.6 ? 0.5 : 0.3); views.hero.hold = p > 0.975; }
      } else {
        vf.style.opacity = 1 - smooth(0.4, 0.9, p);
      }
      vis3D();
    },
  });
}

// ============ 2 · inside the camera: the scroll backbone ============
function inside() {
  const beats = Object.fromEntries($$(".beat").map((b) => [b.dataset.beat, b]));
  const dots = $$(".inside-progress i");
  buildIsoGauge(); buildStopwatch();
  killSwitch();
  if (!motion || !cam3d) return;
  const S = cam3d.state;
  const A = { sensor: cam3d.anchor("sensor"), iris: cam3d.anchor("iris"), chip: cam3d.anchor("chip"), mid: cam3d.anchor("center", 1), mid0: cam3d.anchor("center", 0.25) };
  const W = { crew: [0.15, 0.28], iso: [0.3, 0.46], iris: [0.48, 0.63], wb: [0.65, 0.8], kill: [0.82, 1.2] };
  const order = ["crew", "iso", "iris", "wb", "kill"];
  const T = (key) => [[0, HERO_POSE[key]], [0.06, HERO_POSE[key]], [0.17, A.mid0[key]], [0.25, A.mid[key]], [0.3, A.sensor[key]], [0.45, A.sensor[key]], [0.5, A.iris[key]], [0.62, A.iris[key]], [0.67, A.chip[key]], [0.79, A.chip[key]], [0.86, A.mid[key]], [1, A.mid[key]]];
  ["x", "y", "z"].forEach((c) => { A.mid0["t" + c] = A.mid0[c]; });
  const tk = { tx: T("x").map(([p, v], i) => [p, i < 2 ? HERO_POSE.tx : v]), ty: T("y").map(([p, v], i) => [p, i < 2 ? HERO_POSE.ty : v]), tz: T("z").map(([p, v], i) => [p, i < 2 ? HERO_POSE.tz : v]) };
  const K = {
    yaw: [[0, Math.PI], [0.05, Math.PI], [0.17, 0.95], [0.25, 0.8], [0.3, 1.02], [0.45, 1.08], [0.5, 0.98], [0.62, 1.04], [0.67, 0.55], [0.79, 0.6], [0.87, 0.92], [1, 1.05]],
    pitch: [[0, 0.05], [0.17, 0.2], [0.3, 0.26], [0.45, 0.26], [0.5, 0.18], [0.62, 0.18], [0.67, 0.3], [0.79, 0.3], [0.87, 0.24], [1, 0.24]],
    dist: [[0, 3.4], [0.05, 3.6], [0.17, 7.2], [0.25, 10.8], [0.3, 2.7], [0.45, 2.55], [0.5, 2.7], [0.62, 2.55], [0.67, 3.1], [0.79, 3.1], [0.87, 11.2], [1, 11.4]],
    explode: [[0, 0], [0.13, 0], [0.25, 1], [1, 1]],
    agents: [[0, 0], [0.18, 0], [0.26, 1], [1, 1]],
  };
  const fx = mobile() ? [[0, 0], [1, 0]] : [[0, 0], [0.07, 0], [0.18, 0.2], [1, 0.2]];
  const fy = mobile() ? [[0, 0], [0.07, 0], [0.18, 0.2], [1, 0.2]] : [[0, 0], [1, 0]];
  let lastIso = -1, lastF = -1, lastBeat = "";
  const isoSeq = [6400, 5000, 4000, 3200, 2500, 2000];

  ScrollTrigger.create({ trigger: "#try", start: "top bottom", end: "top 30%", scrub: true, onUpdate: (s) => { prog.try = s.progress; vis3D(); } });
  ScrollTrigger.create({
    trigger: "#inside", start: "top top", end: "bottom bottom", scrub: true,
    onUpdate: (s) => { prog.inside = s.progress; apply(s.progress); vis3D(); },
    onLeaveBack: () => { prog.inside = 0; vis3D(); },
  });
  function apply(p) {
    for (const k in K) S[k] = kf(p, K[k]);
    for (const k in tk) S[k] = kf(p, tk[k]);
    S.frameX = kf(p, fx); S.frameY = kf(p, fy);
    const mob = mobile();
    let active = "";
    order.forEach((name, i) => {
      const [a, b] = W[name], el = beats[name];
      const al = clamp(Math.min((p - a) / 0.035, (b - p) / 0.035), 0, 1);
      if (al > 0.5) active = name;
      el.style.opacity = al; el.style.visibility = al > 0.001 ? "visible" : "hidden";
      const base = mob ? "" : "translateY(-50%) ";
      const out = 1 - al;
      el.style.transform = base + ({ crew: `translateY(${out * 50}px)`, iso: `translateX(${-out * 60}px)`, iris: `scale(${0.94 + 0.06 * al})`, wb: `translateY(${-out * 40}px)`, kill: `translateY(${out * 70}px) scale(${0.96 + 0.04 * al})` })[name];
      el.style.filter = name === "wb" && out > 0.01 ? `blur(${out * 10}px)` : "";
      dots[i]?.classList.toggle("on", al > 0.5);
    });
    S.mode = { iso: "iso", iris: "iris", wb: "wb" }[active] || "idle";
    S.focus = { iso: "sensor", iris: "iris", wb: "chip" }[active] || (p < 0.1 ? "lcd" : "body");
    if (active !== lastBeat) { if (active) sound.whoosh(); lastBeat = active; }
    // ISO: the real Oct 19 sequence
    const li = smooth(0.32, 0.43, p), k = Math.min(5, Math.floor(li * 5.999));
    if (k !== lastIso) { lastIso = k; setIso(isoSeq[k], p > W.iso[0] && p < W.iso[1]); }
    S.sensorGain = p < W.iso[0] - 0.05 ? 0 : 1 - (k / 5) * 0.75;
    // iris: f/2.8 to f/8 in thirds
    const lf = smooth(0.5, 0.6, p), fi = FNUMS.indexOf(2.8) + Math.round(lf * 9);
    if (fi !== lastF) { lastF = fi; setIris(FNUMS[fi], p > W.iris[0] && p < W.iris[1]); }
    S.fnum = FNUMS[fi];
    // white balance: 3200 K to 5600 K, the crew repaints the chip
    const lw = smooth(0.67, 0.77, p), K2 = Math.round((3200 + lw * 2400) / 100) * 100;
    $("#wb-val").textContent = K2 + "K"; $("#wb-marker").style.left = ((K2 - 2500) / 7500) * 100 + "%";
    S.chipGoal = lw;
    if (p < W.kill[0] - 0.02 && cam3d.frozen) release(true);
  }
}
function buildIsoGauge() {
  const g = $("#iso-ticks"); if (!g) return;
  let out = "";
  const list = ISOS.filter((v) => v >= 800 && v <= 12800);
  list.forEach((v) => {
    const f = Math.log2(v / 800) / 4, a = Math.PI * (1 - f);
    const major = [800, 1600, 3200, 6400, 12800].includes(v);
    const r1 = 128, r2 = major ? 140 : 135;
    out += `<line class="${major ? "major" : ""}" x1="${150 + Math.cos(a) * r1}" y1="${150 - Math.sin(a) * r1}" x2="${150 + Math.cos(a) * r2}" y2="${150 - Math.sin(a) * r2}"/>`;
    if (major) out += `<text x="${150 + Math.cos(a) * 154}" y="${150 - Math.sin(a) * 154 + 4}">${v}</text>`;
  });
  g.innerHTML = out;
  const arc = $("#iso-arc"), len = arc.getTotalLength(); arc.style.strokeDasharray = `${len} ${len}`; arc.dataset.len = len;
  setIso(6400, false);
}
function setIso(v, audible) {
  const f = Math.log2(v / 800) / 4;
  $("#iso-needle").style.transform = `rotate(${-90 + 180 * f}deg)`;
  const arc = $("#iso-arc"); arc.style.strokeDashoffset = arc.dataset.len * (1 - f);
  $("#iso-val").textContent = v;
  if (audible) sound.tick();
}
function setIris(f, audible) {
  const r = 74 * (2.8 / f), R = r / Math.cos(Math.PI / 9), rot = (f - 2.8) * 0.08;
  const pts = Array.from({ length: 9 }, (_, i) => { const a = rot + (i / 9) * Math.PI * 2; return `${100 + Math.cos(a) * R},${100 + Math.sin(a) * R}`; }).join(" ");
  $("#iris-poly").setAttribute("points", pts);
  const bl = $("#iris-blades");
  if (bl) bl.innerHTML = Array.from({ length: 9 }, (_, i) => { const a = rot + (i / 9) * Math.PI * 2, b = a + 1.25; return `<line x1="${100 + Math.cos(a) * R}" y1="${100 + Math.sin(a) * R}" x2="${100 + Math.cos(b) * 88}" y2="${100 + Math.sin(b) * 88}"/>`; }).join("");
  $("#iris-val").textContent = "F" + f;
  if (audible) sound.tick();
}
function buildStopwatch() {
  const g = $("#sw-ticks"); if (!g) return;
  let out = "";
  for (let i = 0; i < 20; i++) { const a = (i / 20) * Math.PI * 2; out += `<line x1="${80 + Math.cos(a) * 72}" y1="${80 + Math.sin(a) * 72}" x2="${80 + Math.cos(a) * (i % 5 ? 75 : 78)}" y2="${80 + Math.sin(a) * (i % 5 ? 75 : 78)}"/>`; }
  g.innerHTML = out;
}
let release = () => {};
function killSwitch() {
  const b = $("#estop"), arc = $("#sw-arc"), val = $("#sw-val");
  const ms = data?.tests?.test1?.kill?.ms_to_stop ?? 33;
  const press = () => {
    if (cam3d?.frozen) return release();
    cam3d?.freeze(true);
    html.classList.add("killed"); b.setAttribute("aria-pressed", "true");
    sound.clunk();
    const o = { v: 0 };
    gsap.to(o, { v: ms, duration: 0.7, ease: "power3.out", onUpdate: () => { val.textContent = Math.round(o.v); arc.style.strokeDashoffset = 402 * (1 - o.v / 100); } });
    toast("Stopped · " + ms + " ms", "bad");
  };
  release = (quiet) => {
    cam3d?.freeze(false);
    html.classList.remove("killed"); b.setAttribute("aria-pressed", "false");
    val.textContent = "0"; arc.style.strokeDashoffset = 402;
    if (!quiet) { toast("Back to work"); sound.pop(); }
  };
  b.addEventListener("click", press);
}

// ============ 3 · try it ============
function tryIt() {
  const v = (views.sim = sim.view($("#sim-canvas"), { scene: 0, maxW: 1440 }));
  sim.observe(v);
  let sceneIdx = 1, busy = false;
  v.setScene(1);
  Object.assign(v.a, solve(sim, 1, { iso: 3200, shutter: 1 / 48, fnum: 2.8, wb: 3200 }).target);
  const feed = Feed($("#sim-feed"), { max: 7 });
  const tally = $("#sim-tally"), needle = $("#sim-needle"), af = $("#sim-af");
  const dials = makeDials($("#sim-dials"), v, () => { af.classList.remove("lock"); }, mobile() ? 64 : 92);
  af.classList.add("lock");
  const ro = $("#ro-subj"), hx = $("#sim-histo").getContext("2d");
  let lastH = 0;
  v.onFrame = (view) => {
    placeAF(af, view);
    const m = sim.meter(sceneIdx, view.a, view.scene);
    needle.style.left = clamp((m.subject + 3) / 6, 0, 1) * 100 + "%";
    const off = m.subject > -0.05 || m.subject < -0.85;
    needle.className = "ev-needle" + (off ? " over" : "");
    ro.textContent = (m.subject >= 0 ? "+" : "−") + Math.abs(m.subject).toFixed(1); ro.classList.toggle("off", off);
    const now = performance.now();
    if (now - lastH > 300) { lastH = now; histogram(view.canvas, hx, 240, 56); }
  };
  let greeted = false;
  ScrollTrigger.create({ trigger: "#sim", start: "top 75%", once: true, onEnter: async () => { if (greeted) return; greeted = true; await feed.say("Exposure's good. Your turn: break it.", "done", 500); await feed.say("Turn any dial. Then let me fix it.", "", 400); } });
  const go = async () => {
    if (busy) return; busy = true; $("#sim-ai").disabled = true;
    await runAI(v, sceneIdx, { feed, dials, tally });
    af.classList.add("lock");
    busy = false; $("#sim-ai").disabled = false;
  };
  $("#sim-ai").addEventListener("click", go);
  $$("#sim .scenes button").forEach((b) => b.addEventListener("click", async () => {
    if (busy) return;
    $$("#sim .scenes button").forEach((x) => x.setAttribute("aria-checked", x === b));
    sceneIdx = +b.dataset.scene; v.setScene(sceneIdx, 1.6); af.classList.remove("lock");
    sound.whoosh();
    await feed.say(`${SCENES[sceneIdx].name}. The light changed.`, "warn", 300);
    await wait(1300);
    go();
  }));
  $("#sim-fc").addEventListener("click", (e) => {
    v.a.falseColor = !v.a.falseColor; e.currentTarget.setAttribute("aria-pressed", v.a.falseColor); sound.tick();
  });
}

// ============ 4 · beat the AI ============
function game() {
  const card = $("#game-card");
  const gv = sim.view($("#g-canvas"), { scene: 0 }), yv = sim.view($("#g-you"), {}), av = sim.view($("#g-ai"), {});
  [gv, yv, av].forEach((v) => sim.observe(v));
  let dials = null, sceneIdx = 0, start = null, timer = null, best = 0;
  try { best = +localStorage.getItem("best") || 0; } catch {}
  const showBest = () => { const el = $("#g-best"); if (best) { el.hidden = false; el.textContent = "Best · " + best; } };
  showBest();
  // one height for every stage, so nothing below the game moves (and no re-measuring mid-play)
  makeDials($("#g-dials"), { a: { iso: 800, shutter: 1 / 48, fnum: 2.8, wb: 5600 } }, null, mobile() ? 62 : 84);
  const lockH = () => { card.style.minHeight = ""; card.style.minHeight = card.offsetHeight + "px"; };
  document.fonts.ready.then(lockH); addEventListener("resize", () => { if (card.dataset.stage !== "result") lockH(); });
  const ring = $("#g-timer");
  gv.setScene(1); Object.assign(gv.a, { iso: 6400, shutter: 1 / 48, fnum: 2.8, wb: 9000 });
  function round() {
    sceneIdx = Math.floor(Math.random() * 4);
    let s, tries = 0;
    do {
      s = { iso: ISOS[3 + Math.floor(Math.random() * 22)], shutter: SHUTTERS[2 + Math.floor(Math.random() * 18)], fnum: FNUMS[Math.floor(Math.random() * 22)], wb: KELVINS[Math.floor(Math.random() * KELVINS.length)] };
    } while (score(sim, sceneIdx, s).score > 45 && tries++ < 40);
    start = s;
    gv.setScene(sceneIdx); Object.assign(gv.a, start, { falseColor: false });
    card.dataset.stage = "play";
    dials = makeDials($("#g-dials"), gv, null, mobile() ? 62 : 84);
    const T = 15;
    gsap.killTweensOf(ring);
    gsap.fromTo(ring, { strokeDashoffset: 0 }, { strokeDashoffset: 107, duration: T, ease: "none" });
    clearTimeout(timer); timer = setTimeout(lockIn, T * 1000);
    sound.beep();
  }
  async function lockIn() {
    clearTimeout(timer); gsap.killTweensOf(ring);
    const you = { ...gv.a };
    const ys = score(sim, sceneIdx, you), plan = solve(sim, sceneIdx, start), as = score(sim, sceneIdx, plan.target);
    yv.setScene(sceneIdx); av.setScene(sceneIdx);
    Object.assign(yv.a, you); Object.assign(av.a, start);
    card.dataset.stage = "result";
    sound.click();
    ["#g-you-score", "#g-ai-score"].forEach((s) => ($(s).textContent = "0"));
    ["#g-you-ring", "#g-ai-ring"].forEach((s) => ($(s).style.strokeDashoffset = 119.4));
    $("#g-you-why").innerHTML = ""; $("#g-ai-why").innerHTML = ""; $("#g-verdict").textContent = "";
    const showScore = (who, sc) => {
      $(`#g-${who}-ring`).style.strokeDashoffset = 119.4 * (1 - sc.score / 100);
      countUp($(`#g-${who}-score`), sc.score, { dur: 1.1 });
      $(`#g-${who}-why`).innerHTML = sc.why.map((w) => `<span class="${w === "Nailed it" ? "good" : ""}">${w}</span>`).join("");
    };
    await wait(250); showScore("you", ys);
    for (const st of plan.steps) await turn(st.key, st.from, st.to, (val) => { av.a[st.key] = val; sound.tick(); }, { speed: 2.4 });
    showScore("ai", as);
    await wait(900);
    const d = ys.score - as.score;
    $("#g-verdict").textContent = d > 0 ? `You win by ${d}.` : d === 0 ? "A tie. Respect." : d > -8 ? `So close. The AI by ${-d}.` : `The AI wins by ${-d}.`;
    if (ys.score > best) { best = ys.score; try { localStorage.setItem("best", best); } catch {} showBest(); }
  }
  $("#g-start").addEventListener("click", round);
  $("#g-lock").addEventListener("click", lockIn);
  $("#g-again").addEventListener("click", round);
}

// ============ 5 · before / after ============
function compare() {
  const v = sim.view($("#ba-canvas"), { scene: 3 });
  sim.observe(v);
  const bad = { iso: 2500, shutter: 1 / 48, fnum: 2.8, wb: 7200, mode: "normal" };
  const good = { ...solve(sim, 3, bad).target, mode: "normal" };
  const modes = {
    fix: [bad, good, "Before", "AI fixed"],
    log: [{ ...good, mode: "log" }, good, "S-Log3", "Graded"],
    false: [good, { ...good, falseColor: true }, "Picture", "False color"],
    zebra: [bad, { ...bad, zebra: true }, "Picture", "Zebras"],
  };
  const setMode = (m) => {
    const [a, b, l, r] = modes[m];
    v.a = { ...a }; v.b = { ...b };
    $("#ba-l").textContent = l; $("#ba-r").textContent = r;
  };
  setMode("fix");
  const handle = $("#ba-handle"), box = $("#ba");
  const setSplit = (x) => { v.split = clamp(x, 0.02, 0.98); handle.style.left = v.split * 100 + "%"; handle.setAttribute("aria-valuenow", Math.round(v.split * 100)); };
  setSplit(0.5);
  let drag = false;
  box.addEventListener("pointerdown", (e) => { drag = true; try { box.setPointerCapture(e.pointerId); } catch {} const r = box.getBoundingClientRect(); setSplit((e.clientX - r.left) / r.width); });
  box.addEventListener("pointermove", (e) => { if (!drag) return; const r = box.getBoundingClientRect(); setSplit((e.clientX - r.left) / r.width); });
  box.addEventListener("pointerup", () => (drag = false)); box.addEventListener("pointercancel", () => (drag = false));
  handle.addEventListener("keydown", (e) => { const d = { ArrowLeft: -0.04, ArrowRight: 0.04 }[e.key]; if (d) { setSplit(v.split + d); e.preventDefault(); } });
  $$("#compare .modes button").forEach((b) => b.addEventListener("click", () => {
    $$("#compare .modes button").forEach((x) => x.setAttribute("aria-checked", x === b));
    setMode(b.dataset.mode); sound.tick();
  }));
  if (motion) ScrollTrigger.create({ trigger: box, start: "top 70%", once: true, onEnter: () => {
    const o = { x: 0.5 };
    gsap.timeline().to(o, { x: 0.16, duration: 0.9, ease: "power2.inOut", onUpdate: () => setSplit(o.x) })
      .to(o, { x: 0.84, duration: 1.3, ease: "power2.inOut", onUpdate: () => setSplit(o.x) })
      .to(o, { x: 0.5, duration: 0.9, ease: "power3.out", onUpdate: () => setSplit(o.x) });
  } });
}

// section headlines rise out of their lines as they arrive
function heads() {
  if (!motion) return;
  $$(".sec-head .big").forEach((h) => {
    const ins = $$(".in", h);
    gsap.set(ins, { yPercent: 105 });
    ScrollTrigger.create({ trigger: h, start: "top 82%", once: true, onEnter: () => gsap.to(ins, { yPercent: 0, duration: 1.1, ease: "expo.out", stagger: 0.09 }) });
  });
}

// ============ 6 · the real test: the agent's own log ============
function real() {
  const t = data?.tests?.test1;
  if (!t) return;
  buildChart($("#real-chart"), t);
  const conf = { kill: [t.kill.ms_to_stop, t.kill.ms_to_stop / 100, 0, ""], confirm: [data.safety.confirmed, data.safety.confirmed / data.safety.changes, 0, "/" + data.safety.changes],
    settle: [t.settle_s, t.settle_s / 20, 1, ""], hold: [t.changes_during_hold, 1, 0, ""] };
  $$(".g4").forEach((g) => {
    const [v, frac, dec, suf] = conf[g.dataset.k];
    const b = g.querySelector("[data-v]"); b.textContent = (0).toFixed(dec) + suf;
    ScrollTrigger.create({ trigger: g, start: "top 85%", once: true, onEnter: () => {
      g.querySelector(".fill").style.strokeDashoffset = 314.2 * (1 - frac);
      countUp(b, v, { dec, suffix: suf });
    } });
  });
}
function buildChart(fig, t) {
  const rows = t.trace.filter((r) => r[1] != null && r[0] >= -2 && r[0] <= t.settle_s + 6);
  const W = 800, H = 340, L = 46, R = 16, T = 18, B = 36;
  const t0 = rows[0][0], t1 = rows[rows.length - 1][0];
  const ks = rows.map((r) => r[1]), ymin = Math.min(-1.5, ...ks) - 0.2, ymax = Math.max(3.2, ...ks) + 0.2;
  const X = (x) => L + ((x - t0) / (t1 - t0)) * (W - L - R), Y = (y) => T + ((ymax - y) / (ymax - ymin)) * (H - T - B);
  const [w0, w1] = t.window;
  let g = "";
  for (let y = Math.ceil(ymin); y <= Math.floor(ymax); y++) g += `<line x1="${L}" x2="${W - R}" y1="${Y(y)}" y2="${Y(y)}"/><text x="${L - 10}" y="${Y(y) + 4}" text-anchor="end">${y > 0 ? "+" : ""}${y}</text>`;
  let xt = "";
  for (let x = Math.ceil(t0 / 5) * 5; x <= t1; x += 5) xt += `<text x="${X(x)}" y="${H - 10}" text-anchor="middle">${x} S</text>`;
  const d = rows.map((r, i) => `${i ? "L" : "M"}${X(r[0]).toFixed(1)},${Y(r[1]).toFixed(1)}`).join("");
  const keyAt = (x) => { let best = rows[0]; rows.forEach((r) => { if (Math.abs(r[0] - x) < Math.abs(best[0] - x)) best = r; }); return best[1]; };
  const ch = t.changes;
  const marks = ch.map((c, i) => {
    const x = X(c.t), y = Y(keyAt(c.t)), lab = i === 0 ? `ISO ${c.from.replace("ISO ", "")} → ${c.to.replace("ISO ", "")}` : i === ch.length - 1 ? `→ ${c.to.replace("ISO ", "")}` : "";
    return `<line class="tick-line" x1="${x}" x2="${x}" y1="${T}" y2="${H - B}"/><circle class="tick-dot" cx="${x}" cy="${y}" r="5"/>${lab ? `<text class="tick-lab" x="${x + 9}" y="${y - 10}">${lab}</text>` : ""}`;
  }).join("");
  fig.innerHTML = `<div class="chart-head nerd"><span class="label">Scene exposure in stops · seconds after auto turned on</span></div>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Real test on Oct 19: the scene started ${ks[0] > 0 ? "+" : ""}${ks[0].toFixed(1)} stops over; five ISO changes brought it to ${ks[ks.length - 1].toFixed(1)} stops, inside the −1 to +1 window, in ${t.settle_s} seconds.">
      <rect class="band" x="${L}" y="${Y(w1)}" width="${W - L - R}" height="${Y(w0) - Y(w1)}"/>
      <line class="band-edge" x1="${L}" x2="${W - R}" y1="${Y(w1)}" y2="${Y(w1)}"/><line class="band-edge" x1="${L}" x2="${W - R}" y1="${Y(w0)}" y2="${Y(w0)}"/>
      <text class="band-lab" x="${W - R - 8}" y="${Y(w0) - 10}" text-anchor="end">INSIDE THE WINDOW</text>
      <g class="grid axis">${g}</g><g class="axis">${xt}</g>
      ${marks}
      <path class="line" id="real-line" d="${d}"/>
      <line class="cross" id="real-cross" x1="0" x2="0" y1="${T}" y2="${H - B}" style="opacity:0"/>
      <rect id="real-hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>
    </svg><div class="tip" id="real-tip"></div>`;
  const path = $("#real-line", fig), len = path.getTotalLength();
  path.style.strokeDasharray = len; path.style.strokeDashoffset = motion ? len : 0;
  if (motion) ScrollTrigger.create({ trigger: fig, start: "top 75%", once: true, onEnter: () => gsap.to(path, { strokeDashoffset: 0, duration: 2.4, ease: "power2.inOut" }) });
  const svg = $("svg", fig), tip = $("#real-tip", fig), cross = $("#real-cross", fig);
  const isoAt = (x) => { let iso = t.changes[0].from; t.changes.forEach((c) => { if (c.t <= x) iso = c.to; }); return x < 0 ? t.setup?.[0]?.to ?? iso : iso; };
  svg.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect(), sx = ((e.clientX - r.left) / r.width) * W;
    const x = t0 + ((sx - L) / (W - L - R)) * (t1 - t0);
    if (x < t0 || x > t1) return;
    const k = keyAt(x);
    cross.setAttribute("x1", sx); cross.setAttribute("x2", sx); cross.style.opacity = 1;
    tip.style.left = (sx / W) * 100 + "%"; tip.style.top = (Y(k) / H) * r.height + 40 + "px";
    tip.innerHTML = `<b>${x.toFixed(1)} s</b> · scene ${k > 0 ? "+" : ""}${k.toFixed(1)} st · ${isoAt(x)}`;
  });
  svg.addEventListener("pointerleave", () => (cross.style.opacity = 0));
}

// ============ 7 · safety ============
function safety() {
  $$("#locks .key").forEach((k) => k.addEventListener("click", () => {
    k.classList.remove("denied"); void k.offsetWidth; k.classList.add("denied");
    sound.deny(); toast(`${k.dataset.k}: locked. Never touched.`, "bad");
  }));
  const R = [
    ["ISO", 100, 51200, 800, 12800, "log", (v) => v],
    ["Iris", 1.4, 22, 2.8, 11, "log", (v) => "f/" + v],
    ["Shutter", 8, 2000, 48, 100, "log", (v) => "1/" + v],
    ["WB", 2500, 10000, 2800, 7500, "lin", (v) => v + "K"],
  ];
  const box = $("#ranges");
  box.innerHTML = R.map(([n, a, b, lo, hi, sc, f]) => {
    const fr = (v) => sc === "log" ? Math.log(v / a) / Math.log(b / a) : (v - a) / (b - a);
    const pt = (u) => { const ang = Math.PI * (1 - u); return [100 + Math.cos(ang) * 86, 92 - Math.sin(ang) * 86]; };
    const [x0, y0] = pt(fr(lo)), [x1, y1] = pt(fr(hi));
    return `<div class="range"><svg viewBox="0 0 200 100"><path class="arc-all" d="M14 92 A86 86 0 0 1 186 92"/><path class="arc-ok" d="M${x0} ${y0} A86 86 0 0 1 ${x1} ${y1}"/></svg>
      <div class="ends"><span><small>${n}</small>${f(lo)}</span><span style="text-align:right"><small>&nbsp;</small>${f(hi)}</span></div></div>`;
  }).join("");
  $$(".range", box).forEach((r) => {
    const p = $(".arc-ok", r), len = p.getTotalLength(); r.style.setProperty("--len", len);
    if (motion) ScrollTrigger.create({ trigger: r, start: "top 88%", once: true, onEnter: () => r.classList.add("in") }); else r.classList.add("in");
  });
}

// ============ 8 · dashboard ============
function dash() {
  const img = $("#dash-img"), dev = $("#device");
  $$("#dash-modes button").forEach((b) => b.addEventListener("click", () => {
    $$("#dash-modes button").forEach((x) => x.setAttribute("aria-checked", x === b));
    img.style.opacity = 0; sound.tick();
    setTimeout(() => { img.src = `media/screens/${b.dataset.shot}.png`; img.onload = () => (img.style.opacity = 1); }, 180);
  }));
  if (html.classList.contains("fine") && motion) {
    dev.addEventListener("pointermove", (e) => {
      const r = dev.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      dev.style.transform = `perspective(1600px) rotateY(${x * 5}deg) rotateX(${-y * 4}deg)`;
    });
    dev.addEventListener("pointerleave", () => (dev.style.transform = ""));
  }
}

// ============ 9 · finale: the camera snaps back together ============
function finale() {
  const lines = $$("#finale-title .in"), cta = $(".cta-row");
  if (!motion || !cam3d) return;
  gsap.set(lines, { yPercent: 110 }); gsap.set(cta, { opacity: 0, y: 20 });
  const S = cam3d.state;
  let snapped = false;
  const mid = cam3d.anchor("center", 1);
  ScrollTrigger.create({
    trigger: "#finale", start: "top bottom", end: "bottom bottom", scrub: true,
    onUpdate: (s) => {
      const p = s.progress; prog.finale = p; vis3D();
      if (cam3d.frozen) release(true);
      if (!snapped) {
        Object.assign(S, { explode: 1, agents: 1, mode: p > 0.42 ? "home" : "idle", yaw: 0.85 + p * 0.5, pitch: 0.24, dist: 11, tx: mid.x, ty: mid.y, tz: mid.z, frameX: 0, frameY: mobile() ? -0.08 : -0.06, focus: "body", turntable: 0, snap: 0 });
      }
      if (p > 0.66 && !snapped) doSnap();
      else if (p < 0.55 && snapped) unSnap();
    },
    onLeaveBack: () => { prog.finale = 0; vis3D(); },
  });
  function doSnap() {
    snapped = true;
    S.agents = 0; S.snap = 1;
    gsap.to(S, { explode: 0, duration: 0.5, ease: "power4.in", onComplete: () => {
      cam3d.flashSweep(); sound.snap();
      gsap.fromTo("#cam3d", { x: -8 }, { x: 0, duration: 0.5, ease: "elastic.out(1.2, 0.3)" });
      Object.assign(S, { dist: mobile() ? 8.2 : 5.2, pitch: 0.16, tx: 0, ty: 0.06, tz: 0.25, turntable: 1, frameY: mobile() ? -0.16 : -0.1 });
      gsap.to(lines, { yPercent: 0, duration: 1.2, ease: "expo.out", stagger: 0.1 });
      gsap.to(cta, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out", delay: 0.35 });
    } });
  }
  function unSnap() {
    snapped = false; gsap.killTweensOf(S); S.snap = 0; S.turntable = 0;
    gsap.to(lines, { yPercent: 110, duration: 0.4, ease: "power2.in" }); gsap.to(cta, { opacity: 0, y: 20, duration: 0.3 });
  }
}

main();
