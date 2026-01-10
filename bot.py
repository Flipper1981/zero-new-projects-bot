import requests
import os
import json
from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Set

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

STATE_FILE = "/tmp/flipper_mega_state.json"

PRIORITY_REPOS = [
    "flipperdevices/flipperzero-firmware", "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins", "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware", "RocketGod-git/ProtoPiratein"
]

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

# ═══════════════════════════════════════════════════════════
# STRATEGIE 1: WATCHERS NETWORK
# ═══════════════════════════════════════════════════════════

def strategy_watchers_network(state: Dict) -> Set[str]:
    """Wer Flipper watchet → deren Subscriptions"""
    print("\n👁️ WATCHERS NETWORK...")
    repos = set()
    
    for priority_repo in PRIORITY_REPOS[:3]:
        try:
            watchers = requests.get(
                f"https://api.github.com/repos/{priority_repo}/subscribers?per_page=30",
                headers=get_headers(), timeout=10
            ).json()
            
            for watcher in watchers[:15]:
                subscriptions = requests.get(
                    f"https://api.github.com/users/{watcher['login']}/subscriptions?per_page=20",
                    headers=get_headers(), timeout=8
                ).json()
                
                for sub in subscriptions:
                    if any(kw in sub['full_name'].lower() for kw in ['flipper', 'subghz', 'nfc']):
                        repos.add(sub['full_name'])
                        print(f"  🔍 Via Watcher: {sub['full_name']}")
                
                time.sleep(0.5)
            
            time.sleep(1)
        except:
            pass
    
    print(f"  ✅ {len(repos)} via Watchers")
    return repos

# ═══════════════════════════════════════════════════════════
# STRATEGIE 2: STARGAZERS NETWORK
# ═══════════════════════════════════════════════════════════

def strategy_stargazers_network(state: Dict) -> Set[str]:
    """Stargazers → ihre Stars"""
    print("\n⭐ STARGAZERS NETWORK...")
    repos = set()
    
    for priority_repo in PRIORITY_REPOS[:2]:
        try:
            stargazers = requests.get(
                f"https://api.github.com/repos/{priority_repo}/stargazers?per_page=50",
                headers=get_headers(), timeout=10
            ).json()
            
            for user in stargazers[:20]:
                starred = requests.get(
                    f"https://api.github.com/users/{user['login']}/starred?per_page=30",
                    headers=get_headers(), timeout=8
                ).json()
                
                for star in starred:
                    if any(kw in star['full_name'].lower() for kw in ['flipper', 'fap', 'subghz']):
                        repos.add(star['full_name'])
                
                time.sleep(0.4)
            
            time.sleep(1)
        except:
            pass
    
    print(f"  ✅ {len(repos)} via Stargazers")
    return repos

# ═══════════════════════════════════════════════════════════
# STRATEGIE 3: FORK NETWORK
# ═══════════════════════════════════════════════════════════

def strategy_fork_network(state: Dict) -> Set[str]:
    """Forks + Forks-von-Forks"""
    print("\n🔱 FORK NETWORK...")
    repos = set()
    
    for priority_repo in PRIORITY_REPOS[:4]:
        try:
            forks = requests.get(
                f"https://api.github.com/repos/{priority_repo}/forks?sort=stargazers&per_page=50",
                headers=get_headers(), timeout=10
            ).json()
            
            for fork in forks[:30]:
                repos.add(fork['full_name'])
                
                # Forks-von-Forks!
                sub_forks = requests.get(
                    f"https://api.github.com/repos/{fork['full_name']}/forks?per_page=10",
                    headers=get_headers(), timeout=5
                ).json()
                
                for sf in sub_forks[:5]:
                    repos.add(sf['full_name'])
                
                time.sleep(0.3)
            
            time.sleep(1)
        except:
            pass
    
    print(f"  ✅ {len(repos)} via Forks")
    return repos

# ═══════════════════════════════════════════════════════════
# STRATEGIE 4: CONTRIBUTORS NETWORK
# ═══════════════════════════════════════════════════════════

def strategy_contributors_network(state: Dict) -> Set[str]:
    """Contributors → ihre Repos"""
    print("\n👨‍💻 CONTRIBUTORS NETWORK...")
    repos = set()
    
    for priority_repo in PRIORITY_REPOS[:3]:
        try:
            contributors = requests.get(
                f"https://api.github.com/repos/{priority_repo}/contributors?per_page=30",
                headers=get_headers(), timeout=10
            ).json()
            
            for dev in contributors[:15]:
                dev_repos = requests.get(
                    f"https://api.github.com/users/{dev['login']}/repos?sort=updated&per_page=20",
                    headers=get_headers(), timeout=8
                ).json()
                
                for r in dev_repos:
                    if any(kw in r['full_name'].lower() for kw in ['flipper', 'subghz', 'nfc', 'fap']):
                        repos.add(r['full_name'])
                
                time.sleep(0.5)
            
            time.sleep(1)
        except:
            pass
    
    print(f"  ✅ {len(repos)} via Contributors")
    return repos

# ═══════════════════════════════════════════════════════════
# STRATEGIE 5: TRENDING (Unofficial API)
# ═══════════════════════════════════════════════════════════

def strategy_trending(state: Dict) -> Set[str]:
    """GitHub Trending für C/C++"""
    print("\n📈 TRENDING...")
    repos = set()
    
    try:
        # Unofficial API
        url = "https://github-trending-api.now.sh/repositories?language=c&since=weekly"
        resp = requests.get(url, timeout=10).json()
        
        for repo in resp:
            if any(kw in repo.get('name', '').lower() or kw in repo.get('description', '').lower()
                   for kw in ['flipper', 'subghz', 'nfc', 'rfid']):
                repos.add(repo['author'] + '/' + repo['name'])
                print(f"  🔥 Trending: {repo['author']}/{repo['name']}")
    except:
        pass
    
    print(f"  ✅ {len(repos)} Trending")
    return repos

# ═══════════════════════════════════════════════════════════
# STRATEGIE 6: ORG MEMBERS
# ═══════════════════════════════════════════════════════════

def strategy_org_members(state: Dict) -> Set[str]:
    """Flipper Orgs → Members → Repos"""
    print("\n🏢 ORG MEMBERS...")
    repos = set()
    
    orgs = ["flipperdevices", "DarkFlippers", "Flipper-XFW", "Next-Flip"]
    
    for org in orgs:
        try:
            members = requests.get(
                f"https://api.github.com/orgs/{org}/members?per_page=50",
                headers=get_headers(), timeout=10
            ).json()
            
            for member in members[:20]:
                member_repos = requests.get(
                    f"https://api.github.com/users/{member['login']}/repos?per_page=30",
                    headers=get_headers(), timeout=8
                ).json()
                
                for r in member_repos:
                    if 'flipper' in r['full_name'].lower():
                        repos.add(r['full_name'])
                
                time.sleep(0.4)
            
            time.sleep(1)
        except:
            pass
    
    print(f"  ✅ {len(repos)} via Orgs")
    return repos

# ═══════════════════════════════════════════════════════════
# STRATEGIE 7-10: [Vorherige Methoden bleiben]
# ═══════════════════════════════════════════════════════════

def main():
    state = {"known_repos": set(), "posted_events": set()}
    
    print("=" * 70)
    print("🎯 FLIPPER ZERO MEGA BOT v7.0 - MAXIMUM DISCOVERY")
    print("=" * 70 + "\n")
    
    all_repos = set(PRIORITY_REPOS)
    
    # ALLE STRATEGIEN
    all_repos.update(strategy_watchers_network(state))
    all_repos.update(strategy_stargazers_network(state))
    all_repos.update(strategy_fork_network(state))
    all_repos.update(strategy_contributors_network(state))
    all_repos.update(strategy_trending(state))
    all_repos.update(strategy_org_members(state))
    
    print(f"\n{'='*70}")
    print(f"🎉 TOTAL: {len(all_repos)} REPOS GEFUNDEN!")
    print(f"{'='*70}\n")
    
    state["known_repos"] = all_repos

if __name__ == "__main__":
    main()
