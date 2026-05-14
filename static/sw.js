const CACHE_NAME = 'node-v2';
const urlsToCache = [
    '/',
    '/dashboard/',
    '/trading/',
    '/portfolio/',
    '/deposit/',
    '/withdraw/',
    '/profile/',
    '/referral/',
    '/static/favicon.png',
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(urlsToCache);
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