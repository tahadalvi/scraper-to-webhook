"""
Tiny local webhook receiver for testing.

Run:  python webhook_receiver.py
Then point WEBHOOK_URL at http://127.0.0.1:5005/webhook

Every payload is printed and appended to received.jsonl so you can see exactly
what the scraper sends before wiring up the real destination.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)
LOG = Path(__file__).with_name("received.jsonl")


@app.post("/webhook")
def webhook():
    payload = request.get_json(force=True, silent=True) or {}
    record = {"received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "payload": payload}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[{record['received_at']}] {payload.get('count', '?')} items: {payload.get('items')}")
    return jsonify(ok=True, received=payload.get("count", 0))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005)
