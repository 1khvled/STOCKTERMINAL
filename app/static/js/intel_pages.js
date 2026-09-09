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
        const settled = await Promise.allSettled([fetch(`/api/intel/filings/${ticker}`), fetch(`/api/stock/${ticker}`)]);
        const intel = settled[0].status === "fulfilled" && settled[0].value.ok ? await settled[0].value.json().catch(() => ({})) : { error: "intel fetch failed" };
        const stock = settled[1].status === "fulfilled" && settled[1].value.ok ? await settled[1].value.json().catch(() => ({})) : {};
        if (intel.error && !Object.keys(stock).length) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${esc(intel.error)}</div>`; side.innerHTML = ""; return; }
        const data = intel.error ? {} : intel;
        const sec = stock.sec_data || {};
        const facts = sec.facts_summary || {};
        const fmoney = v => { if (v == null || v.value == null) return "--"; const n = Number(v.value); if (!Number.isFinite(n)) return "--";
            const a = Math.abs(n); const s = a >= 1e9 ? "$" + (n / 1e9).toFixed(2) + "B" : a >= 1e6 ? "$" + (n / 1e6).toFixed(2) + "M" : "$" + n.toLocaleString();
            return `${s} <span style="color:var(--dim);font-size:10px">${esc(v.form || "")} ${esc(v.filed || "")}</span>`; };
        const factRow = (label, key) => facts[key] ? `<div class="ops-row"><span>${label}</span><strong>${fmoney(facts[key])}</strong></div>` : "";
        const formBadge = f => { const u = String(f || "").toUpperCase();
            const c = u === "10-K" ? "pro-positive" : u === "10-Q" ? "" : u === "8-K" ? "pro-negative" : "pro-muted";
            return `<strong class="${c}">${esc(f)}</strong>`; };
        primary.innerHTML = `
            <div class="ops-row"><span>CIK</span><strong>${esc(data.cik || sec.cik || "N/A")}</strong></div>
            <div class="ops-row"><span>Filing Risk</span><strong class="${clsImpact(data.filing_risk)}">${esc(data.filing_risk || "UNKNOWN")}</strong></div>
            <div class="ops-row"><span>Tone</span><strong class="${clsImpact(data.tone)}">${esc(data.tone || "NEUTRAL")}</strong></div>
            <p class="intel-copy">${esc(data.terminal_summary || "SEC filing metadata below. Open any document to read the source filing.")}</p>
            <div class="pro-title">XBRL Company Facts (direct from filings)</div>
            ${factRow("Revenue", "revenue")}
            ${factRow("Net Income", "net_income")}
            ${factRow("Total Assets", "assets")}
            ${factRow("Stockholders Equity", "stockholders_equity")}
            ${factRow("Operating Cash Flow", "operating_cash_flow")}
            ${factRow("CapEx", "capex")}
            ${factRow("Diluted EPS", "eps_diluted")}
            ${factRow("Shares Out.", "shares_outstanding")}
            <div class="pro-title" style="margin-top:12px">Filing Tape (${(data.filings || []).length})</div>
            ${table(["Form", "Filed", "Report Date", "Document"], (data.filings || []).map(f => `
                <tr>
                    <td>${formBadge(f.form)}</td>
                    <td>${esc(f.filed)}</td>
                    <td>${esc(f.report_date)}</td>
                    <td><a href="${esc(f.url)}" target="_blank" rel="noopener" style="color:var(--orange);">OPEN &#8599;</a></td>
                </tr>`))}
            ${(data.watch_forms || []).length ? `<div class="pro-title" style="margin-top:12px">Watch Forms</div>` + data.watch_forms.map(w => `<div class="ops-row"><span>${esc(w.form)} ${esc(w.filed || "")}</span><strong>${esc(w.why_it_matters || "")}</strong></div>`).join("") : ""}
        `;
        side.innerHTML = `<div class="pro-title">Red Flags</div>${(data.red_flags || []).map(x => `<div class="ops-row"><span>FLAG</span><strong>${esc(x)}</strong></div>`).join("") || "<div class='pro-muted'>NO AI FLAGS RETURNED</div>"}`;
    }

    async function runScenarios(ticker) {
        primary.textContent = "BUILDING VALUATION SCENARIO LAB...";
        side.textContent = "STRESSING DCF VARIABLES...";
        let data, live = null;
        try {
            const [a, b] = await Promise.allSettled([
                fetch(`/api/intel/scenarios/${ticker}`).then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }),
                fetch(`/api/stock/${ticker}/live-quote`).then(r => r.json()).catch(() => null)
            ]);
            if (a.status !== "fulfilled") throw new Error("scenarios fetch failed");
            data = a.value;
            live = (b.status === "fulfilled" && b.value && b.value.price) ? b.value : null;
        } catch (e) {
            primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${esc(e.message)}</div>`; side.innerHTML = ""; return;
        }
        if (data.error) { primary.innerHTML = `<div class="pro-negative">FETCH FAILED: ${esc(data.error)}</div>`; side.innerHTML = ""; return; }
        renderLab(ticker, data, live);
    }

    function renderLab(ticker, data, live) {
        const storedPx = Number(data.current_price || 0);
        const px = (live && Number.isFinite(Number(live.price))) ? Number(live.price) : storedPx;
        const pxSrc = (live && Number.isFinite(Number(live.price))) ? "live" : "stored";
        const base = Number(data.base_fair_value || 0);
        const inp = data.dcf_inputs || {};
        const rows = (data.scenarios || []).map(s => {
            const f = Number(s.fair_value || 0);
            const u = px ? ((f - px) / px) : 0;
            return { ...s, fair_value: f, upside: u };
        });
        const lo = Math.min(...rows.map(s => s.fair_value), px || Infinity);
        const hi = Math.max(...rows.map(s => s.fair_value), px || 0);
        const pos = v => (hi > lo ? Math.min(96, Math.max(4, ((v - lo) / (hi - lo)) * 100)) : 50);
        primary.innerHTML = `
            <div class="ops-row"><span>Current Price (${pxSrc})</span><strong>$${px.toFixed(2)}</strong></div>
            <div class="ops-row"><span>Base Fair Value</span><strong>$${base.toFixed(2)}</strong></div>
            <div style="position:relative;height:8px;border-radius:99px;background:#1c1e26;margin:12px 0 4px">
              ${rows.map(s => `<div title="${esc(s.case)} $${s.fair_value.toFixed(2)}" style="position:absolute;top:-3px;width:10px;height:14px;border-radius:3px;background:var(--orange);left:calc(${pos(s.fair_value).toFixed(1)}% - 5px)"></div>`).join("")}
              <div title="price" style="position:absolute;top:-3px;width:3px;height:14px;background:var(--green);left:calc(${pos(px).toFixed(1)}% - 1px)"></div>
              <div title="base fair" style="position:absolute;top:-3px;width:3px;height:14px;background:var(--blue);left:calc(${pos(base).toFixed(1)}% - 1px)"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);font-family:JetBrains Mono,monospace;margin-bottom:12px"><span>$${lo.toFixed(0)}</span><span style="color:var(--green)">| price</span><span style="color:var(--blue)">| base</span><span>$${hi.toFixed(0)}</span></div>
            <p class="intel-copy">${esc(data.ai_readout)}</p>
            ${table(["Case", "Fair Value", "Upside vs " + (pxSrc === "live" ? "live" : "stored"), "Model Note"], rows.map(s => `
                <tr>
                    <td>${esc(s.case)}</td>
                    <td>$${s.fair_value.toFixed(2)}</td>
                    <td class="${s.upside >= 0 ? "pro-positive" : "pro-negative"}">${(s.upside >= 0 ? "+" : "") + (s.upside * 100).toFixed(1)}%</td>
                    <td>${esc(s.note)}</td>
                </tr>`))}
            <div class="pro-title" style="margin-top:12px">Stress your own DCF (posts to model, rescales cases)</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:8px">
              <label style="font-size:11px;color:var(--muted)">WACC %<input id="lab-wacc" type="number" step="0.1" value="${inp.wacc_default || 9}" style="width:100%;margin-top:4px;padding:7px;background:#0a0a0b;border:1px solid var(--border);color:var(--text);border-radius:8px"/></label>
              <label style="font-size:11px;color:var(--muted)">Growth 1-5 %<input id="lab-g15" type="number" step="0.5" value="15" style="width:100%;margin-top:4px;padding:7px;background:#0a0a0b;border:1px solid var(--border);color:var(--text);border-radius:8px"/></label>
              <label style="font-size:11px;color:var(--muted)">Growth 6-10 %<input id="lab-g610" type="number" step="0.5" value="10" style="width:100%;margin-top:4px;padding:7px;background:#0a0a0b;border:1px solid var(--border);color:var(--text);border-radius:8px"/></label>
              <label style="font-size:11px;color:var(--muted)">Terminal %<input id="lab-term" type="number" step="0.1" value="${inp.terminal_default || 2.5}" style="width:100%;margin-top:4px;padding:7px;background:#0a0a0b;border:1px solid var(--border);color:var(--text);border-radius:8px"/></label>
            </div>
            <button class="btn btn-primary" id="lab-recalc" style="margin-top:8px">RECALCULATE BASE</button>
            <span id="lab-msg" style="font-size:11px;color:var(--muted);margin-left:8px"></span>
        `;
        side.innerHTML = `<div class="pro-title">Key Variables</div>${(data.key_variables || []).map(x => `<div class="ops-row"><span>WATCH</span><strong>${esc(x)}</strong></div>`).join("")}`;
        document.getElementById("lab-recalc").onclick = async () => {
            const msg = document.getElementById("lab-msg"); msg.textContent = "recalculating...";
            const body = { wacc: Number(document.getElementById("lab-wacc").value), growth_1_5: Number(document.getElementById("lab-g15").value), growth_6_10: Number(document.getElementById("lab-g610").value), terminal_growth: Number(document.getElementById("lab-term").value) };
            try {
                const r = await fetch(`/api/stock/${ticker}/recalculate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
                const j = await r.json();
                if (!r.ok || j.error) throw new Error(j.error || ("HTTP " + r.status));
                const nb = Number((j.dcf_data || {}).implied_price || 0);
                if (!nb) throw new Error("no implied price returned");
                const ratio = base ? (nb / base) : 1;
                msg.textContent = `base $${base.toFixed(2)} -> $${nb.toFixed(2)} (cases rescaled)`;
                if (window.showToast) showToast("Lab base recalculated", "success");
                const _oldBase = base;
                data.base_fair_value = nb;
                data.scenarios = (data.scenarios || []).map(s => ({ ...s, fair_value: s.fair_value * ratio }));
                renderLab(ticker, data, live);
                const _m2 = document.getElementById("lab-msg");
                if (_m2) _m2.textContent = `base $${_oldBase.toFixed(2)} -> $${nb.toFixed(2)} (cases rescaled)`;
            } catch (e) { msg.textContent = "failed: " + e.message; }
        };
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

})();
