document.addEventListener('DOMContentLoaded', () => {
    // Inject HTML for Terminal Overlay
    const terminalHTML = `
        <button id="terminal-toggle-btn" title="Toggle Terminal (Ctrl+~)"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg></button>
        <div id="bbg-terminal-overlay">
            <div class="bbg-terminal-header">
                <span>STOCKER AI // TERMINAL INTERFACE</span>
                <button class="bbg-close-btn" id="bbg-close-btn">&times;</button>
            </div>
            <div class="bbg-terminal-body" id="bbg-terminal-body">
                <div class="bbg-log-line">SYSTEM INITIALIZED.</div>
                <div class="bbg-log-line">Type 'HELP' for a list of available commands.</div>
            </div>
            <div class="bbg-input-line">
                <span class="bbg-prompt">&gt;</span>
                <input type="text" id="bbg-input" class="bbg-input" autocomplete="off" spellcheck="false" autofocus>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', terminalHTML);

    const overlay = document.getElementById('bbg-terminal-overlay');
    const toggleBtn = document.getElementById('terminal-toggle-btn');
    const closeBtn = document.getElementById('bbg-close-btn');
    const inputField = document.getElementById('bbg-input');
    const terminalBody = document.getElementById('bbg-terminal-body');

    let commandHistory = [];
    let historyIndex = -1;

    window.toggleTerminal = function() {
        overlay.classList.toggle('open');
        if (overlay.classList.contains('open')) {
            setTimeout(() => inputField.focus(), 300);
        }
    };

    const toggleTerminal = window.toggleTerminal;

    toggleBtn.addEventListener('click', toggleTerminal);
    closeBtn.addEventListener('click', toggleTerminal);

    // Global keyboard shortcut
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === '`') {
            e.preventDefault();
            toggleTerminal();
        }
    });

    function printLog(text, isHtml=false) {
        const line = document.createElement('div');
        line.className = 'bbg-log-line';
        if (isHtml) {
            line.innerHTML = text;
        } else {
            line.innerText = text;
        }
        terminalBody.appendChild(line);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    function escapeHTML(str) {
        if (typeof str !== 'string') return String(str);
        return str.replace(/[&<>'"]/g, tag => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[tag]));
    }

    window.runTerminalCommand = function(cmd) {
        inputField.value = cmd;
        const event = new KeyboardEvent('keydown', { key: 'Enter' });
        inputField.dispatchEvent(event);
    };

    const AVAILABLE_COMMANDS = ['HELP', 'CLEAR', 'ANALYZE', 'COMPARE', 'SCREEN', 'NEWS', 'PORTFOLIO', 'SUMMARY', 'FINANCIALS', 'WACC', 'DCF', 'PEERS', 'EXIT'];

    inputField.addEventListener('keydown', async (e) => {
        if (e.key === 'Tab') {
            e.preventDefault();
            const val = inputField.value.trim().toUpperCase();
            if (!val) return;
            const matches = AVAILABLE_COMMANDS.filter(c => c.startsWith(val));
            if (matches.length === 1) {
                inputField.value = matches[0] + " ";
            } else if (matches.length > 1) {
                printLog(`> ${val}`);
                printLog(`<span style="color:var(--bbg-orange);">${matches.join("  ")}</span>`, true);
            }
        } else if (e.key === 'Enter') {
            const rawCmd = inputField.value.trim();
            if (!rawCmd) return;

            // Push to history
            commandHistory.push(rawCmd);
            historyIndex = commandHistory.length;

            printLog(`> ${rawCmd}`);
            inputField.value = '';
            inputField.disabled = true;

            // Handle client-side commands
            const cmdUpper = rawCmd.toUpperCase();
            if (cmdUpper === 'CLEAR') {
                terminalBody.innerHTML = '';
                inputField.disabled = false;
                inputField.focus();
                return;
            }

            // Send to backend
            try {
                const response = await fetch('/api/terminal/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: rawCmd })
                });

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }

                const data = await response.json();
                
                if (data.html) {
                    printLog(data.html, true);
                } else if (data.text) {
                    printLog(data.text);
                } else {
                    printLog('No output received from server.', false);
                }

            } catch (err) {
                printLog(`<span class="bbg-text-red">Error executing command: ${escapeHTML(err.message)}</span>`, true);
            } finally {
                inputField.disabled = false;
                inputField.focus();
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (historyIndex > 0) {
                historyIndex--;
                inputField.value = commandHistory[historyIndex];
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyIndex < commandHistory.length - 1) {
                historyIndex++;
                inputField.value = commandHistory[historyIndex];
            } else {
                historyIndex = commandHistory.length;
                inputField.value = '';
            }
        }
    });
});
