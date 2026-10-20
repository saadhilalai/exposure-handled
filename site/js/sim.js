// A toy cinema camera: one made-up scene, seen the way a camera sees it.
// Exposure follows ISO × shutter / f-stop², the shutter smears the spinning reel, the f-stop sets depth of field
// (with real bokeh from the lights), white balance tints by colour temperature, high ISO adds noise, and highlights
// clip like a sensor does. Shown through a soft film-style display curve, or flat S-Log3, false colour or zebras.
// One WebGL2 context renders for every view on the page and copies into each view's own canvas.

const CLIP = 0.18 * 64;                       // sensor clips about 6 stops over middle grey
const FOCUS_M = 1.6, FOCAL_M = 0.085;         // focused on the reel, an 85 mm lens
export const BASE = { iso: 800, shutter: 1 / 48, fnum: 2.8 };

// ---------- the four lighting setups (scene units: middle grey under the key light is about 0.18) ----------
export const SCENES = [
  { id: "window", name: "Window light", keyK: 5800, key: 0.42, keyDir: [-0.92, 0.38], ambK: 6800, amb: 0.1,
    skyTopK: 8000, skyTop: 2.2, skyBotK: 6800, skyBot: 3.6, bldgK: 6500, bldg: 0.55, sunK: 5500, sun: 0, sunY: 0.5,
    city: 0, lampK: 2900, lamp: 0, lampLight: 0, string: 0.35, patchK: 5600, patch: 0.22, hazeK: 6000, haze: 0.05,
    correct: { iso: 800, shutter: 1 / 48, fnum: 4 }, light: 5800 },
  { id: "tungsten", name: "Tungsten", keyK: 3200, key: 0.66, keyDir: [0.9, 0.3], ambK: 4000, amb: 0.08,
    skyTopK: 11000, skyTop: 0.045, skyBotK: 8500, skyBot: 0.085, bldgK: 9000, bldg: 0.02, sunK: 5500, sun: 0, sunY: 0.5,
    city: 0.7, lampK: 2900, lamp: 2.4, lampLight: 1.0, string: 1.3, patchK: 5600, patch: 0, hazeK: 3200, haze: 0.0,
    correct: { iso: 3200, shutter: 1 / 48, fnum: 2.8 }, light: 3200 },
  { id: "low", name: "Low light", keyK: 4300, key: 0.5, keyDir: [-0.8, 0.5], ambK: 5200, amb: 0.04,
    skyTopK: 12000, skyTop: 0.008, skyBotK: 9000, skyBot: 0.022, bldgK: 8000, bldg: 0.005, sunK: 5500, sun: 0, sunY: 0.5,
    city: 2.2, lampK: 2900, lamp: 0, lampLight: 0, string: 0.95, patchK: 5600, patch: 0, hazeK: 4300, haze: 0.0,
    correct: { iso: 12800, shutter: 1 / 48, fnum: 2.8 }, light: 4300 },
  { id: "sunset", name: "Sunset", keyK: 3300, key: 0.85, keyDir: [-0.97, 0.12], ambK: 9500, amb: 0.06,
    skyTopK: 9000, skyTop: 1.1, skyBotK: 2500, skyBot: 4.8, bldgK: 4000, bldg: 0.12, sunK: 2400, sun: 90, sunY: 0.03,
    city: 0, lampK: 2900, lamp: 0, lampLight: 0, string: 0.45, patchK: 2900, patch: 1.7, hazeK: 2800, haze: 0.13,
    correct: { iso: 800, shutter: 1 / 48, fnum: 5.6 }, light: 3300 },
];

// ---------- light colour: a black body at K kelvin, in linear Rec.709, luminance 1 ----------
export function kelvinRGB(T) {
  T = Math.min(25000, Math.max(1667, T));
  const t = 1e3 / T, t2 = t * t, t3 = t2 * t;
  const x = T <= 4000 ? -0.2661239 * t3 - 0.2343589 * t2 + 0.8776956 * t + 0.17991
                      : -3.0258469 * t3 + 2.1070379 * t2 + 0.2226347 * t + 0.24039;
  const y = T <= 2222 ? -1.1063814 * x ** 3 - 1.3481102 * x ** 2 + 2.18555832 * x - 0.20219683
          : T <= 4000 ? -0.9549476 * x ** 3 - 1.37418593 * x ** 2 + 2.09137015 * x - 0.16748867
                      : 3.081758 * x ** 3 - 5.8733867 * x ** 2 + 3.75112997 * x - 0.37001483;
  const X = x / y, Y = 1, Z = (1 - x - y) / y;
  const r = 3.2406 * X - 1.5372 * Y - 0.4986 * Z, g = -0.9689 * X + 1.8758 * Y + 0.0415 * Z, b = 0.0557 * X - 0.204 * Y + 1.057 * Z;
  const c = [Math.max(r, 0), Math.max(g, 0), Math.max(b, 0)];
  const l = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  return c.map((v) => v / l);
}
const mul = (k, I) => kelvinRGB(k).map((v) => v * I);

// White balance like a camera: green stays put, red and blue are scaled so light at K comes out neutral.
export function wbGains(K) { const c = kelvinRGB(K); return [c[1] / c[0], 1, c[1] / c[2]]; }

export const gainOf = (s) => (s.iso / BASE.iso) * (s.shutter / BASE.shutter) * (BASE.fnum / s.fnum) ** 2;
export const stopsBetween = (a, b) => Math.log2(gainOf(a) / gainOf(b));

// ---------- the dial steps a cinema camera offers ----------
export const ISOS = [100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000,
  6400, 8000, 10000, 12800, 16000, 20000, 25600, 32000, 40000, 51200];
export const SHUTTERS = [8, 10, 13, 15, 20, 25, 30, 40, 48, 50, 60, 80, 100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600, 2000].map((d) => 1 / d);
export const FNUMS = [1.4, 1.6, 1.8, 2, 2.2, 2.5, 2.8, 3.2, 3.5, 4, 4.5, 5, 5.6, 6.3, 7.1, 8, 9, 10, 11, 13, 14, 16, 18, 20, 22];
export const KELVINS = Array.from({ length: 76 }, (_, i) => 2500 + i * 100);   // 2500 … 10000 K

// ---------- shaders ----------
const VS = `#version 300 es
in vec2 aPos; out vec2 vUv;
void main(){ vUv = aPos * .5 + .5; gl_Position = vec4(aPos, 0., 1.); }`;

const COMMON = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform vec2 uRes; uniform vec4 uWin; uniform float uTime;
float hash11(float p){ p = fract(p * .1031); p *= p + 33.33; p *= p + p; return fract(p); }
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
  return mix(mix(hash12(i), hash12(i+vec2(1,0)), f.x), mix(hash12(i+vec2(0,1)), hash12(i+vec2(1,1)), f.x), f.y); }
float fbm(vec2 p){ float s = 0., a = .5; for (int i = 0; i < 4; i++){ s += a * vnoise(p); p = p * 2.03 + 17.1; a *= .5; } return s; }
float sdBox(vec2 p, vec2 b){ vec2 d = abs(p) - b; return length(max(d, 0.)) + min(max(d.x, d.y), 0.); }
vec2 scenePos(vec2 uv){ return uWin.xy + uv * uWin.zw; }
`;

// Pass 1: the scene in linear light (rgb) and distance from the camera in metres (a). The reel's motion blur is
// integrated here, over the shutter time.
const SCENE_FS = COMMON + `
uniform float uShutter, uReel;
uniform vec3 uKey; uniform vec2 uKeyDir; uniform vec3 uAmb;
uniform vec3 uSkyTop, uSkyBot, uBldg; uniform vec4 uSun; uniform float uCity;
uniform vec3 uLamp, uLampLight, uPatch, uHaze, uString;
float PX;
float cover(float sd){ return clamp(.5 - sd / PX, 0., 1.); }
const vec2 WC = vec2(-.54, .25), WH = vec2(.32, .37);         // the window
const float YH = .05, DK = .69;                                // horizon height, desk depth constant

vec3 exterior(vec2 p){
  float t = smoothstep(-.12, .62, p.y);
  vec3 sky = mix(uSkyBot, uSkyTop, pow(t, .8));
  vec2 sp = vec2(-.47, uSun.w); float sd = length((p - sp) * vec2(1., 1.05));
  sky += uSun.rgb * (smoothstep(.034, .029, sd) + .05 * exp(-sd * 22.) + .012 * exp(-sd * 6.));
  float cx = floor((p.x + 2.) * 15.);
  float h = -.07 + .13 * hash11(cx) + .07 * hash11(cx * 1.7 + 3.) * step(.6, hash11(cx + 9.));
  if (p.y < h) {
    vec3 b = uBldg * (.55 + .45 * hash11(cx + 3.)) * (.8 + .2 * smoothstep(h - .2, h, p.y));
    vec2 g = vec2((p.x + 2.) * 120., p.y * 90.); vec2 gi = floor(g), gf = fract(g);
    float lit = step(.62, hash12(gi + cx)) * step(.25, gf.x) * step(gf.x, .75) * step(.3, gf.y) * step(gf.y, .8);
    b += uCity * .55 * lit * mix(vec3(1., .72, .42), vec3(.8, .9, 1.), hash12(gi * 1.3));
    return b;
  }
  return sky;
}

// Brushed-metal film reel, spinning. Returns colour; cov = how much of the pixel the reel covers.
vec3 reel(vec2 p, vec3 behind, out float cov){
  vec2 c = vec2(-.13, .085); float R = .19; vec2 v = p - c; float r = length(v);
  cov = cover(r - R);
  if (cov <= 0.) return behind;
  float th = atan(v.y, v.x);
  vec2 L = normalize(uKeyDir); float la = atan(L.y, L.x);
  // flange: radial brushing gives a bow-tie highlight across the light direction
  float brush = .55 + .45 * vnoise(vec2(th * 160., r * 9.));
  float bow = pow(abs(sin(th - la)), 18.) * brush;
  float diffuse = .35 + .65 * clamp(dot(normalize(v + 1e-4), L) * .5 + .5, 0., 1.);
  vec3 flange = vec3(.62, .63, .66) * (uAmb * 1.4 + uKey * (diffuse * .55 + bow * 2.1));
  float rim = smoothstep(R - .012, R - .004, r) * (1. - smoothstep(R - .002, R, r));
  flange += uKey * rim * 1.6 * clamp(dot(normalize(v + 1e-4), L), 0., 1.);
  // hub
  float hub = 1. - smoothstep(.044, .047, r);
  vec3 hubc = vec3(.32) * (uAmb * 1.5 + uKey * (.5 + 1.4 * pow(abs(sin(th - la + .4)), 10.)));
  hubc *= smoothstep(.014, .018, r);
  // film pack seen through the holes
  float fr = .128;
  vec3 film = vec3(.05, .035, .028) * (uAmb + uKey * .5) + uKey * .25 * pow(abs(sin(th - la)), 40.) * step(r, fr);
  // average the holes over the shutter time
  float blurPx = uReel * 6.2832 * uShutter * r / PX;
  int K = int(clamp(1. + blurPx * .6, 1., 40.));
  float inHole = 0.;
  for (int k = 0; k < 40; k++) {
    if (k >= K) break;
    float tt = uTime + uShutter * ((float(k) + .5) / float(K) - .5);
    float a = th - uReel * 6.2832 * tt;
    float s = mod(a + 3.14159 / 6., 6.28318 / 6.) - 3.14159 / 6.;
    float sd = length(vec2(r * cos(s) - .108, r * sin(s))) - .043;
    inHole += clamp(.5 - sd / PX, 0., 1.);
  }
  inHole /= float(K);
  vec3 through = r < fr ? film : behind;
  vec3 col = mix(flange, through, inHole);
  col = mix(col, hubc, hub);
  return mix(behind, col, cov);
}

void main(){
  vec2 p = scenePos(vUv); PX = uWin.z / uRes.x;
  vec3 col; float dep;
  vec2 L = normalize(uKeyDir);
  // ---- back wall + window ----
  float dWin = sdBox(p - WC, WH);
  float crossSd = min(abs(p.x - WC.x) - .007, abs(p.y - WC.y) - .007);
  float paneSd = max(sdBox(p - WC, WH - .024), -crossSd);
  float plaster = .86 + .14 * fbm(p * 22.) + .04 * vnoise(p * 140.);
  vec3 wallAlb = vec3(.47, .44, .40) * plaster;
  vec3 light = uAmb * (1.05 + .25 * p.y);
  light += uKey * .14 * exp(-length(p - vec2(-.2, .2)) * 1.6);
  vec2 lp = vec2(.62, .09);
  light += uLampLight * (.42 / (1. + 22. * dot(p - lp, p - lp)));
  // sun patch: the window, sheared onto the wall
  vec2 q = vec2((p.x - .4) - (p.y - .12) * .62, (p.y - .12) * 1.18);
  float patchSd = max(sdBox(q, vec2(.2, .22)), -min(abs(q.x) - .009, abs(q.y - .02) - .009));
  float patchM = smoothstep(.012, -.012, patchSd) * (.8 + .2 * vnoise(p * 30. + uTime * .2));
  light += uPatch * patchM;
  col = wallAlb * light; dep = 5.;
  // window frame and glass
  float frameCov = cover(dWin);
  vec3 frameC = vec3(.07, .068, .065) * (uAmb * 1.4 + uKey * .2 + uLampLight * .05);
  col = mix(col, frameC, frameCov);
  float pane = cover(paneSd);
  if (pane > 0.) { col = mix(col, exterior(p) + uAmb * .02, pane); if (pane > .5) dep = 60.; }
  // string-light wire
  float wy = .40 - .1 * (1. - p.x * p.x);
  float wire = cover(abs(p.y - wy) - .0012);
  col = mix(col, vec3(.01) * (uAmb + uKey * .1), wire * .9);
  // ---- desk ----
  if (p.y < -.18) {
    float dd = DK / max(YH - p.y, 1e-3);
    vec2 w = vec2(p.x * dd, dd);
    float grain = .5 + .5 * sin(w.x * 38. + fbm(vec2(w.x * 6., w.y * 1.6)) * 7.);
    vec3 alb = vec3(.26, .15, .085) * (.62 + .5 * grain * fbm(vec2(w.x * 30., w.y * .8)) + .12);
    vec3 dl = uAmb * 1.1 + uKey * (.35 + .65 * clamp(-L.x * (p.x + .1) * 1.2 + .55, 0., 1.)) * .85;
    vec2 dlp = vec2(.62, -.24);
    dl += uLampLight * (.55 / (1. + 30. * dot((p - dlp) * vec2(1., 2.), (p - dlp) * vec2(1., 2.))));
    vec3 deskC = alb * dl;
    // glossy reflection of the window and the patch
    vec2 m = vec2(p.x, -.36 - p.y);
    float wr = smoothstep(.06, -.04, sdBox(m - WC, WH - .02));
    deskC += (uSkyBot * .6 + uSkyTop * .2 + uSun.rgb * .002) * wr * .07 * smoothstep(-.9, -.2, p.y);
    deskC += uPatch * .05 * smoothstep(.05, -.05, sdBox(m - vec2(.4, .12), vec2(.22)));
    float edge = cover(abs(p.y + .182) - .003);
    deskC = mix(deskC, (uKey + uAmb) * .5 + uLampLight * .08, edge * .8);
    // contact shadows
    deskC *= 1. - .6 * exp(-pow(length((p - vec2(-.13, -.384)) * vec2(1., 5.)) * 9., 2.));
    deskC *= 1. - .55 * exp(-pow(length((p - vec2(.31, -.347)) * vec2(1., 5.)) * 13., 2.));
    deskC *= 1. - .5 * exp(-pow(length((p - vec2(.62, -.217)) * vec2(1., 5.)) * 16., 2.));
    float dc = cover(-.18 - p.y);
    col = mix(col, deskC, dc); if (dc > .04) dep = dd;
  }
  // ---- lamp, on the desk at 2.6 m ----
  {
    float y0 = -.0, y1 = .17;
    float tY = clamp((p.y - y0) / (y1 - y0), 0., 1.);
    float hw = mix(.125, .075, tY);
    float shadeSd = max(abs(p.x - .62) - hw, max(y0 - p.y, p.y - y1));
    float sc = cover(shadeSd);
    vec3 shadeC = vec3(.55, .5, .42) * (uAmb * 1.3 + uKey * .25) + uLamp * (.55 + .5 * (1. - tY)) * (.92 + .08 * fbm(p * 60.));
    float stemSd = max(abs(p.x - .62) - .005, max(-.214 - p.y, p.y - y0));
    float baseSd = length((p - vec2(.62, -.212)) / vec2(.06, .012)) - 1.;
    vec3 metal = vec3(.05) * (uAmb * 2. + uKey * .5) + uLampLight * .06;
    col = mix(col, metal, cover(stemSd)); col = mix(col, metal * 1.3, cover(baseSd * .012));
    col = mix(col, shadeC, sc);
    if (max(cover(stemSd), max(sc, cover(baseSd * .012))) > .04) dep = 2.6;
    col += uLamp * .045 * exp(-length((p - vec2(.62, .08)) * vec2(1., 1.4)) * 7.);
  }
  // ---- reel stand + reel at 1.6 m ----
  {
    float postSd = max(abs(p.x + .13) - .011, max(-.381 - p.y, p.y - .085));
    float baseSd = length((p - vec2(-.13, -.379)) / vec2(.1, .02)) - 1.;
    float hx = (p.x + .13) / .011;
    vec3 post = vec3(.06) * (uAmb * 1.5 + uKey * (.4 + 1.2 * smoothstep(.2, 1., -hx * sign(L.x + 1e-4))));
    vec3 basec = vec3(.07) * (uAmb * 1.5 + uKey * (.6 + .6 * smoothstep(.5, -1., (p.y + .379) / .02)));
    float pc = cover(postSd), bc = cover(baseSd * .02);
    col = mix(col, post, pc); col = mix(col, basec, bc);
    if (max(pc, bc) > .04) dep = 1.6;
    float rc; vec3 before = col;
    col = reel(p, col, rc);
    if (rc > .04) dep = 1.6;
  }
  // ---- white mug at 1.75 m, with steam ----
  {
    vec2 mc = vec2(.31, -.27); float hw = .062;
    float bodySd = max(abs(p.x - mc.x) - hw, max(-.345 - p.y + .012 * (1. - pow((p.x - mc.x) / hw, 2.)), p.y + .194));
    float rimSd = length((p - vec2(mc.x, -.194)) / vec2(hw, .014)) - 1.;
    vec2 hp = (p - vec2(mc.x + .066, -.268)) / vec2(.036, .046);
    float handleSd = abs(length(hp) - 1.) * .036 - .0075; handleSd = max(handleSd, mc.x + .055 - p.x);
    float nx = clamp((p.x - mc.x) / hw, -1., 1.); vec3 n = vec3(nx, 0., sqrt(1. - nx * nx));
    vec3 Ld = normalize(vec3(L, .55));
    float lam = max(dot(n, Ld), 0.);
    float spec = pow(max(dot(reflect(-Ld, n), vec3(0, 0, 1)), 0.), 60.);
    vec3 mug = vec3(.8, .79, .77) * (uAmb * (.7 + .3 * n.z) + uKey * lam * .95 + uLampLight * .05) + uKey * spec * 3.2;
    float mcov = max(cover(bodySd), cover(handleSd));
    col = mix(col, mug * (handleSd < bodySd ? .85 : 1.), mcov);
    float inside = cover(rimSd * .014);
    vec3 coffee = vec3(.035, .02, .012) * (uAmb + uKey * .3);
    float lip = smoothstep(-.25, 0., rimSd) * inside;
    col = mix(col, mix(coffee, vec3(.82) * (uAmb + uKey * .7), lip), inside);
    if (max(mcov, inside) > .04) dep = 1.75;
    float sy = clamp((p.y + .19) / .3, 0., 1.);
    float swx = p.x - mc.x - .03 * sin(p.y * 13. + uTime * 1.3) * sy;
    float steam = fbm(vec2(swx * 16., p.y * 7. - uTime * .55)) * exp(-pow(swx / (.02 + .06 * sy), 2.)) * smoothstep(0., .06, sy) * (1. - sy);
    col += (uAmb * 1.4 + uKey * .22 + uLampLight * .05) * steam * .55 * step(-.194, p.y);
  }
  // ---- haze shaft from the window ----
  {
    vec2 d = normalize(vec2(.78, -.52)); vec2 nrm = vec2(d.y, -d.x);
    float along = dot(p - WC, d), perp = abs(dot(p - WC, nrm));
    float shaft = smoothstep(.34, .06, perp) * smoothstep(-.15, .25, along) * exp(-along * 1.1);
    col += uHaze * shaft * (.55 + .45 * fbm(p * 3.5 + vec2(uTime * .03, 0.)));
  }
  // ---- out-of-focus leaves in the foreground, 0.55 m ----
  {
    float best = 1e9; vec3 leafC = vec3(0.);
    for (int i = 0; i < 5; i++) {
      float fi = float(i);
      vec2 base = vec2(-1.02 + .1 * fi, -.95 + .02 * fi);
      float ang = .55 + .28 * fi + .05 * sin(uTime * .6 + fi);
      vec2 dir = vec2(cos(ang), sin(ang));
      float len = .34 - .03 * fi;
      vec2 lp2 = p - base; float u = dot(lp2, dir), v2 = dot(lp2, vec2(-dir.y, dir.x));
      float wv = .055 * sin(clamp(u / len, 0., 1.) * 3.14159);
      float sd = max(abs(v2) - wv, max(-u, u - len));
      if (sd < best) { best = sd;
        float vein = smoothstep(.004, 0., abs(v2));
        leafC = vec3(.035, .075, .028) * (uAmb * 1.6 + uKey * (.35 + .4 * (1. - abs(v2) / max(wv, 1e-3)))) + vec3(.06, .14, .03) * uKey * .25 * vein; }
    }
    float lc = cover(best);
    col = mix(col, leafC, lc); if (lc > .04) dep = .55;
  }
  o = vec4(max(col, 0.), dep);
}`;

// Pass 2a: biggest blur circle in each 16 × 16 tile, so the gather knows how far to look.
const TILE_FS = COMMON + `
uniform sampler2D uSrc; uniform vec4 uLens;   // focus m, f-number, focal m, px per metre on the sensor
float coc(float d){ return min(uLens.z * uLens.z / uLens.y * abs(d - uLens.x) / (d * (uLens.x - uLens.z)) * uLens.w * .5, 70.); }
void main(){
  ivec2 t = ivec2(gl_FragCoord.xy) * 16; ivec2 sz = textureSize(uSrc, 0); float m = 0.;
  for (int y = 0; y < 16; y += 2) for (int x = 0; x < 16; x += 2) {
    ivec2 q = min(t + ivec2(x, y), sz - 1); m = max(m, coc(texelFetch(uSrc, q, 0).a)); }
  o = vec4(m);
}`;

// Pass 2b: depth of field by gathering. Each nearby pixel spreads over its own blur circle; sharp things
// in front aren't smeared by blurry things behind them.
const DOF_FS = COMMON + `
uniform sampler2D uSrc, uTile; uniform vec4 uLens; uniform int uTaps;
float coc(float d){ return min(uLens.z * uLens.z / uLens.y * abs(d - uLens.x) / (d * (uLens.x - uLens.z)) * uLens.w * .5, 70.); }
void main(){
  vec2 px = 1. / uRes;
  vec4 c0 = texture(uSrc, vUv); float r0 = coc(c0.a);
  ivec2 ti = ivec2(gl_FragCoord.xy) / 16; ivec2 ts = textureSize(uTile, 0); float R = r0;
  for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) R = max(R, texelFetch(uTile, clamp(ti + ivec2(x, y), ivec2(0), ts - 1), 0).r);
  if (R < .75) { o = c0; return; }
  float ign = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(.06711056, .00583715))));
  float rot = ign * 6.2832;
  int n = int(clamp(R * R * .45, 12., float(uTaps)));
  vec3 acc = c0.rgb; float wsum = 1.;
  for (int i = 0; i < 128; i++) {
    if (i >= n) break;
    float fi = float(i) + .5;
    float rr = sqrt(fi / float(n)) * R, a = fi * 2.39996 + rot;
    vec2 off = vec2(cos(a), sin(a)) * rr;
    vec4 s = texture(uSrc, vUv + off * px);
    float rs = coc(s.a);
    float reach = s.a < c0.a ? rs : min(rs, r0);
    float w = clamp(reach - rr + .5, 0., 1.);
    acc += s.rgb * w; wsum += w;
  }
  o = vec4(acc / wsum, c0.a);
}`;

// Pass 3: the camera. Point lights as bokeh, lens vignetting, exposure, white balance, sensor noise and clipping,
// then the display curve (or S-Log3, false colour, zebras).
const CAM_FS = COMMON + `
uniform sampler2D uSrc; uniform vec4 uLens;
uniform float uExpo, uIso, uMode, uSeed, uZebra, uFalse;
uniform vec3 uWB, uString, uCityC; uniform float uCity, uHazeI; uniform vec3 uHazeC;
const float CLIP = ${CLIP.toFixed(4)};
float coc(float d){ return min(uLens.z * uLens.z / uLens.y * abs(d - uLens.x) / (d * (uLens.x - uLens.z)) * uLens.w * .5, 70.); }
vec3 dispCurve(vec3 x){ vec3 s = log2(max(x, 1e-6) / .18); vec3 lo = .42 * exp2(s * .7), hi = 1. - .58 * exp2(-s * .55); return mix(lo, hi, step(0., s)); }
float shapeR(vec2 q, float r){       // bokeh: round wide open, nine-sided when stopped down
  float th = atan(q.y, q.x); float n = 9.;
  float k = cos(3.14159 / n) / cos(mod(th + .3, 6.28318 / n) - 3.14159 / n);
  float poly = smoothstep(2.8, 9., uLens.y) * .9;
  return length(q) / mix(r, r * k, poly);
}
vec3 bokeh(vec2 frag, vec2 lightPx, float r, vec3 E, vec2 center){
  vec2 q = frag - lightPx; float rr = max(r, 1.1);
  if (dot(q, q) > (rr + 2.) * (rr + 2.)) return vec3(0.);
  float d = shapeR(q, rr);
  vec2 toC = (lightPx - center) / max(length(uRes), 1.);
  float cat = length(q + toC * rr * 2.2 * smoothstep(2.8, 1.4, uLens.y + .6)) / (rr * 1.05);
  d = max(d, cat * step(2.5, rr));
  float edge = 1. - smoothstep(1. - 1.4 / rr, 1., d);
  float ring = mix(.78, 1.2, smoothstep(.55, .98, d));
  return E * edge * ring / (3.14159 * rr * rr);
}
void main(){
  vec4 s = texture(uSrc, vUv); vec3 x = s.rgb; float dep = s.a;
  vec2 frag = vUv * uRes, center = uRes * .5;
  vec2 p = scenePos(vUv);
  float pxPerUnit = uRes.x / uWin.z;
  // string-light bulbs at 3.4 m
  if (dep > 3.2 && dot(uString, uString) > 0.) {
    float r = coc(3.4);
    for (int i = 0; i < 30; i++) {
      float bx = -1.02 + float(i) * .072;
      vec2 bp = vec2(bx, .40 - .1 * (1. - bx * bx) - .014);
      vec2 lpx = (bp - uWin.xy) / uWin.zw * uRes;
      float tw = .8 + .2 * sin(uTime * (1. + hash11(float(i))) * 2. + float(i));
      x += bokeh(frag, lpx, r, uString * (6. + 3. * hash11(float(i) * 3.1)) * tw, center);
    }
  }
  // city lights through the window, at 60 m
  if (dep > 30. && uCity > 0.) {
    float r = coc(60.);
    for (int i = 0; i < 26; i++) {
      float fi = float(i);
      vec2 cp = vec2(-.84 + .62 * hash11(fi * 7.3), -.11 + .16 * hash11(fi * 3.7));
      vec2 lpx = (cp - uWin.xy) / uWin.zw * uRes;
      vec3 cc = mix(vec3(1., .62, .3), vec3(.75, .88, 1.), step(.55, hash11(fi * 1.9)));
      x += bokeh(frag, lpx, r, cc * uCity * (5. + 8. * hash11(fi * 2.3)), center);
    }
  }
  // dust in the window light, 1–3 m
  if (uHazeI > 0.) {
    for (int i = 0; i < 22; i++) {
      float fi = float(i); float z = 1.1 + 2. * hash11(fi * 5.1);
      if (dep < z) continue;
      vec2 mp = vec2(-.45 + .9 * hash11(fi * 1.7), .35 - .55 * hash11(fi * 2.9));
      mp += .03 * vec2(sin(uTime * .21 + fi), cos(uTime * .17 + fi * 1.3));
      vec2 lpx = (mp - uWin.xy) / uWin.zw * uRes;
      x += bokeh(frag, lpx, coc(z), uHazeC * uHazeI * (2. + 3. * hash11(fi)), center);
    }
  }
  // optical vignetting: stronger wide open
  vec2 vc = (vUv - .5) * vec2(uRes.x / uRes.y, 1.);
  float vig = 1. - mix(.12, .5, smoothstep(8., 1.4, uLens.y)) * smoothstep(.2, 1.1, length(vc));
  x *= vig;
  // veiling glare around very bright things
  vec3 g = textureLod(uSrc, vUv, 5.).rgb;
  x += max(g - .9, 0.) * .07;
  x *= uExpo * uWB;
  // sensor noise: grows with ISO, strongest in the shadows
  float a = .011 * pow(uIso / 800., .55);
  vec2 nf = floor(frag) + uSeed;
  vec3 nz = vec3(hash12(nf), hash12(nf + 7.1), hash12(nf + 13.7)) - .5;
  float nl = hash12(nf * 1.37 + 3.) - .5;
  x += (vec3(nl) * 1.6 + nz * .9) * a * (sqrt(max(x, 0.) * .18) + .025) * 3.;
  x = clamp(x, 0., CLIP);
  vec3 y;
  if (uMode > 2.5) {                 // S-Log3, before any LUT
    vec3 lg = vec3(0.);
    for (int c = 0; c < 3; c++) { float v = x[c]; lg[c] = v >= .01125 ? (420. + 261.5 * log(  (v + .01) / .19) / log(10.)) / 1023. : (v * (171.2102946929 - 95.) / .01125 + 95.) / 1023.; }
    y = mix(vec3(dot(lg, vec3(.2126, .7152, .0722))), lg, .7);
  } else {
    y = dispCurve(x) / dispCurve(vec3(CLIP)).x;
    float l = dot(y, vec3(.2126, .7152, .0722)); y = max(mix(vec3(l), y, 1.08), 0.);
  }
  float L = dot(y, vec3(.2126, .7152, .0722));
  if (uFalse > .5 && uMode < 2.5) {
    vec3 grey = vec3(L * .82 + .04);
    y = L < .025 ? vec3(.42, .16, 1.) : L < .1 ? vec3(.12, .42, 1.) : (L > .4 && L < .49) ? vec3(.18, .83, .36)
      : (L > .6 && L < .68) ? vec3(1., .44, .7) : (L > .93 && L < .985) ? vec3(1., .82, .23) : L >= .985 ? vec3(1., .23, .19) : grey;
  }
  if (uZebra > .5 && L >= .95) {
    float st = step(.5, fract((gl_FragCoord.x + gl_FragCoord.y - uTime * 40.) / 11.));
    y = mix(y, vec3(st), .85);
  }
  o = vec4(clamp(y, 0., 1.), 1.);
}`;

// ---------- WebGL plumbing ----------
function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) + "\n" + src.split("\n").map((l, i) => i + 1 + ": " + l).join("\n"));
  return s;
}
function program(gl, fs) {
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, VS));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
  gl.bindAttribLocation(p, 0, "aPos");
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const a = gl.getActiveUniform(p, i); u[a.name.replace(/\[0\]$/, "")] = gl.getUniformLocation(p, a.name); }
  return { p, u };
}

// Scene lighting as numbers, so one setup can melt into another.
function sceneVector(s) { return { ...s }; }
function lerpScene(a, b, t) {
  const o = {};
  for (const k in b) {
    const va = a[k], vb = b[k];
    if (typeof vb === "number" && typeof va === "number") o[k] = /K$/.test(k) ? 1e6 / ((1e6 / va) * (1 - t) + (1e6 / vb) * t) : va + (vb - va) * t;
    else if (Array.isArray(vb)) o[k] = vb.map((v, i) => va[i] + (v - va[i]) * t);
    else o[k] = t < 0.5 ? va : vb;
  }
  // exposure for "correct" melts in stops
  const ga = Math.log2(gainOf(a.correct)), gb = Math.log2(gainOf(b.correct));
  o.correctStops = ga + (gb - ga) * t;
  o.light = 1e6 / ((1e6 / a.light) * (1 - t) + (1e6 / b.light) * t);
  return o;
}

export function createSim({ low = false } = {}) {
  const glc = document.createElement("canvas");
  const gl = glc.getContext("webgl2", { antialias: false, alpha: false, premultipliedAlpha: false, powerPreference: "high-performance" });
  if (!gl) return null;
  const floatOK = !!gl.getExtension("EXT_color_buffer_float");
  gl.getExtension("OES_texture_float_linear");
  const P = { scene: program(gl, SCENE_FS), tile: program(gl, TILE_FS), dof: program(gl, DOF_FS), cam: program(gl, CAM_FS) };
  const vb = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vb);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  function target(w, h, fmt, mips) {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    const internal = fmt === "r" ? (floatOK ? gl.R16F : gl.R8) : (floatOK ? gl.RGBA16F : gl.RGBA8);
    const levels = mips ? Math.floor(Math.log2(Math.max(w, h))) + 1 : 1;
    gl.texStorage2D(gl.TEXTURE_2D, levels, internal, w, h);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mips ? gl.LINEAR_MIPMAP_LINEAR : (fmt === "r" ? gl.NEAREST : gl.LINEAR));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, fmt === "r" ? gl.NEAREST : gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const f = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, f);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    return { t, f, w, h };
  }
  function free(T) { for (const k in T) if (T[k] && T[k].t) { gl.deleteTexture(T[k].t); gl.deleteFramebuffer(T[k].f); } }
  function targetsFor(v, w, h) {
    if (!v.T || v.T.w !== w || v.T.h !== h) {
      if (v.T) free(v.T);
      v.T = { w, h, scene: target(w, h), tile: target(Math.ceil(w / 16), Math.ceil(h / 16), "r"), dofA: target(w, h, 0, true), dofB: null };
    }
    if (v.b && !v.T.dofB) v.T.dofB = target(w, h, 0, true);
    return v.T;
  }

  let frame = 0;
  function setScene(u, sc, t, shutter, win, w, h) {
    gl.uniform2f(u.uRes, w, h); gl.uniform4f(u.uWin, win[0], win[1], win[2], win[3]); gl.uniform1f(u.uTime, t);
    gl.uniform1f(u.uShutter, shutter); gl.uniform1f(u.uReel, sc.reel ?? 0.9);
    gl.uniform3fv(u.uKey, mul(sc.keyK, sc.key)); gl.uniform2fv(u.uKeyDir, sc.keyDir); gl.uniform3fv(u.uAmb, mul(sc.ambK, sc.amb));
    gl.uniform3fv(u.uSkyTop, mul(sc.skyTopK, sc.skyTop)); gl.uniform3fv(u.uSkyBot, mul(sc.skyBotK, sc.skyBot)); gl.uniform3fv(u.uBldg, mul(sc.bldgK, sc.bldg));
    gl.uniform4fv(u.uSun, [...mul(sc.sunK, sc.sun), sc.sunY]); gl.uniform1f(u.uCity, sc.city);
    gl.uniform3fv(u.uLamp, mul(sc.lampK, sc.lamp)); gl.uniform3fv(u.uLampLight, mul(sc.lampK, sc.lampLight));
    gl.uniform3fv(u.uPatch, mul(sc.patchK, sc.patch)); gl.uniform3fv(u.uHaze, mul(sc.hazeK, sc.haze)); gl.uniform3fv(u.uString, mul(2600, sc.string));
  }
  function quad() { gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); }
  function lensVec(s, w) { return [FOCUS_M, s.fnum, FOCAL_M, (w / 0.036) * (s.fnumScale ?? 1)]; }

  // the sides of the picture: camera settings + display mode
  function passDof(T, s, dst, w, h, win) {
    gl.useProgram(P.tile.p);
    gl.bindFramebuffer(gl.FRAMEBUFFER, T.tile.f); gl.viewport(0, 0, T.tile.w, T.tile.h);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, T.scene.t);
    gl.uniform1i(P.tile.u.uSrc, 0); gl.uniform4fv(P.tile.u.uLens, lensVec(s, w));
    quad();
    gl.useProgram(P.dof.p);
    gl.bindFramebuffer(gl.FRAMEBUFFER, dst.f); gl.viewport(0, 0, w, h);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, T.scene.t);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, T.tile.t);
    gl.uniform1i(P.dof.u.uSrc, 0); gl.uniform1i(P.dof.u.uTile, 1);
    gl.uniform4fv(P.dof.u.uLens, lensVec(s, w)); gl.uniform2f(P.dof.u.uRes, w, h); gl.uniform1i(P.dof.u.uTaps, low ? 36 : 72);
    gl.uniform4f(P.dof.u.uWin, win[0], win[1], win[2], win[3]);
    quad();
    gl.bindTexture(gl.TEXTURE_2D, dst.t); gl.generateMipmap(gl.TEXTURE_2D);
  }
  function passCam(src, s, sc, t, w, h, win, fx) {
    const u = P.cam.u;
    gl.useProgram(P.cam.p);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, src.t);
    gl.uniform1i(u.uSrc, 0); gl.uniform4fv(u.uLens, lensVec(s, w));
    gl.uniform2f(u.uRes, w, h); gl.uniform4f(u.uWin, win[0], win[1], win[2], win[3]); gl.uniform1f(u.uTime, t);
    const stops = Math.log2(gainOf(s)) - (sc.correctStops ?? Math.log2(gainOf(sc.correct)));
    gl.uniform1f(u.uExpo, 2 ** stops); gl.uniform1f(u.uIso, s.iso); gl.uniform3fv(u.uWB, wbGains(s.wb));
    gl.uniform1f(u.uMode, s.mode === "log" ? 3 : 0); gl.uniform1f(u.uSeed, (frame % 97) * 17.3);
    gl.uniform1f(u.uZebra, s.zebra || fx.zebra ? 1 : 0); gl.uniform1f(u.uFalse, s.falseColor || fx.falseColor ? 1 : 0);
    gl.uniform3fv(u.uString, mul(2600, sc.string)); gl.uniform1f(u.uCity, sc.city);
    gl.uniform1f(u.uHazeI, sc.haze); gl.uniform3fv(u.uHazeC, kelvinRGB(sc.hazeK));
    quad();
  }

  // window into the scene that fills a w × h picture (crops like "cover")
  function windowFor(w, h, zoom = 1) {
    const a = w / h, baseH = 1.0 / zoom;
    let ww = baseH * a, hh = baseH;
    if (ww > 2.0) { ww = 2.0; hh = ww / a; }
    if (hh > 1.75) { hh = 1.75; ww = hh * a; }
    const cy = 0.02 - (hh - 1) * 0.12;
    return [-ww / 2 + (a < 1 ? -0.06 : 0), cy - hh / 2, ww, hh];
  }

  const views = new Set();
  const fx = { zebra: false, falseColor: false };

  function view(canvas, opts = {}) {
    const ctx = canvas.getContext("2d", { alpha: false });
    const v = {
      canvas, ctx, visible: true, scale: opts.scale ?? 1, zoom: opts.zoom ?? 1, maxW: opts.maxW ?? 1280, size: opts.size ?? null,
      scene: sceneVector(SCENES[opts.scene ?? 0]),
      a: { iso: 800, shutter: 1 / 48, fnum: 2.8, wb: 5600, mode: "normal" },
      b: null, split: 0.5, splitDir: "x",
      t0: performance.now() / 1000, time: 0, onFrame: null, w: 0, h: 0, dirty: true,
      setScene(i, dur = 0) { tweenScene(v, SCENES[i], dur); },
      destroy() { views.delete(v); if (v.T) free(v.T); },
    };
    views.add(v);
    return v;
  }
  function tweenScene(v, to, dur) {
    const from = { ...v.scene };
    if (!dur) { v.scene = lerpScene(from, to, 1); return; }
    const t0 = performance.now();
    v.sceneTween = (now) => {
      const k = Math.min(1, (now - t0) / (dur * 1000));
      const e = k < 0.5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2;
      v.scene = lerpScene(from, to, e);
      if (k >= 1) v.sceneTween = null;
    };
  }

  function sizeOf(v) {
    if (v.size) return v.size;
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    const r = v.canvas.getBoundingClientRect();
    let w = Math.max(2, Math.round(r.width * dpr * v.scale)), h = Math.max(2, Math.round(r.height * dpr * v.scale));
    const cap = low ? Math.min(v.maxW, 760) : v.maxW;
    if (w > cap) { h = Math.round(h * cap / w); w = cap; }
    return [w, h];
  }

  function renderView(v, now) {
    if (v.sceneTween) v.sceneTween(now);
    const [w, h] = sizeOf(v);
    if (v.canvas.width !== w || v.canvas.height !== h) { v.canvas.width = w; v.canvas.height = h; }
    if (glc.width < w || glc.height < h) { glc.width = Math.max(glc.width, w); glc.height = Math.max(glc.height, h); }
    const T = targetsFor(v, w, h), win = windowFor(w, h, v.zoom), t = v.time;
    const sc = v.scene;
    // the reel is rendered once per side when the shutters differ; usually one pass is shared
    const sides = v.b ? [v.a, v.b] : [v.a];
    sides.forEach((s, i) => {
      if (i === 0 || s.shutter !== v.a.shutter) {
        gl.useProgram(P.scene.p);
        gl.bindFramebuffer(gl.FRAMEBUFFER, T.scene.f); gl.viewport(0, 0, w, h);
        setScene(P.scene.u, sc, t, s.shutter, win, w, h);
        quad();
      }
      const dst = i === 0 ? T.dofA : T.dofB;
      passDof(T, s, dst, w, h, win);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, w, h);
      if (i === 1) {
        gl.enable(gl.SCISSOR_TEST);
        const sx = Math.round(w * v.split);
        gl.scissor(sx, 0, w - sx, h);
      }
      passCam(dst, s, sc, t, w, h, win, fx);
      gl.disable(gl.SCISSOR_TEST);
    });
    v.ctx.drawImage(glc, 0, glc.height - h, w, h, 0, 0, w, h);
    v.w = w; v.h = h;
    if (v.onFrame) v.onFrame(v);
  }

  function render(now = performance.now()) {
    frame++;
    for (const v of views) {
      if (!v.visible || v.hold) {
        // a picture that has been off screen for a while gives its GPU memory back (phones are tight)
        if (v.T && v.hiddenSince && now - v.hiddenSince > 15000) { free(v.T); v.T = null; }
        if (!v.hiddenSince) v.hiddenSince = now;
        continue;
      }
      v.hiddenSince = 0;
      v.time = now / 1000 - v.t0;
      renderView(v, now);
    }
  }

  // ---------- light meter: what the agent would measure, read back from a small render of each setup ----------
  const stats = [];
  function measure() {
    const w = 192, h = 108, win = windowFor(w, h);
    const T = target(w, h);
    for (const sc0 of SCENES) {
      const sc = sceneVector(sc0);
      gl.useProgram(P.scene.p);
      gl.bindFramebuffer(gl.FRAMEBUFFER, T.f); gl.viewport(0, 0, w, h);
      setScene(P.scene.u, sc, 0.5, 1 / 48, win, w, h);
      quad();
      let px;
      if (floatOK) { px = new Float32Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.FLOAT, px); }
      stats.push(px ? summarize(px, w, h) : null);
    }
    gl.deleteFramebuffer(T.f); gl.deleteTexture(T.t);
  }
  function summarize(px, w, h) {
    let subj = 0, ns = 0, cw = 0, cwn = 0;
    const hist = new Float32Array(25 * 6);          // log2(max channel / 0.18) from -12 to +13, 1/6-stop bins
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4, r = px[i], g = px[i + 1], b = px[i + 2], d = px[i + 3];
      const L = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const lg = Math.log2(Math.max(L, 1e-5) / 0.18);
      if (d > 1.5 && d < 1.9) { subj += lg; ns++; }
      const wgt = Math.exp(-(((x / w - 0.47) / 0.3) ** 2 + ((y / h - 0.5) / 0.35) ** 2));
      cw += lg * wgt; cwn += wgt;
      const m = Math.log2(Math.max(r, g, b, 1e-5) / 0.18);
      hist[Math.max(0, Math.min(hist.length - 1, Math.floor((m + 12) * 6)))]++;
    }
    for (let i = 0; i < hist.length; i++) hist[i] /= w * h;
    return { subject: ns ? subj / ns : cw / cwn, center: cw / cwn, hist };
  }
  try { measure(); } catch (e) { console.warn("meter", e); }

  // Measure a picture: subject exposure in stops from middle grey, and how much of the frame clips.
  function meter(sceneIndex, s, sceneOverride) {
    const sc = sceneOverride ?? SCENES[sceneIndex];
    const st = stats[sceneIndex] || FALLBACK[sceneIndex];
    const shift = Math.log2(gainOf(s)) - (sc.correctStops ?? Math.log2(gainOf(sc.correct)));
    const clipStop = Math.log2(CLIP / 0.18) - shift - 0.15;
    let clip = 0;
    for (let i = 0; i < st.hist.length; i++) if ((i + 0.5) / 6 - 12 > clipStop) clip += st.hist[i];
    return { subject: st.subject + shift, center: st.center + shift, clip, shift };
  }

  return { view, views, render, meter, stats, fx, gl, floatOK, SCENES, windowFor };
}

// Used when the browser can't read float pixels back: the same numbers, measured on a Mac.
const FALLBACK = SCENES.map(() => ({ subject: 0, center: 0, hist: new Float32Array(150) }));
