/* Progreso de la lista de reproducción: qué temas se vieron qué día y cuándo vuelve cada uno a repaso.
 *
 * Funciones puras: no tocan el DOM ni localStorage, y no cambian el estado que reciben (devuelven uno
 * nuevo). Las fechas son "AAAA-MM-DD" en hora local; quien llama decide qué día es hoy.
 *
 * Estado (v3): { v: 3, cur: "<temaId>", dias: { "2026-11-12": ["t01", "t02"] },
 *                repaso: { "t01": { nivel: 0|1|2, proxima: "AAAA-MM-DD", historial: [{ fecha, aciertos, total }] } } }
 * Formatos viejos, que se migran al cargar:
 *   v2: { v: 2, cur, dias }  (sin repaso)
 *   v1: { dia, vistos: [índices del día `dia`], cur: índice }
 *
 * Repaso: un Leitner de 3 niveles con las preguntas de cada tema. Si hay algún error, el tema vuelve a
 * nivel 0 y toca mañana; si acierta todo, sube un nivel (hasta 2) y vuelve a los 3 días (nivel 1) o a
 * los 7 (nivel 2). Los temas sin preguntas no entran al repaso: se ven una vez y quedan al día.
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
  const INTERVALO = [1, 3, 7];          // días hasta el próximo repaso, según el nivel
  const NIVEL_MAX = INTERVALO.length - 1;

  // temas: [{ id, preguntas?, … }] (o directamente los ids) en el orden en que se ven
  const idsDe = temas => (temas || []).map(t => (typeof t === "string" ? t : t.id));
  const esFecha = f => typeof f === "string" && FECHA_RE.test(f);
  const conPreguntas = t => !!t && typeof t === "object" && Array.isArray(t.preguntas) && t.preguntas.length > 0;
  const esEntero = (x, min, max) => Number.isInteger(x) && x >= min && x <= max;

  function vacio(temas) {
    const ids = idsDe(temas);
    return { v: 3, cur: ids.length ? ids[0] : null, dias: {}, repaso: {} };
  }

  function limpiarRepaso(r) {
    const out = {};
    if (!r || typeof r !== "object" || Array.isArray(r)) return out;
    for (const id of Object.keys(r)) {
      const x = r[id];
      if (!id || !x || typeof x !== "object" || !esEntero(x.nivel, 0, NIVEL_MAX) || !esFecha(x.proxima)) continue;
      const historial = (Array.isArray(x.historial) ? x.historial : [])
        .filter(h => h && esFecha(h.fecha) && esEntero(h.total, 1, 1000) && esEntero(h.aciertos, 0, h.total))
        .map(h => ({ fecha: h.fecha, aciertos: h.aciertos, total: h.total }));
      out[id] = { nivel: x.nivel, proxima: x.proxima, historial };
    }
    return out;
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
      if (d.v >= 3) st.repaso = limpiarRepaso(d.repaso);   // v2 no tenía repaso: queda vacío
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

  function sumarDias(fecha, n) {
    const [a, m, d] = fecha.split("-").map(Number);
    return new Date(Date.UTC(a, m - 1, d) + n * DIA_MS).toISOString().slice(0, 10);
  }
  const diaAnterior = fecha => sumarDias(fecha, -1);

  /** Días de `desde` a `hasta` (negativo si `hasta` es antes). */
  function diasEntre(desde, hasta) {
    const utc = f => { const [a, m, d] = f.split("-").map(Number); return Date.UTC(a, m - 1, d); };
    return Math.round((utc(hasta) - utc(desde)) / DIA_MS);
  }

  /** Registra las respuestas de un tema: con algún error vuelve a nivel 0 (mañana); con todo bien sube
   *  un nivel, hasta 2 (a los 3 días desde nivel 1, a los 7 desde nivel 2). No marca el tema como visto. */
  function responder(estado, temaId, aciertos, total, fecha) {
    if (!esFecha(fecha)) throw new TypeError("fecha inválida: " + fecha);
    if (typeof temaId !== "string" || !temaId) throw new TypeError("tema inválido: " + temaId);
    if (!esEntero(total, 1, 1000) || !esEntero(aciertos, 0, total)) {
      throw new RangeError(`respuestas inválidas: ${aciertos} de ${total}`);
    }
    const antes = (estado.repaso || {})[temaId];
    const nivel = aciertos < total ? 0 : Math.min((antes ? antes.nivel : 0) + 1, NIVEL_MAX);
    const historial = (antes ? antes.historial : []).concat([{ fecha, aciertos, total }]);
    const repaso = Object.assign({}, estado.repaso, {
      [temaId]: { nivel, proxima: sumarDias(fecha, INTERVALO[nivel]), historial },
    });
    return Object.assign({}, estado, { repaso });
  }

  function vistosHasta(estado, fecha) {
    const s = new Set();
    for (const f of Object.keys(estado.dias)) {
      if (f > fecha) continue;                       // un reloj adelantado no cuenta
      for (const id of estado.dias[f]) s.add(id);
    }
    return s;
  }

  /** Lo que toca hoy, en orden: primero los repasos vencidos (proxima <= hoy; los más atrasados primero,
   *  y a igual fecha, en el orden de la lista), después los temas que nunca se vieron, en orden. Un tema
   *  entra al repaso solo si tiene preguntas. */
  function pendientesHoy(estado, temas, fecha) {
    const lista = (temas || []).map(t => (typeof t === "string" ? { id: t } : t));
    const repaso = estado.repaso || {}, vistos = vistosHasta(estado, fecha);
    const vencidos = lista
      .map((t, i) => ({ t, i, r: conPreguntas(t) ? repaso[t.id] : null }))
      .filter(x => x.r && x.r.proxima <= fecha)
      .sort((a, b) => (a.r.proxima < b.r.proxima ? -1 : a.r.proxima > b.r.proxima ? 1 : a.i - b.i))
      .map(x => x.t.id);
    const nuevos = lista.filter(t => !vistos.has(t.id) && !(conPreguntas(t) && repaso[t.id])).map(t => t.id);
    return vencidos.concat(nuevos);
  }

  /** El primer tema de pendientesHoy, o null si hoy no queda nada. */
  function queTocaHoy(estado, temas, fecha) {
    const p = pendientesHoy(estado, temas, fecha);
    return p.length ? p[0] : null;
  }

  /** Cómo está un tema hoy: { estado: "pendiente" | "aldia" | "nuevo", proxima?: "AAAA-MM-DD" }.
   *  pendiente = le toca repaso hoy; aldia = se vio (y si tiene repaso, todavía no le toca); nuevo = nunca se vio. */
  function estadoTema(estado, tema, fecha) {
    const t = typeof tema === "string" ? { id: tema } : tema;
    const r = conPreguntas(t) ? (estado.repaso || {})[t.id] : null;
    if (r) return r.proxima <= fecha ? { estado: "pendiente", proxima: r.proxima } : { estado: "aldia", proxima: r.proxima };
    return vistosHasta(estado, fecha).has(t.id) ? { estado: "aldia" } : { estado: "nuevo" };
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

  /** Lo que se comparte en el piloto: { titulo, generado, dias (en orden), racha, repaso }. */
  function exportar(estado, datos) {
    datos = datos || {};
    const fecha = datos.fecha || fechaLocal(new Date());
    const dias = {};
    for (const f of Object.keys(estado.dias).sort()) dias[f] = estado.dias[f].slice();
    const repaso = {};
    for (const id of Object.keys(estado.repaso || {}).sort()) {
      const r = estado.repaso[id];
      repaso[id] = { nivel: r.nivel, proxima: r.proxima, historial: r.historial.map(h => Object.assign({}, h)) };
    }
    return {
      titulo: datos.titulo || "",
      generado: datos.generado || new Date().toISOString(),
      dias,
      racha: racha(estado, fecha),
      repaso,
    };
  }

  function fechaLocal(d) {
    const p = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  return { cargar, vacio, marcarVisto, responder, queTocaHoy, pendientesHoy, estadoTema, racha, exportar,
           fechaLocal, diaAnterior, sumarDias, diasEntre, INTERVALO };
});
