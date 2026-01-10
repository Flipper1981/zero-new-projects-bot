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

# VERBESSERTE QUERIES (mehr Coverage + präziser)
FLIPPER_QUERIES = [
    'topic:flipperzero OR topic:"flipper-zero" OR topic:flipperzero-firmware OR topic:flipper-plugin OR topic:flipper-app',
    '"flipper zero" OR flipperzero OR fap OR "flipper app" OR protpiratein OR protpirate',
    'subghz OR nfc OR rfid OR badusb OR ibutton OR gpio OR infrared OR "flipper mod" OR ir',
    'unleashed-firmware OR rogiemaster OR momentum-firmware OR xtreme-firmware OR darkflippers',
    'flipperzero OR "flipper zero" pushed:>2026-01-09 OR updated:>2026-01-09',
    'awesome-flipperzero OR "all-the-plugins" OR fap-store OR flipperhttp OR fliptelegram',
    '"flipper zero" language:C OR language:cpp fork:false stars:>0'
]

# CRITICAL REPOS (Top-Priority, immer checken)
PRIORITY_REPOS = [
    "RocketGod-git/ProtoPiratein", "flipperdevices/flipperzero-firmware",
    "DarkFlippers/unleashed-firmware", "RogueMaster/flipperzero-firmware-wPlugins",
    "Next-Flip/Momentum-Firmware", "Flipper-XFW/Xtreme-Firmware",
    "djsime1/awesome-flipperzero", "xMasterX/all-the-plugins",
    "UberGuidoZ/Flipper", "jblanked/FlipTelegram", "jblanked/FlipperHTTP"
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
    save_state_copy = state.copy()
    save_state_copy["posted_events"] = list(state["posted_events"])
    save_state_copy["known_repos"] = list(state["known_repos"])
    with open(STATE_FILE, 'w') as f:
        json.dump(save_state_copy, f, indent=2)

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def ultimate_flipper_search(state: Dict) -> List[str]:
    """OPTIMIERT: 7 Queries x 25 Pages = 5000+ Repos!"""
    print("🔥 MEGA FLIPPER GITHUB SUCHE!")
    all_repos: Set[str] = set(state["known_repos"])
    all_repos.update(PRIORITY_REPOS)  # Priority immer drin
    
    for q_num, query in enumerate(FLIPPER_QUERIES, 1):
        print(f"\n🔎 Query {q_num}/{len(FLIPPER_QUERIES)}: {query[:55]}...")
        for page in range(1, 26):  # 25 Pages = 750 Repos/Query
            url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=30&page={page}"
            try:
                resp = requests.get(url, headers=get_headers(), timeout=25)
                if resp.status_code == 403:
                    print("  ⏳ Rate limit - 90s Pause...")
                    time.sleep(90)
                    continue
                if resp.status_code != 200:
                    print(f"  ❌ HTTP {resp.status_code}")
                    break
                    
                data = resp.json()
                total = data.get("total_count", 0)
                items = data.get("items", [])
                
                hits = 0
                for item in items:
                    repo_name = item["full_name"]
                    topics = item.get("topics", [])
                    desc_text = (item.get("description") or "" + item["name"]).lower()
                    
                    # VERBESSERTER Filter
                    if (any(t in topics for t in ["flipperzero", "flipper-zero", "badusb", "subghz"]) or
                        re.search(r'flipper|fap|subghz|nfc|protpirate|badusb', desc_text)):
                        all_repos.add(repo_name)
                        hits += 1
                
                print(f"  Seite {page}: {hits}/{len(items)} Treffer | Total API: {total:,}")
                if len(items) < 30:
                    break
                time.sleep(1.2)
                
            except Exception as e:
                print(f"  ❌ Fehler Seite {page}: {e}")
                break
    
    state["known_repos"] = all_repos
    print(f"\n✅ {len(all_repos)} UNIQUE FLIPPER REPOS gefunden!")
    return sorted(list(all_repos))

def deep_repo_scan(repo_name: str, state: Dict) -> List[Dict]:
    """OPTIMIERT: Speichert SHA/Tag für 100% Change Detection"""
    updates = []
    repo_state = state["repo_states"].get(repo_name, {})
    posted = state["posted_events"]
    
    try:
        # 1. RELEASES
        releases = requests.get(f"https://api.github.com/repos/{repo_name}/releases",
                               headers=get_headers(), timeout=10).json()
        if isinstance(releases, list) and releases:
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
                    repo_state["last_release_tag"] = latest["tag_name"]
        
        # 2. COMMITS + FILES (nur Flipper-relevant)
        commits = requests.get(f"https://api.github.com/repos/{repo_name}/commits?per_page=5",
                              headers=get_headers(), timeout=10).json()
        if isinstance(commits, list) and commits:
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
                            "files": [f["filename"] for f in flipper_files[:3]],
                            "msg": latest_commit["commit"]["message"][:120],
                            "url": latest_commit["html_url"]
                        })
                        repo_state["last_commit_sha"] = latest_commit["sha"]
        
        # 3. PRs/Issues (nur neue)
        for typ, endpoint in [("PR", "pulls?state=all"), ("ISSUE", "issues?state=all")]:
            items = requests.get(f"https://api.github.com/repos/{repo_name}/{endpoint}&per_page=1",
                                headers=get_headers(), timeout=10).json()
            if isinstance(items, list) and items:
                latest = items[0]
                event_id = f"{typ}:{repo_name}:{latest['number']}"
                if event_id not in posted:
                    updates.append({
                        "type": typ, "repo": repo_name,
                        "title": latest["title"][:100],
                        "num": latest["number"],
                        "url": latest["html_url"]
                    })
        
        # State updaten
        if repo_state:
            state["repo_states"][repo_name] = repo_state
    
    except Exception as e:
        pass  # Silent fail
    
    return updates

def is_flipper_file(filename: str) -> bool:
    """ERWEITERT: Mehr File-Types"""
    patterns = [
        r'\.fap$', r'\.c$', r'\.h$', r'\.cpp$', r'\.S$', r'application\.fam',
        r'applications/', r'firmware/', r'subghz/', r'nfc/', r'rfid/', 
        r'badusb/', r'infrared/', r'ibutton/', r'gpio/'
    ]
    return any(re.search(p, filename.lower()) for p in patterns)

def post_all_updates(updates: List[Dict], state: Dict):
    """OPTIMIERT: 50 Posts/Run + HTML Links + Event-Tracking"""
    sent = 0
    for update in updates[:50]:  # VON 25 auf 50 ERHÖHT!
        repo_name = update['repo']
        repo_url = f"https://github.com/{repo_name}"
        
        if update["type"] == "RELEASE":
            msg = f"""🚀 <b>NEUER RELEASE!</b>

<a href="{repo_url}">{repo_name}</a>
⏰ {update.get('time', 'Gerade')}
🏷️ <code>{update['tag']}</code>
<i>{update.get('name', '')}</i>

<a href="{update['url']}">📥 Download</a>"""
        elif update["type"] == "COMMIT":
            files_str = " | ".join(update["files"][:2])
            msg = f"""💾 <b>COMMIT ÄNDERUNG!</b>

<a href="{repo_url}">{repo_name}</a>
<code>{update['sha']}</code>
📁 {files_str}
📝 {update['msg']}

<a href="{update['url']}">🔗 Commit</a>"""
        else:
            emoji = {"PR": "🔄", "ISSUE": "🐛"}[update["type"]]
            msg = f"""{emoji} <b>{update['type']}!</b>

<a href="{repo_url}">{repo_name}</a>
#{update['num']}: {update['title']}

<a href="{update['url']}">👁️ Öffnen</a>"""
        
        send_message(msg)
        event_id = f"{update['type']}:{repo_name}:{update.get('tag') or update.get('sha') or update.get('num')}"
        state["posted_events"].add(event_id)
        sent += 1
        time.sleep(0.35)
    
    return sent

def send_message(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHANNEL, "text": msg, "parse_mode": "HTML",
        "disable_web_page_preview": False, "message_thread_id": 40
    }
    try:
        r = requests.post(url, json=data, timeout=12)
        r.raise_for_status()
        print("✅ Posted")
    except Exception as e:
        print(f"❌ {e}")

def main():
    state = load_state()
    print("🎯 FLIPPER ZERO GITHUB MEGA BOT v3.0\n")
    
    # Discovery
    repos = ultimate_flipper_search(state)
    
    # Priority Repos zuerst
    priority_first = [r for r in repos if r in PRIORITY_REPOS] + [r for r in repos if r not in PRIORITY_REPOS]
    
    print(f"\n🛠️ Deep Scan {min(250, len(repos))} Repos (Priority zuerst)...")
    all_updates = []
    
    for i, repo in enumerate(priority_first[:250]):  # VON 200 auf 250
        updates = deep_repo_scan(repo, state)
        all_updates.extend(updates)
        if updates:
            print(f"  ✅ {i+1}: {repo} = {len(updates)} Updates")
        time.sleep(0.15)
    
    # Post + Stats
    if all_updates:
        sent = post_all_updates(all_updates, state)
        print(f"\n🎉 {sent}/{len(all_updates)} FLIPPER UPDATES GEPOSTET!")
        print(f"📊 Repos: {len(repos)} | Gescannt: {min(250, len(repos))} | Updates: {len(all_updates)}")
    else:
        print("\nℹ️ Keine Änderungen (scanne 5000+ Repos)")
    
    save_state(state)
    print("\n✅ Bot fertig - Nächster Run in 3h")

if __name__ == "__main__":
    main()
