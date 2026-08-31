window.ScreenerController = {
  data: [],
  
  init: function(app) {
    this.app = app;
    this.fetchData();
    this.bindEvents();
  },

  fetchData: function() {
    fetch("/api/stocks")
      .then(r => r.json())
      .then(data => {
        this.data = data.stocks || [];
        this.updateCount(this.data.length);
        this.populateDropdowns();
      })
      .catch(err => console.error("Screener error:", err));
  },

  bindEvents: function() {
    const aiInput = document.getElementById("screener-ai-query");
    if (aiInput) {
      aiInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this.runAIScreen();
      });
    }
    
    // Bind global export function
    window.exportScreenerCSV = this.exportCSV.bind(this);
    window.runAIScreen = this.runAIScreen.bind(this);
    window.runFilterScreen = this.runTraditionalFilter.bind(this);
  },

  populateDropdowns: function() {
    const sectors = new Set();
    this.data.forEach(s => {
      if (s.sector && s.sector !== "N/A") sectors.add(s.sector);
    });
    
    const industrySelect = document.getElementById("screener-industry");
    if (industrySelect) {
      industrySelect.innerHTML = '<option value="">All Industries</option>';
      Array.from(sectors).sort().forEach(sector => {
        const opt = document.createElement("option");
        opt.value = sector;
        opt.textContent = sector;
        industrySelect.appendChild(opt);
      });
    }
  },

  runTraditionalFilter: async function() {
    const industry = document.getElementById("screener-industry")?.value || "";
    const verdict = document.getElementById("screener-verdict")?.value || "";
    const maxPe = document.getElementById("screener-country")?.value || "";
    const minUpside = document.getElementById("screener-exchange")?.value || "";
    const minRoe = document.getElementById("screener-roe")?.value || "";
    const maxDebt = document.getElementById("screener-debt")?.value || "";
    const minPiotroski = document.getElementById("screener-piotroski")?.value || "";
    const params = new URLSearchParams();
    if (industry) params.set("sector", industry);
    if (verdict) params.set("verdict", verdict);
    if (maxPe) params.set("max_pe", maxPe);
    if (minUpside) params.set("min_upside", minUpside);
    if (minRoe) params.set("min_roe", minRoe);
    if (maxDebt) params.set("max_debt_to_equity", maxDebt);
    if (minPiotroski) params.set("min_piotroski", minPiotroski);

    try {
      const res = await fetch(`/api/screener/filter?${params.toString()}`);
      const data = await res.json();
      this.renderResults(data.stocks || []);
    } catch (err) {
      console.error("Traditional filter fetch failed:", err);
      // Fallback
      let filtered = this.data;
      if (industry) {
        filtered = filtered.filter(s => (s.sector || "").toLowerCase() === industry.toLowerCase());
      }
      if (verdict) {
        filtered = filtered.filter(s => (s.verdict || "").toUpperCase().includes(verdict.toUpperCase()));
      }
      if (maxPe) filtered = filtered.filter(s => parseFloat(s.pe_ratio) <= parseFloat(maxPe));
      if (minUpside) filtered = filtered.filter(s => parseFloat(s.upside || 0) >= parseFloat(minUpside));
      if (minRoe) filtered = filtered.filter(s => parseFloat(s.returnOnEquity || 0) >= parseFloat(minRoe));
      if (maxDebt) filtered = filtered.filter(s => parseFloat(s.debtToEquity || Infinity) <= parseFloat(maxDebt));
      if (minPiotroski) filtered = filtered.filter(s => parseFloat(s.piotroski_f || 0) >= parseFloat(minPiotroski));
      this.renderResults(filtered);
    }
  },

  runAIScreen: async function() {
    const q = document.getElementById("screener-ai-query")?.value.trim();
    if (!q) return;

    const tbody = document.getElementById("screener-results-body");
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 40px 20px; color: var(--fiscal-text-tertiary);">AI is screening catalog...</td></tr>';
    }

    try {
      const res = await fetch("/api/screener/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q })
      });
      const data = await res.json();
      this.renderResults(data.stocks || []);
      
      if (data.criteria && Object.keys(data.criteria).length > 0) {
        let msg = "AI applied filters: " + Object.entries(data.criteria).map(([k,v]) => `${k}=${v}`).join(", ");
        this.app.showToast(msg, "success");
      }
    } catch (err) {
      console.error("AI screen fetch failed:", err);
      // Client-side fallback
      const q_lower = q.toLowerCase();
      let filtered = this.data;
      
      if (q_lower.includes("buy") || q_lower.includes("strong buy")) {
        filtered = filtered.filter(s => (s.verdict || "").toUpperCase() === "BUY");
      }
      if (q_lower.includes("sell")) {
        filtered = filtered.filter(s => (s.verdict || "").toUpperCase() === "SELL");
      }
      if (q_lower.includes("hold")) {
        filtered = filtered.filter(s => (s.verdict || "").toUpperCase() === "HOLD");
      }
      if (q_lower.includes("oversold") || q_lower.includes("cheap") || q_lower.includes("undervalued")) {
        filtered = filtered.filter(s => parseFloat(s.upside || 0) > 0.20);
      }
      if (q_lower.includes("overvalued") || q_lower.includes("expensive")) {
        filtered = filtered.filter(s => parseFloat(s.upside || 0) < -0.10);
      }
      if (q_lower.includes("dividend")) {
        filtered = filtered.filter(s => ["Utilities", "Real Estate", "Financials"].includes(s.sector));
      }
      if (q_lower.includes("tech") || q_lower.includes("software")) {
        filtered = filtered.filter(s => ["Technology", "Communication Services"].includes(s.sector));
      }
      this.renderResults(filtered);
    }
  },

  renderResults: function(results) {
    const tbody = document.getElementById("screener-results-body");
    if (!tbody) return;

    if (!results || !results.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 40px 20px; color: var(--fiscal-text-tertiary);">No matching companies found</td></tr>';
      this.updateCount(0);
      return;
    }

    let html = "";
    results.forEach(s => {
      const ticker = this.app.escapeHtml(s.ticker || "");
      const company = this.app.escapeHtml(s.company_name || "--");
      const sector = this.app.escapeHtml(s.sector || "--");
      const verdict = this.app.escapeHtml(s.verdict || "--");
      const price = s.current_price ? "$" + parseFloat(s.current_price).toFixed(2) : "--";
      const fv = s.fair_value_mid ? "$" + parseFloat(s.fair_value_mid).toFixed(2) : "--";
      const up = parseFloat(s.upside || 0);
      const upStr = up ? (up >= 0 ? "+" : "") + (up * 100).toFixed(1) + "%" : "--";
      const upCls = up >= 0.1 ? "pos" : (up <= -0.1 ? "neg" : "");
      const vCls = (s.verdict || "").toUpperCase() === "BUY" ? "badge-success" : ((s.verdict || "").toUpperCase() === "SELL" ? "badge-danger" : "");
      
      html += `<tr class="screener-result-row" onclick="window.App.loadAnalysis('${ticker}')">
            <td style="font-weight: 600; color: var(--fiscal-text-primary);">${ticker}</td>
            <td>${company}</td>
            <td>${sector}</td>
            <td style="font-family: var(--font-mono);">${price}</td>
            <td style="font-family: var(--font-mono);">${fv}</td>
            <td style="font-family: var(--font-mono);" class="fiscal-ticker-pct ${upCls}">${upStr}</td>
            <td style="font-family: var(--font-mono);">${typeof s.pe_ratio === "number" ? s.pe_ratio.toFixed(2) : s.pe_ratio || "--"}</td>
            <td><span class="fiscal-badge ${vCls}">${verdict}</span></td>
        </tr>`;
    });
    
    tbody.innerHTML = html;
    this.updateCount(results.length);
  },

  updateCount: function(count) {
    const el = document.getElementById("screener-count");
    if (el) el.textContent = `${count} results`;
  },

  exportCSV: function() {
    const rows = [["Ticker", "Company", "Sector", "Price", "Fair Value", "Upside", "P/E", "Verdict"]];
    this.data.forEach(s => {
      rows.push([
        s.ticker, s.company_name, s.sector, s.current_price, s.fair_value_mid, s.upside, s.pe_ratio, s.verdict
      ]);
    });
    const csv = rows.map(r => r.map(v => '"' + String(v || "") + '"').join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "screener-export.csv";
    a.click();
  }
};
