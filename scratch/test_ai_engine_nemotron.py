import json
import sys
import time


sys.path.insert(0, "app")

from ai_engine import _call_llm


messages = [
    {
        "role": "system",
        "content": (
            "Return ONLY valid JSON. Use private reasoning but output only conclusions. "
            "Be beginner-clear and grounded in the data."
        ),
    },
    {
        "role": "user",
        "content": (
            "Ticker ABC: price 100, fair value 80, revenue growth -5%, high debt, "
            "falling free cash flow. Give verdict, confidence, three risks, and one plain-English reason."
        ),
    },
]

started = time.time()
result = _call_llm(messages, max_tokens=900)

print(f"SECONDS={round(time.time() - started, 2)}")
print(json.dumps(result, indent=2))
