// Minimal Service Worker - No caching
const CACHE_NAME = 'english-teacher-v4';

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    // Clear all old caches
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(name => caches.delete(name))
            );
        })
    );
    return self.clients.claim();
});

self.addEventListener('fetch', event => {
    // Always fetch from network, never use cache
    event.respondWith(fetch(event.request));
});
