/* Notificaciones push del navegador — chat interno y notificaciones del
 * sistema en general, aunque la pestaña no este abierta. Funciona en PC y
 * celular (Android/Chrome sin instalar nada; iPhone solo si el sitio se
 * agrego a la pantalla de inicio, es una limitacion de iOS, no del sitio). */
(function () {
  'use strict';

  var DISMISS_KEY = 'sc-push-dismissed-at';
  var DISMISS_DAYS = 3;

  function swSupported() {
    return 'serviceWorker' in navigator;
  }

  function pushSupported() {
    return swSupported() && 'PushManager' in window && 'Notification' in window;
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
    return outputArray;
  }

  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function subscribe(vapidPublicKey, registration) {
    return registration.pushManager.getSubscription().then(function (existing) {
      if (existing) return existing;
      return registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });
    }).then(function (sub) {
      return fetch('/chat/push/suscribir/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify(sub.toJSON()),
      });
    });
  }

  function showBanner(onEnable) {
    var lastDismiss = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
    var daysSince = (Date.now() - lastDismiss) / 86400000;
    if (lastDismiss && daysSince < DISMISS_DAYS) return;

    var bar = document.createElement('div');
    bar.id = 'sc-push-banner';
    bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;' +
      'background:var(--color-surface,#221414);border-top:1px solid var(--color-border,#3A2020);' +
      'padding:.75rem 1rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;' +
      'font-family:Inter,system-ui,sans-serif;box-shadow:0 -4px 16px rgba(0,0,0,.25);';
    bar.innerHTML =
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'style="color:var(--color-primary,#C4121A);flex-shrink:0;">' +
        '<path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>' +
      '</svg>' +
      '<span style="flex:1;min-width:180px;font-size:.8125rem;color:var(--color-text-primary,#F5EDEB);">' +
        'Activa las notificaciones para no perderte mensajes ni avisos, aunque no tengas el navegador abierto.' +
      '</span>' +
      '<button type="button" id="sc-push-enable" style="background:linear-gradient(135deg,#C4121A,#5A0B0B);color:#fff;' +
        'border:none;padding:.5rem 1rem;border-radius:.5rem;font-size:.78rem;font-weight:700;cursor:pointer;font-family:inherit;">' +
        'Activar' +
      '</button>' +
      '<button type="button" id="sc-push-dismiss" style="background:none;border:none;color:var(--color-text-muted,#7A6060);' +
        'font-size:1rem;cursor:pointer;padding:.25rem .5rem;line-height:1;">✕</button>';
    document.body.appendChild(bar);

    document.getElementById('sc-push-dismiss').addEventListener('click', function () {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
      bar.remove();
    });
    document.getElementById('sc-push-enable').addEventListener('click', function () {
      bar.remove();
      onEnable();
    });
  }

  function showDeniedHint() {
    var lastDismiss = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
    var daysSince = (Date.now() - lastDismiss) / 86400000;
    if (lastDismiss && daysSince < DISMISS_DAYS) return;

    var bar = document.createElement('div');
    bar.id = 'sc-push-banner';
    bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;' +
      'background:var(--color-surface,#221414);border-top:1px solid var(--color-border,#3A2020);' +
      'padding:.75rem 1rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;' +
      'font-family:Inter,system-ui,sans-serif;box-shadow:0 -4px 16px rgba(0,0,0,.25);';
    bar.innerHTML =
      '<span style="flex:1;min-width:220px;font-size:.78125rem;color:var(--color-text-secondary,#C0A8A8);">' +
        'Las notificaciones están bloqueadas para este sitio. Actívalas desde el candado 🔒 junto a la dirección del navegador (Permisos → Notificaciones).' +
      '</span>' +
      '<button type="button" id="sc-push-dismiss" style="background:none;border:none;color:var(--color-text-muted,#7A6060);' +
        'font-size:1rem;cursor:pointer;padding:.25rem .5rem;line-height:1;">✕</button>';
    document.body.appendChild(bar);
    document.getElementById('sc-push-dismiss').addEventListener('click', function () {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
      bar.remove();
    });
  }

  window.SCPush = {
    init: function (vapidPublicKey) {
      // El service worker se registra siempre que el navegador lo soporte
      // (habilita "Instalar app"), independiente de si el push ya está
      // configurado (VAPID_PUBLIC_KEY) o no.
      if (!swSupported()) return;

      navigator.serviceWorker.register('/sw.js').then(function (registration) {
        if (!pushSupported() || !vapidPublicKey) return;

        if (Notification.permission === 'granted') {
          subscribe(vapidPublicKey, registration).catch(function () {});
        } else if (Notification.permission === 'default') {
          showBanner(function () {
            Notification.requestPermission().then(function (perm) {
              if (perm === 'granted') subscribe(vapidPublicKey, registration).catch(function () {});
            });
          });
        } else if (Notification.permission === 'denied') {
          showDeniedHint();
        }
      }).catch(function () {});
    },
  };
})();
