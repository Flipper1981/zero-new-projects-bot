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

# WICHTIG: Nur Releases der letzten X Tage posten
RELEASE_AGE_DAYS = int(os.environ.get("RELEASE_AGE_DAYS", "90"))  # Default: 90 Tage

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
        
        return search['remaining'] > 5
    except Exception as e:
        print(f"⚠️ Rate Limit Check failed: {e}")
        return True

# ═══════════════════════════════════════════════════════════
# OPTIMIERTE BREITE SUCHE
# ═══════════════════════════════════════════════════════════

def optimized_search() -> Set[str]:
    """Breite effiziente Queries - findet 597+ Repos"""
    print("\n🔍 OPTIMIERTE REPO SUCHE...\n")
    all_repos = set()
    
    base_queries = [
        "flipper archived:false",
        "flipperzero archived:false",
        "flipper-zero archived:false",
        "topic:flipperzero",
        "topic:flipper-zero",
        "topic:flipper",
        "topic:flipper-app",
        "topic:flipper-plugin",
        "subghz archived:false",
        "flipper nfc archived:false",
        "flipper badusb archived:false",
        "flipper infrared archived:false",
        "flipper rfid archived:false",
        "flipper language:C archived:false",
        "flipper language:Python archived:false",
        "flipper language:Rust archived:false",
        "unleashed firmware archived:false",
        "roguemaster archived:false",
        "momentum firmware flipper archived:false",
        "xtreme firmware flipper archived:false",
        "flipper stars:>5 archived:false",
        "flipper stars:>20 archived:false",
        "flipper stars:>50 archived:false",
        "flipper forks:>3 archived:false",
        "fap flipper archived:false",
        "flipper application archived:false",
        "flipper tool archived:false",
        "flipper game archived:false",
        "flipper esp32 archived:false",
        "flipper gpio archived:false",
        "flipper wifi archived:false",
        "flipper sdk archived:false",
        "flipper api archived:false",
        "ufbt archived:false",
        "flipper pushed:>2025-01-01 archived:false",
        "flipper pushed:>2025-11-01 archived:false"
    ]
    
    for i, query in enumerate(base_queries, 1):
        url = f"https://api.github.com/search/repositories?q={query}&per_page=100&sort=updated"
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
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
            
            time.sleep(2.5)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    print(f"\n  ✅ GEFUNDEN: {len(all_repos)} unique repos!\n")
    return all_repos

# ═══════════════════════════════════════════════════════════
# RSS FEEDS MIT ZEIT-FILTER
# ═══════════════════════════════════════════════════════════

def is_recent_release(published_str: str, days: int = RELEASE_AGE_DAYS) -> bool:
    """
    Check ob Release aktuell genug ist
    
    published_str: "2026-01-11T10:30:00Z" oder "2026-01-11 10:30:00"
    days: Max Alter in Tagen
    
    Returns: True wenn Release neuer als X Tage
    """
    try:
        # Parse verschiedene Formate
        if 'T' in published_str:
            dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(published_str, '%Y-%m-%d %H:%M:%S')
            dt = dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age = now - dt
        
        return age.days <= days
    except Exception as e:
        # Bei Parse-Fehler: Lieber posten als übersehen
        return True

def check_rss_releases(repo: str, state: Dict, first_run: bool = False) -> List[Dict]:
    """
    RSS Feed Check mit Zeit-Filter
    
    first_run: Bei erstem Run NUR letzte 7 Tage (sonst Spam!)
    """
    updates = []
    feed_url = f"https://github.com/{repo}/releases.atom"
    
    # First Run: Nur 7 Tage, sonst normaler Filter
    age_limit = 7 if first_run else RELEASE_AGE_DAYS
    
    try:
        resp = requests.get(feed_url, timeout=8)
        if resp.status_code != 200:
            return []
        
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns)[:10]:  # Max 10 neueste
            title_elem = entry.find('atom:title', ns)
            link_elem = entry.find('atom:link', ns)
            published_elem = entry.find('atom:published', ns)
            
            if title_elem is None or link_elem is None:
                continue
            
            title = title_elem.text or ""
            link = link_elem.get('href', '')
            published = published_elem.text if published_elem is not None else ""
            
            # ZEIT-FILTER: Nur aktuelle Releases!
            if published and not is_recent_release(published, age_limit):
                continue  # Skip alte Releases
            
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
                    'time': published[:19].replace('T', ' ') if published else '',
                    'event_id': event_id
                })
        
        time.sleep(0.1)
        
    except Exception:
        pass
    
    return updates

def check_all_rss(repos: Set[str], state: Dict) -> List[Dict]:
    """RSS Check für alle Repos"""
    
    # Detect First Run
    first_run = len(state.get('posted_events', set())) == 0
    
    if first_run:
        print(f"\n📡 RSS CHECK - FIRST RUN (nur letzte 7 Tage!)")
        print(f"   (Verhindert Spam von alten Releases)\n")
    else:
        print(f"\n📡 RSS RELEASE CHECK ({len(repos)} repos, letzte {RELEASE_AGE_DAYS} Tage)...\n")
    
    all_updates = []
    old_skipped = 0
    
    for i, repo in enumerate(sorted(repos), 1):
        updates = check_rss_releases(repo, state, first_run)
        
        if updates:
            print(f"  [{i:4d}] 🆕 {repo:50s} → {len(updates)} releases")
            all_updates.extend(updates)
        
        if i % 100 == 0:
            print(f"\n  📊 Progress: {i}/{len(repos)} repos, {len(all_updates)} updates\n")
            time.sleep(1)
    
    print(f"\n  ✅ RSS CHECK COMPLETE: {len(all_updates)} neue Releases!\n")
    
    if first_run:
        print(f"  ℹ️ First Run: Alte Releases gefiltert (nur 7 Tage)")
        print(f"  ℹ️ Nächste Runs: Normale {RELEASE_AGE_DAYS} Tage Filter\n")
    
    return all_updates

# ═══════════════════════════════════════════════════════════
# GRUPPIERUNG NACH REPO
# ═══════════════════════════════════════════════════════════

def group_updates_by_repo(updates: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Gruppiert Updates nach Repository
    
    Beispiel:
    Input:  [
        {repo: "A", tag: "v2"},
        {repo: "A", tag: "v1"},
        {repo: "B", tag: "v1"}
    ]
    Output: {
        "A": [{tag: "v2"}, {tag: "v1"}],  # Sortiert: neueste zuerst
        "B": [{tag: "v1"}]
    }
    """
    grouped = {}
    
    for update in updates:
        repo = update.get('repo', '')
        if repo not in grouped:
            grouped[repo] = []
        grouped[repo].append(update)
    
    # Sortiere Releases pro Repo (neueste zuerst)
    for repo in grouped:
        grouped[repo].sort(key=lambda x: x.get('time', ''), reverse=True)
    
    return grouped

# ═══════════════════════════════════════════════════════════
# TELEGRAM - GROUPED POSTS
# ═══════════════════════════════════════════════════════════

def post_repo_updates_to_telegram(repo: str, updates: List[Dict]) -> bool:
    """
    Post ALLE Updates eines Repos in EINEM Post
    
    1 Release:
    🚀 NEUE RELEASE!
    📦 repo
    🏷️ v1.0
    
    Mehrere Releases:
    🚀 5 NEUE RELEASES!
    📦 repo
    🏷️ v1.5 (neueste)
    🏷️ v1.4
    🏷️ v1.3
    🏷️ v1.2
    🏷️ v1.1
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        return False
    
    if not updates:
        return False
    
    repo_url = f"https://github.com/{repo}"
    count = len(updates)
    
    # Neueste Release Info (updates ist bereits sortiert!)
    latest = updates[0]
    latest_tag = latest.get('tag', 'unknown')
    latest_time = latest.get('time', 'Jetzt')
    latest_url = latest.get('url', repo_url)
    
    # Baue Release Liste
    if count == 1:
        # Einzelnes Release: Klassisches Format
        msg = f"""🚀 <b>NEUE RELEASE!</b>

📦 <a href="{repo_url}">{repo}</a>
🏷️ <code>{latest_tag}</code>
⏰ {latest_time}

<a href="{latest_url}">📥 Release ansehen</a>"""
    
    else:
        # Multiple Releases: Gruppiert
        release_list = []
        
        for i, update in enumerate(updates[:10], 1):  # Max 10 anzeigen
            tag = update.get('tag', 'unknown')
            if i == 1:
                release_list.append(f"🏷️ <code>{tag}</code> (neueste)")
            else:
                release_list.append(f"🏷️ <code>{tag}</code>")
        
        # Mehr als 10? Hinweis
        if count > 10:
            release_list.append(f"<i>... und {count - 10} weitere</i>")
        
        releases_text = "\n".join(release_list)
        
        msg = f"""🚀 <b>{count} NEUE RELEASES!</b>

📦 <a href="{repo_url}">{repo}</a>

{releases_text}

📅 Neueste: {latest_time}
<a href="{latest_url}">📥 Alle Releases ansehen</a>"""
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    data = {
        'chat_id': TELEGRAM_CHANNEL,
        'text': msg,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    
    # Optional: Thread ID
    thread_id = os.environ.get("THREAD_ID", "")
    if thread_id:
        try:
            data['message_thread_id'] = int(thread_id)
        except:
            pass
    
    # POST mit Retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(api_url, json=data, timeout=10)
            
            if resp.status_code == 200:
                if count == 1:
                    print(f"  ✅ Telegram: {repo} - {latest_tag}")
                else:
                    print(f"  ✅ Telegram: {repo} ({count} releases)")
                time.sleep(3)  # Rate Limit Safe: 20 msg/min
                return True
            
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 60))
                print(f"  ⏳ Rate Limit! Warte {retry_after}s...")
                time.sleep(retry_after)
                continue
            
            else:
                error_msg = resp.json().get('description', 'Unknown')
                print(f"  ❌ Telegram Error {resp.status_code}: {error_msg}")
                
                if "chat not found" in error_msg.lower():
                    print(f"\n  ⚠️⚠️⚠️ FALSCHER CHANNEL! Check CHANNEL_ID! ⚠️⚠️⚠️\n")
                
                return False
                
        except Exception as e:
            print(f"  ❌ Telegram failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return False
    
    return False

# ═══════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════

def load_state() -> Dict:
    """Load persistent state"""
    try:
        with open(STATE_FILE, 'r') as f:
            s = json.load(f)
            s['known_repos'] = set(s.get('known_repos', []))
            s['posted_events'] = set(s.get('posted_events', []))
            return s
    except:
        return {
            'known_repos': set(),
            'posted_events': set(),
            'last_run': None,
            'post_offset': 0
        }

def save_state(state: Dict):
    """Save persistent state"""
    try:
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
    print("🎯 FLIPPER ZERO BOT v15.2 FINAL - FULLY OPTIMIZED")
    print("=" * 70)
    
    # Validate Config
    if not TELEGRAM_TOKEN:
        print("⚠️ TELEGRAM_TOKEN fehlt!")
        return
    
    if not TELEGRAM_CHANNEL:
        print("⚠️ CHANNEL_ID fehlt!")
        return
    
    if not TELEGRAM_CHANNEL.startswith("-100"):
        print(f"⚠️ WARNUNG: CHANNEL_ID sollte mit -100 starten!")
        print(f"   Aktuell: {TELEGRAM_CHANNEL}\n")
    
    # Load State
    state = load_state()
    first_run = len(state.get('posted_events', set())) == 0
    
    print(f"\n📂 Loaded State:")
    print(f"   Known Repos: {len(state['known_repos'])}")
    print(f"   Posted Events: {len(state['posted_events'])}")
    print(f"   Post Offset: {state.get('post_offset', 0)}")
    
    if first_run:
        print(f"   🆕 FIRST RUN DETECTED!")
        print(f"   ℹ️ Nur Releases der letzten 7 Tage werden gepostet\n")
    else:
        print(f"   ℹ️ Release Filter: Letzte {RELEASE_AGE_DAYS} Tage\n")
    
    # Rate Limit Check
    if not check_rate_limit():
        print("⚠️ Rate Limit zu niedrig - nur RSS Check")
        new_repos = set()
    else:
        # PHASE 1: Repository Discovery
        print("\n" + "=" * 70)
        print("PHASE 1: REPOSITORY DISCOVERY")
        print("=" * 70)
        
        new_repos = optimized_search()
        
        before_count = len(state['known_repos'])
        state['known_repos'].update(new_repos)
        after_count = len(state['known_repos'])
        new_count = after_count - before_count
        
        print(f"\n📊 Repository Stats:")
        print(f"   Neu gefunden: {new_count}")
        print(f"   Gesamt bekannt: {after_count}")
    
    # PHASE 2: RSS Release Check mit Zeit-Filter
    print("\n" + "=" * 70)
    print("PHASE 2: RSS RELEASE CHECK (ZEIT-GEFILTERT)")
    print("=" * 70)
    
    all_updates = check_all_rss(state['known_repos'], state)
    
    # Filter: Nur noch nicht gepostete
    unposted_updates = [
        u for u in all_updates 
        if u.get('event_id') not in state['posted_events']
    ]
    
    print(f"\n  📋 Noch nicht gepostet: {len(unposted_updates)}/{len(all_updates)}")
    
    # PHASE 3: Telegram Posting (GROUPED!)
    if unposted_updates:
        print("\n" + "=" * 70)
        print(f"PHASE 3: TELEGRAM POSTING (GROUPED)")
        print("=" * 70 + "\n")
        
        # GRUPPIERE NACH REPO
        grouped = group_updates_by_repo(unposted_updates)
        
        print(f"  📊 {len(unposted_updates)} updates von {len(grouped)} repos")
        print(f"  ℹ️ Gruppiert: 1 Post pro Repo (statt {len(unposted_updates)} Posts!)\n")
        
        # Sortiere Repos (meiste Releases zuerst, dann alphabetisch)
        sorted_repos = sorted(
            grouped.items(), 
            key=lambda x: (-len(x[1]), x[0])
        )
        
        # Zeige Top 10 Repos mit meisten Releases
        print(f"  🔝 Top Repos mit meisten Releases:")
        for repo, updates in sorted_repos[:10]:
            print(f"     {repo:50s} → {len(updates)} releases")
        print()
        
        # BATCH: Max 20 REPOS/run
        BATCH_SIZE = 20
        offset = state.get('post_offset', 0)
        
        batch_repos = sorted_repos[offset:offset + BATCH_SIZE]
        
        print(f"  📤 Poste Repos {offset+1} bis {offset+len(batch_repos)} von {len(sorted_repos)} total\n")
        
        posted_repos = 0
        posted_releases = 0
        failed = 0
        
        for repo_name, repo_updates in batch_repos:
            if post_repo_updates_to_telegram(repo_name, repo_updates):
                posted_repos += 1
                posted_releases += len(repo_updates)
                
                # Mark ALLE Releases dieses Repos als gepostet
                for update in repo_updates:
                    state['posted_events'].add(update.get('event_id'))
            else:
                failed += 1
                if failed >= 3:
                    print(f"\n  ⚠️ Zu viele Fehler - Check Config!\n")
                    break
            
            # Progress
            if posted_repos % 5 == 0:
                print(f"\n  📊 {posted_repos} repos, {posted_releases} releases posted\n")
        
        # Update Offset
        if posted_repos > 0:
            state['post_offset'] = offset + posted_repos
        
        # Reset wenn fertig
        if state['post_offset'] >= len(sorted_repos):
            state['post_offset'] = 0
            print(f"\n  ✅ Alle Repos gepostet! Offset reset.\n")
        
        print(f"\n  ✅ Posted: {posted_repos} repos, {posted_releases} releases")
        print(f"  ℹ️ Nächster Run: Repo #{state['post_offset']+1}")
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
    print(f"   Total Releases Found: {len(all_updates)}")
    print(f"   Posted This Run: {posted_repos if unposted_updates else 0} repos / {posted_releases if unposted_updates else 0} releases")
    print(f"   Total Events Tracked: {len(state['posted_events'])}")
    
    if unposted_updates:
        pending = len(grouped) - state.get('post_offset', 0)
        print(f"   Pending Repos: {pending}")
    
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
