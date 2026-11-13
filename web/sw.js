/* Service worker: guarda el reproductor al instalarse y lo sirve desde la caché primero, así la app
 * abre en modo avión. Los videos no pasan por acá: están en IndexedDB.
 *
 * tools/sitio.py reemplaza __VERSION__ (una huella de todos los archivos del sitio) y la lista de
 * ARCHIVOS al armar _site/: cada cambio publicado es una caché nueva, y al activarse se borran las viejas.
 */
"use strict";
const VERSION = "__VERSION__";
const PREFIJO = "s2s-app-";
const CACHE = PREFIJO + VERSION;
const ARCHIVOS = ["./", /*__ARCHIVOS__*/];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k.startsWith(PREFIJO) && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(
    caches.open(CACHE).then(async c => {
      const guardada = await c.match(req, { ignoreSearch: true });
      if (guardada) return guardada;
      try {
        return await fetch(req);
      } catch (err) {
        // sin red y sin esa URL en caché: una navegación abre igual el reproductor
        if (req.mode === "navigate") {
          const inicio = await c.match("./");
          if (inicio) return inicio;
        }
        throw err;
      }
    }));
});
