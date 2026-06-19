import os
import socket
import time

import requests
import urllib3.util.connection as urllib3_connection
from dotenv import load_dotenv


urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
load_dotenv(".env")

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://127.0.0.1:5001",
    "X-Title": "Stock Terminal",
}
base = {
    "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "messages": [{"role": "user", "content": 'Return only JSON: {"ok": true}'}],
    "max_tokens": 80,
    "temperature": 0.1,
}
variants = [
    ("plain", {}),
    ("json_mode", {"response_format": {"type": "json_object"}}),
    ("reasoning", {"reasoning": {"enabled": True}}),
]

for name, extra in variants:
    body = {**base, **extra}
    print(f"\n--- {name} ---", flush=True)
    started = time.time()
    try:
        response = requests.post(url, headers=headers, json=body, timeout=(10, 35))
        print("seconds", round(time.time() - started, 2), "status", response.status_code, flush=True)
        print(response.text[:1000], flush=True)
    except Exception as exc:
        print("seconds", round(time.time() - started, 2), "ERROR", repr(exc), flush=True)
