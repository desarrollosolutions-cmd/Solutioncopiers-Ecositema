/* Banner "Instalar app" — no dependemos solo del aviso automatico del
 * navegador (a veces no aparece o el usuario ya lo cerro sin querer):
 * capturamos el evento de Chrome/Edge y mostramos nuestro propio boton,
 * y para Firefox/Safari (que no ofrecen ese evento) damos instrucciones
 * claras de como instalarla manualmente en cada uno. */
(function () {
  'use strict';

  var DISMISS_KEY = 'sc-install-dismissed-at';
  var DISMISS_DAYS = 7;
  var deferredPrompt = null;

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }
  function isFirefox() { return /Firefox/i.test(navigator.userAgent) && !/Seamonkey/i.test(navigator.userAgent); }
  function isIOS() { return /iPhone|iPad|iPod/i.test(navigator.userAgent); }
  function isSafari() { return /^((?!chrome|android|crios|fxios).)*safari/i.test(navigator.userAgent); }

  function recentlyDismissed() {
    var lastDismiss = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
    var daysSince = (Date.now() - lastDismiss) / 86400000;
    return !!(lastDismiss && daysSince < DISMISS_DAYS);
  }
  function markDismissed() { localStorage.setItem(DISMISS_KEY, String(Date.now())); }

  function makeBar() {
    var bar = document.createElement('div');
    bar.id = 'sc-install-banner';
    bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:10000;' +
      'background:var(--color-surface,#221414);border-top:1px solid var(--color-border,#3A2020);' +
      'padding:.75rem 1rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;' +
      'font-family:Inter,system-ui,sans-serif;box-shadow:0 -4px 16px rgba(0,0,0,.25);';
    return bar;
  }

  function showChromeBanner() {
    if (isStandalone() || document.getElementById('sc-install-banner') || recentlyDismissed()) return;
    var bar = makeBar();
    bar.innerHTML =
      '<img src="/static/images/icons/icon-192.png" alt="" style="width:28px;height:28px;border-radius:6px;flex-shrink:0;">' +
      '<span style="flex:1;min-width:180px;font-size:.8125rem;color:var(--color-text-primary,#F5EDEB);">Instala esta app en tu celular o PC para un acceso más rápido.</span>' +
      '<button type="button" id="sc-install-btn" style="background:linear-gradient(135deg,#C4121A,#5A0B0B);color:#fff;border:none;padding:.5rem 1rem;border-radius:.5rem;font-size:.78rem;font-weight:700;cursor:pointer;font-family:inherit;">Instalar</button>' +
      '<button type="button" id="sc-install-dismiss" style="background:none;border:none;color:var(--color-text-muted,#7A6060);font-size:1rem;cursor:pointer;padding:.25rem .5rem;line-height:1;">✕</button>';
    document.body.appendChild(bar);
    document.getElementById('sc-install-dismiss').addEventListener('click', function () { markDismissed(); bar.remove(); });
    document.getElementById('sc-install-btn').addEventListener('click', function () {
      bar.remove();
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () { deferredPrompt = null; });
    });
  }

  function showInfoBanner(html) {
    if (isStandalone() || document.getElementById('sc-install-banner') || recentlyDismissed()) return;
    var bar = makeBar();
    bar.innerHTML =
      '<span style="flex:1;min-width:200px;font-size:.78125rem;color:var(--color-text-secondary,#C0A8A8);">' + html + '</span>' +
      '<button type="button" id="sc-install-dismiss" style="background:none;border:none;color:var(--color-text-muted,#7A6060);font-size:1rem;cursor:pointer;padding:.25rem .5rem;line-height:1;flex-shrink:0;">✕</button>';
    document.body.appendChild(bar);
    document.getElementById('sc-install-dismiss').addEventListener('click', function () { markDismissed(); bar.remove(); });
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showChromeBanner();
  });

  window.addEventListener('appinstalled', function () {
    var bar = document.getElementById('sc-install-banner');
    if (bar) bar.remove();
    deferredPrompt = null;
  });

  // Si el navegador no dispara beforeinstallprompt (Firefox, Safari), no hay
  // boton que ofrecer -- pero si damos los pasos manuales de cada uno.
  setTimeout(function () {
    if (deferredPrompt || isStandalone()) return;
    if (isIOS() && isSafari()) {
      showInfoBanner('Para instalar esta app: toca <strong>Compartir</strong> (el ícono de la flecha ⬆) y luego <strong>"Agregar a pantalla de inicio"</strong>.');
    } else if (isFirefox()) {
      showInfoBanner('Firefox no permite instalar esta app automáticamente. Para instalarla, abre este mismo sitio con <strong>Chrome</strong> (Android/PC) o <strong>Safari</strong> (iPhone).');
    }
  }, 2500);
})();
