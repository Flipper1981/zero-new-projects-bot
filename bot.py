#!/usr/bin/env python3
import requests
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
TOPIC_ID = os.environ.get("TOPIC_ID", "")

print(f"CHANNEL_ID: {CHANNEL_ID}")
print(f"TOPIC_ID: {TOPIC_ID}")

msg = f"""🧪 TEST POST

Topic ID: {TOPIC_ID}
Channel ID: {CHANNEL_ID}

Wenn du das in TOPIC 186 siehst: ✅
Wenn du das im Hauptthread siehst: ❌"""

api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

data = {
    'chat_id': CHANNEL_ID,
    'text': msg
}

# WICHTIG: Topic ID setzen
if TOPIC_ID:
    data['message_thread_id'] = int(TOPIC_ID)
    print(f"Poste mit Topic ID: {TOPIC_ID}")
else:
    print("KEIN TOPIC_ID gesetzt!")

resp = requests.post(api_url, json=data)

print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
