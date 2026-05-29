/**
 * Service Worker — 小说阅读器 PWA
 *
 * 策略：
 *   - 静态资源（CSS/JS/图标）: Cache First（优先缓存，更新后台刷新）
 *   - 阅读页 /read/*          : Stale-While-Revalidate（有缓存先显示，后台悄悄更新）
 *   - 搜索页 /search          : Network First（优先网络，离线才用缓存）
 *   - API 接口                : Network Only（不缓存）
 */

const CACHE_VERSION = "v1";
const STATIC_CACHE  = `novel-static-${CACHE_VERSION}`;
const PAGE_CACHE    = `novel-pages-${CACHE_VERSION}`;

// 预缓存的静态资源
const PRECACHE_URLS = [
  "/static/css/main.css",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/",
];

// ── Install：预缓存静态资源 ────────────────────────────────────
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      return cache.addAll(PRECACHE_URLS).catch(err => {
        console.warn("[SW] precache 部分失败:", err);
      });
    }).then(() => self.skipWaiting())
  );
});

// ── Activate：清理旧缓存 ───────────────────────────────────────
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== STATIC_CACHE && k !== PAGE_CACHE)
            .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch：路由策略 ───────────────────────────────────────────
self.addEventListener("fetch", event => {
  const { request } = event;
  const url = new URL(request.url);

  // 只处理同源 GET 请求
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  const path = url.pathname;

  // API 接口 → Network Only
  if (path.startsWith("/api/")) return;

  // 静态资源 → Cache First
  if (path.startsWith("/static/")) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // 阅读页 → Stale-While-Revalidate
  if (path.startsWith("/read/")) {
    event.respondWith(staleWhileRevalidate(request, PAGE_CACHE));
    return;
  }

  // 搜索页 → Network First
  if (path.startsWith("/search")) {
    event.respondWith(networkFirst(request, PAGE_CACHE));
    return;
  }

  // 其他页面 → Stale-While-Revalidate
  event.respondWith(staleWhileRevalidate(request, PAGE_CACHE));
});

// ── 策略实现 ──────────────────────────────────────────────────

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("离线中，资源不可用", { status: 503 });
  }
}

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || offlinePage();
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache  = await caches.open(cacheName);
  const cached = await cache.match(request);

  // 后台更新
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);

  return cached || (await fetchPromise) || offlinePage();
}

function offlinePage() {
  return new Response(
    `<!DOCTYPE html><html lang="zh-CN"><head>
      <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>离线中</title>
      <style>
        body{font-family:system-ui,sans-serif;display:flex;align-items:center;
             justify-content:center;height:100vh;margin:0;background:#f5f0e8;color:#2a2016;}
        .box{text-align:center;padding:40px 20px;}
        .icon{font-size:3rem;margin-bottom:16px;}
        h2{margin-bottom:8px;}
        p{color:#7a6e5e;font-size:0.9rem;}
        button{margin-top:20px;padding:10px 24px;background:#c0392b;color:#fff;
               border:none;border-radius:20px;font-size:0.95rem;cursor:pointer;}
      </style>
     </head><body>
      <div class="box">
        <div class="icon">📵</div>
        <h2>当前处于离线状态</h2>
        <p>已缓存的阅读页面仍可访问</p>
        <button onclick="location.reload()">重新连接</button>
      </div>
     </body></html>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}
