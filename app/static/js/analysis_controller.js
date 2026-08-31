window.AnalysisController = {
  app: null,
  ticker: null,
  data: null,

  init: async function (app, ticker) {
    this.app = app;
    this.ticker = ticker;
    if (!ticker) return;
    const t = document.getElementById("an-ticker");
    if (t) t.textContent = ticker;
    const l = document.getElementById("an-ticker-logo");
    if (l) l.textContent = ticker.slice(0, 2);
    const c = document.getElementById("an-company");
    if (c) c.textContent = "Loading " + ticker + "...";

    this.data = await app.fetchTickerData(ticker);
    if (this.data) {
      this.renderOverview();
      this.renderFinancials();
      this.renderEstimates();
      this.renderNews();
      this.renderOwnership();
      this.renderModeling();
      this.renderRatios();
      this.renderFilings();
      this.renderIndustry();
      this.renderDividends();
      this.renderResearch();
      this.renderSegments();
      this.renderIR();
    }
    this.setupSubNav();
    this.setupDCFRecalc();
  },

  setupSubNav: function () {
    document.querySelectorAll(".analysis-subnav-item").forEach((el) => {
      el.addEventListener("click", function () {
        document
          .querySelectorAll(".analysis-subnav-item")
          .forEach((e) => e.classList.remove("active"));
        this.classList.add("active");
        document
          .querySelectorAll(".an-panel")
          .forEach((p) => (p.style.display = "none"));
        const t = document.getElementById(this.dataset.anPanel);
        if (t) t.style.display = "block";
      });
    });
  },

  fmtNum: function (v) {
    if (v == null || v === "N/A" || v === "--" || v === "") return "--";
    const n = parseFloat(String(v).replace(/,/g, ''));
    if (isNaN(n)) return v; // return original if not a number
    if (Math.abs(n) >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
    if (Math.abs(n) >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
    if (Math.abs(n) >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
    if (Math.abs(n) >= 1e3) return "$" + (n / 1e3).toFixed(2) + "K";
    return "$" + n.toFixed(2);
  },

  fmtPct: function (v) {
    if (v == null || v === "N/A") return "--";
    const n = parseFloat(String(v).replace(/,/g, ''));
    return isNaN(n) ? "--" : (n * 100).toFixed(2) + "%";
  },

  renderOverview: function () {
    const d = this.data,
      m = d.key_metrics || {},
      an = d.analysis || {};
    const s = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v || "--";
    };
    s("an-mcap", this.fmtNum(m.marketCap));
    s("an-ev", this.fmtNum(m.enterpriseValue));
    s("an-pe", m.trailingPE ? m.trailingPE.toFixed(2) : "--");
    s(
      "an-div",
      m.dividendYield ? (m.dividendYield * 100).toFixed(2) + "%" : "--",
    );
    s("an-gross", this.fmtPct(m.grossMargins));
    s("an-ebitda", this.fmtPct(m.ebitdaMargins));
    s("an-roic", this.fmtPct(m.returnOnEquity));
    s("an-beta", m.beta ? m.beta.toFixed(2) : "--");
    s(
      "an-description",
      d.company_description ||
        d.longBusinessSummary ||
        m.longBusinessSummary ||
        "No description available.",
    );

    const v = d.valuation_assessment || an.valuation_assessment || {};
    const verdict = an.verdict || v.verdict || "HOLD";
    const b = document.getElementById("an-verdict-badge");
    if (b) {
      b.textContent = verdict;
      b.className =
        "fiscal-badge " +
        (verdict === "BUY"
          ? "badge-success"
          : verdict === "SELL"
            ? "badge-danger"
            : "badge-warning");
    }
    s("an-confidence", an.verdict_confidence || v.verdict_confidence || "--");
    s(
      "an-ai-thesis",
      an.investment_thesis ||
        v.investment_thesis ||
        an.investment_thesis_summary ||
        an.executive_summary ||
        "AI analysis available after running the full pipeline.",
    );

    const p = document.getElementById("an-price");
    const ch = document.getElementById("an-change");
    if (p)
      p.textContent = m.currentPrice || m.current_price
        ? "$" + parseFloat(m.currentPrice || m.current_price).toFixed(2)
        : "--";
    if (ch)
      ch.textContent = m.previousClose
        ? "Prev Close: $" + parseFloat(m.previousClose).toFixed(2)
        : "";

    const cn = document.getElementById("an-company");
    if (cn)
      cn.textContent = d.company_name || m.shortName || m.longName || this.ticker;
  },

  renderFinancials: function () {
    const c = document.getElementById("an-financials-container");
    if (!c) return;
    
    const updateTable = () => {
        const stmt = document.querySelector("[data-statement].active")?.dataset?.statement || "income";
        const period = document.querySelector("[data-period].active")?.dataset?.period || "annual";
        window.AnalysisController.renderFinTable(stmt, period);
    };

    document.querySelectorAll("[data-statement]").forEach((b) =>
      b.addEventListener("click", function () {
          document.querySelectorAll("[data-statement]").forEach((x) => x.classList.remove("active"));
          this.classList.add("active");
          updateTable();
      })
    );
    
    document.querySelectorAll("[data-period]").forEach((b) =>
      b.addEventListener("click", function () {
          document.querySelectorAll("[data-period]").forEach((x) => x.classList.remove("active"));
          this.classList.add("active");
          updateTable();
      })
    );
    
    // Add common-size and YoY toggles if they don't exist
    const btnGroup = document.querySelector(".fiscal-toggle-group").parentNode;
    if (!document.getElementById("toggle-yoy")) {
        const extraToggles = document.createElement("div");
        extraToggles.className = "fiscal-toggle-group";
        extraToggles.innerHTML = `
          <button class="fiscal-toggle-btn" id="toggle-yoy">YoY %</button>
          <button class="fiscal-toggle-btn" id="toggle-commonsize">Common-Size %</button>
        `;
        btnGroup.appendChild(extraToggles);
        
        document.getElementById("toggle-yoy").addEventListener("click", function() {
            this.classList.toggle("active");
            document.getElementById("toggle-commonsize").classList.remove("active");
            updateTable();
        });
        document.getElementById("toggle-commonsize").addEventListener("click", function() {
            this.classList.toggle("active");
            document.getElementById("toggle-yoy").classList.remove("active");
            updateTable();
        });
    }

    this.renderFinTable("income", "annual");
  },

  renderFinTable: function (type, period) {
    const c = document.getElementById("an-financials-container");
    if (!c) return;
    if (!this.data) {
      c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">No data</div>';
      return;
    }
    
    let source = null;
    if (period === "quarterly") {
        if (type === 'income') source = this.data.q_financials;
        if (type === 'balance') source = this.data.q_balance_sheet;
        if (type === 'cashflow') source = this.data.q_cashflow;
    } else {
        if (type === 'income') source = this.data.financials;
        if (type === 'balance') source = this.data.balance_sheet;
        if (type === 'cashflow') source = this.data.cashflow;
    }
    
    if (!source || !source.columns || !source.rows || source.rows.length === 0) {
      c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">No ' + period + ' ' + type + ' data available</div>';
      return;
    }
    
    const showYoY = document.getElementById("toggle-yoy")?.classList.contains("active");
    const showCommon = document.getElementById("toggle-commonsize")?.classList.contains("active");
    
    let html = '<table class="fiscal-table" style="font-size:0.85rem; width: 100%;"><thead><tr>';
    for (let i = 0; i < source.columns.length; i++) {
        html += `<th style="white-space: nowrap; text-align: right;">${source.columns[i]}</th>`;
    }
    html += '</tr></thead><tbody>';
    
    for (let row of source.rows) {
        html += '<tr class="fiscal-row-hover">';
        let baseVal = null; // For common-size, usually Revenue or Total Assets
        if (showCommon && source.rows.length > 0) {
            baseVal = source.rows[0].slice(1).map(v => parseFloat(String(v).replace(/,/g, '')) || 0); // Assuming first row is Revenue/Assets
        }

        row.forEach((val, i) => {
            if (i === 0) {
                html += `<td style="font-weight: 500; color: var(--fiscal-text-primary); white-space: nowrap;">${val}</td>`;
            } else {
                let displayVal = this.fmtNum(val);
                let subHtml = "";
                
                let cur = parseFloat(String(val).replace(/,/g, ''));
                if (!isNaN(cur)) {
                    if (showYoY && i < row.length - 1) {
                        // Compare with previous column (which is chronologically older, assuming columns are sorted newest to oldest)
                        let prev = parseFloat(String(row[i+1]).replace(/,/g, ''));
                        if (!isNaN(prev) && prev !== 0) {
                            let yoy = ((cur - prev) / Math.abs(prev)) * 100;
                            let color = yoy > 0 ? "var(--fiscal-accent-success)" : (yoy < 0 ? "var(--fiscal-accent-danger)" : "var(--fiscal-text-tertiary)");
                            subHtml = `<span style="font-size:0.7rem; color:${color}; margin-left: 6px;">${yoy > 0 ? '+' : ''}${yoy.toFixed(1)}%</span>`;
                        }
                    } else if (showCommon && baseVal && baseVal[i-1] !== 0 && !isNaN(baseVal[i-1])) {
                        let pct = (cur / baseVal[i-1]) * 100;
                        subHtml = `<span style="font-size:0.7rem; color:var(--fiscal-text-tertiary); margin-left: 6px;">${pct.toFixed(1)}%</span>`;
                    }
                }
                
                html += `<td style="font-family: var(--font-mono); white-space: nowrap; text-align: right;">${displayVal}${subHtml}</td>`;
            }
        });
        html += '</tr>';
    }
    html += '</tbody></table>';
    c.innerHTML = html;
  },

  renderRatios: function () {
    const c = document.getElementById("an-ratios-container"),
      m = this.data?.key_metrics || {};
    if (!c) return;
    const items = [
      ["Current Ratio", m.currentRatio, "x"],
      ["Quick Ratio", m.quickRatio, "x"],
      ["Debt to Equity", m.debtToEquity, "x"],
      ["ROE", m.returnOnEquity, "%"],
      ["ROA", m.returnOnAssets, "%"],
      ["Gross Margin", m.grossMargins, "%"],
      ["Operating Margin", m.operatingMargins, "%"],
      ["Profit Margin", m.profitMargins, "%"],
      ["Price to Book", m.priceToBook, "x"],
      ["Price to Sales", m.priceToSalesTrailing12Months || m.priceToSales, "x"],
      ["EV/Revenue", m.enterpriseToRevenue, "x"],
      ["EV/EBITDA", m.enterpriseToEbitda, "x"],
    ];
    c.innerHTML = items
      .map(
        ([n, v, u]) =>
          '<div class="metric-tile"><div class="metric-tile-label">' +
          n +
          '</div><div class="metric-tile-val">' +
          (v != null
            ? u === "%"
              ? (v * 100).toFixed(2) + "%"
              : v.toFixed(2) + " " + u
            : "--") +
          "</div></div>",
      )
      .join("");
  },

  renderEstimates: function () {
    const c = document.getElementById("an-estimates-container");
    if (!c) return;
    const an = this.data?.analysis || {};
    const dcf = this.data?.dcf_data || {};
    const m = this.data?.key_metrics || {};
    
    c.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">' +
      '<div class="metric-tile"><div class="metric-tile-label">DCF Fair Value</div><div class="metric-tile-val">' +
      (dcf.implied_price
        ? "$" + parseFloat(dcf.implied_price).toFixed(2)
        : "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">Analyst Target (Mean)</div><div class="metric-tile-val">' +
      (m.targetMeanPrice ? "$" + parseFloat(m.targetMeanPrice).toFixed(2) : "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">Analyst Rating</div><div class="metric-tile-val" style="text-transform: capitalize;">' +
      (m.recommendationKey || "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">AI Verdict</div><div class="metric-tile-val">' +
      (an.verdict || "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">AI Confidence</div><div class="metric-tile-val">' +
      (an.verdict_confidence || "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">12M Target</div><div class="metric-tile-val">' +
      (an.price_target_12m || "--") +
      "</div></div></div>";
  },

  renderNews: function () {
    const c = document.getElementById("an-news-container");
    if (!c || !this.ticker) return;
    fetch("/api/news/stock/" + this.ticker)
      .then((r) => r.json())
      .then((d) => {
        if (d.news && d.news.length) {
          c.innerHTML = d.news
            .slice(0, 8)
            .map(
              (n) =>
                '<div class="glass-panel" style="padding:14px 18px;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.transform=\\'translateY(-2px)\\'" onmouseout="this.style.transform=\\'none\\'" onclick="window.open(\'' +
                (n.link || "#") +
                "','_blank')\"><div style=\"font-weight:600;font-size:0.9rem;margin-bottom:6px;color:var(--fiscal-text-primary);\">" +
                n.title +
                '</div><div style="font-size:0.78rem;color:var(--fiscal-text-tertiary);">' +
                (n.publisher || "News") +
                " &middot; " +
                (n.providerPublishTime ? new Date(n.providerPublishTime * 1000).toLocaleDateString() : (n.pubDate ? new Date(n.pubDate).toLocaleDateString() : "")) +
                "</div></div>",
            )
            .join("");
        } else {
          c.innerHTML =
            '<div style="color:var(--fiscal-text-tertiary);text-align:center;padding:40px;">No recent news for ' +
            this.ticker +
            "</div>";
        }
      })
      .catch(() => {
        c.innerHTML =
          '<div style="color:var(--fiscal-text-tertiary);text-align:center;padding:40px;">News unavailable</div>';
      });
  },

  renderOwnership: function () {
    const c = document.getElementById("an-ownership-container"),
      m = this.data?.key_metrics || {};
    if (!c) return;
    c.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;">' +
      '<div class="metric-tile"><div class="metric-tile-label">Insider Holdings</div><div class="metric-tile-val">' +
      (m.heldPercentInsiders
        ? (m.heldPercentInsiders * 100).toFixed(2) + "%"
        : "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">Institutional Holdings</div><div class="metric-tile-val">' +
      (m.heldPercentInstitutions
        ? (m.heldPercentInstitutions * 100).toFixed(2) + "%"
        : "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">Short % Float</div><div class="metric-tile-val">' +
      (m.shortPercentOfFloat
        ? (m.shortPercentOfFloat * 100).toFixed(2) + "%"
        : "--") +
      "</div></div>" +
      '<div class="metric-tile"><div class="metric-tile-label">Shares Outstanding</div><div class="metric-tile-val">' +
      (m.sharesOutstanding
        ? (m.sharesOutstanding / 1e9).toFixed(3) + "B"
        : "--") +
      "</div></div></div>";
  },

  renderModeling: function () {
    const dcf = this.data?.dcf_data || {};
    const val = dcf.implied_price || null;
    const el = document.getElementById("dcf-result");
    if (el) el.textContent = val ? "$" + parseFloat(val).toFixed(2) : "$--";
    const nt = document.getElementById("dcf-note");
    if (nt)
      nt.textContent = val
        ? "Based on current assumptions"
        : "Enter assumptions and recalculate";
  },

  setupDCFRecalc: function () {
    const btn = document.getElementById("dcf-recalc-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      if (!this.ticker) return;
      const wacc = document.getElementById("dcf-wacc")?.value || 9;
      const g1 = document.getElementById("dcf-g1")?.value || 15;
      const g2 = document.getElementById("dcf-g2")?.value || 10;
      const tg = document.getElementById("dcf-tg")?.value || 2.5;
      btn.textContent = "...";
      btn.disabled = true;
      try {
        const r = await fetch("/api/stock/" + this.ticker + "/recalculate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            wacc: parseFloat(wacc),
            growth_1_5: parseFloat(g1),
            growth_6_10: parseFloat(g2),
            terminal_growth: parseFloat(tg),
          }),
        });
        const d = await r.json();
        if (d.dcf_data) {
          const ip = d.dcf_data.implied_price;
          const el = document.getElementById("dcf-result");
          if (el) el.textContent = ip ? "$" + parseFloat(ip).toFixed(2) : "$--";
        }
      } catch (e) {
        console.error(e);
      }
      btn.textContent = "Recalculate DCF";
      btn.disabled = false;
    });
  },

  renderFilings: function() {
    const c = document.getElementById("an-filings-container");
    if (!c) return;
    const sec = this.data?.sec_data?.recent_filings;
    if (!sec || !sec.length) {
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">No SEC filings available</div>';
        return;
    }
    
    let html = '<div style="display: flex; flex-direction: column; gap: 8px;">';
    sec.forEach(f => {
        html += `
        <div class="glass-panel" style="padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;">
           <div>
              <span class="fiscal-badge" style="background: var(--fiscal-bg-elevated); margin-right: 8px;">${f.form}</span>
              <span style="font-size: 0.9rem; font-weight: 500;">Filing Date: ${f.filing_date}</span>
           </div>
           <a href="https://www.sec.gov/Archives/edgar/data/${this.data.sec_data.cik}/${f.accession_number.replace(/-/g, '')}/${f.primary_document}" target="_blank" class="fiscal-btn-secondary" style="font-size: 0.8rem; padding: 4px 8px; text-decoration: none;">View SEC</a>
        </div>`;
    });
    html += '</div>';
    c.innerHTML = html;
  },

  renderIndustry: function() {
    const c = document.getElementById("an-industry-container");
    if (!c) return;
    const peers = this.data?.peers_data;
    if (!peers || !peers.length) {
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">No industry data available</div>';
        return;
    }
    
    let html = '<div style="overflow-x:auto;"><table class="fiscal-table" style="width:100%; font-size:0.85rem;"><thead><tr><th style="text-align:left;">Ticker</th><th style="text-align:left;">Name</th><th>P/E</th><th>P/S</th><th>Gross Margin</th><th>Rev Growth</th></tr></thead><tbody>';
    peers.forEach(p => {
        html += `
        <tr class="fiscal-row-hover">
          <td style="font-weight: 600; color: var(--fiscal-text-primary); cursor: pointer;" onclick="window.App.loadAnalysis('${p.ticker}')">${p.ticker}</td>
          <td>${p.name || '--'}</td>
          <td style="font-family: var(--font-mono); text-align:center;">${p.pe ? p.pe.toFixed(2) : '--'}</td>
          <td style="font-family: var(--font-mono); text-align:center;">${p.ps ? p.ps.toFixed(2) : '--'}</td>
          <td style="font-family: var(--font-mono); text-align:center;">${p.margins ? (p.margins * 100).toFixed(2) + '%' : '--'}</td>
          <td style="font-family: var(--font-mono); text-align:center; color: ${p.rev_growth >= 0 ? 'var(--fiscal-accent-success)' : 'var(--fiscal-accent-danger)'};">${p.rev_growth ? (p.rev_growth * 100).toFixed(2) + '%' : '--'}</td>
        </tr>`;
    });
    html += '</tbody></table></div>';
    c.innerHTML = html;
  },

  renderDividends: function() {
    const c = document.getElementById("an-dividends-container");
    if (!c) return;
    const m = this.data?.key_metrics || {};
    
    c.innerHTML = `
    <div style="display: flex; gap: 16px; margin-bottom: 24px;">
      <div class="glass-panel" style="padding: 16px; flex: 1;">
          <div style="color: var(--fiscal-text-secondary); font-size: 0.85rem; margin-bottom: 4px;">Dividend Yield</div>
          <div style="font-size: 1.5rem; font-family: var(--font-mono); font-weight: 600;">${m.dividendYield ? (m.dividendYield * 100).toFixed(2) + '%' : '--'}</div>
      </div>
      <div class="glass-panel" style="padding: 16px; flex: 1;">
          <div style="color: var(--fiscal-text-secondary); font-size: 0.85rem; margin-bottom: 4px;">Annual Dividend</div>
          <div style="font-size: 1.5rem; font-family: var(--font-mono); font-weight: 600;">${m.dividendRate ? '$' + m.dividendRate.toFixed(2) : '--'}</div>
      </div>
      <div class="glass-panel" style="padding: 16px; flex: 1;">
          <div style="color: var(--fiscal-text-secondary); font-size: 0.85rem; margin-bottom: 4px;">Payout Ratio</div>
          <div style="font-size: 1.5rem; font-family: var(--font-mono); font-weight: 600;">${m.payoutRatio ? (m.payoutRatio * 100).toFixed(2) + '%' : '--'}</div>
      </div>
    </div>
    <div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">Detailed dividend history coming soon</div>
    `;
  },

  renderResearch: function() {
    const c = document.getElementById("an-research-container");
    if (!c) return;
    const an = this.data?.analysis;
    if (!an) {
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">No research reports available</div>';
        return;
    }
    
    c.innerHTML = `
    <div style="text-align: left;">
        <h3 style="color: var(--fiscal-accent-primary); margin-bottom: 12px; font-size: 1.1rem;">Executive Summary</h3>
        <p style="color: var(--fiscal-text-primary); line-height: 1.6; margin-bottom: 24px; font-size: 0.95rem;">${an.executive_summary || 'N/A'}</p>
        
        <h3 style="color: var(--fiscal-accent-primary); margin-bottom: 12px; font-size: 1.1rem;">Investment Thesis</h3>
        <p style="color: var(--fiscal-text-primary); line-height: 1.6; margin-bottom: 24px; font-size: 0.95rem;">${an.investment_thesis || 'N/A'}</p>
        
        <h3 style="color: var(--fiscal-accent-primary); margin-bottom: 12px; font-size: 1.1rem;">Key Catalysts</h3>
        <p style="color: var(--fiscal-text-primary); line-height: 1.6; margin-bottom: 24px; font-size: 0.95rem;">${an.catalysts || 'N/A'}</p>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 24px;">
          <div class="glass-panel" style="padding: 20px; border-left: 4px solid var(--fiscal-accent-success);">
              <h4 style="margin-bottom: 12px; font-size: 1rem;">Bull Case</h4>
              <p style="font-size: 0.9rem; color: var(--fiscal-text-secondary); line-height: 1.5;">${an.bull_case_narrative || 'N/A'}</p>
          </div>
          <div class="glass-panel" style="padding: 20px; border-left: 4px solid var(--fiscal-accent-danger);">
              <h4 style="margin-bottom: 12px; font-size: 1rem;">Bear Case</h4>
              <p style="font-size: 0.9rem; color: var(--fiscal-text-secondary); line-height: 1.5;">${an.bear_case_narrative || 'N/A'}</p>
          </div>
        </div>
    </div>
    `;
  },

  renderSegments: function() {
    const c = document.getElementById("an-segments-container");
    if (!c) return;
    const desc = this.data?.key_metrics?.longBusinessSummary || this.data?.longBusinessSummary || "";
    
    const sentences = desc.split(/[.!?]\s+/);
    const segmentSentences = sentences.filter(s => s.toLowerCase().includes("segment") || s.toLowerCase().includes("division"));
    
    if (segmentSentences.length > 0) {
        let html = '<div style="display:grid; grid-template-columns: 1fr; gap:16px; text-align: left;">';
        segmentSentences.forEach((sentence, idx) => {
            let title = `Segment ${idx + 1}`;
            const match = sentence.match(/([A-Z][A-Za-z0-9\s,&]+segment)/);
            if (match) {
                title = match[1];
            }
            html += `
              <div class="glass-panel" style="padding: 16px; border-left: 4px solid var(--fiscal-accent-primary);">
                  <h4 style="margin-bottom: 8px; color: var(--fiscal-text-primary); font-size:1rem;">${title}</h4>
                  <p style="font-size: 0.9rem; color: var(--fiscal-text-secondary); line-height: 1.5; margin: 0;">${sentence}.</p>
              </div>`;
        });
        html += '</div>';
        c.innerHTML = html;
    } else {
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--fiscal-text-tertiary);">Segment breakdowns are not explicitly detailed in the business summary.</div>';
    }
  },

  renderIR: function() {
    const c = document.getElementById("an-ir-container");
    if (!c || !this.ticker) return;
    
    let html = '<div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px; text-align: left;">';
    
    // Column 1: News & Calls
    html += '<div><h3 style="font-size: 1rem; color: var(--fiscal-text-secondary); margin-bottom: 12px;">Earnings Releases & Calls</h3><div id="ir-news-list" style="display:flex; flex-direction:column; gap:10px;">Loading news...</div></div>';
    
    // Column 2: Official Filings
    const filings = this.data?.sec_data?.recent_filings || [];
    let filingsHtml = '<div><h3 style="font-size: 1rem; color: var(--fiscal-text-secondary); margin-bottom: 12px;">Official Disclosures</h3><div style="display:flex; flex-direction:column; gap:10px;">';
    
    if (filings.length === 0) {
        filingsHtml += '<div style="color:var(--fiscal-text-tertiary); font-size:0.85rem;">No disclosures available.</div>';
    } else {
        const filtered = filings.filter(f => ['10-K', '10-Q', '8-K'].includes(f.form)).slice(0, 4);
        if (filtered.length === 0) {
            filingsHtml += '<div style="color:var(--fiscal-text-tertiary); font-size:0.85rem;">No recent 10-K/10-Q reports.</div>';
        } else {
            filtered.forEach(f => {
                const cik = this.data?.sec_data?.cik;
                const acc = f.accession_number ? f.accession_number.replace(/-/g, '') : '';
                const doc = f.primary_document;
                const link = cik && acc && doc ? `https://www.sec.gov/Archives/edgar/data/${cik}/${acc}/${doc}` : '#';
                
                filingsHtml += `
                  <div class="glass-panel" style="padding: 12px;">
                      <div style="display:flex; justify-content:space-between; align-items:center;">
                          <span class="fiscal-badge" style="background:var(--fiscal-bg-elevated);">${f.form}</span>
                          <span style="font-size:0.75rem; color:var(--fiscal-text-tertiary);">${f.filing_date}</span>
                      </div>
                      <div style="margin-top:8px;"><a href="${link}" target="_blank" style="color:var(--fiscal-accent-primary); text-decoration:none; font-size:0.85rem; font-weight:500;">SEC EDGAR Report &rarr;</a></div>
                  </div>`;
            });
        }
    }
    filingsHtml += '</div></div>';
    html += filingsHtml + '</div>';
    c.innerHTML = html;
    
    fetch("/api/news/stock/" + this.ticker)
      .then(r => r.json())
      .then(d => {
          const listDiv = document.getElementById("ir-news-list");
          if (!listDiv) return;
          
          if (d.news && d.news.length) {
              const keywords = ["earnings", "quarter", "results", "call", "transcript", "eps", "revenue", "fiscal"];
              const irNews = d.news.filter(n => 
                  keywords.some(k => (n.title || "").toLowerCase().includes(k))
              ).slice(0, 6);
              
              if (irNews.length === 0) {
                  listDiv.innerHTML = '<div style="color:var(--fiscal-text-tertiary); padding: 20px 0; font-size:0.85rem;">No recent earnings news found. Showing all news:</div>' + 
                      d.news.slice(0, 3).map(n => `
                        <div class="glass-panel" style="padding:12px; cursor:pointer;" onclick="window.open('${n.link}','_blank')">
                            <div style="font-weight:500; font-size:0.85rem; color:var(--fiscal-text-primary);">${n.title}</div>
                            <div style="font-size:0.75rem; color:var(--fiscal-text-tertiary); margin-top:4px;">${n.publisher}</div>
                        </div>
                      `).join("");
              } else {
                  listDiv.innerHTML = irNews.map(n => `
                    <div class="glass-panel" style="padding:12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center;" onclick="window.open('${n.link}','_blank')">
                        <div style="text-align:left;">
                            <div style="font-weight:500; font-size:0.85rem; color:var(--fiscal-text-primary);">${n.title}</div>
                            <div style="font-size:0.75rem; color:var(--fiscal-text-tertiary); margin-top:4px;">${n.publisher}</div>
                        </div>
                        <span style="font-size:1.1rem; color:var(--fiscal-accent-primary); margin-left:12px;">🎙️</span>
                    </div>
                  `).join("");
              }
          } else {
              listDiv.innerHTML = '<div style="color:var(--fiscal-text-tertiary); font-size:0.85rem;">No earnings news available.</div>';
          }
      })
      .catch(() => {
          const listDiv = document.getElementById("ir-news-list");
          if (listDiv) listDiv.innerHTML = '<div style="color:var(--fiscal-text-tertiary); font-size:0.85rem;">IR news feeds temporarily unavailable.</div>';
      });
  }
};
