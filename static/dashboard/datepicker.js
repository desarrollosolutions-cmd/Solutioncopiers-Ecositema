/* Calendario personalizado para agendar tareas y tickets (dashboard + panel).
 * Convierte cualquier <input class="dp-input" type="date"|"datetime-local">
 * en un selector con estetica propia, que ademas subraya (con un punto) los
 * dias que ya tienen tareas o tickets agendados, usando la fecha que llega
 * en el atributo data-occupied-url.
 *
 * El input original se reemplaza por:
 *   - un <input type="hidden"> con el mismo name (lo que realmente se envia)
 *   - un <input type="text" readonly> que muestra la fecha en dd/mm/aaaa
 *   - (si era datetime-local) un <input type="time"> nativo para la hora
 * asi el backend recibe exactamente el mismo formato que antes, sin cambios.
 */
(function () {
  'use strict';

  var MONTHS_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var WEEKDAYS_ES = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];

  var _occupiedCache = {};
  var _occupiedPromises = {};

  function fetchOccupied(url) {
    if (!url) return Promise.resolve({});
    if (_occupiedCache[url]) return Promise.resolve(_occupiedCache[url]);
    if (_occupiedPromises[url]) return _occupiedPromises[url];
    _occupiedPromises[url] = fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.ok ? r.json() : { dates: {} }; })
      .then(function (data) { _occupiedCache[url] = data.dates || {}; return _occupiedCache[url]; })
      .catch(function () { return {}; });
    return _occupiedPromises[url];
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function toISO(y, m, d) { return y + '-' + pad(m + 1) + '-' + pad(d); }
  function parseISODate(s) {
    if (!s) return null;
    var parts = s.split('-');
    if (parts.length < 3) return null;
    var y = parseInt(parts[0], 10), m = parseInt(parts[1], 10), d = parseInt(parts[2], 10);
    if (!y || !m || !d) return null;
    return new Date(y, m - 1, d);
  }
  function fmtDisplay(iso) {
    var d = parseISODate(iso);
    if (!d) return '';
    return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + '/' + d.getFullYear();
  }

  function DatePicker(input) {
    this.isDateTime = input.type === 'datetime-local';
    this.name = input.name;
    this.occupiedUrl = input.dataset.occupiedUrl || '';
    this.min = input.getAttribute('min') || null;
    this.max = input.getAttribute('max') || null;
    this.wasRequired = input.required;
    this.occupied = {};
    this.panelEl = null;

    var rawValue = input.value || '';
    var datePart = rawValue.split('T')[0] || '';
    var timePart = this.isDateTime ? (rawValue.split('T')[1] || '') : '';

    this.viewDate = parseISODate(datePart) || new Date();
    this.selectedISO = datePart || null;

    this._build(input, datePart, timePart);

    var self = this;
    fetchOccupied(this.occupiedUrl).then(function (data) {
      self.occupied = data;
      if (self.panelEl) self._renderGrid();
    });
  }

  DatePicker.prototype._build = function (input, datePart, timePart) {
    var wrap = document.createElement('div');
    wrap.className = 'dp-wrap';
    var extraStyle = input.getAttribute('style');
    if (extraStyle) wrap.setAttribute('style', extraStyle);
    input.parentNode.insertBefore(wrap, input);

    var hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = this.name;
    hidden.value = input.value || '';
    wrap.appendChild(hidden);
    this.hidden = hidden;

    var displayBox = document.createElement('div');
    displayBox.style.cssText = 'position:relative;flex:1;min-width:0;';
    var display = document.createElement('input');
    display.type = 'text';
    display.className = input.className + ' dp-display-input';
    display.readOnly = true;
    display.autocomplete = 'off';
    display.placeholder = 'dd/mm/aaaa';
    display.value = datePart ? fmtDisplay(datePart) : '';
    if (input.id) display.id = input.id;
    displayBox.appendChild(display);
    this.display = display;

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'dp-trigger';
    trigger.setAttribute('aria-label', 'Abrir calendario');
    trigger.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4.5" width="18" height="16" rx="2"/><path stroke-linecap="round" d="M8 3v3M16 3v3M3 9.5h18"/></svg>';
    displayBox.appendChild(trigger);
    this.trigger = trigger;

    wrap.appendChild(displayBox);

    if (this.isDateTime) {
      var timeInput = document.createElement('input');
      timeInput.type = 'time';
      timeInput.className = input.className + ' dp-time-input';
      timeInput.value = timePart;
      wrap.appendChild(timeInput);
      this.timeInput = timeInput;
      var self1 = this;
      timeInput.addEventListener('change', function () { self1._syncHidden(); });
    }

    input.parentNode.removeChild(input);

    var self2 = this;
    var open = function (e) { e.preventDefault(); self2.toggle(); };
    display.addEventListener('click', open);
    trigger.addEventListener('click', open);

    if (this.wasRequired) {
      var form = wrap.closest('form');
      if (form) {
        form.addEventListener('submit', function (e) {
          if (!self2.hidden.value) {
            e.preventDefault();
            self2.display.classList.add('dp-invalid');
            setTimeout(function () { self2.display.classList.remove('dp-invalid'); }, 1800);
            self2.display.scrollIntoView({ block: 'center', behavior: 'smooth' });
          }
        });
      }
    }

    this.wrap = wrap;
  };

  DatePicker.prototype._syncHidden = function () {
    if (!this.selectedISO) { this.hidden.value = ''; return; }
    if (this.isDateTime) {
      var t = (this.timeInput && this.timeInput.value) || '00:00';
      this.hidden.value = this.selectedISO + 'T' + t;
    } else {
      this.hidden.value = this.selectedISO;
    }
  };

  DatePicker.prototype.toggle = function () {
    if (this.panelEl) this.close(); else this.open();
  };

  DatePicker.prototype.open = function () {
    document.querySelectorAll('.dp-panel').forEach(function (p) {
      if (p._dp) p._dp.close();
    });
    var panel = document.createElement('div');
    panel.className = 'dp-panel';
    panel._dp = this;
    this.panelEl = panel;
    this.wrap.appendChild(panel);
    this._renderGrid();
    this._positionPanel();
    requestAnimationFrame(function () { panel.classList.add('dp-open'); });

    var self = this;
    this._onDocClick = function (e) { if (!self.wrap.contains(e.target)) self.close(); };
    document.addEventListener('mousedown', this._onDocClick);
    this._onResize = function () { self._positionPanel(); };
    window.addEventListener('resize', this._onResize);
  };

  DatePicker.prototype.close = function () {
    if (!this.panelEl) return;
    this.panelEl.remove();
    this.panelEl = null;
    document.removeEventListener('mousedown', this._onDocClick);
    window.removeEventListener('resize', this._onResize);
  };

  DatePicker.prototype._positionPanel = function () {
    var panel = this.panelEl;
    if (!panel) return;
    var rect = this.wrap.getBoundingClientRect();
    var spaceBelow = window.innerHeight - rect.bottom;
    panel.classList.toggle('dp-panel-up', spaceBelow < 340 && rect.top > 340);
  };

  DatePicker.prototype._renderGrid = function () {
    var panel = this.panelEl;
    if (!panel) return;
    var y = this.viewDate.getFullYear();
    var m = this.viewDate.getMonth();
    var firstDow = (new Date(y, m, 1).getDay() + 6) % 7;
    var daysInMonth = new Date(y, m + 1, 0).getDate();
    var now = new Date();
    var todayISO = toISO(now.getFullYear(), now.getMonth(), now.getDate());
    var hasOccupied = false;

    var html = '' +
      '<div class="dp-head">' +
        '<button type="button" class="dp-nav" data-nav="-1" aria-label="Mes anterior">&lsaquo;</button>' +
        '<div class="dp-title">' + MONTHS_ES[m] + ' ' + y + '</div>' +
        '<button type="button" class="dp-nav" data-nav="1" aria-label="Mes siguiente">&rsaquo;</button>' +
      '</div>' +
      '<div class="dp-weekdays">' + WEEKDAYS_ES.map(function (w) { return '<span>' + w + '</span>'; }).join('') + '</div>' +
      '<div class="dp-days">';

    for (var i = 0; i < firstDow; i++) html += '<span class="dp-day dp-empty"></span>';
    for (var d = 1; d <= daysInMonth; d++) {
      var iso = toISO(y, m, d);
      var classes = ['dp-day'];
      if (iso === todayISO) classes.push('dp-today');
      if (iso === this.selectedISO) classes.push('dp-selected');
      var count = this.occupied[iso];
      var title = '';
      if (count) {
        classes.push('dp-occupied');
        hasOccupied = true;
        title = ' title="' + count + (count === 1 ? ' tarea/ticket agendado ese dia' : ' tareas/tickets agendados ese dia') + '"';
      }
      if ((this.min && iso < this.min) || (this.max && iso > this.max)) classes.push('dp-disabled');
      html += '<button type="button" class="' + classes.join(' ') + '" data-date="' + iso + '"' + title + '>' + d +
        (count ? '<span class="dp-dot"></span>' : '') + '</button>';
    }
    html += '</div><div class="dp-foot">' +
      '<button type="button" class="dp-today-btn" data-today="1">Hoy</button>' +
      (hasOccupied ? '<span class="dp-legend"><span class="dp-dot"></span> con tareas/tickets</span>' : '') +
      '</div>';

    panel.innerHTML = html;

    var self = this;
    panel.querySelectorAll('[data-nav]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        self.viewDate = new Date(y, m + parseInt(btn.dataset.nav, 10), 1);
        self._renderGrid();
      });
    });
    panel.querySelectorAll('.dp-day:not(.dp-empty):not(.dp-disabled)').forEach(function (btn) {
      btn.addEventListener('click', function () { self._select(btn.dataset.date); });
    });
    var todayBtn = panel.querySelector('[data-today]');
    if (todayBtn) todayBtn.addEventListener('click', function () { self._select(todayISO); });
  };

  DatePicker.prototype._select = function (iso) {
    this.selectedISO = iso;
    this.display.value = fmtDisplay(iso);
    this.display.classList.remove('dp-invalid');
    this.viewDate = parseISODate(iso);
    this._syncHidden();
    this.close();
  };

  function enhance(root) {
    (root || document).querySelectorAll('input.dp-input').forEach(function (input) {
      if (input._dpDone) return;
      input._dpDone = true;
      new DatePicker(input);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { enhance(); });
  } else {
    enhance();
  }
  window.DPEnhance = enhance;
})();
