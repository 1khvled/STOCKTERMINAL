(function () {
    if (window.Chart) return;

    class LocalChartFallback {
        constructor(ctx, config) {
            this.ctx = ctx;
            this.config = config || {};
            this.options = this.config.options || {};
            this.data = this.config.data || {};
            this.draw();
        }

        destroy() {}

        draw() {
            const canvas = this.ctx && this.ctx.canvas;
            if (!canvas) return;
            const ctx = this.ctx;
            const width = canvas.width || canvas.clientWidth || 600;
            const height = canvas.height || canvas.clientHeight || 260;
            canvas.width = width;
            canvas.height = height;

            ctx.clearRect(0, 0, width, height);
            ctx.fillStyle = "#09090b";
            ctx.fillRect(0, 0, width, height);
            ctx.strokeStyle = "rgba(161, 161, 170, 0.18)";
            ctx.lineWidth = 1;
            for (let i = 1; i < 5; i++) {
                const y = (height / 5) * i;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(width, y);
                ctx.stroke();
            }

            const datasets = ((this.config.data || {}).datasets || [])
                .filter(ds => Array.isArray(ds.data) && ds.data.some(v => Number.isFinite(Number(v))));
            if (!datasets.length) {
                ctx.fillStyle = "#a1a1aa";
                ctx.font = "12px monospace";
                ctx.fillText("Chart data unavailable", 16, 24);
                return;
            }

            const values = datasets.flatMap(ds => ds.data.map(Number).filter(Number.isFinite));
            const min = Math.min(...values);
            const max = Math.max(...values);
            const range = max - min || 1;

            datasets.forEach((ds, index) => {
                const points = ds.data.map(Number);
                ctx.strokeStyle = ds.borderColor || (index ? "#3b82f6" : "#10b981");
                ctx.lineWidth = ds.borderWidth || 2;
                ctx.beginPath();
                points.forEach((value, i) => {
                    if (!Number.isFinite(value)) return;
                    const x = points.length <= 1 ? 0 : (i / (points.length - 1)) * width;
                    const y = height - ((value - min) / range) * (height - 24) - 12;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.stroke();
            });
        }
    }

    window.Chart = LocalChartFallback;
    window.Chart.defaults = {
        color: "#a1a1aa",
        font: { family: "monospace" }
    };
})();
