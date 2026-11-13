/* Lo que pasa entre la página y el iframe del video, igual en la lista de la compu (videos/index.html) y
 * en la app del teléfono (web/).
 *
 * El video (PLAYER_JS de reproductor.py) avisa con postMessage { s2s: { tipo, t, video } }:
 *   listo      cargó y está quieto en t = 0
 *   inicio     empezó desde el principio          sigue   siguió después de una pausa
 *   pausa      se pausó                            fin     terminó
 *   tiempo     sigue sonando: va por t (cada 2 s)  salto   se movió a t (barra, doble toque, teclado)
 * Cada aviso trae también duracion y reproducidos: los segundos que sonaron de verdad (sin contar dos
 * veces lo que se vio dos veces). La página le pide { s2s: "play" }, { s2s: "play", desde: t },
 * { s2s: "pausa" }, o le pasa un toque { s2s: "toque", x } o una tecla { s2s: "tecla", tecla }.
 *
 * Visto: un video cuenta como visto (y muestra sus preguntas) solo si sonó al menos MINIMO_VISTO de su
 * duración. Si no, queda en el final con "Ver de nuevo". Los videos hechos antes de este dato cuentan
 * como siempre.
 *
 * Cortes: si llega un segundo "listo" del mismo video sin que la página lo haya vuelto a abrir, el iframe
 * se recargó solo (iOS mata el proceso del video cuando se queda sin memoria y lo vuelve a cargar). Se
 * retoma desde el último tiempo conocido, no desde 0, y se anota { fecha, video, t, ua } en un registro de
 * diagnóstico (localStorage, aparte del progreso, con tope de TOPE_CORTES). "Exportar progreso" lo incluye
 * como "cortes". Nada sale del navegador.
 *
 * Funciona suelto: con require() exporta las funciones puras; cargado en una página deja todo en
 * window.Reproduccion.
 */
(function (raiz, hacer) {
  if (typeof module === "object" && module.exports) module.exports = hacer();
  else raiz.Reproduccion = hacer();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const TOPE_CORTES = 50;
  const MINIMO_VISTO = 0.7;
  const numero = x => typeof x === "number" && isFinite(x);

  /** El registro guardado (texto, o ya leído) -> lista de cortes válidos, los últimos TOPE_CORTES. */
  function cargarCortes(json) {
    let d = json;
    if (typeof json === "string") {
      try { d = JSON.parse(json); } catch (e) { d = null; }
    }
    if (!Array.isArray(d)) return [];
    return d.filter(c => c && typeof c === "object" && typeof c.fecha === "string" && typeof c.video === "string" &&
                         numero(c.t) && c.t >= 0 && typeof c.ua === "string")
      .map(c => ({ fecha: c.fecha, video: c.video, t: c.t, ua: c.ua }))
      .slice(-TOPE_CORTES);
  }

  /** Suma un corte al final; si pasa del tope, se van los más viejos. No cambia la lista que recibe. */
  function sumarCorte(lista, corte) {
    return (lista || []).concat([corte]).slice(-TOPE_CORTES);
  }

  /** Si lo que sonó alcanza para contar el video como visto. Sin el dato (videos de antes), sí. */
  function contarComoVisto(reproducidos, duracion) {
    if (!numero(reproducidos) || !numero(duracion) || duracion <= 0) return true;
    return reproducidos >= MINIMO_VISTO * duracion - 0.05;
  }

  /** Engancha la página al iframe del video.
   *  o = { iframe, claveCortes() -> clave de localStorage del registro,
   *        alFin(visto, detalle)   el video terminó; visto: si sonó lo suficiente (contarComoVisto),
   *        alCambiar()             cambió `sonando` (para mostrar u ocultar la capa de gestos),
   *        activo()?               false para ignorar los mensajes (la app sin paquete) }
   *  Devuelve { cargar(id, auto), detener(), cortes(), enviar(msg), sonando() }: cargar se llama justo
   *  antes de poner el src del iframe; auto = reproducir apenas esté listo. */
  function conectar(o) {
    const v = o.iframe;
    let id = null, arrancar = false, esperando = false, ultimoT = 0, terminado = false, sonando = false;
    let ultimoR = 0, base = 0;   // reproducidos según el último aviso; lo que sonó antes de una recarga
    const enviar = m => { if (v.contentWindow) v.contentWindow.postMessage(m, "*"); };
    function cortes() {
      try { return cargarCortes(localStorage.getItem(o.claveCortes())); } catch (e) { return []; }
    }
    function anotarCorte(t) {
      const c = { fecha: new Date().toISOString(), video: id, t, ua: String(navigator.userAgent || "") };
      try { localStorage.setItem(o.claveCortes(), JSON.stringify(sumarCorte(cortes(), c))); } catch (e) {}
    }
    function ponerSonando(x) {
      if (x === sonando) return;
      sonando = x;
      if (o.alCambiar) o.alCambiar();
    }
    function cargar(nuevo, auto) {
      id = nuevo; arrancar = !!auto; esperando = true; ultimoT = 0; terminado = false; ultimoR = 0; base = 0;
      ponerSonando(false);
    }
    function detener() { id = null; esperando = false; ponerSonando(false); }

    addEventListener("message", e => {
      if (e.source !== v.contentWindow || !e.data || !e.data.s2s || typeof e.data.s2s !== "object") return;
      if (id === null || (o.activo && !o.activo())) return;
      const d = e.data.s2s, tipo = d.tipo;
      if (tipo !== "listo" && numero(d.t) && d.t >= 0) ultimoT = d.t;
      if (tipo !== "listo" && numero(d.reproducidos) && d.reproducidos >= 0) ultimoR = d.reproducidos;
      if (tipo === "listo") {
        ponerSonando(false);
        if (esperando) {                      // el primero: lo abrió la página
          esperando = false;
          if (arrancar) enviar({ s2s: "play" });
        } else {                              // otro más: el iframe se recargó solo
          anotarCorte(ultimoT);
          base += ultimoR; ultimoR = 0;      // lo que ya había sonado sigue contando
          if (!terminado) enviar({ s2s: "play", desde: ultimoT });
        }
        return;
      }
      if (tipo === "inicio" || tipo === "sigue" || tipo === "tiempo") { terminado = false; ponerSonando(true); return; }
      if (tipo === "pausa") { ponerSonando(false); return; }
      if (tipo === "fin") {
        terminado = true; ponerSonando(false);
        const r = numero(d.reproducidos) ? base + d.reproducidos : undefined;
        o.alFin(contarComoVisto(r, d.duracion), d);
      }
    });
    return { cargar, detener, cortes, enviar, sonando: () => sonando };
  }

  return { TOPE_CORTES, MINIMO_VISTO, cargarCortes, sumarCorte, contarComoVisto, conectar };
});
