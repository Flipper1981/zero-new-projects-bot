import requests
import os
import json
from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Set

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)

STATE_FILE = "/tmp/flipper_state.json"

# Dynamische Liste: Alle bekannten Flipper-Repos (erweitert alle 24h)
def get_flipper_repos() -> List[str]:
    return [
        "flipperdevices/flipperzero-firmware", "DarkFlippers/unleashed-firmware",
        "RogueMaster/flipperzero-firmware-wPlugins", "Next-Flip/Momentum-Firmware",
        "Flipper-XFW/Xtreme-Firmware", "xMasterX/all-the-plugins",
        "djsime1/awesome-flipperzero", "UberGuidoZ/Flipper",
        "xMasterX/fap-store", "jblanked/WebCrawler-FlipperZero",
        "UberGuidoZ/Flipper_Zero-BadUsb", "FalsePhilosopher/badusb",
        # Dynamisch laden (aus State oder API)
    ]

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"repos": {}, "last_full_scan": None, "posted_events": set()}

def save_state(state: Dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def discover_flipper_repos(state: Dict) -> List[str]:
    """Schritt 1: Alle Repos mit topic:flipperzero finden (max Coverage)"""
    since = state.get("last_full_scan", (datetime.now(timezone.utc) - timedelta(days=30)).isoformat())
    all_repos: Set[str] = set()
    
    # Multi-Page Topic-Suche (GitHub limitiert 1000, aber wir paginieren)
    for page in range(1, 35):  # Bis ~1000 Repos
        q = f"topic:flipperzero OR topic:flipper-zero OR topic:flipperzero-firmware"
        url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=30&page={page}"
        try:
            resp = requests.get(url, headers=get_headers(), timeout=20)
            if resp.status_code == 403:
                time.sleep(60)
                continue
            data = resp.json()
            if not data.get("items"):
                break
            for item in data["items"]:
                repo_name = item["full_name"]
                if item.get("stargazers_count", 0) >= 0:  # Alle, auch 0 Stars
                    all_repos.add(repo_name)
            print(f"Seite {page}: {len(data['items'])} Repos gefunden. Total: {len(all_repos)}")
            time.sleep(1.2)  # Rate limit (40/min authenticated)
        except Exception as e:
            print(f"Discovery Fehler Seite {page}: {e}")
            break
    
    # Speichere Liste
    state["known_flipper_repos"] = list(all_repos)
    state["last_full_scan"] = datetime.now(timezone.utc).isoformat()
    print(f"🔍 {len(all_repos)} einzigartige Flipper-Repos entdeckt!")
    return list(all_repos)

def check_all_repo_changes(state: Dict, repos: List[str]) -> List[Dict]:
    """Schritt 2: JEDES Repo auf Änderungen prüfen (Commits/Files/Pushes)"""
    new_changes = []
    posted = state.get("posted_events", set())
    last_check = state.get("repos", {})
    
    for i, repo in enumerate(repos[:100]):  # Top 100 priorisieren (performant)
        if repo in last_check and (datetime.now(timezone.utc) - datetime.fromisoformat(last_check[repo])).seconds < 1800:
            continue  # Schon kürzlich geprüft (30min)
        
        changes = check_single_repo(repo)
        for change in changes:
            event_id = f"{repo}:{change['type']}:{change['sha'][:7]}:{change.get('path', '')}"
            if event_id not in posted:
                new_changes.append({"repo": repo, **change})
                posted.add(event_id)
        
        state["repos"][repo] = datetime.now(timezone.utc).isoformat()
        if i % 10 == 0:
            time.sleep(0.5)  # Pace selbst
    
    state["posted_events"] = posted
    return new_changes

def check_single_repo(repo_name: str) -> List[Dict]:
    """Prüft ein Repo: Neueste Commits + geänderte Dateien"""
    changes = []
    try:
        # Neueste Commits (letzten Tag)
        url_commits = f"https://api.github.com/repos/{repo_name}/commits?per_page=5&since={(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat()}"
        commits = requests.get(url_commits, headers=get_headers()).json()
        
        for commit in commits:
            files = commit.get("files", [])
            for file in files:
                if is_flipper_file(file.get("filename", "")):
                    changes.append({
                        "type": "file_change",
                        "sha": commit["sha"],
                        "message": commit["commit"]["message"][:100],
                        "path": file["filename"],
                        "additions": file.get("additions", 0),
                        "deletions": file.get("deletions", 0),
                        "status": file.get("status", ""),
                        "url": commit["html_url"]
                    })
                    break  # Nur 1 pro Commit
        
        # Neueste Release/PR/Issue (wie vorher)
        # ... (integriere check_new_releases etc. für dieses Repo)
        
    except Exception as e:
        print(f"Repo-Check Fehler {repo_name}: {e}")
    
    return changes

def is_flipper_file(filename: str) -> bool:
    """File relevant für Flipper? (.fap, .c, applications/ etc.)"""
    flipper_ext = ['.fap', '.c', '.h', '.cpp', '.S', '.ld', 'application.fam', 'Makefile']
    paths = ['applications/', 'firmware/', 'lib/', 'subghz/', 'nfc/']
    return any(ext in filename for ext in flipper_ext) or any(path in filename for path in paths)

def post_changes(changes: List[Dict]):
    """Poste ALLE Änderungen mit File-Details"""
    for change in changes[:15]:  # Max 15 pro Run
        repo = change["repo"]
        emoji = "✏️" if change["status"] == "modified" else "➕" if change["status"] == "added" else "➖"
        message = f"""{emoji} <b>Datei-Änderung in <a href="https://github.com/{repo}">{repo}</a></b>

📄 <b>{change['path']}</b>
💬 <code>{change['message']}</code>
🔄 {change['status'].upper()} | +{change['additions']} -{change['deletions']}

<a href="{change['url']}">🔗 Commit ansehen</a>"""
        send_message(message)
        time.sleep(0.3)  # Telegram Pace

def send_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL, "text": message, "parse_mode": "HTML",
        "disable_web_page_preview": False, "message_thread_id": 40
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Send Fehler: {e}")

def main():
    state = load_state()
    
    # 1. Entdecke alle flipperzero-topic Repos (täglich)
    if not state.get("known_flipper_repos") or (datetime.now(timezone.utc) - datetime.fromisoformat(state["last_full_scan"])).days > 1:
        repos = discover_flipper_repos(state)
    else:
        repos = state["known_flipper_repos"]
    
    # 2. Prüfe JEDES Repo auf File-Änderungen (auch alte Repos)
    changes = check_all_repo_changes(state, repos)
    
    if changes:
        post_changes(changes)
        print(f"✅ {len(changes)} Änderungen in Flipper Repos gepostet!")
    else:
        print("Keine neuen File-Änderungen.")
    
    save_state(state)

if __name__ == "__main__":
    main()
