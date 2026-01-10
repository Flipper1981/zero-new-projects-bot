import requests
import os
import json
from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Set
from collections import defaultdict  # Für sichere Serialisierung

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)

STATE_FILE = "/tmp/flipper_state.json"

def get_flipper_repos() -> List[str]:
    return [
        "flipperdevices/flipperzero-firmware", "DarkFlippers/unleashed-firmware",
        "RogueMaster/flipperzero-firmware-wPlugins", "Next-Flip/Momentum-Firmware",
        "Flipper-XFW/Xtreme-Firmware", "xMasterX/all-the-plugins",
        "djsime1/awesome-flipperzero", "UberGuidoZ/Flipper",
        "xMasterX/fap-store", "jblanked/WebCrawler-FlipperZero",
        "UberGuidoZ/Flipper_Zero-BadUsb", "FalsePhilosopher/badusb",
    ]

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            # Konvertiere strings zurück zu sets
            if "posted_events" in state:
                state["posted_events"] = set(state["posted_events"])
            if "known_flipper_repos" in state:
                state["known_flipper_repos"] = list(state["known_flipper_repos"])
            return state
    except:
        return {"repos": {}, "known_flipper_repos": [], "posted_events": set(), "last_full_scan": None}

def save_state(state: Dict):
    # Sets zu lists konvertieren für JSON
    save_state = state.copy()
    if "posted_events" in save_state:
        save_state["posted_events"] = list(save_state["posted_events"])
    if "known_flipper_repos" in save_state and isinstance(save_state["known_flipper_repos"], set):
        save_state["known_flipper_repos"] = list(save_state["known_flipper_repos"])
    with open(STATE_FILE, 'w') as f:
        json.dump(save_state, f)

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def discover_flipper_repos(state: Dict) -> List[str]:
    """Finde alle Repos mit topic:flipperzero (Pagination)"""
    print("🔍 Starte Topic-Discovery...")
    all_repos: Set[str] = set()
    
    for page in range(1, 35):  # Max ~1000 Repos
        q = 'topic:flipperzero OR topic:"flipper-zero" OR topic:flipperzero-firmware'
        url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=30&page={page}"
        print(f"Discovery Seite {page}...")
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=20)
            if resp.status_code == 403:
                print("⏳ Rate limit - warte 60s...")
                time.sleep(60)
                continue
            if resp.status_code != 200:
                print(f"❌ HTTP {resp.status_code}")
                break
                
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
                
            new_on_page = 0
            for item in items:
                repo_name = item["full_name"]
                stars = item.get("stargazers_count", 0)
                if stars >= 0:  # Alle Repos
                    all_repos.add(repo_name)
                    new_on_page += 1
            
            print(f"✅ Seite {page}: {new_on_page} neue. Total: {len(all_repos)}")
            time.sleep(1.2)  # 40/min Rate limit
            
        except Exception as e:
            print(f"❌ Discovery Fehler Seite {page}: {e}")
            break
    
    state["known_flipper_repos"] = list(all_repos)
    state["last_full_scan"] = datetime.now(timezone.utc).isoformat()
    print(f"🎉 {len(all_repos)} Flipper-Repos entdeckt!")
    return list(all_repos)

def is_flipper_file(filename: str) -> bool:
    """Flipper-relevante Datei?"""
    flipper_ext = ['.fap', '.c', '.h', '.cpp', '.S', '.ld', '.json', 'application.fam']
    paths = ['applications/', 'firmware/', 'lib/', 'subghz/', 'nfc/', 'rfid/']
    name_lower = filename.lower()
    return any(ext in name_lower for ext in flipper_ext) or any(path in name_lower for path in paths)

def check_single_repo(repo_name: str) -> List[Dict]:
    """Prüfe EIN Repo auf NEUE File-Änderungen"""
    changes = []
    try:
        # Letzte 10 Commits (24h)
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        url = f"https://api.github.com/repos/{repo_name}/commits"
        params = {"since": since, "per_page": 10}
        
        resp = requests.get(url, headers=get_headers(), params=params, timeout=15)
        commits = resp.json() if resp.status_code == 200 else []
        
        for commit in commits:
            files = commit.get("files", [])
            for file_info in files:
                filename = file_info.get("filename", "")
                if is_flipper_file(filename):
                    changes.append({
                        "type": "file_change",
                        "sha": commit["sha"][:7],
                        "repo": repo_name,
                        "path": filename,
                        "status": file_info.get("status", "modified"),
                        "additions": file_info.get("additions", 0),
                        "deletions": file_info.get("deletions", 0),
                        "message": commit["commit"]["message"][:120],
                        "url": commit["html_url"] + f"#diff-{file_info.get('sha', 'unknown')}"
                    })
        
        print(f"✅ {repo_name}: {len(changes)} relevante File-Changes")
    except Exception as e:
        print(f"❌ {repo_name}: {e}")
    
    return changes

def check_all_repo_changes(state: Dict, repos: List[str]) -> List[Dict]:
    """Prüfe TOP 50 Repos (performant)"""
    new_changes = []
    posted = state.setdefault("posted_events", set())
    repo_checks = state.setdefault("repos", {})
    
    # Priorisiere bekannte + top Repos
    priority_repos = get_flipper_repos() + repos[:20]
    all_repos = list(set(priority_repos))[:50]  # Max 50 pro Run
    
    for repo in all_repos:
        # Skip wenn kürzlich geprüft (<15min)
        last = repo_checks.get(repo)
        if last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).seconds < 900:
            continue
        
        changes = check_single_repo(repo)
        for change in changes:
            event_id = f"{repo}:{change['path']}:{change['sha']}"
            if event_id not in posted:
                new_changes.append(change)
                posted.add(event_id)
        
        repo_checks[repo] = datetime.now(timezone.utc).isoformat()
        time.sleep(0.3)  # Pace
    
    state["posted_events"] = posted
    return new_changes

def post_changes(changes: List[Dict]):
    """Poste ALLE File-Changes"""
    for change in changes[:20]:  # Max 20 pro Run
        emoji = {"added": "➕", "modified": "✏️", "deleted": "➖"}.get(change["status"], "🔄")
        message = f"""{emoji} <b>File-Update: <a href="https://github.com/{change['repo']}">{change['repo']}</a></b>

📁 <code>{change['path']}</code>
💬 <i>{change['message']}</i>
🔄 <b>{change['status'].upper()}</b> | +{change['additions']} -{change['deletions']}

<a href="{change['url']}">🔗 Commit/File</a>"""
        send_message(message)
        time.sleep(0.5)  # Telegram Rate limit

def send_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL, "text": message, "parse_mode": "HTML",
        "disable_web_page_preview": False, "message_thread_id": 40
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("✅ Message gesendet")
    except Exception as e:
        print(f"❌ Send Fehler: {e}")

def main():
    state = load_state()
    print("🚀 Flipper Zero File-Change Bot gestartet")
    
    # Discovery wenn alt (>24h)
    repos = []
    if not state.get("known_flipper_repos") or \
       (datetime.now(timezone.utc) - datetime.fromisoformat(state["last_full_scan"])).days > 1:
        repos = discover_flipper_repos(state)
    else:
        repos = state["known_flipper_repos"]
    
    # Änderungen finden
    changes = check_all_repo_changes(state, repos)
    
    if changes:
        post_changes(changes)
        print(f"🎉 {len(changes)} File-Changes gepostet!")
    else:
        print("ℹ️ Keine neuen Flipper File-Changes")
    
    save_state(state)
    print("✅ Bot fertig")

if __name__ == "__main__":
    main()
