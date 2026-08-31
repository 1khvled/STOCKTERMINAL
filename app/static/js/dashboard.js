        const TICKER = window.location.pathname.split('/').filter(Boolean).pop().toUpperCase();

        let STOCK_DATA = null;



        function safeDisplay(v, fallback="N/A"){ return (v===null||v===undefined||v===""||v==="undefined"||String(v).toLowerCase()==="nan")?fallback:String(v); }

        function setText(id, value) {

            const el = document.getElementById(id);

            if (el) el.innerText = value;

        }



        function cleanText(value, fallback = '--') {

            if (value === null || value === undefined) return fallback;

            let text = String(value).trim();

            if (!text) return fallback;

            // remove mojibake/control artifacts, keep readable unicode

            text = text.replace(/[\uFFFD]/g, "");

            return text || fallback;

        }



        function summarizeRisk(an) {

            const risk = an.risk_assessment || {};

            const flaw = cleanText(an.fatal_flaw_probability || risk.risk_reward_ratio || 'Balanced', 'Balanced');

            if (flaw.includes('HIGH') || flaw.includes('UNFAVORABLE')) return 'High';

            if (flaw.includes('LOW') || flaw.includes('FAVORABLE')) return 'Low';

            return 'Balanced';

        }



        function populateHero(currPrice, weightedFair, priceChange1d, analystCount, an) {

            const company = STOCK_DATA.company_name || TICKER;

            const verdict = cleanText(an.verdict || 'HOLD', 'HOLD');

            const confidence = parseFloat(an.verdict_confidence || 0);

            const upsidePct = currPrice > 0 && weightedFair > 0 ? ((weightedFair - currPrice) / currPrice) * 100 : 0;

            const riskLevel = summarizeRisk(an);

            const executive = cleanText(an.executive_summary || 'Snapshot loading.', 'Snapshot loading.');

            const shortSummary = executive.split('.').slice(0, 2).join('.').trim();



            setText('hero-company', company);

            setText('hero-summary', shortSummary || 'Pulling together the headline story, current valuation, and biggest watch-outs.');

            setText('hero-verdict', verdict);

            setText('hero-confidence', `${Number.isFinite(confidence) ? confidence : 0}%`);

            setText('hero-target-gap', `${upsidePct >= 0 ? '+' : ''}${upsidePct.toFixed(1)}%`);

            setText('hero-price', Number.isFinite(currPrice) ? `$${currPrice.toFixed(2)}` : '--');

            setText('hero-fair', Number.isFinite(weightedFair) ? `$${weightedFair.toFixed(2)}` : '--');

            setText('hero-risk', riskLevel);

            setText('hero-fair-note', analystCount ? `${analystCount} analyst views in the mix` : 'Model midpoint');

            setText('hero-price-move', Number.isFinite(priceChange1d) ? `${priceChange1d >= 0 ? '+' : ''}${priceChange1d.toFixed(2)}% on the day` : 'Daily move not available');

            setText('hero-risk-note', riskLevel === 'High' ? 'More caution needed here' : riskLevel === 'Low' ? 'Risk profile looks calmer' : 'Mixed picture right now');

        }



        function num(value) {

            const n = parseFloat(value);

            return Number.isFinite(n) ? n : null;

        }



        function pct(value) {

            const n = num(value);

            if (n === null) return '--';

            const v = Math.abs(n) <= 1 ? n * 100 : n;

            return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

        }



        function money(value) {

            const n = num(value);

            return n === null ? '--' : `$${n.toFixed(2)}`;

        }



        function firstRisk(an) {

            const risks = (((an || {}).risk_assessment || {}).risk_factors || []);

            if (Array.isArray(risks) && risks.length) {

                const r = risks[0];

                return cleanText(typeof r === 'string' ? r : (r.risk || r.impact || 'Risk captured'));

            }

            return cleanText(an.red_team_audit || 'No major red flag captured yet.');

        }



        function buildDiagnosis(m, an, currPrice, fairValue) {

            const verdict = cleanText(an.verdict || 'HOLD', 'HOLD').toUpperCase();

            const growth = num(m.revenueGrowth_pct ?? m.revenueGrowth);

            const debt = num(m.totalDebt);

            const cash = num(m.totalCash);

            const fcf = num(m.freeCashflow);

            const upside = currPrice && fairValue ? ((fairValue - currPrice) / currPrice) * 100 : 0;

            let title = 'Balanced stock under review';

            let severity = summarizeRisk(an);

            let symptom = 'Mixed valuation and quality signals';

            let followup = 'Recheck after the next earnings update';



            if (verdict.includes('SELL') || upside < -15) {

                title = 'Overvalued or weakening setup';

                severity = severity === 'Low' ? 'Moderate' : severity;

                symptom = `Price sits ${Math.abs(upside).toFixed(1)}% above fair value`;

            } else if (verdict.includes('BUY') || upside > 15) {

                title = 'Possible undervalued opportunity';

                symptom = `Fair value suggests ${upside.toFixed(1)}% upside`;

            }



            if (growth !== null && growth < 0) symptom = `Revenue growth is negative (${pct(growth)})`;

            if (debt && cash !== null && debt > cash * 2) severity = 'High';

            if (fcf !== null && fcf < 0) severity = 'High';



            return { title, severity, symptom, redflag: firstRisk(an), followup };

        }



        function buildWhyList(m, an, currPrice, fairValue) {

            const items = [];

            const upside = currPrice && fairValue ? ((fairValue - currPrice) / currPrice) * 100 : null;

            if (upside !== null) items.push(`Price is ${money(currPrice)} versus fair value around ${money(fairValue)} (${upside >= 0 ? '+' : ''}${upside.toFixed(1)}%).`);

            if (m.revenueGrowth_pct !== undefined || m.revenueGrowth !== undefined) items.push(`Revenue growth signal: ${pct(m.revenueGrowth_pct ?? m.revenueGrowth)}.`);

            if (m.totalDebt || m.totalCash) items.push(`Balance sheet: debt ${m.totalDebt ? money(m.totalDebt) : '--'} versus cash ${m.totalCash ? money(m.totalCash) : '--'}.`);

            if (m.freeCashflow !== undefined) items.push(`Free cash flow: ${money(m.freeCashflow)}.`);

            items.push(`AI call: ${cleanText(an.verdict || 'HOLD')} with ${cleanText(an.verdict_confidence || '--')}% confidence.`);

            return items.slice(0, 5);

        }



        function dataQualityGrade(data) {

            const availability = (((data || {}).source_metadata || {}).availability || {});

            let score = 0;

            ['annual_financials', 'quarterly_financials', 'quarterly_balance_sheet', 'quarterly_cashflow', 'history_1y_rows', 'news_items', 'peer_count'].forEach(k => {

                if (availability[k]) score += 1;

            });

            if (score >= 6) return 'High';

            if (score >= 3) return 'Medium';

            return 'Low';

        }



        function earningsWatchText(data, an) {

            const m = data.key_metrics || {};

            const dates = ((((data.source_metadata || {}).freshness || {}).quarterly_income_statement_dates) || []);

            const needs = [];

            if (m.revenueGrowth_pct !== undefined || m.revenueGrowth !== undefined) needs.push(`revenue growth staying better than ${pct(m.revenueGrowth_pct ?? m.revenueGrowth)}`);

            if (m.operatingMargins_pct !== undefined || m.operatingMargins !== undefined) needs.push(`operating margin holding near ${pct(m.operatingMargins_pct ?? m.operatingMargins)}`);

            if (m.freeCashflow !== undefined) needs.push(`free cash flow not deteriorating from ${money(m.freeCashflow)}`);

            if (!needs.length) needs.push('revenue, margin, guidance, and free cash flow');

            const last = dates[0] ? `Last statement seen: ${dates[0]}. ` : '';

            return `${last}Next check: ${needs.slice(0, 3).join(', ')}.`;

        }



        function buildMemory(data, currPrice, fairValue, an) {

            const key = `stocker_memory_${TICKER}`;

            const previous = JSON.parse(localStorage.getItem(key) || 'null');

            const current = {

                date: new Date().toISOString(),

                price: currPrice,

                fair: fairValue,

                verdict: an.verdict || 'HOLD'

            };

            localStorage.setItem(key, JSON.stringify(current));

            if (!previous) return 'First snapshot saved. Next visit, I will compare what changed.';

            const priceMove = previous.price && currPrice ? ((currPrice - previous.price) / previous.price) * 100 : 0;

            const verdictChanged = previous.verdict !== current.verdict ? ` Verdict changed from ${previous.verdict} to ${current.verdict}.` : ' Verdict unchanged.';

            return `Last snapshot: ${new Date(previous.date).toLocaleDateString()}. Price moved ${priceMove >= 0 ? '+' : ''}${priceMove.toFixed(1)}%. ${verdictChanged}`;

        }



        function setupPortfolioMode(currPrice, an) {

            const key = `stocker_portfolio_${TICKER}`;

            const sharesEl = document.getElementById('portfolio-shares');

            const entryEl = document.getElementById('portfolio-entry');

            const saveBtn = document.getElementById('portfolio-save');

            const note = document.getElementById('portfolio-note');

            const saved = JSON.parse(localStorage.getItem(key) || '{}');

            if (sharesEl && saved.shares) sharesEl.value = saved.shares;

            if (entryEl && saved.entry) entryEl.value = saved.entry;



            const render = () => {

                const shares = num(sharesEl && sharesEl.value);

                const entry = num(entryEl && entryEl.value);

                if (!shares || !entry || !currPrice) {

                    if (note) note.innerText = 'Add your position to see simple risk notes.';

                    return;

                }

                const pnl = (currPrice - entry) * shares;

                const pnlPct = ((currPrice - entry) / entry) * 100;

                const risk = summarizeRisk(an);

                if (note) note.innerText = `${shares} shares. P/L: ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%). Risk read: ${risk}.`;

            };

            if (saveBtn) saveBtn.onclick = () => {

                localStorage.setItem(key, JSON.stringify({ shares: sharesEl.value, entry: entryEl.value }));

                render();

            };

            render();

        }



        function populateDecisionCockpit(currPrice, fairValue, an) {

            const m = STOCK_DATA.key_metrics || {};

            const diagnosis = buildDiagnosis(m, an, currPrice, fairValue);

            setText('dx-title', diagnosis.title);

            setText('dx-summary', cleanText(an.executive_summary || 'A compact diagnosis from valuation, quality, and risk signals.'));

            setText('dx-severity', diagnosis.severity);

            setText('dx-symptom', diagnosis.symptom);

            setText('dx-redflag', diagnosis.redflag);

            setText('dx-followup', diagnosis.followup);



            const why = document.getElementById('why-list');

            if (why) why.innerHTML = buildWhyList(m, an, currPrice, fairValue).map(item => `<li>${formatNarrativeText(item)}</li>`).join('');



            setText('grade-data', dataQualityGrade(STOCK_DATA));

            setText('grade-ai', `${cleanText(an.verdict_confidence || '--')}%`);

            setText('grade-risk', summarizeRisk(an));

            setText('earnings-watch', earningsWatchText(STOCK_DATA, an));

            setText('debate-bull', cleanText(an.bull_case_narrative || an.investment_thesis || 'Bull case not captured.'));

            setText('debate-bear', cleanText(an.bear_case_narrative || firstRisk(an)));

            setText('debate-judge', `Judge: ${cleanText(an.verdict || 'HOLD')} because ${cleanText(an.verdict_reasoning || 'the evidence is mixed.').split('.').slice(0, 1).join('.')}.`);

            setText('memory-note', buildMemory(STOCK_DATA, currPrice, fairValue, an));

            setupPortfolioMode(currPrice, an);

        }



        // Fetch stock data from local JSON database

        async function fetchStockData() {

            try {

                const res = await fetch(`/api/stock/${TICKER}?t=${new Date().getTime()}`);

                if (!res.ok) throw new Error("Database record not found");

                STOCK_DATA = await res.json();

                

                populateStaticMetrics();

                populateNarratives();

                initTabs();

                initNotionHub();

                initCAPMSliders();

                initDuPontScore();

                initPiotroskiScore();

                initAltmanTable();

                initPeersTable();

                loadStatement('income');

                fetchAndRenderNews();

            } catch (err) {

                console.error("Failed to load stock database record:", err);

                document.body.innerHTML = `<div style="padding: 100px; text-align: center;"><h1>❌ Error Loading Terminal</h1><p>${err.message}</p><a href="/" style="color: #fff; margin-top: 20px; display: inline-block;">Back to Stock Hub</a></div>`;

            }

        }



        function populateStaticMetrics() {

            const m = STOCK_DATA.key_metrics || {};

            const dcf = STOCK_DATA.dcf_data || {};

            const sc = STOCK_DATA.financial_scores || {};

            const an = STOCK_DATA.analysis || {};

            const valAssess = an.valuation_assessment || {};



            // Nav & Header

            const el_stock_name = document.getElementById('stock-name'); if(el_stock_name) el_stock_name.innerText = STOCK_DATA.company_name || TICKER;

            const el_stock_ticker_header = document.getElementById('stock-ticker-header'); if(el_stock_ticker_header) el_stock_ticker_header.innerText = `${TICKER} // ${STOCK_DATA.company_name || 'Personal Ingestion'}`;

            const el_stock_sector = document.getElementById('stock-sector'); if(el_stock_sector) el_stock_sector.innerText = m.sector || "—";

            

            // Verdict Badge

            const verd = (an.verdict || "HOLD").toUpperCase();

            const verdBadge = document.getElementById('stock-verdict');

            if (verdBadge) {

                verdBadge.innerText = verd;

                verdBadge.className = 'badge-verdict';

                if (verd.includes("BUY")) verdBadge.classList.add('badge-buy');

                else if (verd.includes("SELL")) verdBadge.classList.add('badge-sell');

                else verdBadge.classList.add('badge-hold');

            }



            // Thematic Verdict Badge

            const tv = (an.thematic_verdict || "HOLD").toUpperCase();

            const tvBadge = document.getElementById('thematic-verdict');

            if (tvBadge) {

                tvBadge.innerText = tv;

                tvBadge.className = 'badge-verdict';

                if (tv.includes("BUY")) tvBadge.classList.add('badge-buy');

                else if (tv.includes("SELL")) tvBadge.classList.add('badge-sell');

                else tvBadge.classList.add('badge-hold');

                tvBadge.style.color = tv.includes("BUY") ? "var(--green)" : tv.includes("SELL") ? "var(--red)" : "var(--yellow)";

            }



            // Confidence Badge

            const conf = an.verdict_confidence || "—";

            const confEl = document.getElementById('stock-confidence');

            if (confEl) {

                confEl.innerText = conf !== "—" ? `${conf}%` : "—";

            }

            const confContainer = document.getElementById('stock-confidence-container');

            const confRing = document.getElementById('stock-confidence-ring');

            const numConf = parseFloat(conf);

            if (confRing && !isNaN(numConf)) {

                confRing.style.strokeDashoffset = 100 - numConf;

                const color = numConf >= 75 ? 'var(--emerald)' : numConf >= 50 ? 'var(--gold)' : 'var(--ruby)';

                confRing.style.stroke = color;

            }

            if (confContainer) {

                confContainer.className = 'narrative-card verdict-banner-dynamic';

                if (!isNaN(numConf)) {

                    if (numConf >= 80) {

                        confContainer.style.borderColor = 'rgba(16, 185, 129, 0.4)';

                        confContainer.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.05)';

                        if (confEl) confEl.style.color = 'var(--emerald)';

                    } else if (numConf >= 60) {

                        confContainer.style.borderColor = 'rgba(245, 158, 11, 0.4)';

                        confContainer.style.boxShadow = '0 0 10px rgba(245, 158, 11, 0.05)';

                        if (confEl) confEl.style.color = 'var(--gold)';

                    } else {

                        confContainer.style.borderColor = 'rgba(239, 68, 68, 0.4)';

                        confContainer.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.05)';

                        if (confEl) confEl.style.color = 'var(--ruby)';

                    }

                } else {

                    confContainer.style.borderColor = 'var(--border)';

                    confContainer.style.boxShadow = 'none';

                    if (confEl) confEl.style.color = 'var(--text-primary)';

                }

            }



            // Strip Stats & Header Quotes

            const currPrice = parseFloat(m.current_price || m.currentPrice || NaN);

            const targetMean = parseFloat(m.targetMeanPrice || currPrice);

            const priceChange1d = parseFloat(m.price_change_1d || NaN);

            const analystCount = m.numberOfAnalystOpinions || "?";

            let weightedFair = parseFloat(valAssess.fair_value_mid || dcf.implied_price || currPrice);



            const el_price_val = document.getElementById('price-val'); if(el_price_val) el_price_val.innerText = !isNaN(currPrice) ? `$${currPrice.toFixed(2)}` : '—';

            const el_header_price = document.getElementById('header-price'); if(el_header_price) el_header_price.innerText = !isNaN(currPrice) ? `$${currPrice.toFixed(2)}` : '—';

            

            const priceChangeEl = document.getElementById('header-price-change');

            if (priceChangeEl) {

                if (!isNaN(priceChange1d)) {

                    priceChangeEl.innerText = `${priceChange1d >= 0 ? '+' : ''}${priceChange1d.toFixed(2)}% today`;

                    priceChangeEl.style.color = priceChange1d >= 0 ? 'var(--emerald)' : 'var(--ruby)';

                } else {

                    priceChangeEl.innerText = 'N/A today';

                    priceChangeEl.style.color = 'var(--text-secondary)';

                }

            }

            

            const el_header_target = document.getElementById('header-target'); if(el_header_target) el_header_target.innerText = !isNaN(targetMean) ? `$${targetMean.toFixed(2)}` : '—';

            const el_header_analyst_count = document.getElementById('header-analyst-count'); if(el_header_analyst_count) el_header_analyst_count.innerText = `${analystCount} Analyst consensus`;

            

            weightedFair = parseFloat(valAssess.fair_value_mid || dcf.implied_price || currPrice);

            populateHero(currPrice, weightedFair, priceChange1d, analystCount, an);

            populateDecisionCockpit(currPrice, weightedFair, an);

            const el_fair_val = document.getElementById('fair-val'); if(el_fair_val) el_fair_val.innerText = !isNaN(weightedFair) ? `$${weightedFair.toFixed(2)}` : '—';

            

            // Color code fair value card based on upside/downside

            const fairValNode = document.getElementById('stat-fair-val');

            const upsideSub = document.getElementById('upside-sub');

            if (currPrice > 0 && weightedFair > 0) {

                const upsidePct = ((weightedFair - currPrice) / currPrice * 100);

                const isUpside = upsidePct >= 0;

                if (el_fair_val) el_fair_val.classList.add(isUpside ? 'val-positive' : 'val-negative');

                if (fairValNode) fairValNode.classList.add(isUpside ? 'accent-positive' : 'accent-negative');

                if (upsideSub) {

                    upsideSub.innerText = `${isUpside ? '▲' : '▼'} ${Math.abs(upsidePct).toFixed(1)}% ${isUpside ? 'upside' : 'downside'}`;

                    upsideSub.style.color = isUpside ? 'var(--signal-positive)' : 'var(--signal-negative)';

                }

            }



            // Price change sub-label with color arrow

            const priceChangeSub = document.getElementById('price-change-sub');

            if (priceChangeSub && priceChange1d !== 0) {

                const arrow = priceChange1d >= 0 ? '▲' : '▼';

                priceChangeSub.innerText = `${arrow} ${Math.abs(priceChange1d).toFixed(2)}% today`;

                priceChangeSub.style.color = priceChange1d >= 0 ? 'var(--signal-positive)' : 'var(--signal-negative)';

            }

            

            const fmtPE = (v) => (v !== undefined && v !== '—') ? Number(v).toFixed(2) : '—';

            const el_pe_val = document.getElementById('pe-val'); if(el_pe_val) el_pe_val.innerHTML = `${fmtPE(m.trailingPE)} <span style=\"color:#c7c7cc;\">/</span> ${fmtPE(m.forwardPE)}`;

            const el_eps_val = document.getElementById('eps-val'); if(el_eps_val) el_eps_val.innerText = `$${(m.trailingEps || 0).toFixed(2)} / $${(m.forwardEps || 0).toFixed(2)}`;



            // Solvency Summary

            const altman = parseFloat(sc.altman_z || 0);

            const altmanEl = document.getElementById('altman-val');

            if (altmanEl) altmanEl.innerText = altman.toFixed(2);

            const piotroskiEl = document.getElementById('piotroski-val');

            if (piotroskiEl) piotroskiEl.innerText = `${sc.piotroski_f || 0}/9`;

            

            // Sub-valuation grids

            const el_rel_dcf_target = document.getElementById('rel-dcf-target'); if(el_rel_dcf_target) el_rel_dcf_target.innerText = `$${(dcf.implied_price || currPrice).toFixed(2)}`;

            const el_rel_analyst_target = document.getElementById('rel-analyst-target'); if(el_rel_analyst_target) el_rel_analyst_target.innerText = `$${(m.targetMeanPrice || currPrice).toFixed(2)}`;

            const el_rel_reconciled_target = document.getElementById('rel-reconciled-target'); if(el_rel_reconciled_target) el_rel_reconciled_target.innerText = `$${weightedFair.toFixed(2)}`;



            // Microstructure

            const el_micro_insider = document.getElementById('micro-insider'); 

            if(el_micro_insider) el_micro_insider.innerText = m.heldPercentInsiders ? (m.heldPercentInsiders * 100).toFixed(2) + '%' : '--';

            const el_micro_inst = document.getElementById('micro-inst'); 

            if(el_micro_inst) el_micro_inst.innerText = m.heldPercentInstitutions ? (m.heldPercentInstitutions * 100).toFixed(2) + '%' : '--';

            const el_micro_short = document.getElementById('micro-short'); 

            if(el_micro_short) el_micro_short.innerText = m.shortPercentOfFloat ? (m.shortPercentOfFloat * 100).toFixed(2) + '%' : '--';

            const el_micro_short_ratio = document.getElementById('micro-short-ratio'); 

            if(el_micro_short_ratio) el_micro_short_ratio.innerText = m.shortRatio ? m.shortRatio.toFixed(2) : '--';

            const el_micro_iv = document.getElementById('micro-iv'); 

            if(el_micro_iv) el_micro_iv.innerText = m.impliedVolatility ? (m.impliedVolatility * 100).toFixed(2) + '%' : '--';



            // Historical Multiples

            const hm = (STOCK_DATA.advanced_models && STOCK_DATA.advanced_models.historical_multiples) || {};

            const el_val_curr_pe = document.getElementById('val-curr-pe');

            if(el_val_curr_pe) el_val_curr_pe.innerText = m.trailingPE ? m.trailingPE.toFixed(2) + 'x' : '--';

            const el_val_avg_pe = document.getElementById('val-avg-pe');

            if(el_val_avg_pe) el_val_avg_pe.innerText = hm.avg_pe_5y ? hm.avg_pe_5y.toFixed(2) + 'x' : '--';

            const el_val_med_pe = document.getElementById('val-med-pe');

            if(el_val_med_pe) el_val_med_pe.innerText = hm.median_pe_5y ? hm.median_pe_5y.toFixed(2) + 'x' : '--';

            const el_val_pe_premium = document.getElementById('val-pe-premium');

            if(el_val_pe_premium) {

                if (hm.pe_premium_discount_pct !== undefined) {

                    const isPrem = hm.pe_premium_discount_pct > 0;

                    el_val_pe_premium.innerText = (isPrem ? '+' : '') + hm.pe_premium_discount_pct.toFixed(2) + '%';

                    el_val_pe_premium.style.color = isPrem ? 'var(--signal-negative)' : 'var(--signal-positive)';

                } else {

                    el_val_pe_premium.innerText = '--';

                }

            }

        }



        function formatNarrativeText(text) {

            if (!text || text === "—") return "—";

            

            // Basic sanitization/escape to prevent raw HTML execution

            let sanitized = text

                .replace(/&/g, "&amp;")

                .replace(/</g, "&lt;")

                .replace(/>/g, "&gt;");

            

            // Format bold text (**bold**)

            sanitized = sanitized.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

            

            // Split into paragraphs/bullets

            const lines = sanitized.split(/\n+/);

            let resultHtml = "";

            let inList = false;

            

            lines.forEach((line) => {

                const trimmed = line.trim();

                if (!trimmed) return;

                

                // Bullet points: starts with "-", "*", or "•"

                if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {

                    if (!inList) {

                        resultHtml += '<ul class="narrative-ul" style="margin-left: 20px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 6px; list-style-type: disc;">';

                        inList = true;

                    }

                    const content = trimmed.substring(2);

                    resultHtml += `<li>${content}</li>`;

                } else {

                    if (inList) {

                        resultHtml += '</ul>';

                        inList = false;

                    }

                    // Paragraph: first sentence gets bold as lede

                    const sentences = trimmed.split(/(\. |\? |\! )/);

                    if (sentences.length > 1) {

                        const lede = sentences[0] + (sentences[1] || "");

                        const rest = sentences.slice(2).join("");

                        resultHtml += `<p style="margin-bottom: 12px; line-height: 1.65;"><strong class="lede-text" style="color: var(--text-primary);">${lede}</strong>${rest}</p>`;

                    } else {

                        resultHtml += `<p style="margin-bottom: 12px; line-height: 1.65;">${trimmed}</p>`;

                    }

                }

            });

            

            if (inList) {

                resultHtml += '</ul>';

            }

            

            return resultHtml;

        }



        function safeNarrative(id, text, placeholder = "No data captured in this analysis run.") {

            const el = document.getElementById(id);

            if (!el) return;

            el.classList.remove('skeleton');

            if (!text || text === "—" || text.trim() === "") {

                el.innerHTML = `<p style="color:var(--text-muted); font-style:italic;">${placeholder}</p>`;

            } else {

                el.innerHTML = formatNarrativeText(text);

            }

        }



        function populateNarratives() {

            const an = STOCK_DATA.analysis || {};

            const fund = an.fundamental_analysis || {};

            const mac = an.macro_analysis || {};

            const sent = an.sentiment_analysis || {};

            

            // Step 1: Verdict & Thesis

            safeNarrative('executive-summary', an.executive_summary, 'No executive summary generated.');

            safeNarrative('verdict-reasoning', an.verdict_reasoning, 'No verdict reasoning generated.');

            safeNarrative('sizing-strategy', an.position_sizing, 'No position sizing strategy generated.');



            // Step 2: SWOT Analysis

            const swot = an.swot_analysis || {};

            const populateList = (id, items) => {

                const el = document.getElementById(id);

                if (!el) return;

                if (!items || items.length === 0) {

                    el.innerHTML = '<li style="color: var(--text-muted); list-style: none;">No data points identified.</li>';

                } else {

                    el.innerHTML = items.map(item => `<li style="margin-bottom: 6px;">${item}</li>`).join('');

                }

            };

            populateList('swot-strengths', swot.strengths);

            populateList('swot-weaknesses', swot.weaknesses);

            populateList('swot-opportunities', swot.opportunities);

            populateList('swot-threats', swot.threats);



            // Step 3: Fundamentals

            safeNarrative('f-revenue', fund.revenue_quality, 'No revenue quality analysis captured.');

            safeNarrative('f-profit', fund.profitability, 'No profitability analysis captured.');

            safeNarrative('f-earnings', fund.earnings_power, 'No earnings power analysis captured.');

            safeNarrative('f-balance', fund.balance_sheet, 'No balance sheet health analysis captured.');

            safeNarrative('f-moat', fund.competitive_moat, 'No moat/competitive analysis captured.');



            // Step 4: Macro & Sentiment

            safeNarrative('m-macro', mac.macro_environment, 'No macro environment data captured in this analysis run.');

            safeNarrative('m-sector', mac.sector_outlook, 'No sector outlook data captured in this analysis run.');

            safeNarrative('s-analysts', sent.analyst_sentiment, 'No analyst sentiment captured in this analysis run.');

            safeNarrative('s-institution', sent.institutional_positioning, 'No institutional positioning captured in this analysis run.');

            safeNarrative('s-news', sent.news_sentiment, 'No recent news sentiment captured in this analysis run.');



            // Section 5: Catalysts & Risks list (Intelligence Alerts) and CRO risk assessments

            const catList = document.getElementById('catalysts-list');

            if (catList) {

                catList.innerHTML = "";

                (an.catalysts || []).forEach(cat => {

                    const impact = cat.impact || "UNKNOWN";

                    const impactClass = impact.toUpperCase().includes('POS') ? 'badge-bull' : impact.toUpperCase().includes('NEG') ? 'badge-bear' : 'badge-cat';

                    catList.innerHTML += `

                        <div class="intel-alert alert-catalyst">

                            <div class="intel-header">

                                <span class="intel-title">${cat.catalyst || '—'}</span>

                                <span class="intel-badge badge-cat">${cat.timeline || '—'}</span>

                            </div>

                            <div class="intel-body">

                                <span class="intel-desc">Projected Impact Vector</span>

                                <span class="intel-badge ${impactClass}">${impact}</span>

                            </div>

                        </div>

                    `;

                });

            }



            const rkList = document.getElementById('risks-list');

            const riskObj = an.risk_assessment || {};

            if (rkList) {

                rkList.innerHTML = "";

                (riskObj.risk_factors || []).forEach(rk => {

                    const severity = rk.severity || "LOW";

                    const alertClass = severity === 'HIGH' ? 'alert-high' : severity === 'MEDIUM' ? 'alert-medium' : 'alert-low';

                    const badgeClass = severity === 'HIGH' ? 'badge-severe' : severity === 'MEDIUM' ? 'badge-warn' : 'badge-low';

                    

                    rkList.innerHTML += `

                        <div class="intel-alert ${alertClass}">

                            <div class="intel-header">

                                <span class="intel-title">${rk.risk || '—'}</span>

                                <span class="intel-badge ${badgeClass}">${severity} Threat</span>

                            </div>

                            <div class="intel-body">

                                <span class="intel-desc">${rk.impact || '—'}</span>

                                <span class="intel-prob">Prob: ${rk.probability || '—'}</span>

                            </div>

                        </div>

                    `;

                });

            }



            // Populate CRO Vitals Strip and additional outlook text

            const el_rr_profile = document.getElementById('risks-rr-profile');

            if (el_rr_profile) {

                el_rr_profile.innerText = riskObj.risk_reward_ratio || '—';

                el_rr_profile.style.color = (riskObj.risk_reward_ratio || '').toUpperCase().includes('UNFAVOR') ? 'var(--signal-red)' : '#ffffff';

            }



            const el_flaw_prob = document.getElementById('risks-flaw-prob');

            if (el_flaw_prob) {

                const prob = an.fatal_flaw_probability || 'LOW';

                el_flaw_prob.innerText = prob;

                const flawCard = document.getElementById('risks-flaw-card');

                if (flawCard) {

                    if (prob.toUpperCase() === 'HIGH') {

                        flawCard.style.borderLeft = '2px solid var(--signal-red)';

                        el_flaw_prob.style.color = 'var(--signal-red)';

                    } else {

                        flawCard.style.borderLeft = '2px solid var(--border-strong)';

                        el_flaw_prob.style.color = '#ffffff';

                    }

                }

            }



            const el_cro_verdict = document.getElementById('risks-cro-verdict');

            if (el_cro_verdict) {

                const croVer = an.adjusted_verdict || 'MAINTAIN';

                el_cro_verdict.innerText = croVer;

                const croCard = document.getElementById('risks-cro-card');

                if (croCard) {

                    if (croVer.toUpperCase().includes('DOWNGRADE') || croVer.toUpperCase().includes('SELL')) {

                        croCard.style.borderLeft = '2px solid var(--signal-red)';

                        el_cro_verdict.style.color = 'var(--signal-red)';

                    } else {

                        croCard.style.borderLeft = '2px solid var(--border-strong)';

                        el_cro_verdict.style.color = '#ffffff';

                    }

                }

            }



            const el_short_term = document.getElementById('risks-short-term-outlook');

            if (el_short_term) el_short_term.innerHTML = formatNarrativeText(an.short_term_outlook || 'No short-term tactical directional outlook generated by PM.');



            const el_long_term = document.getElementById('risks-long-term-outlook');

            if (el_long_term) el_long_term.innerHTML = formatNarrativeText(an.long_term_outlook || 'No long-term secular growth/threat thesis generated by PM.');



            const el_red_team = document.getElementById('risks-red-team-audit');

            if (el_red_team) {

                const audit = an.red_team_audit || '—';

                el_red_team.innerHTML = formatNarrativeText(audit);

                const redTeamCard = document.getElementById('risks-red-team-card');

                if (redTeamCard) {

                    if (audit !== '—' && audit.toUpperCase() !== 'NONE') {

                        redTeamCard.style.borderLeft = '2px solid var(--signal-red)';

                    } else {

                        redTeamCard.style.borderLeft = '1px solid var(--border)';

                    }

                }

            }



            const el_worst_case = document.getElementById('risks-worst-case');

            if (el_worst_case) {

                const scenario = riskObj.worst_case_scenario || 'No worst-case multiple contraction scenario modeled.';

                const bearTarget = an.bear_case_target ? `$${an.bear_case_target}` : '—';

                el_worst_case.innerHTML = `${formatNarrativeText(scenario)}<br><br><strong style="font-family:var(--font-mono); color:var(--signal-red);">Projected Bear Target: ${bearTarget}</strong>`;

            }

        }



        function initTabs() {

            const tabBtns = document.querySelectorAll('.tab-btn');

            const tabPanels = document.querySelectorAll('.tab-panel');



            tabBtns.forEach(btn => {

                btn.addEventListener('click', () => {

                    tabBtns.forEach(b => b.classList.remove('active'));

                    tabPanels.forEach(p => p.classList.remove('active'));



                    btn.classList.add('active');

                    const targetId = btn.getAttribute('data-tab');

                    if (targetId) {

                        const targetPanel = document.getElementById(targetId);

                        if (targetPanel) targetPanel.classList.add('active');

                        if (targetId === 'tab-charts') {

                            loadChartsTab();

                        }

                    }

                });

            });

        }



        function initNotionHub() {

            const notionData = STOCK_DATA.notion_data;

            const subNav = document.getElementById('notion-sub-nav');

            const contentArea = document.getElementById('notion-content-area');

            const notionNavBtn = document.getElementById('notion-nav-btn');



            if (!notionData || !notionData.subpages || Object.keys(notionData.subpages).length === 0) {

                if (notionNavBtn) notionNavBtn.style.display = "none";

                const notConfigured = document.getElementById('notion-not-configured');

                if (notConfigured) notConfigured.style.display = 'block';

                return;

            }

            

            const notConfigured = document.getElementById('notion-not-configured');

            if (notConfigured) notConfigured.style.display = 'none';



            notionNavBtn.style.display = "block";

            subNav.innerHTML = "";

            const subpages = notionData.subpages;

            

            let first = true;

            for (const [key, page] of Object.entries(subpages)) {

                const activeClass = first ? 'active' : '';

                subNav.innerHTML += `<button class="sub-tab-btn ${activeClass}" data-key="${key}">${page.title}</button>`;

                if (first) {

                    contentArea.innerHTML = page.html || "<p>Empty page contents.</p>";

                    first = false;

                }

            }



            const subBtns = document.querySelectorAll('.sub-tab-btn');

            subBtns.forEach(btn => {

                btn.addEventListener('click', () => {

                    subBtns.forEach(b => b.classList.remove('active'));

                    btn.classList.add('active');

                    const key = btn.getAttribute('data-key');

                    contentArea.innerHTML = subpages[key].html || "<p>Empty page.</p>";

                });

            });

        }



        // Advanced CAPM Cost of Equity sliders

        function initCAPMSliders() {

            const dcf = STOCK_DATA.dcf_data || {};

            const m = STOCK_DATA.key_metrics || {};



            const rfSlider = document.getElementById('rf-slider');

            const betaSlider = document.getElementById('beta-slider');

            const erpSlider = document.getElementById('erp-slider');

            

            const growth15Slider = document.getElementById('growth15-slider');

            const growth610Slider = document.getElementById('growth610-slider');

            const terminalSlider = document.getElementById('terminal-slider');



            const rfVal = document.getElementById('rf-val');

            const betaVal = document.getElementById('beta-val');

            const erpVal = document.getElementById('erp-val');

            

            const growth15Val = document.getElementById('growth15-val');

            const growth610Val = document.getElementById('growth610-val');

            const terminalVal = document.getElementById('terminal-val');



            if (!rfSlider || !betaSlider || !erpSlider || !growth15Slider || !growth610Slider || !terminalSlider) return;



            // Default Values from yfinance key_metrics

            betaSlider.value = parseFloat(m.beta || 1.10);

            rfSlider.value = 4.2; // Standard 10Y US Treasury Yield default

            erpSlider.value = 5.5; // Standard equity risk premium



            growth15Slider.value = dcf.growth_1_5_used || 15.0;

            growth610Slider.value = dcf.growth_6_10_used || 10.0;

            terminalSlider.value = dcf.terminal_growth || 2.5;



            const updateDisplays = () => {

                const rf = parseFloat(rfSlider.value);

                const beta = parseFloat(betaSlider.value);

                const erp = parseFloat(erpSlider.value);



                rfVal.innerText = `${rf.toFixed(1)}%`;

                betaVal.innerText = `${beta.toFixed(2)}`;

                erpVal.innerText = `${erp.toFixed(1)}%`;



                growth15Val.innerText = `${parseFloat(growth15Slider.value).toFixed(1)}%`;

                growth610Val.innerText = `${parseFloat(growth610Slider.value).toFixed(1)}%`;

                terminalVal.innerText = `${parseFloat(terminalSlider.value).toFixed(1)}%`;



                // Calculate Cost of Equity (CAPM)

                const capmCost = rf + (beta * erp);

                const capmVal = document.getElementById('capm-cost-val');

                const capmCard = document.querySelector('.capm-card');

                

                let costColor = 'var(--gold)';

                if (capmCost <= 8.5) {

                    costColor = 'var(--emerald)';

                    if (capmCard) {

                        capmCard.style.borderColor = 'rgba(16,185,129,0.3)';

                        capmCard.style.boxShadow = '0 0 16px rgba(16,185,129,0.1)';

                        capmCard.style.background = 'linear-gradient(135deg, rgba(16,185,129,0.06), rgba(16,185,129,0.01))';

                    }

                } else if (capmCost > 11.5) {

                    costColor = 'var(--ruby)';

                    if (capmCard) {

                        capmCard.style.borderColor = 'rgba(239,68,68,0.3)';

                        capmCard.style.boxShadow = '0 0 16px rgba(239,68,68,0.1)';

                        capmCard.style.background = 'linear-gradient(135deg, rgba(239,68,68,0.06), rgba(239,68,68,0.01))';

                    }

                } else {

                    costColor = 'var(--gold)';

                    if (capmCard) {

                        capmCard.style.borderColor = 'rgba(245,158,11,0.3)';

                        capmCard.style.boxShadow = '0 0 16px rgba(245,158,11,0.1)';

                        capmCard.style.background = 'linear-gradient(135deg, rgba(245,158,11,0.06), rgba(245,158,11,0.01))';

                    }

                }

                

                capmVal.innerHTML = `Cost of Equity: <span style="color: ${costColor}; font-weight: 800;">${capmCost.toFixed(2)}%</span>`;



                recalculateDCFLocal(capmCost / 100.0);

            };



            [rfSlider, betaSlider, erpSlider, growth15Slider, growth610Slider, terminalSlider].forEach(slider => {

                slider.addEventListener('input', updateDisplays);

            });



            updateDisplays();

        }



        function recalculateDCFLocal(discountRate) {

            const m = STOCK_DATA.key_metrics || {};

            const dcf = STOCK_DATA.dcf_data || {};



            const growth15Slider = document.getElementById('growth15-slider');

            const growth610Slider = document.getElementById('growth610-slider');

            const terminalSlider = document.getElementById('terminal-slider');



            if (!growth15Slider || !growth610Slider || !terminalSlider) return;



            const growth_1_5 = parseFloat(growth15Slider.value) / 100.0;

            const growth_6_10 = parseFloat(growth610Slider.value) / 100.0;

            const terminal_growth = parseFloat(terminalSlider.value) / 100.0;



            const fcf_base = parseFloat(dcf.fcf_base || m.freeCashflow || 0);

            const total_cash = parseFloat(m.totalCash || 0);

            const total_debt = parseFloat(m.totalDebt || 0);

            

            // Resolve shares outstanding

            let shares = parseFloat(m.sharesOutstanding || 0);

            if (!shares || shares <= 1) {

                const mc = parseFloat(m.marketCap || 0);

                const cp = parseFloat(m.current_price || m.currentPrice || 1.0);

                shares = mc > 0 ? (mc / cp) : 1.0;

            }



            // Projections

            let npv = 0;

            let current_fcf = fcf_base;

            for (let i = 1; i <= 10; i++) {

                const gr = i <= 5 ? growth_1_5 : growth_6_10;

                current_fcf *= (1.0 + gr);

                const pv = current_fcf / Math.pow(1.0 + discountRate, i);

                npv += pv;

            }



            const terminal_value = (current_fcf * (1.0 + terminal_growth)) / (discountRate - terminal_growth);

            const terminal_pv = terminal_value / Math.pow(1.0 + discountRate, 10);



            const enterprise_val = npv + terminal_pv;

            const net_debt = total_debt - total_cash;

            const equity_val = enterprise_val - net_debt;

            const implied_price = equity_val / shares;



            // Update Widgets

            const impliedEl = document.getElementById('implied-dcf-val');

            if (impliedEl) impliedEl.innerText = `$${implied_price.toFixed(2)}`;



            const currPrice = parseFloat(m.current_price || m.currentPrice || 1.0);

            const returnPct = ((implied_price - currPrice) / currPrice) * 100.0;

            

            const returnEl = document.getElementById('implied-return-val');

            if (returnEl) {

                returnEl.innerText = `${returnPct >= 0 ? '▲ +' : '▼ '}${returnPct.toFixed(1)}%`;

                returnEl.className = 'widget-return';

                if (returnPct >= 0) returnEl.classList.add('return-positive');

                else returnEl.classList.add('return-negative');

            }

            

            const dcfWidget = document.querySelector('.dcf-widget');

            if (returnPct >= 0) {

                if (dcfWidget) {

                    dcfWidget.style.borderColor = 'rgba(16,185,129,0.3)';

                    dcfWidget.style.boxShadow = '0 0 24px rgba(16,185,129,0.08)';

                    dcfWidget.style.background = 'linear-gradient(180deg, var(--s1) 0%, rgba(16,185,129,0.02) 100%)';

                }

            } else {

                if (dcfWidget) {

                    dcfWidget.style.borderColor = 'rgba(239,68,68,0.3)';

                    dcfWidget.style.boxShadow = '0 0 24px rgba(239,68,68,0.08)';

                    dcfWidget.style.background = 'linear-gradient(180deg, var(--s1) 0%, rgba(239,68,68,0.02) 100%)';

                }

            }



            // Update relative valuation sync

            const el_rel_dcf_target = document.getElementById('rel-dcf-target'); if(el_rel_dcf_target) el_rel_dcf_target.innerText = `$${implied_price.toFixed(2)}`;

        }



        // Solvency DuPont ROE

        function initDuPontScore() {

            const sc = STOCK_DATA.financial_scores || {};

            const dp = sc.dupont || {};



            const updateText = (id, val) => {

                const el = document.getElementById(id);

                if (el) el.innerText = val;

            };



            if (Object.keys(dp).length === 0) {

                updateText('dp-margin', "—");

                updateText('dp-margin-rail', "—");

                updateText('dp-turnover', "—");

                updateText('dp-turnover-rail', "—");

                updateText('dp-leverage', "—");

                updateText('dp-leverage-rail', "—");

                updateText('dp-roe', "—");

                updateText('dp-roe-rail', "—");

                return;

            }



            const netMarginVal = `${parseFloat(dp.net_margin || 0).toFixed(2)}%`;

            const assetTurnoverVal = `${parseFloat(dp.asset_turnover || 0).toFixed(2)}x`;

            const equityMultiplierVal = `${parseFloat(dp.equity_multiplier || 1.0).toFixed(2)}x`;

            const roeVal = `${parseFloat(dp.roe_computed || 0).toFixed(2)}%`;



            updateText('dp-margin', netMarginVal);

            updateText('dp-margin-rail', netMarginVal);

            updateText('dp-turnover', assetTurnoverVal);

            updateText('dp-turnover-rail', assetTurnoverVal);

            updateText('dp-leverage', equityMultiplierVal);

            updateText('dp-leverage-rail', equityMultiplierVal);

            updateText('dp-roe', roeVal);

            updateText('dp-roe-rail', roeVal);

        }



        function initPiotroskiScore() {

            const sc = STOCK_DATA.financial_scores || {};

            const fScore = sc.piotroski_f;

            const el = document.getElementById('piotroski-val');

            const labelEl = document.getElementById('piotroski-label');

            if (!el) return;

            

            if (fScore === undefined || fScore === null) {

                el.innerText = '—';

                return;

            }

            const score = parseInt(fScore);

            el.innerText = `${score}/9`;

            

            if (labelEl) {

                if (score >= 7) {

                    labelEl.innerText = 'STRONG';

                    labelEl.className = 'solvency-zone-label zone-safe';

                } else if (score >= 4) {

                    labelEl.innerText = 'NEUTRAL';

                    labelEl.className = 'solvency-zone-label zone-grey';

                } else {

                    labelEl.innerText = 'WEAK';

                    labelEl.className = 'solvency-zone-label zone-distress';

                }

            }

            

            // Color-code the score element itself

            if (score >= 7) el.style.color = 'var(--signal-positive, #10b981)';

            else if (score >= 4) el.style.color = 'var(--signal-caution, #f59e0b)';

            else el.style.color = 'var(--signal-negative, #ef4444)';

        }



        async function fetchAndRenderNews() {

            const container = document.getElementById('news-feed-container');

            if (!container) return;

            try {

                const res = await fetch(`/api/news/stock/${TICKER}`);

                if (!res.ok) throw new Error("News fetch failed");

                const data = await res.json();

                const newsItems = data.news || [];

                

                if (newsItems.length === 0) {

                    container.innerHTML = `<div style="color: var(--text-muted); font-style: italic; font-size: 0.85rem; text-align: center; padding: 20px;">No recent news found for ${TICKER}.</div>`;

                    return;

                }

                

                container.innerHTML = newsItems.map(item => {

                    const pubDate = item.pubDate ? new Date(item.pubDate).toLocaleDateString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : '';

                    return `

                        <a href="${item.link}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; display: block; padding: 12px 14px; background: var(--bg-header, #0d0e12); border: 1px solid var(--border); border-radius: 4px; transition: border-color 0.15s ease; cursor: pointer;" onmouseover="this.style.borderColor='var(--emerald)'" onmouseout="this.style.borderColor='var(--border)'">

                            <div style="font-size: 0.87rem; font-weight: 600; color: var(--text-primary); line-height: 1.4; margin-bottom: 6px;">${item.title}</div>

                            <div style="display: flex; gap: 12px; align-items: center;">

                                <span style="font-size: 0.72rem; font-family: var(--font-mono, monospace); color: var(--text-muted); background: rgba(255,255,255,0.04); padding: 2px 6px; border-radius: 3px;">${item.publisher}</span>

                                ${pubDate ? `<span style="font-size: 0.72rem; color: var(--text-muted);">${pubDate}</span>` : ''}

                            </div>

                        </a>

                    `;

                }).join('');

            } catch (err) {

                if (container) container.innerHTML = `<div style="color: var(--text-muted); font-style: italic; font-size: 0.85rem; text-align: center; padding: 20px;">Could not load news at this time.</div>`;

            }

        }



        // Altman Z deconstruction factors

        function initAltmanTable() {

            const sc = STOCK_DATA.financial_scores || {};

            const parseNum = (val, def) => {

                const parsed = parseFloat(val);

                return isNaN(parsed) ? def : parsed;

            };

            const altmanStr = sc.altman_z !== undefined ? sc.altman_z : 0;

            const altman = parseNum(altmanStr, 0);



            // Use true backend weights instead of simulated splits

            const x1 = parseNum(sc.altman_x1, altman * 0.15);

            const x2 = parseNum(sc.altman_x2, altman * 0.10);

            const x3 = parseNum(sc.altman_x3, altman * 0.40);

            const x4 = parseNum(sc.altman_x4, altman * 0.20);

            const x5 = parseNum(sc.altman_x5, altman * 0.15);



            const el_altman_x1 = document.getElementById('altman-x1'); if(el_altman_x1) el_altman_x1.innerText = (x1 / 1.2).toFixed(3);

            const wx1El = document.getElementById('altman-wx1');

            if(wx1El) {

                wx1El.innerText = x1.toFixed(3);

                wx1El.style.color = x1 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            }



            const el_altman_x2 = document.getElementById('altman-x2'); if(el_altman_x2) el_altman_x2.innerText = (x2 / 1.4).toFixed(3);

            const wx2El = document.getElementById('altman-wx2');

            if(wx2El) {

                wx2El.innerText = x2.toFixed(3);

                wx2El.style.color = x2 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            }



            const el_altman_x3 = document.getElementById('altman-x3'); if(el_altman_x3) el_altman_x3.innerText = (x3 / 3.3).toFixed(3);

            const wx3El = document.getElementById('altman-wx3');

            if(wx3El) {

                wx3El.innerText = x3.toFixed(3);

                wx3El.style.color = x3 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            }



            const el_altman_x4 = document.getElementById('altman-x4'); if(el_altman_x4) el_altman_x4.innerText = (x4 / 0.6).toFixed(3);

            const wx4El = document.getElementById('altman-wx4');

            if(wx4El) {

                wx4El.innerText = x4.toFixed(3);

                wx4El.style.color = x4 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            }



            const el_altman_x5 = document.getElementById('altman-x5'); if(el_altman_x5) el_altman_x5.innerText = (x5 / 0.999).toFixed(3);

            const wx5El = document.getElementById('altman-wx5');

            if(wx5El) {

                wx5El.innerText = x5.toFixed(3);

                wx5El.style.color = x5 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            }



            const totalScoreEl = document.getElementById('altman-total-score');

            const railScoreEl = document.getElementById('altman-rail-score');

            let badgeHtml = '';

            let zoneLabel = '';

            let zoneClass = '';

            if (altman > 2.99) {

                badgeHtml = `${altman.toFixed(2)} <span style="font-size: 0.72rem; font-weight: 700; color: var(--signal-positive); margin-left: 12px; border: 1px solid var(--signal-positive); padding: 2px 6px;">SAFE</span>`;

                zoneLabel = 'SAFE';

                zoneClass = 'zone-safe';

            } else if (altman >= 1.81) {

                badgeHtml = `${altman.toFixed(2)} <span style="font-size: 0.72rem; font-weight: 700; color: var(--signal-caution); margin-left: 12px; border: 1px solid var(--signal-caution); padding: 2px 6px;">GREY</span>`;

                zoneLabel = 'GREY';

                zoneClass = 'zone-grey';

            } else {

                badgeHtml = `${altman.toFixed(2)} <span style="font-size: 0.72rem; font-weight: 700; color: var(--signal-negative); margin-left: 12px; border: 1px solid var(--signal-negative); padding: 2px 6px;">DISTRESS</span>`;

                zoneLabel = 'DISTRESS';

                zoneClass = 'zone-distress';

            }



            if (totalScoreEl) totalScoreEl.innerHTML = badgeHtml;

            if (railScoreEl) {

                railScoreEl.innerHTML = `

                    <span class="metric-val">${altman.toFixed(2)}</span>

                    <span class="solvency-zone-label ${zoneClass}">${zoneLabel}</span>

                `;

            }

        }



        // Relative Valuation multiples grid

        function initPeersTable() {

            const tbody = document.getElementById('peers-table-body');

            const m = STOCK_DATA.key_metrics || {};

            const peers = STOCK_DATA.peers_data || [];



            if (peers.length === 0) {

                // Show no data instead of hallucinating peers

                tbody.innerHTML = `

                    <tr>

                        <td colspan="5" style="text-align: center; color: var(--text-secondary); font-style: italic;">No comparable peer data available in database.</td>

                    </tr>

                `;

                const el_rel_multiple_target = document.getElementById('rel-multiple-target'); if(el_rel_multiple_target) el_rel_multiple_target.innerText = `N/A`;

                return;

            }



            // Clean render from database peers_data

            tbody.innerHTML = "";

            let sumPE = 0, count = 0;

            

            // Calculate averages first for heatmapping

            peers.forEach(p => { 

                let peVal = parseFloat(p.pe);

                if (!isNaN(peVal) && peVal > 0) { 

                    sumPE += peVal; 

                    count++; 

                } 

            });

            const avgPE = count > 0 ? (sumPE / count) : 25.0;



            // Render Target Company Row first

            const targetPE = m.trailingPE || null;

            const targetFwdPE = m.forwardPE || null;

            const targetPS = m.priceToSalesTrailing12Months || null;

            const targetPB = m.priceToBook || null;

            

            tbody.innerHTML += `

                <tr class="matrix-target-row">

                    <td style="font-weight: 800; color: var(--brand-secondary); text-align: left;">${TICKER} (TARGET)</td>

                    <td style="font-weight: 800; color: var(--brand-secondary);">${targetPE ? targetPE.toFixed(1) + 'x' : '—'}</td>

                    <td style="font-weight: 800; color: var(--brand-secondary);">${targetFwdPE ? targetFwdPE.toFixed(1) + 'x' : '—'}</td>

                    <td style="font-weight: 800; color: var(--brand-secondary);">${targetPS ? targetPS.toFixed(2) + 'x' : '—'}</td>

                    <td style="font-weight: 800; color: var(--brand-secondary);">${targetPB ? targetPB.toFixed(2) + 'x' : '—'}</td>

                </tr>

            `;



            // Render Peers with Heatmapping

            peers.forEach(p => {

                let peVal = parseFloat(p.pe);

                let fwdPeVal = parseFloat(p.fwd_pe);

                let psVal = parseFloat(p.ps);

                let pbVal = parseFloat(p.pb);



                let peClass = "";

                if (!isNaN(peVal) && targetPE) {

                    peClass = peVal > avgPE * 1.2 ? "heat-premium" : peVal < avgPE * 0.8 ? "heat-discount" : "";

                }

                tbody.innerHTML += `

                    <tr>

                        <td style="font-weight: 700; color: #fff; text-align: left;">${p.ticker}</td>

                        <td class="${peClass}">${!isNaN(peVal) ? peVal.toFixed(1) + 'x' : '—'}</td>

                        <td>${!isNaN(fwdPeVal) ? fwdPeVal.toFixed(1) + 'x' : '—'}</td>

                        <td>${!isNaN(psVal) ? psVal.toFixed(2) + 'x' : '—'}</td>

                        <td>${!isNaN(pbVal) ? pbVal.toFixed(2) + 'x' : '—'}</td>

                    </tr>

                `;

            });



            const currPrice = parseFloat(m.current_price || m.currentPrice || 1.0);

            const adv = STOCK_DATA.advanced_models || {};

            const cca = adv.cca || {};

            const impliedPEVal = cca.implied_pe_price || (m.trailingEps || 2.0) * avgPE;

            const el_rel_multiple_target = document.getElementById('rel-multiple-target'); if(el_rel_multiple_target) el_rel_multiple_target.innerText = `$${(impliedPEVal || currPrice * 1.05).toFixed(2)}`;

        }



// --- LIVE QUOTE RAPID POLLING ---

let liveQuoteInterval = null;

function startRapidPolling() {

    if (liveQuoteInterval) clearInterval(liveQuoteInterval);

    const ticker = typeof CURRENT_TICKER !== 'undefined' ? CURRENT_TICKER : null;

    if (!ticker) return;

    

    // Initial fetch

    fetchLiveQuote(ticker);

    

    // Poll every 3.5 seconds

    liveQuoteInterval = setInterval(() => {

        fetchLiveQuote(ticker);

    }, 3500);

}



async function fetchLiveQuote(ticker) {

    try {

        const res = await fetch(`/api/stock/${ticker}/live-quote`);

        if (!res.ok) return;

        const data = await res.json();

        if (data.status === 'success') {

            const price = data.price.toFixed(2);

            const change = data.change.toFixed(2);

            const pct = data.change_pct.toFixed(2);

            const sign = change >= 0 ? '+' : '';

            const colorClass = change >= 0 ? 'text-bull' : 'text-bear';

            

            // Update Header

            const hPrice = document.getElementById('header-price');

            const hChange = document.getElementById('header-price-change');

            if (hPrice) {

                hPrice.innerText = `$${price}`;

                hPrice.style.textShadow = change >= 0 ? '0 0 10px rgba(30,215,96,0.8)' : '0 0 10px rgba(255,75,75,0.8)';

                setTimeout(() => hPrice.style.textShadow = 'none', 500);

            }

            if (hChange) {

                hChange.innerText = `${sign}${pct}% today`;

                hChange.className = `quote-change ${colorClass}`;

            }

            

            // Update Stat Node

            const nPrice = document.getElementById('price-val');

            const nChange = document.getElementById('price-change-sub');

            if (nPrice) nPrice.innerText = `$${price}`;

            if (nChange) {

                nChange.innerText = `${sign}$${Math.abs(change)} (${sign}${pct}%)`;

                nChange.style.color = change >= 0 ? 'var(--terminal-green)' : 'var(--terminal-red)';

            }

        }

    } catch (e) {

        console.error("Live quote fetch failed", e);

    }

}



document.addEventListener('DOMContentLoaded', () => {

    startRapidPolling();

});

        // Render Quarterly Statements dynamically

        function loadStatement(type, btn) {

            document.querySelectorAll('.financial-statement-selector button').forEach(b => b.classList.remove('active'));

            if (btn) {

                btn.classList.add('active');

            } else {

                const buttons = document.querySelectorAll('.financial-statement-selector button');

                if (type === 'income' && buttons[0]) buttons[0].classList.add('active');

                if (type === 'balance' && buttons[1]) buttons[1].classList.add('active');

                if (type === 'cashflow' && buttons[2]) buttons[2].classList.add('active');

            }

            

            let data;

            if (type === 'income') data = STOCK_DATA.q_financials;

            else if (type === 'balance') data = STOCK_DATA.q_balance_sheet;

            else data = STOCK_DATA.q_cashflow;

            

            const root = document.getElementById('statement-table-root');

            if (!root) return;

            root.innerHTML = '';

            

            if (!data || !data.columns || !data.columns.length) {

                root.innerHTML = '<tr><td style="padding: 20px; text-align: center;">No quarterly statement data loaded.</td></tr>';

                return;

            }

            

            let headerHtml = '<tr>';

            data.columns.forEach(c => {

                let displayName = c;

                if (c !== 'Metric') {

                    const d = new Date(c);

                    if (!isNaN(d)) {

                        const q = Math.floor(d.getMonth() / 3) + 1;

                        displayName = `Q${q} '${d.getFullYear().toString().slice(-2)}`;

                    }

                }

                headerHtml += `<th>${displayName}</th>`;

            });

            headerHtml += '</tr>';

            root.innerHTML += headerHtml;

            

            data.rows.forEach(row => {

                const isHeaderItem = ['Total Revenue', 'Net Income', 'Gross Profit', 'Operating Income', 

                                      'Total Assets', 'Total Liabilities', 'Total Liabilities And Equity',

                                      'Cash Flow From Operating Activities', 'Net Income From Continuing Operations'].includes(row.Metric);

                

                let rowHtml = `<tr class="${isHeaderItem ? 'header-row' : ''} interactive-row" onclick="chartFinancialRow('${row.Metric.replace(/'/g, "\\'")}', '${type}')">`;

                data.columns.forEach(col => {

                    const val = row[col];

                    if (col === 'Metric') {

                        rowHtml += `<td class="metric-name">${val}</td>`;

                    } else {

                        let printVal = '-';

                        let cellStyle = '';

                        if (val !== null && val !== undefined) {

                            let sign = val < 0 ? '-' : '';

                            let abs = Math.abs(val);

                            if (abs >= 1e9) printVal = sign + (abs / 1e9).toFixed(2) + 'B';

                            else if (abs >= 1e6) printVal = sign + (abs / 1e6).toFixed(2) + 'M';

                            else printVal = sign + abs.toLocaleString();

                            

                            if (val < 0) {

                                cellStyle = ' style="color: var(--red); font-weight: 500;"';

                            } else if (val > 0 && ['Net Income', 'Operating Income', 'Gross Profit', 'Total Revenue', 'Cash Flow From Operating Activities'].includes(row.Metric)) {

                                cellStyle = ' style="color: var(--emerald); font-weight: 600;"';

                            }

                        }

                        rowHtml += `<td class="val-cell"${cellStyle}>${printVal}</td>`;

                    }

                });

                rowHtml += '</tr>';

                root.innerHTML += rowHtml;

            });

        }

        

        let financialChartInstance = null;

        function chartFinancialRow(metricName, type) {

            let data;

            if (type === 'income') data = STOCK_DATA.q_financials;

            else if (type === 'balance') data = STOCK_DATA.q_balance_sheet;

            else data = STOCK_DATA.q_cashflow;

            

            if (!data) return;

            const row = data.rows.find(r => r.Metric === metricName);

            if (!row) return;

            

            const dateCols = data.columns.filter(c => c !== 'Metric');

            const sortedCols = [...dateCols].sort((a, b) => new Date(a) - new Date(b));

            

            const labels = sortedCols.map(c => {

                const d = new Date(c);

                if (isNaN(d)) return c;

                const q = Math.floor(d.getMonth() / 3) + 1;

                return `Q${q} '${d.getFullYear().toString().slice(-2)}`;

            });

            

            const values = sortedCols.map(c => row[c]);

            

            const placeholder = document.getElementById('chart-placeholder');

            const container = document.getElementById('financial-row-chart-container');

            if (placeholder) placeholder.style.display = 'none';

            if (container) container.style.display = 'block';



            const el_financial_chart_title = document.getElementById('financial-chart-title'); if(el_financial_chart_title) el_financial_chart_title.innerText = `${metricName} — Quarterly Progression`;

            

            const canvas = document.getElementById('financial-row-chart');

            if (!canvas) return;

            const ctx = canvas.getContext('2d');

            if (financialChartInstance) {

                financialChartInstance.destroy();

            }

            

            financialChartInstance = new Chart(ctx, {

                type: 'bar',

                data: {

                    labels: labels,

                    datasets: [{

                        label: metricName,

                        data: values,

                        backgroundColor: 'rgba(63, 97, 236, 0.4)',

                        borderColor: '#3f61ec',

                        borderWidth: 1.5,

                        borderRadius: 4

                    }]

                },

                options: {

                    responsive: true,

                    maintainAspectRatio: false,

                    plugins: {

                        legend: { display: false },

                        tooltip: {

                            callbacks: {

                                label: function(context) {

                                    let v = context.parsed.y;

                                    let sign = v < 0 ? '-' : '';

                                    let abs = Math.abs(v);

                                    if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';

                                    if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';

                                    return sign + '$' + abs.toLocaleString();

                                }

                            }

                        }

                    },

                    scales: {

                        x: { grid: { display: false }, ticks: { color: '#9ca3af' } },

                        y: { 

                            grid: { color: 'rgba(255, 255, 255, 0.05)' }, 

                            ticks: { 

                                color: '#9ca3af',

                                callback: function(value) {

                                    let sign = value < 0 ? '-' : '';

                                    let abs = Math.abs(value);

                                    if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(1) + 'B';

                                    if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(1) + 'M';

                                    return sign + '$' + value.toLocaleString();

                                }

                            }

                        }

                    }

                }

            });

        }



        function closeFinancialChart() {

            const placeholder = document.getElementById('chart-placeholder');

            const container = document.getElementById('financial-row-chart-container');

            if (placeholder) placeholder.style.display = 'flex';

            if (container) container.style.display = 'none';

            if (financialChartInstance) {

                financialChartInstance.destroy();

                financialChartInstance = null;

            }

        }



        // Save CAPM DCF Recalculations back to backend Excel and database

        const saveBtn = document.getElementById('save-btn');

        if (saveBtn) {

            saveBtn.addEventListener('click', async () => {

                saveBtn.disabled = true;

                saveBtn.innerText = "Saving Workbook...";



                // Extract calculated Cost of Equity

                const capmCostValEl = document.getElementById('capm-cost-val');

                const capmText = capmCostValEl ? capmCostValEl.innerText : "";

                const waccMatch = capmText.match(/([\d.]+)%/);

                const wacc = waccMatch ? parseFloat(waccMatch[1]) : 10.0;



                const g15El = document.getElementById('growth15-slider');

                const growth_1_5 = g15El ? parseFloat(g15El.value) : 15.0;

                

                const g610El = document.getElementById('growth610-slider');

                const growth_6_10 = g610El ? parseFloat(g610El.value) : 10.0;

                

                const termEl = document.getElementById('terminal-slider');

                const terminal_growth = termEl ? parseFloat(termEl.value) : 2.5;



            try {

                const res = await fetch(`/api/stock/${TICKER}/recalculate`, {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ wacc, growth_1_5, growth_6_10, terminal_growth })

                });



                if (!res.ok) throw new Error("Recalculation API failed");

                STOCK_DATA = await res.json();

                

                populateStaticMetrics();

                populateNarratives();

                initDuPontScore();

                

                // Show notification badge

                const notify = document.getElementById('notification');

                notify.classList.add('show');

                setTimeout(() => notify.classList.remove('show'), 3000);



            } catch (err) {

                alert(`Error saving recalculations: ${err.message}`);

            } finally {

                saveBtn.disabled = false;

                saveBtn.innerHTML = `

                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>

                    Save Changes to Excel

                `;

            }

            });

        }



        // Initialize Page

        fetchStockData();



        function updateLiveClockAndSession() {

            const now = new Date();

            const utcStr = now.toISOString().slice(11, 19) + " UTC";

            const clockEl = document.getElementById('live-clock');

            if (clockEl) clockEl.innerText = utcStr;

            

            const sessionBadge = document.getElementById('market-session');

            if (!sessionBadge) return;

            

            try {

                const estTimeStr = now.toLocaleString("en-US", {timeZone: "America/New_York", hour12: false});

                const estMatch = estTimeStr.match(/(\d+):(\d+):(\d+)/);

                if (estMatch) {

                    const hours = parseInt(estMatch[1]);

                    const minutes = parseInt(estMatch[2]);

                    const decimalTime = hours + minutes / 60;

                    

                    const estDateObj = new Date(estTimeStr);

                    const day = estDateObj.getDay();

                    

                    if (day === 0 || day === 6) {

                        sessionBadge.className = 'session-badge closed';

                        sessionBadge.innerText = 'MARKET CLOSED';

                    } else {

                        if (decimalTime >= 4 && decimalTime < 9.5) {

                            sessionBadge.className = 'session-badge pre-mkt';

                            sessionBadge.innerText = 'PRE-MARKET';

                        } else if (decimalTime >= 9.5 && decimalTime < 16) {

                            sessionBadge.className = 'session-badge open';

                            sessionBadge.innerText = 'MARKET OPEN';

                        } else if (decimalTime >= 16 && decimalTime < 20) {

                            sessionBadge.className = 'session-badge after-hrs';

                            sessionBadge.innerText = 'AFTER HOURS';

                        } else {

                            sessionBadge.className = 'session-badge closed';

                            sessionBadge.innerText = 'MARKET CLOSED';

                        }

                    }

                }

            } catch (e) {

                const utcHours = now.getUTCHours();

                if (utcHours >= 14 && utcHours < 21) {

                    sessionBadge.className = 'session-badge open';

                    sessionBadge.innerText = 'MARKET OPEN';

                } else {

                    sessionBadge.className = 'session-badge closed';

                    sessionBadge.innerText = 'MARKET CLOSED';

                }

            }

        }

        updateLiveClockAndSession();

        setInterval(updateLiveClockAndSession, 1000);





        window.applyDCFPreset = function(scenario) {

            const presets = {

                bear: { rf: 4.5, beta: 1.50, erp: 5.0, g15: 5.0,  g610: 3.0,  terminal: 1.5 },

                base: { rf: 4.2, beta: 1.00, erp: 4.8, g15: 12.0, g610: 7.0,  terminal: 2.5 },

                bull: { rf: 3.5, beta: 0.80, erp: 4.375, g15: 22.0, g610: 12.0, terminal: 3.5 },

            };

            const p = presets[scenario];

            if (!p) return;

            

            const rfSlider = document.getElementById('rf-slider');

            const betaSlider = document.getElementById('beta-slider');

            const erpSlider = document.getElementById('erp-slider');

            const growth15Slider = document.getElementById('growth15-slider');

            const growth610Slider = document.getElementById('growth610-slider');

            const terminalSlider = document.getElementById('terminal-slider');

            

            if (rfSlider) rfSlider.value = p.rf;

            if (betaSlider) betaSlider.value = p.beta;

            if (erpSlider) erpSlider.value = p.erp;

            if (growth15Slider) growth15Slider.value = p.g15;

            if (growth610Slider) growth610Slider.value = p.g610;

            if (terminalSlider) terminalSlider.value = p.terminal;

            

            if (rfSlider) rfSlider.dispatchEvent(new Event('input'));

        };



        let chartsLoaded = false;

        async function loadChartsTab() {

            if (chartsLoaded) return;

            const container = document.getElementById('charts-container');

            if (!container) return;



            container.innerHTML = `

                <div class="narrative-card" style="width: 100%; max-width: 900px; margin: 0 auto; padding: 20px; background: var(--bg-surface);">

                    <div style="font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 12px; font-weight: 700;">

                        5-Year Interactive Price History

                    </div>

                    <canvas id="historical-price-chart" height="300"></canvas>

                </div>

            `;



            try {

                const res = await fetch(`/api/stock/${TICKER}/history?period=5y`);

                if (!res.ok) throw new Error("Failed to fetch historical data");

                const data = await res.json();

                const history = data.history || [];



                if (history.length === 0) {

                    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 40px; font-style: italic;">

                        📈 No historical data available for this stock.

                    </div>`;

                    return;

                }



                const labels = history.map(row => row.date);

                const prices = history.map(row => row.close);



                const ctx = document.getElementById('historical-price-chart').getContext('2d');

                new Chart(ctx, {

                    type: 'line',

                    data: {

                        labels: labels,

                        datasets: [{

                            label: 'Close Price',

                            data: prices,

                            borderColor: '#3f61ec',

                            backgroundColor: 'rgba(63, 97, 236, 0.1)',

                            borderWidth: 2,

                            fill: true,

                            pointRadius: 0,

                            pointHoverRadius: 4,

                            tension: 0.1

                        }]

                    },

                    options: {

                        responsive: true,

                        interaction: {

                            mode: 'index',

                            intersect: false,

                        },

                        plugins: {

                            legend: { display: false },

                            tooltip: {

                                backgroundColor: 'rgba(0,0,0,0.8)',

                                titleFont: { family: "'Geist Mono', monospace", size: 11 },

                                bodyFont: { family: "'Geist Mono', monospace", size: 12 },

                                padding: 10,

                                displayColors: false,

                                callbacks: {

                                    label: function(context) {

                                        return '$' + context.parsed.y.toFixed(2);

                                    }

                                }

                            }

                        },

                        scales: {

                            x: {

                                grid: { color: '#1a1a1a' },

                                ticks: { color: '#888', maxTicksLimit: 10, font: { family: "'Geist Mono', monospace", size: 9 } }

                            },

                            y: {

                                grid: { color: '#1a1a1a' },

                                ticks: { color: '#888', font: { family: "'Geist Mono', monospace", size: 9 }, callback: function(value) { return '$' + value; } }

                            }

                        }

                    }

                });



                chartsLoaded = true;

            } catch(e) {

                console.error("Error loading charts:", e);

                container.innerHTML = `<div style="text-align: center; color: var(--ruby); padding: 40px;">

                    ❌ Failed to load financial charts: ${e.message}

                </div>`;

            }

        }



