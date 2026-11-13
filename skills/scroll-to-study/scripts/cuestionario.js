/* Las preguntas de práctica después de cada video, en la lista de la compu (videos/index.html) y en la
 * app del teléfono (web/): la misma interfaz y los mismos textos en los dos lados.
 *
 * mostrar(caja, opciones) pone las preguntas encima del reproductor (dentro de `caja`), una por una:
 * opciones grandes; al elegir, la correcta en verde, la elegida en rojo si falló, y la explicación. Al
 * final, aciertos sobre total y cuándo vuelve el tema. La lógica del repaso no está acá: está en
 * progreso.js, y quien llama la usa en los callbacks:
 *   opciones = { idioma: "es"|"en", preguntas: [{ texto, opciones, correcta, explicacion, general }],
 *                alTerminar(aciertos, total) -> { dias, siguiente }   // dias hasta que vuelve; título o null
 *                alSeguir(), alSaltear() }
 * Devuelve { cerrar() }. Sin "Saltear" no hay forma de cerrarlo desde adentro: quien llama lo cierra al
 * cambiar de video.
 *
 * Funciona suelto: cargado en una página deja las funciones en window.Cuestionario; con require() las
 * exporta (sin DOM solo sirven textos y cuando).
 */
(function (raiz, hacer) {
  if (typeof module === "object" && module.exports) module.exports = hacer();
  else raiz.Cuestionario = hacer();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const TEXTOS = {
    es: {
      pregunta: "Pregunta {n} de {t}", saltear: "Saltear preguntas", siguiente: "Siguiente",
      verResultado: "Ver resultado", bien: "¡Bien!", mal: "No era esa.",
      tuya: "tu respuesta", correcta: "correcta",
      general: "método general · no está en tu material",
      resultado: "{a} de {t} correctas", vuelve: "Este tema vuelve {cuando}.",
      hoy: "hoy", manana: "mañana", enDias: "en {n} días",
      seguir: "Seguir: {t}", nada: "Nada pendiente hoy", cerrar: "Cerrar",
      region: "Preguntas del video",
      pendiente: "Pendiente hoy", aldia: "Al día", aldiaVuelve: "Al día · vuelve {cuando}", nuevo: "Nuevo",
      paraHoy: "para hoy",
    },
    en: {
      pregunta: "Question {n} of {t}", saltear: "Skip questions", siguiente: "Next",
      verResultado: "See result", bien: "Right!", mal: "Not that one.",
      tuya: "your answer", correcta: "correct",
      general: "general method · not in your material",
      resultado: "{a} of {t} correct", vuelve: "This topic comes back {cuando}.",
      hoy: "today", manana: "tomorrow", enDias: "in {n} days",
      seguir: "Next up: {t}", nada: "Nothing left for today", cerrar: "Close",
      region: "Questions about the video",
      pendiente: "Due today", aldia: "Up to date", aldiaVuelve: "Up to date · back {cuando}", nuevo: "New",
      paraHoy: "due today",
    },
  };
  const textos = idioma => TEXTOS[idioma] || TEXTOS.es;
  const fmt = (s, d) => s.replace(/\{(\w+)\}/g, (m, k) => (k in d ? d[k] : m));

  /** "mañana", "en 3 días"… para `dias` días desde hoy. */
  function cuando(dias, idioma) {
    const tx = textos(idioma);
    if (dias <= 0) return tx.hoy;
    if (dias === 1) return tx.manana;
    return fmt(tx.enDias, { n: dias });
  }

  /** El texto y la clase de un tema en la lista, a partir de Progreso.estadoTema y los días que faltan. */
  function etiqueta(e, dias, idioma) {
    const tx = textos(idioma);
    if (e.estado === "pendiente") return { texto: tx.pendiente, clase: "rep-pendiente" };
    if (e.estado === "nuevo") return { texto: tx.nuevo, clase: "rep-nuevo" };
    return { texto: e.proxima ? fmt(tx.aldiaVuelve, { cuando: cuando(dias, idioma) }) : tx.aldia, clase: "rep-aldia" };
  }

  /** El <span> de la etiqueta de un tema en la lista (e: Progreso.estadoTema; dias: hasta e.proxima). */
  function chip(doc, e, dias, idioma) {
    ponerCss(doc);
    const et = etiqueta(e, dias, idioma), s = doc.createElement("span");
    s.className = "s2s-rep " + et.clase; s.textContent = et.texto;
    return s;
  }

  const CSS = `
.s2s-quiz { position:absolute; inset:0; z-index:5; overflow:auto; display:flex; flex-direction:column; gap:12px;
  padding:18px 16px; background:var(--bg, #f6f1e3); color:var(--fg, #1d2b4f); text-align:left;
  font:15px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
.s2s-quiz .q-cab { display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; }
.s2s-quiz .q-num { color:var(--muted, #5f6a86); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
.s2s-quiz .q-gen { font-size:12px; font-weight:700; color:#7a4b00; background:#fff1d1; border:1px solid #e7c77d;
  border-radius:999px; padding:2px 8px; }
.s2s-quiz h2 { font:700 19px/1.3 system-ui, sans-serif; margin:0; outline:none; }
.s2s-quiz .q-ops { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; }
.s2s-quiz .q-op { width:100%; min-height:52px; text-align:left; font:600 16px/1.3 system-ui, sans-serif;
  color:var(--fg, #1d2b4f); background:var(--card, #fffdf6); border:2px solid var(--line, #d9cfb4);
  border-radius:12px; padding:12px 14px; cursor:pointer; display:flex; gap:10px; align-items:center; }
.s2s-quiz .q-op:hover:not(:disabled) { border-color:var(--accent, #2f5bd3); }
.s2s-quiz .q-op:disabled { cursor:default; opacity:1; color:var(--fg, #1d2b4f); }
.s2s-quiz .q-op .q-marca { flex:none; width:22px; text-align:center; font-weight:800; }
.s2s-quiz .q-op.bien { border-color:#1f8f52; background:#e3f5ea; }
.s2s-quiz .q-op.mal { border-color:#b3261e; background:#fbe5e3; }
.s2s-quiz .q-op.bien .q-marca { color:#1f8f52; }
.s2s-quiz .q-op.mal .q-marca { color:#b3261e; }
.s2s-quiz .q-exp { border-left:4px solid var(--line, #d9cfb4); padding:4px 0 4px 10px; margin:0; }
.s2s-quiz .q-exp b { display:block; }
.s2s-quiz .q-exp.bien { border-color:#1f8f52; } .s2s-quiz .q-exp.mal { border-color:#b3261e; }
.s2s-quiz .q-pie { display:flex; gap:8px; flex-wrap:wrap; margin-top:auto; padding-top:4px; }
.s2s-quiz .q-pie button { font:600 15px system-ui, sans-serif; border-radius:10px; padding:11px 16px; cursor:pointer;
  color:var(--fg, #1d2b4f); background:var(--card, #fffdf6); border:1px solid var(--line, #d9cfb4); }
.s2s-quiz .q-pie button.prim { background:var(--accent, #2f5bd3); border-color:var(--accent, #2f5bd3); color:#fff; }
.s2s-quiz .q-res { font:800 30px/1.1 system-ui, sans-serif; margin:8px 0 0; }
.s2s-rep.s2s-rep { display:inline-block; margin-top:6px; font-size:12px; font-weight:700; border-radius:999px;
  padding:2px 8px; }
.s2s-rep.rep-pendiente { background:#fde7c8; color:#7a3e00; }
.s2s-rep.rep-nuevo { background:#e3e9fb; color:#1d3a8f; }
.s2s-rep.rep-aldia { background:#e3f5ea; color:#17683c; }
.s2s-quiz button:focus-visible, .s2s-quiz h2:focus-visible { outline:2px solid var(--accent, #2f5bd3); outline-offset:2px; }
`;

  function ponerCss(doc) {
    if (doc.getElementById("s2s-quiz-css")) return;
    const s = doc.createElement("style"); s.id = "s2s-quiz-css"; s.textContent = CSS;
    doc.head.append(s);
  }

  function mostrar(caja, o) {
    const doc = caja.ownerDocument, tx = textos(o.idioma), preguntas = o.preguntas;
    ponerCss(doc);
    const el = (tag, clase, texto) => {
      const e = doc.createElement(tag);
      if (clase) e.className = clase;
      if (texto !== undefined) e.textContent = texto;
      return e;
    };
    const boton = (texto, clase, accion) => {
      const b = el("button", clase, texto); b.type = "button"; b.onclick = accion; return b;
    };
    const raiz = el("section", "s2s-quiz");
    raiz.setAttribute("role", "region"); raiz.setAttribute("aria-label", tx.region);
    caja.append(raiz);
    let aciertos = 0, cerrado = false;

    function cerrar() { cerrado = true; raiz.remove(); }
    const saltear = () => { cerrar(); if (o.alSaltear) o.alSaltear(); };

    function pregunta(i) {
      const p = preguntas[i];
      raiz.textContent = "";
      const cab = el("div", "q-cab");
      cab.append(el("span", "q-num", fmt(tx.pregunta, { n: i + 1, t: preguntas.length })));
      if (p.general) cab.append(el("span", "q-gen", tx.general));
      const h = el("h2", "", p.texto); h.tabIndex = -1;
      const ops = el("ul", "q-ops");
      const botones = p.opciones.map((texto, j) => {
        const b = el("button", "q-op"); b.type = "button";
        const marca = el("span", "q-marca"); marca.setAttribute("aria-hidden", "true");
        b.append(marca, el("span", "", texto));
        b.onclick = () => elegir(j);
        const li = el("li"); li.append(b); ops.append(li);
        return b;
      });
      const devolucion = el("div"); devolucion.setAttribute("aria-live", "polite");
      const pie = el("div", "q-pie");
      pie.append(boton(tx.saltear, "", saltear));
      raiz.append(cab, h, ops, devolucion, pie);
      h.focus();

      function elegir(j) {
        if (botones[0].disabled) return;
        const bien = j === p.correcta;
        if (bien) aciertos++;
        botones.forEach((b, k) => {
          b.disabled = true;
          const marca = b.querySelector(".q-marca");
          if (k === p.correcta) {
            b.classList.add("bien"); marca.textContent = "✓";
            b.setAttribute("aria-label", `${p.opciones[k]} (${tx.correcta})`);
          } else if (k === j) {
            b.classList.add("mal"); marca.textContent = "✗";
            b.setAttribute("aria-label", `${p.opciones[k]} (${tx.tuya})`);
          }
        });
        const exp = el("p", "q-exp " + (bien ? "bien" : "mal"));
        exp.append(el("b", "", bien ? tx.bien : tx.mal), el("span", "", p.explicacion));
        devolucion.append(exp);
        const ultima = i === preguntas.length - 1;
        const sig = boton(ultima ? tx.verResultado : tx.siguiente, "prim q-sig", () => (ultima ? resultado() : pregunta(i + 1)));
        pie.prepend(sig);
        sig.focus();
      }
    }

    function resultado() {
      const r = o.alTerminar(aciertos, preguntas.length) || {};
      if (cerrado) return;
      raiz.textContent = "";
      const h = el("h2", "q-res", fmt(tx.resultado, { a: aciertos, t: preguntas.length })); h.tabIndex = -1;
      const vuelve = el("p", "q-vuelve", fmt(tx.vuelve, { cuando: cuando(r.dias, o.idioma) }));
      const pie = el("div", "q-pie");
      const sigue = r.siguiente ? fmt(tx.seguir, { t: r.siguiente }) : tx.cerrar;
      pie.append(boton(sigue, "prim q-seguir", () => { cerrar(); if (o.alSeguir) o.alSeguir(); }));
      const partes = [h, vuelve];
      if (!r.siguiente) partes.push(el("p", "q-nada", tx.nada));
      raiz.append(...partes, pie);
      h.focus();
    }

    if (preguntas && preguntas.length) pregunta(0); else cerrar();
    return { cerrar };
  }

  return { TEXTOS, textos, fmt, cuando, etiqueta, chip, mostrar };
});
