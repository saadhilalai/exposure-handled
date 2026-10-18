/* Camera Agent dashboard: polls the runner (/api/state, 4x a second), pulls live-view frames
   one at a time (/api/frame.jpg), and sends the operator's controls. All text from the
   agent goes in with textContent, never as HTML. */
"use strict";

const $ = (id) => document.getElementById(id);
const VIEW_FPS = 12;                  // live-view refresh in the browser (the agent itself runs at 24)
const WINDOW_S = 60;                  // chart time window
const KIND = {
  change: "Changed", would_change: "Would change", advice: "Advice", kill: "Kill switch", pause: "Auto",
  lock: "Lock", look: "Look", face: "Face", mark: "Mark", start: "Start", end: "End", refused: "Refused", error: "Error", restore: "Restore",
};
const ICONS = {
  AUTO: '<svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="11" cy="11" r="4.5" fill="currentColor"/></svg>',
  SUGGESTING: '<svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M11 2a9 9 0 0 1 0 18z" fill="currentColor"/></svg>',
  LOCKED: '<svg viewBox="0 0 22 22"><rect x="4.5" y="10" width="13" height="9" rx="1" fill="currentColor"/><path d="M7.5 10V7a3.5 3.5 0 0 1 7 0v3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
  RECORDING: '<svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="7" fill="currentColor"/></svg>',
  KILLED: '<svg viewBox="0 0 22 22"><rect x="4" y="4" width="14" height="14" fill="currentColor"/></svg>',
};
const STATE_WORD = { AUTO: "Auto", SUGGESTING: "Suggesting", LOCKED: "Locked", RECORDING: "Recording", KILLED: "Killed" };

let state = null;
let mode = "clean";
let lastFrame = -1;
let showFaces = true, showRegions = false, showTable = false;
let armedUntil = 0;
let shownCamera = {};
let hoverX = null;                    // chart crosshair position (kept across redraws)

/* ---------------------------------------------------------------- helpers */
function post(action, body) {
  return fetch("/api/" + action, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Camera-Agent": "1" },
    body: JSON.stringify(body || {}),
  }).then((r) => r.json()).catch(() => ({ ok: false, error: "no connection" }));
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function svg(tag, attrs) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
const signed = (v, d = 1) => (v === null || v === undefined ? "—" : (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d));
const clock = (t) => { t = Math.max(0, Math.floor(t)); return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0"); };

/* ------------------------------------------------------------- live view */
let frameUrl = null;
async function frameLoop() {
  const started = performance.now();
  try {
    const r = await fetch("/api/frame.jpg?mode=" + mode + "&after=" + lastFrame, { cache: "no-store" });
    if (r.ok) {
      lastFrame = Number(r.headers.get("X-Frame-No"));
      const url = URL.createObjectURL(await r.blob());
      const img = $("live");
      img.onload = () => { if (frameUrl && frameUrl !== url) URL.revokeObjectURL(frameUrl); frameUrl = url; };
      img.src = url;
      $("frame-empty").hidden = true;
    } else {
      $("frame-empty").hidden = false;
    }
  } catch (e) {
    $("frame-empty").textContent = "Lost connection to the agent";
    $("frame-empty").hidden = false;
    await new Promise((res) => setTimeout(res, 1000));
  }
  if (state && state.killed && lastFrame >= 0) return;          // agent stopped: keep the last frame
  setTimeout(frameLoop, Math.max(0, 1000 / VIEW_FPS - (performance.now() - started)));
}

/* --------------------------------------------------------------- state */
async function stateLoop() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (r.ok) { state = await r.json(); render(); }
  } catch (e) {
    $("status").textContent = "Lost connection to the agent. If the runner stopped, nothing more is sent to the camera.";
  }
  setTimeout(stateLoop, 250);
}

function render() {
  const s = state;
  // top bar
  $("source").textContent = s.fake ? "Fake camera" : (s.model || "Camera");
  $("source").classList.toggle("fake", !!s.fake);
  $("run-mode").textContent = s.mode === "live" ? "Live" : "Dry run";
  $("run-mode").classList.toggle("live", s.mode === "live");
  $("perf").textContent = (s.fps ? s.fps.toFixed(0) + " fps" : "") + (s.eyes_ms ? " · eyes " + s.eyes_ms.toFixed(0) + " ms" : "");

  // state
  const st = s.state;
  for (const id of ["state", "frame-state"]) $(id).dataset.state = st;
  $("frame-state").querySelector(".state-dot").dataset.state = st;
  $("state-icon").innerHTML = ICONS[st] || "";
  $("state-word").textContent = STATE_WORD[st] || st;
  $("frame-state-word").textContent = STATE_WORD[st] || st;
  $("status").textContent = s.killed ? "The agent has stopped and the bridge is locked. The camera is yours." : s.status;
  const adv = $("advice");
  adv.replaceChildren(...(s.killed ? [] : s.advice.slice(0, 4).map((a) => el("li", "", a))));
  const last = s.events.filter((e) => e.kind === "change").pop();
  $("last-change").hidden = !last;
  if (last) { $("last-change-t").textContent = clock(last.t); $("last-change-text").textContent = last.text; }
  $("frame").classList.toggle("killed", s.killed);

  renderControls(s);
  renderTiles(s);
  renderMarks(s);
  renderMeters(s);
  renderFeed(s);
  renderPeople(s);
  if (showTable) renderTable(s); else renderChart(s);
}

function renderControls(s) {
  const auto = $("btn-auto"), lock = $("btn-lock");
  const armed = performance.now() < armedUntil;
  auto.setAttribute("aria-pressed", String(s.auto));
  auto.classList.toggle("armed", armed && !s.auto);
  $("auto-v").textContent = s.auto ? "On" : armed ? "Press again" : "Off";
  auto.disabled = s.killed || s.mode !== "live";
  lock.setAttribute("aria-pressed", String(s.held));
  $("lock-v").textContent = s.held ? "On" : "Off";
  lock.disabled = s.killed;
  let hint = "";
  if (s.killed) hint = "Restart the bridge to use the agent again.";
  else if (s.mode !== "live") hint = "Dry run: the agent only suggests. Start the runner with --live to let it change " + s.approved.join(", ").replace("IsoSensitivity", "ISO") + ".";
  else if (armed) hint = "Press Auto again to let the agent change ISO.";
  else if (!s.auto) hint = "Auto off: suggesting only. Turn Auto on to let it change ISO (800–12800).";
  else if (s.held) hint = "Locked: holding every setting until you unlock.";
  $("auto-hint").textContent = hint;

  const looks = $("looks");
  if (!looks.childElementCount) {
    s.looks.forEach((l, i) => {
      const b = el("button", "btn", l.name.replace(/ \(.*\)$/, ""));
      b.type = "button"; b.dataset.key = l.key; b.title = l.name + " · key " + (i + 1);
      b.addEventListener("click", () => post("look", { key: l.key }));
      looks.append(b);
    });
  }
  for (const b of looks.children) {
    b.setAttribute("aria-pressed", String(b.dataset.key === s.look.key));
    b.disabled = s.killed;
  }
  $("look-desc").textContent = s.look.description;

  const faceBtn = $("btn-face");
  const faces = (s.eyes && s.eyes.faces) || [];
  faceBtn.disabled = s.killed || !s.faces_available || !faces.length;
  $("face-hint").textContent = !s.faces_available ? "Needs the face model: run tools/fetch_models.sh."
    : !faces.length ? "No face in frame."
    : "Only for people who agree. Frame them, then press it: the agent holds them at this exposure from now on. Saved only on this computer, never uploaded; Forget deletes it.";

  const kill = $("btn-kill");
  kill.classList.toggle("done", s.killed);
  kill.querySelector(".kill-title").textContent = s.killed ? "Killed" : "Kill switch";
  $("kill-sub").textContent = s.killed ? (s.kill_reason || "") + " · bridge locked · the camera is yours"
    : "Stops the agent and locks the bridge · Space";
}

function wouldNote(advice, test) {
  const a = advice.find((x) => x.startsWith("Would change, not approved yet:") && test(x));
  if (!a) return null;
  const m = a.match(/→ ([^;,]+)/) || a.match(/setting (\S+)$/);
  return m ? m[1].trim() : null;
}

function renderTiles(s) {
  const c = s.camera, adv = s.advice || [];
  const set = (id, value, note, cls) => {
    const v = $("v-" + id);
    if (shownCamera[id] !== undefined && shownCamera[id] !== value) {
      const tile = v.closest(".tile");
      tile.classList.remove("changed"); void tile.offsetWidth; tile.classList.add("changed");
    }
    shownCamera[id] = value;
    v.textContent = value;
    const n = $("n-" + id);
    n.className = "note " + (cls || "");
    n.textContent = note;
  };
  const iso = c.iso.replace("ISO ", "");
  const isoApproved = s.approved.includes("IsoSensitivity");
  set("iso", iso, isoApproved ? (s.auto && !s.held ? "Agent sets this" : "Agent may set this") : "Yours", "agent");
  const sh = wouldNote(adv, (a) => a.includes("shutter"));
  set("shutter", c.shutter, sh ? "Would set " + sh + " · not approved" : "Yours", sh ? "would" : "");
  const f = wouldNote(adv, (a) => a.includes("look wants f/"));
  set("fnumber", c.fnumber, f ? "Would set " + f + " · not approved" : "Yours", f ? "would" : "");
  const wbText = c.wb === "ColorTemp" && c.wb_kelvin ? c.wb_kelvin + "K" : c.wb;
  const wb = wouldNote(adv, (a) => a.includes("Light measures"));
  set("wb", wbText, wb ? "Would set " + wb + " · not approved" : c.wb === "AWB" ? "Auto: may drift mid-shot" : "Yours", wb ? "would" : "");
  set("fps", c.frame_rate.replace(/^(\d+)\.(\d+)p$/, "$1.$2p"), c.recording ? "Recording" : "Never changed", "");
}

function renderMarks(s) {
  const marks = $("marks");
  const frame = $("frame");
  frame.querySelectorAll(".face-tag").forEach((t) => t.remove());
  marks.replaceChildren();
  if (!s.eyes) return;
  const [w, h] = s.eyes.frame;
  marks.setAttribute("viewBox", "0 0 " + w + " " + h);
  if (showRegions) {
    const cw = w / 8, ch = h / 6;
    for (const [r, c] of s.eyes.light_sources) {
      marks.append(svg("rect", { x: c * cw + 2, y: r * ch + 2, width: cw - 4, height: ch - 4, class: "mark-region" }));
    }
  }
  if (!showFaces) return;
  for (const f of s.eyes.faces) {
    const [x, y, fw, fh] = f.box;
    const k = Math.min(fw, fh) * 0.22;
    const path = ["M", x, y + k, "V", y, "H", x + k, "M", x + fw - k, y, "H", x + fw, "V", y + k,
      "M", x + fw, y + fh - k, "V", y + fh, "H", x + fw - k, "M", x + k, y + fh, "H", x, "V", y + fh - k].join(" ");
    marks.append(svg("path", { d: path, class: "mark-face" + (f.clipping ? " clipping" : "") }));
    const tag = el("div", "face-tag" + (f.clipping ? " clipping" : ""),
      (f.name ? f.name + " · " : "") + signed(f.stops) + " st" + (f.target !== null && f.target !== undefined ? " · target " + signed(f.target) : "") + (f.clipping ? " · clipping" : ""));
    tag.style.left = (x / w * 100) + "%";
    tag.style.top = "calc(" + (y / h * 100) + "% - 6px)";
    frame.append(tag);
  }
}

function renderMeters(s) {
  const e = s.eyes;
  if (!e) return;
  const clipStops = 6.2;
  const hr = Math.max(0, e.headroom);
  $("headroom-v").textContent = hr.toFixed(1) + " st";
  const hf = $("headroom-fill");
  hf.style.width = Math.min(100, hr / clipStops * 100) + "%";
  hf.dataset.level = hr < 1 / 3 ? "stop" : hr < 1 ? "caution" : "go";
  const limit = s.look.max_clip_pct || 0.5, scale = Math.max(limit * 4, 2);
  $("clip-v").textContent = e.clipped_important.toFixed(1) + "% · limit " + limit + "%";
  const cf = $("clip-fill");
  cf.style.width = Math.min(100, e.clipped_important / scale * 100) + "%";
  cf.dataset.level = e.clipped_important > limit ? "stop" : e.clipped_important > limit / 2 ? "caution" : "go";
  $("clip-limit").style.left = (limit / scale * 100) + "%";
}

let feedKey = "";
function renderFeed(s) {
  const items = s.events.filter((e) => e.kind !== "status").slice(-40).reverse();
  const key = items.length ? items[0].t + items[0].text + items.length : "";
  if (key === feedKey) return;
  feedKey = key;
  const feed = $("feed");
  if (!items.length) { feed.replaceChildren(el("li", "feed-empty", "Nothing yet.")); return; }
  feed.replaceChildren(...items.map((e) => {
    const li = el("li", "k-" + e.kind);
    li.append(el("span", "f-time", clock(e.t)), el("span", "f-kind", KIND[e.kind] || e.kind), el("span", "f-text", e.text));
    return li;
  }));
}

let peopleKey = "";
function renderPeople(s) {
  const key = JSON.stringify(s.people) + s.killed;
  if (key === peopleKey) return;
  peopleKey = key;
  $("people").replaceChildren(...s.people.map((p) => {
    const li = el("li");
    const forget = el("button", "p-forget", "Forget");
    forget.type = "button";
    forget.disabled = s.killed;
    forget.addEventListener("click", () => post("forget", { id: p.id }));
    li.append(el("span", "p-name", p.name), el("span", "p-target", signed(p.target) + " st"), forget);
    return li;
  }));
}

/* ----------------------------------------------------------------- chart */
function renderChart(s) {
  const box = $("chart");
  const W = box.clientWidth, H = box.clientHeight;
  const m = { l: 34, r: 74, t: 14, b: 22 };
  const hist = s.history;
  const root = $("chart-svg");
  root.replaceChildren();
  root.setAttribute("viewBox", "0 0 " + W + " " + H);
  if (!hist.length) return;
  const tMax = hist[hist.length - 1].t, tMin = tMax - WINDOW_S;
  const pts = hist.filter((p) => p.t >= tMin);
  let lo = -4, hi = 4;
  for (const p of pts) for (const v of [p.face, p.key, p.target]) if (v !== null && v !== undefined) { lo = Math.min(lo, Math.floor(v)); hi = Math.max(hi, Math.ceil(v)); }
  lo = Math.max(lo, -8); hi = Math.min(hi, 7);
  const x = (t) => m.l + (t - tMin) / WINDOW_S * (W - m.l - m.r);
  const y = (v) => m.t + (hi - Math.max(lo, Math.min(hi, v))) / (hi - lo) * (H - m.t - m.b);

  for (let v = Math.ceil(lo / 2) * 2; v <= hi; v += 2) {
    root.append(svg("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: v === 0 ? "grid zero" : "grid" }));
    const label = svg("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", class: "tick" });
    label.textContent = v === 0 ? "0" : (v > 0 ? "+" : "−") + Math.abs(v);
    root.append(label);
  }
  for (let ago = 0; ago <= WINDOW_S; ago += 15) {
    const label = svg("text", { x: x(tMax - ago), y: H - 4, "text-anchor": ago === 0 ? "end" : "middle", class: "tick" });
    label.textContent = ago === 0 ? "now" : "−" + ago + " s";
    root.append(label);
  }
  // target band (±⅓ stop dead band), only where there's a face
  let band = "";
  const seg = [];
  const flushBand = () => {
    if (seg.length > 1) band += "M" + seg.map((p) => x(p.t) + "," + y(p.target + 1 / 3)).join("L") + "L" +
      seg.slice().reverse().map((p) => x(p.t) + "," + y(p.target - 1 / 3)).join("L") + "Z";
    seg.length = 0;
  };
  for (const p of pts) { if (p.target !== null && p.target !== undefined) seg.push(p); else flushBand(); }
  flushBand();
  if (band) root.append(svg("path", { d: band, class: "band" }));

  const line = (key) => {
    let d = "", pen = false;
    for (const p of pts) {
      if (p[key] === null || p[key] === undefined) { pen = false; continue; }
      d += (pen ? "L" : "M") + x(p.t).toFixed(1) + "," + y(p[key]).toFixed(1);
      pen = true;
    }
    return d;
  };
  root.append(svg("path", { d: line("key"), class: "l-key" }));
  root.append(svg("path", { d: line("face"), class: "l-face" }));

  // agent changes
  const changes = s.events.filter((e) => e.kind === "change" && e.t >= tMin);
  for (const c of changes) {
    root.append(svg("line", { x1: x(c.t), x2: x(c.t), y1: m.t, y2: H - m.b, class: "change" }));
    root.append(svg("circle", { cx: x(c.t), cy: m.t, r: 4, class: "change-dot" }));
  }
  // end labels (move apart only if they'd overlap)
  const last = pts[pts.length - 1];
  const ends = [];
  if (last.face !== null && last.face !== undefined) ends.push({ v: last.face, text: "Face " + signed(last.face), cls: "end-label face" });
  if (last.key !== null && last.key !== undefined) ends.push({ v: last.key, text: "Key " + signed(last.key), cls: "end-label" });
  ends.forEach((e) => { e.py = y(e.v); });
  if (ends.length === 2 && Math.abs(ends[0].py - ends[1].py) < 14) {
    const mid = (ends[0].py + ends[1].py) / 2, up = ends[0].py <= ends[1].py ? 0 : 1;
    ends[up].py = mid - 7; ends[1 - up].py = mid + 7;
  }
  for (const e of ends) {
    const t = svg("text", { x: x(last.t) + 8, y: e.py + 4, class: e.cls });
    t.textContent = e.text;
    root.append(t);
  }
  hover(root, pts, changes, x, y, m, W, H);
}

function hover(root, pts, changes, x, y, m, W, H) {
  const tip = $("tip");
  const hit = svg("rect", { x: m.l, y: 0, width: Math.max(0, W - m.l - m.r), height: H, fill: "transparent" });
  root.append(hit);
  const show = (px) => {
    let best = pts[0];
    for (const p of pts) if (Math.abs(x(p.t) - px) < Math.abs(x(best.t) - px)) best = p;
    root.querySelectorAll(".cross,.hover-dot").forEach((n) => n.remove());
    root.insertBefore(svg("line", { x1: x(best.t), x2: x(best.t), y1: m.t, y2: H - m.b, class: "cross" }), hit);
    for (const [k, color] of [["face", "#ffffff"], ["key", "#8c8c8c"]]) {
      if (best[k] !== null && best[k] !== undefined) root.insertBefore(svg("circle", { cx: x(best.t), cy: y(best[k]), r: 4, fill: color, class: "hover-dot" }), hit);
    }
    tip.replaceChildren();
    tip.append(el("div", "t-time", Math.round(pts[pts.length - 1].t - best.t) === 0 ? "Now" : Math.round(pts[pts.length - 1].t - best.t) + " s ago"));
    const row = (color, value, label) => {
      const d = el("div", "t-row"); const i = el("i"); i.style.background = color;
      d.append(i, el("b", "", value), el("span", "", label)); tip.append(d);
    };
    if (best.face !== null && best.face !== undefined) row("#ffffff", signed(best.face) + " st", "Face");
    if (best.target !== null && best.target !== undefined) row("rgba(255,255,255,.3)", signed(best.target) + " st", "Target");
    row("#8c8c8c", signed(best.key) + " st", "Scene key");
    row("transparent", best.headroom.toFixed(1) + " st", "Headroom");
    row("transparent", "ISO " + best.iso, "Camera");
    const near = changes.find((c) => Math.abs(c.t - best.t) <= 0.6);
    if (near) tip.append(el("div", "t-change", near.text));
    tip.hidden = false;
    const left = Math.min(Math.max(0, x(best.t) + 14), W - tip.offsetWidth);
    tip.style.left = (x(best.t) + 14 + tip.offsetWidth > W ? x(best.t) - 14 - tip.offsetWidth : left) + "px";
  };
  if (hoverX !== null && hoverX >= m.l && hoverX <= W - m.r) show(hoverX); else tip.hidden = true;
}
// One set of listeners on the chart; the drawing is redone 4 times a second.
$("chart-svg").addEventListener("pointermove", (ev) => {
  hoverX = ev.clientX - $("chart-svg").getBoundingClientRect().left;
  if (state && !showTable) renderChart(state);
});
$("chart-svg").addEventListener("pointerleave", () => { hoverX = null; $("tip").hidden = true; if (state) renderChart(state); });

function renderTable(s) {
  const rows = s.history.filter((p, i) => i % 20 === 0 || i === s.history.length - 1).slice(-30).reverse();
  $("chart-rows").replaceChildren(...rows.map((p) => {
    const tr = el("tr");
    for (const v of [clock(p.t), signed(p.face), signed(p.target), signed(p.key), p.headroom.toFixed(1), p.iso]) tr.append(el("td", "", String(v)));
    return tr;
  }));
}

/* -------------------------------------------------------------- controls */
function kill() { post("kill"); }
function toggleAuto() {
  if (!state || state.killed || state.mode !== "live") return;
  if (state.auto) { post("auto", { on: false }); return; }
  if (performance.now() < armedUntil) { armedUntil = 0; post("auto", { on: true }); }
  else { armedUntil = performance.now() + 3000; render(); setTimeout(() => state && render(), 3100); }
}
function toggleLock() { if (state && !state.killed) post("lock", { on: !state.held }); }

document.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => {
  mode = b.dataset.mode;
  document.querySelectorAll("[data-mode]").forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
  $("fc-legend").hidden = mode !== "false_color";
  lastFrame = -1;
}));
$("t-faces").addEventListener("click", (e) => { showFaces = !showFaces; e.currentTarget.setAttribute("aria-pressed", String(showFaces)); if (state) render(); });
$("t-regions").addEventListener("click", (e) => { showRegions = !showRegions; e.currentTarget.setAttribute("aria-pressed", String(showRegions)); if (state) render(); });
$("table-toggle").addEventListener("click", (e) => {
  showTable = !showTable;
  e.currentTarget.setAttribute("aria-pressed", String(showTable));
  $("chart").hidden = showTable; $("chart-table").hidden = !showTable;
  if (state) render();
});
$("btn-kill").addEventListener("click", kill);
$("btn-auto").addEventListener("click", toggleAuto);
$("btn-lock").addEventListener("click", toggleLock);
$("btn-face").addEventListener("click", () => {
  $("face-form").hidden = false; $("btn-face").hidden = true;
  $("face-name").value = ""; $("face-name").focus();
});
$("face-cancel").addEventListener("click", () => { $("face-form").hidden = true; $("btn-face").hidden = false; });
$("face-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const reply = await post("face", { name: $("face-name").value });
  $("face-form").hidden = true; $("btn-face").hidden = false;
  if (!reply.ok) $("face-hint").textContent = "Not saved: " + reply.error;
});
document.addEventListener("keydown", (ev) => {
  if (ev.target.closest("input, textarea") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  if (ev.code === "Space") { ev.preventDefault(); kill(); }
  else if (ev.key === "a") toggleAuto();
  else if (ev.key === "l") toggleLock();
  else if (ev.key === "m") post("mark", { label: "light change" });
  else if (state && /^[1-5]$/.test(ev.key)) post("look", { key: state.looks[Number(ev.key) - 1].key });
});
window.addEventListener("resize", () => state && render());

stateLoop();
frameLoop();
