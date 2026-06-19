"""
Configuration & Settings for AI Stock Analyzer
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ─── API Configuration ───────────────────────────────────────────────
raw_groq_key = os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS = []
if raw_groq_key:
    GROQ_API_KEYS.extend([k.strip() for k in raw_groq_key.split(",") if k.strip()])

# Check for additional key environment variables GROQ_API_KEY_2, GROQ_API_KEY_3...
idx = 2
while True:
    extra_key = os.getenv(f"GROQ_API_KEY_{idx}", "")
    if not extra_key:
        extra_key = os.getenv(f"GROQ_API_KEY{idx}", "")
    if not extra_key:
        break
    GROQ_API_KEYS.append(extra_key.strip())
    idx += 1

if GROQ_API_KEYS:
    GROQ_API_KEY = GROQ_API_KEYS[0]
else:
    GROQ_API_KEY = ""

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS = 3500
GROQ_TEMPERATURE = 0.3  # Lower = more focused/factual

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "AI Stock Analyzer research contact@example.com")

# ─── Notion API Configuration ───────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID", "")

# ─── Claude, Qwen & Gemini Configuration ────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
raw_openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_KEYS = []
if raw_openrouter_key:
    OPENROUTER_API_KEYS.extend([k.strip() for k in raw_openrouter_key.split(",") if k.strip()])

idx = 2
while True:
    extra_key = os.getenv(f"OPENROUTER_API_KEY_{idx}", "")
    if not extra_key:
        extra_key = os.getenv(f"OPENROUTER_API_KEY{idx}", "")
    if not extra_key:
        break
    OPENROUTER_API_KEYS.append(extra_key.strip())
    idx += 1

OPENROUTER_API_KEY = OPENROUTER_API_KEYS[0] if OPENROUTER_API_KEYS else ""
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "60"))
OPENROUTER_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0.25"))

raw_gemini_key = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = []
if raw_gemini_key:
    GEMINI_API_KEYS.extend([k.strip() for k in raw_gemini_key.split(",") if k.strip()])

# Check for additional key environment variables GEMINI_API_KEY_2, GEMINI_API_KEY_3...
idx = 2
while True:
    extra_key = os.getenv(f"GEMINI_API_KEY_{idx}", "")
    if not extra_key:
        extra_key = os.getenv(f"GEMINI_API_KEY{idx}", "")
    if not extra_key:
        break
    GEMINI_API_KEYS.append(extra_key.strip())
    idx += 1

if GEMINI_API_KEYS:
    GEMINI_API_KEY = GEMINI_API_KEYS[0]
else:
    GEMINI_API_KEY = ""

# ─── Free Financial APIs ────────────────────────────────────────────
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FMP_API_KEY = os.getenv("FMP_API_KEY", "")
TIINGO_API_KEY = os.getenv("TIINGO_API_KEY", "")

# ─── OPENCODE ZEN API CONFIG ───────────────────────────────────────
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")
OPENCODE_BASE_URL = "https://opencode.ai/zen/v1/chat/completions"
OPENCODE_MODEL = "north-mini-code-free"

# ─── NVIDIA NEMOTRON CONFIG ─────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# ─── Paths ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"

# ─── Chart Styling ───────────────────────────────────────────────────
CHART_STYLE = {
    "bg_color": "#09090b",
    "text_color": "#fafafa",
    "grid_color": "#27272a",
    "accent_green": "#10b981",
    "accent_red": "#ef4444",
    "accent_blue": "#2563eb",
    "accent_purple": "#8b5cf6",
    "accent_orange": "#f59e0b",
    "accent_cyan": "#06b6d4",
    "font_family": "sans-serif",
    "fig_width": 10,
    "fig_height": 5,
}

# ─── Excel Styling ───────────────────────────────────────────────────
EXCEL_COLORS = {
    "header_bg": "#0e0e11",
    "header_font": "#fafafa",
    "positive": "#10b981",
    "negative": "#ef4444",
    "accent": "#2563eb",
    "border": "#27272a",
}

# ─── Analysis Periods ────────────────────────────────────────────────
HISTORY_PERIOD_SHORT = "1y"
HISTORY_PERIOD_LONG = "5y"
SMA_WINDOWS = [20, 50, 200]

raw_gemini_key = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = []
if raw_gemini_key:
    GEMINI_API_KEYS.extend([k.strip() for k in raw_gemini_key.split(",") if k.strip()])

# Check for additional key environment variables GEMINI_API_KEY_2, GEMINI_API_KEY_3...
idx = 2
while True:
    extra_key = os.getenv(f"GEMINI_API_KEY_{idx}", "")
    if not extra_key:
        extra_key = os.getenv(f"GEMINI_API_KEY{idx}", "")
    if not extra_key:
        break
    GEMINI_API_KEYS.append(extra_key.strip())
    idx += 1

if GEMINI_API_KEYS:
    GEMINI_API_KEY = GEMINI_API_KEYS[0]
else:
    GEMINI_API_KEY = ""

# ─── Free Financial APIs ────────────────────────────────────────────
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FMP_API_KEY = os.getenv("FMP_API_KEY", "")
TIINGO_API_KEY = os.getenv("TIINGO_API_KEY", "")

# ─── OPENCODE ZEN API CONFIG ───────────────────────────────────────
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")
OPENCODE_BASE_URL = "https://opencode.ai/zen/v1/chat/completions"
OPENCODE_MODEL = "north-mini-code-free"

# ─── NVIDIA NEMOTRON CONFIG ─────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# ─── Paths ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"

# ─── Chart Styling ───────────────────────────────────────────────────
CHART_STYLE = {
    "bg_color": "#09090b",
    "text_color": "#fafafa",
    "grid_color": "#27272a",
    "accent_green": "#10b981",
    "accent_red": "#ef4444",
    "accent_blue": "#2563eb",
    "accent_purple": "#8b5cf6",
    "accent_orange": "#f59e0b",
    "accent_cyan": "#06b6d4",
    "font_family": "sans-serif",
    "fig_width": 10,
    "fig_height": 5,
}

# ─── Excel Styling ───────────────────────────────────────────────────
EXCEL_COLORS = {
    "header_bg": "#0e0e11",
    "header_font": "#fafafa",
    "positive": "#10b981",
    "negative": "#ef4444",
    "accent": "#2563eb",
    "border": "#27272a",
}

# ─── Analysis Periods ────────────────────────────────────────────────
HISTORY_PERIOD_SHORT = "1y"
HISTORY_PERIOD_LONG = "5y"
SMA_WINDOWS = [20, 50, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ─── Feature Flags ───────────────────────────────────────────────────
FEATURE_FLAGS = {
    "USE_NEW_DASHBOARD": True,
    "ENABLE_RATE_LIMITING": True,
    "ENABLE_PORTFOLIO": True,
    "ENABLE_NEWS_AGGREGATE": True
}


def validate_config():
    """Check that required configuration is present."""
    import logging
    logger = logging.getLogger(__name__)
    
    is_valid = True
    
    if not OPENROUTER_API_KEY:
        msg = (
            "\n[WARNING] No OpenRouter API key found.\n"
            "   1. Go to https://openrouter.ai and create an API key\n"
            "   2. Copy your API key\n"
            "   3. Create a .env file with: OPENROUTER_API_KEY=your_key_here\n"
            "   Or run setup.bat for guided setup.\n"
        )
        print(msg)
        logger.warning(msg)
        is_valid = False
        
    if not GROQ_API_KEY:
        logger.warning("No GROQ_API_KEY found. AI Engine features may be disabled or fall back to OpenRouter.")
        
    return is_valid
