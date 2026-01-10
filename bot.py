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

# DEIN USERNAME!
MY_GITHUB_USERNAME = "Flipper1981"

STATE_FILE = "/tmp/flipper_ultimate_state.json"

# [Alle vorherigen Queries + Optimierungen bleiben...]
FLIPPER_QUERIES = [
    'topic:flipperzero archived:false',
    'topic:"flipper-zero" OR topic:flipperzero-firmware archived:false',
    '"flipper zero" archived:false stars:>5',
    'unleashed-firmware OR rogiemaster OR momentum-firmware archived:false'
]

PRIORITY_REPOS = [
    "flipperdevices/flipperzero-firmware", "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins", "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware", "RocketGod-git/ProtoPiratein"
]

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state["posted_events"] = set(state.get("posted_events", []))
            state["known_repos"] = set(state.get("known_repos", []))
            state["repo_states"] = state.get("repo_states", {})
            return state
    except:
        return {"posted_events": set(), "known_repos": set(), "repo_states": {}}

def save_state(state):
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
# FLIPPER1981 HOMEPAGE INTEGRATION!
# ═══════════════════════════════════════════════════════════

def check_flipper1981_homepage(state: Dict) -> List[Dict]:
    """
    DEINE GitHub Homepage (Flipper1981)
    - Received Events = Was DU siehst auf github.com
    - FRÜHESTE Flipper Zero Updates!
    """
    print(f"\n🏠 FLIPPER1981 HOMEPAGE CHECK...")
    homepage_updates = []
    
    # Received Events = Dein Homepage Feed
    url = f"https://api.github.com/users/{MY_GITHUB_USERNAME}/received_events?per_page=100"
    
    try:
        resp = requests.get(url, headers=get_headers(), timeout=20)
        if resp.status_code != 200:
            print(f"  ⚠️ Homepage API: {resp.status_code}")
            return []
        
        events = resp.json()
        flipper_keywords = ['flipper', 'flipperzero', 'fap', 'subghz', 'nfc', 'badusb', 'protpirate']
        
        for event in events:
            repo_name = event.get("repo", {}).get("name", "")
            event_type = event.get("type")
            created_at = event.get("created_at", "")
            
            # Flipper-Filter
            is_flipper = any(kw in repo_name.lower() for kw in flipper_keywords)
            if not is_flipper:
                continue
            
            event_id = f"HOME:{event_type}:{repo_name}:{event.get('id')}"
            if event_id in state["posted_events"]:
                continue
            
            # Release Event (WICHTIGSTE!)
            if event_type == "ReleaseEvent":
                release = event.get("payload", {}).get("release", {})
                homepage_updates.append({
                    "type": "HOME-RELEASE", "repo": repo_name,
                    "tag": release.get("tag_name", "?"),
                    "name": release.get("name", "Release"),
                    "time": created_at[:19],
                    "url": release.get("html_url", f"https://github.com/{repo_name}/releases"),
                    "priority": 1  # Höchste Priorität!
                })
                print(f"  🔥 Flipper1981 Feed: {repo_name} → {release.get('tag_name')}")
            
            # Push Event
            elif event_type == "PushEvent":
                commits = event.get("payload", {}).get("commits", [])
                if commits:
                    homepage_updates.append({
                        "type": "HOME-PUSH", "repo": repo_name,
                        "commits": len(commits),
                        "msg": commits[0].get("message", "")[:120],
                        "url": f"https://github.com/{repo_name}/commits",
                        "priority": 2
                    })
            
            # Watch/Star Event
            elif event_type == "WatchEvent":
                actor = event.get("actor", {}).get("login", "?")
                homepage_updates.append({
                    "type": "HOME-STAR", "repo": repo_name,
                    "actor": actor,
                    "url": f"https://github.com/{repo_name}",
                    "priority": 3
                })
            
            # Create Event (neue Repos!)
            elif event_type == "CreateEvent":
                ref_type = event.get("payload", {}).get("ref_type")
                if ref_type == "repository":
                    homepage_updates.append({
                        "type": "HOME-NEW-REPO", "repo": repo_name,
                        "url": f"https://github.com/{repo_name}",
                        "priority": 2
                    })
                    state["known_repos"].add(repo_name)
                    print(f"  🆕 Neues Flipper Repo: {repo_name}")
            
            state["posted_events"].add(event_id)
        
        print(f"  ✅ {len(homepage_updates)} Updates von deinem Feed!")
    
    except Exception as e:
        print(f"  ❌ Homepage: {e}")
    
    return homepage_updates

def check_flipper1981_stars(state: Dict) -> List[Dict]:
    """Repos die DU gestarrt hast"""
    print("\n⭐ FLIPPER1981 STARS...")
    updates = []
    
    url = f"https://api.github.com/users/{MY_GITHUB_USERNAME}/starred?per_page=20"
    
    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        if resp.status_code != 200:
            return []
        
        for repo in resp.json():
            repo_name = repo["full_name"]
            state["known_repos"].add(repo_name)
            
            # Check neueste Releases
            rel_url = f"https://api.github.com/repos/{repo_name}/releases?per_page=1"
            rel_resp = requests.get(rel_url, headers=get_headers(), timeout=8)
            
            if rel_resp.status_code == 200:
                releases = rel_resp.json()
                if releases:
                    latest = releases[0]
                    event_id = f"STAR-REL:{repo_name}:{latest['tag_name']}"
                    if event_id not in state["posted_events"]:
                        updates.append({
                            "type": "STARRED-RELEASE", "repo": repo_name,
                            "tag": latest["tag_name"],
                            "time": latest["published_at"][:19],
                            "url": latest["html_url"],
                            "priority": 2
                        })
                        state["posted_events"].add(event_id)
                        print(f"  🆕 Star Release: {repo_name}")
            
            time.sleep(0.3)
        
        print(f"  ✅ {len(updates)} Star Updates")
    except:
        pass
    
    return updates

def check_flipper1981_rss(state: Dict) -> List[Dict]:
    """Dein persönlicher RSS Feed"""
    print("\n📡 FLIPPER1981 RSS FEED...")
    updates = []
    
    feed_url = f"https://github.com/{MY_GITHUB_USERNAME}.atom"
    
    try:
        resp = requests.get(feed_url, timeout=10)
        if resp.status_code != 200:
            return []
        
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns)[:10]:
            title = entry.find('atom:title', ns).text
            link = entry.find('atom:link', ns).get('href')
            published = entry.find('atom:published', ns).text
            
            event_id = f"RSS:{MY_GITHUB_USERNAME}:{link}"
            if event_id in state["posted_events"]:
                continue
            
            # Parse Title für Flipper Keywords
            if any(kw in title.lower() for kw in ['flipper', 'fap', 'subghz', 'nfc']):
                updates.append({
                    "type": "RSS-ACTIVITY", "title": title,
                    "time": published[:19],
                    "url": link,
                    "priority": 3
                })
                state["posted_events"].add(event_id)
        
        print(f"  ✅ {len(updates)} RSS Updates")
    except:
        pass
    
    return updates

# [ALLE VORHERIGEN FUNKTIONEN BLEIBEN: GraphQL, Events, Code Search, etc...]

def post_all_updates(all_updates: List[Dict], state: Dict):
    """Post mit HOMEPAGE = HÖCHSTE PRIORITÄT!"""
    sent = 0
    
    # Sort by priority (1=highest)
    sorted_updates = sorted(all_updates, key=lambda x: x.get("priority", 99))
    
    for update in sorted_updates[:100]:
        repo = update.get('repo', '')
        repo_url = f"https://github.com/{repo}" if repo else update.get('url', '')
        
        if update["type"] == "HOME-RELEASE":
            msg = f"""🔥 <b>RELEASE AUF DEINEM FEED!</b>

<a href="{repo_url}">{repo}</a>
🏷️ <code>{update['tag']}</code>
{update.get('name', '')}
⏰ {update.get('time', 'Gerade')}
👤 <i>Von deinem Following</i>

<a href="{update['url']}">📥 Download</a>"""
        
        elif update["type"] == "STARRED-RELEASE":
            msg = f"""⭐ <b>RELEASE IN DEINEM STAR!</b>

<a href="{repo_url}">{repo}</a>
🏷️ <code>{update['tag']}</code>
⏰ {update['time']}

<a href="{update['url']}">📥 Download</a>"""
        
        elif update["type"] == "HOME-PUSH":
            msg = f"""💾 <b>PUSH AUF DEINEM FEED!</b>

<a href="{repo_url}">{repo}</a>
📝 {update['commits']} Commits
{update.get('msg', '')}

<a href="{update['url']}">🔗 Details</a>"""
        
        elif update["type"] == "HOME-NEW-REPO":
            msg = f"""🆕 <b>NEUES FLIPPER REPO!</b>

<a href="{repo_url}">{repo}</a>
👤 <i>Von deinem Following</i>

<a href="{update['url']}">👁️ Ansehen</a>"""
        
        elif update["type"] == "HOME-STAR":
            msg = f"""⭐ <b>NEUER STAR!</b>

<a href="{repo_url}">{repo}</a>
👤 von @{update.get('actor', '?')}

<a href="{update['url']}">👁️ Repo</a>"""
        
        elif update["type"] == "RSS-ACTIVITY":
            msg = f"""📡 <b>FLIPPER1981 AKTIVITÄT!</b>

{update['title']}

<a href="{update['url']}">👁️ Details</a>"""
        
        else:
            continue
        
        send_message(msg)
        sent += 1
        time.sleep(0.25)
    
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
    print("🎯 FLIPPER ZERO BOT v7.0 + FLIPPER1981 HOMEPAGE!")
    print("=" * 70 + "\n")
    
    all_updates = []
    
    # LAYER 0: FLIPPER1981 HOMEPAGE (HÖCHSTE PRIORITÄT!)
    homepage = check_flipper1981_homepage(state)
    all_updates.extend(homepage)
    
    stars = check_flipper1981_stars(state)
    all_updates.extend(stars)
    
    rss = check_flipper1981_rss(state)
    all_updates.extend(rss)
    
    # LAYER 1-6: [GraphQL, Events, Code Search, etc. bleiben alle...]
    
    # Post
    if all_updates:
        sent = post_all_updates(all_updates, state)
        print(f"\n{'='*70}")
        print(f"🎉 {sent}/{len(all_updates)} UPDATES GEPOSTET!")
        print(f"🏠 Flipper1981 Homepage: {len(homepage)} Releases/Pushes")
        print(f"⭐ Stars: {len(stars)} | 📡 RSS: {len(rss)}")
        print(f"{'='*70}")
    else:
        print("\nℹ️ Keine Änderungen auf deinem Feed")
    
    save_state(state)
    print("\n✅ Fertig - Next in 30min!\n")

if __name__ == "__main__":
    main()
