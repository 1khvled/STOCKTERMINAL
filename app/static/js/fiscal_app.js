class FiscalApp {
  constructor() {
    this.state = {
      currentModule: "dashboard",
      activeTicker: null,
      openTabs: [],
      stockCatalog: [],
      cache: {},
    };
    this.searchParams = new URLSearchParams(window.location.search);
  }

  async init() {
    this.container = document.getElementById("module-container");
    this.tabContainer = document.getElementById("tab-container");

    await this.fetchCatalog();
    
    // Handle initial routing from hash or search params
    const hash = window.location.hash.slice(1);
    const initialTicker = this.searchParams.get("ticker");
    
    if (hash.startsWith('analysis/')) {
        this.loadAnalysis(hash.split('/')[1]);
    } else if (hash) {
        this.loadModule(hash);
    } else if (initialTicker) {
      this.loadAnalysis(initialTicker);
    } else {
      this.loadModule("dashboard");
    }
    
    this.setupGlobalSearch();
    this.setupKeyboardShortcuts();
    
    // Handle browser back/forward buttons
    window.addEventListener('hashchange', () => {
        const h = window.location.hash.slice(1);
        if (h.startsWith('analysis/')) {
            const t = h.split('/')[1];
            if (this.state.activeTicker !== t) this.loadAnalysis(t, false);
        } else if (h && this.state.currentModule !== h) {
            this.loadModule(h, null, false);
        } else if (!h && this.state.currentModule !== "dashboard") {
            this.loadModule("dashboard", null, false);
        }
    });
  }

  async fetchCatalog() {
    try {
      const res = await fetch("/api/stocks");
      const data = await res.json();
      this.state.stockCatalog = data.stocks || [];
    } catch (e) {
      console.error("Failed to load catalog", e);
    }
  }

  async fetchTickerData(ticker) {
    ticker = ticker.toUpperCase();
    if (this.state.cache[ticker]) return this.state.cache[ticker];
    try {
      const res = await fetch(`/api/stock/${ticker}`);
      if (!res.ok) throw new Error("Ticker not found");
      const data = await res.json();
      this.state.cache[ticker] = data;
      return data;
    } catch (e) {
      console.error(`Failed to load ${ticker}`, e);
      return null;
    }
  }

  escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  async loadModule(moduleName, ticker = null, updateHash = true) {
    this.state.currentModule = moduleName;
    if (updateHash) {
        window.location.hash = moduleName;
    }
    
    document
      .querySelectorAll(".fiscal-nav-item")
      .forEach((el) => el.classList.remove("active"));
    const navItem = document.querySelector(
      `.fiscal-nav-item[data-module="${moduleName}"]`,
    );
    if (navItem) navItem.classList.add("active");

    try {
      this.showLoading(this.container);
      const res = await fetch(`/module/${moduleName}`);
      if (!res.ok) throw new Error(`Module ${moduleName} returned ${res.status}`);
      const html = await res.text();
      this.container.innerHTML = html;
      this.updateTabs(moduleName, ticker);

      if (moduleName === "analysis" && ticker) {
        this.state.activeTicker = ticker;
      }
      
      // Initialize module specific controllers
      if (moduleName === "charting" && typeof ChartingController !== 'undefined') ChartingController.init(this);
      if (moduleName === "screener" && typeof ScreenerController !== 'undefined') ScreenerController.init(this);
      if (moduleName === "query" && typeof QueryController !== 'undefined') QueryController.init(this);
      if (moduleName === "resources" && typeof ResourcesController !== 'undefined') ResourcesController.init(this);
      
    } catch (e) {
      console.error(`Failed to load module ${moduleName}`, e);
      this.container.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--fiscal-accent-danger);">Failed to load ${moduleName}</div>`;
      this.showToast(`Failed to load ${moduleName}`, 'error');
    }
  }

  loadAnalysis(ticker, updateHash = true) {
    this.state.activeTicker = ticker.toUpperCase();
    if (updateHash) {
        window.location.hash = `analysis/${ticker.toUpperCase()}`;
    }
    this.loadModule("analysis", ticker.toUpperCase(), false);
  }

  updateTabs(moduleName, ticker) {
    let tabName = moduleName.charAt(0).toUpperCase() + moduleName.slice(1);
    if (moduleName === "analysis" && ticker) tabName = `${ticker} Analysis`;

    document
      .querySelectorAll(".fiscal-tab")
      .forEach((el) => el.classList.remove("active"));
      
    let exists = Array.from(this.tabContainer.children).find(
      (t) => t.dataset.name === tabName,
    );
    
    if (!exists) {
      const tab = document.createElement("div");
      tab.className = "fiscal-tab active";
      tab.dataset.name = tabName;
      tab.innerHTML = `${tabName}<svg class="fiscal-tab-close" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
      tab.onclick = (e) => {
        if (e.target.closest(".fiscal-tab-close")) {
          tab.remove();
          // If we closed the active tab, go to dashboard
          if (tab.classList.contains('active')) {
             this.loadModule("dashboard");
          }
        } else {
          if (moduleName === "analysis") this.loadAnalysis(ticker);
          else this.loadModule(moduleName);
        }
      };
      this.tabContainer.appendChild(tab);
    } else {
      exists.classList.add("active");
    }
  }

  async handleTickerSearch(ticker) {
    ticker = ticker.toUpperCase();
    const exists = this.state.stockCatalog.find((s) => s.ticker === ticker);
    if (exists) {
      this.loadAnalysis(ticker);
    } else {
      this.triggerLiveAnalysis(ticker);
    }
  }

  handleCommand(raw) {
    const value = raw.trim();
    if (!value) return;
    const parts = value.split(/\s+/);
    const command = parts[0].toUpperCase();
    const arg = (parts[1] || "").toUpperCase();
    const routeCommands = {
      NEWS: "/news-impact",
      IMPACT: "/news-impact",
      SEC: "/filings",
      FILINGS: "/filings",
      LAB: "/scenario-lab",
      SCENARIO: "/scenario-lab",
      IC: "/committee",
      COMMITTEE: "/committee",
      FLAGS: "/red-flags",
      RISK: "/red-flags",
      PORT: "/portfolio",
      PORTFOLIO: "/portfolio",
      WATCH: "/watchlist",
      WATCHLIST: "/watchlist",
      REPORTS: "/reports",
      SYSTEM: "/system",
      SYS: "/system",
      GUIDE: "/guide",
    };

    if (["RUN", "EXEC", "ANALYZE"].includes(command) && arg) {
      this.triggerLiveAnalysis(arg);
      return;
    }
    if (["OPEN", "DASH", "LOAD"].includes(command) && arg) {
      this.handleTickerSearch(arg);
      return;
    }
    if (command === "COMPARE" && parts.length > 1) {
      window.location.href = `/compare?tickers=${encodeURIComponent(parts.slice(1).join(","))}`;
      return;
    }
    if (routeCommands[command]) {
      const route = routeCommands[command];
      window.location.href = arg ? `${route}?ticker=${encodeURIComponent(arg)}` : route;
      return;
    }
    this.handleTickerSearch(value);
  }

  setupGlobalSearch() {
    const input = document.getElementById("global-search");
    const container = document.querySelector(".fiscal-search-container");
    if (!input || !container) return;
    
    // Create dropdown container
    const dropdown = document.createElement('div');
    dropdown.className = 'search-dropdown';
    container.appendChild(dropdown);
    
    let selectedIndex = -1;
    let currentResults = [];

    const renderDropdown = (query) => {
        if (!query) {
            dropdown.classList.remove('visible');
            return;
        }
        
        query = query.toLowerCase();
        currentResults = this.state.stockCatalog.filter(s => 
            s.ticker.toLowerCase().includes(query) || 
            s.company_name.toLowerCase().includes(query)
        ).slice(0, 8); // Max 8 results
        
        if (currentResults.length === 0) {
            dropdown.innerHTML = `<div class="search-dropdown-item" style="color: var(--fiscal-text-tertiary); justify-content: center;">Press Enter to run "${this.escapeHtml(query.toUpperCase())}"</div>`;
        } else {
            dropdown.innerHTML = currentResults.map((s, i) => `
                <div class="search-dropdown-item ${i === selectedIndex ? 'selected' : ''}" data-index="${i}">
                    <div style="display:flex; align-items:center;">
                        <span class="ticker">${this.escapeHtml(s.ticker)}</span>
                        <span class="company">${this.escapeHtml(s.company_name)}</span>
                    </div>
                    <span class="sector">${this.escapeHtml(s.sector || '')}</span>
                </div>
            `).join('');
        }
        
        dropdown.classList.add('visible');
    };

    input.addEventListener("input", (e) => {
        selectedIndex = -1;
        renderDropdown(e.target.value.trim());
    });
    
    input.addEventListener("focus", () => {
        if (input.value.trim()) renderDropdown(input.value.trim());
    });

    input.addEventListener("keydown", (e) => {
      const query = input.value.trim();
      if (!query) return;

      if (e.key === "Enter") {
        e.preventDefault();
        dropdown.classList.remove('visible');
        if (selectedIndex >= 0 && currentResults[selectedIndex]) {
            this.handleTickerSearch(currentResults[selectedIndex].ticker);
            input.value = "";
        } else {
            this.handleCommand(query);
            input.value = "";
        }
      } else if (e.key === "ArrowDown") {
          e.preventDefault();
          selectedIndex = Math.min(selectedIndex + 1, currentResults.length - 1);
          renderDropdown(query);
      } else if (e.key === "ArrowUp") {
          e.preventDefault();
          selectedIndex = Math.max(selectedIndex - 1, -1);
          renderDropdown(query);
      } else if (e.key === "Escape") {
          dropdown.classList.remove('visible');
          input.blur();
      }
    });
    
    dropdown.addEventListener('mousedown', (e) => {
        const item = e.target.closest('.search-dropdown-item');
        if (item && item.dataset.index !== undefined) {
            e.preventDefault();
            const idx = parseInt(item.dataset.index);
            if (currentResults[idx]) {
                this.handleTickerSearch(currentResults[idx].ticker);
                input.value = "";
                dropdown.classList.remove('visible');
            }
        }
    });

    // Close dropdown on click outside
    document.addEventListener("click", (e) => {
        if (!container.contains(e.target)) {
            dropdown.classList.remove('visible');
        }
    });
  }

  setupKeyboardShortcuts() {
      document.addEventListener("keydown", (e) => {
          // Focus search on '/'
          if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) {
            e.preventDefault();
            document.getElementById("global-search")?.focus();
          }
          // Focus search on Ctrl+K or Cmd+K
          if ((e.ctrlKey || e.metaKey) && e.key === "k") {
              e.preventDefault();
              document.getElementById("global-search")?.focus();
          }
        });
  }

  triggerLiveAnalysis(ticker) {
    const modal = document.createElement("div");
    modal.id = "stream-modal";
    modal.style.cssText =
      "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);backdrop-filter:blur(5px);z-index:1000;display:flex;align-items:center;justify-content:center;";
    modal.innerHTML = `
            <div class="glass-panel module-animated" style="width:600px;padding:32px;display:flex;flex-direction:column;gap:20px;">
                <h2 style="color:var(--fiscal-accent-primary);">Compiling Analysis for ${this.escapeHtml(ticker)}</h2>
                <div id="stream-logs" style="height:300px;overflow-y:auto;font-family:var(--font-mono);font-size:0.85rem;color:var(--fiscal-text-secondary);background:var(--fiscal-bg-base);padding:16px;border-radius:8px; border: 1px solid var(--fiscal-border-light);">Starting connection to AI Engine...</div>
                <div style="height:4px;background:var(--fiscal-border-light);border-radius:2px;overflow:hidden;"><div id="stream-progress" style="height:100%;width:0%;background:var(--fiscal-accent-primary);transition:width 0.3s;"></div></div>
            </div>`;
    document.body.appendChild(modal);

    const logContainer = document.getElementById("stream-logs");
    const progressBar = document.getElementById("stream-progress");
    const source = new EventSource(`/api/stream?ticker=${ticker}`);

    source.onmessage = (event) => {
      if (event.data.startsWith("REDIRECT:")) {
        source.close();
        progressBar.style.width = "100%";
        progressBar.style.background = "var(--fiscal-accent-success)";
        const route = event.data.replace("REDIRECT:", "").trim();
        const redirectedTicker = route.split("/").pop() || ticker;
        setTimeout(() => {
          modal.remove();
          this.fetchCatalog().then(() => this.loadAnalysis(redirectedTicker));
        }, 800);
      } else if (
        event.data.includes("DONE:") ||
        event.data.includes("Analysis complete")
      ) {
        source.close();
        progressBar.style.width = "100%";
        progressBar.style.background = "var(--fiscal-accent-success)";
        setTimeout(() => {
          modal.remove();
          this.fetchCatalog().then(() => this.loadAnalysis(ticker));
        }, 1500);
      } else if (
        event.data.includes("Error:") ||
        event.data.includes("FAILED")
      ) {
        source.close();
        logContainer.innerHTML += `<br><span style="color:var(--fiscal-accent-danger);">${this.escapeHtml(event.data)}</span>`;
        progressBar.style.background = "var(--fiscal-accent-danger)";
        setTimeout(() => modal.remove(), 4000);
      } else {
        logContainer.innerHTML += `<br>${this.escapeHtml(event.data)}`;
        logContainer.scrollTop = logContainer.scrollHeight;
        let w = parseFloat(progressBar.style.width) || 0;
        if (w < 95) progressBar.style.width = w + 5 + "%";
      }
    };
    source.onerror = () => {
      source.close();
      logContainer.innerHTML += `<br><span style="color:var(--fiscal-accent-danger);">Connection lost.</span>`;
      setTimeout(() => modal.remove(), 4000);
    };
  }

  toggleTheme() {
    document.body.classList.toggle('theme-light');
  }
  
  // --- Global UI Utilities ---
  
  showToast(message, type = 'info') {
      const toast = document.createElement('div');
      toast.className = `fiscal-toast ${type}`;
      toast.innerText = message;
      document.body.appendChild(toast);
      setTimeout(() => {
          toast.style.animation = 'toastIn 0.3s ease-out reverse forwards';
          setTimeout(() => toast.remove(), 300);
      }, 3000);
  }
  
  showLoading(container) {
      if (!container) return;
      container.innerHTML = `
        <div style="padding: 24px; display:flex; flex-direction:column; gap:16px;">
            <div class="skeleton-pulse" style="height: 40px; width: 30%;"></div>
            <div class="skeleton-pulse" style="height: 200px; width: 100%;"></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
                <div class="skeleton-pulse" style="height: 120px; width: 100%;"></div>
                <div class="skeleton-pulse" style="height: 120px; width: 100%;"></div>
            </div>
        </div>
      `;
  }
  
  formatNumber(num, isCurrency=false) {
        if (!num && num !== 0) return 'N/A';
        const abs = Math.abs(num);
        let formatted;
        if (abs >= 1e12) formatted = (num / 1e12).toFixed(2) + 'T';
        else if (abs >= 1e9) formatted = (num / 1e9).toFixed(2) + 'B';
        else if (abs >= 1e6) formatted = (num / 1e6).toFixed(2) + 'M';
        else formatted = num.toLocaleString(undefined, {maximumFractionDigits:2});
        return isCurrency ? '$' + formatted : formatted;
  }
  
  formatPct(num) {
      if (!num && num !== 0) return 'N/A';
      const val = (num * 100).toFixed(1);
      const sign = num > 0 ? '+' : '';
      return `${sign}${val}%`;
  }
}

window.App = new FiscalApp();
document.addEventListener("DOMContentLoaded", () => window.App.init());
