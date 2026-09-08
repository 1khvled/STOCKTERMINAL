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

    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    function row(stock) {
        const up = Number(stock.upside || 0);
        return `
            <tr>
                <td><a href="/dashboard/${esc(stock.ticker)}" style="color:var(--text);text-decoration:none;font-weight:800;">${esc(stock.ticker)}</a></td>
                <td>${esc(stock.company_name) || "N/A"}</td>
                <td class="${verdictClass(stock.verdict)}">${esc(stock.verdict) || "HOLD"}</td>
                <td>${fmtMoney(stock.current_price)}</td>
                <td class="${up >= 0 ? "pro-positive" : "pro-negative"}">${fmtPct(up)}</td>
                <td>${esc(stock.sector) || "N/A"}</td>
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

        if (page === "reports") {
            const byDate = stocks.slice().sort((a, b) => new Date(b.generated_at || 0) - new Date(a.generated_at || 0));
            const body = document.getElementById("pro-primary-table");
            body.innerHTML = byDate.map(stock => `
                <tr>
                    <td>${esc(stock.ticker)}</td>
                    <td>${esc(stock.company_name) || "N/A"}</td>
                    <td>${esc(stock.generated_at) || "N/A"}</td>
                    <td><a href="/excel/${stock.ticker}" class="ops-link" style="display:inline-flex;padding:6px 10px;">EXCEL</a></td>
                    <td><a href="/json/${stock.ticker}" class="ops-link" style="display:inline-flex;padding:6px 10px;">JSON</a></td>
                    <td><a href="/dashboard/${stock.ticker}" class="ops-link" style="display:inline-flex;padding:6px 10px;">OPEN</a></td>
                </tr>`).join("");
        }

        if (page === "market-feed") {
            renderTable("pro-primary-table", stocks.slice().sort((a, b) => Number(b.upside || 0) - Number(a.upside || 0)).slice(0, 12));
            renderTable("pro-secondary-table", stocks.slice().sort((a, b) => Number(a.upside || 0) - Number(b.upside || 0)).slice(0, 8));
        }

    async function renderSystem() {
        const set = (id, txt, cls) => { const el = document.getElementById(id); if (!el) return; el.textContent = txt; if (cls) el.className = cls; };
        try {
            const res = await Promise.all([fetch("/api/system/auto-update/status"), fetch("/api/system/earnings-schedule")]);
            const st = await res[0].json();
            const es = await res[1].json();
            const due = st.earnings_due || es.due || [];
            const qn = (st.queue || []).length;
            set("auto-state", st.running ? ("RUNNING" + (qn ? " - " + qn + " QUEUED" : "")) : "IDLE", st.running ? "pro-positive" : "pro-muted");
            set("auto-tracked", String(st.total_tracked != null ? st.total_tracked : "--"));
            set("auto-due", due.length ? String(due.length) + " DUE" : "NONE DUE", due.length ? "pro-negative" : "pro-positive");
            set("auto-lastrun", st.last_run || "NEVER");
            const log = document.getElementById("auto-log");
            if (log) { const lines = (st.log || []).slice(-12); log.innerHTML = lines.length ? lines.map(function (l) { return esc(l); }).join("<br/>") : "No auto-update runs yet - engine checks hourly, refreshes records older than 85 days or just past earnings."; }
            const sched = es.schedule || st.earnings_schedule || {};
            const dueMap = {}; due.forEach(function (d) { dueMap[d.ticker] = d.reason || "due"; });
            const today = new Date(); today.setHours(0, 0, 0, 0);
            const rows = Object.keys(sched).map(function (t) {
                const nx = (sched[t] || {}).next_earnings;
                let days = null;
                if (nx) { const d = new Date(nx + "T12:00:00"); if (!isNaN(d)) days = Math.round((d - today) / 86400000); }
                return { ticker: t, next: nx || "N/A", days: days, due: !!dueMap[t], reason: dueMap[t] || "" };
            }).sort(function (a, b) { return (a.days == null ? 9999 : a.days) - (b.days == null ? 9999 : b.days); });
            const tb = document.getElementById("earn-table");
            if (tb) { tb.innerHTML = rows.length ? rows.map(function (r) {
                const cd = r.days == null ? "N/A" : (r.days < 0 ? Math.abs(r.days) + "d AGO" : (r.days === 0 ? "TODAY" : "IN " + r.days + "d"));
                return "<tr><td><a href=\"/dashboard/" + esc(r.ticker) + "\" style=\"color:var(--text);text-decoration:none;font-weight:800;\">" + esc(r.ticker) + "</a></td><td>" + esc(r.next) + "</td><td>" + esc(cd) + "</td><td class=\"" + (r.due ? "pro-negative" : "pro-muted") + "\">" + (r.due ? "QUEUED - " + esc(r.reason) : "SCHEDULED") + "</td></tr>";
            }).join("") : "<tr><td colspan=\"4\" class=\"pro-muted\">NO EARNINGS DATES CACHED</td></tr>"; }
        } catch (err) { set("auto-state", "UNREACHABLE", "pro-negative"); console.error(err); }
        const btn = document.getElementById("auto-trigger");
        if (btn && !btn.dataset.wired) {
            btn.dataset.wired = "1";
            btn.addEventListener("click", async function () {
                btn.disabled = true; btn.textContent = "CHECKING...";
                try { await fetch("/api/system/auto-update/trigger", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); if (window.showToast) window.showToast("Refresh check triggered", "success"); }
                catch (e) { if (window.showToast) window.showToast("Trigger failed", "error"); }
                setTimeout(function () { btn.disabled = false; btn.textContent = "RUN REFRESH CHECK"; renderSystem(); }, 4000);
            });
        }
    }

        if (page === "system") {
            await renderSystem();
        }
    }

    init().catch(err => {
        document.querySelectorAll("tbody").forEach(el => {
            el.innerHTML = `<tr><td colspan="6" class="pro-negative">FAILED TO LOAD LOCAL STOCK DATABASE</td></tr>`;
        });
        console.error(err);
    });
})();
