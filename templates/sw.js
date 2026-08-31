/*
 * Service worker — Maisonnée PWA.
 *
 * Servi à la racine (`/sw.js`) par Django (voir config/urls.py) pour avoir un
 * scope `/` et contrôler tout `/app/*`. NE PAS le déplacer sous /static/ :
 * son scope serait réduit à /static/ et il ne contrôlerait plus le SPA.
 *
 * Rôles :
 *  - rendre l'app installable + consultable hors-ligne (cache app-shell + assets
 *    Vite immuables). Les réponses /api ne sont volontairement jamais mises en
 *    cache ici (auth par Bearer token → risque de fuite entre utilisateurs), et
 *    /media n'est pas intercepté du tout (un fichier du foyer n'est pas une page
 *    de l'app — voir la garde du handler `fetch`).
 *  - recevoir les notifications push (Web Push) et gérer le clic → deep-link.
 *
 * Fichier servi via TemplateView : ne pas y introduire de syntaxe de template
 * Django (doubles accolades ou balises pourcent), elle serait interprétée.
 */

const STATIC_CACHE = 'house-static-v1';
const SHELL_CACHE = 'house-shell-v1';
const SHELL_KEY = '__app_shell__';
const KNOWN_CACHES = [STATIC_CACHE, SHELL_CACHE];

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => !KNOWN_CACHES.includes(k)).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

function isImmutableAsset(url) {
  return (
    url.origin === self.location.origin &&
    (url.pathname.startsWith('/static/react/assets/') || url.pathname.startsWith('/static/icons/'))
  );
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(STATIC_CACHE);
    cache.put(request, response.clone());
  }
  return response;
}

function isHtml(response) {
  const type = response.headers.get('content-type') || '';
  return type.includes('text/html');
}

async function networkFirstShell(request) {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const response = await fetch(request);
    // Tous les chemins /app/* renvoient le même index.html : on le stocke sous
    // une clé unique pour servir n'importe quelle route hors-ligne.
    //
    // La garde sur le type est ce qui rend cette clé unique tenable : une
    // navigation qui ne rend pas une page (un fichier, un export, un flux)
    // remplacerait la coquille par elle, et l'app relancée hors-ligne
    // afficherait ce contenu au lieu du tableau de bord.
    if (response && response.ok && isHtml(response)) {
      cache.put(SHELL_KEY, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(SHELL_KEY);
    if (cached) return cached;
    throw err;
  }
}

// --- Cible de partage (Android) --------------------------------------------
//
// ⚠️ Un service worker **ne peut pas lire localStorage**, où vit le jeton du SPA.
// Il ne peut donc pas fabriquer l'en-tête Authorization, et ne doit surtout pas
// tenter l'envoi lui-même : on obtiendrait des 401 et on chercherait longtemps.
//
// Il met donc les fichiers de côté, répond par une redirection, et c'est **la
// page** — qui, elle, lit localStorage — qui téléverse.
const SHARE_PATH = '/app/photos/share';
const SHARE_CACHE = 'shared-files-v1';
const SHARE_KEY = '/__shared__';

async function stashSharedFiles(request) {
  try {
    const form = await request.formData();
    const files = form.getAll('photos').filter((f) => f && f.size > 0);
    if (files.length) {
      const cache = await caches.open(SHARE_CACHE);
      // Les Response ne se sérialisent pas en lot : une entrée de cache par
      // fichier, indexée, et un index qui dit combien il y en a.
      await cache.put(SHARE_KEY, new Response(String(files.length)));
      await Promise.all(
        files.map((file, i) =>
          cache.put(
            `${SHARE_KEY}/${i}`,
            new Response(file, {
              headers: {
                'content-type': file.type || 'application/octet-stream',
                'x-file-name': encodeURIComponent(file.name || `photo-${i}.jpg`),
              },
            }),
          ),
        ),
      );
    }
  } catch (err) {
    // Un partage qui échoue ici ne doit pas bloquer la navigation : la page
    // s'ouvrira vide et le dira.
  }
  return Response.redirect(SHARE_PATH, 303);
}

self.addEventListener('fetch', (event) => {
  const request = event.request;

  if (request.method === 'POST' && new URL(request.url).pathname === SHARE_PATH) {
    event.respondWith(stashSharedFiles(request));
    return;
  }

  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  if (isImmutableAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // ⚠️ Un fichier du foyer n'est pas une page de l'app, et le service worker ne
  // doit pas s'en mêler : un `<a download>` arrive ici en `mode: 'navigate'`
  // (Chromium), donc l'intercepter ferait passer chaque téléchargement par la
  // logique de coquille — celle-là même qui, avant la garde sur le type,
  // remplaçait la page hors-ligne par le PDF qu'on venait d'ouvrir. Il n'y a
  // rien à servir hors-ligne pour un fichier : on laisse descendre au réseau.
  if (request.mode === 'navigate' && !url.pathname.startsWith('/media/')) {
    event.respondWith(networkFirstShell(request));
    return;
  }

  // Tout le reste (dont /api) : réseau direct, pas de cache SW.
});

// --- Web Push -------------------------------------------------------------

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (err) {
    payload = { body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'Maisonnée';
  const options = {
    body: payload.body || '',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    tag: payload.tag || undefined,
    data: { url: payload.url || '/app/dashboard' },
  };

  // App-icon badge (Badging API): the count rides in the payload so the badge
  // stays right even when the SPA is closed. Guarded — not every UA/OS exposes
  // it, and it only surfaces on an installed PWA (iOS 16.4+).
  const tasks = [self.registration.showNotification(title, options)];
  if (typeof payload.unreadCount === 'number' && self.navigator.setAppBadge) {
    tasks.push(
      payload.unreadCount > 0
        ? self.navigator.setAppBadge(payload.unreadCount)
        : self.navigator.clearAppBadge()
    );
  }
  event.waitUntil(Promise.all(tasks).catch(() => {}));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/app/dashboard';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          if ('navigate' in client) client.navigate(targetUrl);
          return client.focus();
        }
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
