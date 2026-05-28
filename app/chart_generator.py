"""
Chart Generator — Creates matplotlib charts for PDF and Excel reports
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path
from config import CHART_STYLE as CS


def _setup_style():
    plt.rcParams.update({
        "figure.facecolor": CS["bg_color"],
        "axes.facecolor": CS["bg_color"],
        "axes.edgecolor": CS["grid_color"],
        "axes.labelcolor": CS["text_color"],
        "text.color": CS["text_color"],
        "xtick.color": CS["text_color"],
        "ytick.color": CS["text_color"],
        "grid.color": CS["grid_color"],
        "grid.alpha": 0.3,
        "font.family": CS["font_family"],
        "font.size": 10,
    })


def generate_price_chart(history, ticker, output_path):
    """Generate price chart with SMAs and volume."""
    _setup_style()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(CS["fig_width"], CS["fig_height"] + 2),
                                     gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    fig.subplots_adjust(hspace=0.05)

    dates = history.index
    close = history["Close"]

    # Price line
    ax1.plot(dates, close, color=CS["accent_blue"], linewidth=1.5, label="Price", zorder=3)

    # SMAs
    sma_colors = {20: CS["accent_cyan"], 50: CS["accent_orange"], 200: CS["accent_purple"]}
    for w, c in sma_colors.items():
        col = f"SMA_{w}"
        if col in history.columns:
            ax1.plot(dates, history[col], color=c, linewidth=1, alpha=0.7, label=f"SMA {w}")

    # Bollinger Bands
    if "BB_Upper" in history.columns:
        ax1.fill_between(dates, history["BB_Lower"], history["BB_Upper"],
                         alpha=0.08, color=CS["accent_blue"])

    ax1.set_title(f"{ticker} — Price & Moving Averages", fontsize=14, fontweight="bold", pad=15)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))
    ax1.grid(True, alpha=0.2)

    # Volume bars
    if "Volume" in history.columns:
        colors = [CS["accent_green"] if close.iloc[i] >= close.iloc[max(0, i-1)]
                  else CS["accent_red"] for i in range(len(close))]
        ax2.bar(dates, history["Volume"], color=colors, alpha=0.6, width=0.8)
        ax2.set_ylabel("Volume", fontsize=9)
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.0f}M"))

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=CS["bg_color"])
    plt.close(fig)
    return output_path


def generate_rsi_chart(history, ticker, output_path):
    """Generate RSI chart."""
    _setup_style()
    if "RSI" not in history.columns:
        return None
    fig, ax = plt.subplots(figsize=(CS["fig_width"], 3))
    dates = history.index
    rsi = history["RSI"]
    ax.plot(dates, rsi, color=CS["accent_purple"], linewidth=1.5)
    ax.axhline(70, color=CS["accent_red"], linestyle="--", alpha=0.5, label="Overbought (70)")
    ax.axhline(30, color=CS["accent_green"], linestyle="--", alpha=0.5, label="Oversold (30)")
    ax.fill_between(dates, 70, rsi, where=(rsi >= 70), alpha=0.15, color=CS["accent_red"])
    ax.fill_between(dates, 30, rsi, where=(rsi <= 30), alpha=0.15, color=CS["accent_green"])
    ax.set_ylim(0, 100)
    ax.set_title(f"{ticker} — RSI (14)", fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.3)
    ax.grid(True, alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=CS["bg_color"])
    plt.close(fig)
    return output_path


def generate_macd_chart(history, ticker, output_path):
    """Generate MACD chart."""
    _setup_style()
    if "MACD" not in history.columns:
        return None
    fig, ax = plt.subplots(figsize=(CS["fig_width"], 3))
    dates = history.index
    ax.plot(dates, history["MACD"], color=CS["accent_blue"], linewidth=1.2, label="MACD")
    ax.plot(dates, history["MACD_Signal"], color=CS["accent_orange"], linewidth=1.2, label="Signal")
    colors = [CS["accent_green"] if v >= 0 else CS["accent_red"] for v in history["MACD_Hist"]]
    ax.bar(dates, history["MACD_Hist"], color=colors, alpha=0.5, width=0.8)
    ax.axhline(0, color=CS["text_color"], linewidth=0.5, alpha=0.3)
    ax.set_title(f"{ticker} — MACD", fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
    ax.grid(True, alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=CS["bg_color"])
    plt.close(fig)
    return output_path


def generate_financials_chart(financials, ticker, output_path):
    """Generate revenue & net income bar chart."""
    _setup_style()
    if financials is None or financials.empty:
        return None
    fig, ax = plt.subplots(figsize=(CS["fig_width"], CS["fig_height"]))
    rev_row = None
    inc_row = None
    for name in ["Total Revenue", "TotalRevenue"]:
        if name in financials.index:
            rev_row = name
            break
    for name in ["Net Income", "NetIncome"]:
        if name in financials.index:
            inc_row = name
            break
    if rev_row is None:
        plt.close(fig)
        return None
    dates = [str(d.year) if hasattr(d, "year") else str(d)[:4] for d in financials.columns]
    dates.reverse()
    rev = financials.loc[rev_row].values[::-1] / 1e9
    x = np.arange(len(dates))
    w = 0.35
    ax.bar(x - w/2, rev, w, label="Revenue ($B)", color=CS["accent_blue"], alpha=0.8)
    if inc_row:
        inc = financials.loc[inc_row].values[::-1] / 1e9
        ax.bar(x + w/2, inc, w, label="Net Income ($B)", color=CS["accent_green"], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(dates)
    ax.set_title(f"{ticker} — Revenue & Net Income", fontsize=14, fontweight="bold")
    ax.legend(fontsize=9, framealpha=0.3)
    ax.grid(True, alpha=0.2, axis="y")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.1fB"))
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=CS["bg_color"])
    plt.close(fig)
    return output_path


def generate_returns_chart(history, ticker, output_path):
    """Generate cumulative returns chart."""
    _setup_style()
    if "Cumulative_Return" not in history.columns:
        return None
    fig, ax = plt.subplots(figsize=(CS["fig_width"], 4))
    dates = history.index
    cum = history["Cumulative_Return"] * 100
    ax.fill_between(dates, 0, cum, alpha=0.15, color=CS["accent_blue"])
    ax.plot(dates, cum, color=CS["accent_blue"], linewidth=1.5)
    ax.axhline(0, color=CS["text_color"], linewidth=0.5, alpha=0.3)
    ax.set_title(f"{ticker} — Cumulative Returns", fontsize=12, fontweight="bold")
    ax.set_ylabel("Return (%)")
    ax.grid(True, alpha=0.2)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=CS["bg_color"])
    plt.close(fig)
    return output_path


def generate_all_charts(stock_data, output_dir):
    """Generate all charts and return paths dict."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    t = stock_data["ticker"]
    h = stock_data["history_1y"]
    charts = {}
    if not h.empty:
        charts["price"] = str(generate_price_chart(h, t, output_dir / f"{t}_price.png"))
        rsi = generate_rsi_chart(h, t, output_dir / f"{t}_rsi.png")
        if rsi: charts["rsi"] = str(rsi)
        macd = generate_macd_chart(h, t, output_dir / f"{t}_macd.png")
        if macd: charts["macd"] = str(macd)
        ret = generate_returns_chart(h, t, output_dir / f"{t}_returns.png")
        if ret: charts["returns"] = str(ret)
    fin = generate_financials_chart(stock_data["financials"], t, output_dir / f"{t}_financials.png")
    if fin: charts["financials"] = str(fin)
    return charts
