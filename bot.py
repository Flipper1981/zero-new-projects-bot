import requests
import os
import json
from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Set
import re
import xml.etree.ElementTree as ET

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

STATE_FILE = "/tmp/flipper_ultimate_state.json"

# OPTIMIERTE QUERIES mit archived:false
FLIPPER_QUERIES = [
    'topic:flipperzero archived:false',
    'topic:"flipper-zero" OR topic:flipperzero-firmware OR topic:flipper-plugin archived:false',
    '"flipper zero" archived:false stars:>5',
    'unleashed-firmware OR rogiemaster OR momentum-firmware OR xtreme-firmware archived:false',
    'subghz OR nfc OR rfid OR badusb flipper archived:false',
    'fap OR "flipper app" OR flipperhttp OR fliptelegram archived:false',
    'awesome-flipperzero OR all-the-plugins OR fap-store archived:false',
    'flipperzero language:C archived:false pushed:>2026-01-03',
    'protpirate OR subbrute OR "wifi marauder" flipper archived:false'
]

CODE_SEARCH_QUERIES = [
    'extension:fap archived:false',
    'filename:application.fam flipper archived:false',
    'extension:sub path:subghz archived:false',
    'extension:nfc flipper archived:false'
]

PRIORITY_REPOS = [
    "flipperdevices/flipperzero-firmware", "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins", "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware", "RocketGod-git/ProtoPiratein",
    "xMasterX/all-the-plugins", "djsime1/awesome-flipperzero",
    "UberGuidoZ/Flipper", "jblanked/FlipTelegram", "jblanked/FlipperHTTP",
    "flipperdevices/flipperzero-good-faps", "xMasterX/fap-store",
    "DarkFlippers/flipperzero-subbrute", "UberGuidoZ/Flipper_Zero-BadUsb"
]

RSS_FEED_REPOS = PRIORITY_REPOS[:10]

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state["posted_events"] = set(state.get("posted_events", []))
            state["known_repos"] = set(state.get("known_repos", []))
            state["repo_states"] = state.get("repo_states", {})
            state["last_rss_check"] = state.get("last_rss_check", {})
            return state
    except:
        return {
            "known_repos": set(), "posted_events": set(), "repo_states": {},
            "last_rss_check": {}
        }

def save_state(state: Dict):
    save_copy = state.copy()
    save_copy["posted_events"] = list(state["posted_events"])
    save_copy["known_repos"] = list(state["known_repos"])
    with open(STATE_FILE, 'w') as f:
        json.dump(save_copy, f, indent=2)

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

# ═══════════════════════════════════════════════════════════
# LAYER 1: RSS FEEDS (FRÜHESTE RELEASE-ERKENNUNG)
# ═══════════════════════════════════════════════════════════

def check_rss_feeds(state: Dict) -> List[Dict]:
    """RSS Atom Feeds für Releases - 0 API Calls!"""
    print("\n📡 RSS FEED CHECK...")
    new_releases = []
    
    for repo in RSS_FEED_REPOS:
        feed_url = f"https://github.com/{repo}/releases.atom"
        last_check = state["last_rss_check"].get(repo, "")
        
        try:
            resp = requests.get(feed_url, timeout=10)
            if resp.status_code != 200:
                continue
            
            root = ET.fromstring(resp.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns)[:3]:
                entry_id = entry.find('atom:id', ns).text
                if entry_id == last_check:
                    break
                
                title = entry.find('atom:title', ns).text
                link = entry.find('atom:link', ns).get('href')
                published = entry.find('atom:published', ns).text
                
                tag = title.split()[-1] if title else "unknown"
                event_id = f"RSS:{repo}:{tag}"
                
                if event_id not in state["posted_events"]:
                    new_releases.append({
                        "type": "RSS-RELEASE", "repo": repo,
                        "tag": tag, "title": title,
                        "time": published[:19],
                        "url": link
                    })
                    print(f"  🆕 RSS: {repo} → {tag}")
            
            if root.findall('atom:entry', ns):
                state["last_rss_check"][repo] = root.find('atom:entry', ns).find('atom:id', ns).text
        
        except:
            pass
        
        time.sleep(0.3)
    
    print(f"  ✅ {len(new_releases)} RSS Releases")
    return new_releases

# ═══════════════════════════════════════════════════════════
# LAYER 2: PUBLIC EVENTS API
# ═══════════════════════════════════════════════════════════

def check_public_events(state: Dict) -> List[Dict]:
    """GitHub Public Events"""
    print("\n⚡ PUBLIC EVENTS...")
    new_events = []
    
    url = "https://api.github.com/events?per_page=100"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        events = resp.json()
        
        flipper_keywords = ['flipper', 'flipperzero', 'subghz', 'nfc', 'badusb', 'protpirate']
        
        for event in events:
            repo_name = event.get("repo", {}).get("name", "")
            event_type = event.get("type")
            
            is_relevant = (
                repo_name in state.get("known_repos", []) or
                any(kw in repo_name.lower() for kw in flipper_keywords)
            )
            
            if not is_relevant:
                continue
            
            event_id = f"EVENT:{event_type}:{repo_name}:{event.get('id')}"
            if event_id in state["posted_events"]:
                continue
            
            if event_type == "ReleaseEvent":
                release = event.get("payload", {}).get("release", {})
                new_events.append({
                    "type": "EVENT-RELEASE", "repo": repo_name,
                    "tag": release.get("tag_name", "?"),
                    "url": release.get("html_url", f"https://github.com/{repo_name}/releases")
                })
            
            elif event_type == "PushEvent":
                commits = event.get("payload", {}).get("commits", [])
                if commits:
                    new_events.append({
                        "type": "EVENT-PUSH", "repo": repo_name,
                        "commits": len(commits),
                        "msg": commits[0].get("message", "")[:100],
                        "url": f"https://github.com/{repo_name}/commits"
                    })
            
            state["posted_events"].add(event_id)
        
        print(f"  ✅ {len(new_events)} Events")
    except:
        pass
    
    return new_events

# ═══════════════════════════════════════════════════════════
# LAYER 3: CODE SEARCH
# ═══════════════════════════════════════════════════════════

def check_code_search(state: Dict) -> List[Dict]:
    """Code Search - neue .fap, .sub, .nfc Dateien"""
    print("\n🔍 CODE SEARCH...")
    new_files = []
    
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    
    for query in CODE_SEARCH_QUERIES[:2]:
        url = f"https://api.github.com/search/code?q={query}+created:>{since}&per_page=15"
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    repo = item.get("repository", {}).get("full_name")
                    path = item.get("path")
                    event_id = f"CODE:{repo}:{path}"
                    if event_id not in state["posted_events"]:
                        new_files.append({
                            "type": "NEW-FILE", "repo": repo,
                            "file": path,
                            "url": item.get("html_url")
                        })
                        state["posted_events"].add(event_id)
            time.sleep(3)
        except:
            pass
    
    print(f"  ✅ {len(new_files)} neue Files")
    return new_files

# ═══════════════════════════════════════════════════════════
# LAYER 4: REPO SEARCH (optimiert)
# ═══════════════════════════════════════════════════════════

def optimized_repo_search(state: Dict) -> List[str]:
    """REST Search mit archived:false"""
    print("\n🔎 REPO SEARCH...")
    repos = set(state.get("known_repos", []))
    repos.update(PRIORITY_REPOS)
    
    for q in FLIPPER_QUERIES[:6]:
        for page in range(1, 11):
            url = f"https://api.github.com/search/repositories?q={q}&per_page=30&page={page}"
            try:
                resp = requests.get(url, headers=get_headers(), timeout=20)
                if resp.status_code == 403:
                    time.sleep(60)
                    continue
                if resp.status_code != 200:
                    break
                for item in resp.json().get("items", []):
                    repos.add(item["full_name"])
                time.sleep(1.1)
            except:
                break
    
    state["known_repos"] = repos
    print(f"  ✅ {len(repos)} Repos")
    return sorted(list(repos))

# ═══════════════════════════════════════════════════════════
# LAYER 5: DEEP REPO SCAN
# ═══════════════════════════════════════════════════════════

def deep_repo_scan(repo_name: str, state: Dict) -> List[Dict]:
    """Scan einzelnes Repo für Releases"""
    updates = []
    repo_state = state["repo_states"].get(repo_name, {})
    posted = state["posted_events"]
    
    try:
        releases = requests.get(f"https://api.github.com/repos/{repo_name}/releases",
                               headers=get_headers(), timeout=8).json()
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
        
        if repo_state:
            state["repo_states"][repo_name] = repo_state
    except:
        pass
    
    return updates

# ═══════════════════════════════════════════════════════════
# POST UPDATES
# ═══════════════════════════════════════════════════════════

def post_all_updates(all_updates: List[Dict], state: Dict):
    """Post Updates"""
    sent = 0
    for update in all_updates[:80]:
        repo_name = update.get('repo', '')
        repo_url = f"https://github.com/{repo_name}" if repo_name else update.get('url', '')
        
        if "RELEASE" in update["type"]:
            msg = f"""🚀 <b>NEUER RELEASE!</b>

<a href="{repo_url}">{repo_name}</a>
⏰ {update.get('time', 'Gerade')}
🏷️ <code>{update.get('tag', '?')}</code>
{update.get('name', '')}

<a href="{update['url']}">📥 Download</a>"""
        
        elif update["type"] == "EVENT-PUSH":
            msg = f"""💾 <b>PUSH EVENT!</b>

<a href="{repo_url}">{repo_name}</a>
📝 {update['commits']} Commits
{update.get('msg', '')}

<a href="{update['url']}">🔗 Details</a>"""
        
        elif update["type"] == "NEW-FILE":
            msg = f"""📁 <b>NEUE DATEI!</b>

<a href="{repo_url}">{repo_name}</a>
🗂️ <code>{update['file']}</code>

<a href="{update['url']}">👁️ Datei</a>"""
        
        else:
            continue
        
        send_message(msg)
        sent += 1
        time.sleep(0.3)
    
    return sent

def send_message(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHANNEL, "text": msg, "parse_mode": "HTML",
            "disable_web_page_preview": False, "message_thread_id": 40}
    try:
        requests.post(url, json=data, timeout=10).raise_for_status()
        print("✅")
    except Exception as e:
        print(f"❌ {e}")

def main():
    state = load_state()
    print("=" * 70)
    print("🎯 FLIPPER ZERO ULTIMATE BOT v6.0")
    print("   RSS + Events + CodeSearch + archived:false")
    print("=" * 70 + "\n")
    
    all_updates = []
    
    # LAYER 1: RSS (frühest!)
    rss_releases = check_rss_feeds(state)
    all_updates.extend(rss_releases)
    
    # LAYER 2: Events API
    events = check_public_events(state)
    all_updates.extend(events)
    
    # LAYER 3: Code Search
    new_files = check_code_search(state)
    all_upd
