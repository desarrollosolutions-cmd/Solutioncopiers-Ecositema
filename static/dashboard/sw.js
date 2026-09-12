/* Service worker minimo — recibe Web Push y muestra la notificacion del
 * sistema operativo aunque el sitio no este abierto, y habilita que el
 * sitio se pueda instalar como PWA (icono propio en el celular/PC). No
 * cachea nada todavia, asi que no hay riesgo de servir contenido viejo.
 *
 * A propósito NO hay un listener de 'fetch': ya no es requisito para que
 * el navegador ofrezca instalar el sitio, y un passthrough ingenuo
 * (event.respondWith(fetch(event.request))) intercepta TAMBIÉN los
 * recursos externos (Leaflet, tiles de OpenStreetMap, geocodificación)
 * que usan los mapas de ubicación — en redes móviles inestables, si esa
 * relectura dentro del service worker falla, el recurso queda marcado
 * como error sin ningún reintento nativo del navegador, y el mapa
 * completo deja de cargar. Sin ese listener, todas esas peticiones pasan
 * derecho por el camino normal del navegador, igual que si no hubiera
 * service worker instalado. */

self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
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
