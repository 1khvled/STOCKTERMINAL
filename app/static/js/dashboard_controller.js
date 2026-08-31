window.DashboardController = {
    init: async function(app) {
        this.app = app;
        this.chartInstance = null;
        this.currentPeriod = '1M';
        
        await this.renderWatchlist();
        this.fetchIndices();
        this.startIndicesInterval();
        
        // Render chart with first watchlist item as proxy
        const stocks = this.app.state.stockCatalog || [];
        if (stocks.length > 0) {
            this.activeChartTicker = stocks[0].ticker;
            await this.updateChartPeriod(this.currentPeriod);
        } else {
            this.renderEmptyChart();
        }
    },

    renderWatchlist: async function() {
        const container = document.getElementById('dash-watchlist-container');
        if (!container) return;

        const stocks = this.app.state.stockCatalog || [];
        if (stocks.length === 0) {
            container.innerHTML = `<p style="color: var(--fiscal-text-tertiary); padding: 16px;">No stocks analyzed yet. Search a ticker above to begin.</p>`;
            return;
        }

        let html = '';
        for (let s of stocks) {
            const price = s.current_price ? `$${parseFloat(s.current_price).toFixed(2)}` : 'N/A';
            const upside = parseFloat(s.upside || 0);
            const color = upside >= 0 ? 'var(--fiscal-accent-success)' : 'var(--fiscal-accent-danger)';
            const sign = upside >= 0 ? '+' : '';
            const pct = (upside * 100).toFixed(2);
            
            html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--fiscal-border-light); cursor: pointer;" onclick="window.App.loadAnalysis('${s.ticker}')">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 32px; height: 32px; background: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                        <img src="https://logo.clearbit.com/${s.ticker.toLowerCase()}.com" style="width: 20px; border-radius: 50%;" onerror="this.style.display='none'">
                    </div>
                    <div>
                        <div style="font-weight: 600;">${s.ticker}</div>
                        <div style="font-size: 0.8rem; color: var(--fiscal-text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px;">${s.company_name}</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: 600; font-family: var(--font-mono);">${price}</div>
                    <div style="font-size: 0.85rem; color: ${color};">${sign}${pct}%</div>
                </div>
            </div>`;
        }
        
        container.innerHTML = html;
        document.getElementById('dash-watchlist-count').innerText = stocks.length;
    },
    
    fetchIndices: function() {
        fetch("/api/ticker-tape")
          .then((r) => r.json())
          .then((data) => {
            if (!data.length) return;
            const ids = {
                "S&P 500": "idx-sp500",
                "NASDAQ 100": "idx-nasdaq",
                "US 10-YR YIELD": "idx-10y",
                "CBOE VIX": "idx-vix"
            };
            data.forEach((d) => {
                const id = ids[d.label];
                if (!id) return;
                
                const valEl = document.getElementById(`${id}-val`);
                const badgeEl = document.getElementById(`${id}-badge`);
                
                if (valEl) valEl.textContent = d.val;
                if (badgeEl) {
                    const p = typeof d.pct === "number" ? d.pct : 0;
                    badgeEl.textContent = (p >= 0 ? "+" : "") + p.toFixed(2) + "%";
                    badgeEl.className = "fiscal-badge " + (p >= 0 ? "badge-success" : "badge-danger");
                }
            });
          })
          .catch(() => {});
    },
    
    startIndicesInterval: function() {
        if (this.interval) clearInterval(this.interval);
        this.interval = setInterval(() => this.fetchIndices(), 60000); // 60s
    },

    updateChartPeriod: async function(period) {
        if (!this.activeChartTicker) return;
        
        this.currentPeriod = period;
        document.querySelectorAll('.fiscal-toggle-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.range === period);
        });
        
        const periodMap = { '1D': '1d', '1W': '5d', '1M': '1mo', 'YTD': 'ytd', '1Y': '1y' };
        const apiPeriod = periodMap[period] || '1mo';
        
        try {
            const res = await fetch(`/api/stock/${this.activeChartTicker}/history?period=${apiPeriod}`);
            const data = await res.json();
            
            if (data.history && data.history.length > 0) {
                this.renderChart(data.history);
                
                // Update portfolio value text based on latest
                const first = data.history[0].close;
                const last = data.history[data.history.length - 1].close;
                const pct = ((last - first) / first) * 100;
                
                document.getElementById('dash-portfolio-val').innerText = `$${last.toFixed(2)}`;
                const pctEl = document.getElementById('dash-portfolio-pct');
                pctEl.innerText = `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}% (${period})`;
                pctEl.style.color = pct >= 0 ? 'var(--fiscal-accent-success)' : 'var(--fiscal-accent-danger)';
            }
        } catch(e) {
            console.error("Failed to fetch chart data", e);
        }
    },

    renderChart: function(historyData) {
        const ctx = document.getElementById('dash-portfolio-chart');
        if (!ctx) return;
        
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }
        
        const labels = historyData.map(d => d.date.split(' ')[0] || d.date);
        const data = historyData.map(d => d.close);
        
        const isPositive = data[data.length - 1] >= data[0];
        const color = isPositive ? '#10b981' : '#f43f5e';
        const bgColor = isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)';
        
        this.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: this.activeChartTicker,
                    data: data,
                    borderColor: color,
                    backgroundColor: bgColor,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { 
                        display: false,
                        min: Math.min(...data) * 0.99,
                        max: Math.max(...data) * 1.01
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                }
            }
        });
    },
    
    renderEmptyChart: function() {
        const ctx = document.getElementById('dash-portfolio-chart');
        if (!ctx) return;
        new Chart(ctx, {
            type: 'line',
            data: { labels: [''], datasets: [{ data: [] }] },
            options: { responsive: true, maintainAspectRatio: false }
        });
    },

    openNewPortfolioModal: function() {
        let modal = document.getElementById("portfolio-modal");
        if (!modal) {
            modal = document.createElement("div");
            modal.id = "portfolio-modal";
            modal.style = "display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:9999; align-items:center; justify-content:center;";
            modal.innerHTML = `
                <div class="glass-panel" style="width: 90%; max-width: 500px; padding: 24px; position: relative; display:flex; flex-direction:column; gap:16px;">
                    <button id="close-portfolio-modal" style="position: absolute; right: 20px; top: 20px; background: transparent; border: none; color: var(--fiscal-text-secondary); cursor: pointer; font-size: 1.5rem;">&times;</button>
                    <h2 style="margin: 0; font-size: 1.35rem; color: var(--fiscal-accent-primary);">Create New Portfolio</h2>
                    <div>
                        <label style="display:block; margin-bottom:6px; font-size:0.85rem; color:var(--fiscal-text-secondary);">Portfolio Name</label>
                        <input type="text" id="port-name-input" class="fiscal-search-input" placeholder="e.g. Tech Growth, Value Stocks" style="width:100%; padding:10px; box-sizing: border-box; background: var(--fiscal-bg-base); color: var(--fiscal-text-primary); border: 1px solid var(--fiscal-border-light); border-radius: 6px;">
                    </div>
                    <div>
                        <label style="display:block; margin-bottom:6px; font-size:0.85rem; color:var(--fiscal-text-secondary);">Select Stocks</label>
                        <div id="port-stocks-select-list" style="max-height: 150px; overflow-y:auto; border: 1px solid var(--fiscal-border-light); border-radius:6px; padding:8px; display:flex; flex-direction:column; gap:6px; background: var(--fiscal-bg-base);">
                            <!-- Populated with checkboxes -->
                        </div>
                    </div>
                    <button class="fiscal-btn-primary" id="save-portfolio-btn" style="padding:10px 16px; margin-top:8px;">Save Portfolio</button>
                </div>
            `;
            document.body.appendChild(modal);
            document.getElementById("close-portfolio-modal").onclick = () => modal.style.display = "none";
            modal.onclick = (e) => { if(e.target === modal) modal.style.display = "none"; };
        }

        const listDiv = document.getElementById("port-stocks-select-list");
        if (listDiv) {
            const stocks = this.app.state.stockCatalog || [];
            if (stocks.length === 0) {
                listDiv.innerHTML = '<div style="color:var(--fiscal-text-tertiary); font-size:0.85rem;">No stocks available. Analyze some first!</div>';
            } else {
                listDiv.innerHTML = stocks.map(s => `
                  <label style="display:flex; align-items:center; gap:8px; font-size:0.9rem; cursor:pointer; color: var(--fiscal-text-primary);">
                      <input type="checkbox" name="port-stock-chk" value="${s.ticker}">
                      <span><strong>${s.ticker}</strong> - ${s.company_name}</span>
                  </label>
                `).join("");
            }
        }

        document.getElementById("save-portfolio-btn").onclick = () => {
            const name = document.getElementById("port-name-input").value.trim();
            if (!name) {
                this.app.showToast("Please enter a portfolio name", "error");
                return;
            }
            const checked = Array.from(document.querySelectorAll('input[name="port-stock-chk"]:checked')).map(el => el.value);
            if (checked.length === 0) {
                this.app.showToast("Please select at least one stock", "error");
                return;
            }

            const portfolios = JSON.parse(localStorage.getItem("fiscal_portfolios") || "[]");
            portfolios.push({ name, stocks: checked, id: Date.now() });
            localStorage.setItem("fiscal_portfolios", JSON.stringify(portfolios));
            
            this.app.showToast(`Portfolio "${name}" created successfully!`, "success");
            modal.style.display = "none";
            
            this.renderWatchlist();
        };

        document.getElementById("port-name-input").value = "";
        modal.style.display = "flex";
    }
};
