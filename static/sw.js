/* Cache the public app shell for offline use. API requests go to the server. */
const CACHE = 'lhc-v2';
const SHELL = [
  '/', '/tools', '/dashboard', '/cases', '/billing', '/hash',
  '/download', '/judgments', '/alerts', '/static/lhc-core.js', '/manifest.json',
  '/favicon.svg', '/static/icon-192.png', '/static/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys
        .filter(key => key.startsWith('lhc-v') && key !== CACHE)
        .map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.search || !SHELL.includes(url.pathname)) return;

  event.respondWith(caches.open(CACHE).then(async cache => {
    try {
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    } catch (error) {
      const cached = await cache.match(request);
      if (cached) return cached;
      throw error;
    }
  }));
});
