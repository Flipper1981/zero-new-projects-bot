import requests
import os
from datetime import datetime, timezone, timedelta

# Secrets genau so verwenden wie du sie angelegt hast
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]   # ← passt zu deinem Secret-Namen!

# Temporäre Datei für den letzten Check-Zeitpunkt
LAST_CHECK_FILE = "/tmp/last_check.txt"


def get_last_check_time():
    try:
        with open(LAST_CHECK_FILE) as f:
            return datetime.fromisoformat(f.read().strip())
    except:
        # Erster Lauf: vor 7 Tagen starten
        return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_check_time():
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


def check_new_projects():
    since = get_last_check_time().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Suche nach neuen Repos mit Topic flipperzero
    url = f"https://api.github.com/search/repositories?q=topic:flipperzero+created:>{since}&sort=created&order=desc&per_page=10"
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
    except Exception as e:
        print("GitHub API Fehler:", str(e))
        save_last_check_time()
        return
    
    items = resp.json().get("items", [])
    if not items:
        print("Keine neuen Projekte gefunden")
        save_last_check_time()
        return
    
    sent = 0
    for repo in items:
        if sent >= 3:  # max. 3 Posts pro Durchlauf
            break
            
        created = repo["created_at"][:10]
        name = repo["full_name"]
        url_repo = repo["html_url"]
        desc = (repo["description"] or "Keine Beschreibung").strip()[:140]
        stars = repo["stargazers_count"]
        
        message = f"""🆕 <b>Neues Flipper Zero Projekt!</b>
<b>{name}</b>
⭐ {stars} • {created}
{desc}

{url_repo}"""
        
        send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        
        try:
            r = requests.post(send_url, json=payload, timeout=10)
            r.raise_for_status()
            print(f"Erfolgreich gesendet: {name}")
            sent += 1
        except Exception as e:
            print("Telegram Fehler:", str(e))
    
    save_last_check_time()


if __name__ == "__main__":
    print("Check startet...")
    check_new_projects()
    print("Check beendet.")
