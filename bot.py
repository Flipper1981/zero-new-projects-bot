import requests
import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set
import xml.etree.ElementTree as ET

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

STATE_FILE = "/tmp/flipper_optimized_state.json"

# PRIORITY REPOS - die WICHTIGSTEN!
PRIORITY_REPOS = [
    "flipperdevices/flipperzero-firmware",
    "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins",
    "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware",
    "RocketGod-git/ProtoPiratein",
    "xMasterX/all-the-plugins",
    "djsime1/awesome-flipperzero",
    "UberGuidoZ/Flipper",
    "jblanked/FlipperHTTP",
    "jblanked/FlipTelegram"
]

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def load_state():
    try:
        with open(STATE_FILE) as f:
            s = json.load(f)
            s['known_repos'] = set(s.get('known_repos', []))
            s['posted_events'] = set(s.get('posted_events', []))
            s['last_rss_check'] = s.get('last_rss_check', {})
            return s
    except:
        return {'known_repos': set(), 'posted_events': set(), 'last_rss_check': {}}

def save_state(s):
    c = s.copy()
    c['known_repos'] = list(s['known_repos'])
    c['posted_events'] = list(s['posted_events'])
    with open(STATE_FILE, 'w') as f:
        json.dump(c, f)

# ═══════════════════════════════════════════════════════════
# LAYER 1: RSS FEEDS (0 API CALLS!)
# ═══════════════════════════════════════════════════════════

def check_rss_releases(repo: str, state: Dict) -> List[Dict]:
    """RSS Feed = 0 API Calls!"""
    updates = []
    feed_url = f"https://github.com/{repo}/releases.atom"
    
    try:
        resp = requests.get(feed_url, timeout=8)
        if resp.status_code != 200:
            return []
        
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        last_check = state['last_rss_check'].get(repo, '')
        
        for entry in root.findall('atom:entry', ns)[:5]:
            entry_id = entry.find('atom:id', ns).text
            
            if entry_id == last_check:
                break
            
            title = entry.find('atom:title', ns).text
            link = entry.find('atom:link', ns).get('href')
            published = entry.find('atom:published', ns).text
            
            # Tag extrahieren
            tag = title.split()[-1] if title else "unknown"
            event_id = f"RSS:{repo}:{tag}"
            
            if event_id not in state['posted_events']:
                updates.append({
                    'type': 'RSS-RELEASE',
                    'repo': repo,
                    'tag': tag,
                    'title': title,
                    'time': published[:19],
                    'url': link
                })
                state['posted_events'].add(event_id)
                print(f"  🆕 RSS: {repo} → {tag}")
        
        # Update last check
        if root.findall('atom:entry', ns):
            state['last_rss_check'][repo] = root.find('atom:entry', ns).find('atom:id', ns).text
    
    except Exception as e:
        pass
    
    return updates

# ═══════════════════════════════════════════════════════════
# LAYER 2: SMART API SEARCH (Rate Limit Safe)
# ═══════════════════════════════════════════════════════════

def check_rate_limit():
    """Check verfügbare API Calls"""
    try:
        resp = requests.get("https://api.github.com/rate_limit", headers=get_headers(), timeout=5)
        data = resp.json()
        remaining = data['resources']['core']['remaining']
        reset_time = data['resources']['core']['reset']
        
        print(f"  📊 Rate Limit: {remaining} remaining")
        
        if remaining < 100:
            reset_dt = datetime.fromtimestamp(reset_time)
            wait_seconds = (reset_dt - datetime.now()).total_seconds()
            print(f"  ⚠️ Rate Limit niedrig! Reset in {int(wait_seconds/60)}min")
            return False
        
        return True
    except:
        return True

def smart_search(state: Dict) -> Set[str]:
    """Smart Search mit Rate Limit Check"""
    print("\n🔍 SMART SEARCH...")
    
    if not check_rate_limit():
        print("  ⚠️ Rate Limit zu niedrig, überspringe API Search")
        return set()
    
    repos = set()
    
    # NUR EINE optimierte Query!
    queries = [
        'topic:flipperzero archived:false stars:>10',
        'flipper language:C archived:false stars:>20 pushed:>2025-12-01',
    ]
    
    for query in queries:
        url = f"https://api.github.com/search/repositories?q={query}&per_page=30&sort=updated"
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            
            if resp.status_code == 403:
                print(f"  ⚠️ Rate Limit Hit! Stoppe weitere Queries")
                break
            
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                for item in items:
                    repos.add(item['full_name'])
                
                print(f"  ✅ Query: {len(items)} repos")
            
            time.sleep(2)
        
        except:
            pass
    
    print(f"  Total: {len(repos)} repos")
    return repos

# ═══════════════════════════════════════════════════════════
# POST TO TELEGRAM
# ═══════════════════════════════════════════════════════════

def post_update(update: Dict):
    """Post to Telegram"""
    repo = update.get('repo', '')
    repo_url = f"https://github.com/{repo}"
    
    if update['type'] == 'RSS-RELEASE':
        msg = f"""🚀 <b>RELEASE!</b>

<a href="{repo_url}">{repo}</a>
🏷️ <code>{update['tag']}</code>
⏰ {update.get('time', 'Gerade')}

<a href="{update['url']}">📥 Download</a>"""
    
    elif update['type'] == 'API-RELEASE':
        msg = f"""🚀 <b>RELEASE!</b>

<a href="{repo_url}">{repo}</a>
🏷️ <code>{update['tag']}</code>
{update.get('name', '')}

<a href="{update['url']}">📥 Download</a>"""
    
    else:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHANNEL,
        'text': msg,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False,
        'message_thread_id': 40
    }
    
    try:
        resp = requests.post(url, json=data, timeout=10)
        resp.raise_for_status()
        print("  ✅ Posted")
        time.sleep(0.3)
    except Exception as e:
        print(f"  ❌ Post Error: {e}")

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    state = load_state()
    
    print("=" * 70)
    print("🎯 FLIPPER ZERO BOT v10.0 - OPTIMIZED")
    print("   RSS First + Smart API")
    print("=" * 70 + "\n")
    
    all_updates = []
    
    # PHASE 1: RSS FEEDS (0 API - IMMER SICHER!)
    print("📡 PHASE 1: RSS FEEDS (0 API)...\n")
    
    # Priority Repos via RSS
    for repo in PRIORITY_REPOS:
        print(f"[RSS] {repo}")
        updates = check_rss_releases(repo, state)
        all_updates.extend(updates)
        state['known_repos'].add(repo)
        time.sleep(0.2)
    
    print(f"\n  ✅ RSS: {len(all_updates)} Updates (0 API calls!)")
    
    # PHASE 2: SMART API (nur wenn Rate Limit OK)
    print(f"\n🔍 PHASE 2: SMART API SEARCH...\n")
    
    new_repos = smart_search(state)
    state['known_repos'].update(new_repos)
    
    # RSS für neue Rep
