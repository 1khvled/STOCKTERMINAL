
        window._hubIntervals = window._hubIntervals || [];
        window._hubIntervals.forEach(clearInterval);
        window._hubIntervals = [];
        function safeSetInterval(fn, t) {
            let id = setInterval(fn, t);
            window._hubIntervals.push(id);
            return id;
        }

        const _DUMMY = { innerText: '', innerHTML: '', style: {}, className: '', classList: { add(){}, remove(){}, contains(){ return false; } } };
        function _el(id) { return document.getElementById(id) || _DUMMY; }

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

        function relativeTime(isoStr) {
            if (!isoStr) return 'N/A';
            try {
                const diff = (Date.now() - new Date(isoStr)) / 1000;
                if (isNaN(diff)) return 'N/A';
                if (diff < 0) return 'Just now';
                if (diff < 60) return 'Just now';
                if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
                if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
                if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
                return new Date(isoStr).toLocaleDateString('en-US', {month:'short', day:'numeric'});
            } catch(e) {
                return 'N/A';
            }
        }

        function confidenceBar(score) {
            const n = parseInt(score) || 0;
            if (score === "N/A" || isNaN(n)) return `<span style="color: var(--text-muted);">N/A</span>`;
            const color = n >= 75 ? 'var(--emerald)' : n >= 50 ? 'var(--gold)' : 'var(--ruby)';
            return `<div style="display:flex; gap:6px; align-items:center;">
                <div style="width:40px; height:4px; background:var(--surface-4); border-radius:2px; overflow:hidden;">
                    <div style="width:${n}%; height:100%; background:${color}; transition:width 0.3s;"></div>
                </div>
                <span>${n}%</span>
            </div>`;
        }

        function flashPriceCell(cell, direction) {
            const cls = direction === 'up' ? 'price-flash-up' : 'price-flash-down';
            cell.classList.add(cls);
            setTimeout(() => cell.classList.remove(cls), 800);
        }

        let hoverTimer = null;
        function attachRowHoverPreview(row, stock) {
            row.addEventListener('mouseenter', () => {
                clearTimeout(hoverTimer);
                hoverTimer = setTimeout(() => showPreviewCard(stock, row), 400);
            });
            row.addEventListener('mouseleave', () => {
                clearTimeout(hoverTimer);
                hidePreviewCard();
            });
        }

        function showPreviewCard(stock, row) {
            const card = document.getElementById('catalog-row-preview');
            if (!card) return;

            // Populate content
            document.getElementById('preview-ticker').innerText = stock.ticker;
            document.getElementById('preview-name').innerText = stock.company_name;

            const priceEl = document.getElementById('preview-price');
            priceEl.innerText = `$${stock.current_price.toFixed(2)}`;

            const returnEl = document.getElementById('preview-return');
            const upVal = (stock.upside || 0) * 100;
            returnEl.innerText = `${upVal >= 0 ? '+' : ''}${upVal.toFixed(1)}%`;
            returnEl.style.color = upVal >= 0 ? 'var(--emerald)' : 'var(--ruby)';

            const peEl = document.getElementById('preview-pe');
            peEl.innerText = stock.pe_ratio && stock.pe_ratio !== 'N/A' ? parseFloat(stock.pe_ratio).toFixed(1) : 'N/A';

            const roeEl = document.getElementById('preview-roe');
            roeEl.innerText = stock.returnOnEquity && stock.returnOnEquity !== 'N/A' ? `${(parseFloat(stock.returnOnEquity) * 100).toFixed(1)}%` : 'N/A';

            const azEl = document.getElementById('preview-az');
            azEl.innerText = stock.altman_z && stock.altman_z !== 'N/A' ? parseFloat(stock.altman_z).toFixed(2) : 'N/A';

            const fsEl = document.getElementById('preview-fs');
            fsEl.innerText = stock.piotroski_f && stock.piotroski_f !== 'N/A' ? stock.piotroski_f : 'N/A';

            // Positioning
            const rect = row.getBoundingClientRect();
            card.style.top = `${rect.top + window.scrollY}px`;
            card.style.left = `${rect.right + 12}px`;
            
            if (rect.right + 300 > window.innerWidth) {
                card.style.left = `${rect.left - 300}px`;
            }

            card.style.display = 'block';
        }

        function hidePreviewCard() {
            const card = document.getElementById('catalog-row-preview');
            if (card) card.style.display = 'none';
        }

        function checkDataFreshness() {
            const staleTickers = STOCKS.filter(s => {
                if (!s.generated_at) return false;
                const ageDays = (Date.now() - new Date(s.generated_at)) / 86400000;
                return ageDays > 7;
            });
            const banner = document.getElementById('freshness-banner');
            const countEl = document.getElementById('freshness-count');
            if (banner && countEl) {
                if (staleTickers.length > 0) {
                    banner.style.display = 'flex';
                    countEl.innerText = staleTickers.length;
                } else {
                    banner.style.display = 'none';
                }
            }
        }

        function updateMissionControl(filteredStocks = null) {
            const list = Array.isArray(filteredStocks) ? filteredStocks : STOCKS;
            const bullish = list.filter(s => {
                const verdict = (s.verdict || '').toUpperCase();
                return verdict.includes('BUY');
            }).length;
            const stale = STOCKS.filter(s => {
                if (!s.generated_at) return false;
                const ageDays = (Date.now() - new Date(s.generated_at)) / 86400000;
                return ageDays > 7;
            }).length;
            const confidences = list
                .map(s => parseFloat(s.confidence))
                .filter(v => !Number.isNaN(v));
            const avgConfidence = confidences.length
                ? Math.round(confidences.reduce((sum, v) => sum + v, 0) / confidences.length)
                : 0;

            _el('mission-coverage').innerText = String(list.length);
            _el('mission-bullish').innerText = String(bullish);
            _el('mission-confidence').innerText = `${avgConfidence}%`;
            _el('mission-watchlist').innerText = String(WATCHLIST.length);
            _el('mission-stale').innerText = String(stale);
        }

        function sanitizeHubCopy() {
            const tickerInput = document.getElementById('ticker-input');
            if (tickerInput) {
                tickerInput.placeholder = 'Enter stock symbol (e.g. CRM) - Press / to focus';
            }
            const badge = document.getElementById('terminal-status-badge');
            if (badge && !badge.querySelector('.status-dot')) {
                badge.innerHTML = '<span class="status-dot status-dot--idle"></span> IDLE';
            }

            const fullscreenBtn = document.querySelector('.terminal-actions .terminal-action-btn');
            if (fullscreenBtn) fullscreenBtn.textContent = 'Fullscreen';
        }

        function initTickerAutocomplete() {
            const input = document.getElementById('ticker-input');
            const dropdown = document.getElementById('ticker-autocomplete');
            if (!input || !dropdown) return;

            function renderDropdown(items, title = "Recently Analyzed") {
                if (items.length === 0) {
                    dropdown.style.display = 'none';
                    return;
                }
                
                dropdown.innerHTML = `
                    <div class="autocomplete-label">${title}</div>
                    ${items.map(stock => {
                        const verd = (stock.verdict || 'HOLD').toUpperCase();
                        let verdColor = 'var(--text-muted)';
                        if (verd.includes("BUY")) verdColor = 'var(--emerald)';
                        else if (verd.includes("SELL")) verdColor = 'var(--ruby)';
                        
                        return `
                            <div class="autocomplete-item" data-ticker="${escapeHTML(stock.ticker)}">
                                <div>
                                    <span style="font-family: var(--font-mono); font-weight: 700; color: #fff;">${escapeHTML(stock.ticker)}</span>
                                    <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 6px;">${escapeHTML(stock.company_name)}</span>
                                </div>
                                <span style="font-size: 0.75rem; font-weight: 600; color: ${verdColor};">${escapeHTML(stock.verdict)}</span>
                            </div>
                        `;
                    }).join('')}
                `;
                dropdown.style.display = 'block';
            }

            function updateAutocomplete() {
                const query = input.value.toUpperCase().trim();
                if (!query) {
                    const recent = [...STOCKS]
                        .filter(s => s.generated_at)
                        .sort((a, b) => new Date(b.generated_at) - new Date(a.generated_at))
                        .slice(0, 8);
                    renderDropdown(recent, "Recently Analyzed");
                } else {
                    const matches = STOCKS.filter(s => 
                        s.ticker.includes(query) || 
                        s.company_name.toUpperCase().includes(query)
                    ).slice(0, 8);
                    renderDropdown(matches, "Search Results");
                }
            }

            input.addEventListener('focus', () => {
                dropdown.style.top = `${input.offsetHeight + 6}px`;
                dropdown.style.left = '0';
                dropdown.style.right = '0';
                dropdown.style.width = '100%';
                updateAutocomplete();
            });

            input.addEventListener('input', updateAutocomplete);

            document.addEventListener('click', (e) => {
                if (e.target !== input && !dropdown.contains(e.target)) {
                    dropdown.style.display = 'none';
                }
            });

            dropdown.addEventListener('click', (e) => {
                const item = e.target.closest('.autocomplete-item');
                if (item) {
                    const ticker = item.dataset.ticker;
                    input.value = ticker;
                    dropdown.style.display = 'none';
                    startAnalysis({ preventDefault: () => {} });
                }
            });
        }

        window.closeKbdModal = function() {
            const m = document.getElementById('keyboard-shortcuts-modal');
            if (m) m.classList.remove('open');
        };
        window.openKbdModal = function() {
            const m = document.getElementById('keyboard-shortcuts-modal');
            if (m) m.classList.add('open');
        };
        window.toggleKbdModal = function() {
            const m = document.getElementById('keyboard-shortcuts-modal');
            if (m) m.classList.toggle('open');
        };

        document.addEventListener('keydown', function(e) {
            const inInput = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable;
            
            if (inInput) {
                if (e.key === 'Escape') {
                    e.target.blur();
                    const input = document.getElementById('ticker-input');
                    if (e.target === input) {
                        input.value = '';
                    }
                    closeKbdModal();
                } else if (e.key === 'Enter' && e.ctrlKey) {
                    e.preventDefault();
                    startAnalysis({ preventDefault: () => {} });
                }
                return;
            }

            if (e.key === '/') {
                e.preventDefault();
                const input = document.getElementById('ticker-input');
                if (input) {
                    input.focus();
                    input.select();
                }
            } else if (e.key === 'Escape') {
                closeKbdModal();
            } else if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
                e.preventDefault();
                toggleKbdModal();
            } else if (e.key === 'e' && e.ctrlKey) {
                e.preventDefault();
                if (typeof exportCatalogToCSV === 'function') {
                    exportCatalogToCSV();
                }
            } else if (e.key === 'C' && e.ctrlKey && e.shiftKey) {
                e.preventDefault();
                if (WATCHLIST.length > 0) {
                    window.location.href = `/compare?tickers=${WATCHLIST.join(',')}`;
                } else {
                    if (typeof showToast === 'function') {
                        showToast('Watchlist is empty. Add stocks to compare.', 'warn');
                    } else {
                        alert('Watchlist is empty. Add stocks to compare.');
                    }
                }
            }
        });

        let STOCKS = [];
        let SORT_COL = "ticker";
        let SORT_ASC = true;
        let selectedTicker = null;
        
        let WATCHLIST = [];
        try {
            WATCHLIST = JSON.parse(localStorage.getItem('stocker_watchlist') || '[]');
            if (!Array.isArray(WATCHLIST)) WATCHLIST = [];
        } catch (e) {
            WATCHLIST = [];
        }
        let SHOW_WATCHLIST_ONLY = false;

        function toggleWatchlistFilter() {
            SHOW_WATCHLIST_ONLY = !SHOW_WATCHLIST_ONLY;
            const btn = document.getElementById('filter-watchlist-btn');
            if (SHOW_WATCHLIST_ONLY) {
                btn.style.backgroundColor = 'rgba(16, 185, 129, 0.2)';
                btn.style.color = 'var(--emerald)';
                btn.style.borderColor = 'var(--emerald)';
            } else {
                btn.style.backgroundColor = '';
                btn.style.color = '';
                btn.style.borderColor = '';
            }
            applyFilters();
        }

        function toggleStar(ticker, event) {
            event.stopPropagation();
            if (WATCHLIST.includes(ticker)) {
                WATCHLIST = WATCHLIST.filter(t => t !== ticker);
            } else {
                WATCHLIST.push(ticker);
            }
            localStorage.setItem('stocker_watchlist', JSON.stringify(WATCHLIST));
            renderCatalog();
        }

        // Fetch index catalog on page load
        async function fetchCatalog() {
            try {
                const res = await fetch('/api/stocks');
                if (!res.ok) throw new Error("Catalog fetch failed with status: " + res.status);
                const data = await res.json();
                STOCKS = data.stocks || [];
                
                populateSectorFilter();
                renderCatalog();
                fetchLiveQuotesForCatalog(); // Fetch real-time quotes immediately on load
                checkDataFreshness();
                updateMissionControl(STOCKS);
                
                
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
                document.getElementById('catalog-body').innerHTML = `<tr><td colspan="12" class="empty-state" style="color: var(--ruby);">Failed to load local database.</td></tr>`;
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
                        _el('market-session-copy').innerText = 'Weekend';
                    } else {
                        if (decimalTime >= 4 && decimalTime < 9.5) {
                            sessionBadge.className = 'session-badge pre-mkt';
                            sessionBadge.innerText = 'PRE-MARKET';
                            _el('market-session-copy').innerText = 'Pre-market';
                        } else if (decimalTime >= 9.5 && decimalTime < 16) {
                            sessionBadge.className = 'session-badge open';
                            sessionBadge.innerText = 'MARKET OPEN';
                            _el('market-session-copy').innerText = 'Live';
                        } else if (decimalTime >= 16 && decimalTime < 20) {
                            sessionBadge.className = 'session-badge after-hrs';
                            sessionBadge.innerText = 'AFTER HOURS';
                            _el('market-session-copy').innerText = 'After-hours';
                        } else {
                            sessionBadge.className = 'session-badge closed';
                            sessionBadge.innerText = 'MARKET CLOSED';
                            _el('market-session-copy').innerText = 'Closed';
                        }
                    }
                }
            } catch (e) {
                // Fallback to UTC simple hours if locale parsing fails
                const utcHours = now.getUTCHours();
                if (utcHours >= 14 && utcHours < 21) {
                    sessionBadge.className = 'session-badge open';
                    sessionBadge.innerText = 'MARKET OPEN';
                    _el('market-session-copy').innerText = 'Live';
                } else {
                    sessionBadge.className = 'session-badge closed';
                    sessionBadge.innerText = 'MARKET CLOSED';
                    _el('market-session-copy').innerText = 'Closed';
                }
            }
        }
        updateLiveClockAndSession();
        safeSetInterval(updateLiveClockAndSession, 1000);

        function populateSectorFilter() {
            const select = document.getElementById('filter-sector');
            if (!select) return;
            const sectors = [...new Set(STOCKS.map(s => s.sector).filter(Boolean))];
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

        function isStockStale(stock) {
            if (!stock || !stock.generated_at) return false;
            const ageDays = (Date.now() - new Date(stock.generated_at)) / 86400000;
            return ageDays > 7;
        }

        window.closeBalanceSheetPanel = function() {
            const panel = document.getElementById('bs-slideover');
            if (panel) {
                panel.classList.remove('open');
                panel.setAttribute('aria-hidden', 'true');
            }
        };

        window.openBalanceSheetPanel = function() {
            const panel = document.getElementById('bs-slideover');
            if (panel) {
                panel.classList.add('open');
                panel.setAttribute('aria-hidden', 'false');
            }
        };

        window.toggleScreener = function() {
            const screener = document.getElementById('catalog-screener');
            const btn = document.getElementById('toggle-screener-btn');
            if (!screener) return;
            screener.classList.toggle('is-collapsed');
            if (btn) btn.classList.toggle('active', !screener.classList.contains('is-collapsed'));
        };

        window.toggleAdvancedColumns = function() {
            const table = document.getElementById('catalog-table');
            const btn = document.getElementById('toggle-advanced-btn');
            if (!table) return;
            table.classList.toggle('show-advanced');
            if (btn) btn.classList.toggle('active', table.classList.contains('show-advanced'));
        };

        window.toggleTableDensity = function() {
            const table = document.getElementById('catalog-table');
            const btn = document.getElementById('toggle-density-btn');
            if (!table) return;
            table.classList.toggle('density-compact');
            if (btn) btn.textContent = table.classList.contains('density-compact') ? 'Comfortable' : 'Compact';
        };

        function loadBalanceSheetCardByTicker(ticker) {
            const stock = STOCKS.find(s => s.ticker === ticker);
            if (stock) loadBalanceSheetCard(stock);
        }

        // Live Balance Sheet scoreloader card
        function loadBalanceSheetCard(stock) {
            if (!stock) return;
            selectedTicker = stock.ticker;

            openBalanceSheetPanel();
            _el('bs-placeholder').style.display = 'none';
            _el('bs-grid').style.display = 'grid';

            _el('bs-company-title').innerText = stock.company_name;
            const tickerBadge = _el('bs-ticker-badge');
            tickerBadge.style.display = 'inline-block';
            tickerBadge.innerText = stock.ticker;

            const dashLink = document.getElementById('bs-open-dashboard');
            if (dashLink) {
                dashLink.href = `/dashboard/${encodeURIComponent(stock.ticker)}`;
                dashLink.style.display = 'inline-flex';
            }
            
            // Populate metric tiles
            _el('bs-market-cap').innerText = formatLargeNumber(stock.marketCap);
            _el('bs-revenue').innerText = formatLargeNumber(stock.totalRevenue);
            _el('bs-fcf').innerText = formatLargeNumber(stock.freeCashflow);
            _el('bs-cash').innerText = formatLargeNumber(stock.totalCash);
            _el('bs-debt').innerText = formatLargeNumber(stock.totalDebt);
            
            // Net debt computation
            const netDebt = (stock.totalDebt || 0) - (stock.totalCash || 0);
            _el('bs-net-debt').innerText = formatLargeNumber(netDebt);
            _el('bs-net-debt-sub').innerText = netDebt >= 0 ? "Net Debt Position" : "Net Cash Positive";
            
            // Book value per share
            _el('bs-book-value').innerText = stock.bookValue && stock.bookValue !== "N/A" ? `$${parseFloat(stock.bookValue).toFixed(2)}` : "N/A";
            
            // Leverage score
            const deVal = stock.debtToEquity;
            const deEl = _el('bs-de-ratio');
            deEl.innerText = deVal !== undefined && deVal !== "N/A" ? parseFloat(deVal).toFixed(1) + "%" : "N/A";
            const deSub = _el('bs-de-ratio-sub');
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
            _el('bs-roe').innerText = formatPercent(stock.returnOnEquity);
            
            // ROA
            _el('bs-roa').innerText = formatPercent(stock.returnOnAssets);
            
            // Apply selection styling to the database catalog row
            const rows = document.querySelectorAll('#catalog-body tr');
            rows.forEach(r => {
                r.classList.remove('selected');
                // Ticker is in the 2nd <td> (index 1), not the 1st (which is the star icon)
                const cells = r.querySelectorAll('td');
                const tickerCell = cells[1];
                if (tickerCell && tickerCell.innerText.trim() === stock.ticker) {
                    r.classList.add('selected');
                }
            });
        }

        function renderCatalog() {
            const tbody = document.getElementById('catalog-body');
            const countText = document.getElementById('catalog-count');
            
            const filtered = getFilteredStocks();
            
            countText.innerText = `Analyzed Stock Universe (${filtered.length} Tickers)`;
            updateMissionControl(filtered);

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="12" class="empty-state">No matching stock records found in database.</td></tr>`;
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
                if (zLabel.includes("Safe")) zClass = 'badge-safe';
                else if (zLabel.includes("Grey")) zClass = 'badge-grey';

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

                // Confidence format using visual progress bar
                const confBarHtml = confidenceBar(stock.confidence);

                // After-hours / Pre-market sub-line
                let extHtml = '';
                const postP = parseFloat(stock.post_market_price || 0);
                const preP = parseFloat(stock.pre_market_price || 0);
                if (postP > 0) {
                    let chg = parseFloat(stock.post_market_change_pct || 0);
                    const chgColor = chg >= 0 ? 'var(--emerald)' : 'var(--ruby)';
                    extHtml = `<div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;">AH: <span style="color: ${chgColor}; font-weight: 600;">$${postP.toFixed(2)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%)</span></div>`;
                } else if (preP > 0) {
                    let chg = parseFloat(stock.pre_market_change_pct || 0);
                    const chgColor = chg >= 0 ? 'var(--emerald)' : 'var(--ruby)';
                    extHtml = `<div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;">PM: <span style="color: ${chgColor}; font-weight: 600;">$${preP.toFixed(2)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%)</span></div>`;
                }

                const isStarred = WATCHLIST.includes(stock.ticker);
                const starClass = isStarred ? 'star-btn active' : 'star-btn';
                const starLabel = isStarred ? '★' : '☆';
                const staleClass = isStockStale(stock) ? 'is-stale' : '';

                return `
                    <tr class="${staleClass}" onclick="loadBalanceSheetCardByTicker('${escapeHTML(stock.ticker)}')">
                        <td class="${starClass}" onclick="toggleStar('${escapeHTML(stock.ticker)}', event)">${starLabel}</td>
                        <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #fff;">${escapeHTML(stock.ticker)}</td>
                        <td style="font-weight: 500;">${escapeHTML(stock.company_name)}</td>
                        <td style="font-size: 0.8rem;">${escapeHTML(stock.sector)}</td>
                        <td><span class="badge ${verdClass}">${escapeHTML(stock.verdict)}</span></td>
                        <td>${confBarHtml}</td>
                        <td class="live-price-cell" data-current-price="${stock.current_price.toFixed(2)}" style="font-family: 'JetBrains Mono', monospace;">
                            <span class="price-val" style="transition: color 0.3s ease, text-shadow 0.3s ease;">$${stock.current_price.toFixed(2)}</span>
                            ${extHtml}
                        </td>
                        <td>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${upColor}; min-width: 55px; display: inline-block; text-align: right;">${upText}</span>
                                <div class="sparkline-track">
                                    <div class="sparkline-bar" style="width: ${Math.min(Math.abs(upVal), 100)}%; background: ${upColor}; left: ${upVal >= 0 ? 0 : 'auto'}; right: ${upVal < 0 ? 0 : 'auto'};"></div>
                                </div>
                            </div>
                        </td>
                        <td class="col-advanced"><span class="badge ${zClass}">${isNaN(zVal) ? "N/A" : zVal.toFixed(2)} (${zLabel})</span></td>
                        <td class="col-advanced"><span class="badge ${mClass}">${isNaN(mVal) ? "N/A" : mVal.toFixed(2)} (${mLabel})</span></td>
                        <td style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted);">${escapeHTML(relativeTime(stock.generated_at))}</td>
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

            // Attach row hover previews
            const rows = tbody.querySelectorAll('tr');
            rows.forEach((row, idx) => {
                const stock = filtered[idx];
                if (stock) attachRowHoverPreview(row, stock);
            });

            // Reselect the selected row if still present (without re-opening panel animation)
            if (selectedTicker) {
                const rows = tbody.querySelectorAll('tr');
                rows.forEach(r => {
                    r.classList.remove('selected');
                    const cells = r.querySelectorAll('td');
                    const tickerCell = cells[1];
                    if (tickerCell && tickerCell.innerText.trim() === selectedTicker) {
                        r.classList.add('selected');
                    }
                });
            }
        }

        function getFilteredStocks() {
            const searchInput = document.getElementById('catalog-search').value.toUpperCase().trim();
            const verdFilter = document.getElementById('filter-verdict').value;
            const secFilter = document.getElementById('filter-sector').value;

            // Advanced Screener Inputs
            const screenUpsideEl = document.getElementById('screen-upside');
            const screenAltmanEl = document.getElementById('screen-altman');
            const screenRoeEl = document.getElementById('screen-roe');
            const screenDeEl = document.getElementById('screen-de');
            const screenVerdictEl = document.getElementById('screen-verdict');

            const screenUpside = screenUpsideEl ? parseFloat(screenUpsideEl.value) : NaN;
            const screenAltman = screenAltmanEl ? parseFloat(screenAltmanEl.value) : NaN;
            const screenRoe = screenRoeEl ? parseFloat(screenRoeEl.value) : NaN;
            const screenDe = screenDeEl ? parseFloat(screenDeEl.value) : NaN;
            const screenVerdict = screenVerdictEl ? screenVerdictEl.value : '';

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

                // Screener logic: skip filtering when slider is at the default minimum/maximum
                let matchScreenUpside = true;
                if (!isNaN(screenUpside) && screenUpside > -50) {
                    let upsideVal = parseFloat(s.upside);
                    matchScreenUpside = !isNaN(upsideVal) && (upsideVal * 100) >= screenUpside;
                }

                let matchScreenAltman = true;
                if (!isNaN(screenAltman) && screenAltman > -2) {
                    let altmanVal = parseFloat(s.altman_z);
                    matchScreenAltman = !isNaN(altmanVal) && altmanVal >= screenAltman;
                }

                let matchScreenRoe = true;
                if (!isNaN(screenRoe) && screenRoe > -50) {
                    let roeVal = parseFloat(s.returnOnEquity);
                    matchScreenRoe = !isNaN(roeVal) && (roeVal * 100) >= screenRoe;
                }

                let matchScreenDe = true;
                if (!isNaN(screenDe) && screenDe < 5) {
                    let deVal = parseFloat(s.debtToEquity);
                    matchScreenDe = !isNaN(deVal) && deVal <= screenDe;
                }

                let matchScreenVerdict = true;
                if (screenVerdict) {
                    if (screenVerdict === "BUY") matchScreenVerdict = s.verdict.toUpperCase() === "BUY";
                    else matchScreenVerdict = s.verdict.toUpperCase() === screenVerdict;
                }
                
                let matchWatchlist = true;
                if (SHOW_WATCHLIST_ONLY) {
                    matchWatchlist = WATCHLIST.includes(s.ticker);
                }

                return matchSearch && matchVerd && matchSec && matchScreenUpside && matchScreenAltman && matchScreenRoe && matchScreenDe && matchScreenVerdict && matchWatchlist;
            });
        }

        function applyFilters() {
            renderCatalog();
        }

        function clearFilters() {
            const defaults = {
                'screen-upside': '-50',
                'screen-roe': '-50',
                'screen-altman': '-2',
                'screen-de': '5',
                'screen-verdict': '',
                'catalog-search': ''
            };
            Object.keys(defaults).forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = defaults[id];
            });

            // Update range text indicators
            const upsideVal = document.getElementById('upside-val');
            if (upsideVal) upsideVal.innerText = '-50%';
            const roeVal = document.getElementById('roe-val');
            if (roeVal) roeVal.innerText = '-50%';
            const altmanVal = document.getElementById('altman-val');
            if (altmanVal) altmanVal.innerText = '-2';
            const deVal = document.getElementById('de-val');
            if (deVal) deVal.innerText = '5';

            const filterVerd = document.getElementById('filter-verdict');
            if (filterVerd) filterVerd.value = 'ALL';
            const filterSec = document.getElementById('filter-sector');
            if (filterSec) filterSec.value = 'ALL';
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
            const headers = ['ticker', 'company_name', 'sector', 'verdict', 'confidence', 'current_price', 'upside', 'altman_z', 'beneish_m', 'generated_at'];
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

        function exportCatalogToCSV() {
            const filtered = getFilteredStocks();
            if (filtered.length === 0) {
                alert("No stocks to export. Adjust your filters.");
                return;
            }

            // CSV Header
            let csvContent = "data:text/csv;charset=utf-8,";
            csvContent += "Ticker,Company Name,Sector,Verdict,Confidence,Price,Implied Return %,Altman Z,Beneish M\n";

            filtered.forEach(s => {
                let ticker = s.ticker || "";
                // Escape company name to handle commas
                let company = s.company_name ? `"${s.company_name.replace(/"/g, '""')}"` : "";
                let sector = s.sector || "";
                let verdict = s.verdict || "";
                let conf = s.confidence || "";
                let price = s.current_price !== undefined ? s.current_price.toFixed(2) : "";
                let returnPct = s.upside !== undefined ? (s.upside * 100).toFixed(2) : "";
                let altman = s.altman_z || "";
                let beneish = s.beneish_m || "";
                
                let row = `${ticker},${company},${sector},${verdict},${conf},${price},${returnPct},${altman},${beneish}`;
                csvContent += row + "\n";
            });

            const encodedUri = encodeURI(csvContent);
            const a = document.createElement("a");
            a.setAttribute("href", encodedUri);
            a.setAttribute("download", `Stocker_Quant_Export_${new Date().toISOString().slice(0,10)}.csv`);
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
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
            // Step 3: Nemotron AI qualitative synthesis
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
            statusBadge.innerText = "ABORTED";
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
            isBatchProcessing = false; // Fix: reset processing flag on abort
            batchQueue = []; // Fix: clear the pending batch queue on abort
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
            statusBadge.innerText = "COMPILING";
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
                    
                    statusBadge.innerText = "COMPLETE";
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

                if (line.includes("Subprocess analysis crashed") || line.includes("Server error:")) {
                    if (activeEventSource) {
                        activeEventSource.close();
                        activeEventSource = null;
                    }
                    clearInterval(stopwatchTimer);
                    
                    statusBadge.innerText = "FAILED";
                    statusBadge.className = "badge-status badge-status-failed";
                    termCard.className = "card terminal-card failed";
                    
                    if (activeStep > 0) setStepState(activeStep, "failed");
                    
                    // Allow it to print the line below as an error
                    // Then continue batch or reset
                    setTimeout(() => {
                        document.getElementById('abort-btn').style.display = "none";
                        const submitBtn = document.getElementById('submit-btn');
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = `Compile Terminal <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;

                        if (batchQueue.length > 0) {
                            const contDiv = document.createElement('div');
                            contDiv.className = 'log-line log-warn';
                            contDiv.innerHTML = `<span class="log-timestamp">[SYSTEM]</span> ⚠️ Proceeding to next ticker in queue in 3 seconds...`;
                            logsBox.appendChild(contDiv);
                            appendTerminalCursor(logsBox);
                            logsBox.scrollTop = logsBox.scrollHeight;
                            setTimeout(processNextInBatch, 3000);
                        } else {
                            isBatchProcessing = false;
                            setTimeout(fetchCatalog, 3000);
                        }
                    }, 100);
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
                
                statusBadge.innerText = "FAILED";
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
                    isBatchProcessing = false; // Fix: reset processing flag on failure
                    // Refresh catalog just in case it compiled successfully
                    setTimeout(fetchCatalog, 3000);
                }
            };
        }

        // Initialize Page
        sanitizeHubCopy();
        fetchCatalog();

        // --- Live Price Ticker Simulation ---
        function startLivePriceTicker() {
            safeSetInterval(() => {
                const priceCells = document.querySelectorAll('.live-price-cell');
                if (priceCells.length === 0) return;
                
                // Pick a random subset of stocks to "tick" (about 30%)
                const numToTick = Math.max(1, Math.floor(priceCells.length * 0.3));
                
                for (let i = 0; i < numToTick; i++) {
                    const randomIdx = Math.floor(Math.random() * priceCells.length);
                    const cell = priceCells[randomIdx];
                    const valSpan = cell.querySelector('.price-val');
                    if (!valSpan) continue;
                    
                    const origPrice = parseFloat(cell.getAttribute('data-current-price'));
                    if (isNaN(origPrice)) continue;
                    
                    // random delta between -0.4% and +0.4%
                    const deltaPct = (Math.random() - 0.5) * 0.008;
                    const newPrice = origPrice * (1 + deltaPct);
                    
                    valSpan.innerText = '$' + newPrice.toFixed(2);
                    cell.setAttribute('data-current-price', newPrice.toFixed(2));
                    
                    // Flash effect
                    if (deltaPct >= 0) {
                        valSpan.style.color = '#4ade80'; // Emerald light
                        valSpan.style.textShadow = '0 0 10px rgba(74, 222, 128, 0.4)';
                    } else {
                        valSpan.style.color = '#f87171'; // Ruby light
                        valSpan.style.textShadow = '0 0 10px rgba(248, 113, 113, 0.4)';
                    }
                    
                    // Reset color after 800ms
                    setTimeout(() => {
                        valSpan.style.color = '';
                        valSpan.style.textShadow = 'none';
                    }, 800);
                }
            }, 2500); // tick every 2.5 seconds
        }
        startLivePriceTicker();

        async function fetchLiveQuotesForCatalog() {
            if (!STOCKS || STOCKS.length === 0) return;
            try {
                const tickers = STOCKS.map(s => s.ticker).join(',');
                const res = await fetch(`/api/stocks/live-quotes?tickers=${tickers}&t=${new Date().getTime()}`);
                if (!res.ok) return;
                const result = await res.json();
                const quotes = result.quotes || {};

                // Update STOCKS in-memory
                STOCKS.forEach(stock => {
                    const quote = quotes[stock.ticker];
                    if (quote && !quote.error) {
                        stock.current_price = parseFloat(quote.currentPrice || quote.regularMarketPrice || stock.current_price);
                        stock.pre_market_price = quote.preMarketPrice;
                        stock.pre_market_change_pct = quote.preMarketChangePercent;
                        stock.post_market_price = quote.postMarketPrice;
                        stock.post_market_change_pct = quote.postMarketChangePercent;
                        stock.market_state = quote.marketState;
                    }
                });

                // Update DOM directly to avoid full table re-render jumpiness
                const rows = document.querySelectorAll('#catalog-body tr');
                rows.forEach(row => {
                    const firstCell = row.querySelector('td:nth-child(2)'); // Ticker is the second column
                    if (!firstCell) return;
                    const ticker = firstCell.innerText.trim().toUpperCase();
                    const quote = quotes[ticker];
                    if (quote && !quote.error) {
                        const priceCell = row.querySelector('.live-price-cell');
                        if (priceCell) {
                            const newPrice = parseFloat(quote.currentPrice || quote.regularMarketPrice || 0);
                            if (newPrice > 0) {
                                const valSpan = priceCell.querySelector('.price-val');
                                const oldPrice = parseFloat(priceCell.getAttribute('data-current-price') || 0);
                                
                                priceCell.setAttribute('data-current-price', newPrice.toFixed(2));
                                if (valSpan) {
                                    valSpan.innerText = `$${newPrice.toFixed(2)}`;
                                    
                                    // Price flash glow
                                    if (oldPrice > 0 && Math.abs(newPrice - oldPrice) > 0.001) {
                                        const direction = newPrice > oldPrice ? 'up' : 'down';
                                        flashPriceCell(valSpan, direction);
                                    }
                                }
                            }

                            // Update after-hours / pre-market sub-line
                            const postP = parseFloat(quote.postMarketPrice || 0);
                            const preP = parseFloat(quote.preMarketPrice || 0);
                            let extHtml = '';
                            
                            if (postP > 0) {
                                let chg = parseFloat(quote.postMarketChangePercent || 0);
                                const chgColor = chg >= 0 ? 'var(--emerald)' : 'var(--ruby)';
                                extHtml = `<div class="ext-hours-subline" style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;">AH: <span style="color: ${chgColor}; font-weight: 600;">$${postP.toFixed(2)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%)</span></div>`;
                            } else if (preP > 0) {
                                let chg = parseFloat(quote.preMarketChangePercent || 0);
                                const chgColor = chg >= 0 ? 'var(--emerald)' : 'var(--ruby)';
                                extHtml = `<div class="ext-hours-subline" style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;">PM: <span style="color: ${chgColor}; font-weight: 600;">$${preP.toFixed(2)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%)</span></div>`;
                            }

                            // Replace or add the subline
                            let existingSubline = priceCell.querySelector('.ext-hours-subline');
                            if (existingSubline) {
                                if (extHtml) {
                                    existingSubline.outerHTML = extHtml;
                                } else {
                                    existingSubline.remove();
                                }
                            } else if (extHtml) {
                                priceCell.insertAdjacentHTML('beforeend', extHtml);
                            }
                        }
                    }
                });

                // Also update the loaded details card if it's currently open
                if (selectedTicker) {
                    const activeStock = STOCKS.find(s => s.ticker === selectedTicker);
                    if (activeStock) {
                        const cardPriceEl = document.getElementById('card-current-price');
                        if (cardPriceEl) {
                            cardPriceEl.innerText = `$${activeStock.current_price.toFixed(2)}`;
                        }
                    }
                }
            } catch (err) {
                console.error("Failed to load catalog live quotes:", err);
            }
        }

        // Periodically refresh the catalog live quotes (every 30 seconds)
        safeSetInterval(fetchLiveQuotesForCatalog, 30000);

        // Auto-start analysis from dashboard recompile button
        const urlParams = new URLSearchParams(window.location.search);
        const autoTicker = urlParams.get('ticker');
        if (autoTicker) {
            document.getElementById('ticker-input').value = autoTicker;
            setTimeout(() => startAnalysis({ preventDefault: () => {} }), 500);
        }

        initTickerAutocomplete();

window.addEventListener('before-spa-navigate', () => { 
    if (typeof abortAnalysis === 'function') abortAnalysis(); 
    if (window._hubIntervals) {
        window._hubIntervals.forEach(clearInterval);
        window._hubIntervals = [];
    }
});
