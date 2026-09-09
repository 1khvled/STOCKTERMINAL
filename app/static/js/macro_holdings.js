/* Macro holdings coverage: "Your coverage under this regime". Dependency-free. */
(function () {
  "use strict";

  var STOCKS_URL = "/api/stocks";
  var SNAP_URL = "/api/macro/snapshot";
  var TIMEOUT_MS = 10000;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fetchJson(url, ms) {
    var ctrl = null;
    var timer = null;
    try {
      if (typeof AbortController !== "undefined") {
        ctrl = new AbortController();
        timer = setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, ms);
      }
    } catch (e) { ctrl = null; }
    var opts = {};
    if (ctrl) opts.signal = ctrl.signal;
    return fetch(url, opts).then(function (r) {
      if (timer) clearTimeout(timer);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).catch(function (e) {
      if (timer) clearTimeout(timer);
      throw e;
    });
  }

  function sensitivityFor(sector) {
    var s = String(sector || "N/A").toLowerCase();
    if (s.indexOf("utilit") >= 0) return "HIGH";
    if (s.indexOf("real estate") >= 0 || s === "realestate" || s.indexOf("reit") >= 0) return "HIGH";
    if (s.indexOf("staple") >= 0 || s.indexOf("defensive") >= 0 || s.indexOf("consumer defensive") >= 0) return "HIGH";
    if (s.indexOf("tech") >= 0) return "MED-HIGH";
    if (s.indexOf("energy") >= 0 || s.indexOf("financial") >= 0) return "LOW-beneficiary";
    return "MED";
  }

  function lineFor(regime, sens, names, count) {
    var shown = names.slice(0, 4).join(", ");
    var extra = count > 4 ? " (+" + (count - 4) + " more)" : "";
    if (regime === "STAGFLATION_WATCH") {
      if (sens === "HIGH") return "HIGH-sensitivity names at risk (" + shown + extra + "): rate pressure plus input costs squeeze margins.";
      if (sens === "MED-HIGH") return "MED-HIGH duration exposure (" + shown + extra + "): growth multiples compress while costs run hot.";
      if (sens === "LOW-beneficiary") return "LOW-sensitivity, possible beneficiary (" + shown + extra + "): energy pricing and net interest margins can offset.";
      return "MED sensitivity (" + shown + extra + "): selective pass-through decides winners.";
    }
    if (regime === "RISK_OFF") {
      if (sens === "HIGH") return "HIGH-sensitivity defensives (" + shown + extra + "): relative shelter but rate overhang caps upside.";
      if (sens === "MED-HIGH") return "MED-HIGH growth at risk (" + shown + extra + "): de-rate first in flight to safety.";
      if (sens === "LOW-beneficiary") return "LOW-sensitivity cyclicals (" + shown + extra + "): earnings hold only if credit stays open.";
      return "MED sensitivity (" + shown + extra + "): balance quality against drawdown.";
    }
    if (regime === "RISK_ON") {
      if (sens === "HIGH") return "HIGH-sensitivity laggards (" + shown + extra + "): stable yield but limited torque.";
      if (sens === "MED-HIGH") return "MED-HIGH growth leverage (" + shown + extra + "): multiple expansion favors this bucket.";
      if (sens === "LOW-beneficiary") return "LOW-sensitivity cyclicals (" + shown + extra + "): earnings and credit beta lead.";
      return "MED sensitivity (" + shown + extra + "): participates with the tape.";
    }
    if (regime === "TIGHTENING") {
      if (sens === "HIGH") return "HIGH-sensitivity names under pressure (" + shown + extra + "): higher-for-longer discounts yield value.";
      if (sens === "MED-HIGH") return "MED-HIGH duration drag (" + shown + extra + "): long-duration cash flows re-price lower.";
      if (sens === "LOW-beneficiary") return "LOW-sensitivity, possible beneficiary (" + shown + extra + "): banks and energy pass higher rates through.";
      return "MED sensitivity (" + shown + extra + "): stock-picking over sector call.";
    }
    if (sens === "HIGH") return "HIGH rate sensitivity (" + shown + extra + "): watch real yields for direction.";
    if (sens === "MED-HIGH") return "MED-HIGH rate sensitivity (" + shown + extra + "): growth duration sets the move.";
    if (sens === "LOW-beneficiary") return "LOW sensitivity, possible beneficiary (" + shown + extra + "): tends to hold up as rates rise.";
    return "MED sensitivity (" + shown + extra + "): mixed rate read-through.";
  }

  function render() {
    var box = document.getElementById("mc-holdings");
    if (!box) return;
    box.innerHTML = "<div>Loading coverage...</div>";
    var p1 = fetchJson(STOCKS_URL, TIMEOUT_MS);
    var p2 = fetchJson(SNAP_URL, TIMEOUT_MS);
    Promise.all([p1, p2]).then(function (res) {
      var sj = res[0] || {};
      var mj = res[1] || {};
      var rows = sj.stocks;
      if (!Array.isArray(rows) && Array.isArray(sj)) rows = sj;
      if (!Array.isArray(rows)) rows = [];
      var regime = ((mj.regime || {}).label || "NEUTRAL").toUpperCase();
      var groups = {};
      rows.forEach(function (r) {
        var sector = (r && r.sector) || "N/A";
        var key = String(sector);
        if (!groups[key]) groups[key] = [];
        groups[key].push(String((r && (r.ticker || r.symbol)) || "?").toUpperCase());
      });
      var keys = Object.keys(groups).sort();
      var html = "<div><b>Your coverage under this regime</b> "
        + "<span>Regime: " + esc(regime) + " | " + esc(String(rows.length)) + " holdings</span></div>";
      if (!keys.length) {
        html += "<div>No holdings found.</div>";
      } else {
        html += "<ul>" + keys.map(function (k) {
          var names = groups[k].slice().sort();
          var sens = sensitivityFor(k);
          return "<li><b>" + esc(k) + "</b> "
            + "<span>[" + esc(sens) + "]</span> "
            + "<span>" + esc(String(names.length)) + " name(s): " + esc(names.slice(0, 4).join(", ")) + "</span><br>"
            + "<span>" + esc(lineFor(regime, sens, names, names.length)) + "</span></li>";
        }).join("") + "</ul>";
      }
      box.innerHTML = html;
    }).catch(function () {
      try { box.innerHTML = "<div>Coverage unavailable.</div>"; } catch (e) {}
    });
  }

  window.MacroHoldings = { render: render };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
