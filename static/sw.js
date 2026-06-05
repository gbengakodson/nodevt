const CACHE_NAME = 'node-v3-' + Date.now();
const urlsToCache = [
    '/',
    '/dashboard/',
    '/trading/',
    '/portfolio/',
    '/deposit/',
    '/withdraw/',
    '/profile/',
    '/referral/',
    '/transparency/',
    '/yield/',
    '/chat/',
    '/static/favicon.png',
    '/static/manifest.json',
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(urlsToCache);
        })
    );
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
});

self.addEventListener('fetch', function(event) {
    event.respondWith(
        caches.match(event.request).then(function(response) {
            return response || fetch(event.request);
        })
    );
});