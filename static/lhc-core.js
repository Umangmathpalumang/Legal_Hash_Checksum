/**
 * LHC Core — legalhashchecksum.com Pro
 * Shared across all pages: theme, IndexedDB, device fingerprint, license popup, PWA.
 * Load in <head> (before any theme-related CSS or inline scripts).
 */
'use strict';
(function () {

// Import cases from the previous docket once per browser. Keep the old key for rollback.
(function migrateCases() {
  const oldKey = 'lhc_user_cases';
  const newKey = 'lhc_cases';
  const migratedKey = 'lhc-cases-migrated-v1';
  try {
    const raw = localStorage.getItem(oldKey);
    if (!raw || localStorage.getItem(migratedKey)) return;
    const legacy = JSON.parse(raw);
    const current = JSON.parse(localStorage.getItem(newKey) || '[]');
    if (!Array.isArray(legacy) || !Array.isArray(current)) return;
    const ids = new Set(current.filter(Boolean).map(c => Number(c.id)));
    let nextId = Date.now();
    for (const old of legacy) {
      if (!old || typeof old !== 'object' || (old.uid != null && current.some(c => c && c.legacyUid === old.uid))) continue;
      let id = Number(old.uid);
      if (!Number.isSafeInteger(id) || id < 1 || id > 8640000000000000 || ids.has(id)) {
        while (ids.has(nextId)) nextId++;
        id = nextId++;
      }
      ids.add(id);
      const parties = String(old.client || 'Unknown Parties');
      current.push({
        id, legacyUid: old.uid, clientName: parties, title: parties,
        caseId: String(old.id || 'Unnumbered Case'), caseNumber: String(old.id || ''),
        caseType: String(old.type || 'General'), court: String(old.court || ''),
        hearingDate: /^\d{4}-\d{2}-\d{2}$/.test(old.date) ? old.date : '',
        status: 'Active', createdAt: new Date(id).toISOString()
      });
    }
    localStorage.setItem(newKey, JSON.stringify(current));
    localStorage.setItem(migratedKey, '1');
  } catch (error) {
    // Keep the original records if storage is unavailable or malformed.
  }
})();

/* ═══════════════════════════════════════════════════════════════════
   1. THEME  —  auto-detect OS preference, persist manual override
   ═══════════════════════════════════════════════════════════════════ */
function _ls(k, v) {
  try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) {}
}
function _lsRm(k) { try { localStorage.removeItem(k); } catch(e) {} }

function _applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  _ls('lhc-theme', t);
  document.dispatchEvent(new CustomEvent('lhctheme', { detail: t }));
}

function _sysTheme() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light';
}

// Run immediately (in <head>) to eliminate flash of wrong theme
(function _initTheme() {
  _applyTheme(_ls('lhc-theme') || _sysTheme());
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme:dark)').addEventListener('change', function(e) {
      if (!_ls('lhc-theme-manual')) _applyTheme(e.matches ? 'dark' : 'light');
    });
  }
})();

window.LHCTheme = {
  /** Called by the theme-toggle button in the sidebar */
  toggle: function () {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    _ls('lhc-theme-manual', '1');
    _applyTheme(isDark ? 'light' : 'dark');
  },
  apply: _applyTheme,
  /** Remove manual override → follow system again */
  reset: function () { _lsRm('lhc-theme-manual'); _applyTheme(_sysTheme()); }
};


/* ═══════════════════════════════════════════════════════════════════
   2. IndexedDB — crash-safe backup layer on top of localStorage
      Usage: LHCDB.backup('cases','all', arr)  — fire-and-forget write
             LHCDB.restore('cases','all')       — returns Promise<value|null>
   ═══════════════════════════════════════════════════════════════════ */
var _idb = null;

function _openIDB() {
  if (_idb) return Promise.resolve(_idb);
  return new Promise(function (res, rej) {
    var req = indexedDB.open('lhc-pro-v1', 1);
    req.onupgradeneeded = function (e) {
      var db = e.target.result;
      ['cases','billing','timer','activity','meta'].forEach(function (s) {
        if (!db.objectStoreNames.contains(s)) db.createObjectStore(s);
      });
    };
    req.onsuccess = function (e) { _idb = e.target.result; res(_idb); };
    req.onerror   = function (e) { rej(e.target.error); };
  });
}

window.LHCDB = {
  get: function (store, key) {
    return _openIDB().then(function (db) {
      return new Promise(function (res, rej) {
        var r = db.transaction(store, 'readonly').objectStore(store).get(key);
        r.onsuccess = function () { res(r.result !== undefined ? r.result : null); };
        r.onerror   = function () { rej(r.error); };
      });
    });
  },
  set: function (store, key, val) {
    return _openIDB().then(function (db) {
      return new Promise(function (res, rej) {
        var r = db.transaction(store, 'readwrite').objectStore(store).put(val, key);
        r.onsuccess = function () { res(); };
        r.onerror   = function () { rej(r.error); };
      });
    });
  },
  del: function (store, key) {
    return _openIDB().then(function (db) {
      return new Promise(function (res, rej) {
        var r = db.transaction(store, 'readwrite').objectStore(store).delete(key);
        r.onsuccess = function () { res(); };
        r.onerror   = function () { rej(r.error); };
      });
    });
  },
  /** Write to IDB in background — never throws */
  backup: function (store, key, val) { this.set(store, key, val).catch(function () {}); },
  /** Read from IDB — use when localStorage might be empty after a crash */
  restore: function (store, key) { return this.get(store, key).catch(function () { return null; }); }
};


/* ═══════════════════════════════════════════════════════════════════
   3. DEVICE FINGERPRINT
      • Desktop (Electron): uses real MAC address via preload bridge
      • Browser / PWA:      SHA-256 of hardware characteristics
   ═══════════════════════════════════════════════════════════════════ */
window.LHCDevice = {
  fingerprint: function () {
    // Electron desktop app exposes __LHCDesktop via preload
    if (window.__LHCDesktop && typeof window.__LHCDesktop.getDeviceId === 'function') {
      return window.__LHCDesktop.getDeviceId().then(function (info) {
        return (info.mac || 'unknown') + '|' + (info.platform || '') + '|' + (info.hostname || '');
      });
    }
    // Browser / PWA fingerprint
    var parts = [
      navigator.userAgent,
      screen.width + 'x' + screen.height,
      screen.colorDepth,
      navigator.language || '',
      (typeof Intl !== 'undefined') ? Intl.DateTimeFormat().resolvedOptions().timeZone : '',
      navigator.hardwareConcurrency || 0,
      typeof navigator.deviceMemory !== 'undefined' ? navigator.deviceMemory : 'u'
    ].join('|');
    if (window.crypto && window.crypto.subtle && typeof TextEncoder !== 'undefined') {
      return window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(parts)).then(function (buf) {
        return Array.from(new Uint8Array(buf)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
      });
    }
    // Non-crypto fallback
    var h = 0;
    for (var i = 0; i < parts.length; i++) h = (Math.imul(31, h) + parts.charCodeAt(i)) | 0;
    return Promise.resolve(Math.abs(h).toString(16));
  }
};


/* ═══════════════════════════════════════════════════════════════════
   4. LICENSE  —  store / check expiry / show renewal popup
      License object: { plan, expiry (ISO date), email, device_id, activated_at }
   ═══════════════════════════════════════════════════════════════════ */
window.LHCLicense = {
  _KEY: 'lhc-pro-license',

  get: function () {
    try { return JSON.parse(localStorage.getItem(this._KEY) || 'null'); } catch (e) { return null; }
  },

  save: function (info) {
    try { localStorage.setItem(this._KEY, JSON.stringify(info)); } catch (e) {}
    LHCDB.backup('meta', 'license', info);
  },

  /**
   * Activate a new license (called from profile/settings page).
   * @param {string} plan       e.g. 'pro' | 'firm'
   * @param {string} expiry     ISO date string e.g. '2027-03-01'
   * @param {string} [email]    subscriber email
   * @returns Promise<licenseObject>
   */
  activate: function (plan, expiry, email) {
    var self = this;
    return window.LHCDevice.fingerprint().then(function (fp) {
      var info = {
        plan: plan,
        expiry: expiry,
        email: email || '',
        device_id: fp,
        activated_at: new Date().toISOString()
      };
      self.save(info);
      return info;
    });
  },

  /** Call on every page load — shows popup if expiry ≤ 7 days or already past */
  check: function () {
    var lic = this.get();
    if (!lic || !lic.expiry) return;
    var msLeft   = new Date(lic.expiry).getTime() - Date.now();
    var daysLeft = Math.ceil(msLeft / 86400000);
    if (daysLeft <= 7) this._showPopup(daysLeft, lic.plan || 'pro');
  },

  _showPopup: function (daysLeft, plan) {
    if (document.getElementById('lhc-renewal-modal')) return;
    var expired  = daysLeft <= 0;
    var color    = expired ? '#DC2626' : (daysLeft <= 3 ? '#D97706' : '#2563EB');
    var label    = plan.charAt(0).toUpperCase() + plan.slice(1).replace(/-/g, ' ');
    var title    = expired ? 'Subscription Expired' : 'Renewal in ' + daysLeft + ' day' + (daysLeft === 1 ? '' : 's');
    var body     = expired
      ? 'Your LHC <strong>' + label + '</strong> subscription has expired. Renew now to restore access to all Pro features.'
      : 'Your LHC <strong>' + label + '</strong> plan expires in <strong>' + daysLeft + ' day' + (daysLeft === 1 ? '' : 's') + '</strong>. Renew to avoid disruption.';
    var later    = expired ? '' :
      '<button onclick="document.getElementById(\'lhc-renewal-modal\').remove()" style="flex-shrink:0;background:var(--sur2,#f1f5f9);border:1px solid var(--bd,#e2e8f0);color:var(--tx2,#64748b);padding:12px 18px;border-radius:11px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">Later</button>';

    var overlay = document.createElement('div');
    overlay.id = 'lhc-renewal-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)';
    overlay.innerHTML =
      '<div style="background:var(--sur,#fff);border-radius:20px;padding:28px 26px 26px;max-width:420px;width:100%;box-shadow:0 32px 100px rgba(0,0,0,.4);font-family:var(--sans,\'Plus Jakarta Sans\',system-ui,sans-serif)">'
    + '<div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:18px">'
    + '<div style="width:46px;height:46px;min-width:46px;border-radius:14px;background:' + color + '18;display:flex;align-items:center;justify-content:center">'
    + '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    + '</div>'
    + '<div style="flex:1"><div style="font-size:16px;font-weight:800;color:var(--tx,#0f172a);line-height:1.2">' + title + '</div>'
    + '<div style="font-size:12px;color:var(--tx2,#64748b);margin-top:4px;font-weight:500">LHC ' + label + ' License</div></div>'
    + '</div>'
    + '<p style="font-size:14px;color:var(--tx2,#475569);line-height:1.7;margin:0 0 22px">' + body + '</p>'
    + '<div style="display:flex;gap:10px;align-items:center">'
    + '<a href="/pricing" style="flex:1;background:' + color + ';color:#fff;padding:13px;border-radius:12px;font-size:14px;font-weight:700;text-decoration:none;text-align:center;display:block;font-family:inherit">' + (expired ? 'Reactivate Now' : 'Renew Now →') + '</a>'
    + later
    + '</div>'
    + '</div>';

    document.body.appendChild(overlay);
    if (!expired) overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
  }
};


/* ═══════════════════════════════════════════════════════════════════
   5. USAGE GATE — 3 uses / feature / month for free users
      Pro license holders bypass all limits automatically.
   ═══════════════════════════════════════════════════════════════════ */
var _FREE_LIMIT = 3;
var _GATE_KEY   = 'lhc-usage';

var _GATE_LABELS = {
  'vakalatnama':         'Vakalatnama Generator',
  'bail-bond':           'Bail Bond Generator',
  'memo-appearance':     'Memo of Appearance',
  'legal-notice':        'Legal Notice Generator',
  'legal-notice-custom': 'Legal Notice (Custom)',
  'stamp-generator':     'Advocate Stamp Generator',
  'hash':                'Hash Evidence Tool'
};

function _getUsage() {
  try {
    var raw      = localStorage.getItem(_GATE_KEY);
    var u        = raw ? JSON.parse(raw) : null;
    var thisMonth = new Date().toISOString().slice(0, 7); // 'YYYY-MM'
    if (!u || u.month !== thisMonth) {
      u = { month: thisMonth, counts: {} };
      localStorage.setItem(_GATE_KEY, JSON.stringify(u));
    }
    return u;
  } catch (e) { return { month: '', counts: {} }; }
}

function _saveUsage(u) {
  try { localStorage.setItem(_GATE_KEY, JSON.stringify(u)); } catch (e) {}
  if (window.LHCDB) LHCDB.backup('meta', 'usage', u);
}

function _isPro() {
  var lic = window.LHCLicense && window.LHCLicense.get();
  return lic && lic.expiry && new Date(lic.expiry) > new Date();
}

window.LHCGate = {
  /** Check without incrementing. Returns {allowed, used, remaining, limit} */
  check: function (feature) {
    if (_isPro()) return { allowed: true, used: 0, remaining: Infinity, limit: _FREE_LIMIT };
    var u    = _getUsage();
    var used = (u.counts[feature] || 0);
    return {
      allowed:   used < _FREE_LIMIT,
      used:      used,
      remaining: Math.max(0, _FREE_LIMIT - used),
      limit:     _FREE_LIMIT
    };
  },

  /** Increment usage, then return check result */
  use: function (feature) {
    if (_isPro()) return { allowed: true, used: 0, remaining: Infinity, limit: _FREE_LIMIT };
    var u    = _getUsage();
    var used = (u.counts[feature] || 0);
    if (used < _FREE_LIMIT) {
      u.counts[feature] = used + 1;
      _saveUsage(u);
    }
    return this.check(feature);
  },

  /**
   * Patch window.print so it runs the gate before printing.
   * Call at the BOTTOM of the page script (after any existing print overrides).
   */
  patchPrint: function (feature) {
    var self = this;
    var orig = window.print.bind(window);
    window.print = function () {
      var r = self.use(feature);
      if (r.allowed) { orig(); }
      else { self._showModal(_GATE_LABELS[feature] || feature, r); }
    };
  },

  /**
   * Wrap any function with the gate.
   * Usage: window.downloadPNG = LHCGate.patchFn('stamp-generator', window.downloadPNG);
   */
  patchFn: function (feature, fn) {
    var self = this;
    return function () {
      var args = arguments, ctx = this;
      var r = self.use(feature);
      if (r.allowed) { return fn.apply(ctx, args); }
      else { self._showModal(_GATE_LABELS[feature] || feature, r); }
    };
  },

  _showModal: function (label, r) {
    if (document.getElementById('lhc-gate-modal')) return;
    var d = new Date();
    d.setMonth(d.getMonth() + 1, 1);
    var resets = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
    var ov = document.createElement('div');
    ov.id = 'lhc-gate-modal';
    ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)';
    ov.innerHTML =
      '<div style="background:var(--sur,#fff);border-radius:20px;padding:28px 26px 26px;max-width:400px;width:100%;box-shadow:0 32px 100px rgba(0,0,0,.4);font-family:var(--sans,\'Plus Jakarta Sans\',system-ui,sans-serif)">'
    + '<div style="width:50px;height:50px;border-radius:14px;background:#FEF3C720;border:1.5px solid #FCD34D;display:flex;align-items:center;justify-content:center;margin-bottom:16px">'
    + '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>'
    + '<div style="font-size:18px;font-weight:800;color:var(--tx,#0f172a);margin-bottom:8px">Free Limit Reached</div>'
    + '<p style="font-size:14px;color:var(--tx2,#475569);line-height:1.65;margin:0 0 6px">'
    + 'You\'ve used <strong>' + label + '</strong> <strong>' + _FREE_LIMIT + '&hairsp;/&hairsp;' + _FREE_LIMIT + ' times</strong> this month.</p>'
    + '<p style="font-size:13px;color:var(--tx3,#94a3b8);margin:0 0 22px">Resets on <strong>' + resets + '</strong>&nbsp; · &nbsp;Upgrade for unlimited access.</p>'
    + '<div style="display:flex;gap:10px;align-items:center">'
    + '<a href="/pricing" style="flex:1;background:#1D4ED8;color:#fff;padding:13px;border-radius:12px;font-size:14px;font-weight:700;text-decoration:none;text-align:center;display:block;font-family:inherit">Upgrade to Pro →</a>'
    + '<button onclick="document.getElementById(\'lhc-gate-modal\').remove()" style="background:var(--sur2,#f1f5f9);border:1px solid var(--bd,#e2e8f0);color:var(--tx2,#64748b);padding:13px 16px;border-radius:12px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">Close</button>'
    + '</div></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
  }
};


/* ═══════════════════════════════════════════════════════════════════
   6. PWA — register service worker
   ═══════════════════════════════════════════════════════════════════ */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js').catch(function () {});
  });
}

})();
