const D = S.D, CX = 540, CY = 960;
const tl = gsap.timeline({ paused: true });
const $ = s => document.getElementById(s);
const W = $("world");
// medir posiciones con el mundo sin transformar
const posOf = id => { const r = $(id).getBoundingClientRect(), w = W.getBoundingClientRect(); return { x: r.left - w.left + r.width / 2, y: r.top - w.top + r.height / 2, w: r.width, h: r.height }; };
const P0 = {}; S.EV.forEach(e => { if (!P0[e.id] && $(e.id)) P0[e.id] = posOf(e.id); });
S.stEls.flat().forEach(id => { if (!P0[id] && $(id)) P0[id] = posOf(id); });
const HID = new Set(S.hidden);
const vis = S.stEls.map(ids => new Set(ids.filter(id => !HID.has(id))));
const topOwner = {}; S.stEls.forEach((ids, si) => ids.forEach(id => topOwner[id] = si));
function frameOf(set) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  set.forEach(id => { const p = P0[id]; if (!p) return; x0 = Math.min(x0, p.x - p.w / 2); x1 = Math.max(x1, p.x + p.w / 2); y0 = Math.min(y0, p.y - p.h / 2); y1 = Math.max(y1, p.y + p.h / 2); });
  if (x0 > x1) return null;
  const w = Math.max(x1 - x0, 560), h = Math.max(y1 - y0, 360);
  return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, s: Math.max(0.55, Math.min(1.45, 1000 / h, 960 / w)) };
}
function camTo(c, t, dur, ease) {
  tl.to(W, { x: CX - c.x * c.s, y: CY - c.y * c.s, scale: c.s, duration: dur, ease }, t);
  tl.to("#grid", { x: -((c.x - 540) * 0.15) % 90, y: -((c.y - 960) * 0.15) % 90, duration: dur, ease }, t);
}
const trav = Object.entries(S.travel).map(([si, t]) => [+si, t]).sort((a, b) => a[1] - b[1]);
const stationAt = t => { let s = 0; trav.forEach(([si, tt]) => { if (t >= tt) s = si; }); return s; };
const visAt = (si, t) => { const v = new Set(vis[si]); S.EV.forEach(e => { if (topOwner[e.id] !== si || e.t > t) return; if (e.a === "show") v.add(e.id); if (e.a === "hide") v.delete(e.id); }); return v; };
let lastEnd = 0, cur = frameOf(visAt(0, 0.8)) || { x: 540, y: 600, s: 1 };
gsap.set(W, { x: CX - cur.x * cur.s * 1.35, y: CY - cur.y * cur.s * 1.35, scale: cur.s * 1.35 });
camTo(cur, 0, 0.75, "expo.out"); lastEnd = 0.75;
const camEvents = S.EV.filter(e => topOwner[e.id] !== undefined && (e.a === "show" || e.a === "hide"));
camEvents.concat(trav.map(([si, t]) => ({ t, travel: si }))).sort((a, b) => a.t - b.t).forEach(e => {
  if (e.travel !== undefined) {
    const si = e.travel, t = e.t, a = cur, b = frameOf(visAt(si, t + 1.6)) || cur;
    const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, s: Math.min(a.s, b.s) * 0.55 };
    camTo(mid, t, 0.45, "power2.in"); camTo(b, t + 0.45, 0.6, "power3.out");
    tl.to(W, { filter: "blur(8px)", duration: 0.3, ease: "power2.in" }, t + 0.2);
    tl.to(W, { filter: "blur(0px)", duration: 0.35, ease: "power2.out" }, t + 0.55);
    const p = $("pth" + (si - 1)); const L = p.getTotalLength();
    gsap.set(p, { strokeDasharray: L, strokeDashoffset: L });
    tl.to(p, { strokeDashoffset: 0, duration: 0.85, ease: "power2.inOut" }, t + 0.1);
    cur = b; lastEnd = t + 1.05; return;
  }
  const si = topOwner[e.id]; if (stationAt(e.t + 0.01) !== si) return;
  const f = frameOf(visAt(si, e.t + 0.6)); if (!f) return;
  if (Math.abs(f.s - cur.s) / cur.s < 0.05 && Math.hypot(f.x - cur.x, f.y - cur.y) < 50) return;
  const st = Math.max(e.t - 0.15, lastEnd); camTo(f, st, 0.55, "power2.inOut"); lastEnd = st + 0.55; cur = f;
});
// estado inicial
S.hidden.forEach(id => { if ($(id)) gsap.set("#" + CSS.escape(id), { opacity: 0 }); });
document.querySelectorAll(".fbox").forEach(b => { if (HID.has(b.id)) { const p = b.previousElementSibling; if (p && p.classList.contains("farrow")) gsap.set(p, { opacity: 0 }); } });
document.querySelectorAll(".ico > span, .alt").forEach(e => gsap.set(e, { opacity: 0 }));
document.querySelectorAll(".sk").forEach(e => gsap.set(e, { scaleX: 0, opacity: 1, transformOrigin: "0 50%" }));
document.querySelectorAll(".tyl").forEach(e => gsap.set(e, { width: 0 }));
// personajes vivos
function alive(id, from, to) {
  const n = Math.max(1, Math.floor((to - from) / 1.6));
  tl.fromTo(`#${id}-body`, { scaleY: 1 }, { scaleY: 1.035, svgOrigin: "101 240", duration: 0.8, ease: "sine.inOut", yoyo: true, repeat: n * 2 - 1 }, from);
  tl.fromTo(`#${id}-head`, { y: 0 }, { y: -4, duration: 0.8, ease: "sine.inOut", yoyo: true, repeat: n * 2 - 1 }, from);
  for (let t = from + 0.9; t < to - 0.2; t += 2.7) {
    tl.to(`#${id}-eyes`, { scaleY: 0.1, svgOrigin: "101 76", duration: 0.06 }, t);
    tl.to(`#${id}-eyes`, { scaleY: 1, svgOrigin: "101 76", duration: 0.08 }, t + 0.1);
  }
}
function talk(id, from, to) {
  for (let t = from; t < to - 0.15; t += 0.22) {
    tl.to(`#${id}-mouth`, { attr: { d: "M88 98 Q101 120 114 98" }, duration: 0.09 }, t);
    tl.to(`#${id}-mouth`, { attr: { d: "M88 100 Q101 110 114 100" }, duration: 0.09 }, t + 0.11);
  }
}
function walkIn(id, t) {
  const k = 4;
  tl.fromTo(`#${id}-legL`, { rotation: -30 }, { rotation: 30, svgOrigin: "90 232", duration: 0.12, yoyo: true, repeat: k - 1 }, t);
  tl.fromTo(`#${id}-legR`, { rotation: 30 }, { rotation: -30, svgOrigin: "112 232", duration: 0.12, yoyo: true, repeat: k - 1 }, t);
  tl.to([`#${id}-legL`, `#${id}-legR`], { rotation: 0, duration: 0.12 }, t + k * 0.12);
}
const shownChars = {};
const endOfPhrase = t => { for (const p of S.phrases) if (t >= p.start - 0.35 && t <= p.end + 0.25) return p.end; return t + 1.5; };
const q = id => "#" + CSS.escape(id);
const isRow = id => $(id) && $(id).classList.contains("row");
const isCell = id => $(id) && ($(id).classList.contains("cell") || $(id).classList.contains("hcell"));
S.EV.forEach(e => {
  const t = e.t, id = e.id, x = e.x || {}, el = $(id);
  if (!el) { console.error("falta", id); return; }
  const cls = el.classList;
  switch (e.a) {
    case "show": {
      if (cls.contains("row")) tl.fromTo(q(id), { opacity: 0, y: -110 }, { opacity: 1, y: 0, duration: 0.45, ease: "back.out(1.6)" }, t);
      else if (cls.contains("dialog")) {
        const cid = id + "-c";
        tl.fromTo(q(id + "-cw"), { x: -220 }, { x: 0, duration: 0.55, ease: "power3.out" }, t);
        tl.fromTo(q(id), { opacity: 0 }, { opacity: 1, duration: 0.2 }, t);
        walkIn(cid, t);
        tl.fromTo(q(id + "-b"), { opacity: 0, scale: 0.5, transformOrigin: "0% 100%" }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.8)" }, t + 0.2);
        talk(cid, t + 0.2, x.until !== undefined ? x.until : endOfPhrase(t));
        if (!shownChars[cid]) { shownChars[cid] = 1; alive(cid, t + 0.6, D); }
      }
      else if (cls.contains("li") || x.from === "left") tl.fromTo(q(id), { opacity: 0, x: -70 }, { opacity: 1, x: 0, duration: 0.4, ease: "power3.out" }, t);
      else if (cls.contains("arrow")) {
        tl.fromTo(q(id), { opacity: 0 }, { opacity: 1, duration: 0.1 }, t);
        tl.fromTo(q(id + "-p"), { scaleY: 0, transformOrigin: "50% 0%" }, { scaleY: 1, duration: 0.35, ease: "power2.out" }, t);
        tl.fromTo(q(id + "-h"), { opacity: 0 }, { opacity: 1, duration: 0.15 }, t + 0.3);
      }
      else if (cls.contains("toast")) tl.fromTo(q(id), { opacity: 0, y: -70, scale: 0.92 }, { opacity: 1, y: 0, scale: 1, duration: 0.45, ease: "back.out(1.5)" }, t);
      else if (cls.contains("card")) tl.fromTo(q(id), { opacity: 0, y: 110, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: 0.55, ease: "power3.out" }, t);
      else if (cls.contains("bigt")) tl.fromTo(q(id), { opacity: 0, scale: 1.6, filter: "blur(10px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.35, ease: "power4.out" }, t);
      else tl.fromTo(q(id), { opacity: 0, scale: 0.4, rotation: x.rot || -8 }, { opacity: 1, scale: 1, rotation: 0, duration: 0.45, ease: "back.out(1.8)" }, t);
      if (cls.contains("fbox")) { const prev = el.previousElementSibling; if (prev && prev.classList.contains("farrow")) tl.fromTo(prev, { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.25 }, t - 0.1); }
      break; }
    case "hide": tl.to(q(id), { opacity: 0, scale: 0.6, duration: 0.25, ease: "power3.in" }, t); break;
    case "hl": tl.to(q(id), { backgroundColor: x.bg || "#ffe7a3", color: x.color || "#2a2000", duration: 0.25 }, t);
      tl.fromTo(q(id), { scale: 1 }, { scale: 1.08, duration: 0.15, yoyo: true, repeat: 1 }, t); break;
    case "good":
      if (isRow(id)) { tl.to(q(id), { backgroundColor: "#d9f5e5", duration: 0.25 }, t); tl.fromTo(q(id + "-ok"), { opacity: 0, scale: 2, rotation: -30 }, { opacity: 1, scale: 1, rotation: 0, duration: 0.4, ease: "back.out(2)" }, t); }
      else if (isCell(id)) tl.to(q(id), { color: "#13824a", backgroundColor: "#d9f5e5", duration: 0.25 }, t);
      else tl.to(q(id), { backgroundColor: "#1fbf6a", color: "#04170b", duration: 0.25 }, t);
      break;
    case "bad":
      if (isRow(id)) { tl.to(q(id), { backgroundColor: "#fde3df", duration: 0.25 }, t); tl.to(q(id + "-ok"), { opacity: 0, duration: 0.1 }, t); tl.fromTo(q(id + "-no"), { opacity: 0, scale: 2, rotation: 30 }, { opacity: 1, scale: 1, rotation: 0, duration: 0.4, ease: "back.out(2)" }, t); }
      else if (isCell(id)) tl.to(q(id), { color: "#c2372b", backgroundColor: "#fde3df", duration: 0.25 }, t);
      else tl.to(q(id), { backgroundColor: "#e5483b", color: "#ffffff", duration: 0.25 }, t);
      tl.fromTo(q(id), { x: 0 }, { x: 22, duration: 0.05, yoyo: true, repeat: 7, ease: "none" }, t);
      break;
    case "strike": tl.to(el.querySelector(":scope > .sk"), { scaleX: 1, duration: 0.3, ease: "power3.out" }, t);
      tl.to(q(id), { opacity: 0.75, duration: 0.3 }, t + 0.1); break;
    case "swap": { const a = $(id + "-alt");
      tl.fromTo(a, { opacity: 0, rotationX: -90 }, { opacity: 1, rotationX: 0, duration: 0.35, ease: "back.out(1.6)" }, t); break; }
    case "type": { const lines = [...el.querySelectorAll(".tyl")]; const tot = lines.reduce((s, l) => s + +l.dataset.n, 0); let tt = t; const dur = x.dur || 1.6;
      lines.forEach(l => { const n = +l.dataset.n, d = dur * n / tot; tl.fromTo(l, { width: 0 }, { width: n * 27.7 + 8, duration: d, ease: `steps(${n})` }, tt); tt += d; }); break; }
    case "shake": tl.fromTo(q(id), { x: 0 }, { x: 18, duration: 0.05, yoyo: true, repeat: 7, ease: "none" }, t); break;
    case "pulse": tl.fromTo(q(id), { scale: 1 }, { scale: 1.15, duration: 0.18, yoyo: true, repeat: 3, ease: "sine.inOut" }, t); break;
    case "boom": tl.fromTo("#shake", { x: 0 }, { x: 20, duration: 0.04, yoyo: true, repeat: 9, ease: "none" }, t);
      tl.fromTo(q(id), { scale: 1 }, { scale: 1.2, duration: 0.15, yoyo: true, repeat: 1 }, t); break;
    case "point": tl.to(`#${id}-c-armR`, { rotation: -130, svgOrigin: "142 132", duration: 0.35, ease: "back.out(2)" }, t);
      tl.to(`#${id}-c-armR`, { rotation: 0, svgOrigin: "142 132", duration: 0.3 }, t + 1.4); break;
    case "focus": { const p = P0[id] || posOf(id); const s = x.s || 1.15; camTo({ x: p.x, y: p.y + (x.dy || 0), s }, t, x.dur || 0.6, "power2.inOut"); break; }
  }
});
// subtítulos
document.querySelectorAll(".capg .w").forEach(el => {
  const t = parseFloat(el.dataset.t), kg = el.classList.contains("kg"), kb = el.classList.contains("kb");
  tl.fromTo(el, { color: "rgba(244,247,245,.35)", scale: 1, backgroundColor: "rgba(0,0,0,0)" },
    { color: kg ? "#04170b" : "#ffffff", backgroundColor: kg ? "#1fbf6a" : (kb ? "#e5483b" : "rgba(0,0,0,0)"), scale: (kg || kb) ? 1.08 : 1, duration: 0.12, ease: "power2.out" }, t);
});
document.querySelectorAll(".capg").forEach(g => tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: 0.1 }, parseFloat(g.dataset.start)));
tl.set({}, {}, D);
window.__timelines["main"] = tl;
