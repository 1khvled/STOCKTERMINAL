const TICKER = window.location.pathname.split('/').filter(Boolean).pop().toUpperCase();
        let STOCK_DATA = null;

        // Dynamic window resize listener to ensure price chart scales perfectly
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                if (STOCK_DATA && STOCK_DATA.price_history_compact) {
                    drawWeeklyPriceChart();
                }
            }, 150);
        });

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
                initAltmanTable();
                initPeersTable();
                drawWeeklyPriceChart();
                loadStatement('income');
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
            document.getElementById('stock-name').innerText = STOCK_DATA.company_name || TICKER;
            document.getElementById('stock-ticker-header').innerText = `${TICKER} // ${STOCK_DATA.company_name || 'Personal Ingestion'}`;
            document.getElementById('stock-sector').innerText = m.sector || "N/A";
            
            // Verdict Badge
            const verd = (an.verdict || "HOLD").toUpperCase();
            const verdBadge = document.getElementById('stock-verdict');
            verdBadge.innerText = verd;
            verdBadge.className = 'badge-verdict';
            if (verd.includes("BUY")) verdBadge.classList.add('badge-buy');
            else if (verd.includes("SELL")) verdBadge.classList.add('badge-sell');
            else verdBadge.classList.add('badge-hold');

            // Confidence Badge
            const conf = an.verdict_confidence || "N/A";
            const confEl = document.getElementById('stock-confidence');
            if (confEl) {
                confEl.innerText = conf !== "N/A" ? `${conf}%` : "N/A";
            }
            const confContainer = document.getElementById('stock-confidence-container');
            const confBar = document.getElementById('stock-confidence-bar');
            if (confContainer) {
                confContainer.className = 'verdict-banner-dynamic';
                const numConf = parseFloat(conf);
                if (confBar) {
                    confBar.style.width = !isNaN(numConf) ? `${numConf}%` : "0%";
                }
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
            const currPrice = parseFloat(m.current_price || m.currentPrice || 0);
            const targetMean = parseFloat(m.targetMeanPrice || currPrice);
            const priceChange1d = parseFloat(m.price_change_1d || 0);
            const analystCount = m.numberOfAnalystOpinions || "?";

            document.getElementById('price-val').innerText = `$${currPrice.toFixed(2)}`;
            document.getElementById('header-price').innerText = `$${currPrice.toFixed(2)}`;
            
            const priceChangeEl = document.getElementById('header-price-change');
            if (priceChangeEl) {
                priceChangeEl.innerText = `${priceChange1d >= 0 ? '+' : ''}${priceChange1d.toFixed(2)}% today`;
                priceChangeEl.style.color = priceChange1d >= 0 ? 'var(--emerald)' : 'var(--ruby)';
            }
            
            document.getElementById('header-target').innerText = `$${targetMean.toFixed(2)}`;
            document.getElementById('header-analyst-count').innerText = `${analystCount} Analyst consensus`;
            
            const weightedFair = parseFloat(valAssess.fair_value_mid || dcf.implied_price || currPrice);
            document.getElementById('fair-val').innerText = `$${weightedFair.toFixed(2)}`;
            
            document.getElementById('pe-val').innerText = `${m.trailingPE || 'N/A'} / ${m.forwardPE || 'N/A'}`;
            document.getElementById('eps-val').innerText = `$${(m.trailingEps || 0).toFixed(2)} / $${(m.forwardEps || 0).toFixed(2)}`;

            // Solvency Summary
            const altman = parseFloat(sc.altman_z || 0);
            const altmanEl = document.getElementById('altman-val');
            if (altmanEl) altmanEl.innerText = altman.toFixed(2);
            const piotroskiEl = document.getElementById('piotroski-val');
            if (piotroskiEl) piotroskiEl.innerText = `${sc.piotroski_f || 0}/9`;
            
            // Sub-valuation grids
            document.getElementById('rel-dcf-target').innerText = `$${(dcf.implied_price || currPrice).toFixed(2)}`;
            document.getElementById('rel-analyst-target').innerText = `$${(m.targetMeanPrice || currPrice).toFixed(2)}`;
            document.getElementById('rel-reconciled-target').innerText = `$${weightedFair.toFixed(2)}`;
        }

        function formatNarrativeText(text) {
            if (!text || text === "N/A") return "N/A";
            
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

        function populateNarratives() {
            const an = STOCK_DATA.analysis || {};
            const fund = an.fundamental_analysis || {};
            const mac = an.macro_analysis || {};
            const sent = an.sentiment_analysis || {};
            
            // Step 1: Verdict & Thesis
            document.getElementById('executive-summary').innerHTML = formatNarrativeText(an.executive_summary);
            document.getElementById('verdict-reasoning').innerHTML = formatNarrativeText(an.verdict_reasoning);
            document.getElementById('sizing-strategy').innerHTML = formatNarrativeText(an.position_sizing);

            // Step 3: Fundamentals
            document.getElementById('f-revenue').innerHTML = formatNarrativeText(fund.revenue_quality);
            document.getElementById('f-profit').innerHTML = formatNarrativeText(fund.profitability);
            document.getElementById('f-earnings').innerHTML = formatNarrativeText(fund.earnings_power);
            document.getElementById('f-balance').innerHTML = formatNarrativeText(fund.balance_sheet);
            document.getElementById('f-moat').innerHTML = formatNarrativeText(fund.competitive_moat);

            // Step 4: Macro & Sentiment
            document.getElementById('m-macro').innerHTML = formatNarrativeText(mac.macro_environment);
            document.getElementById('m-sector').innerHTML = formatNarrativeText(mac.sector_outlook);
            document.getElementById('s-analysts').innerHTML = formatNarrativeText(sent.analyst_sentiment);
            document.getElementById('s-institution').innerHTML = formatNarrativeText(sent.institutional_positioning);
            document.getElementById('s-news').innerHTML = formatNarrativeText(sent.news_sentiment);

            // Section 5: Catalysts & Risks list
            const catList = document.getElementById('catalysts-list');
            catList.innerHTML = "";
            (an.catalysts || []).forEach(cat => {
                catList.innerHTML += `
                    <div class="flex-item">
                        <div class="flex-item-header">
                            <span class="flex-item-title">${cat.catalyst}</span>
                            <span class="flex-item-badge badge-medium">${cat.timeline}</span>
                        </div>
                        <div class="flex-item-desc">Expected Impact: ${cat.impact}</div>
                    </div>
                `;
            });

            const rkList = document.getElementById('risks-list');
            rkList.innerHTML = "";
            const riskObj = an.risk_assessment || {};
            (riskObj.risk_factors || []).forEach(rk => {
                const sevBadge = rk.severity === 'HIGH' ? 'badge-high' : rk.severity === 'MEDIUM' ? 'badge-medium' : 'badge-low';
                rkList.innerHTML += `
                    <div class="flex-item">
                        <div class="flex-item-header">
                            <span class="flex-item-title">${rk.risk}</span>
                            <span class="flex-item-badge ${sevBadge}">${rk.severity} Severity</span>
                        </div>
                        <div class="flex-item-desc">Probability: ${rk.probability} | ${rk.impact}</div>
                    </div>
                `;
            });
        }

        function initTabs() {
            const tabBtns = document.querySelectorAll('.tab-btn');
            const tabPanels = document.querySelectorAll('.tab-panel');

            tabBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    tabBtns.forEach(b => b.classList.remove('active'));
                    tabPanels.forEach(p => p.classList.remove('active'));

                    btn.classList.add('active');
                    document.getElementById(btn.getAttribute('data-tab')).classList.add('active');
                });
            });
        }

        function initNotionHub() {
            const notionData = STOCK_DATA.notion_data;
            const subNav = document.getElementById('notion-sub-nav');
            const contentArea = document.getElementById('notion-content-area');
            const notionNavBtn = document.getElementById('notion-nav-btn');

            if (!notionData || !notionData.subpages || Object.keys(notionData.subpages).length === 0) {
                notionNavBtn.style.display = "none";
                return;
            }

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

            const growth_1_5 = parseFloat(document.getElementById('growth15-slider').value) / 100.0;
            const growth_6_10 = parseFloat(document.getElementById('growth610-slider').value) / 100.0;
            const terminal_growth = parseFloat(document.getElementById('terminal-slider').value) / 100.0;

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
            impliedEl.innerText = `$${implied_price.toFixed(2)}`;

            const currPrice = parseFloat(m.current_price || m.currentPrice || 1.0);
            const returnPct = ((implied_price - currPrice) / currPrice) * 100.0;
            
            const returnEl = document.getElementById('implied-return-val');
            returnEl.innerText = `${returnPct >= 0 ? '▲ +' : '▼ '}${returnPct.toFixed(1)}%`;
            returnEl.className = 'widget-return';
            
            const dcfWidget = document.querySelector('.dcf-widget');
            if (returnPct >= 0) {
                returnEl.classList.add('return-positive');
                if (dcfWidget) {
                    dcfWidget.style.borderColor = 'rgba(16,185,129,0.3)';
                    dcfWidget.style.boxShadow = '0 0 24px rgba(16,185,129,0.08)';
                    dcfWidget.style.background = 'linear-gradient(180deg, var(--s1) 0%, rgba(16,185,129,0.02) 100%)';
                }
            } else {
                returnEl.classList.add('return-negative');
                if (dcfWidget) {
                    dcfWidget.style.borderColor = 'rgba(239,68,68,0.3)';
                    dcfWidget.style.boxShadow = '0 0 24px rgba(239,68,68,0.08)';
                    dcfWidget.style.background = 'linear-gradient(180deg, var(--s1) 0%, rgba(239,68,68,0.02) 100%)';
                }
            }

            // Update relative valuation sync
            document.getElementById('rel-dcf-target').innerText = `$${implied_price.toFixed(2)}`;
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
                updateText('dp-margin', "N/A");
                updateText('dp-margin-rail', "N/A");
                updateText('dp-turnover', "N/A");
                updateText('dp-turnover-rail', "N/A");
                updateText('dp-leverage', "N/A");
                updateText('dp-leverage-rail', "N/A");
                updateText('dp-roe', "N/A");
                updateText('dp-roe-rail', "N/A");
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

        // Altman Z deconstruction factors
        function initAltmanTable() {
            const sc = STOCK_DATA.financial_scores || {};
            const altman = parseFloat(sc.altman_z || 0);

            // Use true backend weights instead of simulated splits
            const x1 = sc.altman_x1 !== undefined ? sc.altman_x1 : (altman * 0.15);
            const x2 = sc.altman_x2 !== undefined ? sc.altman_x2 : (altman * 0.10);
            const x3 = sc.altman_x3 !== undefined ? sc.altman_x3 : (altman * 0.40);
            const x4 = sc.altman_x4 !== undefined ? sc.altman_x4 : (altman * 0.20);
            const x5 = sc.altman_x5 !== undefined ? sc.altman_x5 : (altman * 0.15);

            document.getElementById('altman-x1').innerText = (x1 / 1.2).toFixed(3);
            const wx1El = document.getElementById('altman-wx1');
            wx1El.innerText = x1.toFixed(3);
            wx1El.style.color = x1 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            document.getElementById('altman-x2').innerText = (x2 / 1.4).toFixed(3);
            const wx2El = document.getElementById('altman-wx2');
            wx2El.innerText = x2.toFixed(3);
            wx2El.style.color = x2 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            document.getElementById('altman-x3').innerText = (x3 / 3.3).toFixed(3);
            const wx3El = document.getElementById('altman-wx3');
            wx3El.innerText = x3.toFixed(3);
            wx3El.style.color = x3 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            document.getElementById('altman-x4').innerText = (x4 / 0.6).toFixed(3);
            const wx4El = document.getElementById('altman-wx4');
            wx4El.innerText = x4.toFixed(3);
            wx4El.style.color = x4 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            document.getElementById('altman-x5').innerText = (x5 / 0.999).toFixed(3);
            const wx5El = document.getElementById('altman-wx5');
            wx5El.innerText = x5.toFixed(3);
            wx5El.style.color = x5 >= 0 ? 'var(--emerald)' : 'var(--ruby)';

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
            const adv = STOCK_DATA.advanced_models || {};
            const cca = adv.get_val ? adv.get_val("cca") : adv.cca || {};
            const tbody = document.getElementById('peers-table-body');
            const m = STOCK_DATA.key_metrics || {};

            if (Object.keys(cca).length === 0 || !cca.multiples || cca.multiples.length === 0) {
                // Show no data instead of hallucinating peers
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" style="text-align: center; color: var(--text-secondary); font-style: italic;">No comparable peer data available in database.</td>
                    </tr>
                `;
                document.getElementById('rel-multiple-target').innerText = `N/A`;
                return;
            }

            // Clean render from database CCA data
            tbody.innerHTML = "";
            let sumPE = 0, count = 0;
            cca.multiples.forEach(p => {
                tbody.innerHTML += `
                    <tr>
                        <td style="font-weight: 700; color: #fff;">${p.ticker}</td>
                        <td>${p.pe ? p.pe.toFixed(1) + 'x' : 'N/A'}</td>
                        <td>${p.ps ? p.ps.toFixed(2) + 'x' : 'N/A'}</td>
                        <td>${p.pb ? p.pb.toFixed(2) + 'x' : 'N/A'}</td>
                        <td>${p.ev_ebitda ? p.ev_ebitda.toFixed(1) + 'x' : 'N/A'}</td>
                    </tr>
                `;
                if (p.pe) { sumPE += p.pe; count++; }
            });

            const avgPE = count > 0 ? (sumPE / count) : 25.0;
            const currPrice = parseFloat(m.current_price || m.currentPrice || 1.0);
            const impliedPEVal = (m.trailingEps || 2.0) * avgPE;
            document.getElementById('rel-multiple-target').innerText = `$${(impliedPEVal || currPrice * 1.05).toFixed(2)}`;
        }

        // Premium dependency-free SVG 1-Year Price Line Chart with gradients and draw animation
        function drawWeeklyPriceChart() {
            const history = STOCK_DATA.price_history_compact;
            const svg = document.getElementById('price-chart-svg');
            const tracker = document.getElementById('chart-close-tracker');
            
            if (!history || Object.keys(history).length === 0) {
                svg.innerHTML = `<text x="50%" y="50%" fill="var(--text-secondary)" text-anchor="middle" font-size="12">No price history available in database.</text>`;
                return;
            }

            // Convert to sorted array
            const points = Object.entries(history)
                .map(([date, val]) => ({ date, val: parseFloat(val) }))
                .sort((a, b) => a.date.localeCompare(b.date));

            const container = document.getElementById('chart-container-root');
            const width = container.clientWidth;
            const height = 220;
            
            svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
            
            const vals = points.map(p => p.val);
            const minVal = Math.min(...vals) * 0.98;
            const maxVal = Math.max(...vals) * 1.02;
            const range = maxVal - minVal;

            // Generate path coordinates
            const pathCoords = points.map((p, idx) => {
                const x = (idx / (points.length - 1)) * (width - 40) + 20;
                const y = height - ((p.val - minVal) / range) * (height - 40) - 20;
                return { x, y, date: p.date, val: p.val };
            });

            const pathStr = pathCoords.map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(" ");
            
            // Build the closed area polygon path that fills the chart
            const minX = pathCoords[0].x;
            const maxX = pathCoords[pathCoords.length - 1].x;
            const areaPathStr = `${pathStr} L ${maxX} ${height - 20} L ${minX} ${height - 20} Z`;

            // Renders clean grid paths
            let gridHTML = "";
            for (let i = 0; i <= 4; i++) {
                const y = (i / 4) * (height - 40) + 20;
                const price = maxVal - (i / 4) * range;
                gridHTML += `
                    <line x1="20" y1="${y}" x2="${width - 20}" y2="${y}" stroke="var(--border)" stroke-dasharray="2,4" stroke-width="1" />
                    <text x="${width - 15}" y="${y + 4}" fill="var(--text-muted)" font-family="JetBrains Mono" font-size="8" text-anchor="end">$${price.toFixed(0)}</text>
                `;
            }

            // Gradient and paths
            const gradientHTML = `
                <defs>
                    <linearGradient id="chart-area-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="var(--emerald)" stop-opacity="0.18" />
                        <stop offset="100%" stop-color="var(--emerald)" stop-opacity="0" />
                    </linearGradient>
                </defs>
                <path d="${areaPathStr}" fill="url(#chart-area-grad)" style="opacity: 0; transition: opacity 1s ease 0.5s;" id="price-area-fill" />
                <path d="${pathStr}" fill="none" stroke="var(--emerald)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" id="price-path-draw" />
            `;

            // Active tracker circles
            let trackersHTML = "";
            pathCoords.forEach((pt) => {
                trackersHTML += `
                    <circle cx="${pt.x}" cy="${pt.y}" r="6" fill="var(--emerald)" opacity="0" class="hover-circle" 
                        data-date="${pt.date}" data-val="${pt.val.toFixed(2)}"
                        onmouseover="hoverChartNode(this, ${pt.x}, ${pt.y})"
                        onmouseout="leaveChartNode()" />
                `;
            });

            svg.innerHTML = gridHTML + gradientHTML + trackersHTML;
            
            // Set current closing tracker
            const latestClose = points[points.length - 1].val;
            tracker.innerText = `Latest Close: $${latestClose.toFixed(2)}`;

            // Animate draw-in
            setTimeout(() => {
                const pathEl = svg.querySelector('#price-path-draw');
                const areaEl = svg.querySelector('#price-area-fill');
                if (pathEl) {
                    const length = pathEl.getTotalLength();
                    pathEl.style.strokeDasharray = length;
                    pathEl.style.strokeDashoffset = length;
                    // Force reflow
                    pathEl.getBoundingClientRect();
                    pathEl.style.transition = 'stroke-dashoffset 1.4s var(--ease)';
                    pathEl.style.strokeDashoffset = '0';
                }
                if (areaEl) {
                    areaEl.style.opacity = '1';
                }
            }, 50);
        }

        function hoverChartNode(circle, x, y) {
            const tooltip = document.getElementById('chart-tooltip-el');
            const tracker = document.getElementById('chart-close-tracker');
            
            const date = circle.getAttribute('data-date');
            const val = circle.getAttribute('data-val');

            circle.setAttribute("opacity", "1");
            tracker.innerText = `Close: $${val}`;

            tooltip.style.display = "block";
            // Trigger reflow to ensure transition works
            void tooltip.offsetWidth;
            tooltip.style.opacity = "1";
            
            tooltip.style.left = `${x - 40}px`;
            tooltip.style.top = `${y - 45}px`; // Moved slightly higher
            tooltip.innerHTML = `${date} &middot; <span style="color: var(--emerald);">$${val}</span>`;
        }

        function leaveChartNode() {
            const tooltip = document.getElementById('chart-tooltip-el');
            tooltip.style.opacity = "0";
            
            // Wait for CSS transition (0.2s) before setting display:none
            setTimeout(() => {
                if(tooltip.style.opacity === "0") {
                    tooltip.style.display = "none";
                }
            }, 200);
            
            const hovers = document.querySelectorAll('.hover-circle');
            hovers.forEach(h => h.setAttribute("opacity", "0"));
        }

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

            document.getElementById('financial-chart-title').innerText = `${metricName} — Quarterly Progression`;
            
            const ctx = document.getElementById('financial-row-chart').getContext('2d');
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
        document.getElementById('save-btn').addEventListener('click', async () => {
            const saveBtn = document.getElementById('save-btn');
            saveBtn.disabled = true;
            saveBtn.innerText = "Saving Workbook...";

            // Extract calculated Cost of Equity
            const capmText = document.getElementById('capm-cost-val').innerText;
            const wacc = parseFloat(capmText.split(': ')[1].replace('%', ''));

            const growth_1_5 = parseFloat(document.getElementById('growth15-slider').value);
            const growth_6_10 = parseFloat(document.getElementById('growth610-slider').value);
            const terminal_growth = parseFloat(document.getElementById('terminal-slider').value);

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

        // Initialize Page
        fetchStockData();