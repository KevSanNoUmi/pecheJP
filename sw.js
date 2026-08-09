// Service worker — offline app shell for Carnet Pêche JP
const CACHE = 'carnet-peche-jp-v11';
// Shell minimal indispensable. Les JSON de données sont mis en cache à la volée (réseau d'abord),
// PAS dans addAll — sinon un seul 404 casse toute l'installation et provoque un écran blanc.
const SHELL = ['./', './index.html'];
const OPTIONAL = ['./manifest.webmanifest', './synthesis.json', './lure_typology.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then((c) =>
      // shell critique : doit réussir ; optionnels : best-effort, chaque échec ignoré individuellement
      c.addAll(SHELL)
       .then(() => Promise.allSettled(OPTIONAL.map((u) => c.add(u).catch(() => {}))))
    ).catch(() => {})
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // data.json : réseau en priorité (données vivantes, mises à jour à chaque push), cache en secours hors ligne
  if (url.origin === location.origin && (url.pathname.endsWith('data.json') || url.pathname.endsWith('synthesis.json') || url.pathname.endsWith('lure_typology.json'))) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  if (url.origin === location.origin) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match('./index.html')))
    );
    return;
  }

  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
