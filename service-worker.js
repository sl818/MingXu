/* 晚风Todo PWA Service Worker
   只缓存页面外壳和图标；api.php 永远走网络，避免缓存账号数据。 */
const CACHE = 'lifeboard-shell-v25';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './themes/themes.css',
  './themes/custom.css',
  './themes/skin-mist.css',
  './themes/skin-forest.css',
  './themes/skin-neu.css',
  './themes/skin-cyber.css',
  './themes/skin-retro.css',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // 接口、安装器和安装锁永远不缓存
  if (url.pathname.endsWith('/api.php') ||
      url.pathname.indexOf('/api/') !== -1 ||
      url.pathname.indexOf('/install/') !== -1 ||
      url.pathname.endsWith('/install.lock')) {
    return;
  }

  // 页面导航：网络优先，断网回退到缓存的外壳
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then(cache => cache.put('./index.html', copy)).catch(() => {});
          }
          return response;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  // 图标、manifest 等静态资源：缓存优先
  event.respondWith(
    caches.match(request).then(hit => {
      if (hit) return hit;
      return fetch(request).then(response => {
        if (response && response.ok && (request.destination === 'image' || url.pathname.endsWith('/manifest.json'))) {
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(request, copy)).catch(() => {});
        }
        return response;
      });
    })
  );
});
