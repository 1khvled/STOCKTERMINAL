import json
import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

PROMPT_MESSAGES = [
    {
        "role": "system",
        "content": (
            "Return ONLY valid JSON. You are judging a stock idea for a beginner investor. "
            "Be concise, specific, and grounded in the supplied data."
        ),
    },
    {
        "role": "user",
        "content": (
            "Using only this data: Ticker ABC, price 100, fair value 80, revenue growth -5%, "
            "debt high, free cash flow falling. Give verdict, confidence 0-100, 3 risks, "
            "and a plain-English reason."
        ),
    },
]


def call_model(name, url, headers, body):
    try:
        started = time.time()
        response = requests.post(url, headers=headers, json=body, timeout=60)
        seconds = round(time.time() - started, 2)
        print(f"\n===== {name} seconds={seconds} status={response.status_code} =====")
        text = response.text
        try:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            print(content or json.dumps(data, indent=2)[:2500])
        except Exception:
            print(text[:2500])
    except Exception as exc:
        print(f"\n===== {name} ERROR =====")
        print(str(exc)[:1200])


def main():
    openrouter_body = {
        "model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        "messages": PROMPT_MESSAGES,
        "max_tokens": 700,
        "temperature": 0.3,
        "reasoning": {"enabled": True},
        "response_format": {"type": "json_object"},
    }
    openrouter_headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://127.0.0.1:5001",
        "X-Title": "Stock Terminal",
    }
    call_model(
        "OPENROUTER NEMOTRON SAFETY",
        "https://openrouter.ai/api/v1/chat/completions",
        openrouter_headers,
        openrouter_body,
    )

    groq_body = {
        "model": "llama-3.3-70b-versatile",
        "messages": PROMPT_MESSAGES,
        "max_tokens": 700,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    groq_headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    call_model(
        "GROQ LLAMA 3.3 70B",
        "https://api.groq.com/openai/v1/chat/completions",
        groq_headers,
        groq_body,
    )


if __name__ == "__main__":
    main()
