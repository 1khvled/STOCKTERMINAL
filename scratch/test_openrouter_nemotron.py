import json
import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

messages = [
    {
        "role": "system",
        "content": (
            "Return ONLY valid JSON. You are a careful stock analyst for a beginner. "
            "Use only the supplied data. Be concise, specific, and avoid hype."
        ),
    },
    {
        "role": "user",
        "content": (
            "Stock test case: Ticker ABC. Current price: 100. Fair value estimate: 80. "
            "Revenue growth: -5%. Debt: high. Free cash flow: falling. "
            "Question: give a verdict, confidence 0-100, three specific risks, "
            "and a plain-English explanation."
        ),
    },
]

payload = {
    "model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    "messages": messages,
    "reasoning": {"enabled": True},
    "temperature": 0.3,
    "max_tokens": 900,
    "response_format": {"type": "json_object"},
}

headers = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://127.0.0.1:5001",
    "X-Title": "Stock Terminal",
}

started = time.time()
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=90,
)
seconds = round(time.time() - started, 2)

print(f"MODEL=OpenRouter Nemotron Ultra")
print(f"SECONDS={seconds}")
print(f"STATUS={response.status_code}")

try:
    data = response.json()
    print("OUTPUT=")
    print(data.get("choices", [{}])[0].get("message", {}).get("content") or json.dumps(data, indent=2))
except Exception:
    print("OUTPUT=")
    print(response.text)
