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
    "model": "llama-3.3-70b-versatile",
    "messages": messages,
    "temperature": 0.3,
    "max_tokens": 900,
    "response_format": {"type": "json_object"},
}

headers = {
    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}",
    "Content-Type": "application/json",
}

started = time.time()
response = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=90,
)
seconds = round(time.time() - started, 2)

print(f"MODEL=Groq Llama 3.3 70B")
print(f"SECONDS={seconds}")
print(f"STATUS={response.status_code}")

try:
    data = response.json()
    print("OUTPUT=")
    print(data.get("choices", [{}])[0].get("message", {}).get("content") or json.dumps(data, indent=2))
except Exception:
    print("OUTPUT=")
    print(response.text)
