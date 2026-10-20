// Camera Agent site. Scroll scenes use GSAP + ScrollTrigger (vendor/gsap, 3.14.2) with tall sections and
// sticky stages. Without motion (prefers-reduced-motion) every scene shows its end state instead.
import { initReplay } from "./replay.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const html = document.documentElement;
const motion = html.classList.contains("motion");
const fine = html.classList.contains("fine");

const ready = new Promise((res) => (document.readyState === "complete" ? res() : addEventListener("load", res)));
const scriptsReady = new Promise((res) => {
  const check = () => (window.gsap && window.ScrollTrigger && window.SplitText ? res() : setTimeout(check, 30));
  check();
});

main();

async function main() {
  grain();
  const data = await fetch("data/site.json").then((r) => r.json());
  await scriptsReady;
  gsap.registerPlugin(ScrollTrigger, SplitText);
  ScrollTrigger.config({ ignoreMobileResize: true });
  nav();
  hero(data);
  manifesto();
  logScene();
  how();
  initReplay(data, { motion });
  looks(data);
  safety(data);
  dashboard();
  entrances();
  closeScene();
  cursor();
  videos();
  await document.fonts.ready;
  await ready;
  ScrollTrigger.refresh();
}

// ---------- film grain: a small noise tile drawn once ----------
function grain() {
  const c = document.createElement("canvas");
  c.width = c.height = 180;
  const x = c.getContext("2d");
  const img = x.createImageData(180, 180);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.random() * 255;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  $(".grain").style.backgroundImage = `url(${c.toDataURL()})`;
}

// ---------- nav: under the draft bar at the top, solid after, hides on the way down ----------
function nav() {
  const n = $("#nav"), bar = $(".draft-bar");
  let lastY = scrollY;
  const update = () => {
    const y = scrollY, top = bar.offsetHeight;
    n.style.setProperty("--nav-y", y < top ? top - y + "px" : "0px");
    n.classList.toggle("solid", y > top);
    n.classList.toggle("hide", y > lastY && y > innerHeight * 0.6);
    lastY = y;
  };
  addEventListener("scroll", update, { passive: true });
  update();
  for (const s of $$("[data-theme=light]")) {
    ScrollTrigger.create({ trigger: s, start: "top 64px", end: "bottom 64px", toggleClass: { targets: n, className: "light" } });
  }
}

// ---------- 01 hero: the viewfinder ----------
function hero(data) {
  if (motion) $("#hero-video").play().catch(() => {});
  // Timecode at 23.976 fps, counted in 24-frame seconds, like the camera.
  const tc = $("#hero-tc"), startMs = performance.now();
  const pad = (n) => String(n).padStart(2, "0");
  (function runTC() {
    const f = Math.floor(((performance.now() - startMs) / 1000) * (24000 / 1001));
    const s = Math.floor(f / 24), m = Math.floor(s / 60);
    tc.textContent = `01:${pad(m % 60)}:${pad(s % 60)}:${pad(f % 24)}`;
    requestAnimationFrame(runTC);
  })();
  // Subtitles: the real lines from Test 1, with the ISO readout following them.
  const test = data.tests.test1, sub = $("#hero-sub"), iso = $("#hero-iso");
  const lines = test.changes.map((c) => ({ text: c.reason, small: `Confirmed by the camera in ${c.ms} ms`, iso: c.to }));
  lines.push({ text: test.settled_status, small: `Settled in ${test.settle_s} s · Oct 19, real FX2`, iso: test.changes.at(-1).to });
  let k = 0;
  const next = () => {
    const l = lines[k % lines.length];
    sub.classList.remove("on");
    setTimeout(() => {
      sub.innerHTML = `${l.text}<small>${l.small}</small>`;
      sub.classList.add("on");
      iso.textContent = l.iso.replace("ISO ", "");
      iso.classList.add("flash");
      setTimeout(() => iso.classList.remove("flash"), 900);
    }, 450);
    k = k % lines.length === lines.length - 1 ? 0 : k + 1;
    if (k === 0) setTimeout(() => (iso.textContent = test.setup[0].to.replace("ISO ", "")), 3600);
  };
  setTimeout(() => { next(); setInterval(next, 3900); }, 1400);
  $("#hero-state").closest(".tally").classList.add("auto");

  if (!motion) return;
  gsap.from(".hero-title .ln > span", { yPercent: 118, duration: 1.7, ease: "expo.out", stagger: 0.12, delay: 0.15 });
  gsap.from([".hero .eyebrow", ".hero .lede", ".hero-notes"], { y: 24, opacity: 0, duration: 1.4, ease: "power3.out", stagger: 0.1, delay: 0.5 });
  gsap.from(".hero .vf i", { scale: 1.6, opacity: 0, duration: 1.4, ease: "expo.out", stagger: 0.05, delay: 0.2 });
  gsap.from(".hero .hud", { opacity: 0, duration: 1, delay: 0.7 });
  // Scroll: the frame pushes in, the letterbox closes to 2.39:1, the title lifts away.
  const lb = () => Math.max(innerHeight * 0.08, (innerHeight - innerWidth / 2.39) / 2);
  const tl = gsap.timeline({ scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom bottom", scrub: 0.6, invalidateOnRefresh: true } });
  tl.to(".scroll-cue", { opacity: 0, duration: 0.1 }, 0)
    .fromTo(".hero", { "--lb": "0px" }, { "--lb": () => lb() + "px", duration: 0.6, ease: "power2.inOut" }, 0)
    .fromTo("#hero-frame", { scale: 1.08 }, { scale: 1, duration: 1, ease: "none" }, 0)
    .to(".hero-copy", { y: -80, opacity: 0, duration: 0.45, ease: "power1.in" }, 0.12)
    .to(".hero-notes", { opacity: 0, duration: 0.3 }, 0.2)
    .to("#hero-frame .shade", { opacity: 0.45, duration: 0.4 }, 0.3)
    .to({}, { duration: 0.2 });
}

// ---------- 02 manifesto: words light up as you read ----------
function manifesto() {
  const p = $("#manifesto");
  const split = new SplitText(p, { type: "words", wordsClass: "w" });
  if (!motion) return;
  gsap.to(split.words, {
    opacity: 1, ease: "none", stagger: 0.1,
    scrollTrigger: { trigger: p, start: "top 78%", end: "bottom 42%", scrub: 0.5 },
  });
}

// ---------- 03 S-Log3 -> LUT wipe ----------
function logScene() {
  const log = $("#log-video"), graded = $("#graded-video"), wipe = $("#wipe");
  // Keep the graded copy on the same frame as the log copy.
  setInterval(() => {
    if (!log.paused && Math.abs(graded.currentTime - log.currentTime) > 0.06) graded.currentTime = log.currentTime;
  }, 500);
  if (!motion) return;
  const tl = gsap.timeline({ scrollTrigger: { trigger: ".logscene", start: "top top", end: "bottom bottom", scrub: 0.7 } });
  tl.from(".log-copy > *", { y: 40, opacity: 0, stagger: 0.05, duration: 0.25, ease: "power3.out" }, 0)
    .from(".wipe-label", { opacity: 0, duration: 0.1 }, 0.2)
    .fromTo(wipe, { "--split": "100%" }, { "--split": "50%", duration: 0.5, ease: "power2.inOut" }, 0.22)
    .to(".log-copy", { opacity: 0.15, duration: 0.2 }, 0.5)
    .to({}, { duration: 0.25 });
}

// ---------- 04 how it thinks: four steps, one monitor ----------
function how() {
  const mon = $("#monitor"), cap = $("#monitor-cap");
  const caps = {
    see: "Readouts are an illustration, measured live from the placeholder clip.",
    decide: "Illustration: the Interview look's rules.",
    check: "Illustration: the range check every change goes through.",
    change: "This line is real, from Test 3 on Oct 19. The clip is a placeholder.",
  };
  const set = (step) => {
    mon.dataset.step = step;
    cap.textContent = caps[step];
    for (const s of $$(".step")) s.classList.toggle("on", s.dataset.step === step);
  };
  for (const s of $$(".step")) {
    ScrollTrigger.create({ trigger: s, start: "top 58%", end: "bottom 58%", onToggle: (st) => st.isActive && set(s.dataset.step) });
  }
  set("see");
  // 48 regions, measured from the clip itself every 300 ms (display light, so it's an illustration).
  const v = $("#how-video"), c = $("#region-grid"), x = c.getContext("2d", { willReadFrequently: true }), cells = $("#cells");
  for (let i = 0; i < 48; i++) cells.append(document.createElement("span"));
  const lin = (u) => (u <= 0.04045 ? u / 12.92 : ((u + 0.055) / 1.055) ** 2.4);
  setInterval(() => {
    if (v.paused || mon.dataset.step !== "see" || v.readyState < 2) return;
    x.drawImage(v, 0, 0, 8, 6);
    const d = x.getImageData(0, 0, 8, 6).data;
    let sum = 0;
    cells.childNodes.forEach((cell, i) => {
      const Y = 0.2126 * lin(d[i * 4] / 255) + 0.7152 * lin(d[i * 4 + 1] / 255) + 0.0722 * lin(d[i * 4 + 2] / 255);
      const st = Math.log2(Math.max(Y, 1e-4) / 0.18);
      sum += st;
      cell.textContent = (st >= 0 ? "+" : "−") + Math.abs(st).toFixed(1);
      cell.classList.toggle("hot", st > 1.5);
    });
    $("#see-key").textContent = ((sum / 48) >= 0 ? "+" : "−") + Math.abs(sum / 48).toFixed(1);
  }, 300);
}

// ---------- 06 looks: built from agent/looks.py, scrolled sideways ----------
function looks(data) {
  const track = $("#looks-track");
  const bgs = ["media/placeholder/night.jpg", "media/placeholder/lamp.jpg", "media/placeholder/sunbeam.jpg", "media/placeholder/lamp.jpg", "media/placeholder/sunbeam.jpg"];
  const st = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1);
  data.looks.forEach((l, i) => {
    const [name, sub] = l.name.replace(")", "").split(" (");
    const [a0, a1] = l.aperture_range;
    const card = document.createElement("article");
    card.className = "look-card";
    card.innerHTML = `<div class="bgimg"></div><span class="no"></span><h3></h3><p></p><dl class="specs"></dl>`;
    card.querySelector(".bgimg").style.backgroundImage = `url(${bgs[i % bgs.length]})`;
    card.querySelector(".no").textContent = String(i + 1).padStart(2, "0");
    card.querySelector("h3").textContent = name;
    if (sub) card.querySelector("h3").insertAdjacentHTML("beforeend", "<em></em>"), (card.querySelector("h3 em").textContent = sub);
    card.querySelector("p").textContent = l.description;
    const specs = [
      ["Aperture", a0 === a1 ? `f/${a0}, fixed` : `f/${a0} – f/${a1}`],
      ["Shutter", l.shutter_180 ? "180°" : "Yours"],
      ["Face at", st(l.face_target) + " st"],
      ["Scene window", `${st(l.key_window[0])} to ${st(l.key_window[1])}`],
      ["Clipping", `≤ ${l.max_clip_pct}%`],
      ["ISO", l.iso_policy === "base_first" ? "Base ISO first" : "Free, fast"],
    ];
    const dl = card.querySelector(".specs");
    for (const [k, v] of specs) {
      const d = document.createElement("div");
      d.innerHTML = "<dt></dt><dd></dd>";
      d.firstChild.textContent = k;
      d.lastChild.textContent = v;
      dl.append(d);
    }
    track.append(card);
  });
  if (!motion) return;
  const scene = $(".looks"), dist = () => Math.max(0, track.scrollWidth - innerWidth);
  const size = () => (scene.style.height = dist() + innerHeight + "px");
  size();
  ScrollTrigger.addEventListener("refreshInit", size);
  gsap.to(track, { x: () => -dist(), ease: "none", scrollTrigger: { trigger: scene, start: "top top", end: "bottom bottom", scrub: 0.6, invalidateOnRefresh: true } });
  gsap.from(".look-card", { y: 60, opacity: 0, duration: 1.2, ease: "power3.out", stagger: 0.08, scrollTrigger: { trigger: scene, start: "top 70%" } });
}

// ---------- 07 safety: ranges drawn on the camera's full scale; counters ----------
function safety(data) {
  const r = data.ranges;
  const log2 = Math.log2;
  const rows = [
    { name: "ISO", val: `${r.IsoSensitivity.min_iso} – ${r.IsoSensitivity.max_iso}`, lo: 100, hi: 102400,
      a: r.IsoSensitivity.min_iso, b: r.IsoSensitivity.max_iso, f: log2, ends: ["100", "102,400"], note: "Always on" },
    { name: "Aperture", val: `f/${r.FNumber.min_f} – f/${r.FNumber.max_f}`, lo: 1.4, hi: 22, a: r.FNumber.min_f, b: r.FNumber.max_f,
      f: log2, ends: ["f/1.4", "f/22"], note: "Behind the exposure switch, off by default" },
    { name: "Shutter", val: r.ShutterSpeed.approved_range.replace(" (video only)", ""), lo: 1 / 8000, hi: 1 / 24,
      a: r.ShutterSpeed.min_seconds, b: r.ShutterSpeed.max_seconds, f: log2, ends: ["1/8000", "1/24"], note: "Video only · behind the exposure switch" },
    { name: "White balance", val: `${r.Colortemp.min_k}K – ${r.Colortemp.max_k}K`, lo: 2500, hi: 9900, a: r.Colortemp.min_k, b: r.Colortemp.max_k,
      f: (k) => k, ends: ["2500K", "9900K"], note: "Auto or Color Temp only; presets and Custom blocked" },
  ];
  const host = $("#ranges");
  for (const row of rows) {
    const p = (v) => ((row.f(v) - row.f(row.lo)) / (row.f(row.hi) - row.f(row.lo))) * 100;
    const d = document.createElement("div");
    d.className = "rg";
    d.innerHTML = `<div class="top"><span class="name"></span><span class="val"></span></div>
      <div class="scale"><i class="ok"></i></div><div class="ends"><span></span><span></span></div><p class="note"></p>`;
    d.querySelector(".name").textContent = row.name;
    d.querySelector(".val").textContent = row.val;
    const ok = d.querySelector(".ok");
    ok.style.left = p(row.a) + "%";
    ok.style.width = p(row.b) - p(row.a) + "%";
    const [e0, e1] = d.querySelectorAll(".ends span");
    e0.textContent = row.ends[0];
    e1.textContent = row.ends[1];
    d.querySelector(".note").textContent = row.note;
    host.append(d);
  }
  const get = (path) => path.split(".").reduce((o, k) => o?.[k], data);
  for (const dd of $$("[data-count]")) {
    const target = get(dd.dataset.count);
    if (!motion) { dd.textContent = target; continue; }
    const o = { v: 0 };
    gsap.to(o, { v: target, duration: 1.8, ease: "power3.out", onUpdate: () => (dd.textContent = Math.round(o.v)),
      scrollTrigger: { trigger: "#counters", start: "top 80%" } });
  }
  if (motion) {
    gsap.from(".rg .ok", { scaleX: 0, duration: 1.4, ease: "expo.out", stagger: 0.1, scrollTrigger: { trigger: "#ranges", start: "top 80%" } });
    gsap.from(".rule-col li", { y: 24, opacity: 0, duration: 1, ease: "power3.out", stagger: 0.05, scrollTrigger: { trigger: ".rules", start: "top 78%" } });
  }
}

// ---------- 08 dashboard ----------
function dashboard() {
  const img = $("#dash-img"), cap = $("#dash-cap");
  const shots = {
    auto: ["Auto: it sets ISO itself and says why.", "The Camera Agent dashboard in Auto, on the fake camera"],
    limit: ["A limit: “Light is warmer than your 2800K limit.”", "The dashboard showing an amber limit note"],
    falsecolor: ["False color and the 48 exposure regions, drawn by the agent.", "The dashboard with false color on"],
    locked: ["Locked: it holds everything now and only suggests.", "The dashboard locked"],
    killed: ["Kill switch: the agent stops and the bridge locks.", "The dashboard after the kill switch"],
  };
  for (const k of Object.keys(shots)) new Image().src = `media/screens/${k}.png`;
  for (const b of $$("#dash-seg button")) {
    b.addEventListener("click", () => {
      for (const o of $$("#dash-seg button")) o.setAttribute("aria-selected", String(o === b));
      img.classList.add("swap");
      setTimeout(() => {
        img.src = `media/screens/${b.dataset.shot}.png`;
        img.alt = shots[b.dataset.shot][1];
        cap.textContent = shots[b.dataset.shot][0];
        img.decode().catch(() => {}).then(() => img.classList.remove("swap"));
      }, 220);
    });
  }
  if (!motion) return;
  gsap.fromTo("#device", { rotateX: 22, scale: 0.86, y: 40 }, { rotateX: 0, scale: 1, y: 0, ease: "power2.out",
    scrollTrigger: { trigger: ".device-wrap", start: "top 95%", end: "top 25%", scrub: 0.6 } });
}

// ---------- headings and paragraphs slide up as they arrive ----------
function entrances() {
  const els = $$(".how-head > *, .replay-head > *, .sheet-head > *, .dash-head > *, .proof-inner > *, .next-grid > div > *, .tiles > div, .features li, .chart-card, .stats, .big-stats div");
  els.forEach((e) => e.setAttribute("data-up", ""));
  const io = new IntersectionObserver((es) => {
    for (const e of es) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.1 });
  els.forEach((e, i) => {
    const sib = [...e.parentElement.children].indexOf(e);
    e.style.transitionDelay = Math.min(sib, 6) * 90 + "ms";
    io.observe(e);
  });
}

// ---------- 11 close ----------
function closeScene() {
  const cta = $("#cta");
  cta.addEventListener("click", (e) => e.preventDefault());
  if (!motion) return;
  const split = new SplitText("#close-title", { type: "words,chars", mask: "chars" });
  gsap.from(split.chars, { yPercent: 110, duration: 1.4, ease: "expo.out", stagger: 0.035, scrollTrigger: { trigger: "#close-title", start: "top 72%" } });
  if (!fine) return;
  const xTo = gsap.quickTo(cta, "x", { duration: 0.8, ease: "power3.out" }), yTo = gsap.quickTo(cta, "y", { duration: 0.8, ease: "power3.out" });
  addEventListener("pointermove", (e) => {
    const r = cta.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
    const near = Math.hypot(dx, dy) < 320;
    xTo(near ? dx * 0.35 : 0);
    yTo(near ? dy * 0.35 : 0);
  });
}

// ---------- cursor: an AF frame that locks on (teal) over anything you can click ----------
function cursor() {
  if (!fine) return;
  const af = $("#af");
  let mx = innerWidth / 2, my = innerHeight / 2, x = mx, y = my;
  addEventListener("pointermove", (e) => { mx = e.clientX; my = e.clientY; });
  gsap.ticker.add(() => {
    x += (mx - x) * 0.22;
    y += (my - y) * 0.22;
    af.style.transform = `translate(${x}px, ${y}px)`;
  });
  document.addEventListener("pointerover", (e) => af.classList.toggle("lock", !!e.target.closest("a, button, .look-card, .chart svg")));
}

// ---------- videos only play while they're on screen ----------
function videos() {
  const vids = $$("video.bg");
  if (!motion) { vids.forEach((v) => v.removeAttribute("autoplay")); return; }
  const io = new IntersectionObserver((es) => {
    for (const e of es) {
      const v = e.target;
      if (e.isIntersecting) { if (v.preload === "none") v.preload = "auto"; v.play().catch(() => {}); }
      else v.pause();
    }
  }, { threshold: 0.05 });
  vids.forEach((v) => io.observe(v));
}
