/* Validación de un paquete .s2s.json (lo arma `s2s.py paquete`; el formato está en scripts/paquete.py).
 *
 * Función pura: no toca el DOM ni el almacenamiento. validar(d) devuelve null si el paquete sirve, o
 * { codigo, campo } con lo primero que falla; la app traduce el código a un mensaje.
 *
 * Funciona suelto: con require() exporta las funciones; cargado en una página las deja en window.Paquete.
 */
(function (raiz, hacer) {
  if (typeof module === "object" && module.exports) module.exports = hacer();
  else raiz.Paquete = hacer();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const VERSION = 1;
  const IDIOMAS = ["es", "en"];
  const ID_RE = /^[A-Za-z0-9_-]{1,40}$/;
  const esTexto = x => typeof x === "string";
  const mal = (codigo, campo) => ({ codigo, campo: campo || "" });

  function validar(d) {
    if (!d || typeof d !== "object" || Array.isArray(d)) return mal("no_es_paquete");
    if (!("v" in d) || !("videos" in d)) return mal("no_es_paquete");
    if (d.v !== VERSION) return mal("version", String(d.v));
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

  /** Los metadatos que se guardan aparte de los videos (todo menos el html). */
  function metadatos(d, importado) {
    return {
      titulo: d.titulo, idioma: d.idioma, generado: d.generado, importado,
      videos: d.videos.map(x => ({ id: x.id, titulo: x.titulo, pregunta: x.pregunta, duracion: x.duracion })),
    };
  }

  return { VERSION, validar, leer, metadatos };
});
