const CACHE_NAME = 'node-v4-' + Date.now();
const urlsToCache = [
    '/static/favicon.png',
    '/static/manifest.json',
    // DO NOT cache any HTML pages – they'll always load fresh
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(urlsToCache);
        })
    );
    // Activate the new service worker immediately, don't wait for old tabs to close
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(key) { return key !== CACHE_NAME; })
                    .map(function(key) { return caches.delete(key); })
            );
        })
    );
    // Take control of all pages immediately
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', function(event) {
    // For HTML pages, always go network-first
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(function() {
                return caches.match(event.request);
            })
        );
        return;
    }

    // For other assets, cache-first
    event.respondWith(
        caches.match(event.request).then(function(response) {
            return response || fetch(event.request);
        })
    );
});