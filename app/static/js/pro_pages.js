(function () {
    const page = document.body.dataset.proPage;
    if (!page) return;

    const fmtMoney = (value) => {
        const n = Number(value || 0);
        if (!n) return "N/A";
        if (Math.abs(n) >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
        if (Math.abs(n) >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
        if (Math.abs(n) >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
        return "$" + n.toFixed(2);
    };
    const fmtPct = (value) => {
        const n = Number(value || 0) * 100;
        return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
    };
    const verdictClass = (verdict) => {
        const v = String(verdict || "").toUpperCase();
        if (v.includes("BUY")) return "pro-positive";
        if (v.includes("SELL")) return "pro-negative";
        return "pro-muted";
    };

    async function loadStocks() {
        const res = await fetch("/api/stocks");
        const data = await res.json();
        return data.stocks || [];
    }

    function row(stock) {
        const up = Number(stock.upside || 0);
        return `
            <tr>
                <td><a href="/dashboard/${stock.ticker}" style="color:var(--term-text);text-decoration:none;font-weight:800;">${stock.ticker}</a></td>
                <td>${stock.company_name || "N/A"}</td>
                <td class="${verdictClass(stock.verdict)}">${stock.verdict || "HOLD"}</td>
                <td>${fmtMoney(stock.current_price)}</td>
                <td class="${up >= 0 ? "pro-positive" : "pro-negative"}">${fmtPct(up)}</td>
                <td>${stock.sector || "N/A"}</td>
            </tr>`;
    }

    function renderTable(id, stocks) {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = stocks.length ? stocks.map(row).join("") : `<tr><td colspan="6" class="pro-muted">NO LOCAL RECORDS</td></tr>`;
    }

    function renderStats(stocks) {
        const buy = stocks.filter(s => String(s.verdict || "").toUpperCase().includes("BUY")).length;
        const sell = stocks.filter(s => String(s.verdict || "").toUpperCase().includes("SELL")).length;
        const avgUpside = stocks.length ? stocks.reduce((a, s) => a + Number(s.upside || 0), 0) / stocks.length : 0;
        document.querySelectorAll("[data-stock-count]").forEach(el => el.textContent = stocks.length);
        document.querySelectorAll("[data-buy-count]").forEach(el => el.textContent = buy);
        document.querySelectorAll("[data-sell-count]").forEach(el => el.textContent = sell);
        document.querySelectorAll("[data-avg-upside]").forEach(el => {
            el.textContent = fmtPct(avgUpside);
            el.className = avgUpside >= 0 ? "pro-positive" : "pro-negative";
        });
    }

    async function init() {
        const stocks = await loadStocks();
        renderStats(stocks);

        if (page === "watchlist") {
            const watch = JSON.parse(localStorage.getItem("stocker_watchlist") || "[]");
            renderTable("pro-primary-table", stocks.filter(s => watch.includes(s.ticker)));
            renderTable("pro-secondary-table", stocks.slice().sort((a, b) => Number(b.upside || 0) - Number(a.upside || 0)).slice(0, 8));
        }

        if (page === "reports") {
            const byDate = stocks.slice().sort((a, b) => new Date(b.generated_at || 0) - new Date(a.generated_at || 0));
            const body = document.getElementById("pro-primary-table");
            body.innerHTML = byDate.map(stock => `
                <tr>
                    <td>${stock.ticker}</td>
                    <td>${stock.company_name || "N/A"}</td>
                    <td>${stock.generated_at || "N/A"}</td>
                    <td><a href="/excel/${stock.ticker}" class="ops-link" style="display:inline-flex;padding:6px 10px;">EXCEL</a></td>
                    <td><a href="/json/${stock.ticker}" class="ops-link" style="display:inline-flex;padding:6px 10px;">JSON</a></td>
                    <td><a href="/dashboard/${stock.ticker}" class="ops-link" style="display:inline-flex;padding:6px 10px;">OPEN</a></td>
                </tr>`).join("");
        }

        if (page === "market-feed") {
            renderTable("pro-primary-table", stocks.slice().sort((a, b) => Number(b.upside || 0) - Number(a.upside || 0)).slice(0, 12));
            renderTable("pro-secondary-table", stocks.slice().sort((a, b) => Number(a.upside || 0) - Number(b.upside || 0)).slice(0, 8));
        }

        if (page === "system") {
            renderTable("pro-primary-table", stocks.slice().sort((a, b) => String(b.generated_at || "").localeCompare(String(a.generated_at || ""))).slice(0, 10));
        }
    }

    init().catch(err => {
        document.querySelectorAll("tbody").forEach(el => {
            el.innerHTML = `<tr><td colspan="6" class="pro-negative">FAILED TO LOAD LOCAL STOCK DATABASE</td></tr>`;
        });
        console.error(err);
    });
})();
