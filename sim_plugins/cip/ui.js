/* CIP dashboard renderer. Called by the shell on every poll.
 *
 * Follows ISA-101 for layout and color semantics and ISA-18.2 for
 * alarm presentation. Reads only what the server exposes; never
 * recomputes physics.
 *
 * Layout rules applied:
 *  - Numeric values use tabular figures (ISO 9241-303).
 *  - Colors are muted for normal state; saturated colors are reserved
 *    for alarms (red/amber) and for the "flowing" indication.
 *  - A persistent mode banner and alarm banner sit at the top of the
 *    page so state and alarms are always visible (ISA-101 §8, §18.2 §6).
 *  - Trends include y-scale, min/max in window, and tabular current.
 *  - Respects prefers-reduced-motion (WCAG 2.3.3).
 */
(function () {
  'use strict';

  // --- Colour, fluid code -> muting-friendly CSS class --------------
  var FLUID_CLASS = { 1: 'water', 2: 'caustic', 3: 'acid', 4: 'mixture' };
  var FLUID_FILL = {
    1: '#8cafc8',   // water, pale steel blue
    2: '#d4b77c',   // caustic, pale amber
    3: '#d4a0b4',   // acid, pale rose
    4: '#b0a8bc',   // mixture, pale grey-purple
  };

  // --- Fault information with ISA-18.2 priority --------------------
  //    Bit index follows the plugin's FaultWord definition.
  var FAULT_INFO = {
    0: { label: 'Pump on without liquid',   prio: 'medium'   },
    1: { label: 'Pump on without flow route', prio: 'medium' },
    2: { label: 'Multiple source valves open', prio: 'medium' },
    3: { label: 'Overtemperature',           prio: 'critical' },
    4: { label: 'Drain blocked by residue',  prio: 'high'     },
  };
  var PRIO_RANK = { critical: 3, high: 2, medium: 1 };

  // --- Trend windows -----------------------------------------------
  var HIST_MAX = 90;
  var levelHist = [];
  var tempHist = [];
  var lastHistPush = 0;

  // --- Alarm tracking for durations --------------------------------
  var _prevFaultWord = 0;
  var _faultOnset = {};           // bit index -> timestamp

  // --- Small helpers -----------------------------------------------
  function el(id) { return document.getElementById(id); }
  function txt(id, s) { var e = el(id); if (e) e.textContent = s; }
  function setClass(id, cls) { var e = el(id); if (e) e.className = cls; }

  function setPipe(id, active, fluid) {
    var e = el(id);
    if (!e) return;
    e.setAttribute('class', 'pipe' + (active && fluid ? ' flow ' + fluid : ''));
  }
  function setValve(id, commanded, flowing) {
    var e = el(id);
    if (!e) return;
    var cls = 'valve';
    if (flowing)      cls += ' flow';
    else if (commanded) cls += ' cmd';
    e.setAttribute('class', cls);
  }

  function fmt(value, digits) {
    if (typeof value !== 'number' || !isFinite(value)) return '—';
    return value.toFixed(digits);
  }
  function fmtDuration(ms) {
    var s = Math.floor(ms / 1000);
    if (s < 60) return s + 's';
    var m = Math.floor(s / 60);
    s = s % 60;
    if (m < 60) return m + 'm ' + s + 's';
    var h = Math.floor(m / 60);
    m = m % 60;
    return h + 'h ' + m + 'm';
  }

  // --- State derivation (ISA-101 process state) --------------------
  function deriveProcessState(s, branches) {
    if (s.FaultWord !== 0) return { label: 'Fault',   kind: 'fault',    seq: s.SequenceHint || 'Fault' };
    if (branches.chemicalRecovery) return { label: 'Running', kind: 'running', seq: 'Chemical recovery' };
    if (branches.waterInlet || branches.causticInlet || branches.acidInlet) {
      var what = branches.waterInlet   ? 'Water in'
               : branches.causticInlet ? 'Caustic in'
               :                         'Acid in';
      return { label: 'Running', kind: 'running', seq: what };
    }
    if (branches.pumpRunning && branches.returnFlow) return { label: 'Running', kind: 'running', seq: 'Circulating' };
    if (branches.drainFlow || branches.gravityDrain) return { label: 'Running', kind: 'running', seq: 'Draining' };
    if (s.StatusWord & (1 << 5)) return { label: 'Heating', kind: 'heating', seq: 'Heating (idle flow)' };
    return { label: 'Idle', kind: 'idle', seq: s.SequenceHint || 'Idle' };
  }

  function deriveAction(s, branches) {
    if (s.FaultWord !== 0) return 'Fault';
    if (branches.chemicalRecovery) return 'Chemical recovery';
    var inlet =
      branches.waterInlet   ? 'water'   :
      branches.causticInlet ? 'caustic' :
      branches.acidInlet    ? 'acid'    : null;
    var heat = (s.StatusWord & (1 << 5)) ? ' + heating' : '';
    if (inlet && branches.returnFlow) return 'Wash / circulate (' + inlet + ')' + heat;
    if (inlet) return 'Filling: ' + inlet + heat;
    if (branches.returnFlow) return 'Circulating (return)' + heat;
    if (branches.drainFlow) return 'Draining (pumped)';
    if (branches.gravityDrain) return 'Draining (gravity)';
    if (heat) return 'Heating (idle flow)';
    return 'Idle';
  }

  // --- Mode banner (ISA-101 §8) ------------------------------------
  function renderModeBanner(s, branches) {
    var state = deriveProcessState(s, branches);
    var badge = el('mode-badge');
    if (badge) {
      badge.className = 'mode-badge ' + state.kind;
      badge.textContent = state.label;
    }
    txt('mode-seq', state.seq);
    var now = new Date();
    txt('mode-when',
      String(now.getHours()).padStart(2, '0') + ':' +
      String(now.getMinutes()).padStart(2, '0') + ':' +
      String(now.getSeconds()).padStart(2, '0'));
  }

  // --- Alarm banner (ISA-18.2 §6.3) --------------------------------
  function renderAlarmBanner(word) {
    var bits = [];
    for (var b = 0; b < 16; b++) {
      if (word & (1 << b)) bits.push(b);
    }
    var banner = el('alarm-banner');
    if (!banner) return;

    if (!bits.length) {
      banner.className = 'alarm-banner';
      return;
    }

    // Highest priority among active bits.
    var highest = 'medium';
    var highestLabel = FAULT_INFO[bits[0]] ? FAULT_INFO[bits[0]].label : 'Fault';
    for (var i = 0; i < bits.length; i++) {
      var info = FAULT_INFO[bits[i]] || { label: 'Fault bit ' + bits[i], prio: 'medium' };
      if ((PRIO_RANK[info.prio] || 0) > (PRIO_RANK[highest] || 0)) {
        highest = info.prio;
        highestLabel = info.label;
      }
    }

    banner.className = 'alarm-banner active ' + highest;
    txt('alarm-count', String(bits.length));
    txt('alarm-msg', highestLabel +
        (bits.length > 1 ? ' (+' + (bits.length - 1) + ' more)' : ''));
  }

  // --- Alarm list (ISA-18.2 §6.4) ----------------------------------
  function renderAlarmList(word) {
    var now = Date.now();

    // Update onset tracking. One-time record per new bit.
    for (var b = 0; b < 16; b++) {
      var bit = 1 << b;
      var was = (_prevFaultWord & bit) !== 0;
      var is  = (word & bit) !== 0;
      if (is && !was)      _faultOnset[b] = now;
      else if (!is && was) delete _faultOnset[b];
    }
    _prevFaultWord = word;

    var host = el('faults');
    if (!host) return;
    host.innerHTML = '';

    var active = [];
    for (var i = 0; i < 16; i++) {
      if (word & (1 << i)) active.push(i);
    }

    if (!active.length) {
      var ok = document.createElement('div');
      ok.className = 'alarm-none';
      ok.textContent = 'No active alarms';
      host.appendChild(ok);
      return;
    }

    // Sort by priority (highest first), then by bit index.
    active.sort(function (a, b) {
      var pa = PRIO_RANK[(FAULT_INFO[a] || {}).prio] || 0;
      var pb = PRIO_RANK[(FAULT_INFO[b] || {}).prio] || 0;
      if (pa !== pb) return pb - pa;
      return a - b;
    });

    active.forEach(function (b) {
      var info = FAULT_INFO[b] || { label: 'Fault bit ' + b, prio: 'medium' };
      var row  = document.createElement('div');
      row.className = 'alarm-item-ii ' + info.prio;

      var prio = document.createElement('span');
      prio.className = 'prio';
      prio.textContent = info.prio;

      var text = document.createElement('span');
      text.className = 'text';
      text.textContent = info.label;

      var dur = document.createElement('span');
      dur.className = 'time';
      var onset = _faultOnset[b];
      dur.textContent = onset ? fmtDuration(now - onset) : '—';

      row.appendChild(prio);
      row.appendChild(text);
      row.appendChild(dur);
      host.appendChild(row);
    });
  }

  // --- Trend drawing -----------------------------------------------
  function pushHist(arr, v) {
    arr.push(v);
    if (arr.length > HIST_MAX) arr.shift();
  }

  function drawTrend(id, arr, lo, hi, color) {
    var c = el(id);
    if (!c) return;
    var ctx = c.getContext('2d');
    var w = c.width, h = c.height;
    ctx.clearRect(0, 0, w, h);

    // Gridlines at 25/50/75 % — subtle grey, not decorative.
    ctx.strokeStyle = '#e8ecf0';
    ctx.lineWidth = 1;
    for (var g = 1; g < 4; g++) {
      var gy = Math.round((g / 4) * (h - 4)) + 2;
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke();
    }
    // Baseline.
    ctx.beginPath(); ctx.moveTo(0, h - 2); ctx.lineTo(w, h - 2); ctx.stroke();

    if (arr.length < 2) return;

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (var i = 0; i < arr.length; i++) {
      var x = (i / (HIST_MAX - 1)) * w;
      var norm = Math.max(0, Math.min((arr[i] - lo) / (hi - lo), 1));
      var y = h - norm * (h - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else         ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function updateTrendStats(suffix, arr) {
    if (arr.length < 1) {
      txt('tr-' + suffix + '-minmax', '—');
      return;
    }
    var mn = Math.min.apply(null, arr);
    var mx = Math.max.apply(null, arr);
    txt('tr-' + suffix + '-minmax',
        'min ' + mn.toFixed(1) + ' / max ' + mx.toFixed(1));
  }

  // --- Threshold coloring on metrics (ISA-101 §10.3) ---------------
  function setTileThreshold(tileId, value, warnAt, critAt) {
    var tile = el(tileId);
    if (!tile) return;
    var base = 'cip-tile';
    if (value >= critAt)      tile.className = base + ' crit';
    else if (value >= warnAt) tile.className = base + ' warn';
    else                      tile.className = base;
  }

  // --- Equipment status dots ---------------------------------------
  function setDot(id, on) {
    var e = el(id);
    if (!e) return;
    e.className = 'dot ' + (on ? 'on' : 'off');
  }

  // ================================================================
  // Main render
  // ================================================================
  window.renderState = function (state) {
    var m = state.measurements || {};
    var s = state.status || {};
    var branches = {
      waterInlet:       !!s.waterInlet,
      causticInlet:     !!s.causticInlet,
      acidInlet:        !!s.acidInlet,
      pumpRunning:      !!s.pumpRunning,
      returnFlow:       !!s.returnFlow,
      drainFlow:        !!s.drainFlow,
      gravityDrain:     !!s.gravityDrain,
      drainBlocked:     !!s.drainBlocked,
      chemicalRecovery: !!s.chemicalRecovery,
    };
    var word = (s.FaultWord | 0);

    // --- Banners ---
    renderModeBanner(s, branches);
    renderAlarmBanner(word);
    renderAlarmList(word);

    // --- Metric tiles (tabular + threshold) ---
    var level = m.LevelPercent || 0;
    var flow  = m.FlowLpm      || 0;
    var temp  = m.TemperatureC || 20;
    var cond  = m.Conductivity || 0;

    txt('m-level', fmt(level, 1));
    txt('m-flow',  fmt(flow, 1));
    txt('m-temp',  fmt(temp, 1));
    txt('m-cond',  fmt(cond, 1));

    setTileThreshold('tile-level', level, 80, 95);
    setTileThreshold('tile-temp',  temp,  70, 85);

    // --- Tank fill (muted fluid palette) ---
    var top = 186, H = 238;
    var lvl = Math.max(0, Math.min(level, 100));
    var fillH = H * lvl / 100;
    var liq = el('liquid');
    if (liq) {
      liq.setAttribute('y', (top + H - fillH).toFixed(1));
      liq.setAttribute('height', fillH.toFixed(1));
      var fill = FLUID_FILL[s.LiquidCode] || '#e8ecf0';
      liq.setAttribute('fill', fill);
    }
    txt('liquid-name', s.LiquidName || 'Empty');

    // --- Pipes (server-driven branches, muted colors) ---
    var fluid = FLUID_CLASS[s.LiquidCode] || 'water';
    var suction = branches.pumpRunning && flow > 0.1;
    setPipe('p-water',   branches.waterInlet,   'water');
    setPipe('p-acid',    branches.acidInlet,    'acid');
    setPipe('p-caustic', branches.causticInlet, 'caustic');
    setPipe('p-suction', suction || branches.gravityDrain, fluid);
    setPipe('p-common',  suction || branches.gravityDrain, fluid);
    setPipe('p-return',  branches.returnFlow, fluid);
    setPipe('p-drain',   branches.drainFlow || branches.gravityDrain, fluid);

    // --- Valves ---
    setValve('v-water',   false, branches.waterInlet);
    setValve('v-acid',    false, branches.acidInlet);
    setValve('v-caustic', false, branches.causticInlet);
    setValve('v-return',  false, branches.returnFlow);
    setValve('v-drain',   false, branches.drainFlow || branches.gravityDrain);

    // --- Pump & heater ---
    setClass('pump',
      branches.pumpRunning ? 'pump-run' : 'equip');

    var heaterOn = (s.StatusWord & (1 << 5)) !== 0;
    setClass('heater', heaterOn ? 'heater-on' : 'heater-off');
    txt('caustic-temp', fmt(m.CausticTankTempC || 20, 1) + ' °C');

    // --- State panel ---
    var pumpText = branches.pumpRunning
      ? 'Running'
      : (flow > 0.1 ? 'Running (gravity)' : 'Stopped');
    txt('s-pump',   pumpText);
    txt('s-action', deriveAction(s, branches));
    txt('s-liquid', s.LiquidName || 'Empty');
    txt('s-level',  fmt(level, 1) + ' %');
    txt('s-route',  s.RouteName || 'Closed');

    // --- Heating panel ---
    txt('h-cmd',  heaterOn ? 'On' : 'Off');
    txt('h-temp', fmt(m.CausticTankTempC || 20, 1) + ' °C');
    // Setpoint: available only if the plugin publishes commands in
    // snapshot(). Degrades gracefully to '—' otherwise.
    if (state.commands && typeof state.commands.CausticTempSetpointC === 'number') {
      txt('h-sp', fmt(state.commands.CausticTempSetpointC, 1) + ' °C');
    } else {
      txt('h-sp', '—');
    }

    // --- Equipment status dots ---
    setDot('dot-pump',   branches.pumpRunning);
    setDot('dot-water',  branches.waterInlet);
    setDot('dot-acid',   branches.acidInlet);
    setDot('dot-caustic', branches.causticInlet);
    setDot('dot-return', branches.returnFlow);
    setDot('dot-drain',  branches.drainFlow || branches.gravityDrain);
    setDot('dot-heat',   heaterOn);
    setDot('dot-flow',   flow > 0.1);

    // --- Trends: push at most 1 Hz so the 90-sample window spans ~90 s ---
    var now = Date.now();
    if (now - lastHistPush >= 1000) {
      lastHistPush = now;
      pushHist(levelHist, level);
      pushHist(tempHist,  temp);
      txt('tr-level-v', fmt(level, 1));
      txt('tr-temp-v',  fmt(temp, 1));
      updateTrendStats('level', levelHist);
      updateTrendStats('temp',  tempHist);
    }
    drawTrend('tr-level', levelHist, 0, 100, '#1e88e5');
    drawTrend('tr-temp',  tempHist, 10, 90, '#d97706');
  };
})();