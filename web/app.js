/* scroll to study en el teléfono: un reproductor vacío que guarda en el propio teléfono los videos que
 * cada persona importa (un .s2s.json armado con `s2s.py paquete`). Nada se sube a ningún lado.
 *
 * - IndexedDB "s2s-app": "paquetes" (metadatos, clave = titulo) y "videos" (el html de cada video,
 *   clave = JSON.stringify([titulo, id])). Un paquete por materia; reimportar el mismo título lo reemplaza.
 * - El progreso es el de progreso.js, en localStorage con la clave "s2s:" + titulo, igual que la lista
 *   de la compu (cada navegador tiene el suyo).
 * - Después de cada video, si el tema trae preguntas (paquete v2), se muestran encima del reproductor con
 *   cuestionario.js, igual que en la lista de la compu, y el resultado decide cuándo vuelve el tema.
 * - Lo que pasa con el iframe del video (los avisos, retomarlo si se recarga solo y el registro de cortes)
 *   está en reproduccion.js, compartido con la lista de la compu.
 * - Cada video corre en un iframe sandbox (sin allow-same-origin) desde una URL blob: no puede leer los
 *   otros paquetes ni el progreso. Habla con la lista por postMessage, como en videos/index.html.
 */
(function () {
  "use strict";
  const P = window.Progreso, PQ = window.Paquete, C = window.Cuestionario;

  const TEXTOS = {
    es: {
      importar: "Importar videos", elegir: "Videos guardados", borrar: "Borrar",
      confirmarBorrar: "¿Borrar «{t}» de este teléfono? Si lo volvés a importar, tu progreso sigue.",
      borrado: "Se borró «{t}».",
      importado: "Listo: «{t}», {n} videos guardados en este teléfono.",
      actualizado: "Se actualizó «{t}» ({n} videos). Tu progreso sigue igual.",
      espacio: "Ocupa {mb} en este teléfono",
      err: {
        no_es_json: "Ese archivo no es un paquete de scroll to study. Elegí el .s2s.json que armaste en la compu.",
        no_es_paquete: "Ese archivo no es un paquete de scroll to study. Elegí el .s2s.json que armaste en la compu.",
        version: "Este paquete es de otra versión ({c}): armalo de nuevo con s2s.py paquete.",
        campo: "El paquete está dañado (falta o está mal «{c}»): armalo de nuevo con s2s.py paquete.",
        vacio: "El paquete no tiene videos.",
        repetido: "El paquete tiene el video «{c}» repetido: armalo de nuevo con s2s.py paquete.",
      },
      lleno: "No hay lugar en el teléfono para guardar estos videos. Liberá espacio o borrá otra materia.",
      errGuardar: "No se pudieron guardar los videos ({c}).",
      errLeer: "No se pudo leer el archivo.",
      errVideo: "No se encontró este video: importá el paquete de nuevo.",
      sinDB: "Este navegador no deja guardar datos (¿navegación privada?): abrí la app en una ventana normal.",
      vTitulo: "Tus videos, sin conexión",
      vTexto: "En la compu, pedile a Claude el paquete para el celular (o corré s2s.py paquete). Pasate el archivo .s2s.json por WhatsApp, AirDrop o Drive y tocá «Importar videos».",
      vPrivado: "Los videos quedan guardados solo en este teléfono: no se suben a ningún lado.",
      iTitulo: "Primero, instalá la app",
      iPaso1: "Tocá Compartir (el cuadrado con la flecha hacia arriba).",
      iPaso2: "Elegí «Agregar a inicio».",
      iPaso3: "Abrí scroll to study desde la pantalla de inicio e importá tus videos ahí. Anda sin conexión.",
      iSeparado: "La app instalada tiene su propio almacenamiento, separado de Safari: lo que importes en Safari no aparece en la app.",
      importarIgual: "Importar igual en Safari",
      sub: "Un video por día, en orden. Cada uno prepara una pregunta que te pueden hacer.",
      toca: "Hoy toca", racha: "días seguidos", racha1: "día seguido", vistos: "temas vistos",
      de: "Video {n} de {t}", ant: "Anterior", sig: "Siguiente",
      cero: "Borrar progreso", seguro: "¿Borrar todo el progreso de «{t}»?",
      exportar: "Exportar progreso", copiado: "Copiado al portapapeles",
      copiaManual: "No se pudo copiar solo: seleccioná este texto y copialo.",
    },
    en: {
      importar: "Import videos", elegir: "Saved videos", borrar: "Delete",
      confirmarBorrar: "Delete “{t}” from this phone? If you import it again, your progress is still there.",
      borrado: "Deleted “{t}”.",
      importado: "Done: “{t}”, {n} videos saved on this phone.",
      actualizado: "Updated “{t}” ({n} videos). Your progress is unchanged.",
      espacio: "Uses {mb} on this phone",
      err: {
        no_es_json: "That file is not a scroll to study package. Pick the .s2s.json you made on your computer.",
        no_es_paquete: "That file is not a scroll to study package. Pick the .s2s.json you made on your computer.",
        version: "This package is from another version ({c}): make it again with s2s.py paquete.",
        campo: "The package is damaged (“{c}” is missing or wrong): make it again with s2s.py paquete.",
        vacio: "The package has no videos.",
        repetido: "The package has the video “{c}” twice: make it again with s2s.py paquete.",
      },
      lleno: "There is no room on the phone for these videos. Free up some space or delete another set.",
      errGuardar: "Couldn't save the videos ({c}).",
      errLeer: "Couldn't read the file.",
      errVideo: "This video is missing: import the package again.",
      sinDB: "This browser does not let the app save data (private browsing?): open it in a normal window.",
      vTitulo: "Your videos, offline",
      vTexto: "On your computer, ask Claude for the phone package (or run s2s.py paquete). Send yourself the .s2s.json file by WhatsApp, AirDrop or Drive and tap “Import videos”.",
      vPrivado: "The videos are stored only on this phone: they are not uploaded anywhere.",
      iTitulo: "First, install the app",
      iPaso1: "Tap Share (the square with the arrow pointing up).",
      iPaso2: "Choose “Add to Home Screen”.",
      iPaso3: "Open scroll to study from your home screen and import your videos there. It works offline.",
      iSeparado: "The installed app has its own storage, separate from Safari: what you import in Safari does not show up in the app.",
      importarIgual: "Import in Safari anyway",
      sub: "One video a day, in order. Each one prepares a question you may get.",
      toca: "Up today", racha: "days in a row", racha1: "day in a row", vistos: "topics watched",
      de: "Video {n} of {t}", ant: "Previous", sig: "Next",
      cero: "Clear progress", seguro: "Clear all progress for “{t}”?",
      exportar: "Export progress", copiado: "Copied to the clipboard",
      copiaManual: "Couldn't copy it automatically: select this text and copy it.",
    },
  };
  const IDIOMA = /^es\b/i.test(navigator.language || "") ? "es" : "en";
  const TX = TEXTOS[IDIOMA];
  const fmt = (s, d) => s.replace(/\{(\w+)\}/g, (m, k) => (k in d ? d[k] : m));
  document.documentElement.lang = IDIOMA;
  const QX = C.textos(IDIOMA);

  const $ = id => document.getElementById(id);
  const v = $("v"), capa = $("capa");
  for (const id of ["importar", "vTitulo", "vTexto", "vPrivado", "iTitulo", "iPaso1", "iPaso2", "iPaso3",
                    "iSeparado", "importarIgual", "sub", "ant", "sig", "cero"]) $(id).textContent = TX[id];
  $("borrarPaq").textContent = TX.borrar; $("exp").textContent = TX.exportar;
  $("lToca").textContent = TX.toca; $("lVistos").textContent = TX.vistos; $("lHoy").textContent = QX.paraHoy;
  $("paquetes").setAttribute("aria-label", TX.elegir);

  // ---------------------------------------------------------------------------------------------
  // almacenamiento
  // ---------------------------------------------------------------------------------------------
  const ACTUAL = "s2s-app:actual";
  const claveVideo = (titulo, id) => JSON.stringify([titulo, id]);
  const pedido = r => new Promise((ok, mal) => { r.onsuccess = () => ok(r.result); r.onerror = () => mal(r.error); });
  const terminada = tx => new Promise((ok, mal) => {
    tx.oncomplete = () => ok();
    tx.onerror = () => mal(tx.error);
    tx.onabort = () => mal(tx.error || new Error("abort"));
  });
  const leerLS = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const ponerLS = (k, x) => { try { localStorage.setItem(k, x); } catch (e) {} };
  const quitarLS = k => { try { localStorage.removeItem(k); } catch (e) {} };

  function abrirDB() {
    return new Promise((ok, mal) => {
      let r;
      try { r = indexedDB.open("s2s-app", 1); } catch (e) { mal(e); return; }
      r.onupgradeneeded = () => {
        const db = r.result;
        if (!db.objectStoreNames.contains("paquetes")) db.createObjectStore("paquetes", { keyPath: "titulo" });
        if (!db.objectStoreNames.contains("videos")) db.createObjectStore("videos");
      };
      r.onsuccess = () => ok(r.result);
      r.onerror = () => mal(r.error);
    });
  }
  let db = null;

  /** Guarda un paquete ya validado en una sola transacción: o queda todo, o no queda nada. */
  function guardarPaquete(d) {
    const tx = db.transaction(["paquetes", "videos"], "readwrite");
    const ps = tx.objectStore("paquetes"), vs = tx.objectStore("videos");
    const previo = ps.get(d.titulo);
    let habia = false;
    previo.onsuccess = () => {
      if (previo.result) {
        habia = true;
        for (const x of previo.result.videos) vs.delete(claveVideo(d.titulo, x.id));
      }
      for (const x of d.videos) vs.put(x.html, claveVideo(d.titulo, x.id));
      ps.put(PQ.metadatos(d, new Date().toISOString()));
    };
    return terminada(tx).then(() => habia);
  }

  function borrarPaquete(meta) {
    const tx = db.transaction(["paquetes", "videos"], "readwrite");
    for (const x of meta.videos) tx.objectStore("videos").delete(claveVideo(meta.titulo, x.id));
    tx.objectStore("paquetes").delete(meta.titulo);
    return terminada(tx);
  }

  const listarPaquetes = () => pedido(db.transaction("paquetes").objectStore("paquetes").getAll());
  const leerVideo = (titulo, id) => pedido(db.transaction("videos").objectStore("videos").get(claveVideo(titulo, id)));

  async function mostrarEspacio() {
    const s = navigator.storage;
    if (!s || !s.estimate) return;
    try {
      const e = await s.estimate();
      const mb = (e.usage || 0) / 1048576;
      $("espacio").textContent = fmt(TX.espacio, { mb: (mb < 0.1 ? "0.1" : mb.toFixed(1)) + " MB" });
    } catch (e) {}
  }

  async function pedirPersistencia() {
    // sin esto el navegador puede borrar los videos si se queda sin lugar (Safari, a las semanas sin uso)
    const s = navigator.storage;
    if (!s || !s.persist) return;
    try { if (!(await s.persisted())) await s.persist(); } catch (e) {}
  }

  // ---------------------------------------------------------------------------------------------
  // estado de la app
  // ---------------------------------------------------------------------------------------------
  let paquetes = [];          // metadatos, ordenados por título
  let actual = null;          // metadatos del paquete que se ve
  let VIDEOS = [];
  let st = null, CLAVE = "";
  const hoy = () => P.fechaLocal(new Date());
  const guardar = () => ponerLS(CLAVE, JSON.stringify(st));

  const esIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const instalada = navigator.standalone === true ||
    (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
  let importarEnSafari = false;

  function error(texto) {
    $("error").textContent = texto || "";
    $("error").hidden = !texto;
  }
  function avisar(texto) {
    const a = $("aviso"); a.textContent = texto;
    clearTimeout(avisar.t); avisar.t = setTimeout(() => { a.textContent = ""; }, 4000);
  }

  function pintarApp() {
    const pedirInstalar = esIOS && !instalada && !importarEnSafari;
    $("instalar").hidden = !pedirInstalar;
    $("importar").hidden = pedirInstalar;
    $("vacio").hidden = pedirInstalar || paquetes.length > 0;
    $("reproductor").hidden = !actual;
    $("borrarPaq").hidden = !actual;
    const sel = $("paquetes");
    sel.hidden = paquetes.length < 2;
    sel.textContent = "";
    for (const p of paquetes) {
      const o = document.createElement("option");
      o.value = p.titulo; o.textContent = p.titulo; o.selected = actual && p.titulo === actual.titulo;
      sel.append(o);
    }
  }

  function elegir(titulo) {
    detenerVideo();
    actual = paquetes.find(p => p.titulo === titulo) || paquetes[0] || null;
    if (!actual) { quitarLS(ACTUAL); VIDEOS = []; pintarApp(); return; }
    ponerLS(ACTUAL, actual.titulo);
    // los paquetes guardados antes de las preguntas no tienen "preguntas"
    VIDEOS = actual.videos.map(x => Object.assign({ preguntas: [] }, x));
    CLAVE = "s2s:" + actual.titulo;
    st = P.cargar(leerLS(CLAVE), VIDEOS);
    guardar();
    document.title = actual.titulo;
    $("titulo").textContent = actual.titulo;
    pintarApp();
    const inicial = P.queTocaHoy(st, VIDEOS, hoy());
    abrir(pos(inicial === null ? st.cur : inicial), false);   // lo que toca hoy (o el último, si no queda nada)
  }

  async function recargar(titulo) {
    paquetes = (await listarPaquetes()).sort((a, b) => a.titulo.localeCompare(b.titulo));
    elegir(titulo);
  }

  // ---------------------------------------------------------------------------------------------
  // importar y borrar
  // ---------------------------------------------------------------------------------------------
  const leerTexto = f => (f.text ? f.text() : new Promise((ok, mal) => {
    const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = () => mal(r.error); r.readAsText(f);
  }));

  async function importar(archivo) {
    error("");
    let texto;
    try { texto = await leerTexto(archivo); } catch (e) { error(TX.errLeer); return; }
    const r = PQ.leer(texto);
    texto = null;
    if (r.error) { error(fmt(TX.err[r.error.codigo] || TX.err.no_es_paquete, { c: r.error.campo })); return; }
    const d = r.paquete;
    let habia;
    try {
      habia = await guardarPaquete(d);
    } catch (e) {
      error(e && e.name === "QuotaExceededError" ? TX.lleno : fmt(TX.errGuardar, { c: (e && (e.name || e.message)) || "?" }));
      return;
    }
    await pedirPersistencia();
    await recargar(d.titulo);
    avisar(fmt(habia ? TX.actualizado : TX.importado, { t: d.titulo, n: d.videos.length }));
    mostrarEspacio();
  }

  $("importar").onclick = () => $("archivo").click();
  $("archivo").onchange = () => {
    const f = $("archivo").files[0];
    $("archivo").value = "";            // así elegir el mismo archivo otra vez vuelve a disparar el evento
    if (f) importar(f);
  };
  $("importarIgual").onclick = e => { e.preventDefault(); importarEnSafari = true; pintarApp(); };
  $("paquetes").onchange = () => elegir($("paquetes").value);
  $("borrarPaq").onclick = async () => {
    if (!actual) return;
    const meta = actual;
    if (!confirm(fmt(TX.confirmarBorrar, { t: meta.titulo }))) return;
    try { await borrarPaquete(meta); } catch (e) { error(fmt(TX.errGuardar, { c: e && e.name })); return; }
    await recargar(null);
    error(""); avisar(fmt(TX.borrado, { t: meta.titulo }));
    mostrarEspacio();
  };

  // ---------------------------------------------------------------------------------------------
  // reproductor (mismo espíritu que videos/index.html de la compu)
  // ---------------------------------------------------------------------------------------------
  const pos = id => Math.max(0, VIDEOS.findIndex(x => x.id === id));
  const mmss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  function vistosAlgunaVez() {
    const s = new Set(); for (const f in st.dias) for (const id of st.dias[f]) s.add(id); return s;
  }
  function pintar() {
    if (!actual) return;
    const cur = pos(st.cur), vistos = vistosAlgunaVez(), toca = P.queTocaHoy(st, VIDEOS, hoy());
    const ol = $("lista"); ol.textContent = "";
    VIDEOS.forEach((x, i) => {
      const li = document.createElement("li"), b = document.createElement("button");
      li.classList.toggle("cur", i === cur); li.classList.toggle("visto", vistos.has(x.id));
      b.type = "button";
      const n = document.createElement("span"); n.className = "num"; n.textContent = vistos.has(x.id) ? "✓" : i + 1;
      const t = document.createElement("span"); t.className = "t";
      const tb = document.createElement("b"); tb.textContent = x.titulo;
      const ts = document.createElement("span"); ts.textContent = x.pregunta; t.append(tb, ts);
      const e = P.estadoTema(st, x, hoy()); li.dataset.rep = e.estado;
      t.append(C.chip(document, e, e.proxima ? P.diasEntre(hoy(), e.proxima) : 0, IDIOMA));
      const d = document.createElement("span"); d.className = "dur"; d.textContent = mmss(x.duracion);
      b.append(n, t, d); b.onclick = () => abrir(i, true); li.append(b); ol.append(li);
    });
    // si hoy no queda nada, se dice, y cualquier video de la lista se puede ver igual
    const it = toca === null ? -1 : pos(toca);
    $("toca").disabled = it < 0;
    $("tToca").textContent = it < 0 ? QX.nada : VIDEOS[it].titulo; $("toca").onclick = () => abrir(it, true);
    $("nToca").textContent = it < 0 ? "" : fmt(TX.de, { n: it + 1, t: VIDEOS.length });
    $("nHoy").textContent = P.pendientesHoy(st, VIDEOS, hoy()).length;
    const r = P.racha(st, hoy());
    $("nRacha").textContent = r; $("lRacha").textContent = r === 1 ? TX.racha1 : TX.racha;
    const n = VIDEOS.filter(x => vistos.has(x.id)).length;
    $("nVistos").textContent = `${n} / ${VIDEOS.length}`;
    $("lleno").style.width = (100 * n / VIDEOS.length) + "%";
    $("nAhora").textContent = fmt(TX.de, { n: cur + 1, t: VIDEOS.length });
    $("tAhora").textContent = VIDEOS[cur].titulo;
    $("ant").disabled = cur === 0; $("sig").disabled = cur === VIDEOS.length - 1;
  }

  // capa de gestos (pantallas táctiles): deslizar arriba = siguiente, abajo = anterior, tocar = pausa
  const tactil = (window.matchMedia && matchMedia("(pointer: coarse)").matches) || navigator.maxTouchPoints > 0;
  let ini = null, urlActual = null, turno = 0, quiz = null;
  // lo que pasa con el iframe del video (avisos, retomar si se recarga solo, cortes): reproduccion.js
  const R = window.Reproduccion.conectar({
    iframe: v, claveCortes: () => "s2s-cortes:" + actual.titulo, activo: () => !!actual,
    alCambiar: () => ponerCapa(), alFin: () => terminoVideo(),
  });
  const ponerCapa = () => capa.classList.toggle("activa", tactil && R.sonando());

  function cerrarQuiz() { if (quiz) { quiz.cerrar(); quiz = null; } }
  function seguirConLoQueToca() {
    const t = P.queTocaHoy(st, VIDEOS, hoy());
    if (t !== null) abrir(pos(t), true); else pintar();
  }
  // después del video, sus preguntas (cuestionario.js); el resultado decide cuándo vuelve el tema (progreso.js)
  function preguntar(x) {
    cerrarQuiz();
    quiz = C.mostrar(document.querySelector(".caja"), {
      idioma: IDIOMA, preguntas: x.preguntas,
      alTerminar: (aciertos, total) => {
        st = P.responder(st, x.id, aciertos, total, hoy()); guardar(); pintar();
        const t = P.queTocaHoy(st, VIDEOS, hoy());
        return { dias: P.diasEntre(hoy(), st.repaso[x.id].proxima), siguiente: t === null ? null : VIDEOS[pos(t)].titulo };
      },
      alSeguir: () => { quiz = null; seguirConLoQueToca(); },
      alSaltear: () => { quiz = null; seguirConLoQueToca(); },   // no cuenta como respuesta: ya quedó visto
    });
  }

  function detenerVideo() {
    turno++;
    cerrarQuiz();
    R.detener();
    v.removeAttribute("src");
    if (urlActual) { URL.revokeObjectURL(urlActual); urlActual = null; }
  }

  async function abrir(i, auto) {
    if (!actual || i < 0 || i >= VIDEOS.length) return;
    cerrarQuiz();
    st = Object.assign({}, st, { cur: VIDEOS[i].id }); guardar();
    R.detener(); pintar();
    const mio = ++turno, titulo = actual.titulo;
    let html = null;
    try { html = await leerVideo(titulo, VIDEOS[i].id); } catch (e) {}
    if (mio !== turno) return;                     // mientras tanto se pidió otro video
    if (typeof html !== "string") { error(TX.errVideo); return; }
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    R.cargar(VIDEOS[i].id, auto);
    v.src = url;
    if (urlActual) URL.revokeObjectURL(urlActual);  // la anterior ya no la usa nadie
    urlActual = url;
  }

  capa.addEventListener("pointerdown", e => {
    ini = { x: e.clientX, y: e.clientY };
    try { capa.setPointerCapture(e.pointerId); } catch (err) {}
  });
  capa.addEventListener("pointercancel", () => { ini = null; });
  capa.addEventListener("pointerup", e => {
    if (!ini) return;
    const dx = e.clientX - ini.x, dy = e.clientY - ini.y; ini = null;
    if (Math.abs(dy) > 50 && Math.abs(dy) > 1.5 * Math.abs(dx)) abrir(pos(st.cur) + (dy < 0 ? 1 : -1), true);
    else if (Math.abs(dx) < 12 && Math.abs(dy) < 12 && v.contentWindow) v.contentWindow.postMessage({ s2s: "pausa" }, "*");
  });
  // el video avisa con postMessage cuándo está listo, suena, se pausa y termina (reproduccion.js solo le
  // cree al iframe del reproductor: el origen es opaco por el sandbox, así que se compara la ventana)
  function terminoVideo() {
    if (quiz) return;
    const cur = pos(st.cur), x = VIDEOS[cur];
    st = P.marcarVisto(st, x.id, hoy()); guardar();
    if (x.preguntas.length) { pintar(); preguntar(x); return; }
    if (cur < VIDEOS.length - 1) abrir(cur + 1, true); else pintar();
  }
  $("ant").onclick = () => abrir(pos(st.cur) - 1, true);
  $("sig").onclick = () => abrir(pos(st.cur) + 1, true);

  function mostrarJson(texto) {
    let caja = $("expCaja");
    if (!caja) {
      caja = document.createElement("div"); caja.id = "expCaja";
      const s = document.createElement("small"); s.textContent = TX.copiaManual;
      const ta = document.createElement("textarea"); ta.id = "expTxt"; ta.readOnly = true; ta.setAttribute("aria-label", TX.exportar);
      ta.onfocus = () => ta.select();
      caja.append(s, ta); $("ctrls2").after(caja);
    }
    const ta = $("expTxt"); ta.value = texto; ta.focus(); ta.select();
  }
  $("exp").onclick = async () => {
    const datos = Object.assign(P.exportar(st, { titulo: actual.titulo, fecha: hoy(), generado: new Date().toISOString() }),
                                { cortes: R.cortes() });
    const texto = JSON.stringify(datos, null, 2);
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("sin portapapeles");
      await navigator.clipboard.writeText(texto);
      avisar(TX.copiado);
    } catch (e) { mostrarJson(texto); }
  };
  $("cero").onclick = () => {
    if (!actual || !confirm(fmt(TX.seguro, { t: actual.titulo }))) return;
    st = P.vacio(VIDEOS); guardar(); abrir(0, false);
  };

  // ---------------------------------------------------------------------------------------------
  // arranque
  // ---------------------------------------------------------------------------------------------
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(e => console.warn("service worker:", e));
  }
  pintarApp();
  abrirDB()
    .then(async d => {
      db = d;
      await recargar(leerLS(ACTUAL));
      if (paquetes.length) mostrarEspacio();
    })
    .catch(e => { console.error(e); error(TX.sinDB); $("importar").disabled = true; })
    .then(() => { document.documentElement.dataset.appLista = "1"; });
})();
