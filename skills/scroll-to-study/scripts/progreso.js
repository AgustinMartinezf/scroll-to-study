/* Progreso de la lista de reproducción: qué temas se vieron qué día.
 *
 * Funciones puras: no tocan el DOM ni localStorage, y no cambian el estado que reciben (devuelven uno
 * nuevo). Las fechas son "AAAA-MM-DD" en hora local; quien llama decide qué día es hoy.
 *
 * Estado (v2): { v: 2, cur: "<temaId>", dias: { "2026-11-12": ["t01", "t02"] } }
 * Formato viejo (v1), que se migra al cargar: { dia, vistos: [índices del día `dia`], cur: índice }
 *
 * Funciona suelto: con require() exporta las funciones; cargado en una página las deja en window.Progreso.
 */
(function (raiz, hacer) {
  if (typeof module === "object" && module.exports) module.exports = hacer();
  else raiz.Progreso = hacer();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const FECHA_RE = /^\d{4}-\d{2}-\d{2}$/;
  const DIA_MS = 86400000;

  // temas: [{ id, … }] (o directamente los ids) en el orden en que se ven
  const idsDe = temas => (temas || []).map(t => (typeof t === "string" ? t : t.id));
  const esFecha = f => typeof f === "string" && FECHA_RE.test(f);

  function vacio(temas) {
    const ids = idsDe(temas);
    return { v: 2, cur: ids.length ? ids[0] : null, dias: {} };
  }

  /** json: el texto guardado (o el objeto ya leído, o null). Nunca falla: lo que no entiende lo descarta. */
  function cargar(json, temas) {
    const ids = idsDe(temas);
    let d = json;
    if (typeof json === "string") {
      try { d = JSON.parse(json); } catch (e) { d = null; }
    }
    const st = vacio(ids);
    if (!d || typeof d !== "object" || Array.isArray(d)) return st;
    if (typeof d.v === "number" && d.v >= 2) {
      // los ids que ya no están en la lista se conservan: son historia del piloto
      if (d.dias && typeof d.dias === "object") {
        for (const f of Object.keys(d.dias)) {
          const lista = d.dias[f];
          if (!esFecha(f) || !Array.isArray(lista)) continue;
          const limpia = [...new Set(lista.filter(x => typeof x === "string" && x))];
          if (limpia.length) st.dias[f] = limpia;
        }
      }
      if (ids.includes(d.cur)) st.cur = d.cur;
      return st;
    }
    // v1: los índices eran posiciones en la lista; se pasan a ids y se guardan bajo el día en que se vieron
    if (Array.isArray(d.vistos) && esFecha(d.dia)) {
      const vistos = [];
      for (const i of d.vistos) {
        if (Number.isInteger(i) && i >= 0 && i < ids.length && !vistos.includes(ids[i])) vistos.push(ids[i]);
      }
      if (vistos.length) st.dias[d.dia] = vistos;
    }
    if (Number.isInteger(d.cur) && d.cur >= 0 && d.cur < ids.length) st.cur = ids[d.cur];
    return st;
  }

  function marcarVisto(estado, temaId, fecha) {
    if (!esFecha(fecha)) throw new TypeError("fecha inválida: " + fecha);
    const dias = Object.assign({}, estado.dias);
    const ese = dias[fecha] || [];
    if (!ese.includes(temaId)) dias[fecha] = ese.concat([temaId]);
    return Object.assign({}, estado, { dias });
  }

  /** El primer tema que nunca se vio; si se vieron todos, el que se vio hace más tiempo (empate: el primero). */
  function queTocaHoy(estado, temas, fecha) {
    const ids = idsDe(temas);
    if (!ids.length) return null;
    const ultima = {};
    for (const f of Object.keys(estado.dias)) {
      if (f > fecha) continue;                       // un reloj adelantado no cuenta
      for (const id of estado.dias[f]) if (!ultima[id] || f > ultima[id]) ultima[id] = f;
    }
    const nunca = ids.find(id => !ultima[id]);
    if (nunca !== undefined) return nunca;
    let mejor = ids[0];
    for (const id of ids) if (ultima[id] < ultima[mejor]) mejor = id;
    return mejor;
  }

  function diaAnterior(fecha) {
    const [a, m, d] = fecha.split("-").map(Number);
    return new Date(Date.UTC(a, m - 1, d) - DIA_MS).toISOString().slice(0, 10);
  }

  /** Días seguidos con al menos un video visto, terminando hoy. Si hoy todavía no se vio nada, la racha
   *  que llega hasta ayer sigue viva (se corta recién cuando pasa un día entero sin ver nada). */
  function racha(estado, fecha) {
    if (!esFecha(fecha)) throw new TypeError("fecha inválida: " + fecha);
    const con = f => (estado.dias[f] || []).length > 0;
    let f = con(fecha) ? fecha : diaAnterior(fecha), n = 0;
    while (con(f)) { n++; f = diaAnterior(f); }
    return n;
  }

  /** Lo que se comparte en el piloto: { titulo, generado, dias (en orden), racha }. */
  function exportar(estado, datos) {
    datos = datos || {};
    const fecha = datos.fecha || fechaLocal(new Date());
    const dias = {};
    for (const f of Object.keys(estado.dias).sort()) dias[f] = estado.dias[f].slice();
    return {
      titulo: datos.titulo || "",
      generado: datos.generado || new Date().toISOString(),
      dias,
      racha: racha(estado, fecha),
    };
  }

  function fechaLocal(d) {
    const p = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  return { cargar, vacio, marcarVisto, queTocaHoy, racha, exportar, fechaLocal, diaAnterior };
});
