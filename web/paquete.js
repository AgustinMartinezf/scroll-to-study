/* Validación de un paquete .s2s.json (lo arma `s2s.py paquete`; el formato está en scripts/paquete.py).
 *
 * Acepta v2 (cada video trae "preguntas") y v1 (de antes de las preguntas: se lee como si no tuviera).
 *
 * Función pura: no toca el DOM ni el almacenamiento. validar(d) devuelve null si el paquete sirve, o
 * { codigo, campo } con lo primero que falla (y hecho_con, la versión de scroll-to-study que lo armó, si el
 * paquete la trae); mensaje(error, idioma) lo dice para la persona.
 *
 * Versiones: un paquete con "v" mayor que la última que se acepta lo armó un plugin más nuevo que la app
 * ("version_nueva": lo viejo es la app, que se actualiza abriéndola con internet); uno con "v" que ya no se
 * acepta, o que no es un número, es "version" (lo viejo es el paquete: se arma de nuevo).
 *
 * Funciona suelto: con require() exporta las funciones; cargado en una página las deja en window.Paquete.
 */
(function (raiz, hacer) {
  if (typeof module === "object" && module.exports) module.exports = hacer();
  else raiz.Paquete = hacer();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const VERSION = 2;                // la que arma s2s.py paquete hoy
  const VERSIONES = [1, 2];         // las que se pueden importar
  const MAX_PREGUNTAS = 10, OPCIONES = [2, 6];
  const IDIOMAS = ["es", "en"];
  const ID_RE = /^[A-Za-z0-9_-]{1,40}$/;
  const esTexto = x => typeof x === "string";
  const mal = (codigo, campo) => ({ codigo, campo: campo || "" });
  const ULTIMA = Math.max.apply(null, VERSIONES);
  const lleno = x => esTexto(x) && x.trim().length > 0;

  /** null si la pregunta sirve, o el nombre del campo que está mal. */
  function campoMalo(q) {
    if (!q || typeof q !== "object" || Array.isArray(q)) return "";
    if (!esTexto(q.id)) return ".id";
    if (!lleno(q.texto)) return ".texto";
    if (!Array.isArray(q.opciones) || q.opciones.length < OPCIONES[0] || q.opciones.length > OPCIONES[1] ||
        !q.opciones.every(lleno)) return ".opciones";
    if (!Number.isInteger(q.correcta) || q.correcta < 0 || q.correcta >= q.opciones.length) return ".correcta";
    if (!lleno(q.explicacion)) return ".explicacion";
    if (typeof q.general !== "boolean") return ".general";
    return null;
  }

  function validar(d) {
    if (!d || typeof d !== "object" || Array.isArray(d)) return mal("no_es_paquete");
    if (!("v" in d) || !("videos" in d)) return mal("no_es_paquete");
    if (!VERSIONES.includes(d.v)) {
      const e = mal(Number.isInteger(d.v) && d.v > ULTIMA ? "version_nueva" : "version", String(d.v));
      if (esTexto(d.hecho_con) && /^[0-9A-Za-z.+-]{1,40}$/.test(d.hecho_con)) e.hecho_con = d.hecho_con;
      return e;
    }
    if (!esTexto(d.titulo) || !d.titulo.trim()) return mal("campo", "titulo");
    if (d.titulo.length > 200) return mal("campo", "titulo");
    if (!IDIOMAS.includes(d.idioma)) return mal("campo", "idioma");
    if (!esTexto(d.generado) || isNaN(Date.parse(d.generado))) return mal("campo", "generado");
    if (!Array.isArray(d.videos)) return mal("campo", "videos");
    if (!d.videos.length) return mal("vacio");
    const ids = new Set();
    for (let i = 0; i < d.videos.length; i++) {
      const x = d.videos[i], donde = `videos[${i}]`;
      if (!x || typeof x !== "object" || Array.isArray(x)) return mal("campo", donde);
      if (!esTexto(x.id) || !ID_RE.test(x.id)) return mal("campo", donde + ".id");
      if (ids.has(x.id)) return mal("repetido", x.id);
      ids.add(x.id);
      if (!esTexto(x.titulo) || !x.titulo.trim()) return mal("campo", donde + ".titulo");
      if (!esTexto(x.pregunta)) return mal("campo", donde + ".pregunta");
      if (typeof x.duracion !== "number" || !isFinite(x.duracion) || x.duracion < 0) return mal("campo", donde + ".duracion");
      if (!esTexto(x.html) || !/<html[\s>]/i.test(x.html.slice(0, 2000))) return mal("campo", donde + ".html");
      if (d.v === 1) continue;
      if (!Array.isArray(x.preguntas) || x.preguntas.length > MAX_PREGUNTAS) return mal("campo", donde + ".preguntas");
      for (let k = 0; k < x.preguntas.length; k++) {
        const c = campoMalo(x.preguntas[k]);
        if (c !== null) return mal("campo", `${donde}.preguntas[${k}]${c}`);
      }
    }
    return null;
  }

  /** Lee el texto de un archivo: { paquete } si sirve, { error: { codigo, campo } } si no. */
  function leer(texto) {
    let d;
    try { d = JSON.parse(texto); } catch (e) { return { error: mal("no_es_json") }; }
    const error = validar(d);
    return error ? { error } : { paquete: d };
  }

  /** Los metadatos que se guardan aparte de los videos (todo menos el html). Un paquete v1 queda con
   *  "preguntas": [] en cada video, así la app trata igual a los dos. */
  function metadatos(d, importado) {
    return {
      titulo: d.titulo, idioma: d.idioma, generado: d.generado, importado,
      videos: d.videos.map(x => ({
        id: x.id, titulo: x.titulo, pregunta: x.pregunta, duracion: x.duracion,
        preguntas: (x.preguntas || []).map(q => ({ id: q.id, texto: q.texto, opciones: q.opciones.slice(),
                                                    correcta: q.correcta, explicacion: q.explicacion, general: q.general })),
      })),
    };
  }

  const MENSAJES = {
    es: {
      no_es_json: "Ese archivo no es un paquete de scroll to study. Elegí el .s2s.json que armaste en la compu.",
      no_es_paquete: "Ese archivo no es un paquete de scroll to study. Elegí el .s2s.json que armaste en la compu.",
      version_nueva: "Este paquete es de una versión más nueva que la app. Cerrá la app y abrila con internet para actualizarla.",
      version: "Este paquete es de una versión vieja ({c}) que la app ya no lee: armalo de nuevo con s2s.py paquete.",
      campo: "El paquete está dañado (falta o está mal «{c}»): armalo de nuevo con s2s.py paquete.",
      vacio: "El paquete no tiene videos.",
      repetido: "El paquete tiene el video «{c}» repetido: armalo de nuevo con s2s.py paquete.",
      hecho_con: " (Lo armó scroll-to-study {h}.)",
    },
    en: {
      no_es_json: "That file is not a scroll to study package. Pick the .s2s.json you made on your computer.",
      no_es_paquete: "That file is not a scroll to study package. Pick the .s2s.json you made on your computer.",
      version_nueva: "This package is from a newer version than the app. Close the app and open it with internet to update it.",
      version: "This package is from an old version ({c}) the app no longer reads: make it again with s2s.py paquete.",
      campo: "The package is damaged (“{c}” is missing or wrong): make it again with s2s.py paquete.",
      vacio: "The package has no videos.",
      repetido: "The package has the video “{c}” twice: make it again with s2s.py paquete.",
      hecho_con: " (Made by scroll-to-study {h}.)",
    },
  };

  /** El error de validar/leer, dicho para la persona en "es" o "en". */
  function mensaje(error, idioma) {
    const m = MENSAJES[idioma] || MENSAJES.es;
    const e = error || {};
    let s = (m[e.codigo] || m.no_es_paquete).replace("{c}", () => e.campo || "");
    if ((e.codigo === "version" || e.codigo === "version_nueva") && e.hecho_con) s += m.hecho_con.replace("{h}", () => e.hecho_con);
    return s;
  }

  return { VERSION, VERSIONES, validar, leer, metadatos, mensaje };
});
