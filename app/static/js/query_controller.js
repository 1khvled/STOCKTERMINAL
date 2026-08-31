window.QueryController = {
  docs: [],

  init: function(app) {
    this.app = app;
    this.populateDropdowns();
    this.bindEvents();
  },

  populateDropdowns: function() {
    const sel = document.getElementById("query-ticker");
    if (sel && this.app.state.stockCatalog.length) {
      sel.innerHTML = '<option value="">All Companies</option>';
      this.app.state.stockCatalog.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.ticker;
        opt.textContent = s.ticker + " - " + (s.company_name || "");
        sel.appendChild(opt);
      });
    }
  },

  bindEvents: function() {
    const inp = document.getElementById("query-search-input");
    if (inp) {
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this.runQuery();
      });
    }
    
    // Global bind
    window.runQuery = this.runQuery.bind(this);
  },

  runQuery: async function() {
    const q = document.getElementById("query-search-input")?.value.trim();
    if (!q) return;

    const scope = document.getElementById("query-scope")?.value || "all";
    const ticker = document.getElementById("query-ticker")?.value || "";
    const container = document.getElementById("query-results-container");

    if (container) {
      container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--fiscal-text-tertiary);">Searching documents for "' + q + '"...</div>';
    }

    let types = "";
    if (scope === "filings") types = "10-K,10-Q,8-K";
    else if (scope === "transcripts") types = "transcripts";
    else if (scope === "presentations") types = "presentations";
    else if (scope === "news") types = "news";

    try {
      const url = `/api/query/search?q=${encodeURIComponent(q)}&types=${encodeURIComponent(types)}&ticker=${encodeURIComponent(ticker)}`;
      const res = await fetch(url);
      const data = await res.json();
      
      this.renderResults(data.results || [], q);
    } catch (err) {
      console.error("Query search failed:", err);
      // Fallback
      const results = [];
      const stocks = this.app.state.stockCatalog || [];
      const searchTerms = q.toLowerCase().split(" ");

      stocks.forEach((s) => {
        if (ticker && s.ticker !== ticker) return;

        let score = 0;
        const searchText = (
          (s.company_name || "") + " " +
          (s.sector || "") + " " +
          (s.verdict || "") + " " +
          (s.ticker || "")
        ).toLowerCase();
        
        searchTerms.forEach((term) => {
          if (searchText.includes(term)) score += 10;
        });

        if (score > 0) {
          const price = s.current_price ? "$" + parseFloat(s.current_price).toFixed(2) : "--";
          results.push({
            ticker: s.ticker,
            company: s.company_name || s.ticker,
            snippet: (s.verdict ? "Rating: " + s.verdict + ". " : "") +
                     (s.sector ? "Sector: " + s.sector + ". " : "") +
                     (price !== "--" ? "Price: " + price + ". " : ""),
            score: score,
            source: "filings",
            date: s.generated_at || ""
          });
        }
      });

      results.sort((a, b) => b.score - a.score);
      this.renderResults(results, q);
    }
  },

  renderResults: function(results, q) {
    const container = document.getElementById("query-results-container");
    const countLabel = document.getElementById("query-count");
    
    if (!results || !results.length) {
      if (container) {
        container.innerHTML = '<div class="glass-panel" style="padding: 40px; text-align: center; color: var(--fiscal-text-tertiary);">No results found for "' + q + '". Try different keywords.</div>';
      }
      if (countLabel) countLabel.textContent = "0 results";
      return;
    }

    if (container) {
      container.innerHTML = results.map((r) => {
        const srcIcons = { filings: "📄", transcripts: "🎙️", presentations: "📊", news: "📰" };
        const title = r.title || `${r.ticker} &middot; ${r.company}`;
        const targetLink = r.link || "";
        let onclickAttr = `window.App.loadAnalysis('${r.ticker}')`;
        if (targetLink.startsWith("http")) {
            onclickAttr = `window.open('${targetLink}', '_blank')`;
        }
        
        return `<div class="glass-panel" style="padding: 16px 20px; cursor: pointer; margin-bottom: 12px;" onclick="${onclickAttr}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div style="font-weight: 600; color: var(--fiscal-text-primary);">${srcIcons[r.source] || "📄"} ${title}</div>
                    <div style="font-size: 0.85rem; color: var(--fiscal-text-secondary); margin-top: 6px; line-height: 1.5;">${r.snippet}</div>
                </div>
                <div style="text-align: right; flex-shrink: 0; margin-left: 16px;">
                    <div style="font-size: 0.75rem; color: var(--fiscal-text-tertiary);">${r.date || ""}</div>
                    <div style="font-size: 0.75rem; color: var(--fiscal-accent-primary); margin-top: 4px;">${Math.round(r.score)}% match</div>
                </div>
            </div>
        </div>`;
      }).join("");
    }

    if (countLabel) countLabel.textContent = results.length + " results";
  }
};
