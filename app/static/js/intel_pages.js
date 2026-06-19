(function () {
    const page = document.body.dataset.intelPage;
    if (!page) return;

    const primary = document.getElementById("intel-primary");
    const side = document.getElementById("intel-side");

    const clsImpact = v => {
        const s = String(v || "").toUpperCase();
        if (s.includes("BULL") || s.includes("POSITIVE") || s.includes("LOW")) return "pro-positive";
        if (s.includes("BEAR") || s.includes("NEGATIVE") || s.includes("HIGH")) return "pro-negative";
        return "pro-muted";
    };
    const pct = v => `${(Number(v || 0) * 100).toFixed(1)}%`;
    const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    function table(headers, rows) {
        return `<table class="pro-table"><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="${headers.length}">NO DATA</td></tr>`}</tbody></table>`;
    }

    async function safeFetch(url) {
        try {
            const res = await fetch(url);
            if (!res.ok) return { error: `Server returned status ${res.status}` };
            return await res.json();
        } catch (e) {
            return { error: e.message };
        }
    }

    async function runNewsImpact(ticker) {
        primary.textContent = "RUNNING AI NEWS MATERIALITY ENGINE...";
        side.textContent = "FETCHING HEADLINES / ROUTING MODEL...";
        const data = await safeFetch(`/api/intel/news-impact/${ticker}`);
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${data.error}</div>`; side.innerHTML = ""; return; }
        primary.innerHTML = `
            <div class="ops-row"><span>Overall Impact</span><strong class="${clsImpact(data.overall_impact)}">${esc(data.overall_impact)}</strong></div>
            <div class="ops-row"><span>Impact Score</span><strong>${esc(data.impact_score)}</strong></div>
            <div class="ops-row"><span>Confidence</span><strong>${esc(data.confidence)}%</strong></div>
            <p class="intel-copy">${esc(data.terminal_summary)}</p>
            ${table(["Headline", "Impact", "Materiality", "Affected Assumption"], (data.items || []).map(item => `
                <tr>
                    <td>${esc(item.headline)}</td>
                    <td class="${clsImpact(item.impact)}">${esc(item.impact)}</td>
                    <td class="${clsImpact(item.materiality)}">${esc(item.materiality)}</td>
                    <td>${esc(item.assumption)}</td>
                </tr>`))}
        `;
        side.innerHTML = `<div class="pro-title">Affected Assumptions</div>${(data.affected_assumptions || []).map(x => `<div class="ops-row"><span>MODEL</span><strong>${esc(x)}</strong></div>`).join("")}`;
    }

    async function runFilings(ticker) {
        primary.textContent = "PULLING SEC SUBMISSIONS / REVIEWING FILING TAPE...";
        side.textContent = "SEC EDGAR REQUEST ACTIVE...";
        const data = await safeFetch(`/api/intel/filings/${ticker}`);
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${data.error}</div>`; side.innerHTML = ""; return; }
        primary.innerHTML = `
            <div class="ops-row"><span>CIK</span><strong>${esc(data.cik || "N/A")}</strong></div>
            <div class="ops-row"><span>Filing Risk</span><strong class="${clsImpact(data.filing_risk)}">${esc(data.filing_risk)}</strong></div>
            <div class="ops-row"><span>Tone</span><strong class="${clsImpact(data.tone)}">${esc(data.tone)}</strong></div>
            <p class="intel-copy">${esc(data.terminal_summary)}</p>
            ${table(["Form", "Filed", "Report Date", "Document"], (data.filings || []).map(f => `
                <tr>
                    <td>${esc(f.form)}</td>
                    <td>${esc(f.filed)}</td>
                    <td>${esc(f.report_date)}</td>
                    <td><a href="${esc(f.url)}" target="_blank" style="color:var(--term-orange);">OPEN</a></td>
                </tr>`))}
        `;
        side.innerHTML = `<div class="pro-title">Red Flags</div>${(data.red_flags || []).map(x => `<div class="ops-row"><span>FLAG</span><strong>${esc(x)}</strong></div>`).join("") || "<div class='pro-muted'>NO AI FLAGS RETURNED</div>"}`;
    }

    async function runScenarios(ticker) {
        primary.textContent = "BUILDING VALUATION SCENARIO LAB...";
        side.textContent = "STRESSING DCF VARIABLES...";
        const data = await safeFetch(`/api/intel/scenarios/${ticker}`);
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${data.error}</div>`; side.innerHTML = ""; return; }
        primary.innerHTML = `
            <div class="ops-row"><span>Current Price</span><strong>$${Number(data.current_price || 0).toFixed(2)}</strong></div>
            <div class="ops-row"><span>Base Fair Value</span><strong>$${Number(data.base_fair_value || 0).toFixed(2)}</strong></div>
            <p class="intel-copy">${esc(data.ai_readout)}</p>
            ${table(["Case", "Fair Value", "Upside", "Model Note"], (data.scenarios || []).map(s => `
                <tr>
                    <td>${esc(s.case)}</td>
                    <td>$${Number(s.fair_value || 0).toFixed(2)}</td>
                    <td class="${Number(s.upside || 0) >= 0 ? "pro-positive" : "pro-negative"}">${pct(s.upside)}</td>
                    <td>${esc(s.note)}</td>
                </tr>`))}
        `;
        side.innerHTML = `<div class="pro-title">Key Variables</div>${(data.key_variables || []).map(x => `<div class="ops-row"><span>WATCH</span><strong>${esc(x)}</strong></div>`).join("")}`;
    }

    async function runCommittee(ticker) {
        primary.textContent = "CONVENING AI INVESTMENT COMMITTEE...";
        side.textContent = "BUILDING BULL / BEAR / BASE CASES...";
        const data = await safeFetch(`/api/intel/committee/${ticker}`);
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${data.error}</div>`; side.innerHTML = ""; return; }
        const vote = data.vote || {};
        primary.innerHTML = `
            <div class="ops-row"><span>Chair Verdict</span><strong class="${clsImpact(data.chair_verdict)}">${esc(data.chair_verdict)}</strong></div>
            <div class="ops-row"><span>Vote</span><strong>BUY ${esc(vote.buy || 0)} / HOLD ${esc(vote.hold || 0)} / SELL ${esc(vote.sell || 0)}</strong></div>
            <p class="intel-copy"><strong class="pro-positive">BULL CASE</strong><br>${esc(data.bull_case)}</p>
            <p class="intel-copy"><strong class="pro-negative">BEAR CASE</strong><br>${esc(data.bear_case)}</p>
            <p class="intel-copy"><strong>BASE CASE</strong><br>${esc(data.base_case)}</p>
            <p class="intel-copy"><strong>KEY DEBATE</strong><br>${esc(data.key_debate)}</p>
        `;
        side.innerHTML = `<div class="pro-title">What Changes Mind</div>${(data.what_changes_mind || []).map(x => `<div class="ops-row"><span>EVIDENCE</span><strong>${esc(x)}</strong></div>`).join("")}`;
    }

    async function runRedFlags(ticker) {
        primary.textContent = "SCANNING FINANCIAL RED FLAGS...";
        side.textContent = "CHECKING LEVERAGE / LIQUIDITY / FCF / ACCOUNTING RISK...";
        const data = await safeFetch(`/api/intel/red-flags/${ticker}`);
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${data.error}</div>`; side.innerHTML = ""; return; }
        primary.innerHTML = `
            <div class="ops-row"><span>Risk Level</span><strong class="${clsImpact(data.risk_level)}">${esc(data.risk_level)}</strong></div>
            <div class="ops-row"><span>Active Flags</span><strong>${esc(data.flag_count)}</strong></div>
            <p class="intel-copy">${esc(data.ai_summary)}</p>
            ${table(["Code", "Severity", "Detail"], (data.flags || []).map(f => `
                <tr>
                    <td>${esc(f.code)}</td>
                    <td class="${clsImpact(f.severity)}">${esc(f.severity)}</td>
                    <td>${esc(f.detail)}</td>
                </tr>`))}
        `;
        side.innerHTML = `<div class="pro-title">Mitigants</div>${(data.mitigants || []).map(x => `<div class="ops-row"><span>CHECK</span><strong>${esc(x)}</strong></div>`).join("") || "<div class='pro-muted'>NO MITIGANTS RETURNED</div>"}`;
    }

    async function loadPortfolio() {
        primary.textContent = "LOADING PORTFOLIO COMMAND CENTER...";
        const data = await safeFetch("/api/portfolio");
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${data.error}</div>`; side.innerHTML = ""; return; }
        primary.innerHTML = `
            <div class="ops-row"><span>Total Weight</span><strong>${Number(data.total_weight || 0).toFixed(1)}%</strong></div>
            <div class="ops-row"><span>Weighted Upside</span><strong class="${Number(data.avg_upside || 0) >= 0 ? "pro-positive" : "pro-negative"}">${pct(data.avg_upside)}</strong></div>
            <div class="ops-row"><span>AI Verdict</span><strong>${esc((data.ai || {}).portfolio_verdict)}</strong></div>
            <p class="intel-copy">${esc((data.ai || {}).risk_summary)}</p>
            ${table(["Ticker", "Weight", "Sector", "Verdict", "Upside", "Remove"], (data.positions || []).map(p => `
                <tr>
                    <td><a href="/dashboard/${esc(p.ticker)}" style="color:var(--term-orange);">${esc(p.ticker)}</a></td>
                    <td>${Number(p.weight || 0).toFixed(1)}%</td>
                    <td>${esc(p.sector)}</td>
                    <td>${esc(p.verdict)}</td>
                    <td class="${Number(p.upside || 0) >= 0 ? "pro-positive" : "pro-negative"}">${pct(p.upside)}</td>
                    <td><button class="portfolio-remove" data-ticker="${esc(p.ticker)}">DEL</button></td>
                </tr>`))}
        `;
        side.innerHTML = `<div class="pro-title">Sector Exposure</div>${Object.entries(data.sector_exposure || {}).map(([k, v]) => `<div class="ops-row"><span>${esc(k)}</span><strong>${Number(v).toFixed(1)}%</strong></div>`).join("")}<div class="pro-title" style="margin-top:16px;">AI Actions</div>${((data.ai || {}).actions || []).map(x => `<div class="ops-row"><span>ACTION</span><strong>${esc(x)}</strong></div>`).join("")}`;
        document.querySelectorAll(".portfolio-remove").forEach(btn => btn.onclick = async () => {
            await fetch("/api/portfolio/remove", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ticker: btn.dataset.ticker})});
            loadPortfolio();
        });
    }

    if (page === "news-impact" || page === "filings" || page === "scenario-lab" || page === "committee" || page === "red-flags") {
        const input = document.getElementById("intel-ticker");
        const run = () => {
            const ticker = input.value.trim().toUpperCase();
            if (!ticker) return;
            if (page === "news-impact") runNewsImpact(ticker);
            if (page === "filings") runFilings(ticker);
            if (page === "scenario-lab") runScenarios(ticker);
            if (page === "committee") runCommittee(ticker);
            if (page === "red-flags") runRedFlags(ticker);
        };
        document.getElementById("intel-run").onclick = run;
        input.addEventListener("keydown", e => { if (e.key === "Enter") run(); });
        const preset = new URLSearchParams(window.location.search).get("ticker");
        if (preset) {
            input.value = preset.toUpperCase();
            run();
        }
    }

    if (page === "portfolio") {
        document.getElementById("portfolio-add").onclick = async () => {
            const ticker = document.getElementById("portfolio-ticker").value.trim().toUpperCase();
            const weight = Number(document.getElementById("portfolio-weight").value || 0);
            if (!ticker) return;
            await fetch("/api/portfolio/add", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ticker, weight})});
            loadPortfolio();
        };
        loadPortfolio();
    }
})();
