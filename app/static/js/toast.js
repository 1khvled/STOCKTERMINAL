/**
 * StockerAI — Global Toast Notification System
 * Replaces all alert() calls. Load on every page.
 * Usage: showToast('message', 'success'|'error'|'warn'|'info', durationMs)
 */
(function() {
    // Inject container if not already in DOM
    function ensureContainer() {
        let c = document.getElementById('toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    window.showToast = function(message, type = 'info', duration = 3500) {
        const container = ensureContainer();

        const icons = { info: 'ℹ️', success: '✅', warn: '⚠️', error: '❌' };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type} animate-in`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
            <span style="flex:1; line-height:1.4;">${message}</span>
            <button class="toast-dismiss" onclick="this.closest('.toast').remove()" title="Dismiss">×</button>
        `;

        container.appendChild(toast);

        // Auto-dismiss
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.transition = 'opacity 300ms ease, transform 300ms ease';
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(20px)';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    };

    // Monkey-patch window.alert to use toasts
    const _originalAlert = window.alert;
    window.alert = function(msg) {
        if (typeof msg === 'string') {
            const type = msg.toLowerCase().startsWith('error') || msg.includes('failed') ? 'error' :
                         msg.toLowerCase().startsWith('warn') ? 'warn' : 'info';
            window.showToast(msg, type);
        } else {
            _originalAlert(msg);
        }
    };
})();
