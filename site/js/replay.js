// The real test, replayed from the agent's own logs (data/site.json, made by tools/export_site_data.py).
// Time runs at real speed. The picture is the frame the agent was looking at when it made each change.

const $ = (s, r = document) => r.querySelector(s);
const SVGNS = "http://www.w3.org/2000/svg";
const NAMES = { IsoSensitivity: "iso", ShutterSpeed: "shutter", FNumber: "f", Colortemp: "wb" };
const TAIL_S = 4;                       // keep playing this long after it settles

const fmtStops = (v) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(1);
const fmtT = (t) => "T " + (t < 0 ? "−" : "+") + Math.abs(t).toFixed(1).padStart(4, "0") + " s";
const isoNum = (s) => s.replace("ISO ", "");
const fUp = (s) => s.replace("f/", "F");

export function initReplay(data, { motion }) {
  const root = $("#replay");
  const el = {
    a: $("#rp-img-a"), b: $("#rp-img-b"), tally: $("#rp-tally"), state: $("#rp-state"), look: $("#rp-look"),
    t: $("#rp-t"), sub: $("#rp-sub"), play: $("#rp-play"), chart: $("#rp-chart"), stats: $("#rp-stats"),
    iso: $("#rp-iso"), shutter: $("#rp-shutter"), f: $("#rp-f"), wb: $("#rp-wb"),
  };
  let test, start, end, raf = 0, t0 = 0, playing = false, shownFrame = -1, front = el.a, lastSub = "", chart;

  function select(key) {
    test = data.tests[key];
    for (const b of root.querySelectorAll(".seg button")) b.setAttribute("aria-selected", String(b.dataset.test === key));
    // Start just after the test's own setup moved the camera, so the first frame matches what's on screen.
    const tr = test.trace;
    const jump = tr.findIndex((r, i) => i > 0 && r[2] !== tr[i - 1][2] && r[0] < 0);
    start = jump > 0 ? tr[jump][0] + 0.05 : tr[0][0];
    end = test.settle_s + TAIL_S;
    for (const im of [el.a, el.b]) im.alt = "";
    el.look.textContent = "Look · " + test.look;
    shownFrame = -1;
    lastSub = "";
    el.sub.classList.remove("on");
    chart = buildChart(el.chart, test, start, end);
    buildStats(test);
    draw(motion ? start : end, false);
  }

  function valuesAt(t) {
    const v = { shutter: test.start.shutter, f: fUp(test.start.fnumber), wb: test.start.wb };
    for (const s of test.setup) {
      if (s.setting === "ShutterSpeed") v.shutter = s.to;
      if (s.setting === "FNumber") v.f = fUp(s.to);
      if (s.setting === "Colortemp") v.wb = s.to;
    }
    const done = test.changes.filter((c) => c.t <= t);
    for (const c of done) {
      if (c.setting === "ShutterSpeed") v.shutter = c.to;
      if (c.setting === "FNumber") v.f = fUp(c.to);
      if (c.setting === "Colortemp") v.wb = c.to;
    }
    let row = test.trace[0];
    for (const r of test.trace) { if (r[0] <= t) row = r; else break; }
    v.iso = String(row[2]);
    v.key = row[1];
    v.done = done;
    return v;
  }

  showFrame.n = 0;
  function showFrame(k) {
    if (k === shownFrame) return;
    shownFrame = k;
    const token = ++showFrame.n;                      // only the latest request may swap the picture
    const back = front === el.a ? el.b : el.a;
    back.src = test.frames[k];
    back.alt = "Real FX2 live view: a white wall and one lamp, the frame the agent saw for change " + (k + 1);
    back.decode().catch(() => {}).then(() => {
      if (token !== showFrame.n) return;
      back.classList.add("on");
      if (front !== back) front.classList.remove("on");
      front = back;
    });
  }

  function setSub(html) {
    if (html === lastSub) return;
    lastSub = html;
    el.sub.classList.remove("on");
    clearTimeout(setSub.timer);
    setSub.timer = setTimeout(() => { el.sub.innerHTML = html; if (html) el.sub.classList.add("on"); }, html ? 180 : 0);
  }

  function draw(t, live = true) {
    const v = valuesAt(t);
    const auto = t >= 0;
    el.tally.classList.toggle("auto", auto);
    el.state.textContent = auto ? (t >= test.settle_s ? "Auto · settled" : "Auto") : "Dry run";
    el.t.textContent = fmtT(t);
    for (const [k, id] of Object.entries(NAMES)) {
      const next = k === "IsoSensitivity" ? v.iso : k === "ShutterSpeed" ? v.shutter : k === "FNumber" ? v.f : v.wb;
      if (el[id].textContent !== next) {
        el[id].textContent = next;
        if (live) { el[id].classList.add("flash"); setTimeout(() => el[id].classList.remove("flash"), 900); }
      }
    }
    const used = new Set(test.changes.map((c) => c.setting));
    for (const span of root.querySelectorAll(".hud-bottom span[data-k]")) span.classList.toggle("idle", !used.has(span.dataset.k));
    const k = test.changes.findIndex((c) => c.t > t);
    showFrame(Math.min(k === -1 ? test.frames.length - 1 : k, test.frames.length - 1));
    // Subtitles: the setup line first, then each change's own reason, then the settled status.
    const last = v.done[v.done.length - 1];
    if (!auto) {
      setSub(t > start + 0.3 ? "Test setup, by the test script: " + test.setup.map((s) => s.to).join(", ") +
        "<small>Auto is off: the agent only watches</small>" : "");
    } else if (t >= test.settle_s + 1.2) {
      setSub(test.settled_status + "<small>Settled in " + test.settle_s + " s</small>");
    } else if (last) {
      setSub(last.reason + "<small>Confirmed by the camera in " + last.ms + " ms</small>");
    } else {
      setSub("Auto on<small>The agent may now change " + [...used].map((s) => NAMES[s] === "f" ? "iris" : NAMES[s] === "wb" ? "WB" : NAMES[s] === "iso" ? "ISO" : "shutter").join(", ") + "</small>");
    }
    chart.at(t, v.key);
  }

  function tick(now) {
    const t = start + (now - t0) / 1000;
    draw(Math.min(t, end));
    if (t < end) raf = requestAnimationFrame(tick);
    else { playing = false; el.play.classList.remove("hidden"); }
  }

  function play() {
    cancelAnimationFrame(raf);
    playing = true;
    el.play.classList.add("hidden");
    shownFrame = -1;
    draw(start, false);
    t0 = performance.now();
    raf = requestAnimationFrame(tick);
  }

  function buildStats(tst) {
    const slowest = Math.max(...tst.changes.map((c) => c.ms));
    const settings = new Set(tst.changes.map((c) => c.setting)).size;
    const items = [
      ["Changes", tst.changes.length, ""],
      ["To settle", tst.settle_s, " s"],
      settings > 1 ? ["Settings it used", settings, ""] : ["Slowest confirm", slowest, " ms"],
      ["Changes in the " + tst.hold_s + " s after", tst.changes_during_hold, ""],
    ];
    el.stats.innerHTML = "";
    for (const [dt, dd, unit] of items) {
      const d = document.createElement("div");
      d.innerHTML = "<dt></dt><dd><span></span><small></small></dd>";
      d.querySelector("dt").textContent = dt;
      d.querySelector("span").textContent = dd;
      d.querySelector("small").textContent = unit;
      el.stats.append(d);
    }
  }

  for (const b of root.querySelectorAll(".seg button")) {
    b.addEventListener("click", () => { select(b.dataset.test); if (motion) play(); });
  }
  el.play.addEventListener("click", play);
  window.addEventListener("resize", () => { const t = chart.t; chart = buildChart(el.chart, test, start, end); chart.at(t ?? end, valuesAt(t ?? end).key); });

  select("test1");
  if (motion) {
    let seen = false;
    new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting && !seen) { seen = true; play(); }
    }, { threshold: 0.55 }).observe($("#player"));
  } else {
    el.play.classList.remove("hidden");
  }
}

// Scene exposure (stops from grey) over time, the look's window as a band, a tick at each change.
function buildChart(host, test, start, end) {
  host.innerHTML = "";
  const W = host.clientWidth, H = host.clientHeight, m = { l: 34, r: 10, t: 22, b: 26 };
  const rows = test.trace.filter((r) => r[0] >= start - 0.01 && r[0] <= end + 0.3);
  const ys = rows.map((r) => r[1]).concat(test.window);
  const yLo = Math.floor(Math.min(...ys) - 0.4), yHi = Math.ceil(Math.max(...ys) + 0.4);
  const x = (t) => m.l + ((t - start) / (end - start)) * (W - m.l - m.r);
  const y = (v) => m.t + ((yHi - v) / (yHi - yLo)) * (H - m.t - m.b);
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const add = (parent, tag, attrs, text) => {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    parent.append(n);
    return n;
  };
  const g = add(svg, "g", { class: "grid" }), ax = add(svg, "g", { class: "axis" });
  for (let v = yLo; v <= yHi; v++) {
    add(g, "line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) });
    add(ax, "text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v));
  }
  for (let t = Math.ceil(start / 2) * 2; t <= end; t += 2) {
    add(ax, "text", { x: x(t), y: H - 6, "text-anchor": "middle" }, (t > 0 ? "+" : t < 0 ? "−" : "") + Math.abs(t) + " s");
  }
  add(svg, "rect", { class: "band", x: m.l, width: W - m.l - m.r, y: y(test.window[1]), height: y(test.window[0]) - y(test.window[1]) });
  add(svg, "line", { class: "zero", x1: x(0), x2: x(0), y1: m.t - 8, y2: H - m.b });
  add(svg, "text", { class: "tick-lab", x: x(0) + 6, y: m.t - 2 }, "AUTO ON");
  const pts = rows.map((r) => [x(r[0]), y(r[1])]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join("");
  add(svg, "path", { class: "ghost", d });
  const clipId = "clip-" + Math.random().toString(36).slice(2);
  const clip = add(add(svg, "defs", {}), "clipPath", { id: clipId });
  const clipRect = add(clip, "rect", { x: 0, y: 0, width: 0, height: H });
  add(svg, "path", { class: "line", d, "clip-path": `url(#${clipId})` });
  const ticks = add(svg, "g", {});
  test.changes.forEach((c, i) => {
    const tx = x(c.t);
    const tk = add(ticks, "g", { opacity: 0 });
    add(tk, "line", { class: "tick-ch", x1: tx, x2: tx, y1: H - m.b, y2: H - m.b - 8 });
    if (W > 560 || i % 2 === 0) add(tk, "text", { class: "tick-lab", x: tx, y: H - m.b - 12, "text-anchor": "middle" }, c.to.replace("ISO ", ""));
    c._el = tk;
  });
  const head = add(svg, "g", { class: "head" });
  const hl = add(head, "line", { y1: m.t - 6, y2: H - m.b });
  const hc = add(head, "circle", { r: 5 });
  // Hover: crosshair + tooltip with the logged numbers.
  const hov = add(svg, "g", { class: "hover", opacity: 0 });
  const vl = add(hov, "line", { y1: m.t, y2: H - m.b });
  const dot = add(hov, "circle", { r: 4.5 });
  const tip = document.createElement("div");
  tip.className = "tip";
  host.append(svg, tip);
  const hit = add(svg, "rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" });
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const px = e.clientX - r.left;
    let best = rows[0];
    for (const row of rows) if (Math.abs(x(row[0]) - px) < Math.abs(x(best[0]) - px)) best = row;
    const bx = x(best[0]), by = y(best[1]);
    vl.setAttribute("x1", bx); vl.setAttribute("x2", bx);
    dot.setAttribute("cx", bx); dot.setAttribute("cy", by);
    hov.setAttribute("opacity", 1);
    tip.innerHTML = `<b>${fmtStops(best[1])} st</b> · ISO ${best[2]}<br>${fmtT(best[0])}`;
    tip.style.opacity = 1;
    tip.style.left = Math.min(bx + 12, W - 150) + "px";
    tip.style.top = Math.max(by - 54, 0) + "px";
  });
  hit.addEventListener("pointerleave", () => { hov.setAttribute("opacity", 0); tip.style.opacity = 0; });
  host.setAttribute("aria-label", `Scene exposure for ${test.name}: it starts at ${fmtStops(rows[0][1])} stops, ` +
    `Auto comes on at 0 s, and it settles at ${fmtStops(rows[rows.length - 1][1])} stops after ${test.settle_s} s, ` +
    `inside the look's window of ${test.window[0]} to +${test.window[1]}.`);
  const api = {
    t: null,
    at(t, key) {
      api.t = t;
      const px = x(t);
      clipRect.setAttribute("width", Math.max(0, px));
      hl.setAttribute("x1", px); hl.setAttribute("x2", px);
      hc.setAttribute("cx", px); hc.setAttribute("cy", y(key));
      for (const c of test.changes) c._el.setAttribute("opacity", c.t <= t ? 1 : 0);
    },
  };
  return api;
}
