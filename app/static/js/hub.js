
        function escapeHTML(str) {
            if (typeof str !== 'string') return str;
            return str.replace(/[&<>'"]/g, tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag]));
        }

        let STOCKS = [];
        let SORT_COL = "ticker";
        let SORT_ASC = true;
        let selectedTicker = null;

        // Fetch index catalog on page load
        async function fetchCatalog() {
            try {
                const res = await fetch('/api/stocks');
                const data = await res.json();
                STOCKS = data.stocks || [];
                
                populateSectorFilter();
                renderCatalog();
                
                // Set last analyzed run in HUD vitals if available
                if (STOCKS.length > 0) {
                    const sortedByTime = [...STOCKS].sort((a,b) => new Date(b.generated_at) - new Date(a.generated_at));
                    const latest = sortedByTime[0];
                    if (latest && latest.generated_at) {
                        const dateObj = new Date(latest.generated_at);
                        const formatTime = dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
                        document.getElementById('vitals-last-run').innerText = latest.ticker + " (" + formatTime + ")";
                    }
                }
            } catch (err) {
                console.error("Failed to load local stock database:", err);
                document.getElementById('catalog-body').innerHTML = `<tr><td colspan="10" class="empty-state" style="color: var(--ruby);">❌ Failed to load local database record directory.</td></tr>`;
            }
        }

        // Live clock and market session dynamic logic
        function updateLiveClockAndSession() {
            const now = new Date();
            const utcStr = now.toISOString().slice(11, 19) + " UTC";
            const clockEl = document.getElementById('live-clock');
            if (clockEl) clockEl.innerText = utcStr;
            
            const sessionBadge = document.getElementById('market-session');
            if (!sessionBadge) return;
            
            // Convert UTC to Eastern Standard / Daylight Time (US Market hours timezone)
            try {
                const estTimeStr = now.toLocaleString("en-US", {timeZone: "America/New_York", hour12: false});
                const estMatch = estTimeStr.match(/(\d+):(\d+):(\d+)/);
                if (estMatch) {
                    const hours = parseInt(estMatch[1]);
                    const minutes = parseInt(estMatch[2]);
                    const decimalTime = hours + minutes / 60;
                    
                    // Day of week in EST
                    const estDateObj = new Date(estTimeStr);
                    const day = estDateObj.getDay(); // 0 is Sunday, 6 is Saturday
                    
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
                // Fallback to UTC simple hours if locale parsing fails
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

        function populateSectorFilter() {
            const sectors = [...new Set(STOCKS.map(s => s.sector).filter(Boolean))];
            const select = document.getElementById('filter-sector');
            select.innerHTML = '<option value="ALL">All Sectors</option>';
            sectors.forEach(sec => {
                select.innerHTML += `<option value="${sec}">${sec}</option>`;
            });
        }

        // Large numbers millions/billions/trillions institutional formatting
        function formatLargeNumber(val) {
            if (val === null || val === undefined || isNaN(val) || val === 0) return "N/A";
            const absVal = Math.abs(val);
            if (absVal >= 1e12) return (val / 1e12).toFixed(2) + " T";
            if (absVal >= 1e9) return (val / 1e9).toFixed(2) + " B";
            if (absVal >= 1e6) return (val / 1e6).toFixed(2) + " M";
            return val.toLocaleString();
        }

        function formatPercent(val) {
            if (val === null || val === undefined || isNaN(val) || val === "N/A") return "N/A";
            // Check if it is a fraction (e.g. 0.25) or a pre-multiplied percentage (e.g. 141.47 or 79.5)
            // Typically ROE / ROA are returned as decimals (e.g. 1.41 = 141.47% or 0.26 = 26.2%)
            // Let's multiply if absolute value is low or handle based on context
            const absVal = Math.abs(val);
            if (absVal > 0 && absVal <= 2.5) {
                return (val * 100).toFixed(1) + "%";
            }
            return parseFloat(val).toFixed(1) + "%";
        }

        // Live Balance Sheet scoreloader card
        function loadBalanceSheetCard(stock) {
            if (!stock) return;
            selectedTicker = stock.ticker;
            
            document.getElementById('bs-placeholder').style.display = 'none';
            document.getElementById('bs-grid').style.display = 'grid';
            
            document.getElementById('bs-company-title').innerText = `${stock.company_name} Live Scorecard`;
            const tickerBadge = document.getElementById('bs-ticker-badge');
            tickerBadge.style.display = 'inline-block';
            tickerBadge.innerText = stock.ticker;
            
            // Populate metric tiles
            document.getElementById('bs-market-cap').innerText = formatLargeNumber(stock.marketCap);
            document.getElementById('bs-revenue').innerText = formatLargeNumber(stock.totalRevenue);
            document.getElementById('bs-fcf').innerText = formatLargeNumber(stock.freeCashflow);
            document.getElementById('bs-cash').innerText = formatLargeNumber(stock.totalCash);
            document.getElementById('bs-debt').innerText = formatLargeNumber(stock.totalDebt);
            
            // Net debt computation
            const netDebt = (stock.totalDebt || 0) - (stock.totalCash || 0);
            document.getElementById('bs-net-debt').innerText = formatLargeNumber(netDebt);
            document.getElementById('bs-net-debt-sub').innerText = netDebt >= 0 ? "Net Debt Position" : "Net Cash Positive 🟢";
            
            // Book value per share
            document.getElementById('bs-book-value').innerText = stock.bookValue && stock.bookValue !== "N/A" ? `$${parseFloat(stock.bookValue).toFixed(2)}` : "N/A";
            
            // Leverage score
            const deVal = stock.debtToEquity;
            const deEl = document.getElementById('bs-de-ratio');
            deEl.innerText = deVal !== undefined && deVal !== "N/A" ? parseFloat(deVal).toFixed(1) + "%" : "N/A";
            const deSub = document.getElementById('bs-de-ratio-sub');
            if (deVal !== undefined && deVal !== "N/A") {
                const de = parseFloat(deVal);
                if (de < 100) {
                    deSub.innerHTML = `<span class="bs-badge green">Conservative</span>`;
                } else if (de <= 200) {
                    deSub.innerHTML = `<span class="bs-badge gold">Moderate</span>`;
                } else {
                    deSub.innerHTML = `<span class="bs-badge red">Leveraged</span>`;
                }
            } else {
                deSub.innerText = "Debt to Equity Ratio";
            }
            
            // Solvency Current ratio
            const crVal = stock.currentRatio;
            const crEl = document.getElementById('bs-current-ratio');
            crEl.innerText = crVal !== undefined && crVal !== "N/A" ? parseFloat(crVal).toFixed(2) : "N/A";
            const crSub = document.getElementById('bs-current-ratio-sub');
            if (crVal !== undefined && crVal !== "N/A") {
                const cr = parseFloat(crVal);
                if (cr >= 1.5) {
                    crSub.innerHTML = `<span class="bs-badge green">Solvent</span>`;
                } else if (cr >= 1.0) {
                    crSub.innerHTML = `<span class="bs-badge gold">Adequate</span>`;
                } else {
                    crSub.innerHTML = `<span class="bs-badge red">Risk Profile</span>`;
                }
            } else {
                crSub.innerText = "Current Assets / Liab";
            }
            
            // Acid Test Quick ratio
            const qrVal = stock.quickRatio;
            const qrEl = document.getElementById('bs-quick-ratio');
            qrEl.innerText = qrVal !== undefined && qrVal !== "N/A" ? parseFloat(qrVal).toFixed(2) : "N/A";
            const qrSub = document.getElementById('bs-quick-ratio-sub');
            if (qrVal !== undefined && qrVal !== "N/A") {
                const qr = parseFloat(qrVal);
                if (qr >= 1.0) {
                    qrSub.innerHTML = `<span class="bs-badge green">Safe</span>`;
                } else if (qr >= 0.7) {
                    qrSub.innerHTML = `<span class="bs-badge gold">Caution</span>`;
                } else {
                    qrSub.innerHTML = `<span class="bs-badge red">Liquid Stress</span>`;
                }
            } else {
                qrSub.innerText = "Cash equivalents / Liab";
            }
            
            // ROE
            document.getElementById('bs-roe').innerText = formatPercent(stock.returnOnEquity);
            
            // ROA
            document.getElementById('bs-roa').innerText = formatPercent(stock.returnOnAssets);
            
            // Apply selection styling to the database catalog row
            const rows = document.querySelectorAll('#catalog-body tr');
            rows.forEach(r => {
                r.classList.remove('selected');
                const tickerCell = r.querySelector('td');
                if (tickerCell && tickerCell.innerText === stock.ticker) {
                    r.classList.add('selected');
                }
            });
        }

        function renderCatalog() {
            const tbody = document.getElementById('catalog-body');
            const countText = document.getElementById('catalog-count');
            
            const filtered = getFilteredStocks();
            
            countText.innerText = `Analyzed Stock Universe (${filtered.length} Tickers)`;

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="10" class="empty-state">No matching stock records found in database.</td></tr>`;
                return;
            }

            // Sort stocks
            filtered.sort((a, b) => {
                let valA = a[SORT_COL];
                let valB = b[SORT_COL];

                if (valA === "N/A" || valA === null) return 1;
                if (valB === "N/A" || valB === null) return -1;

                if (typeof valA === 'string') {
                    return SORT_ASC ? valA.localeCompare(valB) : valB.localeCompare(valA);
                } else {
                    return SORT_ASC ? (valA - valB) : (valB - valA);
                }
            });

            const htmlRows = filtered.map(stock => {
                // Verdict badge formatting
                const verd = stock.verdict.toUpperCase();
                let verdClass = 'badge-hold';
                if (verd.includes("BUY")) verdClass = 'badge-buy';
                else if (verd.includes("SELL")) verdClass = 'badge-sell';

                // Return/Upside format
                const upVal = stock.upside * 100.0;
                const upColor = upVal >= 0 ? 'var(--emerald)' : 'var(--ruby)';
                const upText = `${upVal >= 0 ? '+' : ''}${upVal.toFixed(1)}%`;

                // Altman Z formatting
                const zVal = parseFloat(stock.altman_z || 0);
                const zLabel = escapeHTML(stock.altman_z_label || "Distress");
                let zClass = 'badge-distress';
                if (zLabel === "Safe") zClass = 'badge-safe';
                else if (zLabel === "Grey") zClass = 'badge-grey';

                // Beneish M formatting
                const mVal = parseFloat(stock.beneish_m || 0);
                let mClass = 'badge-safe';
                let mLabel = "Safe";
                if (isNaN(mVal)) {
                    mLabel = "N/A";
                    mClass = 'badge-grey';
                } else if (mVal > -1.78) {
                    mLabel = "Manipulator";
                    mClass = 'badge-distress';
                } else {
                    mLabel = "Safe";
                    mClass = 'badge-safe';
                }

                // Confidence format
                const confVal = stock.confidence !== "N/A" && stock.confidence !== undefined ? `${escapeHTML(stock.confidence.toString())}%` : "N/A";

                return `
                    <tr onclick="loadBalanceSheetCard(${escapeHTML(JSON.stringify(stock))})">
                        <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #fff;">${escapeHTML(stock.ticker)}</td>
                        <td style="font-weight: 500;">${escapeHTML(stock.company_name)}</td>
                        <td style="font-size: 0.8rem;">${escapeHTML(stock.sector)}</td>
                        <td><span class="badge ${verdClass}">${escapeHTML(stock.verdict)}</span></td>
                        <td style="font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--text-primary);">${confVal}</td>
                        <td style="font-family: 'JetBrains Mono', monospace;">$${stock.current_price.toFixed(2)}</td>
                        <td>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${upColor}; min-width: 55px; display: inline-block; text-align: right;">${upText}</span>
                                <div class="sparkline-track">
                                    <div class="sparkline-bar" style="width: ${Math.min(Math.abs(upVal), 100)}%; background: ${upColor}; left: ${upVal >= 0 ? 0 : 'auto'}; right: ${upVal < 0 ? 0 : 'auto'};"></div>
                                </div>
                            </div>
                        </td>
                        <td><span class="badge ${zClass}">${isNaN(zVal) ? "N/A" : zVal.toFixed(2)} (${zLabel})</span></td>
                        <td><span class="badge ${mClass}">${isNaN(mVal) ? "N/A" : mVal.toFixed(2)} (${mLabel})</span></td>
                        <td>
                            <div class="action-cell">
                                <a href="/dashboard/${escapeHTML(stock.ticker)}" class="btn-sm btn-sm-primary" onclick="event.stopPropagation();">Open Terminal</a>
                                <a href="/excel/${escapeHTML(stock.ticker)}" class="btn-sm" onclick="event.stopPropagation();">Excel</a>
                            </div>
                        </td>
                    </tr>
                `;
            });
            tbody.innerHTML = htmlRows.join('');

            // Reselect the selected row if still present
            if (selectedTicker) {
                const activeStock = STOCKS.find(s => s.ticker === selectedTicker);
                if (activeStock) {
                    loadBalanceSheetCard(activeStock);
                }
            }
        }

        function getFilteredStocks() {
            const searchInput = document.getElementById('catalog-search').value.toUpperCase().trim();
            const verdFilter = document.getElementById('filter-verdict').value;
            const secFilter = document.getElementById('filter-sector').value;

            return STOCKS.filter(s => {
                let matchSearch = true;
                if (searchInput) {
                    matchSearch = s.ticker.includes(searchInput) || s.company_name.toUpperCase().includes(searchInput);
                }
                
                let matchVerd = true;
                if (verdFilter === "BUY") matchVerd = s.verdict.toUpperCase().includes("BUY");
                else if (verdFilter === "SELL") matchVerd = s.verdict.toUpperCase().includes("SELL");
                else if (verdFilter === "HOLD") matchVerd = s.verdict.toUpperCase() === "HOLD";

                let matchSec = secFilter === "ALL" || s.sector === secFilter;

                return matchSearch && matchVerd && matchSec;
            });
        }

        function applyFilters() {
            renderCatalog();
        }

        function sortCatalog(col) {
            if (SORT_COL === col) {
                SORT_ASC = !SORT_ASC;
            } else {
                SORT_COL = col;
                SORT_ASC = true;
            }

            // Update header arrow symbols
            const headers = ['ticker', 'company_name', 'sector', 'verdict', 'confidence', 'current_price', 'upside', 'altman_z', 'beneish_m'];
            headers.forEach(h => {
                const el = document.getElementById(`sort-${h}`);
                if (!el) return;
                if (h === col) {
                    el.innerText = SORT_ASC ? '▲' : '▼';
                } else {
                    el.innerText = '↕';
                }
            });

            renderCatalog();
        }

        let activeEventSource = null;
        let stopwatchTimer = null;
        let stopwatchStart = 0;
        let activeStep = 0;

        // Toggle terminal card fullscreen
        function toggleFullscreen() {
            const card = document.getElementById('terminal-card');
            card.classList.toggle('terminal-fullscreen');
        }

        // Ticker quick select preset handler
        function selectPreset(ticker) {
            const input = document.getElementById('ticker-input');
            input.value = ticker;
            // Initiate analysis
            document.getElementById('submit-btn').click();
        }

        // Timer control functions
        function startStopwatch() {
            clearInterval(stopwatchTimer);
            stopwatchStart = Date.now();
            const timerEl = document.getElementById('terminal-timer');
            stopwatchTimer = setInterval(() => {
                const elapsed = (Date.now() - stopwatchStart) / 1000;
                timerEl.innerText = `Elapsed: ${elapsed.toFixed(2)}s`;
            }, 30);
        }

        // Stepper state modifiers - Updates connector colors dynamically
        function resetStepper() {
            activeStep = 0;
            for (let i = 1; i <= 6; i++) {
                setStepState(i, "pending");
                if (i < 6) {
                    const conn = document.getElementById(`step-connector-${i}`);
                    if (conn) conn.style.backgroundColor = "var(--border)";
                }
            }
        }

        function setStepState(stepNum, state) {
            const node = document.getElementById(`step-node-${stepNum}`);
            if (!node) return;
            const icon = node.querySelector('.step-status-icon');
            
            node.className = `step-node ${state}`;
            if (state === "active") {
                icon.innerText = "⏳";
            } else if (state === "completed") {
                icon.innerText = "🟢";
                // Light up the connector lines
                const prevConnector = document.getElementById(`step-connector-${stepNum - 1}`);
                if (prevConnector) {
                    prevConnector.style.backgroundColor = "var(--emerald)";
                    prevConnector.style.boxShadow = "0 0 8px var(--emerald)";
                }
            } else if (state === "failed") {
                icon.innerText = "❌";
                const prevConnector = document.getElementById(`step-connector-${stepNum - 1}`);
                if (prevConnector) {
                    prevConnector.style.backgroundColor = "var(--ruby)";
                    prevConnector.style.boxShadow = "0 0 8px var(--ruby)";
                }
            } else {
                icon.innerText = "⚪";
            }
        }

        function parseLogsForStep(line) {
            // Step 1: Statements Ingest
            if (line.includes("[1/5]") || line.includes("Fetching data from Yahoo Finance")) {
                if (activeStep > 0 && activeStep < 1) setStepState(activeStep, "completed");
                activeStep = 1;
                setStepState(1, "active");
            }
            // Step 2: Notion Hub Link
            else if (line.includes("Linked to Notion company hub page") || line.includes("Notion integration")) {
                if (activeStep === 1) setStepState(1, "completed");
                activeStep = 2;
                setStepState(2, "active");
            }
            // Step 3: Groq LLM Qualitative Synthesis
            else if (line.includes("[2/5]") || line.includes("Generating AI analysis")) {
                if (activeStep > 0 && activeStep < 3) {
                    setStepState(1, "completed");
                    setStepState(2, "completed");
                }
                activeStep = 3;
                setStepState(3, "active");
            }
            // Step 4: Asset Chart Compiling
            else if (line.includes("[3/5]") || line.includes("Skipping Matplotlib charts") || line.includes("Generating charts")) {
                if (activeStep > 0 && activeStep < 4) {
                    setStepState(3, "completed");
                }
                activeStep = 4;
                setStepState(4, "active");
            }
            // Step 5: Excel Dynamic Worksheet
            else if (line.includes("[5/5]") || line.includes("Generating dynamic Excel Financial Model")) {
                if (activeStep > 0 && activeStep < 5) {
                    setStepState(4, "completed");
                }
                activeStep = 5;
                setStepState(5, "active");
            }
            // Step 6: Database Serialization JSON Cache
            else if (line.includes("[6/6]") || line.includes("Saving consolidated records")) {
                if (activeStep > 0 && activeStep < 6) {
                    setStepState(5, "completed");
                }
                activeStep = 6;
                setStepState(6, "active");
            }
        }

        // Terminal Interactive Actions
        function clearTerminal() {
            const logsBox = document.getElementById('terminal-logs');
            logsBox.innerHTML = `<div class="log-line log-info"><span class="log-timestamp">[SYSTEM HUD]</span> Telemetry console cleared. Ready.<span class="terminal-cursor">_</span></div>`;
            resetStepper();
        }

        function copyTerminal() {
            const logsBox = document.getElementById('terminal-logs');
            // Hide the terminal cursor dynamically from copy text
            const clone = logsBox.cloneNode(true);
            const cursor = clone.querySelector('.terminal-cursor');
            if (cursor) cursor.remove();
            
            const text = clone.innerText || clone.textContent;
            navigator.clipboard.writeText(text).then(() => {
                printSystemMessage("Log history successfully copied to clipboard.");
            }).catch(err => {
                printSystemMessage("Error copying to clipboard: " + err, true);
            });
        }

        function downloadTerminal() {
            const logsBox = document.getElementById('terminal-logs');
            const clone = logsBox.cloneNode(true);
            const cursor = clone.querySelector('.terminal-cursor');
            if (cursor) cursor.remove();

            const text = clone.innerText || clone.textContent;
            const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `stocker_ai_compilation_${new Date().toISOString().slice(0,10)}.log`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            printSystemMessage("Log file successfully downloaded.");
        }

        function printSystemMessage(msg, isError = false) {
            const logsBox = document.getElementById('terminal-logs');
            const cursor = logsBox.querySelector('.terminal-cursor');
            if (cursor) cursor.remove();

            const div = document.createElement('div');
            div.className = isError ? 'log-line log-error' : 'log-line log-success';
            
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0];
            
            div.innerHTML = `<span class="log-timestamp">[${timeStr}]</span> [SYSTEM HUD] ${msg}`;
            logsBox.appendChild(div);

            appendTerminalCursor(logsBox);
            logsBox.scrollTop = logsBox.scrollHeight;
        }

        function appendTerminalCursor(box) {
            // Ensure single terminal cursor at the end
            const oldCursor = box.querySelector('.terminal-cursor');
            if (oldCursor) oldCursor.remove();
            
            const cursorSpan = document.createElement('span');
            cursorSpan.className = 'terminal-cursor';
            cursorSpan.innerText = '_';
            
            // Append cursor to the last log line or directly to the box
            if (box.lastChild) {
                box.lastChild.appendChild(cursorSpan);
            } else {
                box.appendChild(cursorSpan);
            }
        }

        // Halt / Abort live stream
        function abortAnalysis() {
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            clearInterval(stopwatchTimer);
            
            // Set statuses
            const statusBadge = document.getElementById('terminal-status-badge');
            statusBadge.innerText = "❌ ABORTED";
            statusBadge.className = "badge-status badge-status-failed";
            
            const termCard = document.getElementById('terminal-card');
            termCard.className = "card terminal-card failed";
            
            if (activeStep > 0) {
                setStepState(activeStep, "failed");
            }
            
            const logsBox = document.getElementById('terminal-logs');
            const cursor = logsBox.querySelector('.terminal-cursor');
            if (cursor) cursor.remove();

            const div = document.createElement('div');
            div.className = 'log-line log-error';
            
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0];
            
            div.innerHTML = `<span class="log-timestamp">[${timeStr}]</span> ❌ Subprocess aborted. Terminal session terminated by user.`;
            logsBox.appendChild(div);
            
            appendTerminalCursor(logsBox);
            logsBox.scrollTop = logsBox.scrollHeight;
            
            // Reset button
            const submitBtn = document.getElementById('submit-btn');
            submitBtn.disabled = false;
            submitBtn.innerHTML = `Compile Terminal <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
            
            document.getElementById('abort-btn').style.display = "none";
        }

        let batchQueue = [];
        let isBatchProcessing = false;

        // Start SSE Log Stream Analysis with Batch Queue Support
        function startAnalysis(e) {
            if (e) e.preventDefault();
            const tickerInput = document.getElementById('ticker-input');
            const rawValue = tickerInput.value.trim().toUpperCase();
            
            if (rawValue) {
                // Split by comma, remove whitespace, filter empty strings
                const tickers = rawValue.split(',').map(t => t.trim()).filter(t => t);
                batchQueue.push(...tickers);
                tickerInput.value = ''; // clear input
            }
            
            if (!isBatchProcessing && batchQueue.length > 0) {
                processNextInBatch();
            }
        }

        function processNextInBatch() {
            if (batchQueue.length === 0) {
                isBatchProcessing = false;
                fetchCatalog();
                const submitBtn = document.getElementById('submit-btn');
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Compile Terminal <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
                document.getElementById('abort-btn').style.display = "none";
                return;
            }
            
            isBatchProcessing = true;
            const ticker = batchQueue.shift();

            const submitBtn = document.getElementById('submit-btn');
            submitBtn.disabled = true;
            if (batchQueue.length > 0) {
                submitBtn.innerText = `Compiling (${batchQueue.length} queued)...`;
            } else {
                submitBtn.innerText = "Compiling...";
            }
            
            // Show abort button
            document.getElementById('abort-btn').style.display = "inline-block";

            // Reset stepper and statuses
            resetStepper();
            startStopwatch();
            
            const statusBadge = document.getElementById('terminal-status-badge');
            statusBadge.innerText = "🟡 COMPILING";
            statusBadge.className = "badge-status badge-status-running";

            const termCard = document.getElementById('terminal-card');
            termCard.className = "card terminal-card running";

            const logsBox = document.getElementById('terminal-logs');
            
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0];
            
            // Don't overwrite the whole innerHTML, just append to keep previous run logs if batching
            const cursor = logsBox.querySelector('.terminal-cursor');
            if (cursor) cursor.remove();
            
            logsBox.innerHTML += `<div class="log-line log-info" style="margin-top: 15px; border-top: 1px solid var(--border); padding-top: 10px;"><span class="log-timestamp">[${timeStr}]</span> > Starting real-time compilation log stream for stock: ${ticker}</div>`;
            appendTerminalCursor(logsBox);
            logsBox.scrollTop = logsBox.scrollHeight;

            // Start SSE Ingestion Stream
            activeEventSource = new EventSource(`/api/stream?ticker=${ticker}`);

            activeEventSource.onmessage = function(event) {
                const line = event.data;

                if (line.startsWith("REDIRECT:")) {
                    activeEventSource.close();
                    activeEventSource = null;
                    clearInterval(stopwatchTimer);
                    
                    // Mark all steps complete
                    for (let i = 1; i <= 6; i++) {
                        setStepState(i, "completed");
                    }
                    
                    statusBadge.innerText = "✅ COMPLETE";
                    statusBadge.className = "badge-status badge-status-complete";
                    termCard.className = "card terminal-card complete";

                    const nextUrl = line.split("REDIRECT:")[1].trim();
                    
                    const termCursor = logsBox.querySelector('.terminal-cursor');
                    if (termCursor) termCursor.remove();

                    const div = document.createElement('div');
                    div.className = 'log-line log-success';
                    
                    const nowInner = new Date();
                    const timeStrInner = nowInner.toTimeString().split(' ')[0];
                    
                    if (batchQueue.length > 0) {
                        div.innerHTML = `<span class="log-timestamp">[${timeStrInner}]</span> ✅ ANALYSIS COMPLETE FOR ${ticker}! Starting next in queue in 3 seconds...`;
                        logsBox.appendChild(div);
                        appendTerminalCursor(logsBox);
                        logsBox.scrollTop = logsBox.scrollHeight;
                        
                        setTimeout(processNextInBatch, 3000);
                    } else {
                        div.innerHTML = `<span class="log-timestamp">[${timeStrInner}]</span> ✅ BATCH ANALYSIS COMPLETE! Redirecting to workstation...`;
                        logsBox.appendChild(div);
                        appendTerminalCursor(logsBox);
                        logsBox.scrollTop = logsBox.scrollHeight;
                        
                        setTimeout(() => {
                            window.location.href = nextUrl;
                        }, 1500);
                    }
                    return;
                }

                if (line.includes("keepalive")) {
                    return; // Ignore keepalives
                }

                // Check logs to update stepper checkmarks
                parseLogsForStep(line);

                const cursor = logsBox.querySelector('.terminal-cursor');
                if (cursor) cursor.remove();

                const div = document.createElement('div');
                div.className = 'log-line';
                if (line.includes("❌") || line.includes("failed") || line.includes("failed completely")) {
                    div.className += ' log-error';
                    if (activeStep > 0) setStepState(activeStep, "failed");
                    termCard.className = "card terminal-card failed";
                } else if (line.includes("✅") || line.includes("Saved")) {
                    div.className += ' log-success';
                } else if (line.includes("⚠️") || line.includes("Warning")) {
                    div.className += ' log-warn';
                } else {
                    div.className += ' log-info';
                }

                const nowLog = new Date();
                const timeStrLog = nowLog.toTimeString().split(' ')[0];

                div.innerHTML = `<span class="log-timestamp">[${timeStrLog}]</span> ${line}`;
                logsBox.appendChild(div);
                
                appendTerminalCursor(logsBox);
                logsBox.scrollTop = logsBox.scrollHeight;
            };

            activeEventSource.onerror = function(err) {
                console.error("SSE stream error:", err);
                if (activeEventSource) {
                    activeEventSource.close();
                    activeEventSource = null;
                }
                clearInterval(stopwatchTimer);
                
                statusBadge.innerText = "❌ FAILED";
                statusBadge.className = "badge-status badge-status-failed";
                termCard.className = "card terminal-card failed";
                
                if (activeStep > 0) {
                    setStepState(activeStep, "failed");
                }
                
                const cursor = logsBox.querySelector('.terminal-cursor');
                if (cursor) cursor.remove();

                const div = document.createElement('div');
                div.className = 'log-line log-error';
                
                const nowErr = new Date();
                const timeStrErr = nowErr.toTimeString().split(' ')[0];
                
                div.innerHTML = `<span class="log-timestamp">[${timeStrErr}]</span> ❌ Error: Real-time stream aborted. Terminal compilation succeeded but stream failed. Refreshing database index...`;
                logsBox.appendChild(div);
                appendTerminalCursor(logsBox);
                logsBox.scrollTop = logsBox.scrollHeight;

                const submitBtn = document.getElementById('submit-btn');
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Compile Terminal <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
                document.getElementById('abort-btn').style.display = "none";
                
                // If there are more in the queue, continue despite the error!
                if (batchQueue.length > 0) {
                    const contDiv = document.createElement('div');
                    contDiv.className = 'log-line log-warn';
        let batchQueue = [];
        let isBatchProcessing = false;

        // Start SSE Log Stream Analysis with Batch Queue Support
        function startAnalysis(e) {
            if (e) e.preventDefault();
            const tickerInput = document.getElementById('ticker-input');
            const rawValue = tickerInput.value.trim().toUpperCase();
            
            if (rawValue) {
                // Split by comma, remove whitespace, filter empty strings
                const tickers = rawValue.split(',').map(t => t.trim()).filter(t => t);
                batchQueue.push(...tickers);
                tickerInput.value = ''; // clear input
            }
            
            if (!isBatchProcessing && batchQueue.length > 0) {
                processNextInBatch();
            }
        }

        function processNextInBatch() {
            if (batchQueue.length === 0) {
                isBatchProcessing = false;
                fetchCatalog();
                const submitBtn = document.getElementById('submit-btn');
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Compile Terminal <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
                document.getElementById('abort-btn').style.display = "none";
                return;
            }
            
            isBatchProcessing = true;
            const ticker = batchQueue.shift();

            const submitBtn = document.getElementById('submit-btn');
            submitBtn.disabled = true;
            if (batchQueue.length > 0) {
                submitBtn.innerText = `Compiling (${batchQueue.length} queued)...`;
            } else {
                submitBtn.innerText = "Compiling...";
            }
            
            // Show abort button
            document.getElementById('abort-btn').style.display = "inline-block";

            // Reset stepper and statuses
            resetStepper();
            startStopwatch();
            
            const statusBadge = document.getElementById('terminal-status-badge');
            statusBadge.innerText = "🟡 COMPILING";
            statusBadge.className = "badge-status badge-status-running";

            const termCard = document.getElementById('terminal-card');
            termCard.className = "card terminal-card running";

            const logsBox = document.getElementById('terminal-logs');
            
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0];
            
            // Don't overwrite the whole innerHTML, just append to keep previous run logs if batching
            const cursor = logsBox.querySelector('.terminal-cursor');
            if (cursor) cursor.remove();
            
            logsBox.innerHTML += `<div class="log-line log-info" style="margin-top: 15px; border-top: 1px solid var(--border); padding-top: 10px;"><span class="log-timestamp">[${timeStr}]</span> > Starting real-time compilation log stream for stock: ${ticker}</div>`;
            appendTerminalCursor(logsBox);
            logsBox.scrollTop = logsBox.scrollHeight;

            // Start SSE Ingestion Stream
            activeEventSource = new EventSource(`/api/stream?ticker=${ticker}`);

            activeEventSource.onmessage = function(event) {
                const line = event.data;

                if (line.startsWith("REDIRECT:")) {
                    activeEventSource.close();
                    activeEventSource = null;
                    clearInterval(stopwatchTimer);
                    
                    // Mark all steps complete
                    for (let i = 1; i <= 6; i++) {
                        setStepState(i, "completed");
                    }
                    
                    statusBadge.innerText = "✅ COMPLETE";
                    statusBadge.className = "badge-status badge-status-complete";
                    termCard.className = "card terminal-card complete";

                    const nextUrl = line.split("REDIRECT:")[1].trim();
                    
                    const termCursor = logsBox.querySelector('.terminal-cursor');
                    if (termCursor) termCursor.remove();

                    const div = document.createElement('div');
                    div.className = 'log-line log-success';
                    
                    const nowInner = new Date();
                    const timeStrInner = nowInner.toTimeString().split(' ')[0];
                    
                    if (batchQueue.length > 0) {
                        div.innerHTML = `<span class="log-timestamp">[${timeStrInner}]</span> ✅ ANALYSIS COMPLETE FOR ${ticker}! Starting next in queue in 3 seconds...`;
                        logsBox.appendChild(div);
                        appendTerminalCursor(logsBox);
                        logsBox.scrollTop = logsBox.scrollHeight;
                        
                        setTimeout(processNextInBatch, 3000);
                    } else {
                        div.innerHTML = `<span class="log-timestamp">[${timeStrInner}]</span> ✅ BATCH ANALYSIS COMPLETE! Redirecting to workstation...`;
                        logsBox.appendChild(div);
                        appendTerminalCursor(logsBox);
                        logsBox.scrollTop = logsBox.scrollHeight;
                        
                        setTimeout(() => {
                            window.location.href = nextUrl;
                        }, 1500);
                    }
                    return;
                }

                if (line.includes("keepalive")) {
                    return; // Ignore keepalives
                }

                // Check logs to update stepper checkmarks
                parseLogsForStep(line);

                const cursor = logsBox.querySelector('.terminal-cursor');
                if (cursor) cursor.remove();

                const div = document.createElement('div');
                div.className = 'log-line';
                if (line.includes("❌") || line.includes("failed") || line.includes("failed completely")) {
                    div.className += ' log-error';
                    if (activeStep > 0) setStepState(activeStep, "failed");
                    termCard.className = "card terminal-card failed";
                } else if (line.includes("✅") || line.includes("Saved")) {
                    div.className += ' log-success';
                } else if (line.includes("⚠️") || line.includes("Warning")) {
                    div.className += ' log-warn';
                } else {
                    div.className += ' log-info';
                }

                const nowLog = new Date();
                const timeStrLog = nowLog.toTimeString().split(' ')[0];

                div.innerHTML = `<span class="log-timestamp">[${timeStrLog}]</span> ${line}`;
                logsBox.appendChild(div);
                
                appendTerminalCursor(logsBox);
                logsBox.scrollTop = logsBox.scrollHeight;
            };

            activeEventSource.onerror = function(err) {
                console.error("SSE stream error:", err);
                if (activeEventSource) {
                    activeEventSource.close();
                    activeEventSource = null;
                }
                clearInterval(stopwatchTimer);
                
                statusBadge.innerText = "❌ FAILED";
                statusBadge.className = "badge-status badge-status-failed";
                termCard.className = "card terminal-card failed";
                
                if (activeStep > 0) {
                    setStepState(activeStep, "failed");
                }
                
                const cursor = logsBox.querySelector('.terminal-cursor');
                if (cursor) cursor.remove();

                const div = document.createElement('div');
                div.className = 'log-line log-error';
                
                const nowErr = new Date();
                const timeStrErr = nowErr.toTimeString().split(' ')[0];
                
                div.innerHTML = `<span class="log-timestamp">[${timeStrErr}]</span> ❌ Error: Real-time stream aborted. Terminal compilation succeeded but stream failed. Refreshing database index...`;
                logsBox.appendChild(div);
                appendTerminalCursor(logsBox);
                logsBox.scrollTop = logsBox.scrollHeight;

                const submitBtn = document.getElementById('submit-btn');
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Compile Terminal <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
                document.getElementById('abort-btn').style.display = "none";
                
                // If there are more in the queue, continue despite the error!
                if (batchQueue.length > 0) {
                    const contDiv = document.createElement('div');
                    contDiv.className = 'log-line log-warn';
                    contDiv.innerHTML = `<span class="log-timestamp">[SYSTEM]</span> ⚠️ Proceeding to next ticker in queue in 3 seconds...`;
                    logsBox.appendChild(contDiv);
                    appendTerminalCursor(logsBox);
                    logsBox.scrollTop = logsBox.scrollHeight;
                    setTimeout(processNextInBatch, 3000);
                } else {
                    // Refresh catalog just in case it compiled successfully
                    setTimeout(fetchCatalog, 3000);
                }
            };
        }

        // Initialize Page
        fetchCatalog();

        // Auto-start analysis from dashboard recompile button
        const urlParams = new URLSearchParams(window.location.search);
        const autoTicker = urlParams.get('ticker');
        if (autoTicker) {
            document.getElementById('ticker-input').value = autoTicker;
            setTimeout(() => startAnalysis({ preventDefault: () => {} }), 500);
        }

window.addEventListener('before-spa-navigate', () => { if (typeof abortAnalysis === 'function') abortAnalysis(); });
