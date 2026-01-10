import requests
import os
import json
from datetime import datetime, timezone

# Secrets
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]

# State-Datei (speichert letzte bekannte Release pro Repo)
STATE_FILE = "/tmp/flipper_release_state.json"

# Liste der wichtigsten Flipper-Repos (erweitere bei Bedarf!)
WATCHED_REPOS = [
    "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins",
    "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware",
    "Flipper-Devices/flipperzero-firmware",  # offiziell
    "djsime1/awesome-flipperzero",           # Liste, könnte Updates haben
    # Füge hier eigene hinzu, z.B. "username/dein-projekt"
]

# Hilfsfunktion: Lade gespeicherten State
def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}  # leer beim ersten Mal

# Hilfsfunktion: Speichere neuen State
def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def check_releases():
    state = load_state()
    new_posts = []

    for repo in WATCHED_REPOS:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=5"  # max 5 neueste holen
        headers = {"Accept": "application/vnd.github.v3+json"}

        try:
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            releases = resp.json()
        except Exception as e:
            print(f"Fehler bei {repo}: {e}")
            continue

        if not releases:
            print(f"Keine Releases in {repo}")
            continue

        latest = releases[0]  # neueste ist immer zuerst
        tag = latest["tag_name"]
        published_at = latest["published_at"]
        name = latest["name"] or tag
        body = latest["body"] or "Keine Beschreibung"
        if len(body) > 200:
            body = body[:197] + "..."

        # Letzte bekannte für dieses Repo
        last_tag = state.get(repo, {}).get("last_tag")

        if last_tag != tag:
            # Neu!
            message = f"""🆕 <b>Update in {repo}!</b>

<b>{name}</b> ({tag})
📅 {published_at[:10]}
{body[:200]}...

🔗 {latest["html_url"]}"""

            new_posts.append(message)

            # State updaten
            state[repo] = {"last_tag": tag, "last_published": published_at}

    if new_posts:
        sent = 0
        for msg in new_posts:
            if sent >= 3:  # max 3 pro Lauf
                break
            payload = {
                "chat_id": TELEGRAM_CHANNEL,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json=payload,
                    timeout=10
                )
                r.raise_for_status()
                print("Gesendet Update aus:", msg.splitlines()[1])
                sent += 1
            except Exception as e:
                print("Telegram Fehler:", e)

    # State speichern
    save_state(state)

    if not new_posts:
        print("Keine neuen Releases gefunden")

    print("Check beendet")


if __name__ == "__main__":
    print("Release-Check startet...")
    check_releases()
