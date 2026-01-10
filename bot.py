import requests
import os
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]
LAST_CHECK_FILE = "/tmp/last_check.txt"   # Actions haben kein persistentes Dateisystem!

def get_last_check():
    try:
        with open(LAST_CHECK_FILE) as f:
            return datetime.fromisoformat(f.read().strip())
    except:
        return datetime.now(timezone.utc) - timedelta(days=7)

def save_last_check():
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())

def check_new_flipper_projects():
    since = get_last_check().isoformat()
    url = "https://api.github.com/search/repositories?q=topic:flipperzero+created:>" + since + "&sort=created&order=desc&per_page=10"
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    
    if r.status_code != 200:
        print("GitHub API Fehler:", r.status_code)
        return
    
    items = r.json().get("items", [])
    if not items:
        print("Keine neuen Projekte")
        save_last_check()
        return
    
    for repo in items[:3]:  # max 3 pro Durchlauf
        name = repo["full_name"]
        url = repo["html_url"]
        desc = (repo["description"] or "Keine Beschreibung").strip()[:150]
        stars = repo["stargazers_count"]
        created = repo["created_at"][:10]
        
        message = f"🆕 Neues Flipper Zero Projekt!\n<b>{name}</b>\n⭐ {stars} • {created}\n{desc}\n\n{url}"
        
        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        resp = requests.post(send_url, json=payload)
        if resp.status_code != 200:
            print("Telegram Fehler:", resp.text)
        else:
            print("Gesendet:", name)
    
    save_last_check()

if __name__ == "__main__":
    check_new_flipper_projects()
