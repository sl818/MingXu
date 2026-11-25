/* 明序 PWA Service Worker
   只缓存页面外壳和图标；api.php 永远走网络，避免缓存账号数据。 */
const CACHE = 'lifeboard-shell-v179';
/* 带 ?v= 的资源：HTML 里也是同一个版本串，发版时一起改 */
const VER = 'v179';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './assets/app.css?v=' + VER,
  './assets/theme-v2.css?v=' + VER,
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(cache =>
      /* 逐个 fetch 并指定 cache:'reload'。直接 addAll 会走浏览器的 HTTP 缓存，
         宝塔给静态文件设了缓存头，结果「新 SW 里装的还是旧 CSS」——
         表现就是某些浏览器样式没跟上，另一些是好的。 */
      Promise.all(ASSETS.map(url =>
        fetch(new Request(url, { cache: 'reload' }))
          .then(res => {
            if (res && res.ok) return cache.put(url, res);
          })
          .catch(() => {})
      ))
    ).then(() => self.skipWaiting())
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

/* 点通知：优先聚焦已经开着的窗口，并把要去的页面告诉它；
   全都没开的时候才新开一个。 */
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.view) || 'today';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (let i = 0; i < list.length; i++) {
        const c = list[i];
        if ('focus' in c) {
          if ('postMessage' in c) c.postMessage({ type: 'goto', view: target });
          return c.focus();
        }
      }
      return self.clients.openWindow('./');
    }).catch(() => {})
  );
});
