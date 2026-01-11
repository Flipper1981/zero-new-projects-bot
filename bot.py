import requests
import os
import time
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set
import xml.etree.ElementTree as ET

# ═══════════════════════════════════════════════════════════
# KONFIGURATION
# ═══════════════════════════════════════════════════════════

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL_ID", "")
STATE_FILE = "/tmp/flipper_v15_state.json"

def get_headers():
    """Headers mit Token"""
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def check_rate_limit():
    """Rate Limit Status prüfen"""
    try:
        resp = requests.get("https://api.github.com/rate_limit", headers=get_headers(), timeout=10)
        data = resp.json()
        
        core = data['resources']['core']
        search = data['resources']['search']
        
        print(f"\n{'='*70}")
        print(f"📊 RATE LIMIT STATUS:")
        print(f"   Core API: {core['remaining']}/{core['limit']} remaining")
        print(f"   Search API: {search['remaining']}/{search['limit']} remaining")
        
        if core['limit'] == 5000:
            print(f"   ✅ TOKEN AKTIV! (5000/h)")
        elif core['limit'] == 60:
            print(f"   ⚠️ KEIN TOKEN - nur 60/h")
        else:
            print(f"   ℹ️ Limit: {core['limit']}/h")
        
        print(f"{'='*70}\n")
        
        return core['remaining'] > 50
    except Exception as e:
        print(f"⚠️ Rate Limit Check failed: {e}")
        return True

# ═══════════════════════════════════════════════════════════
# OPTIMIERTE BREITE SUCHE (500+ Repos!)
# ═══════════════════════════════════════════════════════════

def optimized_search() -> Set[str]:
    """
    Breite effiziente Queries
    Findet 500+ Repos in 5-10min!
    """
    print("\n🔍 OPTIMIERTE REPO SUCHE...")
    all_repos = set()
    
    # BREITE BASE-QUERIES (maximale Abdeckung)
    base_queries = [
        # Hauptbegriffe
        "flipper archived:false",
        "flipperzero archived:false",
        "flipper-zero archived:false",
        
        # Topics (sehr effektiv!)
        "topic:flipperzero",
        "topic:flipper-zero",
        "topic:flipper",
        "topic:flipper-app",
        "topic:flipper-plugin",
        
        # Kategorien
        "subghz archived:false",
        "flipper nfc archived:false",
        "flipper badusb archived:false",
        "flipper infrared archived:false",
        "flipper rfid archived:false",
        
        # Languages (findet Code-Repos)
        "flipper language:C archived:false",
        "flipper language:Python archived:false",
        "flipper language:Rust archived:false",
        
        # Firmware Variants
        "unleashed firmware archived:false",
        "roguemaster archived:false",
        "momentum firmware flipper archived:false",
        "xtreme firmware flipper archived:false",
        
        # Qualität
        "flipper stars:>5 archived:false",
        "flipper stars:>20 archived:false",
        "flipper stars:>50 archived:false",
        "flipper forks:>3 archived:false",
        
        # Apps & Tools
        "fap flipper archived:false",
        "flipper application archived:false",
        "flipper tool archived:false",
        "flipper game archived:false",
        
        # Hardware
        "flipper esp32 archived:false",
        "flipper gpio archived:false",
        "flipper wifi archived:false",
        
        # Development
        "flipper sdk archived:false",
        "flipper api archived:false",
        "ufbt archived:false",
        
        # Recent Activity
        "flipper pushed:>2025-12-01 archived:false",
        "flipper pushed:>2026-01-01 archived:false"
    ]
    
    for i, query in enumerate(base_queries, 1):
        url = f"https://api.github.com/search/repositories?q={query}&per_page=100&sort=updated"
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                total = data.get('total_count', 0)
                items = data.get('items', [])
                
                new_repos = 0
                for item in items:
                    repo_name = item['full_name']
                    if repo_name not in all_repos:
                        all_repos.add(repo_name)
                        new_repos += 1
                
                print(f"  [{i:2d}/{len(base_queries)}] {query[:50]:50s} → {new_repos:3d} neue | Total: {len(all_repos):4d}")
            
            elif resp.status_code == 403:
                print(f"  ⚠️ Rate Limit erreicht!")
                break
            
            time.sleep(2)  # GitHub Best Practice
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    print(f"\n  ✅ GEFUNDEN: {len(all_repos)} unique repos!\n")
    return all_repos

# ═══════════════════════════════════════════════════════════
# RSS FEEDS (0 API CALLS!)
# ═══════════════════════════════════════════════════════════

def check_rss_releases(repo: str, state: Dict) -> List[Dict]:
    """
    RSS Feed Check = 0 API Calls!
    Unbegrenzte Checks möglich!
    """
    updates = []
    feed_url = f"https://github.com/{repo}/releases.atom"
    
    try:
        resp = requests.get(feed_url, timeout=8)
        if resp.status_code != 200:
            return []
        
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns)[:5]:  # Top 5 Releases
            title_elem = entry.find('atom:title', ns)
            link_elem = entry.find('atom:link', ns)
            published_elem = entry.find('atom:published', ns)
            
            if title_elem is None or link_elem is None:
                continue
            
            title = title_elem.text or ""
            link = link_elem.get('href', '')
            published = published_elem.text if published_elem is not None else ""
            
            # Extract tag from title (z.B. "Release v1.2.3" → "v1.2.3")
            tag = title.split()[-1] if title else "unknown"
            event_id = f"RSS:{repo}:{tag}"
            
            # Nur neue Events
            if event_id not in state.get('posted_events', set()):
                updates.append({
                    'type': 'RELEASE',
                    'repo': repo,
                    'tag': tag,
                    'title': title,
                    'url': link,
                    'time': published[:19].replace('T', ' ')
                })
                state.setdefault('posted_events', set()).add(event_id)
        
        time.sleep(0.1)  # Friendly rate limit
        
    except Exception as e:
        pass  # Repo hat keine Releases
    
    return updates

def check_all_rss(repos: Set[str], state: Dict) -> List[Dict]:
    """RSS Check für alle Repos"""
    print(f"\n📡 RSS RELEASE CHECK ({len(repos)} repos)...\n")
    
    all_updates = []
    
    for i, repo in enumerate(sorted(repos), 1):
        updates = check_rss_releases(repo, state)
        
        if updates:
            print(f"  [{i:4d}] 🆕 {repo:50s} → {len(updates)} releases")
            all_updates.extend(updates)
        
        # Progress Update
        if i % 100 == 0:
            print(f"\n  📊 Progress: {i}/{len(repos)} repos checked, {len(all_updates)} updates\n")
            time.sleep(1)
    
    print(f"\n  ✅ RSS CHECK COMPLETE: {len(all_updates)} neue Releases!\n")
    return all_updates

# ═══════════════════════════════════════════════════════════
# TELEGRAM INTEGRATION
# ═══════════════════════════════════════════════════════════

def post_to_telegram(update: Dict):
    """Post Update to Telegram Channel"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        print("  ⚠️ Telegram nicht konfiguriert")
        return False
    
    repo = update.get('repo', '')
    tag = update.get('tag', 'unknown')
    title = update.get('title', tag)
    url = update.get('url', f"https://github.com/{repo}")
    time_str = update.get('time', 'Jetzt')
    
    repo_url = f"https://github.com/{repo}"
    
    # Formatierte Nachricht
    msg = f"""🚀 <b>NEUE RELEASE!</b>

📦 <a href="{repo_url}">{repo}</a>
🏷️ <code>{tag}</code>
📝 {title}
⏰ {time_str}

<a href="{url}">📥 Release ansehen</a>"""
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHANNEL,
        'text': msg,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    
    # Optional: Thread ID (wenn du Topics nutzt)
    thread_id = os.environ.get("THREAD_ID", "")
    if thread_id:
        data['message_thread_id'] = int(thread_id)
    
    try:
        resp = requests.post(api_url, json=data, timeout=10)
        
        if resp.status_code == 200:
            print(f"  ✅ Telegram: {repo} - {tag}")
            time.sleep(0.3)  # Avoid flood
            return True
        else:
            print(f"  ❌ Telegram Error: {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Telegram failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════

def load_state() -> Dict:
    """Load persistent state"""
    try:
        with open(STATE_FILE, 'r') as f:
            s = json.load(f)
            # Convert lists back to sets
            s['known_repos'] = set(s.get('known_repos', []))
            s['posted_events'] = set(s.get('posted_events', []))
            return s
    except:
        return {
            'known_repos': set(),
            'posted_events': set(),
            'last_run': None
        }

def save_state(state: Dict):
    """Save persistent state"""
    try:
        # Convert sets to lists for JSON
        state_copy = state.copy()
        state_copy['known_repos'] = sorted(list(state['known_repos']))
        state_copy['posted_events'] = sorted(list(state['posted_events']))
        state_copy['last_run'] = datetime.now(timezone.utc).isoformat()
        
        with open(STATE_FILE, 'w') as f:
            json.dump(state_copy, f, indent=2)
        
        print(f"  💾 State saved: {len(state['known_repos'])} repos, {len(state['posted_events'])} events")
    except Exception as e:
        print(f"  ⚠️ State save failed: {e}")

# ═══════════════════════════════════════════════════════════
# MAIN BOT
# ═══════════════════════════════════════════════════════════

def main():
    """Main Bot Execution"""
    
    print("=" * 70)
    print("🎯 FLIPPER ZERO BOT v15.0 - OPTIMIZED & COMPLETE")
    print("=" * 70)
    
    # Load State
    state = load_state()
    print(f"\n📂 Loaded State: {len(state['known_repos'])} known repos, {len(state['posted_events'])} posted events")
    
    # Rate Limit Check
    if not check_rate_limit():
        print("⚠️ Rate Limit zu niedrig - Abbruch")
        return
    
    # PHASE 1: Repository Discovery
    print("\n" + "=" * 70)
    print("PHASE 1: REPOSITORY DISCOVERY")
    print("=" * 70)
    
    new_repos = optimized_search()
    
    # Merge with known repos
    before_count = len(state['known_repos'])
    state['known_repos'].update(new_repos)
    after_count = len(state['known_repos'])
    new_count = after_count - before_count
    
    print(f"\n📊 Repository Stats:")
    print(f"   Neu gefunden: {new_count}")
    print(f"   Gesamt bekannt: {after_count}")
    
    # PHASE 2: RSS Release Check
    print("\n" + "=" * 70)
    print("PHASE 2: RSS RELEASE CHECK (0 API!)")
    print("=" * 70)
    
    all_updates = check_all_rss(state['known_repos'], state)
    
    # PHASE 3: Telegram Posting
    if all_updates:
        print("\n" + "=" * 70)
        print(f"PHASE 3: TELEGRAM POSTING ({len(all_updates)} updates)")
        print("=" * 70 + "\n")
        
        posted = 0
        for update in all_updates[:50]:  # Max 50 pro Run
            if post_to_telegram(update):
                posted += 1
        
        print(f"\n  ✅ Posted {posted}/{len(all_updates)} updates to Telegram")
    else:
        print("\n  ℹ️ Keine neuen Updates zum Posten")
    
    # Save State
    print("\n" + "=" * 70)
    save_state(state)
    
    # Final Summary
    print("\n" + "=" * 70)
    print("✅ BOT RUN COMPLETE!")
    print("=" * 70)
    print(f"   Known Repos: {len(state['known_repos'])}")
    print(f"   New Releases Found: {len(all_updates)}")
    print(f"   Posted to Telegram: {min(len(all_updates), 50)}")
    print(f"   Total Events Tracked: {len(state['posted_events'])}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
