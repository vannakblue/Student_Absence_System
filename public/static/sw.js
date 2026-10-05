// Service Worker for Hun Sen Kampong Kantuot High School Absence System
const CACHE_NAME = 'kkhs-portal-v2';

const STATIC_ASSETS = [
  '/static/css/mobile.css',
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/favicon.png',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Kantumruy+Pro:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.warn('Some assets could not be pre-cached:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip non-GET and chrome-extension/auth requests
  if (req.method !== 'GET') return;

  // Static assets: Cache-first, then network
  if (url.pathname.startsWith('/static/') || url.hostname.includes('fonts.') || url.hostname.includes('cdnjs.')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // HTML and API: Network-first, fallback to cache
  event.respondWith(
    fetch(req).catch(() => {
      return caches.match(req).then((cached) => {
        if (cached) return cached;
        // If offline and request is an HTML page, return a friendly offline message
        if (req.headers.get('accept')?.includes('text/html')) {
          return new Response(
            `<!DOCTYPE html>
            <html lang="km">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>គ្មានការតភ្ជាប់អ៊ីនធឺណិត | វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត</title>
              <style>
                body { font-family: sans-serif; background: #0f172a; color: #fff; text-align: center; padding: 50px 20px; }
                .box { max-width: 400px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
                h2 { color: #60a5fa; margin-top: 10px; font-size: 1.3rem; }
                p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
                .btn { display: inline-block; margin-top: 15px; padding: 10px 20px; background: #2563eb; color: #fff; text-decoration: none; border-radius: 8px; font-weight: bold; }
              </style>
            </head>
            <body>
              <div class="box">
                <div style="font-size: 48px;">📡</div>
                <h2>គ្មានការតភ្ជាប់អ៊ីនធឺណិត (Offline)</h2>
                <p>សូមពិនិត្យមើលសេវា Wi-Fi ឬទិន្នន័យទូរសព្ទរបស់អ្នក។ កម្មវិធីនឹងដំណើរការឡើងវិញដោយស្វ័យប្រវត្តិនៅពេលមានអ៊ីនធឺណិត។</p>
                <a href="javascript:window.location.reload()" class="btn">ព្យាយាមម្តងទៀត</a>
              </div>
            </body>
            </html>`,
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        }
      });
    })
  );
});
