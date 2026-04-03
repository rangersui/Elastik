const CDNS = ['esm.sh', 'cdn.jsdelivr.net', 'unpkg.com', 'cdnjs.cloudflare.com'];
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const h = url.hostname;
  // CDN: cache-first (immutable assets)
  if (CDNS.some(c => h.includes(c))) {
    e.respondWith(
      caches.open('elastik-cdn').then(c =>
        c.match(e.request).then(r => r || fetch(e.request).then(res => {
          c.put(e.request, res.clone()); return res;
        }))
      )
    );
    return;
  }
  // /read and /stages: stale-while-revalidate
  if (e.request.method === 'GET' &&
      (url.pathname.endsWith('/read') || url.pathname === '/stages')) {
    e.respondWith(
      caches.open('elastik-v1').then(c =>
        c.match(e.request).then(cached => {
          const fresh = fetch(e.request).then(r => {
            if (r.ok) c.put(e.request, r.clone());
            return r;
          }).catch(() => cached);
          return cached || fresh;
        })
      )
    );
  }
});
