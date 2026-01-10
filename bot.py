import requests
import os
import json
from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Set
import re

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)

STATE_FILE = "/tmp/flipper_state.json"

FLIPPER_QUERIES = [
    'topic:flipperzero OR topic:"flipper-zero" OR topic:flipperzero-firmware OR topic:flipper-plugin',
    '"flipper zero" OR flipperzero OR fap OR "flipper app" OR protpiratein OR protpirate',
    'subghz OR nfc OR rfid OR badusb OR ibutton OR gpio OR infrared OR "flipper mod"',
    'unleashed-firmware OR rogiemaster OR momentum-firmware OR xtreme-firmware OR darkflippers',
    'flipperzero OR "flipper zero" pushed:>2026-01-09 OR updated:>2026-01-09'
]

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state["posted_events"] = set(state.get("posted_events", []))
            state["known_repos"] = set(state.get("known_repos", []))
            state["repo_states"] = state.get("repo_states", {})
            return state
    except:
        return {"known_repos": set(), "posted_events": set(), "repo_states": {}}

def save_state(state: Dict):
    save_state = state.copy()
    save_state["posted_events"] = list(state["posted_events"])
    save_state["known_repos"] = list(state["known_repos"])
    with open(STATE_FILE, 'w') as f:
        json.dump(save_state, f, indent=2)

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def ultimate_flipper_search(state: Dict) -> List[str]:
    print("🔥 ULTIMATIVE FLIPPER SUCHE STARTET!")
    all_repos: Set[str] = set(state["known_repos"])
    
    for q_num, query in enumerate(FLIPPER_QUERIES, 1):
        print(f"Query {q_num}/5: {query[:60]}")
        for page in range(1, 21):
            url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=30&page={page}"
            try:
                resp = requests.get(url, headers=get_headers(), timeout=25)
                if resp.status_code == 403:
                    print("Rate limit - warte 90s...")
                    time.sleep(90)
                    page -= 1
                    continue
                data = resp.json()
                total = data.get("total_count", 0)
                items = data.get("items", [])
                
                hits = 0
                for item in items:
                    repo_name = item["full_name"]
                    topics = item.get("topics", [])
                    text = (item["description"] or "" + item["name"]).lower()
                    
                    if ("flipperzero" in topics or "flipper-zero" in topics or 
                        re.search(r'flipper| fap |subghz|nfc|protpirate', text)):
                        all_repos.add(repo_name)
                        hits += 1
                
                print(f"  Seite {page}: {hits} Treffer | API Total: {total}")
                if len(items) < 30:
                    break
                time.sleep(1.3)
                
            except Exception as e:
                print(f"  Fehler: {e}")
                break
    
    state["known_repos"] = all_repos
    print(f"Total UNIQUE FLIPPER REPOS: {len(all_repos)}")
    return sorted(list(all_repos))

def deep_repo_scan(repo_name: str, state: Dict) -> List[Dict]:
    updates = []
    repo_state = state["repo_states"].get(repo_name, {})
    posted = state["posted_events"]
    
    try:
        # 1. RELEASES
        releases = requests.get(f"https://api.github.com/repos/{repo_name}/releases",
                               headers=get_headers()).json()
        if releases:
            latest = releases[0]
            last_tag = repo_state.get("last_release_tag")
            if last_tag != latest["tag_name"]:
                event_id = f"REL:{repo_name}:{latest['tag_name']}"
                if event_id not in posted:
                    updates.append({
                        "type": "RELEASE", "repo": repo_name,
                        "tag": latest["tag_name"],
                        "name": latest.get("name", "Update"),
                        "time": latest["published_at"][:19],
                        "url": latest["html_url"]
                    })
        
        # 2. COMMITS + FILES
        commits = requests.get(f"https://api.github.com/repos/{repo_name}/commits?per_page=5",
                              headers=get_headers()).json()
        if commits:
            latest_commit = commits[0]
            last_sha = repo_state.get("last_commit_sha")
            if last_sha != latest_commit["sha"]:
                files = latest_commit.get("files", [])
                flipper_files = [f for f in files if is_flipper_file(f.get("filename", ""))]
                if flipper_files:
                    event_id = f"COMMIT:{repo_name}:{latest_commit['sha'][:7]}"
                    if event_id not in posted:
                        updates.append({
                            "type": "COMMIT", "repo": repo_name,
                            "sha": latest_commit["sha"][:7],
                            "files": [f["filename"] for f in flipper_files],
                            "msg": latest_commit["commit"]["message"][:100],
                            "url": latest_commit["html_url"]
                        })
        
        # 3. PRs/Issues
        for typ, endpoint in [("PR", "pulls"), ("ISSUE", "issues")]:
            items = requests.get(f"https://api.github.com/repos/{repo_name}/{endpoint}",
                                headers=get_headers()).json()
            if items:
                latest = items[0]
                event_id = f"{typ}:{repo_name}:{latest['number']}"
                if event_id not in posted:
                    updates.append({
                        "type": typ, "repo": repo_name,
                        "title": latest["title"][:80],
                        "num": latest["number"],
                        "url": latest["html_url"]
                    })
    
    except:
        pass
    
    return updates

def is_flipper_file(filename: str) -> bool:
    patterns = [r'\.fap$', r'\.c$', r'\.h$', r'applications/', r'firmware/', r'subghz/']
    return any(re.search(p, filename.lower()) for p in patterns)

def post_all_updates(updates: List[Dict]):
    for update in updates[:25]:
        repo_link = f"<a href=\"https://github.com/{update['repo']}\">{update['repo']}</a>"
        
        if update["type"] == "RELEASE":
            msg = f"""🚀 <b>NEUER RELEASE!</b>

{repo_link}
⏰ {update.get('time', 'Gerade')}
🏷️ <code>{update['tag']}</code>
<i>{update.get('name', '')}</i>

<a href=\"{update['url']}\">📥 Download</a>"""
        elif update["type"] == "COMMIT":
            files_str = " | ".join(update["files"][:2])
            msg = f"""💾 <b>COMMIT ÄNDERUNG!</b>

{repo_link}
<code>{update['sha']}</code>
📁 {files_str}
📝 {update['msg']}

<a href=\"{update['url']}\">🔗 Commit</a>"""
        else:
            emoji = {"PR": "🔄", "ISSUE": "🐛"}[update["type"]]
            msg = f"""{emoji} <b>{update['type']}!</b>

{repo_link}
#{update['num']}: {update['title']}

<a href=\"{update['url']}\">👁️ Öffnen</a>"""
        
        send_message(msg)
        time.sleep(0.4)

def send_message(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHANNEL, "text": msg, "parse_mode": "HTML",
        "disable_web_page_preview": False, "message_thread_id": 40
    }
    try:
        r = requests.post(url, json=data, timeout=12)
        r.raise_for_status()
        print("✅ Gesendet!")
    except Exception as e:
        print(f"❌ {e}")

def main():
    state = load_state()
    print("🎯 FLIPPER ZERO - J E D E Ä N D E R U N G !")
    
    repos = ultimate_flipper_search(state)
    
    print(f"🛠️ Scan {min(200, len(repos))} Repos...")
    all_updates = []
    
    for i, repo in enumerate(repos[:200]):
        updates = deep_repo_scan(repo, state)
        all_updates.extend(updates)
        if updates:
            print(f"  {i+1}: {repo} = {len(updates)} Updates")
        time.sleep(0.18)
    
    if all_updates:
        post_all_updates(all_updates)
        print(f"\n🎉 {len(all_updates)} FLIPPER UPDATES gepostet!")
    else:
        print("\nℹ️ Aktuell keine Änderungen")
    
    save_state(state)

if __name__ == "__main__":
    main()
