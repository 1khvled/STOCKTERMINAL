(function () {
    function active(path) {
        const current = window.location.pathname;
        if (path === "/") return current === "/";
        return current.startsWith(path);
    }

    function initShell() {
        if (!document.body.classList.contains("terminal-shell")) return;
        if (document.querySelector(".term-topbar")) {
            sanitizeTerminalText();
            return;
        }

        const topbar = document.createElement("div");
        topbar.className = "term-topbar";
        topbar.innerHTML = `
            <div class="term-mark">S_AI</div>
            <div class="term-command">
                <span class="term-prompt">CMD</span>
                <input class="term-command-input" id="term-command-input" autocomplete="off" placeholder="RUN AAPL / OPEN MSFT / COMPARE AAPL MSFT / WATCH / REPORTS / SYSTEM">
            </div>
            <div class="term-status-strip">
                <span class="term-status-good">LIVE CONNECTED</span>
                <span id="term-clock">--:--:-- UTC</span>
                <span class="term-status-hot">LOCAL TERMINAL</span>
            </div>`;

        const rail = document.createElement("aside");
        rail.className = "term-rail";
        const links = [
            ["/", "EXEC", "EX"],
            ["/watchlist", "WATCH", "WA"],
            ["/portfolio", "PORT", "PO"],
            ["/compare", "PEER", "PE"],
            ["/news-impact", "NEWS", "NW"],
            ["/filings", "SEC", "SE"],
            ["/scenario-lab", "LAB", "LB"],
            ["/committee", "IC", "IC"],
            ["/red-flags", "FLAGS", "RF"],
            ["/reports", "FILES", "FL"],
            ["/system", "SYS", "SY"],
            ["/guide", "GUIDE", "GD"]
        ];
        rail.innerHTML = links.map(([href, label, code]) => `
            <a href="${href}" class="${active(href) ? "active" : ""}" title="${label}">
                <span class="term-rail-code">${code}</span>
                <span>${label}</span>
            </a>`).join("");

        document.body.prepend(rail);
        document.body.prepend(topbar);

        const main = document.querySelector(".main-content");
        if (main) main.classList.add("term-shell-main");

        const clock = document.getElementById("term-clock");
        const tick = () => {
            if (clock) clock.textContent = new Date().toISOString().slice(11, 19) + " UTC";
        };
        tick();
        setInterval(tick, 1000);

        const input = document.getElementById("term-command-input");
        const placeholders = [
            "RUN AAPL — compile fresh analysis",
            "OPEN MSFT — open ticker dashboard",
            "COMPARE AAPL MSFT NVDA — peer view",
            "WATCH — open watchlist",
            "REPORTS — model vault",
            "SYSTEM — monitor status"
        ];
        let placeholderIdx = 0;
        const rotatePlaceholder = () => {
            if (document.activeElement === input) return;
            input.placeholder = placeholders[placeholderIdx % placeholders.length];
            placeholderIdx += 1;
        };
        rotatePlaceholder();
        setInterval(rotatePlaceholder, 4500);

        function showCmdToast(message, type) {
            if (typeof showToast === 'function') showToast(message, type || 'info');
        }

        input.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") return;
            const raw = input.value.trim().toUpperCase();
            if (!raw) return;
            const parts = raw.split(/\s+/);
            const cmd = parts[0];
            const args = parts.slice(1);
            if ((cmd === "RUN" || cmd === "EXEC") && args[0]) {
                showCmdToast(`Running analysis for ${args[0]}...`, 'info');
                window.location.href = `/?ticker=${encodeURIComponent(args[0])}`;
            } else if ((cmd === "OPEN" || cmd === "DASH") && args[0]) {
                showCmdToast(`Opening dashboard for ${args[0]}...`, 'info');
                window.location.href = `/dashboard/${encodeURIComponent(args[0])}`;
            } else if (cmd === "COMPARE" && args.length) {
                showCmdToast(`Comparing ${args.join(', ')}...`, 'info');
                window.location.href = `/compare?tickers=${encodeURIComponent(args.join(","))}`;
            } else if ((cmd === "NEWS" || cmd === "IMPACT") && args[0]) {
                window.location.href = `/news-impact?ticker=${encodeURIComponent(args[0])}`;
            } else if ((cmd === "FILINGS" || cmd === "SEC") && args[0]) {
                window.location.href = `/filings?ticker=${encodeURIComponent(args[0])}`;
            } else if ((cmd === "SCENARIO" || cmd === "SCENARIOS" || cmd === "LAB") && args[0]) {
                window.location.href = `/scenario-lab?ticker=${encodeURIComponent(args[0])}`;
            } else if ((cmd === "COMMITTEE" || cmd === "IC") && args[0]) {
                window.location.href = `/committee?ticker=${encodeURIComponent(args[0])}`;
            } else if ((cmd === "FLAGS" || cmd === "RED" || cmd === "RISK") && args[0]) {
                window.location.href = `/red-flags?ticker=${encodeURIComponent(args[0])}`;
            } else if (cmd === "PORT" || cmd === "PORTFOLIO") {
                showCmdToast('Opening portfolio...', 'info');
                window.location.href = "/portfolio";
            } else if (cmd === "WATCH") {
                showCmdToast('Opening watchlist...', 'info');
                window.location.href = "/watchlist";
            } else if (cmd === "REPORTS" || cmd === "FILES") {
                window.location.href = "/reports";
            } else if (cmd === "NEWS" || cmd === "FEED") {
                window.location.href = "/market-feed";
            } else if (cmd === "SYSTEM" || cmd === "SYS") {
                window.location.href = "/system";
            } else if (cmd === "GUIDE" || cmd === "HELP") {
                window.location.href = "/guide";
            } else {
                showCmdToast(`Unknown command: ${cmd}`, 'warn');
                input.value = "";
            }
        });

        window.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                input.focus();
            }
            if (event.key === "/" && document.activeElement.tagName !== "INPUT") {
                event.preventDefault();
                input.focus();
            }
        });

        sanitizeTerminalText();
        installSanitizerObserver();
    }

    function sanitizeTerminalText() {
        const replacements = new Map([
            ["🟢", "ONLINE"],
            ["🔎", "SEARCH"],
            ["*", "*"],
            ["☆", "+"],
            ["⚪", "[ ]"],
            ["...", "..."],
            ["⚠", "RISK"],
            ["<-", "<-"],
            ["↕", "<>"],
            ["▲", "ASC"],
            ["▼", "DESC"],
            ["⤢", "[ ]"]
        ]);
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(node => {
            let value = node.nodeValue;
            let changed = false;
            replacements.forEach((clean, broken) => {
                if (broken && value.includes(broken)) {
                    value = value.split(broken).join(clean);
                    changed = true;
                }
            });
            if (changed) node.nodeValue = value;
        });
    }

    function installSanitizerObserver() {
        if (window.__terminalSanitizerObserver) return;
        let scheduled = false;
        window.__terminalSanitizerObserver = new MutationObserver(() => {
            if (scheduled) return;
            scheduled = true;
            requestAnimationFrame(() => {
                scheduled = false;
                sanitizeTerminalText();
            });
        });
        window.__terminalSanitizerObserver.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initShell);
    } else {
        initShell();
    }

    window.addEventListener("spa-page-loaded", () => {
        const main = document.querySelector(".main-content");
        if (main) main.classList.add("term-shell-main");
        sanitizeTerminalText();
    });
})();
