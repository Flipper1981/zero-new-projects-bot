import requests
import os
import json
from datetime import datetime, timezone, timedelta

# Secrets
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]

# State-Datei
STATE_FILE = "/tmp/flipper_state.json"

# Top-Repos für Releases (erweiterbar)
WATCHED_REPOS = [
    "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins",
    "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware",
    "Flipper-Devices/flipperzero-firmware",
    "djsime1/awesome-flipperzero",
    "xMasterX/all-the-plugins"
]

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"last_repo_check": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(), "releases": {}}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def check_new_repos(state):
    since = datetime.fromisoformat(state["last_repo_check"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Vereinfachte, aber immer noch breite Suche (GitHub-Limits einhalten!)
    query = f"flipperzero OR \"flipper zero\" OR fap OR plugin OR firmware OR unleashed OR rogue OR momentum created:>{since}"
    url = f"https://api.github.com/search/repositories?q={query}&sort=created&order=desc&per_page=20"
    
    print(f"Repo-Suche: {query}")
    print(f"URL: {url}")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 422:
            print("Query zu komplex – GitHub lehnt ab (422)")
            return []
        resp.raise_for_status()
        items = resp.json().get("items", [])
        print(f"Gefundene neue Repos: {len(items)}")
        return items
    except Exception as e:
        print("Repo-API Fehler:", str(e))
        return []

def check_new_releases(state):
    new_releases = []
    releases_state = state.get("releases", {})
    
    for repo in WATCHED_REPOS:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=3"
        try:
            releases = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"}, timeout=10).json()
            if not releases:
                continue
            
            latest = releases[0]
            tag = latest["tag_name"]
            last_tag = releases_state.get(repo)
            
            if last_tag != tag:
                new_releases.append((repo, latest))  # Repo + Release-Objekt
                releases_state[repo] = tag
                print(f"Neuer Release in {repo}: {tag}")
        except Exception as e:
            print(f"Release-Fehler bei {repo}: {e}")
    
    state["releases"] = releases_state
    return new_releases

def post_findings(items, new_releases):
    sent = 0
    
    # Neue Repos posten
    for repo in items:
        if sent >= 4:
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
        
        send_message(message)
        sent += 1
    
    # Neue Releases posten
    for repo, release in new_releases:
        if sent >= 4:
            break
        tag = release["tag_name"]
        published = release["published_at"][:10]
        name = release["name"] or tag
        body = (release["body"] or "Keine Beschreibung")[:200] + "..."
        
        message = f"""🆕 <b>Neuer Release in {repo}!</b>
<b>{name}</b> ({tag})
📅 {published}
{body}

{release["html_url"]}"""
        
        send_message(message)
        sent += 1

def send_message(message):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "message_thread_id": 40  # Dein Topic!
    }
    try:
        r = requests.post(send_url, json=payload, timeout=10)
        r.raise_for_status()
        print("Gesendet: " + message.splitlines()[0])
    except Exception as e:
        print("Telegram Fehler:", str(e))

def check_flipper_updates():
    state = load_state()
    
    new_repos = check_new_repos(state)
    new_releases = check_new_releases(state)
    
    post_findings(new_repos, new_releases)
    
    state["last_repo_check"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print("Check beendet")

if __name__ == "__main__":
    check_flipper_updates()
