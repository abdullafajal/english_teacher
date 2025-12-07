// PWA Service Worker v6 - Simplified
const CACHE_NAME = 'english-teacher-v6';

// Install - just skip waiting
self.addEventListener('install', event => {
    self.skipWaiting();
});

// Activate - clear old caches and take control
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys()
            .then(names => Promise.all(names.map(name => caches.delete(name))))
            .then(() => self.clients.claim())
    );
});

// Fetch - network only (most reliable for dev)
self.addEventListener('fetch', event => {
    // Only handle http/https
    if (!event.request.url.startsWith('http')) {
        return;
    }

    // Only handle GET
    if (event.request.method !== 'GET') {
        return;
    }

    // Always use network
    event.respondWith(
        fetch(event.request).catch(() => {
            // If offline and requesting HTML, show simple offline message
            if (event.request.headers.get('accept')?.includes('text/html')) {
                return new Response(
                    '<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui"><h1>You are offline</h1></body></html>',
                    { headers: { 'Content-Type': 'text/html' } }
                );
            }
            return new Response('Offline', { status: 503 });
        })
    );
});
