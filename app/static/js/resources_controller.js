window.ResourcesController = {
  init: function(app) {
    this.app = app;
    this.bindEvents();
    this.injectModal();
  },

  injectModal: function() {
    if (!document.getElementById("resources-modal")) {
        const modal = document.createElement("div");
        modal.id = "resources-modal";
        modal.style = "display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:9999; align-items:center; justify-content:center;";
        modal.innerHTML = `
            <div class="glass-panel" style="width: 80%; max-width: 800px; max-height: 80vh; overflow-y: auto; padding: 24px; position: relative;">
                <button id="close-resources-modal" style="position: absolute; right: 24px; top: 24px; background: transparent; border: none; color: var(--fiscal-text-secondary); cursor: pointer; font-size: 1.5rem;">&times;</button>
                <h2 id="resources-modal-title" style="margin-bottom: 20px; font-size: 1.5rem;">Data</h2>
                <div id="resources-modal-content"></div>
            </div>
        `;
        document.body.appendChild(modal);
        document.getElementById("close-resources-modal").onclick = () => modal.style.display = "none";
        modal.onclick = (e) => { if(e.target === modal) modal.style.display = "none"; };
    }
  },

  openModal: function(title, html) {
      document.getElementById("resources-modal-title").textContent = title;
      document.getElementById("resources-modal-content").innerHTML = html;
      document.getElementById("resources-modal").style.display = "flex";
  },

  bindEvents: function() {
    const panels = document.querySelectorAll('#module-container .glass-panel[style*="cursor: pointer"]');
    if (!panels || panels.length === 0) return;

    // Super Investors
    if (panels[0]) panels[0].onclick = async () => {
        try {
            const res = await fetch("/static/data/super_investors.json");
            const data = await res.json();
            let html = '<table class="fiscal-table" style="width:100%; text-align:left;"><thead><tr><th>Name</th><th>Fund</th><th>AUM</th><th>Top Holdings</th><th>Strategy</th></tr></thead><tbody>';
            data.forEach(inv => {
                html += `<tr class="fiscal-row-hover">
                    <td style="font-weight:600;">${inv.name}</td>
                    <td>${inv.fund}</td>
                    <td style="font-family: var(--font-mono);">${inv.aum}</td>
                    <td>${inv.top_holdings.join(", ")}</td>
                    <td style="color:var(--fiscal-text-secondary);">${inv.strategy}</td>
                </tr>`;
            });
            html += '</tbody></table>';
            this.openModal("Super Investors Portfolios", html);
        } catch (e) {
            this.showToast("Failed to load Super Investors", "error");
        }
    };

    // Institutional Ownership
    if (panels[1]) panels[1].onclick = () => {
      if (this.app.state.stockCatalog.length > 0) {
        this.app.loadAnalysis(this.app.state.stockCatalog[0].ticker);
        // Switch to ownership tab
        setTimeout(() => {
            const anSubnav = document.querySelector('[data-an-panel="panel-ownership"]');
            if (anSubnav) anSubnav.click();
        }, 100);
      } else {
        this.showToast("No analyzed stocks found", "error");
      }
    };

    // Hedge Fund Letters
    if (panels[2]) panels[2].onclick = async () => {
        try {
            const res = await fetch("/static/data/hedge_fund_letters.json");
            const data = await res.json();
            let html = '<div style="display:flex; flex-direction:column; gap:16px;">';
            data.forEach(letter => {
                html += `<div style="padding:16px; border:1px solid var(--fiscal-border-light); border-radius:8px;">
                    <h3 style="font-size:1.1rem; margin-bottom:4px; color:var(--fiscal-accent-primary);"><a href="${letter.link}" target="_blank" style="color:inherit; text-decoration:none;">${letter.title}</a></h3>
                    <div style="font-size:0.85rem; color:var(--fiscal-text-secondary); margin-bottom:8px;">${letter.author} &bull; ${letter.fund} &bull; ${letter.date}</div>
                    <div style="font-size:0.9rem;"><strong>Topics:</strong> ${letter.topic}</div>
                </div>`;
            });
            html += '</div>';
            this.openModal("Hedge Fund Letters & Memos", html);
        } catch (e) {
            this.showToast("Failed to load Letters", "error");
        }
    };

    };
 
    // Earnings Calendar
    if (panels[3]) panels[3].onclick = () => {
        let html = '<table class="fiscal-table" style="width:100%; text-align:left;"><thead><tr><th>Ticker</th><th>Company</th><th>Sector</th><th>Last Analyzed</th><th>Action</th></tr></thead><tbody>';
        const catalog = this.app.state.stockCatalog || [];
        if (catalog.length === 0) {
            html += '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--fiscal-text-tertiary);">No analyzed stocks.</td></tr>';
        } else {
            catalog.forEach(s => {
                const dateStr = s.generated_at ? new Date(s.generated_at).toLocaleDateString() : 'N/A';
                html += `<tr class="fiscal-row-hover">
                    <td style="font-weight:600;">${s.ticker}</td>
                    <td>${s.company_name}</td>
                    <td>${s.sector}</td>
                    <td style="font-family: var(--font-mono);">${dateStr}</td>
                    <td><button class="fiscal-btn-secondary" style="font-size: 0.8rem; padding: 4px 8px;" onclick="window.App.loadAnalysis('${s.ticker}'); document.getElementById('resources-modal').style.display='none';">View</button></td>
                </tr>`;
            });
        }
        html += '</tbody></table>';
        this.openModal("Platform Earnings & Analysis Calendar", html);
    };

    // ETF Analysis
    if (panels[4]) panels[4].onclick = () => {
        let html = `
          <div style="margin-bottom: 16px; display: flex; gap: 8px;">
              <input type="text" id="etf-lookup-input" class="fiscal-search-input" placeholder="Enter ETF ticker (e.g. SPY, QQQ, IVV)" style="padding: 10px 14px; flex: 1;">
              <button class="fiscal-btn-primary" id="etf-lookup-btn">Analyze ETF</button>
          </div>
          <div id="etf-lookup-results" style="padding: 12px; background: var(--fiscal-bg-base); border-radius: 8px; border: 1px solid var(--fiscal-border-light); min-height: 150px; display: flex; align-items: center; justify-content: center; color: var(--fiscal-text-tertiary);">
              Enter an ETF symbol above to fetch components, holdings, and sector weightings.
          </div>
        `;
        this.openModal("ETF Analyzer", html);
        
        document.getElementById("etf-lookup-btn").onclick = async () => {
            const ticker = document.getElementById("etf-lookup-input").value.trim().toUpperCase();
            if (!ticker) return;
            const resultsDiv = document.getElementById("etf-lookup-results");
            resultsDiv.innerHTML = "Fetching ETF holdings and weightings...";
            
            try {
                const res = await fetch(`/api/stock/${ticker}`);
                if (res.ok) {
                    const data = await res.json();
                    const m = data.key_metrics || {};
                    let holdHtml = `
                      <div style="text-align: left; width: 100%;">
                          <h3 style="color: var(--fiscal-accent-primary); margin-bottom: 8px;">${data.company_name || ticker}</h3>
                          <p style="font-size: 0.9rem; color: var(--fiscal-text-secondary); margin-bottom: 16px;">${data.company_description || m.longBusinessSummary || 'ETF descriptions and holdings.'}</p>
                          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                              <div class="glass-panel" style="padding:10px;">
                                  <div style="font-size: 0.75rem; color: var(--fiscal-text-tertiary);">AUM</div>
                                  <div style="font-size: 1.1rem; font-weight: 600;">${this.app.formatNumber(m.marketCap || m.totalAssets, true)}</div>
                              </div>
                              <div class="glass-panel" style="padding:10px;">
                                  <div style="font-size: 0.75rem; color: var(--fiscal-text-tertiary);">Beta</div>
                                  <div style="font-size: 1.1rem; font-weight: 600;">${m.beta ? m.beta.toFixed(2) : '1.00'}</div>
                              </div>
                              <div class="glass-panel" style="padding:10px;">
                                  <div style="font-size: 0.75rem; color: var(--fiscal-text-tertiary);">Yield</div>
                                  <div style="font-size: 1.1rem; font-weight: 600;">${m.dividendYield ? (m.dividendYield * 100).toFixed(2) + '%' : 'N/A'}</div>
                              </div>
                          </div>
                          <h4 style="margin-bottom: 8px;">Top Holdings (Simulated)</h4>
                          <ul style="list-style: none; padding: 0; display:flex; flex-direction:column; gap:6px; font-size:0.9rem;">
                              <li style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid var(--fiscal-border-light);"><span>1. Microsoft Corp (MSFT)</span><strong>8.4%</strong></li>
                              <li style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid var(--fiscal-border-light);"><span>2. Apple Inc (AAPL)</span><strong>7.1%</strong></li>
                              <li style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid var(--fiscal-border-light);"><span>3. Nvidia Corp (NVDA)</span><strong>6.5%</strong></li>
                              <li style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid var(--fiscal-border-light);"><span>4. Amazon.com Inc (AMZN)</span><strong>3.9%</strong></li>
                          </ul>
                      </div>
                    `;
                    resultsDiv.innerHTML = holdHtml;
                } else {
                    const yfRes = await fetch(`/api/stock/${ticker}/history?period=5d`);
                    if (yfRes.ok) {
                        resultsDiv.innerHTML = `
                          <div style="text-align: left; width: 100%;">
                              <h3>${ticker} ETF Found</h3>
                              <p style="font-size: 0.9rem; color: var(--fiscal-text-secondary); margin-bottom: 12px;">This symbol has not been fully analyzed yet, but price data is active. Click below to compile a full report.</p>
                              <button class="fiscal-btn-primary" onclick="window.App.handleTickerSearch('${ticker}'); document.getElementById('resources-modal').style.display='none';">Compile Full ETF Analysis</button>
                          </div>
                        `;
                    } else {
                        resultsDiv.innerHTML = `<span style="color: var(--fiscal-accent-danger);">Symbol ${ticker} not found.</span>`;
                    }
                }
            } catch (err) {
                resultsDiv.innerHTML = `<span style="color: var(--fiscal-accent-danger);">Failed to load: ${err.message}</span>`;
            }
        };
    };

    // Documentation
    if (panels[5]) panels[5].onclick = () => window.open("/guide", "_blank");

    // Blog & Research
    if (panels[6]) panels[6].onclick = () => {
        let html = '<div style="display:flex; flex-direction:column; gap:16px;">';
        const catalog = this.app.state.stockCatalog || [];
        const stocksWithAnalysis = catalog.filter(s => s.verdict);
        if (stocksWithAnalysis.length === 0) {
            html += '<div style="text-align:center;color:var(--fiscal-text-tertiary);padding:20px;">No AI reports compiled yet.</div>';
        } else {
            stocksWithAnalysis.forEach(s => {
                const dateStr = s.generated_at ? s.generated_at.split('T')[0] : 'N/A';
                html += `
                  <div style="padding:16px; border:1px solid var(--fiscal-border-light); border-radius:8px; text-align:left;">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                          <h3 style="font-size:1.1rem; color:var(--fiscal-accent-primary); margin:0;">${s.ticker} - ${s.company_name}</h3>
                          <span class="fiscal-badge ${s.verdict === 'BUY' ? 'badge-success' : (s.verdict === 'SELL' ? 'badge-danger' : 'badge-warning')}">${s.verdict}</span>
                      </div>
                      <div style="font-size:0.85rem; color:var(--fiscal-text-secondary); margin-bottom:8px;">Confidence: ${s.confidence}% &bull; Generated: ${dateStr}</div>
                      <div style="font-size:0.9rem; line-height:1.5;">Altman Z-Score: <strong>${s.altman_z}</strong> (${s.altman_z_label}) | Piotroski F-Score: <strong>${s.piotroski_f}/9</strong>. Click View below for the full investment thesis.</div>
                      <button class="fiscal-btn-secondary" style="font-size: 0.8rem; padding: 4px 8px; margin-top: 10px;" onclick="window.App.loadAnalysis('${s.ticker}'); document.getElementById('resources-modal').style.display='none';">View Report</button>
                  </div>`;
            });
        }
        html += '</div>';
        this.openModal("AI Blog & Research Summaries", html);
    };
  },

  showToast: function(msg, type) {
    if (window.Toast) {
      window.Toast.show(msg, type);
    } else {
      alert(msg);
    }
  }
};
