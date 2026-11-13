/* Lo que pasa entre la página y el iframe del video, igual en la lista de la compu (videos/index.html) y
 * en la app del teléfono (web/).
 *
 * El video (PLAYER_JS de reproductor.py) avisa con postMessage { s2s: { tipo, t, video } }:
 *   listo      cargó y está quieto en t = 0
 *   inicio     empezó desde el principio          sigue   siguió después de una pausa
 *   pausa      se pausó                            fin     terminó
 *   tiempo     sigue sonando: va por t (cada 2 s)  salto   se movió a t (barra, doble toque, teclado)
 *   deslizar   un gesto sobre su tapa en el modo feed { dx, dy, ms, y0 }
 *   tecla      una tecla que es de la página (↑, ↓, Esc…) { tecla }     rueda   la rueda del mouse { dy }
 * Cada aviso trae también duracion y reproducidos: los segundos que sonaron de verdad (sin contar dos
 * veces lo que se vio dos veces). La página le pide { s2s: "play" }, { s2s: "play", desde: t },
 * { s2s: "pausa" }, le pasa un toque { s2s: "toque", x } o una tecla { s2s: "tecla", tecla }, y le dice
 * si está en el modo feed { s2s: "feed", activo }.
 *
 * Dos modos:
 *   normal  el reproductor en la página, con la lista abajo. No hay gestos sobre el video: la página
 *           scrollea normal y los toques llegan al video (pausa, barra, doble toque). Para cambiar de
 *           video, los botones.
 *   feed    "Pantalla completa": el video ocupa toda la pantalla (un contenedor fijo de 100dvh; iOS no
 *           tiene la API Fullscreen para lo que no es <video>). Deslizar arriba es el siguiente y abajo el
 *           anterior; mientras suena, una capa de gestos tapa el video salvo la franja de abajo (la barra)
 *           y le pasa los toques. Con el video quieto la capa no está (así el toque que lo arranca es del
 *           video, como pide iOS) y es el video el que avisa los gestos sobre su tapa. La X, o deslizar
 *           hacia abajo desde el borde de arriba, vuelve a la lista. En la compu: ↑/↓ o la rueda cambian de
 *           video y Esc sale. Las preguntas también se ven ahí, a pantalla completa.
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
  const UMBRAL = 80;          // px que hay que deslizar para cambiar de video
  const VELOCIDAD = 0.25;     // px/ms como mínimo (un arrastre lento no cambia de video)
  const TOQUE = 12;           // px: menos que eso es un toque
  const BORDE = 56;           // px desde arriba: deslizar hacia abajo desde ahí sale del modo feed
  const FRANJA = 56;          // px de abajo que la capa deja libres para la barra del video
  const numero = x => typeof x === "number" && isFinite(x);

  const TEXTOS = {
    es: { feed: "Pantalla completa", salir: "Volver a la lista" },
    en: { feed: "Full screen", salir: "Back to the list" },
  };

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

  /** Qué fue un gesto de dx, dy px en ms milisegundos: "toque", "siguiente" (hacia arriba), "anterior"
   *  (hacia abajo) o null (ni una cosa ni la otra: corto, lento o de costado). */
  function gesto(dx, dy, ms) {
    const ax = Math.abs(dx), ay = Math.abs(dy);
    if (ax < TOQUE && ay < TOQUE) return "toque";
    if (ay >= UMBRAL && ay > 1.5 * ax && ay / Math.max(ms, 1) >= VELOCIDAD) return dy < 0 ? "siguiente" : "anterior";
    return null;
  }

  const CSS = `
.s2s-capa { position:absolute; left:0; right:0; top:0; bottom:${FRANJA}px; z-index:3; display:none; touch-action:none;
  -webkit-tap-highlight-color:transparent; }
.s2s-salir { display:none; }
.caja.s2s-feed { position:fixed; inset:0; z-index:50; width:auto; max-width:none; height:100vh; height:100dvh;
  aspect-ratio:auto; margin:0; border:0; border-radius:0; background:#000;
  padding:env(safe-area-inset-top, 0px) 0 env(safe-area-inset-bottom, 0px); }
.caja.s2s-feed .s2s-capa { top:env(safe-area-inset-top, 0px); bottom:calc(${FRANJA}px + env(safe-area-inset-bottom, 0px)); }
.caja.s2s-feed .s2s-capa.activa { display:block; }
.caja.s2s-feed .s2s-salir { display:flex; align-items:center; justify-content:center; position:absolute; z-index:7;
  top:calc(env(safe-area-inset-top, 0px) + 10px); right:10px; width:44px; height:44px; padding:0; border:0;
  border-radius:50%; background:rgba(0,0,0,.55); color:#fff; font:700 22px/1 system-ui, sans-serif; cursor:pointer; }
.caja.s2s-feed .s2s-quiz { padding:calc(env(safe-area-inset-top, 0px) + 64px) max(16px, calc(50% - 300px))
  calc(env(safe-area-inset-bottom, 0px) + 18px); }
html.s2s-feed-abierto, html.s2s-feed-abierto body { overflow:hidden; }
`;

  function ponerCss(doc) {
    if (doc.getElementById("s2s-feed-css")) return;
    const s = doc.createElement("style"); s.id = "s2s-feed-css"; s.textContent = CSS;
    doc.head.append(s);
  }

  /** Engancha la página al iframe del video.
   *  o = { iframe, caja (el contenedor del iframe), botonFeed (el botón "Pantalla completa"), idioma,
   *        claveCortes() -> clave de localStorage del registro,
   *        hay(delta) -> si existe el video a delta de este,   mover(delta) abre ese video,
   *        alFin(visto, detalle)   el video terminó; visto: si sonó lo suficiente (contarComoVisto),
   *        activo()?               false para ignorar los mensajes (la app sin paquete) }
   *  Devuelve { cargar(id, auto), detener(), cortes(), enviar(msg), sonando(), feed(), entrar(), salir() }:
   *  cargar se llama justo antes de poner el src del iframe; auto = reproducir apenas esté listo. */
  function conectar(o) {
    const v = o.iframe, caja = o.caja, doc = caja.ownerDocument, tx = TEXTOS[o.idioma] || TEXTOS.es;
    let id = null, arrancar = false, esperando = false, ultimoT = 0, terminado = false, sonando = false;
    let ultimoR = 0, base = 0;   // reproducidos según el último aviso; lo que sonó antes de una recarga
    let nuevo = true;            // el video entiende "toque" y "feed" (los de antes solo "play" y "pausa")
    let enFeed = false;
    const enviar = m => { if (v.contentWindow) v.contentWindow.postMessage(m, "*"); };

    ponerCss(doc);
    const capa = doc.createElement("div"); capa.className = "s2s-capa";
    const salirBtn = doc.createElement("button"); salirBtn.type = "button"; salirBtn.className = "s2s-salir";
    salirBtn.textContent = "✕"; salirBtn.setAttribute("aria-label", tx.salir); salirBtn.title = tx.salir;
    caja.append(capa, salirBtn);
    if (!caja.hasAttribute("tabindex")) caja.tabIndex = -1;    // para las teclas del modo feed
    if (o.botonFeed) { o.botonFeed.textContent = tx.feed; o.botonFeed.onclick = () => entrar(); }

    function cortes() {
      try { return cargarCortes(localStorage.getItem(o.claveCortes())); } catch (e) { return []; }
    }
    function anotarCorte(t) {
      const c = { fecha: new Date().toISOString(), video: id, t, ua: String(navigator.userAgent || "") };
      try { localStorage.setItem(o.claveCortes(), JSON.stringify(sumarCorte(cortes(), c))); } catch (e) {}
    }
    const ponerCapa = () => capa.classList.toggle("activa", enFeed && sonando);
    function ponerSonando(x) { sonando = x; ponerCapa(); }
    function cargar(nuevoId, auto) {
      id = nuevoId; arrancar = !!auto; esperando = true; ultimoT = 0; terminado = false; ultimoR = 0; base = 0;
      ponerSonando(false);
    }
    function detener() { id = null; esperando = false; ponerSonando(false); }

    // --- modo feed ---------------------------------------------------------------------------------
    function entrar() {
      if (enFeed) return;
      enFeed = true;
      caja.classList.add("s2s-feed"); doc.documentElement.classList.add("s2s-feed-abierto");
      enviar({ s2s: "feed", activo: true }); ponerCapa();
      try { caja.focus({ preventScroll: true }); } catch (e) {}
    }
    function salir() {
      if (!enFeed) return;
      enFeed = false;
      caja.classList.remove("s2s-feed"); doc.documentElement.classList.remove("s2s-feed-abierto");
      v.style.transition = ""; v.style.transform = "";
      enviar({ s2s: "feed", activo: false }); ponerCapa();
      if (o.botonFeed) { try { o.botonFeed.focus({ preventScroll: true }); } catch (e) {} }
    }
    salirBtn.onclick = salir;
    const conMovimiento = () => !(doc.defaultView.matchMedia && doc.defaultView.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let pasando = false;
    // cambia de video con una transición vertical: el actual sale para un lado y el nuevo entra del otro
    function pasar(delta) {
      if (!enFeed || pasando || caja.querySelector(".s2s-quiz")) return;
      if (!o.hay(delta)) {      // no hay más para ese lado: un rebote corto
        if (conMovimiento()) {
          v.style.transition = "transform .12s ease-out"; v.style.transform = `translateY(${-delta * 6}%)`;
          setTimeout(() => { v.style.transform = ""; }, 120);
        }
        return;
      }
      if (!conMovimiento()) { o.mover(delta); return; }
      pasando = true;
      v.style.transition = "transform .18s ease-in"; v.style.transform = `translateY(${-delta * 100}%)`;
      setTimeout(() => {
        o.mover(delta);
        v.style.transition = "none"; v.style.transform = `translateY(${delta * 100}%)`;
        void v.offsetHeight;
        v.style.transition = "transform .22s ease-out"; v.style.transform = "";
        setTimeout(() => { pasando = false; }, 220);
      }, 180);
    }
    // un gesto (de la capa o de la tapa del video): y0 se mide desde el borde de arriba del video
    function gestoFeed(dx, dy, ms, x, y0) {
      if (!enFeed) return;
      const g = gesto(dx, dy, ms);
      if (g === "toque") { if (x !== null) enviar(nuevo ? { s2s: "toque", x } : { s2s: "pausa" }); return; }
      if (g === "anterior" && y0 < BORDE) { salir(); return; }
      if (g) pasar(g === "siguiente" ? 1 : -1);
    }
    let ini = null;
    capa.addEventListener("pointerdown", e => {
      ini = { x: e.clientX, y: e.clientY, t: e.timeStamp };
      try { capa.setPointerCapture(e.pointerId); } catch (err) {}
    });
    capa.addEventListener("pointercancel", () => { ini = null; });
    capa.addEventListener("pointerup", e => {
      if (!ini) return;
      const a = ini, r = v.getBoundingClientRect(); ini = null;
      gestoFeed(e.clientX - a.x, e.clientY - a.y, e.timeStamp - a.t, (e.clientX - r.left) / r.width, a.y - r.top);
    });
    let rueda = 0, ruedaHasta = 0;
    function girar(dy) {
      const ya = Date.now();
      if (ya < ruedaHasta) return;
      rueda += dy;
      if (Math.abs(rueda) >= 50) { pasar(rueda > 0 ? 1 : -1); rueda = 0; ruedaHasta = ya + 700; }
    }
    caja.addEventListener("wheel", e => { if (!enFeed) return; e.preventDefault(); girar(e.deltaY); }, { passive: false });
    function teclaFeed(k) {
      if (!enFeed) return false;
      if (k === "Escape") { salir(); return true; }
      if (k === "ArrowDown" || k === "PageDown") { pasar(1); return true; }
      if (k === "ArrowUp" || k === "PageUp") { pasar(-1); return true; }
      return false;
    }
    // ← → y espacio van al video aunque el foco esté en la página (salvo en un campo, o en un botón para
    // el espacio, o con las preguntas a la vista)
    doc.addEventListener("keydown", e => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const t = e.target, tag = t && t.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
      if (teclaFeed(e.key)) { e.preventDefault(); return; }
      if (caja.querySelector(".s2s-quiz") || id === null) return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight" || (e.key === " " && tag !== "BUTTON" && tag !== "A")) {
        e.preventDefault(); enviar({ s2s: "tecla", tecla: e.key });
      }
    });

    addEventListener("message", e => {
      if (e.source !== v.contentWindow || !e.data || !e.data.s2s || typeof e.data.s2s !== "object") return;
      if (id === null || (o.activo && !o.activo())) return;
      const d = e.data.s2s, tipo = d.tipo;
      if (tipo !== "listo" && numero(d.t) && d.t >= 0) ultimoT = d.t;
      if (tipo !== "listo" && numero(d.reproducidos) && d.reproducidos >= 0) ultimoR = d.reproducidos;
      if (tipo === "listo") {
        ponerSonando(false);
        nuevo = numero(d.duracion);
        if (enFeed) enviar({ s2s: "feed", activo: true });
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
      if (tipo === "deslizar") {
        if ([d.dx, d.dy, d.ms, d.y0].every(numero)) gestoFeed(d.dx, d.dy, d.ms, null, d.y0);
        return;
      }
      if (tipo === "tecla") { if (typeof d.tecla === "string") teclaFeed(d.tecla); return; }
      if (tipo === "rueda") { if (enFeed && numero(d.dy)) girar(d.dy); return; }
      if (tipo === "fin") {
        terminado = true; ponerSonando(false);
        const r = numero(d.reproducidos) ? base + d.reproducidos : undefined;
        o.alFin(contarComoVisto(r, d.duracion), d);
      }
    });
    return { cargar, detener, cortes, enviar, sonando: () => sonando, feed: () => enFeed, entrar, salir };
  }

  return { TOPE_CORTES, MINIMO_VISTO, UMBRAL, VELOCIDAD, BORDE, TEXTOS, cargarCortes, sumarCorte, contarComoVisto,
           gesto, conectar };
});
