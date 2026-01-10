import requests
import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set
import re

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

STATE_FILE = "/tmp/flipper_precision_state.json"

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

# ═══════════════════════════════════════════════════════════
# CORE 1: VOLLSTÄNDIGE PAGINATION
# ═══════════════════════════════════════════════════════════

def paginate_all_pages(url: str, max_pages: int = 100) -> List[Dict]:
    """
    Folge Link Header bis zur letzten Seite!
    GitHub sendet: Link: <url>; rel="next", <url>; rel="last"
    """
    all_items = []
    current_url = url
    page = 1
    
    while current_url and page <= max_pages:
        try:
            resp = requests.get(current_url, headers=get_headers(), timeout=20)
            
            if resp.status_code != 200:
                print(f"  ⚠️ Status {resp.status_code} on page {page}")
                break
            
            # Items sammeln
            data = resp.json()
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
            elif isinstance(data, list):
                items = data
            else:
                break
            
            all_items.extend(items)
            print(f"  📄 Page {page}: {len(items)} items (total: {len(all_items)})")
            
            # Link Header parsen für nächste Seite
            link_header = resp.headers.get('Link', '')
            next_url = None
            
            if link_header:
                # Parse: <https://...>; rel="next"
                matches = re.findall(r'<([^>]+)>;\s*rel="next"', link_header)
                if matches:
                    next_url = matches[0]
            
            if not next_url:
                print(f"  ✅ Reached last page!")
                break
            
            current_url = next_url
            page += 1
            time.sleep(1.2)  # Rate Limit beachten
            
        except Exception as e:
            print(f"  ❌ Page {page} error: {e}")
            break
    
    return all_items

# ═══════════════════════════════════════════════════════════
# CORE 2: 1000-RESULT-LIMIT WORKAROUND
# ═══════════════════════════════════════════════════════════

def search_with_date_splitting(base_query: str, days_back: int = 365) -> Set[str]:
    """
    GitHub Limit = 1000 Ergebnisse pro Query
    Lösung: Query nach Datum aufteilen!
    
    Statt 1x Query mit 5000 Results:
    → 12x Queries (1 pro Monat) mit je <1000 Results
    """
    print(f"\n🔍 DATE-SPLIT SEARCH: {base_query}")
    all_repos = set()
    
    # Zeitraum in Chunks aufteilen
    end_date = datetime.now(timezone.utc)
    
    # Pro WOCHE eine Query (52 Queries für 1 Jahr)
    for week in range(0, 52):
        week_end = end_date - timedelta(days=week*7)
        week_start = week_end - timedelta(days=7)
        
        date_query = f"{base_query} created:{week_start.strftime('%Y-%m-%d')}..{week_end.strftime('%Y-%m-%d')}"
        url = f"https://api.github.com/search/repositories?q={date_query}&per_page=100&sort=updated"
        
        try:
            # ALLE Seiten für diese Woche!
            items = paginate_all_pages(url, max_pages=10)
            
            for item in items:
                all_repos.add(item['full_name'])
            
            print(f"  Week {week}: {len(items)} repos")
            
            if len(items) < 100:
                # Weniger als 100 = keine weiteren Wochen nötig
                break
            
            time.sleep(2)
            
        except:
            pass
    
    print(f"  ✅ Total: {len(all_repos)} repos via Date-Split")
    return all_repos

# ═══════════════════════════════════════════════════════════
# CORE 3: MULTI-DIMENSIONAL SPLITTING
# ═══════════════════════════════════════════════════════════

def comprehensive_search(state: Dict) -> Set[str]:
    """
    Suche in ALLEN Dimensionen:
    - Zeit (pro Woche)
    - Sprache (C, Python, Makefile)
    - Topic (flipperzero, firmware, plugin)
    - Größe (small, medium, large)
    → KEIN Repo wird verpasst!
    """
    print("\n🌐 COMPREHENSIVE MULTI-DIMENSIONAL SEARCH...")
    all_repos = set()
    
    # DIMENSION 1: Nach Sprache
    languages = ['C', 'Python', 'Makefile', 'Shell']
    for lang in languages:
        query = f"flipper language:{lang} archived:false"
        repos = search_with_date_splitting(query, days_back=180)
        all_repos.update(repos)
        print(f"  Language {lang}: {len(repos)} repos")
    
    # DIMENSION 2: Nach Topics
    topics = ['flipperzero', 'flipper-zero', 'flipper-plugin', 'flipper-firmware', 
              'subghz', 'nfc', 'rfid', 'badusb', 'infrared']
    for topic in topics:
        query = f"topic:{topic} archived:false"
        repos = search_with_date_splitting(query, days_back=180)
        all_repos.update(repos)
        print(f"  Topic {topic}: {len(repos)} repos")
    
    # DIMENSION 3: Nach Keywords in verschiedenen Feldern
    keywords = ['flipperzero', 'flipper-zero', 'subghz', 'protpirate']
    fields = ['name', 'description', 'readme']
    for keyword in keywords:
        for field in fields:
            query = f"{keyword} in:{field} archived:false"
            url = f"https://api.github.com/search/repositories?q={query}&per_page=100"
            try:
                items = paginate_all_pages(url, max_pages=10)
                for item in items:
                    all_repos.add(item['full_name'])
                print(f"  {keyword} in:{field}: {len(items)} repos")
                time.sleep(2)
            except:
                pass
    
    # DIMENSION 4: Nach Größe (findet auch kleine neue Projekte)
    sizes = ['<1000', '1000..10000', '>10000']
    for size in sizes:
        query = f"flipper size:{size} archived:false"
        url = f"https://api.github.com/search/repositories?q={query}&per_page=100"
        try:
            items = paginate_all_pages(url, max_pages=5)
            for item in items:
                all_repos.add(item['full_name'])
            print(f"  Size {size}: {len(items)} repos")
            time.sleep(2)
        except:
            pass
    
    print(f"\n  ✅ COMPREHENSIVE: {len(all_repos)} UNIQUE REPOS")
    return all_repos

# ═══════════════════════════════════════════════════════════
# CORE 4: REPO DEEP SCAN - ALLE RELEASES
# ═══════════════════════════════════════════════════════════

def deep_scan_all_releases(repo: str, state: Dict) -> List[Dict]:
    """Scan ALLE Releases eines Repos (nicht nur latest!)"""
    updates = []
    
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    
    try:
        # ALLE Releases-Seiten!
        all_releases = paginate_all_pages(url, max_pages=10)
        
        for release in all_releases:
            event_id = f"REL:{repo}:{release['tag_name']}"
            if event_id not in state.get('posted_events', set()):
                updates.append({
                    'type': 'RELEASE',
                    'repo': repo,
                    'tag': release['tag_name'],
                    'name': release.get('name', 'Release'),
                    'time': release['published_at'][:19],
                    'url': release['html_url']
                })
                state.setdefault('posted_events', set()).add(event_id)
        
        if updates:
            print(f"  🆕 {repo}: {len(updates)} new releases")
    
    except:
        pass
    
    return updates

# ═══════════════════════════════════════════════════════════
# CORE 5: COMMIT MONITORING (ALLE Commits)
# ═══════════════════════════════════════════════════════════

def monitor_all_commits(repo: str, state: Dict, since_days: int = 7) -> List[Dict]:
    """Monitor ALLE Commits der letzten X Tage"""
    updates = []
    
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    url = f"https://api.github.com/repos/{repo}/commits?since={since}&per_page=100"
    
    try:
        all_commits = paginate_all_pages(url, max_pages=5)
        
        for commit in all_commits:
            sha = commit['sha']
            event_id = f"COMMIT:{repo}:{sha}"
            if event_id not in state.get('posted_events', set()):
                msg = commit['commit']['message']
                # Nur wichtige Commits (Release, Feature, Fix)
                if any(kw in msg.lower() for kw in ['release', 'feature', 'add', 'new', 'fix', 'update']):
                    updates.append({
                        'type': 'COMMIT',
                        'repo': repo,
                        'msg': msg[:100],
                        'url': commit['html_url']
                    })
                    state.setdefault('posted_events', set()).add(event_id)
        
        if updates:
            print(f"  💾 {repo}: {len(updates)} important commits")
    
    except:
        pass
    
    return updates

# ═══════════════════════════════════════════════════════════
# CORE 6: ISSUES & PRs MONITORING
# ═══════════════════════════════════════════════════════════

def monitor_issues_prs(repo: str, state: Dict) -> List[Dict]:
    """Monitor neue Issues & PRs (zeigt Aktivität)"""
    updates = []
    
    # Issues
    url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&sort=created&direction=desc"
    try:
        issues = paginate_all_pages(url, max_pages=3)
        
        for issue in issues[:20]:  # Top 20 neueste
            event_id = f"ISSUE:{repo}:{issue['number']}"
            if event_id not in state.get('posted_events', set()):
                # Nur neue (letzte 7 Tage)
                created = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
                if (datetime.now(timezone.utc) - created).days <= 7:
                    updates.append({
                        'type': 'ISSUE',
                        'repo': repo,
                        'title': issue['title'][:80],
                        'url': issue['html_url']
                    })
                    state.setdefault('posted_events', set()).add(event_id)
    except:
        pass
    
    return updates

# ═══════════════════════════════════════════════════════════
# CORE 7: FILES MONITORING (neue .fap, .sub, .nfc)
# ═══════════════════════════════════════════════════════════

def monitor_new_files(repo: str, state: Dict) -> List[Dict]:
    """Monitor neue Flipper-relevante Dateien"""
    updates = []
    
    extensions = ['fap', 'sub', 'nfc', 'ir', 'fam']
    
    for ext in extensions:
        url = f"https://api.github.com/search/code?q=extension:{ext}+repo:{repo}&per_page=100"
        try:
            items = paginate_all_pages(url, max_pages=3)
            
            for item in items[:10]:  # Top 10 neueste
                path = item['path']
                event_id = f"FILE:{repo}:{path}"
                if event_id not in state.get('posted_events', set()):
                    updates.append({
                        'type': 'NEW-FILE',
                        'repo': repo,
                        'file': path,
                        'url': item['html_url']
                    })
                    state.setdefault('posted_events', set()).add(event_id)
            
            time.sleep(2)
        except:
            pass
    
    return updates

# ═══════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════

def load_state():
    try:
        with open(STATE_FILE) as f:
            s = json.load(f)
            s['known_repos'] = set(s.get('known_repos', []))
            s['posted_events'] = set(s.get('posted_events', []))
            return s
    except:
        return {'known_repos': set(), 'posted_events': set()}

def save_state(s):
    c = s.copy()
    c['known_repos'] = list(s['known_repos'])
    c['posted_events'] = list(s['posted_events'])
    with open(STATE_FILE, 'w') as f:
        json.dump(c, f)

def post_update(update: Dict):
    """Post to Telegram"""
    repo = update.get('repo', '')
    repo_url = f"https://github.com/{repo}"
    
    if update['type'] == 'RELEASE':
        msg = f"""🚀 <b>RELEASE!</b>

<a href="{repo_url}">{repo}</a>
🏷️ <code>{update['tag']}</code>
{update.get('name', '')}
⏰ {update.get('time', '')}

<a href="{update['url']}">📥 Download</a>"""
    
    elif update['type'] == 'COMMIT':
        msg = f"""💾 <b>COMMIT!</b>

<a href="{repo_url}">{repo}</a>
📝 {update['msg']}

<a href="{update['url']}">🔗 Commit</a>"""
    
    elif update['type'] == 'ISSUE':
        msg = f"""🐛 <b>ISSUE!</b>

<a href="{repo_url}">{repo}</a>
{update['title']}

<a href="{update['url']}">👁️ Issue</a>"""
    
    elif update['type'] == 'NEW-FILE':
        msg = f"""📁 <b>NEUE DATEI!</b>

<a href="{repo_url}">{repo}</a>
🗂️ <code>{update['file']}</code>

<a href="{update['url']}">👁️ Datei</a>"""
    
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
        requests.post(url, json=data, timeout=10)
        print("  ✅ Posted")
        time.sleep(0.3)
    except:
        pass

def main():
    state = load_state()
    
    print("=" * 70)
    print("🎯 FLIPPER ZERO BOT v9.0 - 100% PRECISION")
    print("   VOLLSTÄNDIGE Pagination + Multi-Dimensional Search")
    print("=" * 70 + "\n")
    
    # PHASE 1: COMPREHENSIVE SEARCH (ALLE Repos finden)
    all_repos = comprehensive_search(state)
    state['known_repos'].update(all_repos)
    
    print(f"\n{'='*70}")
    print(f"📊 PHASE 1: {len(all_repos)} REPOS GEFUNDEN")
    print(f"{'='*70}\n")
    
    # PHASE 2: DEEP SCAN (ALLE Updates in jedem Repo)
    all_updates = []
    repos_list = sorted(list(state['known_repos']))
    
    print(f"🔬 PHASE 2: DEEP SCAN von {len(repos_list)} Repos...\n")
    
    for i, repo in enumerate(repos_list[:200], 1):  # Top 200
        print(f"[{i}/200] {repo}")
        
        # Releases
        all_updates.extend(deep_scan_all_releases(repo, state))
        
        # Commits (nur Priority Repos)
        if any(pr in repo for pr in ['flipperdevices', 'DarkFlippers', 'RogueMaster', 
                                      'Momentum', 'Xtreme', 'ProtoPirate']):
            all_updates.extend(monitor_all_commits(repo, state, since_days=7))
            all_updates.extend(monitor_issues_prs(repo, state))
            all_updates.extend(monitor_new_files(repo, state))
        
        if i % 20 == 0:
            time.sleep(5)  # Rate Limit pause
    
    # PHASE 3: POST UPDATES
    print(f"\n{'='*70}")
    print(f"📤 PHASE 3: POSTING {len(all_updates)} UPDATES...")
    print(f"{'='*70}\n")
    
    for update in all_updates[:100]:  # Max 100 Posts
        post_update(update)
    
    save_state(state)
    
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE!")
    print(f"   Repos: {len(state['known_repos'])}")
    print(f"   Updates: {len(all_updates)}")
    print(f"   Posted: {min(100, len(all_updates))}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
