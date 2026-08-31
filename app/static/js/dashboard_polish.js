(function () {
    const labels = {
        "tab-verdict": "OVERVIEW",
        "tab-financials": "FINANCIALS",
        "tab-solvency": "SOLVENCY",
        "tab-fundamentals": "FUNDAMENTALS",
        "tab-relative": "PEERS",
        "tab-sentiment": "SENTIMENT",
        "tab-risks": "RISKS",
        "tab-notion": "NOTION HUB"
    };

    function polish() {
        Object.entries(labels).forEach(([tab, label]) => {
            const button = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
            if (button) button.textContent = label;
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", polish);
    } else {
        polish();
    }
})();
