/* Macro page: rates, Fed stance & regime. Dependency-free except Chart.js.
   Perf/hardening: parallel snapshot+impact (progressive render), 12s abort
   timeout per fetch, stale-while-revalidate, #mc-countdown driver. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var TEST = (typeof window.TEST_MODE !== "undefined") && !!window.TEST_MODE;
  var SNAP_URL = "/api/macro/snapshot";
  var INTEL_URL = function (t) { return "/api/intel/macro/" + encodeURIComponent(t); };
  var POLL_MS = 5 * 60 * 1000;
  var FETCH_TIMEOUT_MS = 12000;

  /* Stale-while-revalidate: last good snapshot kept in memory. */
  var lastGood = null;
  var remainSec = Math.round(POLL_MS / 1000);
  var countdownTimer = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function num(v) {
    if (v == null || v === "" || isNaN(Number(v))) return null;
    return Number(v);
  }
  function fmtV(v, digits) {
    var n = num(v);
    if (n == null) return "--";
    return n.toFixed(digits == null ? 2 : digits);
  }
  function fmtChg(v) {
    var n = num(v);
    if (n == null) return { t: "--", c: "flat" };
    var s = (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
    return { t: s, c: n > 0.005 ? "up" : (n < -0.005 ? "dn" : "flat") };
  }
  function toast(m, t) {
    try { if (typeof showToast === "function") showToast(m, t || "info"); } catch (e) {}
  }
  function setText(el, t) {
    try { if (el) el.textContent = t; } catch (e) {}
  }

  /* Fetch JSON with an AbortController timeout so one slow endpoint
     can't hang the page. Rejects with AbortError on timeout. */
  function fetchJson(url, timeoutMs) {
    var ms = timeoutMs == null ? FETCH_TIMEOUT_MS : timeoutMs;
    var Ctrl = null;
    try { Ctrl = (typeof AbortController !== "undefined") ? AbortController : null; } catch (e) { Ctrl = null; }
    if (!Ctrl) {
      return fetch(url).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      });
    }
    var ctrl = new Ctrl();
    var timer = null;
    try {
      timer = setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, ms);
    } catch (e) { timer = null; }
    return fetch(url, { signal: ctrl.signal }).then(function (r) {
      if (timer) clearTimeout(timer);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).catch(function (e) {
      if (timer) clearTimeout(timer);
      throw e;
    });
  }

  /* Normalize a gauge entry: backend may send a bare number or an object. */
  function normGauge(raw) {
    if (raw == null) return { value: null, chg: null };
    if (typeof raw === "number" || typeof raw === "string") {
      return { value: num(raw), chg: null };
    }
    return {
      value: num(raw.value != null ? raw.value : (raw.price != null ? raw.price : raw.level)),
      chg: num(raw.change_pct != null ? raw.change_pct : (raw.change != null ? raw.change : (raw.day_change != null ? raw.day_change : raw.chg)))
    };
  }
  function pick(obj, keys) {
    for (var i = 0; i < keys.length; i++) {
      if (obj && obj[keys[i]] != null) return obj[keys[i]];
    }
    return null;
  }

  var GAUGES = [
    { keys: ["vix"], label: "VIX", invert: true },
    { keys: ["dollar", "dxy", "dx_y"], label: "Dollar", invert: false },
    { keys: ["gold", "gold_price", "xau"], label: "Gold", invert: false },
    { keys: ["oil", "wti", "crude", "brent"], label: "Oil", invert: false },
    { keys: ["hyg_tlt_ratio", "hyg_tlt", "credit", "hyg", "tlt", "credit_proxy"], label: "HYG/TLT", invert: false }
  ];

  function renderRegime(regime) {
    var label = $("mc-regime-label"), score = $("mc-regime-score"), list = $("mc-regime-reasons");
    if (!regime) {
      setText(label, "Regime unavailable");
      setText(score, "");
      if (list) list.innerHTML = "";
      return;
    }
    setText(label, regime.label || "Unknown regime");
    var sc = num(regime.score);
    setText(score, sc == null ? "" : ("votes " + sc.toFixed(0) + " (heuristic)"));
    var rs = regime.reasons || [];
    if (list) {
      list.innerHTML = rs.length
        ? rs.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("")
        : "<li>Watch rate direction and credit spreads for confirmation.</li>";
    }
  }

  function renderFed(fed) {
    var label = $("mc-fed-label"), list = $("mc-fed-reasons");
    if (!fed) {
      setText(label, "--");
      if (list) list.innerHTML = "<li>Fed stance unavailable.</li>";
      return;
    }
    setText(label, fed.label || "--");
    var rs = fed.reasons || [];
    if (list) {
      list.innerHTML = rs.length
        ? rs.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("")
        : "<li>No stated reasons.</li>";
    }
  }

  function curveSpread(points) {
    var y3m = null, y10 = null, i;
    for (i = 0; i < points.length; i++) {
      var l = String(points[i].label || "").toUpperCase().replace(/\s/g, "");
      if (l === "3M" || l === "3MO" || l === "13W" || l === "13WK") y3m = num(points[i].yield);
      if (l === "10Y" || l === "10YR") y10 = num(points[i].yield);
    }
    if (y3m == null || y10 == null) return null;
    return y10 - y3m;
  }

  function renderCurve(yields) {
    var cv = $("mc-curve"), badge = $("mc-inv"), spread = $("mc-spread"), empty = $("mc-curve-empty");
    var pts = (yields && yields.points) || [];
    pts = pts.filter(function (p) { return num(p.yield) != null; });
    if (!pts.length) {
      if (empty) empty.style.display = "block";
      setText(badge, "--");
      try { if (badge) badge.className = "mc-badge"; } catch (e) {}
      setText(spread, "10Y-13W spread: --");
      return;
    }
    if (empty) empty.style.display = "none";
    var inv = !!(yields && yields.inverted);
    var sp = curveSpread(pts);
    if (sp != null && !inv && sp < 0) inv = true;
    setText(badge, inv ? "INVERTED" : "NORMAL");
    try { if (badge) badge.className = "mc-badge " + (inv ? "inv" : "norm"); } catch (e) {}
    setText(spread, "10Y-13W spread: " + (sp == null ? "--" : ((sp >= 0 ? "+" : "") + sp.toFixed(2) + " pp")));
    if ((typeof Chart === "undefined") || !cv) return;
    try {
      if (window._mcCurve) window._mcCurve.destroy();
      window._mcCurve = new Chart(cv, {
        type: "line",
        data: {
          labels: pts.map(function (p) { return String(p.label); }),
          datasets: [{
            label: "Yield %",
            data: pts.map(function (p) { return num(p.yield); }),
            borderColor: inv ? "#ff9f0a" : "#34c759",
            backgroundColor: inv ? "rgba(255,159,10,.12)" : "rgba(52,199,89,.12)",
            fill: true, tension: 0.25, pointRadius: 3
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { labels: { color: "#8a8d93", font: { size: 10 } } } },
          scales: {
            x: { ticks: { color: "#8a8d93", font: { size: 10 } }, grid: { color: "#1e1f23" } },
            y: { ticks: { color: "#8a8d93", font: { size: 10 }, callback: function (v) { return v + "%"; } }, grid: { color: "#1e1f23" } }
          }
        }
      });
    } catch (e) { toast("Curve chart failed", "warn"); }
  }

  function renderGauges(gauges) {
    var box = $("mc-gauges");
    if (!box) return;
    var g = gauges || {};
    box.innerHTML = GAUGES.map(function (def) {
      var raw = pick(g, def.keys);
      if (raw != null && typeof raw !== "object" && g.changes) {
        for (var _gk in g.changes) { if (g[_gk] === raw) { raw = { value: raw, change_pct: g.changes[_gk] }; break; } }
      }
      var n = normGauge(raw);
      var ch = fmtChg(n.chg);
      var cls = ch.c;
      if (def.invert && n.chg != null) cls = n.chg > 0.005 ? "dn" : (n.chg < -0.005 ? "up" : "flat");
      return '<div class="mc-gauge"><div class="g-l">' + esc(def.label) + '</div>' +
        '<div class="g-v">' + esc(fmtV(n.value)) + '</div>' +
        '<div class="g-c ' + cls + '">' + esc(ch.t) + '</div></div>';
    }).join("");
  }

  function renderSnapshot(j) {
    renderRegime(j.regime);
    renderCurve(j.yields);
    renderGauges(j.gauges);
    renderFed(j.fed_stance);
    var gen = $("mc-generated");
    setText(gen, j.generated_at ? ("snapshot " + String(j.generated_at)) : "snapshot loaded");
  }

  /* Error state used only when there is no cached snapshot to keep. */
  function renderSnapshotError(timedOut) {
    var gen = $("mc-generated");
    setText(gen, timedOut ? "snapshot unavailable (request timed out)" : "snapshot unavailable");
    renderRegime(null);
    renderCurve(null);
    var box = $("mc-gauges");
    if (box) box.innerHTML = '<div class="mc-empty">Gauges unavailable.</div>';
    renderFed(null);
  }

  /* Stale-while-revalidate: keep old content, flag it in #mc-generated. */
  function markStale(timedOut) {
    var gen = $("mc-generated");
    if (!gen) return;
    var base = "stale - retrying";
    if (timedOut) base = "stale - retrying (request timed out)";
    try {
      if (lastGood && lastGood.generated_at) base += " (snapshot " + String(lastGood.generated_at) + ")";
    } catch (e) {}
    setText(gen, base);
  }

  function loadSnapshot() {
    return fetchJson(SNAP_URL, FETCH_TIMEOUT_MS).then(function (j) {
      lastGood = j || {};
      renderSnapshot(lastGood);
      return lastGood;
    }).catch(function (e) {
      var timedOut = !!(e && e.name === "AbortError");
      if (lastGood) {
        /* Keep old regions on screen; do not blank. */
        markStale(timedOut);
      } else {
        renderSnapshotError(timedOut);
      }
      return null;
    });
  }

  var FIELDS = [
    ["regime_read", "Regime read"],
    ["rate_sensitivity", "Rate sensitivity"],
    ["winners_losers_mechanism", "Winners / losers"],
    ["earnings_impact", "Earnings impact"],
    ["valuation_impact", "Valuation impact"],
    ["positioning", "Positioning"]
  ];

  function fmtImpact(v) {
    if (v == null || v === "") return "--";
    if (typeof v === "object") {
      if (v.level) return String(v.level) + (v.why ? " \u2014 " + String(v.why) : "");
      if (v.text) return String(v.text);
      try { return JSON.stringify(v); } catch (e) { return "--"; }
    }
    return String(v);
  }

  function lookup(ticker) {
    var t = String(ticker || "").trim().toUpperCase();
    var msg = $("mc-impact-msg"), box = $("mc-impact");
    if (!t) return Promise.resolve(null);
    if (!/^[A-Z0-9.\^-]{1,12}$/.test(t)) { toast("Invalid ticker", "error"); return Promise.resolve(null); }
    setText(msg, "Loading " + t + "...");
    return fetchJson(INTEL_URL(t), FETCH_TIMEOUT_MS).then(function (j) {
      setText($("mc-impact-head"), t + " in this regime");
      var rows = $("mc-impact-rows");
      if (rows) {
        rows.innerHTML = FIELDS.map(function (f) {
          return '<div class="mc-kv"><span>' + esc(f[1]) + '</span><div>' + esc(fmtImpact(j[f[0]])) + '</div></div>';
        }).join("");
      }
      var risks = (j && j.risk_flags) || [];
      var riskBox = $("mc-impact-risks");
      if (riskBox) {
        riskBox.innerHTML = risks.length
          ? risks.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("")
          : "<li>None flagged.</li>";
      }
      try { if (box) box.style.display = "block"; } catch (e) {}
      setText(msg, t + " loaded.");
      try {
        var u = new URL(location.href);
        u.searchParams.set("ticker", t);
        history.replaceState({}, "", u);
      } catch (e) {}
      return j;
    }).catch(function (e) {
      try { if (box) box.style.display = "none"; } catch (err) {}
      var timedOut = !!(e && e.name === "AbortError");
      setText(msg, timedOut ? ("Impact lookup timed out for " + t + ".") : ("Impact lookup failed for " + t + "."));
      toast("Macro intel fetch failed", "error");
      return null;
    });
  }

  /* Countdown: "refresh in M:SS", reset on each poll; silent if absent. */
  function paintCountdown() {
    var el = null;
    try { el = $("mc-countdown"); } catch (e) { el = null; }
    if (!el) return;
    var s = Math.max(0, remainSec);
    var m = Math.floor(s / 60);
    var rest = s % 60;
    setText(el, "refresh in " + m + ":" + (rest < 10 ? "0" + rest : String(rest)));
  }
  function resetCountdown() {
    remainSec = Math.round(POLL_MS / 1000);
    paintCountdown();
  }
  function startCountdown() {
    paintCountdown();
    if (TEST || countdownTimer) return;
    try {
      countdownTimer = setInterval(function () {
        remainSec = Math.max(0, remainSec - 1);
        paintCountdown();
      }, 1000);
    } catch (e) {}
  }
  function poll() {
    resetCountdown();
    return loadSnapshot();
  }

  function init() {
    var go = $("mc-go"), inp = $("mc-ticker"), copy = $("mc-copylink");
    var q = null;
    try { q = new URLSearchParams(location.search).get("ticker"); } catch (e) { q = null; }
    if (q && inp) {
      try { inp.value = String(q).toUpperCase().slice(0, 12); } catch (e) {}
    }
    /* Parallel boot: snapshot + (optional) impact race together via
       Promise.allSettled; each renders the moment its own data lands. */
    try {
      var jobs = [loadSnapshot()];
      if (q) jobs.push(lookup(q));
      if (typeof Promise !== "undefined" && Promise.allSettled) Promise.allSettled(jobs);
    } catch (e) {
      try { loadSnapshot(); } catch (err) {}
      try { if (q) lookup(q); } catch (err2) {}
    }
    if (!TEST) {
      try { setInterval(poll, POLL_MS); } catch (e) {}
      startCountdown();
    } else {
      paintCountdown();
    }
    resetCountdown();
    if (go) go.onclick = function () { if (inp) lookup(inp.value); };
    if (inp) inp.addEventListener("keydown", function (e) { if (e.key === "Enter") lookup(inp.value); });
    if (copy) copy.onclick = async function () {
      try { await navigator.clipboard.writeText(location.href); toast("Link copied", "success"); }
      catch (e) { toast(location.href, "info"); }
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
