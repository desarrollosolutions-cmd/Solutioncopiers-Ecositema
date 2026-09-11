/* Service worker minimo — recibe Web Push y muestra la notificacion del
 * sistema operativo aunque el sitio no este abierto, y habilita que el
 * sitio se pueda instalar como PWA (icono propio en el celular/PC). No
 * cachea nada todavia, asi que no hay riesgo de servir contenido viejo. */

self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

// Passthrough — requisito de algunos navegadores para ofrecer "Instalar app".
self.addEventListener('fetch', function (event) {
  event.respondWith(fetch(event.request));
});

self.addEventListener('push', function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) {}

  var title = data.title || 'Solution Copiers';
  var options = {
    body: data.body || '',
    icon: '/static/images/icons/icon-192.png',
    badge: '/static/images/icons/icon-192.png',
    data: { url: data.url || '/' },
    vibrate: [100, 50, 100],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windowClients) {
      for (var i = 0; i < windowClients.length; i++) {
        var client = windowClients[i];
        if (client.url.indexOf(url) !== -1 && 'focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
