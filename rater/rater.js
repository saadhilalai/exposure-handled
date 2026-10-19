/* Rater page: shows this rater's scenes in their own order, collects one pick and three ratings
   per scene. The page only knows A, B and C, never which method made which clip. */
"use strict";
const $ = (id) => document.getElementById(id);
const token = location.pathname.split("/")[2];
let sets = [], index = 0, best = null, ratings = {};

function show(id) { for (const s of document.querySelectorAll(".screen")) s.hidden = s.id !== id; window.scrollTo(0, 0); }
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

function progress() {
  const done = sets.filter((s) => s.done).length;
  $("progress-bar").style.width = (sets.length ? done / sets.length * 100 : 0) + "%";
  $("progress-text").textContent = sets.length ? done + " / " + sets.length : "";
}

function radio(container, values, onPick, current) {
  container.replaceChildren(...values.map((v) => {
    const b = el("button", "", String(v));
    b.type = "button"; b.setAttribute("role", "radio"); b.setAttribute("aria-checked", String(v === current));
    b.addEventListener("click", () => { onPick(v); for (const o of container.children) o.setAttribute("aria-checked", String(o === b)); check(); });
    return b;
  }));
}

function check() {
  $("next").disabled = !(best && ["A", "B", "C"].every((l) => ratings[l]));
}

function openScene() {
  index = sets.findIndex((s) => !s.done);
  if (index < 0) { show("done"); progress(); return; }
  const s = sets[index];
  best = null; ratings = {};
  $("scene-title").textContent = "Scene " + (index + 1) + " of " + sets.length;
  $("clips").replaceChildren(...s.labels.map((l) => {
    const box = el("div", "clip");
    const v = el("video");
    v.src = "/clip/" + token + "/" + encodeURIComponent(s.id) + "/" + l;
    v.controls = true; v.muted = true; v.playsInline = true; v.preload = "metadata"; v.setAttribute("playsinline", "");
    box.append(v, el("span", "tag", l));
    return box;
  }));
  radio($("best"), ["A", "B", "C"], (v) => { best = v; }, null);
  $("ratings").replaceChildren(...["A", "B", "C"].map((l) => {
    const row = el("div", "rate-row");
    const scale = el("div", "scale");
    scale.setAttribute("role", "radiogroup"); scale.setAttribute("aria-label", "Rating for " + l);
    radio(scale, [1, 2, 3, 4, 5], (v) => { ratings[l] = v; }, null);
    row.append(el("span", "who", l), scale);
    return row;
  }));
  $("error").hidden = true;
  check(); progress(); show("scene");
}

$("play-all").addEventListener("click", () => {
  for (const v of $("clips").querySelectorAll("video")) { v.currentTime = 0; v.play().catch(() => {}); }
});

$("next").addEventListener("click", async () => {
  $("next").disabled = true;
  const r = await fetch("/api/" + token + "/answer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ set: sets[index].id, best: best, ratings: ratings }),
  }).catch(() => null);
  if (!r || !r.ok) { $("error").textContent = "Couldn't save that. Check your connection and press Next again."; $("error").hidden = false; check(); return; }
  for (const v of $("clips").querySelectorAll("video")) v.pause();
  sets[index].done = true;
  openScene();
});

$("start").addEventListener("click", openScene);

fetch("/api/" + token + "/plan").then((r) => (r.ok ? r.json() : Promise.reject())).then((p) => {
  sets = p.sets;
  $("n-scenes").textContent = sets.length;
  progress();
  if (sets.some((s) => s.done)) openScene();
}).catch(() => show("bad"));
