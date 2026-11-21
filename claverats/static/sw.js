/* CLAVERATS Pro - Service Worker. Mise en cache locale uniquement ; /api/* n'est JAMAIS mis en cache. */
const CACHE_VERSION = "claverats-v2.2";
const PRECACHE = [
  "/",
  "/static/css/style.css",
  "/static/css/geomap.css",
  "/static/css/enhance.css",
  "/static/css/icons.css",
  "/static/css/mobile.css",
  "/static/js/geo-data.js",
  "/static/js/geomap.js",
  "/static/js/main.js",
  "/static/js/enhance.js",
  "/static/js/intel.js",
  "/static/data/world.geojson",
  "/static/js/mobile.js",
  "/static/js/insights.js",
  "/static/js/personal.js",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((c) => Promise.all(PRECACHE.map((u) => c.add(u).catch(() => null))))
  );
  /* pas de skipWaiting automatique : l'utilisateur choisit via la banniere de mise a jour */
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("claverats-") && k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) return; /* donnees : toujours reseau, jamais cache */

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_VERSION).then((c) => c.put("/", copy));
        return res;
      }).catch(() => caches.match("/"))
    );
    return;
  }
  event.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req).then((res) => {
        if (res && res.ok) { const copy = res.clone(); caches.open(CACHE_VERSION).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
