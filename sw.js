// Pyxel Arcade service worker: cache the shell so the arcade opens offline.
// Game code itself streams from the Pyxel web launcher (cross-origin) and is
// not cached here; previews are cached as they're seen.
var CACHE = 'arcade-v1';
var SHELL = [
    './',
    'index.html',
    'styles.css',
    'script.js',
    'demos/manifest.json',
    'assets/favicon.svg',
    'assets/icon-192.png',
];

self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE).then(function (c) { return c.addAll(SHELL); })
            .then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(keys.filter(function (k) { return k !== CACHE; })
                .map(function (k) { return caches.delete(k); }));
        }).then(function () { return self.clients.claim(); })
    );
});

// Same-origin GETs: stale-while-revalidate. Cross-origin (the launcher,
// GitHub): straight to network.
self.addEventListener('fetch', function (e) {
    var url = new URL(e.request.url);
    if (e.request.method !== 'GET' || url.origin !== location.origin) return;

    e.respondWith(
        caches.open(CACHE).then(function (cache) {
            return cache.match(e.request).then(function (cached) {
                var fetched = fetch(e.request).then(function (resp) {
                    if (resp && resp.status === 200) cache.put(e.request, resp.clone());
                    return resp;
                }).catch(function () { return cached; });
                return cached || fetched;
            });
        })
    );
});
