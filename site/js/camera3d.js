// The backbone of the page: an original cinema camera, inspired by the FX2 (no maker's name, not a copy of any
// product), that comes apart into an exploded view as you scroll. Inside, a crew of tiny orange agents works:
// they swarm the sensor for ISO, crank the iris for aperture, repaint the colour chip for white balance, and
// freeze the instant the kill switch is pressed. At the end the camera snaps back together.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { BokehPass } from "three/addons/postprocessing/BokehPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

const AI = new THREE.Color(1.0, 0.42, 0.1);

// ---------- small seeded random, so the camera is the same on every visit ----------
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

// ---------- procedural textures ----------
function canvasTex(w, h, draw, srgb = true) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}
const knurlNormal = () => {
  const t = canvasTex(256, 16, (x, w, h) => {
    for (let i = 0; i < w; i++) { const n = Math.sin((i / w) * Math.PI * 2 * 16); x.fillStyle = `rgb(${128 + n * 110},128,${200 + Math.abs(n) * 55})`; x.fillRect(i, 0, 1, h); }
  }, false);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
};
const grainRough = () => {
  const t = canvasTex(256, 256, (x, w, h) => {
    const r = rng(7), img = x.createImageData(w, h);
    for (let i = 0; i < img.data.length; i += 4) { const v = 150 + r() * 70; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
    x.putImageData(img, 0, 0);
  }, false);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(4, 4); return t;
};
const pcbTex = () => canvasTex(1024, 600, (x, w, h) => {
  const r = rng(42);
  x.fillStyle = "#0a0e0c"; x.fillRect(0, 0, w, h);
  x.strokeStyle = "rgba(201,162,78,.75)"; x.lineCap = "round";
  for (let i = 0; i < 170; i++) {
    let px = r() * w, py = r() * h; x.lineWidth = r() < 0.2 ? 3 : 1.4; x.beginPath(); x.moveTo(px, py);
    for (let k = 0; k < 4; k++) { if (r() < 0.5) px += (r() - 0.5) * 260; else py += (r() - 0.5) * 200; x.lineTo(px, py); }
    x.stroke();
    x.fillStyle = "rgba(220,180,90,.9)"; x.beginPath(); x.arc(px, py, 3.2, 0, 7); x.fill();
  }
  for (let i = 0; i < 260; i++) { x.fillStyle = "rgba(210,170,80,.8)"; x.fillRect(r() * w, r() * h, 6, 3); }
  x.fillStyle = "rgba(235,235,230,.55)"; x.font = "bold 22px D-DIN, Helvetica, Arial"; x.fillText("S4D · CAMERA AGENT · REV 4", 40, h - 34);
  x.font = "14px D-DIN, Helvetica, Arial"; x.fillText("AI CORE", w * 0.47, h * 0.36); x.fillText("COLOUR", w * 0.78, h * 0.12);
  x.strokeStyle = "rgba(235,235,230,.35)"; x.lineWidth = 2; x.strokeRect(12, 12, w - 24, h - 24);
});
const sensorTex = () => canvasTex(512, 342, (x, w, h) => {
  const g = x.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, "#2a2140"); g.addColorStop(0.5, "#1b2a3a"); g.addColorStop(1, "#3a2030");
  x.fillStyle = g; x.fillRect(0, 0, w, h);
  x.globalAlpha = 0.35;
  for (let i = 0; i < w; i += 3) { x.fillStyle = i % 6 ? "#5a4a80" : "#3a6a7a"; x.fillRect(i, 0, 1, h); }
  for (let j = 0; j < h; j += 3) { x.fillStyle = j % 6 ? "#7a3a5a" : "#2a5a4a"; x.fillRect(0, j, w, 1); }
  x.globalAlpha = 1;
});
const labelTex = (lines, bg = "#18191b", fg = "rgba(230,230,226,.8)", w = 512, h = 256) => canvasTex(w, h, (x) => {
  x.fillStyle = bg; x.fillRect(0, 0, w, h);
  lines.forEach(([txt, size, y, color, weight]) => { x.fillStyle = color || fg; x.font = `${weight || 700} ${size}px D-DIN, Helvetica, Arial`; x.fillText(txt, 36, y); });
});

// rounded rectangle shape (centered)
function rrShape(w, h, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}
function rrPath(cx, cy, w, h, r) {
  const p = new THREE.Path(), x = cx - w / 2, y = cy - h / 2;
  p.moveTo(x + r, y); p.lineTo(x + w - r, y); p.quadraticCurveTo(x + w, y, x + w, y + r);
  p.lineTo(x + w, y + h - r); p.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  p.lineTo(x + r, y + h); p.quadraticCurveTo(x, y + h, x, y + h - r);
  p.lineTo(x, y + r); p.quadraticCurveTo(x, y, x + r, y);
  return p;
}
const extrude = (shape, depth, bevel = 0.02, seg = 3) =>
  new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: seg, curveSegments: 18 });

// ---------- the camera ----------
export function createCamera3D(canvas, { low = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !low, alpha: false, powerPreference: "high-performance" });
  renderer.setClearColor(0x050505, 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const dpr = Math.min(window.devicePixelRatio || 1, low ? 1.25 : 1.6);
  renderer.setPixelRatio(dpr);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.6;

  const cam = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
  const key = new THREE.DirectionalLight(0xfff1e2, 2.4); key.position.set(-4, 6, 5); scene.add(key);
  const fill = new THREE.DirectionalLight(0xbcd2ff, 0.5); fill.position.set(5, 1, 4); scene.add(fill);
  const rimCool = new THREE.DirectionalLight(0x9fc4ff, 2.2); rimCool.position.set(5, 3, -6); scene.add(rimCool);
  const rimWarm = new THREE.DirectionalLight(0xff7a2a, 0.45); rimWarm.position.set(-6, -2, -3); scene.add(rimWarm);
  const swarmLight = new THREE.PointLight(0xff6a1a, 0, 3.2, 1.6); scene.add(swarmLight);
  const sweep = new THREE.DirectionalLight(0xffffff, 0); sweep.position.set(-6, 2, 3); scene.add(sweep);

  const model = new THREE.Group(); scene.add(model);

  // materials
  const rough = grainRough(), knurl = knurlNormal();
  const M = {
    body: new THREE.MeshPhysicalMaterial({ color: 0x1c1d20, metalness: 0.55, roughness: 0.4, roughnessMap: rough, clearcoat: 0.3, clearcoatRoughness: 0.4 }),
    bodyInner: new THREE.MeshStandardMaterial({ color: 0x2a2b2e, metalness: 0.7, roughness: 0.45 }),
    rubber: new THREE.MeshStandardMaterial({ color: 0x0d0d0e, roughness: 0.85, metalness: 0, normalMap: knurl, normalScale: new THREE.Vector2(0.9, 0.9) }),
    rubberPlain: new THREE.MeshStandardMaterial({ color: 0x0e0e0f, roughness: 0.9 }),
    steel: new THREE.MeshStandardMaterial({ color: 0xdcdfe3, metalness: 1, roughness: 0.16 }),
    alu: new THREE.MeshStandardMaterial({ color: 0xb4b8bd, metalness: 1, roughness: 0.3 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x101112, metalness: 0.6, roughness: 0.35 }),
    glass: new THREE.MeshPhysicalMaterial({ color: 0x0e141c, metalness: 0, roughness: 0.02, transparent: true, opacity: 0.42, clearcoat: 1,
      iridescence: 1, iridescenceIOR: 1.75, iridescenceThicknessRange: [180, 560], envMapIntensity: 1.5, side: THREE.DoubleSide, depthWrite: false }),
    olpf: new THREE.MeshPhysicalMaterial({ color: 0x5ec8ff, metalness: 0, roughness: 0.05, transparent: true, opacity: 0.22, iridescence: 0.8,
      iridescenceIOR: 1.5, envMapIntensity: 2, side: THREE.DoubleSide, depthWrite: false }),
    sensor: new THREE.MeshPhysicalMaterial({ map: sensorTex(), metalness: 0.85, roughness: 0.14, iridescence: 1, iridescenceIOR: 2.2,
      iridescenceThicknessRange: [120, 900], emissive: new THREE.Color(1, 0.4, 0.1), emissiveIntensity: 0 }),
    gold: new THREE.MeshStandardMaterial({ color: 0xe2b462, metalness: 1, roughness: 0.28 }),
    ceramic: new THREE.MeshStandardMaterial({ color: 0x9d978b, roughness: 0.6 }),
    pcb: new THREE.MeshStandardMaterial({ map: pcbTex(), roughness: 0.5, metalness: 0.25 }),
    chip: new THREE.MeshStandardMaterial({ color: 0x141417, roughness: 0.42, metalness: 0.3 }),
    copper: new THREE.MeshStandardMaterial({ color: 0xc6834e, metalness: 1, roughness: 0.32 }),
    ai: new THREE.MeshStandardMaterial({ color: 0x2a1408, emissive: AI.clone(), emissiveIntensity: 2.4, roughness: 0.4 }),
    aiLine: new THREE.MeshStandardMaterial({ color: 0x2a1408, emissive: AI.clone(), emissiveIntensity: 1.15, roughness: 0.4 }),
    rec: new THREE.MeshStandardMaterial({ color: 0x5a0d0b, emissive: new THREE.Color(1, 0.18, 0.14), emissiveIntensity: 0.6, roughness: 0.4 }),
    battery: new THREE.MeshPhysicalMaterial({ map: labelTex([["S4D", 70, 110], ["7.2 V · 2280 mAh", 30, 170, "rgba(230,230,226,.55)", 400]]), roughness: 0.45, clearcoat: 0.5 }),
    card: new THREE.MeshStandardMaterial({ map: labelTex([["160 GB", 64, 120], ["MEMORY · TYPE A", 26, 178, "rgba(230,230,226,.55)", 400]], "#202124"), roughness: 0.4 }),
    label: new THREE.MeshStandardMaterial({ map: labelTex([["S4D", 120, 170, "rgba(220,220,216,.55)"]], "#1c1d20", undefined, 512, 256), metalness: 0.5, roughness: 0.4 }),
  };
  const lcdCanvas = document.createElement("canvas"); lcdCanvas.width = 640; lcdCanvas.height = 360;
  const lcdTex = new THREE.CanvasTexture(lcdCanvas); lcdTex.colorSpace = THREE.SRGBColorSpace;
  M.lcd = new THREE.MeshBasicMaterial({ map: lcdTex, toneMapped: false });

  // ---- parts: each has an assembled pose, an exploded offset, a delay, and work spots for the agents ----
  const parts = [];
  function part(name, { off = [0, 0, 0], rot = [0, 0, 0], delay = 0, spin = 0 } = {}) {
    const g = new THREE.Group(); g.name = name; model.add(g);
    const p = { name, g, off: new THREE.Vector3(...off), rot: new THREE.Euler(...rot), delay, spin, home: new THREE.Vector3(), spots: [] };
    parts.push(p); return p;
  }
  const add = (p, geo, mat, pos = [0, 0, 0], rot = [0, 0, 0], scale) => {
    const m = new THREE.Mesh(geo, mat); m.position.set(...pos); m.rotation.set(...rot); if (scale) m.scale.set(...scale);
    p.g.add(m); return m;
  };
  const spot = (p, kind, pos) => { const s = { part: p, kind, local: new THREE.Vector3(...pos), world: new THREE.Vector3() }; p.spots.push(s); return s; };

  const W = 1.3, H = 0.82, R = 0.09;
  const LX = 0.04, LY = -0.02;                       // lens axis

  // front housing with the lens opening
  {
    const p = part("frontHousing", { off: [0, 0, 1.05], delay: 0.16 });
    const s = rrShape(W, H, R); const hole = new THREE.Path(); hole.absarc(LX, LY, 0.27, 0, Math.PI * 2, true); s.holes.push(hole);
    add(p, extrude(s, 0.2, 0.024), M.body, [0, 0, 0.19]);
    add(p, new THREE.TorusGeometry(0.31, 0.012, 12, 72), M.steel, [LX, LY, 0.415]);
    // tally lamp + lens release button
    add(p, new THREE.CylinderGeometry(0.022, 0.022, 0.02, 24), M.rec, [0.52, 0.31, 0.42], [Math.PI / 2, 0, 0]);
    add(p, new THREE.CylinderGeometry(0.03, 0.03, 0.025, 24), M.alu, [0.42, -0.24, 0.42], [Math.PI / 2, 0, 0]);
    spot(p, "body", [0.5, 0.3, 0.44]);
  }
  // grip (operator's right hand)
  {
    const p = part("grip", { off: [-0.8, -0.05, 0.85], rot: [0, -0.35, 0], delay: 0.1 });
    add(p, new RoundedBoxGeometry(0.25, H * 0.97, 0.2, 5, 0.09), M.rubber, [-0.535, 0, 0.5]);
    add(p, new THREE.CylinderGeometry(0.05, 0.05, 0.03, 32), M.alu, [-0.53, H / 2 + 0.005, 0.5]);
  }
  // middle sleeve: corner rails stay; panels fly off
  {
    const p = part("rails", { off: [0, 0, 0], delay: 0 });
    for (const sx of [-1, 1]) for (const sy of [-1, 1]) add(p, new THREE.CylinderGeometry(R, R, 0.3, 24), M.body, [sx * (W / 2 - R), sy * (H / 2 - R), 0.02], [Math.PI / 2, 0, 0]);
  }
  for (const side of [1, -1]) {
    const p = part(side > 0 ? "panelLeft" : "panelRight", { off: [side * 1.2, 0.05, 0], rot: [0, 0, -side * 0.14], delay: 0.08 });
    const s = rrShape(0.3, H - 2 * R + 0.02, 0.01);
    for (let i = 0; i < 7; i++) s.holes.push(rrPath(0, -0.24 + i * 0.08, 0.2, 0.026, 0.012));
    const g = extrude(s, 0.03, 0.008, 2);
    add(p, g, M.body, [side * (W / 2 - 0.015), 0, 0.02], [0, side * Math.PI / 2, 0]);
    if (side > 0) {   // operator's left: ports
      add(p, new RoundedBoxGeometry(0.05, 0.06, 0.12, 2, 0.01), M.dark, [W / 2 + 0.01, 0.3, 0.02]);
      spot(p, "port", [W / 2 + 0.02, 0.3, 0.02]);
    } else {          // operator's right: card door + engraved mark
      add(p, new THREE.PlaneGeometry(0.22, 0.11), M.label, [-W / 2 - 0.02, 0.28, 0.02], [0, -Math.PI / 2, 0]);
    }
  }
  {
    const p = part("panelTop", { off: [0, 1.0, 0], rot: [0.1, 0, 0], delay: 0.05 });
    add(p, new RoundedBoxGeometry(W - 2 * R + 0.02, 0.03, 0.3, 2, 0.01), M.body, [0, H / 2 - 0.015, 0.02]);
    add(p, new THREE.CylinderGeometry(0.046, 0.046, 0.03, 32), M.rec, [-0.36, H / 2 + 0.01, -0.02]);
    const dial = add(p, new THREE.CylinderGeometry(0.06, 0.06, 0.045, 48), M.rubber, [-0.16, H / 2 + 0.02, -0.04]);
    p.dial = dial;
    spot(p, "dial", [-0.16, H / 2 + 0.06, -0.04]);
  }
  {
    const p = part("panelBottom", { off: [0, -0.95, 0], delay: 0.06 });
    add(p, new RoundedBoxGeometry(W - 2 * R + 0.02, 0.03, 0.3, 2, 0.01), M.body, [0, -H / 2 + 0.015, 0.02]);
    add(p, new THREE.CylinderGeometry(0.035, 0.035, 0.012, 24), M.alu, [LX, -H / 2 - 0.004, 0.02]);
  }
  // rear housing with screen and buttons
  {
    const p = part("rearHousing", { off: [0, 0, -1.3], delay: 0.15 });
    add(p, extrude(rrShape(W, H, R), 0.2, 0.024), M.body, [0, 0, -0.41]);
    for (let i = 0; i < 4; i++) add(p, new THREE.CylinderGeometry(0.026, 0.026, 0.02, 24), M.dark, [0.38 + (i % 2) * 0.11, 0.2 - Math.floor(i / 2) * 0.12, -0.44], [Math.PI / 2, 0, 0]);
    add(p, new THREE.CylinderGeometry(0.05, 0.05, 0.02, 32), M.rubber, [0.43, -0.2, -0.44], [Math.PI / 2, 0, 0]);
    spot(p, "body", [0.43, 0.2, -0.45]);
  }
  const lcdPart = part("lcd", { off: [0, 0.05, -1.85], rot: [0.12, 0, 0], delay: 0.2 });
  add(lcdPart, new RoundedBoxGeometry(0.7, 0.43, 0.035, 3, 0.02), M.dark, [-0.13, -0.02, -0.462]);
  const lcdMesh = add(lcdPart, new THREE.PlaneGeometry(0.64, 0.36), M.lcd, [-0.13, -0.02, -0.481], [0, Math.PI, 0]);
  [[-0.4, 0.1], [0.14, 0.1], [-0.4, -0.13], [0.14, -0.13]].forEach(([x, y]) => spot(lcdPart, "lcd", [x, y, -0.49]));
  // EVF on the operator's left, at the back
  {
    const p = part("evf", { off: [0.4, 1.3, -0.55], rot: [0, 0.3, 0], delay: 0.1 });
    add(p, new RoundedBoxGeometry(0.28, 0.16, 0.3, 4, 0.05), M.body, [0.42, H / 2 + 0.08, -0.26]);
    add(p, new RoundedBoxGeometry(0.22, 0.15, 0.08, 4, 0.05), M.rubberPlain, [0.42, H / 2 + 0.08, -0.44]);
    spot(p, "evf", [0.42, H / 2 + 0.17, -0.26]);
  }
  // top handle with two XLR inputs
  {
    const p = part("handle", { off: [0, 1.6, 0.15], rot: [-0.12, 0, 0], delay: 0 });
    add(p, new RoundedBoxGeometry(0.85, 0.09, 0.14, 4, 0.04), M.body, [-0.12, H / 2 + 0.24, 0.12]);
    add(p, new RoundedBoxGeometry(0.1, 0.2, 0.12, 3, 0.03), M.body, [-0.46, H / 2 + 0.1, 0.12]);
    add(p, new RoundedBoxGeometry(0.1, 0.2, 0.12, 3, 0.03), M.body, [0.18, H / 2 + 0.1, 0.12]);
    for (const x of [-0.26, -0.08]) { add(p, new THREE.CylinderGeometry(0.045, 0.045, 0.06, 32), M.alu, [x, H / 2 + 0.24, 0.2], [Math.PI / 2, 0, 0]); add(p, new THREE.CylinderGeometry(0.03, 0.03, 0.062, 24), M.dark, [x, H / 2 + 0.24, 0.2], [Math.PI / 2, 0, 0]); }
    spot(p, "audio", [-0.17, H / 2 + 0.3, 0.2]);
  }
  // battery (in the grip, drops out the bottom) + memory card (slides out the side)
  {
    const p = part("battery", { off: [-0.25, -1.55, 0.3], rot: [0.15, 0.2, 0], delay: 0.18 });
    add(p, new RoundedBoxGeometry(0.17, 0.4, 0.3, 3, 0.03), M.battery, [-0.52, -0.06, 0.12]);
    add(p, new THREE.BoxGeometry(0.1, 0.012, 0.08), M.gold, [-0.52, 0.145, 0.12]);
    spot(p, "power", [-0.52, 0.16, 0.12]);
  }
  {
    const p = part("card", { off: [-1.8, 0.3, -0.25], rot: [0, 0.6, 0.1], delay: 0.2 });
    add(p, new RoundedBoxGeometry(0.03, 0.2, 0.28, 2, 0.01), M.card, [-0.6, 0.12, -0.02]);
  }
  // fan + heatsink under the top panel
  const fanPart = part("fan", { off: [0, 0.6, 0], delay: 0.2 });
  {
    for (let i = 0; i < 18; i++) add(fanPart, new THREE.BoxGeometry(0.006, 0.08, 0.24), M.copper, [-0.45 + i * 0.035, 0.27, 0.0]);
    add(fanPart, new THREE.TorusGeometry(0.12, 0.012, 10, 48), M.dark, [0.32, 0.27, 0.0], [Math.PI / 2, 0, 0]);
    const rotor = new THREE.Group(); rotor.position.set(0.32, 0.27, 0.0); fanPart.g.add(rotor);
    for (let i = 0; i < 9; i++) { const b = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.006, 0.035), M.dark); b.position.set(Math.cos(i / 9 * 6.283) * 0.06, 0, Math.sin(i / 9 * 6.283) * 0.06); b.rotation.set(0.5, -i / 9 * 6.283, 0); rotor.add(b); }
    add(fanPart, new THREE.CylinderGeometry(0.035, 0.035, 0.02, 24), M.alu, [0.32, 0.27, 0.0]);
    fanPart.rotor = rotor;
    spot(fanPart, "fan", [0.32, 0.3, 0.0]); spot(fanPart, "fan", [-0.2, 0.32, 0.0]); spot(fanPart, "fan", [0.0, 0.32, 0.08]);
  }
  // main board: processor, the AI core (where the crew lives), and the colour chip
  const pcbPart = part("pcb", { off: [0, 0.26, -0.68], rot: [-0.08, 0, 0], delay: 0.22 });
  const chipTiles = [];
  {
    add(pcbPart, new THREE.BoxGeometry(1.12, 0.66, 0.016), M.pcb, [0, 0, -0.08]);
    add(pcbPart, new THREE.BoxGeometry(0.17, 0.17, 0.02), M.chip, [-0.18, 0.02, -0.06]);
    add(pcbPart, new THREE.BoxGeometry(0.13, 0.13, 0.008), M.alu, [-0.18, 0.02, -0.046]);
    for (let i = 0; i < 2; i++) add(pcbPart, new THREE.BoxGeometry(0.12, 0.06, 0.014), M.chip, [-0.42, 0.14 - i * 0.1, -0.065]);
    const core = add(pcbPart, new RoundedBoxGeometry(0.11, 0.11, 0.03, 2, 0.01), M.ai, [0.07, 0.1, -0.06]);
    pcbPart.core = core;
    const r = rng(9);
    for (let i = 0; i < 14; i++) add(pcbPart, new THREE.CylinderGeometry(0.012, 0.012, 0.03, 12), r() < 0.5 ? M.alu : M.dark, [-0.5 + r() * 1.0, -0.28 + r() * 0.15, -0.06], [Math.PI / 2, 0, 0]);
    add(pcbPart, new THREE.BoxGeometry(0.26, 0.04, 0.03), M.dark, [0.1, -0.29, -0.06]);
    // colour chip: 3 × 3 tiles the crew repaints
    for (let i = 0; i < 9; i++) {
      const mat = new THREE.MeshStandardMaterial({ color: 0x111111, emissive: new THREE.Color(1, 0.55, 0.2), emissiveIntensity: 0.55, roughness: 0.35 });
      const m = add(pcbPart, new RoundedBoxGeometry(0.036, 0.036, 0.012, 1, 0.004), mat, [0.33 + (i % 3) * 0.044, 0.2 - Math.floor(i / 3) * 0.044, -0.064]);
      chipTiles.push({ m, mat, paint: 0 });
      spot(pcbPart, "chip", [0.33 + (i % 3) * 0.044, 0.2 - Math.floor(i / 3) * 0.044, -0.05]).tile = i;
    }
    const chipDial = add(pcbPart, new THREE.CylinderGeometry(0.024, 0.024, 0.02, 24), M.alu, [0.5, 0.2, -0.06], [Math.PI / 2, 0, 0]);
    pcbPart.chipDial = chipDial;
    [[-0.18, 0.02], [-0.1, 0.1], [-0.26, -0.06], [0.07, 0.1], [0.07, 0.05], [-0.42, 0.14], [0.1, -0.28]].forEach(([x, y], i) => spot(pcbPart, i === 3 || i === 4 ? "core" : "pcb", [x, y, -0.04]));
  }
  // sensor: ceramic package, the iridescent die, and two tiny gain dials
  const sensorPart = part("sensor", { off: [0, 0, 0.32], delay: 0.3 });
  let sensorDie;
  {
    add(sensorPart, new THREE.BoxGeometry(0.62, 0.48, 0.02), M.dark, [LX, LY, 0.05]);
    for (const [x, y] of [[-0.27, 0.2], [0.35, 0.2], [-0.27, -0.24], [0.35, -0.24]]) add(sensorPart, new THREE.CylinderGeometry(0.012, 0.012, 0.05, 10), M.steel, [x, y, 0.07], [Math.PI / 2, 0, 0]);
    add(sensorPart, new RoundedBoxGeometry(0.54, 0.4, 0.035, 2, 0.01), M.ceramic, [LX, LY, 0.085]);
    add(sensorPart, new THREE.BoxGeometry(0.44, 0.3, 0.004), M.gold, [LX, LY, 0.104]);
    sensorDie = add(sensorPart, new THREE.PlaneGeometry(0.4, 0.267), M.sensor, [LX, LY, 0.107]);
    const d1 = add(sensorPart, new THREE.CylinderGeometry(0.026, 0.026, 0.022, 28), M.rubber, [LX + 0.22, LY + 0.165, 0.1], [Math.PI / 2, 0, 0]);
    const d2 = add(sensorPart, new THREE.CylinderGeometry(0.02, 0.02, 0.02, 28), M.alu, [LX - 0.22, LY + 0.165, 0.1], [Math.PI / 2, 0, 0]);
    sensorPart.dials = [d1, d2];
    for (let i = 0; i < 5; i++) for (let j = 0; j < 4; j++) spot(sensorPart, "sensor", [LX - 0.17 + i * 0.085, LY - 0.11 + j * 0.073, 0.112]);
    spot(sensorPart, "sensorDial", [LX + 0.22, LY + 0.165, 0.115]); spot(sensorPart, "sensorDial", [LX - 0.22, LY + 0.165, 0.115]);
  }
  {
    const p = part("olpf", { off: [0, 0, 0.64], delay: 0.28 });
    add(p, new THREE.PlaneGeometry(0.46, 0.33), M.olpf, [LX, LY, 0.14]);
    add(p, new THREE.BoxGeometry(0.48, 0.35, 0.006), M.dark, [LX, LY, 0.136]).scale.set(1, 1, 1);
    p.g.children[1].visible = false;
    spot(p, "sensor", [LX, LY + 0.17, 0.15]);
  }
  // lens mount, with the orange ring: the only colour on the outside
  {
    const p = part("mount", { off: [0, 0, 1.55], delay: 0.24 });
    add(p, new THREE.TorusGeometry(0.265, 0.03, 16, 80), M.steel, [LX, LY, 0.44]);
    for (let i = 0; i < 4; i++) { const a = i / 4 * Math.PI * 2 + 0.4; add(p, new THREE.BoxGeometry(0.09, 0.03, 0.02), M.steel, [LX + Math.cos(a) * 0.23, LY + Math.sin(a) * 0.23, 0.45], [0, 0, a + Math.PI / 2]); }
    add(p, new THREE.TorusGeometry(0.305, 0.006, 10, 96), M.aiLine, [LX, LY, 0.462]);
    for (let i = 0; i < 4; i++) { const a = i / 4 * Math.PI * 2; spot(p, "mount", [LX + Math.cos(a) * 0.27, LY + Math.sin(a) * 0.27, 0.47]); }
  }
  // lens: two barrel halves, glass elements and the iris
  const lensZ0 = 0.47;
  const barrelProfile = [[0.27, 0], [0.31, 0], [0.31, 0.08], [0.365, 0.1], [0.365, 0.16], [0.385, 0.17], [0.385, 0.4], [0.37, 0.41], [0.37, 0.5],
    [0.385, 0.51], [0.385, 0.72], [0.37, 0.73], [0.37, 0.92], [0.395, 0.95], [0.395, 1.0], [0.33, 1.0], [0.33, 0.96], [0.3, 0.95]].map(([r, z]) => new THREE.Vector2(r, z));
  const ringProfile = (z0, z1) => [[0.388, z0], [0.392, z0 + 0.01], [0.392, z1 - 0.01], [0.388, z1]].map(([r, z]) => new THREE.Vector2(r, z));
  for (const side of [0, 1]) {
    const p = part(side ? "barrelR" : "barrelL", { off: [side ? -0.85 : 0.85, 0.02, 2.55], rot: [0, side ? -0.3 : 0.3, 0], delay: 0.26 });
    const phi0 = side ? Math.PI : 0;
    const mk = (prof, mat) => { const g = new THREE.LatheGeometry(prof, 64, phi0, Math.PI); const m = add(p, g, mat, [LX, LY, lensZ0], [Math.PI / 2, 0, 0]); return m; };
    mk(barrelProfile, M.body);
    const k1 = mk(ringProfile(0.18, 0.39), M.rubber), k2 = mk(ringProfile(0.52, 0.71), M.rubber);
    for (const k of [k1, k2]) { k.material = M.rubber.clone(); k.material.normalMap = knurl.clone(); k.material.normalMap.repeat.set(26, 1); k.material.normalMap.needsUpdate = true; }
    const ai = new THREE.LatheGeometry([new THREE.Vector2(0.398, 0.955), new THREE.Vector2(0.398, 0.965)], 64, phi0, Math.PI);
    add(p, ai, M.aiLine, [LX, LY, lensZ0], [Math.PI / 2, 0, 0]);
    spot(p, "lens", [LX + (side ? -0.39 : 0.39), LY, lensZ0 + 0.6]);
  }
  const lensProfile = (rad, t) => { const pts = []; for (let i = 0; i <= 12; i++) { const r = (i / 12) * rad; pts.push(new THREE.Vector2(r, t * (1 - (r / rad) ** 2) + 0.006)); } for (let i = 12; i >= 0; i--) { const r = (i / 12) * rad; pts.push(new THREE.Vector2(r, -t * 0.7 * (1 - (r / rad) ** 2) - 0.006)); } return pts; };
  const elements = [[0.62, 0.22, 0.02, 1.95], [0.8, 0.2, 0.025, 2.3], [1.05, 0.23, 0.03, 3.05], [1.25, 0.27, 0.035, 3.35], [1.4, 0.31, 0.04, 3.75]];
  elements.forEach(([z, rad, t, ex], i) => {
    const p = part("element" + i, { off: [0, 0, ex], delay: 0.3 + i * 0.02 });
    add(p, new THREE.LatheGeometry(lensProfile(rad, t), 48), M.glass, [LX, LY, z], [Math.PI / 2, 0, 0]);
    add(p, new THREE.TorusGeometry(rad, 0.008, 8, 64), M.dark, [LX, LY, z]);
    spot(p, "glass", [LX + rad, LY, z]); spot(p, "glass", [LX - rad * 0.7, LY + rad * 0.7, z]);
  });
  // iris: 9 blades; their inner edges make the opening
  const irisPart = part("iris", { off: [0, 0, 2.7], delay: 0.32 });
  const blades = [];
  {
    const ringZ = 0.92;
    add(irisPart, new THREE.TorusGeometry(0.255, 0.02, 12, 80), M.dark, [LX, LY, ringZ]);
    const lever = add(irisPart, new THREE.BoxGeometry(0.03, 0.09, 0.02), M.ai, [LX, LY + 0.3, ringZ]);
    irisPart.lever = lever;
    const shape = new THREE.Shape();
    shape.moveTo(0, -0.16); shape.lineTo(0.0, 0.16); shape.quadraticCurveTo(0.17, 0.2, 0.3, 0.05); shape.lineTo(0.3, -0.12); shape.quadraticCurveTo(0.15, -0.2, 0, -0.16);
    const bg = new THREE.ExtrudeGeometry(shape, { depth: 0.004, bevelEnabled: false, curveSegments: 10 });
    const bladeMat = new THREE.MeshStandardMaterial({ color: 0x1a1a1c, metalness: 0.8, roughness: 0.3 });
    for (let i = 0; i < 9; i++) {
      const piv = new THREE.Group(); piv.position.set(LX, LY, ringZ + (i % 2 ? 0.003 : -0.003)); piv.rotation.z = (i / 9) * Math.PI * 2;
      const b = new THREE.Mesh(bg, bladeMat); piv.add(b); irisPart.g.add(piv); blades.push({ piv, b });
    }
    for (let i = 0; i < 9; i++) { const a = (i / 9) * Math.PI * 2; spot(irisPart, "iris", [LX + Math.cos(a) * 0.22, LY + Math.sin(a) * 0.22, ringZ + 0.012]); }
    spot(irisPart, "irisLever", [LX, LY + 0.3, ringZ + 0.02]);
  }
  function setIris(fnum) {
    const a = THREE.MathUtils.clamp(0.165 * (2.8 / fnum), 0.018, 0.2);    // opening apothem
    blades.forEach(({ b }) => { b.position.set(a, 0, 0); b.scale.set((0.25 - a) / 0.3, 0.75, 1); b.rotation.z = 0.18 + (0.165 - a) * 1.2; });
    irisPart.lever.rotation.z = (a - 0.165) * 3;
  }
  // screws: tiny, and they fly further than their panel
  const screwGeo = new THREE.CylinderGeometry(0.014, 0.014, 0.01, 16);
  [["frontHousing", [[-0.55, 0.33, 0.44], [0.55, 0.33, 0.44], [-0.55, -0.33, 0.44], [0.55, -0.33, 0.44]]],
   ["rearHousing", [[-0.55, 0.33, -0.44], [0.55, 0.33, -0.44], [-0.55, -0.33, -0.44], [0.55, -0.33, -0.44]]],
   ["panelTop", [[-0.4, H / 2 + 0.005, 0.1], [0.4, H / 2 + 0.005, 0.1], [-0.4, H / 2 + 0.005, -0.06], [0.4, H / 2 + 0.005, -0.06]]]].forEach(([owner, list]) => {
    const o = parts.find((p) => p.name === owner);
    list.forEach((pos, i) => {
      const p = part("screw", { off: o.off.clone().multiplyScalar(1.3).add(new THREE.Vector3((i % 2 ? 1 : -1) * 0.15, (i < 2 ? 1 : -1) * 0.12, 0)).toArray(), delay: o.delay, spin: 7 });
      const rotX = owner === "panelTop" ? 0 : Math.PI / 2;
      add(p, screwGeo, M.steel, pos, [rotX, 0, 0]);
      p.g.children[0].position.set(0, 0, 0); p.g.position.set(...pos); p.homePos = new THREE.Vector3(...pos);
      p.g.children[0].rotation.set(rotX, 0, 0);
    });
  });
  parts.forEach((p) => { if (!p.homePos) p.homePos = new THREE.Vector3(); });

  // ---------- the crew ----------
  const N = low ? 150 : 380;
  const allSpots = parts.flatMap((p) => p.spots);
  const byKind = {};
  allSpots.forEach((s) => (byKind[s.kind] ||= []).push(s));
  const agentGeo = new THREE.BufferGeometry();
  const pos = new Float32Array(N * 3), size = new Float32Array(N), hot = new Float32Array(N);
  agentGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  agentGeo.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
  agentGeo.setAttribute("aHot", new THREE.BufferAttribute(hot, 1));
  const agentMat = new THREE.ShaderMaterial({
    uniforms: { uScale: { value: 300 }, uAlpha: { value: 0 }, uFreeze: { value: 0 } },
    vertexShader: `attribute float aSize; attribute float aHot; uniform float uScale; varying float vHot;
      void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.); gl_Position = projectionMatrix * mv; gl_PointSize = aSize * uScale / -mv.z; vHot = aHot; }`,
    fragmentShader: `uniform float uAlpha, uFreeze; varying float vHot;
      void main(){ vec2 d = gl_PointCoord - .5; float r = length(d); if (r > .5) discard;
        float core = smoothstep(.16, .0, r); float glow = exp(-r * r * 30.);
        vec3 col = mix(vec3(1., .38, .08), vec3(1., .86, .62), clamp(core * .7 + vHot * .5, 0., 1.)) * (glow * 1.6 + core * 4.5);
        col = mix(col, vec3(.95, .28, .22) * (glow * .9 + core * 1.6), uFreeze);
        gl_FragColor = vec4(col * uAlpha, 1.); }`,
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  });
  const agentPts = new THREE.Points(agentGeo, agentMat); agentPts.frustumCulled = false; model.add(agentPts);
  const streakGeo = new THREE.BufferGeometry();
  const spos = new Float32Array(N * 6), scol = new Float32Array(N * 6);
  streakGeo.setAttribute("position", new THREE.BufferAttribute(spos, 3));
  streakGeo.setAttribute("color", new THREE.BufferAttribute(scol, 3));
  const streakMat = new THREE.LineBasicMaterial({ vertexColors: true, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false });
  const streaks = new THREE.LineSegments(streakGeo, streakMat); streaks.frustumCulled = false; model.add(streaks);

  const R0 = rng(1234);
  const A = Array.from({ length: N }, (_, i) => ({
    p: new THREE.Vector3(), prev: new THREE.Vector3(), s: new THREE.Vector3(), c: new THREE.Vector3(),
    spot: null, from: null, t: 0, dur: 0.5, work: 0, state: 0, speed: 6 + R0() * 9, courier: R0() < 0.22,
    phase: R0() * 6.28, orbit: 0.012 + R0() * 0.03, size: 0.034 + R0() * 0.022,
  }));

  // ---------- state, driven by the page ----------
  const S = {
    explode: 0, yaw: Math.PI, pitch: 0.0, dist: 6.2, frameX: 0, frameY: 0, lift: 0, tx: 0, ty: 0, tz: 0,
    fnum: 2.8, focus: "body", mode: "idle", agents: 0, chipGoal: 0, sensorGain: 0, snap: 0, turntable: 0,
  };
  const D = { ...S };            // damped copies
  let frozen = false, freezeT = 0;

  function weightsFor(mode) {
    switch (mode) {
      case "iso": return { sensor: 7, sensorDial: 3, pcb: 1, core: 1, glass: 0.3, lcd: 0.3 };
      case "iris": return { iris: 8, irisLever: 3, glass: 1, mount: 0.4, core: 0.3 };
      case "wb": return { chip: 9, core: 1, pcb: 0.6, lcd: 0.4 };
      case "home": return { core: 1 };
      default: return { sensor: 2, sensorDial: 0.6, pcb: 2, core: 1.5, chip: 1, iris: 1.4, irisLever: 0.4, glass: 1.4, mount: 0.8, lcd: 1, fan: 0.8, dial: 0.4, port: 0.5, power: 0.5, evf: 0.4, audio: 0.4, body: 0.5 };
    }
  }
  function pick(mode, a) {
    const w = weightsFor(mode);
    if (a.courier && mode === "idle") {      // couriers carry frames: sensor → core → somewhere that acts on it
      const route = a.spot?.kind === "sensor" ? ["core", "pcb"] : a.spot?.kind === "core" || a.spot?.kind === "pcb" ? ["iris", "chip", "lcd", "sensorDial"] : ["sensor"];
      const k = route[Math.floor(R0() * route.length)];
      const list = byKind[k]; if (list) return list[Math.floor(R0() * list.length)];
    }
    let tot = 0; for (const k in w) if (byKind[k]) tot += w[k];
    let r = R0() * tot;
    for (const k in w) { if (!byKind[k]) continue; r -= w[k]; if (r <= 0) { const list = byKind[k]; return list[Math.floor(R0() * list.length)]; } }
    return allSpots[0];
  }

  function placeParts(e) {
    const tmpE = new THREE.Euler();
    parts.forEach((p) => {
      const k = THREE.MathUtils.clamp((e - p.delay) / (1 - 0.35), 0, 1);
      const ease = k < 0.5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2;
      p.g.position.copy(p.homePos).addScaledVector(p.off, ease);
      tmpE.set(p.rot.x * ease, p.rot.y * ease, p.rot.z * ease);
      p.g.rotation.copy(tmpE);
      if (p.spin) p.g.children[0].rotation.z = ease * p.spin;
      p.g.updateMatrix();
    });
  }
  function updateSpots() { allSpots.forEach((s) => s.world.copy(s.local).applyMatrix4(s.part.g.matrix)); }

  const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();
  let activity = { sensor: 0, iris: 0, chip: 0 };
  function updateAgents(dt, time) {
    const vis = D.agents;
    agentMat.uniforms.uAlpha.value = vis;
    streaks.visible = agentPts.visible = vis > 0.01;
    if (vis <= 0.01) { A.forEach((a) => { a.spot = null; }); return; }
    if (frozen) { agentMat.uniforms.uFreeze.value = Math.min(1, agentMat.uniforms.uFreeze.value + dt * 12); return; }
    agentMat.uniforms.uFreeze.value = Math.max(0, agentMat.uniforms.uFreeze.value - dt * 3);
    activity = { sensor: 0, iris: 0, chip: 0 };
    const centroid = new THREE.Vector3(); let nc = 0;
    const mode = S.mode;
    A.forEach((a, i) => {
      if (!a.spot) {      // spawn from the AI core
        const core = byKind.core[i % byKind.core.length];
        a.p.copy(core.world); a.prev.copy(a.p); a.from = core; a.spot = pick(mode, a); a.state = 0; a.t = 0;
        a.s.copy(a.p); a.dur = 0.25 + R0() * 0.5; a.c.set((R0() - 0.5) * 1.4, R0() * 1.2, (R0() - 0.5) * 1.4);
      }
      a.prev.copy(a.p);
      if (a.state === 0) {            // flying along an arc
        a.t += dt / a.dur;
        const e = a.spot.world;
        if (a.t >= 1) { a.state = 1; a.work = 0.18 + R0() * (mode === "idle" ? 0.7 : 1.3); a.p.copy(e); }
        else {
          const t = a.t, u = 1 - t;
          tmp.copy(a.s).add(e).multiplyScalar(0.5).add(a.c);
          a.p.set(u * u * a.s.x + 2 * u * t * tmp.x + t * t * e.x, u * u * a.s.y + 2 * u * t * tmp.y + t * t * e.y, u * u * a.s.z + 2 * u * t * tmp.z + t * t * e.z);
        }
      } else {                        // working: buzzing in a tiny orbit on the spot
        a.work -= dt;
        const e = a.spot.world, w = time * (18 + a.speed) + a.phase;
        a.p.set(e.x + Math.cos(w) * a.orbit, e.y + Math.sin(w * 1.3) * a.orbit, e.z + Math.sin(w) * a.orbit * 0.6);
        const k = a.spot.kind;
        if (k === "sensor" || k === "sensorDial") activity.sensor++;
        if (k === "iris" || k === "irisLever") activity.iris++;
        if (k === "chip") { activity.chip++; const tile = chipTiles[a.spot.tile ?? 0]; if (tile) tile.paint += (S.chipGoal - tile.paint) * Math.min(1, dt * 2.2); }
        if (a.work <= 0) {
          const next = mode === "home" ? byKind.core[0] : pick(mode, a);
          a.from = a.spot; a.spot = next; a.s.copy(a.p); a.state = 0; a.t = 0;
          const dist = a.s.distanceTo(next.world);
          a.dur = Math.max(0.12, dist / a.speed) * (mode === "home" ? 0.8 : 1);
          tmp2.set(R0() - 0.5, R0() * 0.8 + 0.1, R0() - 0.5).normalize().multiplyScalar(dist * (0.2 + R0() * 0.35));
          a.c.copy(tmp2);
        }
      }
      if (S.mode === "home" && a.spot.kind === "core" && a.state === 1) a.hidden = true; else a.hidden = false;
      centroid.add(a.p); nc++;
    });
    swarmLight.position.copy(centroid.multiplyScalar(1 / Math.max(nc, 1))).applyMatrix4(model.matrixWorld);
    swarmLight.intensity = 3.5 * vis;
  }
  function writeAgents(dt) {
    const fz = agentMat.uniforms.uFreeze.value;
    A.forEach((a, i) => {
      pos[i * 3] = a.p.x; pos[i * 3 + 1] = a.p.y; pos[i * 3 + 2] = a.p.z;
      size[i] = a.hidden ? 0 : a.size * (a.courier ? 1.5 : 1);
      hot[i] = a.courier ? 1 : 0;
      if (!frozen) {
        const vx = (a.p.x - a.prev.x), vy = (a.p.y - a.prev.y), vz = (a.p.z - a.prev.z);
        const k = 1.3;   // short streak: about one frame of travel
        spos[i * 6] = a.p.x; spos[i * 6 + 1] = a.p.y; spos[i * 6 + 2] = a.p.z;
        spos[i * 6 + 3] = a.p.x - vx * k; spos[i * 6 + 4] = a.p.y - vy * k; spos[i * 6 + 5] = a.p.z - vz * k;
      }
      const v = a.hidden ? 0 : D.agents;
      const r = 1.0 * (1 - fz) + 0.9 * fz, g = 0.45 * (1 - fz) + 0.25 * fz, b = 0.12 * (1 - fz) + 0.2 * fz;
      scol[i * 6] = r * 1.25 * v; scol[i * 6 + 1] = g * 1.25 * v; scol[i * 6 + 2] = b * 1.25 * v;
      scol[i * 6 + 3] = 0; scol[i * 6 + 4] = 0; scol[i * 6 + 5] = 0;
    });
    agentGeo.attributes.position.needsUpdate = true; agentGeo.attributes.aSize.needsUpdate = true; agentGeo.attributes.aHot.needsUpdate = true;
    streakGeo.attributes.position.needsUpdate = true; streakGeo.attributes.color.needsUpdate = true;
  }

  // ---------- post: depth of field (rack focus to whatever the story is about) + bloom for the crew ----------
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, cam));
  const bokeh = low ? null : new BokehPass(scene, cam, { focus: 6, aperture: 0.0016, maxblur: 0.0065 });
  if (bokeh) composer.addPass(bokeh);
  const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), low ? 0.5 : 0.55, 0.45, 1.25);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  // where a named thing sits when the camera is exploded by e (model space, rotations ignored)
  function anchor(name, e = 1) {
    const p = { sensor: sensorPart, iris: irisPart, chip: pcbPart, lcd: lcdPart }[name];
    if (!p) return new THREE.Vector3(0, 0.15 * e, 0.9 * e);
    const s = name === "chip" ? p.spots.find((x) => x.kind === "chip" && x.tile === 4) : name === "sensor" ? p.spots[7] : name === "lcd" ? null : p.spots[0];
    const local = s ? s.local.clone() : new THREE.Vector3(-0.13, -0.02, -0.47);
    if (name === "iris") local.set(0.04, -0.02, 0.92);
    return local.add(p.homePos).addScaledVector(p.off, e);
  }
  function focusPoint(name) {
    const p = name === "sensor" ? sensorPart : name === "iris" ? irisPart : name === "chip" ? pcbPart : name === "lcd" ? lcdPart : null;
    if (!p) return model.localToWorld(new THREE.Vector3(0, 0, D.explode * 0.8));
    const s = name === "chip" ? p.spots.find((x) => x.kind === "chip") : name === "sensor" ? p.spots[7] : p.spots[0];
    return model.localToWorld(s ? s.world.clone() : p.g.position.clone());
  }

  let W0 = 1, H0 = 1;
  function resize() {
    const w = canvas.clientWidth || innerWidth, h = canvas.clientHeight || innerHeight;
    if (w === W0 && h === H0) return;
    W0 = w; H0 = h;
    renderer.setSize(w, h, false); composer.setSize(w, h);
    cam.aspect = w / h; cam.updateProjectionMatrix();
    agentMat.uniforms.uScale.value = h * dpr * 0.5;
  }

  const clock = new THREE.Timer();
  let time = 0, running = false, raf = 0, focusDist = 6;
  const damp = (a, b, k, dt) => a + (b - a) * (1 - Math.exp(-k * dt));
  function frame() {
    raf = requestAnimationFrame(frame);
    clock.update(); const dt = Math.min(clock.getDelta(), 1 / 20);
    step(dt);
    composer.render(dt);
  }
  let spin = 0;
  function placeCamera() {
    const tgt = new THREE.Vector3(D.tx, D.ty + D.lift, D.tz);
    const yaw = D.yaw + spin;
    cam.position.set(tgt.x + Math.sin(yaw) * Math.cos(D.pitch) * D.dist, tgt.y + Math.sin(D.pitch) * D.dist, tgt.z + Math.cos(yaw) * Math.cos(D.pitch) * D.dist);
    cam.lookAt(tgt);
    cam.setViewOffset(W0, H0, -D.frameX * W0, -D.frameY * H0, W0, H0);
    placeParts(D.explode);
    model.updateMatrixWorld(true);
    cam.updateMatrixWorld(true);
  }
  function step(dt) {
    resize();
    if (!frozen) time += dt;
    for (const k of ["explode", "yaw", "pitch", "dist", "frameX", "frameY", "lift", "tx", "ty", "tz", "fnum", "agents", "sensorGain"]) D[k] = damp(D[k], S[k], k === "explode" ? 7 : 4.5, dt);
    if (S.snap) { D.explode = S.explode; }
    if (!frozen) spin += dt * S.turntable * 0.25;
    placeCamera();
    updateSpots();
    setIris(D.fnum);
    // spinning things, unless the kill switch froze them
    if (!frozen) {
      fanPart.rotor.rotation.y += dt * (5 + 18 * D.agents);
      sensorPart.dials[0].rotation.y += dt * activity.sensor * 0.05; sensorPart.dials[1].rotation.y -= dt * activity.sensor * 0.04;
      pcbPart.chipDial.rotation.y += dt * activity.chip * 0.06;
      blades.forEach(({ piv }) => (piv.userData.j = Math.sin(time * 40) * 0.002 * Math.min(activity.iris, 30) / 30));
    }
    chipTiles.forEach((t, i) => {
      if (!frozen && S.mode !== "wb") t.paint += (S.chipGoal - t.paint) * Math.min(1, dt * 0.8);
      const warm = new THREE.Color(1, 0.5, 0.16), cool = new THREE.Color(0.82, 0.9, 1.0);
      t.mat.emissive.copy(warm).lerp(cool, THREE.MathUtils.clamp(t.paint, 0, 1));
      t.mat.emissiveIntensity = 0.62 + 0.12 * Math.sin(time * 3 + i);
    });
    M.sensor.emissiveIntensity = D.sensorGain * (0.35 + 0.15 * Math.sin(time * 6));
    pcbPart.core.material.emissiveIntensity = 1.5 + Math.sin(time * 4) * 0.35;
    updateAgents(dt, time);
    writeAgents(dt);
    // rack focus
    if (bokeh) {
      const fp = focusPoint(S.focus);
      const d = cam.position.distanceTo(fp);
      focusDist = damp(focusDist, d, 4, dt);
      bokeh.uniforms.focus.value = focusDist;
      bokeh.uniforms.aperture.value = 0.0006 + 0.0013 * Math.min(1, D.explode * 1.5);
    }
    sweep.intensity = Math.max(0, sweep.intensity - dt * 3);
    lcdTex.needsUpdate = true;
  }

  // Screen rectangle of the rear screen (CSS pixels), for the "pull back from the viewfinder" move.
  function lcdRect() {
    resize(); placeCamera();
    const g = lcdMesh.geometry; g.computeBoundingBox();
    const bb = g.boundingBox, pts = [];
    for (const x of [bb.min.x, bb.max.x]) for (const y of [bb.min.y, bb.max.y]) {
      const v = new THREE.Vector3(x, y, 0).applyMatrix4(lcdMesh.matrixWorld).project(cam);
      pts.push([(v.x * 0.5 + 0.5) * W0, (-v.y * 0.5 + 0.5) * H0]);
    }
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    return { left: Math.min(...xs), top: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
  }

  return {
    state: S, lcdCanvas, anchor,
    start() { if (running) return; running = true; clock.update(); frame(); },
    stop() { running = false; cancelAnimationFrame(raf); },
    get running() { return running; },
    renderOnce() { resize(); step(1 / 60); composer.render(); },
    freeze(on) { frozen = on; freezeT = time; },
    get frozen() { return frozen; },
    flashSweep() { sweep.intensity = 6; },
    settle() { Object.assign(D, S); },
    lcdRect, resize,
    info: () => renderer.info,
  };
}
