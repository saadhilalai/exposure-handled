// Small UI kit for the site: camera dials, the AI's chat feed, sound (off until you turn it on),
// magnetic buttons, the focus brackets and toasts.

const html = document.documentElement;
export const motion = html.classList.contains("motion");
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const wait = (ms) => new Promise((r) => setTimeout(r, ms));
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

// ---------- sound: synthesized, nothing to download ----------
export const sound = (() => {
  let ctx = null, master = null, on = false, lastTick = 0;
  function ensure() {
    if (ctx) return;
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 0.55; master.connect(ctx.destination);
  }
  function noise(dur) {
    const b = ctx.createBuffer(1, Math.max(1, Math.floor(ctx.sampleRate * dur)), ctx.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    const s = ctx.createBufferSource(); s.buffer = b; return s;
  }
  function env(node, t, a, peak, dec) {
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + dec);
    node.connect(g); g.connect(master); return g;
  }
  function burst(t, f, q, peak, dec, type = "bandpass") {
    const n = noise(dec + 0.02), fl = ctx.createBiquadFilter(); fl.type = type; fl.frequency.value = f; fl.Q.value = q;
    n.connect(fl); env(fl, t, 0.001, peak, dec); n.start(t); n.stop(t + dec + 0.03);
  }
  function tone(t, f, peak, dec, type = "sine", f2) {
    const o = ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t); if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dec);
    env(o, t, 0.004, peak, dec); o.start(t); o.stop(t + dec + 0.05);
  }
  const api = {
    get on() { return on; },
    enable() { ensure(); ctx.resume(); on = true; },
    disable() { on = false; },
    tick() { if (!on) return; const now = performance.now(); if (now - lastTick < 28) return; lastTick = now; const t = ctx.currentTime; burst(t, 4200, 3, 0.35, 0.018); tone(t, 2600, 0.05, 0.012, "triangle"); },
    click() { if (!on) return; const t = ctx.currentTime; burst(t, 2400, 1.2, 0.6, 0.03); burst(t + 0.055, 1800, 1.4, 0.45, 0.04); tone(t, 140, 0.25, 0.06); },
    beep() { if (!on) return; const t = ctx.currentTime; tone(t, 1040, 0.12, 0.12); tone(t + 0.16, 1040, 0.12, 0.12); },
    clunk() { if (!on) return; const t = ctx.currentTime; tone(t, 110, 0.9, 0.28, "sine", 48); burst(t, 600, 0.8, 0.7, 0.06, "lowpass"); tone(t + 0.01, 1800, 0.08, 0.04, "square"); },
    snap() { if (!on) return; const t = ctx.currentTime; burst(t, 3000, 0.9, 0.8, 0.05); tone(t, 90, 1, 0.35, "sine", 40); burst(t + 0.07, 5200, 2, 0.4, 0.03); },
    deny() { if (!on) return; const t = ctx.currentTime; tone(t, 220, 0.18, 0.09, "square", 160); tone(t + 0.11, 165, 0.18, 0.12, "square", 120); },
    pop() { if (!on) return; const t = ctx.currentTime; tone(t, 880, 0.06, 0.07, "sine", 1320); },
    whoosh() { if (!on) return; const t = ctx.currentTime; const n = noise(0.5), f = ctx.createBiquadFilter(); f.type = "bandpass"; f.Q.value = 0.7; f.frequency.setValueAtTime(400, t); f.frequency.exponentialRampToValueAtTime(3200, t + 0.35); n.connect(f); env(f, t, 0.12, 0.25, 0.35); n.start(t); n.stop(t + 0.55); },
  };
  return api;
})();

// ---------- toast ----------
let toastT = 0;
export function toast(text, cls = "") {
  const t = $("#toast");
  t.textContent = text; t.className = "toast on " + cls;
  clearTimeout(toastT); toastT = setTimeout(() => (t.className = "toast " + cls), 2200);
}

// ---------- camera dial ----------
// values: the detents; format(v) → text; ok: [lo, hi] of the approved range (values), shown in orange on the scale.
export function Dial(parent, { key, label, values, format, index = 0, ok, onChange, size }) {
  const el = document.createElement("div");
  el.className = "dial"; el.dataset.key = key;
  if (size) el.style.setProperty("--size", size + "px");
  const n = values.length, A0 = -135, SPAN = 270;
  const ticks = values.map((v, i) => {
    const a = ((A0 + (SPAN * i) / (n - 1)) * Math.PI) / 180;
    const r1 = 50, r2 = i % 3 === 0 ? 44 : 46.5;
    const okc = ok && v >= Math.min(...ok) && v <= Math.max(...ok) ? "ok" : "";
    return `<line class="${okc}" x1="${50 + Math.sin(a) * r1}" y1="${50 - Math.cos(a) * r1}" x2="${50 + Math.sin(a) * r2}" y2="${50 - Math.cos(a) * r2}"/>`;
  }).join("");
  el.innerHTML = `<div class="dial-face"><svg class="dial-scale" viewBox="0 0 100 100" aria-hidden="true">${ticks}</svg>
    <div class="dial-knob" role="slider" tabindex="0" aria-label="${label}" aria-valuemin="0" aria-valuemax="${n - 1}"></div></div>
    <div class="dial-read"><small>${label}</small><b></b></div>`;
  parent.appendChild(el);
  const knob = el.querySelector(".dial-knob"), read = el.querySelector("b"), lines = [...el.querySelectorAll("line")];
  let i = index, locked = false;
  function paint() {
    knob.style.transform = `rotate(${A0 + (SPAN * i) / (n - 1)}deg)`;
    read.textContent = format(values[i]);
    knob.setAttribute("aria-valuenow", i); knob.setAttribute("aria-valuetext", `${label} ${format(values[i])}`);
    lines.forEach((l, k) => l.classList.toggle("on", k === i));
  }
  function set(k, { silent = false, source = "user" } = {}) {
    k = clamp(Math.round(k), 0, n - 1);
    if (k === i) return;
    i = k; paint();
    if (!silent) sound.tick();
    onChange?.(values[i], i, source);
  }
  paint();
  // drag: up or right turns it up; one detent every 9 px (13 px with a finger)
  let start = null;
  knob.addEventListener("pointerdown", (e) => {
    if (locked) return;
    try { knob.setPointerCapture(e.pointerId); } catch {}           // keeps the drag even when the finger leaves the knob
    start = { x: e.clientX, y: e.clientY, i, px: e.pointerType === "touch" ? 13 : 9 }; el.classList.add("grab"); e.preventDefault();
  });
  knob.addEventListener("pointermove", (e) => {
    if (!start) return;
    const d = (e.clientX - start.x - (e.clientY - start.y)) / start.px;   // a finger gets bigger steps than a mouse
    set(start.i + d);
  });
  const end = () => { start = null; el.classList.remove("grab"); };
  knob.addEventListener("pointerup", end); knob.addEventListener("pointercancel", end);
  let wheelAcc = 0;
  knob.addEventListener("wheel", (e) => {
    if (locked) return;
    e.preventDefault(); wheelAcc += e.deltaY;
    if (Math.abs(wheelAcc) > 30) { set(i + (wheelAcc < 0 ? 1 : -1)); wheelAcc = 0; }
  }, { passive: false });
  knob.addEventListener("keydown", (e) => {
    if (locked) return;
    const k = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1, PageUp: 3, PageDown: -3 }[e.key];
    if (k) { set(i + k); e.preventDefault(); }
    if (e.key === "Home") { set(0); e.preventDefault(); }
    if (e.key === "End") { set(n - 1); e.preventDefault(); }
  });
  return {
    el, key,
    get index() { return i; },
    get value() { return values[i]; },
    set, setValue(v, opts) { set(nearest(values, v), opts); },
    ai(on) { el.classList.toggle("ai", on); },
    lock(on) { locked = on; },
  };
}
export function nearest(list, v) {
  let best = 0, bd = Infinity;
  list.forEach((x, k) => { const d = Math.abs(Math.log(x) - Math.log(v)); if (d < bd) { bd = d; best = k; } });
  return best;
}

// ---------- the AI's chat feed ----------
export function Feed(ol, { max = 5 } = {}) {
  function push(htmlText, cls = "") {
    const li = document.createElement("li");
    li.className = "msg " + cls; li.innerHTML = `<span>${htmlText}</span>`;
    ol.appendChild(li);
    while (ol.children.length > max) ol.firstElementChild.remove();
    if (motion && window.gsap) gsap.fromTo(li, { opacity: 0, y: 14, scale: 0.92 }, { opacity: 1, y: 0, scale: 1, duration: 0.55, ease: "back.out(1.7)" });
    sound.pop();
    return li;
  }
  function typing() {
    const li = document.createElement("li");
    li.className = "msg typing"; li.innerHTML = "<span><i></i><i></i><i></i></span>";
    ol.appendChild(li);
    while (ol.children.length > max + 1) ol.firstElementChild.remove();
    return () => li.remove();
  }
  async function say(htmlText, cls = "", think = 260) {
    if (motion && think) { const stop = typing(); await wait(think); stop(); }
    return push(htmlText, cls);
  }
  return { push, say, typing, clear: () => (ol.innerHTML = "") };
}

// ---------- magnetic buttons ----------
export function magnetic() {
  if (!html.classList.contains("fine") || !motion) return;
  $$(".magnetic").forEach((b) => {
    b.addEventListener("pointermove", (e) => {
      const r = b.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
      b.style.transform = `translate(${dx * 0.22}px, ${dy * 0.3}px)`;
    });
    b.addEventListener("pointerleave", () => { b.style.transform = ""; });
  });
}

// ---------- focus brackets: over anything you can use, orange brackets snap around it, like an AF lock ----------
// They follow the element (read once a frame while it's locked), never the mouse, so they can't lag behind it.
export function lockFrame() {
  if (!html.classList.contains("fine")) return;
  const SEL = "a, button, [role=slider], .key", OUT = 7, PRESS = 3.5, GONE = 12, ARM = 8;
  const f = document.createElement("div");
  f.className = "lockframe"; f.setAttribute("aria-hidden", "true");
  f.innerHTML = "<i></i><i></i><i></i><i></i>";
  document.body.append(f);
  const c = [...f.children], dpr = window.devicePixelRatio || 1, px = (v) => Math.round(v * dpr) / dpr;
  let target = null, pressed = false, last = null, s = { x: 0, y: 0, w: 0, h: 0, o: GONE, a: 0 };
  let from = s, t0 = 0, dur = 1, raf = 0, mx = -1, my = -1, scrollT = 0;
  const box = (t) => {
    const r = t.getBoundingClientRect();
    return r.width && r.height && r.width < 420 && r.height < 300 ? r : null;
  };
  const goal = () => {
    const r = target && target.isConnected && box(target);
    if (target && !r) { release(); return goal(); }
    if (r) last = { x: r.left, y: r.top, w: r.width, h: r.height };
    return { ...(last || s), o: target ? (pressed ? PRESS : OUT) : GONE, a: target ? 1 : 0 };
  };
  const animate = (ms) => { from = { ...s }; t0 = performance.now(); dur = motion ? ms : 0; if (!raf) raf = requestAnimationFrame(draw); };
  function draw(now) {
    const g = goal(), k = dur ? Math.min(1, (now - t0) / dur) : 1, e = 1 - (1 - k) ** 4;
    for (const key in s) s[key] = from[key] + (g[key] - from[key]) * e;
    const { x, y, w, h, o } = s, r = x + w + o - ARM, b = y + h + o - ARM;
    [[x - o, y - o], [r, y - o], [x - o, b], [r, b]].forEach(([u, v], i) => (c[i].style.transform = `translate(${px(u)}px, ${px(v)}px)`));
    f.style.opacity = s.a.toFixed(3);
    raf = target || k < 1 ? requestAnimationFrame(draw) : 0;
  }
  function lock(t) {
    if (t === target) return;
    if (!t || !box(t)) return release();
    const moving = target && s.a > 0.5;           // already locked on a neighbour: jump across
    target = t; pressed = false;
    if (!moving) { const r = box(t); s = { x: r.left, y: r.top, w: r.width, h: r.height, o: 13, a: 0 }; }
    animate(moving ? 120 : 110);
  }
  function release() {
    if (!target) return;
    target = null; pressed = false; animate(120);
  }
  addEventListener("pointerover", (e) => { mx = e.clientX; my = e.clientY; lock(e.target.closest?.(SEL)); }, { passive: true });
  addEventListener("pointermove", (e) => { mx = e.clientX; my = e.clientY; }, { passive: true });
  html.addEventListener("pointerleave", release);
  addEventListener("blur", release);
  addEventListener("pointerdown", () => { if (target) { pressed = true; animate(60); } }, { passive: true });
  addEventListener("pointerup", () => { if (pressed) { pressed = false; animate(140); } }, { passive: true });
  // while the page scrolls the brackets step aside, and lock again on whatever is under the pointer once it stops
  addEventListener("scroll", () => {
    if (target) { target = null; animate(70); }
    clearTimeout(scrollT);
    scrollT = setTimeout(() => { const t = mx >= 0 && document.elementFromPoint(mx, my); t && lock(t.closest(SEL)); }, 140);
  }, { passive: true });
}

// ---------- film grain: a small noise tile drawn once ----------
export function grain() {
  const c = document.createElement("canvas");
  c.width = c.height = 180;
  const x = c.getContext("2d"), img = x.createImageData(180, 180);
  for (let i = 0; i < img.data.length; i += 4) { const v = Math.random() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
  x.putImageData(img, 0, 0);
  $(".grain").style.backgroundImage = `url(${c.toDataURL()})`;
}

// count a number up when it appears
export function countUp(el, to, { dur = 1.4, dec = 0, suffix = "" } = {}) {
  if (!motion) { el.textContent = to.toFixed(dec) + suffix; return; }
  const o = { v: 0 };
  gsap.to(o, { v: to, duration: dur, ease: "power3.out", onUpdate: () => (el.textContent = o.v.toFixed(dec) + suffix) });
}
