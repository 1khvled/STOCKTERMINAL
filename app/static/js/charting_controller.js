window.ChartingController = {
    app: null,
    ticker: 'AAPL',
    widgets: [],

    init: function(app, ticker) {
        this.app = app;
        if (ticker) this.ticker = ticker;
        
        // Wait for TV script to load if needed
        const checkTV = setInterval(() => {
            if (typeof TradingView !== 'undefined') {
                clearInterval(checkTV);
                this.updateLayout('1'); // Default to 1 chart
            }
        }, 100);
    },

    createWidget: function(containerId, ticker) {
        const isDark = !document.body.classList.contains('theme-light');
        
        return new TradingView.widget({
          "autosize": true,
          "symbol": ticker || this.ticker,
          "interval": "D",
          "timezone": "Etc/UTC",
          "theme": isDark ? "dark" : "light",
          "style": "1",
          "locale": "en",
          "enable_publishing": false,
          "backgroundColor": isDark ? "#0f172a" : "#ffffff",
          "gridColor": isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(0, 0, 0, 0.05)",
          "hide_top_toolbar": false,
          "hide_legend": false,
          "save_image": false,
          "container_id": containerId,
          "toolbar_bg": isDark ? "#0f172a" : "#ffffff"
        });
    },

    updateLayout: function(layout) {
        const grid = document.getElementById('tv-grid-container');
        if (!grid) return;
        
        const charts = [
            document.getElementById('tv-chart-1'),
            document.getElementById('tv-chart-2'),
            document.getElementById('tv-chart-3'),
            document.getElementById('tv-chart-4')
        ];
        
        // Reset
        charts.forEach(c => {
            if (c) {
                c.style.display = 'none';
                c.innerHTML = '';
            }
        });
        
        this.widgets = [];

        if (layout === '1') {
            grid.style.gridTemplateColumns = '1fr';
            grid.style.gridTemplateRows = '1fr';
            charts[0].style.display = 'block';
            this.widgets.push(this.createWidget('tv-chart-1', this.ticker));
            
        } else if (layout === '2h') {
            grid.style.gridTemplateColumns = '1fr 1fr';
            grid.style.gridTemplateRows = '1fr';
            charts[0].style.display = 'block';
            charts[1].style.display = 'block';
            this.widgets.push(this.createWidget('tv-chart-1', this.ticker));
            this.widgets.push(this.createWidget('tv-chart-2', 'QQQ'));
            
        } else if (layout === '2v') {
            grid.style.gridTemplateColumns = '1fr';
            grid.style.gridTemplateRows = '1fr 1fr';
            charts[0].style.display = 'block';
            charts[1].style.display = 'block';
            this.widgets.push(this.createWidget('tv-chart-1', this.ticker));
            this.widgets.push(this.createWidget('tv-chart-2', 'SPY'));
            
        } else if (layout === '4') {
            grid.style.gridTemplateColumns = '1fr 1fr';
            grid.style.gridTemplateRows = '1fr 1fr';
            charts.forEach(c => c.style.display = 'block');
            this.widgets.push(this.createWidget('tv-chart-1', this.ticker));
            this.widgets.push(this.createWidget('tv-chart-2', 'QQQ'));
            this.widgets.push(this.createWidget('tv-chart-3', 'SPY'));
            this.widgets.push(this.createWidget('tv-chart-4', 'IWM'));
        }
    }
};
