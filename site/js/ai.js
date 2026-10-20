// The demo AI: a small copy of the agent's rules, for the simulator, the game and the hero.
// 180° shutter first, the iris only when ISO can't go lower, ISO to land the subject, protect highlights,
// then white balance to the light (kept warm at sunset). It never leaves the agent's approved ranges.
import { ISOS, SHUTTERS, FNUMS, KELVINS, SCENES } from "./sim.js";

export const TARGET = -0.4;                      // subject a little under middle grey, like a DP would expose
export const RANGES = { iso: [800, 12800], fnum: [2.8, 11], shutter: [1 / 100, 1 / 48], wb: [2800, 7500] };
export const LISTS = { iso: ISOS, shutter: SHUTTERS, fnum: FNUMS, wb: KELVINS };
const SH180 = 1 / 48;

export const fmt = {
  iso: (v) => String(v),
  shutter: (v) => "1/" + Math.round(1 / v),
  fnum: (v) => "f/" + v,
  wb: (v) => Math.round(v) + "K",
};
const nearestIdx = (list, v) => { let b = 0, d = Infinity; list.forEach((x, i) => { const e = Math.abs(Math.log(x / v)); if (e < d) { d = e; b = i; } }); return b; };
const snap = (list, v, lo = -Infinity, hi = Infinity) => list[nearestIdx(list.filter((x) => x >= lo - 1e-9 && x <= hi + 1e-9), v) + list.findIndex((x) => x >= lo - 1e-9)];
const st = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(1) + " st";

export function idealWB(sceneIdx) {
  const sc = SCENES[sceneIdx];
  if (sc.id === "sunset") return 4800;          // a DP keeps golden hour warm
  if (sc.id === "tungsten") return 3500;        // ...and a little warmth under tungsten
  return Math.min(RANGES.wb[1], Math.max(RANGES.wb[0], Math.round(sc.light / 100) * 100));
}
const LIGHT = { window: "Daylight", tungsten: "Tungsten. Keeping a little warmth", low: "Mixed street light", sunset: "Golden hour. Keeping it warm" };

export function solve(sim, sceneIdx, start) {
  const s = { ...start };
  const m0 = sim.meter(sceneIdx, s);
  const t = { ...s, shutter: SH180 };
  // iris: wide open unless base ISO is still too bright
  const atBase = sim.meter(sceneIdx, { ...t, iso: 800, fnum: 2.8 });
  const excess = atBase.subject - TARGET;
  t.fnum = excess > 0.17 ? snap(FNUMS, 2.8 * 2 ** (excess / 2), ...RANGES.fnum) : 2.8;
  // ISO to land the subject
  const m1 = sim.meter(sceneIdx, { ...t, iso: 800 });
  t.iso = snap(ISOS, 800 * 2 ** (TARGET - m1.subject), ...RANGES.iso);
  // protect highlights: a third at a time
  let guard = 0;
  while (sim.meter(sceneIdx, t).clip > 0.012 && guard++ < 12) {
    const k = ISOS.indexOf(t.iso);
    if (t.iso > RANGES.iso[0]) t.iso = ISOS[k - 1];
    else if (t.fnum < RANGES.fnum[1]) t.fnum = FNUMS[FNUMS.indexOf(t.fnum) + 1];
    else break;
    if (sim.meter(sceneIdx, t).subject < TARGET - 0.8) break;
  }
  t.wb = idealWB(sceneIdx);
  const mf = sim.meter(sceneIdx, t);

  const steps = [];
  const assess = m0.clip > 0.03 ? `Subject <b>${st(m0.subject)}</b>. Highlights clipping.`
    : m0.subject > 0.7 ? `Subject <b>${st(m0.subject)}</b>. Too bright.`
    : m0.subject < -1.2 ? `Subject <b>${st(m0.subject)}</b>. Too dark.`
    : `Subject <b>${st(m0.subject)}</b>. Close. Tidying up.`;
  if (Math.abs(Math.log2(s.shutter / SH180)) > 0.05) steps.push({ key: "shutter", from: s.shutter, to: SH180, msg: `Shutter to 180°: <b>${fmt.shutter(s.shutter)} → 1/48</b>` });
  if (t.fnum !== s.fnum) steps.push({ key: "fnum", from: s.fnum, to: t.fnum, msg: t.fnum > s.fnum ? `Too bright for base ISO. Closing to <b>f/${t.fnum}</b>` : `Opening up to <b>f/${t.fnum}</b>` });
  if (t.iso !== s.iso) steps.push({ key: "iso", from: s.iso, to: t.iso, msg: `ISO <b>${s.iso} → ${t.iso}</b>${t.iso === 800 || t.iso === 12800 ? " (base ISO)" : ""}` });
  if (Math.abs(t.wb - s.wb) >= 100) steps.push({ key: "wb", from: s.wb, to: t.wb, msg: `${LIGHT[SCENES[sceneIdx].id]}. WB <b>${fmt.wb(s.wb)} → ${fmt.wb(t.wb)}</b>` });
  const maxed = t.iso >= RANGES.iso[1] && t.fnum <= 2.8 && mf.subject < TARGET - 0.3;
  const final = maxed ? { msg: `Max ISO, wide open: <b>${st(mf.subject)}</b>. Right for night.`, cls: "done" }
    : { msg: `Locked. Subject <b>${st(mf.subject)}</b>${mf.clip < 0.012 ? ", highlights safe" : ""}.`, cls: "done" };
  return { start: s, target: t, steps, assess, final, meterStart: m0, meterEnd: mf };
}

// 100 minus penalties; the same rules for you and for the AI
export function score(sim, sceneIdx, s) {
  const m = sim.meter(sceneIdx, s);
  const pen = [];
  const e = m.subject - TARGET;
  if (Math.abs(e) > 0.25) pen.push([Math.min(45, (Math.abs(e) - 0.25) * 24), e > 0 ? `${st(e)} over` : `${st(e)} under`]);
  if (m.clip > 0.004) pen.push([Math.min(30, m.clip * 400), "Clipped"]);
  const mired = 1e6 / s.wb - 1e6 / idealWB(sceneIdx);
  if (Math.abs(mired) > 15) pen.push([Math.min(25, (Math.abs(mired) - 15) * 0.16), mired > 0 ? "Too warm" : "Too cold"]);
  const sh = Math.log2(s.shutter / SH180);
  if (Math.abs(sh) > 0.35) pen.push([Math.min(20, (Math.abs(sh) - 0.35) * 9), sh > 0 ? "Smeared motion" : "Choppy motion"]);
  if (s.iso > 12800) pen.push([Math.log2(s.iso / 12800) * 8, "Noisy"]);
  const total = pen.reduce((a, [p]) => a + p, 0);
  const why = pen.filter(([p]) => p >= 3).sort((a, b) => b[0] - a[0]).slice(0, 2).map(([, w]) => w);
  return { score: Math.max(0, Math.round(100 - total)), why: why.length ? why : ["Nailed it"], meter: m };
}

// Walk one setting from → to, a detent at a time, so you can watch (and hear) the dial turn.
export async function turn(key, from, to, apply, { speed = 1, signal } = {}) {
  const list = LISTS[key];
  let i = nearestIdx(list, from);
  const j = nearestIdx(list, to);
  const dir = Math.sign(j - i);
  const per = { iso: 95, fnum: 120, shutter: 105, wb: 14 }[key] / speed;
  while (i !== j) {
    if (signal?.aborted) return;
    i += dir;
    apply(list[i], i);
    await new Promise((r) => setTimeout(r, per));
  }
  apply(list[j], j);
}
