<<<<<<< HEAD
const CACHE_NAME = 'checklist-hogar-v1';
const STATIC_ASSETS = ['/', '/static/styles.css', '/static/app.js', '/static/manifest.json', '/static/icon-192.png', '/static/icon-512.png'];
=======
const CACHE_NAME = 'checklist-hogar-v5';
const STATIC_ASSETS = [
  '/',
  '/static/index.html',
  '/static/styles.css',
  '/static/app.js',
  '/static/api.js',
  '/static/date.js',
  '/static/state.js',
  '/static/manifest.json',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg'
];
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const request = fetch(event.request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone)).catch(() => {});
        }
        return response;
      }).catch(() => cached);
      return cached || request;
    })
  );
});
