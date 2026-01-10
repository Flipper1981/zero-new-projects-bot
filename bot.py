import os
import requests
from datetime import datetime, timezone, timedelta

# Secrets holen – genau deine Namen!
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]

LAST_CHECK_FILE = "/tmp/last_check.txt"

def get_last_check():
    try:
        with open(LAST_CHECK_FILE) as f:
            return datetime.fromisoformat(f.read().strip())
    except:
        return datetime.now(timezone.utc) - timedelta(days=7)

def save_last_check():
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())

def main():
    since = get_last_check().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = f"https://api.github.com/search/repositories?q=topic:flipperzero+created:>{since}&sort=created&order=desc&per_page=5"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        items = r.json()["items"]
    except Exception as e:
        print("GitHub API Fehler:", str(e))
        save_last_check()
        return
    
    if not items:
        print("Keine neuen Projekte")
        save_last_check()
        return
    
    sent = 0
    for repo in items:
        if sent >= 3:
            break
        msg = f"🆕 {repo['full_name']}\n{repo['html_url']}"
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHANNEL, "text": msg}
            ).raise_for_status()
            print("Gesendet:", repo['full_name'])
            sent += 1
        except Exception as e:
            print("Send-Fehler:", str(e))
    
    save_last_check()

if __name__ == "__main__":
    main()
