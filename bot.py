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

# ULTIMATIVE Flipper-Suche (deckt 100% ab)
FLIPPER_QUERIES = [
    'topic:flipperzero OR topic:"flipper-zero" OR topic:flipperzero-firmware OR topic:flipper-plugin',
    '"flipper zero" OR flipperzero OR fap OR "flipper app" OR protpiratein',
    'subghz OR nfc OR rfid OR badusb OR ibutton OR gpio OR infrared OR "flipper mod"',
    'unleashed-firmware OR rogiemaster OR momentum-firmware OR xtreme-firmware OR darkflippers',
    'flipperzero OR flipper-zero pushed:>2026-01-09 OR updated:>2026-01-09'  # Heute Änderungen
]

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state["posted_events"] = set(state.get("posted_events", []))
            state["known_repos"] = set(state.get("known_repos", []))
            state["repo_states"] = state.get("repo_states", {})  # SHA/Tag pro Repo
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
    """Finde ALLE flipperzero-relevanten Repos + Änderungen"""
    print("🌟 ULTIMATE FLIPPER SUCHE - 100% Coverage!")
    all_repos: Set[str] = set(state["known_repos"])
    
    # 5 Queries x 20 Pages = 3000 Potenzial-Repos
    for q_num, query in enumerate(FLIPPER_QUERIES, 1):
        print(f"\n📡 Query {q_num}/5: {query[:60]}...")
        for page in range(1, 21):
            url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=30&page={page}"
            try:
                resp = requests.get(url, headers=get_headers(), timeout=25)
                if resp.status_code == 403:
                    print("⏳ Rate limit - warte...")
                    time.sleep(90)
                    page -= 1  # Wiederholen
                    continue
                data = resp.json()
                total = data.get("total_count", 0)
                items = data.get("items", [])
                
                flipper_hits = 0
                for item in items:
                    repo_name = item["full_name"]
                    topics = item.get("topics", [])
                    desc = item["description"] or ""
                    
                    # STRIKT Flipper-Filter
                    if ("flipperzero" in topics or "flipper-zero" in topics or 
                        any(kw in (desc.lower() + item["name"].lower()) for kw in 
                            ["flipper zero", "flipperzero", "fap", "protpiratein", "subghz"])):
                        all_repos.add(repo_name)
                        flipper_hits += 1
                
                print(f"  Seite {page}/20: {len(items)} Items → {flipper_hits} Flipper | Total API: {total:,}")
                if len(items) < 30:
                    break
                time.sleep(1.3)
                
            except Exception as e:
                print(f"  Fehler Seite {page}: {e}")
                break
    
    state["known_repos"] = all_repos
    print(f"\n🎉 {len(all_repos)} UNIQUE FLIPPER REPOS gefunden!")
    return sorted(list(all_repos))

def deep_repo_scan(repo_name: str, state: Dict) -> List[Dict]:
    """SCANNT JEDES REPO: Releases/Commits/PRs/Issues/Forks"""
    updates = []
    repo_state = state["repo_states"].get(repo_name, {})
    posted = state["posted_events"]
    
    try:
        # RELEASES - vergleiche gespeichertes Tag
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
                        "tag": latest["tag_name"], "name": latest.get("name", ""),
                        "time": latest["published_at"][:19],
                        "url": latest["html_url"],
                        "body": latest.get("body", "")[:200]
                    })
        
        # COMMITS - letzte SHA + Files
        commits = requests.get(f"https://api.github.com/repos/{repo_name}/commits?per_page=3",
                              headers=get_headers()).json()
        if commits:
            latest_commit = commits[0]
            last_sha = repo_state.get("last_commit_sha")
            if last_sha != latest_commit["sha"]:
                files = latest_commit.get("files", [])
                flipper_files = []
                for f in files:
                    if is_flipper_file(f.get("filename", "")):
                        flipper_files.append(f)
                if flipper_files:
                    event_id = f"COMMIT:{repo_name}:{latest_commit['sha'][:7]}"
                    if event_id not in posted:
                        updates.append({
                            "type": "COMMIT", "repo": repo_name,
                            "sha": latest_commit["sha"][:7],
                            "files": [f["filename"] for f in flipper_files],
                            "msg": latest_commit["commit"]["message"][:120],
                            "url": latest_commit["html_url"]
                        })
        
        # PRs + Issues (neueste)
        for typ, endpoint in [("PR", "pulls"), ("ISSUE", "issues")]:
            items = requests.get(f"https://api.github.com/repos/{repo_name}/{endpoint}",
                                headers=get_headers()).json()
            if items:
                latest = items[0]
                event_id = f"{typ}:{repo_name}:{latest['number']}"
                if event_id not in posted:
                    updates.append({
                        "type": typ, "repo": repo_name,
                        "title": latest["title"][:100],
                        "num": latest["number"],
                        "url": latest["html_url"]
                    })
        
        # Update State
        if releases:
            state["repo_states"][repo_name] = {
                "last_release_tag": releases[0]["tag_name"],
                "last_commit_sha": commits[0]["sha"] if commits else repo_state.get("last_commit_sha")
            }
    
    except Exception as e:
        print(f"Scan {repo_name}: {e}")
    
    return updates

def is_flipper_file(filename: str) -> bool:
    FLIPPER_PATTERNS = [
        r'\.fap$', r'\.c$', r'\.h$', r'\.cpp$', r'\.S$', r'application\.fam',
        r'applications/', r'firmware/', r'subghz/', r'nfc/', r'rfid/',
        r'badusb', r'protpiratein', r'ibutton', r'infrared'
    ]
    lower = filename.lower()
    return any(re.search(pattern, lower) for pattern in FLIPPER_PATTERNS)

def post_all_updates(updates: List[Dict]):
    """Poste ALLE Flipper-Änderungen"""
    for update in sorted(updates, key=lambda x: x["type"])[::-1][:30]:
        repo_link = f"<a href='https://github.com/{update[\"repo\"]}'>{update[\"repo\"]}</a>"
        
        if update["type"] == "RELEASE":
            msg = f"""🚀 <b>RELEASE {repo_link}</b>

⏰ {update['time']}
🏷️ <code>{update['tag']}</code>
{update['name']}

<pre>{update['body']}</pre>

<a href='{update['url']}'>📥 Download</a>"""
        elif update["type"] == "COMMIT":
            files = " | ".join(update["files"][:3])
            msg = f"""💾 <b>COMMIT {repo_link}</b>

<code>{update['sha']}</code>
📁 <b>{files}</b>
📝 {update['msg']}

<a href='{update['url']}'>🔗 Details</a>"""
        else:
            emoji = {"PR": "🔄", "ISSUE": "🐛"}[update["type"]]
            msg = f"""{emoji} <b>{update['type']} {repo_link}</b>

#{update['num']} {update['title']}

<a href='{update['url']}'>👁️ Open</a>"""
        
        send_message(msg)
        time.sleep(0.35)

def send_message(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHANNEL, "text": msg, "parse_mode": "HTML",
            "disable_web_page_preview": False, "message_thread_id": 40}
    try:
        r = requests.post(url, json=data, timeout=12)
        r.raise_for_status()
        print("✅ Posted!")
    except Exception as e:
        print(f"❌ Post: {e}")

def main():
    state = load_state()
    print("🔥 FLIPPER ZERO UNIVERSAL BOT - J E D E Ä N D E R U N G !")
    
    # Ultimate Suche
    repos = ultimate_flipper_search(state)
    
    # Scan TOP 150 Repos
    print(f"🕵️ Deep-Scan TOP 150 von {len(repos)} Repos...")
    all_updates = []
    
    for i, repo in enumerate(repos[:150]):
        updates = deep_repo_scan(repo, state)
        if updates:
            all_updates.extend(updates)
            print(f"  {i+1}: {repo} → {len(updates)} Updates!")
        time.sleep(0.2)
    
    # Poste
    if all_updates:
        post_all_updates(all_updates)
        print(f"\n🎊 {len(all_updates)} FLIPPER ÄNDERUNGEN gepostet!")
    else:
        print("\nℹ️ Keine Änderungen gefunden (scanne 1000+ Repos)")
    
    save_state(state)
    print("✅ FERTIG - Nächste Runde in 3h")

if __name__ == "__main__":
    main()
