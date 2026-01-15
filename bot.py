import requests
import os
import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set

# Config
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
STATE_FILE = "/tmp/flipper_state_v2.json"

# Filter-Konstanten
LOOKBACK_HOURS = 24  # Nur Änderungen letzte X Stunden
MIN_STARS = 5
FLIPPER_KEYWORDS = re.compile(r'(flipperzero|subghz|nfc|rfid|fap|applications)', re.I)
BLACKLIST_REPOS = {"DigitalNZ/plug", "PyMoDAQ/pymodaq_plugins", "adoptware/pinball"}

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            # Migrate alte State falls vorhanden
            state.setdefault("last_run", datetime.now(timezone.utc).isoformat())
            state.setdefault("known_releases", {})
            state.setdefault("known_commits", {})
            return state
    except:
        return {"last_run": datetime.now(timezone.utc).isoformat(), "known_releases": {}, "known_commits": {}}

def save_state(state: Dict):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def is_recent(timestamp_str: str) -> bool:
    """Check ob Release/Commit in LOOKBACK_HOURS liegt"""
    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    return (datetime.now(timezone.utc) - dt) < timedelta(hours=LOOKBACK_HOURS)

def search_repos(query: str, page: int = 1) -> List[Dict]:
    """GitHub Search mit Filtern"""
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=30&page={page}"
    resp = requests.get(url, headers=HEADERS).json()
    return [r for r in resp.get('items', []) if (
        r['stargazers_count'] >= MIN_STARS and
        not r.get('fork', True) and  # Keine Forks
        r['created_at'] > '2025-01-01T00:00:00Z'  # <1 Jahr alt
    )][:10]  # Top 10

def get_new_releases(owner: str, repo: str, state: Dict) -> List[Dict]:
    """Neueste Releases mit Filter"""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"
    resp = requests.get(url, headers=HEADERS).json()
    repo_key = f"{owner}/{repo}"
    known = set(state["known_releases"].get(repo_key, []))
    new = []
    
    for r in resp:
        tag = r.get('tag_name', '')
        published = r.get('published_at', '')
        body = r.get('body', '')
        if (tag not in known and 
            is_recent(published) and 
            FLIPPER_KEYWORDS.search(body or r.get('name', ''))):
            new.append({
                'tag': tag, 'url': r['html_url'], 'published': published[:19],
                'name': r.get('name', 'Unnamed')
            })
    
    state["known_releases"][repo_key] = [r['tag_name'] for r in resp[:10]]
    return new

def get_recent_commits(owner: str, repo: str, state: Dict) -> List[Dict]:
    """Neueste Commits mit File-Filter"""
    since = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat() + 'Z'
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?since={since}&per_page=3"
    resp = requests.get(url, headers=HEADERS).json()
    repo_key = f"{owner}/{repo}_commits"
    known_shas = set(state["known_commits"].get(repo_key, []))
    new = []
    
    for c in resp:
        sha = c['sha'][:7]
        if sha not in known_shas:
            files = c.get('files', [])
            flipper_files = [f for f in files if FLIPPER_KEYWORDS.search(f.get('filename', ''))]
            if flipper_files:  # Nur wenn Flipper-relevante Files geändert
                new.append({
                    'sha': sha, 'message': c['commit']['message'][:50],
                    'url': c['html_url'], 'files': len(flipper_files)
                })
    
    state["known_commits"][repo_key] = [c['sha'][:7] for c in resp]
    return new

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        print(f"[DRY-RUN] Würde posten: {msg[:100]}...")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHANNEL, "text": msg, "parse_mode": "HTML"})

def main():
    print("🚀 Flipper Zero News Bot v2.0 startet...")
    state = load_state()
    
    # 1. Suche frische Repos
    queries = [
        "topic:flipperzero stars:>5 -fork:true",
        "flipperzero filename:.fap OR path:applications/ language:C",
        "subghz OR nfc flipperzero stars:>5"
    ]
    all_repos: Set[str] = set()
    for q in queries:
        for repo in search_repos(q):
            name = f"{repo['owner']['login']}/{repo['name']}"
            if name not in BLACKLIST_REPOS:
                all_repos.add(name)
    
    print(f"📊 {len(all_repos)} Kandidaten-Repos gefunden")
    
    # 2. Check Releases & Commits
    posts = []
    for repo in sorted(all_repos)[:20]:  # Top 20 priorisieren
        owner, name = repo.split('/')
        new_rel = get_new_releases(owner, name, state)
        if new_rel:
            posts.append(f"🚀 {len(new_rel)} NEUE RELEASES!\n📦 <b>{repo}</b>\n" +
                        "\n".join([f"🏷️ <a href='{r['url']}'>{r['tag']}</a> ({r['published']})" for r in new_rel]) +
                        f"\n📅 <a href='https://github.com/{repo}/releases'>Alle ansehen</a>")
        
        new_com = get_recent_commits(owner, name, state)
        if new_com:
            posts.append(f"🔄 {len(new_com)} NEUE COMMITS!\n📦 <b>{repo}</b>\n" +
                        "\n".join([f"💾 <a href='{c['url']}'>{c['sha']}</a> {c['message']} (+{c['files']} Flipper-Dateien)" for c in new_com]))
        
        time.sleep(0.5)  # Rate-Limit Schutz
    
    # 3. Posten & Save
    for post in posts[:10]:  # Max 10 Posts pro Run
        send_telegram(post)
        time.sleep(1)
    
    save_state(state)
    print(f"✅ {len(posts)} Posts generiert/gesendet. State gespeichert.")

if __name__ == "__main__":
    main()
