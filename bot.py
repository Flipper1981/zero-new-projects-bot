#!/usr/bin/env python3
import requests
import os
import json
import time
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set
from collections import defaultdict

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
STATE_FILE = "/tmp/flipper_mega_state.json"

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

# ═══════════════════════════════════════════════════════════
# 1. 1000-RESULT-LIMIT WORKAROUND (Date + Size Slicing)
# ═══════════════════════════════════════════════════════════

def break_1000_limit_search(base_query: str) -> Set[str]:
    """
    UMGEHT das 1000-Result-Limit durch:
    - Date Slicing (monatlich, wöchentlich, täglich)
    - Size Slicing (KB-Ranges)
    - Kombinationen
    
    Findet ALLE Repos statt nur 1000!
    """
    print(f"\n🔓 BREAKING 1000-LIMIT: {base_query[:50]}...")
    all_repos = set()
    
    # ────────────────────────────────────────────────────────
    # METHOD 1: DATE SLICING (nach Monat/Woche/Tag)
    # ────────────────────────────────────────────────────────
    
    now = datetime.now(timezone.utc)
    start_year = 2020  # Flipper Zero Launch
    
    # MONTHLY SLICES
    for year in range(start_year, now.year + 1):
        for month in range(1, 13):
            if year == now.year and month > now.month:
                break
            
            month_start = f"{year}-{month:02d}-01"
            if month == 12:
                month_end = f"{year + 1}-01-01"
            else:
                month_end = f"{year}-{month + 1:02d}-01"
            
            query = f"{base_query} created:{month_start}..{month_end}"
            repos = execute_single_search(query)
            
            # Wenn > 900 Results → WEEKLY SLICE!
            if len(repos) > 900:
                print(f"    ⚠️ {month_start}: {len(repos)} results → WEEKLY SLICE")
                repos = weekly_slice(base_query, year, month)
            
            all_repos.update(repos)
            print(f"    📅 {month_start}: +{len(repos)} repos (total: {len(all_repos)})")
            time.sleep(1)
    
    # ────────────────────────────────────────────────────────
    # METHOD 2: SIZE SLICING (paralleles Suchen)
    # ────────────────────────────────────────────────────────
    
    size_ranges = [
        '<10', '10..50', '50..100', '100..200', '200..500',
        '500..1000', '1000..2000', '2000..5000', '5000..10000',
        '10000..20000', '20000..50000', '>50000'
    ]
    
    for size_range in size_ranges:
        query = f"{base_query} size:{size_range}"
        repos = execute_single_search(query)
        new_count = len(repos - all_repos)
        
        if new_count > 0:
            all_repos.update(repos)
            print(f"    📦 size:{size_range}: +{new_count} new repos")
        
        time.sleep(1)
    
    print(f"  ✅ TOTAL: {len(all_repos)} repos (broke 1000 limit!)\n")
    return all_repos

def weekly_slice(base_query: str, year: int, month: int) -> Set[str]:
    """Wöchentliche Slices für dichte Monate"""
    repos = set()
    
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    
    for day_start in range(1, days_in_month, 7):
        day_end = min(day_start + 6, days_in_month)
        
        date_start = f"{year}-{month:02d}-{day_start:02d}"
        date_end = f"{year}-{month:02d}-{day_end:02d}"
        
        query = f"{base_query} created:{date_start}..{date_end}"
        week_repos = execute_single_search(query)
        repos.update(week_repos)
        
        time.sleep(0.5)
    
    return repos

def execute_single_search(query: str, max_pages: int = 10) -> Set[str]:
    """Einzelne Search mit Pagination"""
    repos = set()
    
    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/search/repositories?q={query}&per_page=100&page={page}"
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            
            if resp.status_code != 200:
                break
            
            data = resp.json()
            items = data.get('items', [])
            
            if not items:
                break
            
            for item in items:
                repos.add(item['full_name'])
            
            # Wenn < 100, das war die letzte Seite
            if len(items) < 100:
                break
        
        except:
            break
        
        time.sleep(0.3)
    
    return repos

# ═══════════════════════════════════════════════════════════
# 2. ULTRA TOPIC COMBINATIONS (Machine Learning-ähnlich)
# ═══════════════════════════════════════════════════════════

def discover_topic_combinations(state: Dict) -> List[str]:
    """
    Intelligente Topic-Kombinationen basierend auf:
    - Co-Occurrence (welche Topics oft zusammen vorkommen)
    - Semantic Similarity
    - Frequency Analysis
    """
    print("\n🧠 INTELLIGENT TOPIC DISCOVERY...")
    
    all_queries = []
    
    # ────────────────────────────────────────────────────────
    # BASE TOPICS (kategorisiert)
    # ────────────────────────────────────────────────────────
    
    topic_categories = {
        'device': [
            'flipperzero', 'flipper-zero', 'flipper', 'flipper0',
            'flipper-device', 'flipper-one'
        ],
        'wireless': [
            'subghz', 'sub-ghz', '433mhz', '315mhz', '868mhz', '915mhz',
            'rf', 'radio', 'wireless', 'remote', 'transmitter', 'receiver',
            'ask', 'fsk', 'ook', 'gfsk', 'rolling-code', 'static-code'
        ],
        'nfc': [
            'nfc', 'nfc-a', 'nfc-b', 'nfc-v', 'nfc-f',
            'mifare', 'ntag', 'ultralight', 'desfire', 'felica',
            'iso14443', 'iso15693', 'nfc-card', 'nfc-tag', 'emv'
        ],
        'rfid': [
            'rfid', 'lf-rfid', 'hf-rfid', 'em4100', 'em4102', 'em4305',
            'hid', 'indala', 't5577', 'fdx-b', '125khz', '13.56mhz'
        ],
        'infrared': [
            'infrared', 'ir', 'ir-remote', 'ir-blaster', 'lirc',
            'tv-remote', 'ac-remote', 'universal-remote', 'pronto'
        ],
        'ibutton': [
            'ibutton', 'dallas-key', 'one-wire', '1-wire',
            'ds1990', 'ds1992', 'ds1993', 'maxim'
        ],
        'badusb': [
            'badusb', 'bad-usb', 'rubber-ducky', 'ducky-script',
            'hid-attack', 'usb-attack', 'payload', 'keystroke',
            'digispark', 'teensy', 'bash-bunny'
        ],
        'app': [
            'fap', 'flipper-app', 'flipper-application', 'flipper-plugin',
            'flipper-tool', 'flipper-game', 'flipper-utility',
            'fap-file', 'application-fam'
        ],
        'firmware': [
            'firmware', 'custom-firmware', 'unleashed', 'roguemaster',
            'momentum', 'xtreme', 'firmware-mod', 'ota', 'bootloader'
        ],
        'hardware': [
            'gpio', 'uart', 'i2c', 'spi', 'usb', 'bluetooth', 'ble',
            'wifi', 'esp32', 'cc1101', 'nrf24', 'lora'
        ],
        'security': [
            'pentest', 'pentesting', 'redteam', 'security', 'hacking',
            'exploit', 'vulnerability', 'infosec', 'cybersecurity'
        ],
        'dev': [
            'sdk', 'api', 'library', 'framework', 'toolchain',
            'debugging', 'ufbt', 'fbt', 'vscode', 'ide'
        ]
    }
    
    # ────────────────────────────────────────────────────────
    # 2-TOPIC COMBINATIONS (alle Kategorien)
    # ────────────────────────────────────────────────────────
    
    categories = list(topic_categories.keys())
    
    # Device + Everything
    for device in topic_categories['device'][:3]:
        for category, topics in topic_categories.items():
            if category == 'device':
                continue
            for topic in topics[:5]:
                all_queries.append(f"topic:{device} topic:{topic} archived:false")
    
    # Cross-Category (logische Paare)
    logical_pairs = [
        ('wireless', 'security'),
        ('nfc', 'security'),
        ('badusb', 'security'),
        ('app', 'wireless'),
        ('app', 'nfc'),
        ('firmware', 'wireless'),
        ('firmware', 'hardware'),
        ('dev', 'app'),
        ('infrared', 'hardware')
    ]
    
    for cat1, cat2 in logical_pairs:
        for topic1 in topic_categories[cat1][:3]:
            for topic2 in topic_categories[cat2][:3]:
                all_queries.append(f"topic:{topic1} topic:{topic2} archived:false")
    
    # ────────────────────────────────────────────────────────
    # 3-TOPIC COMBINATIONS (hochspezifisch)
    # ────────────────────────────────────────────────────────
    
    triple_combinations = [
        ('device', 'app', 'wireless'),
        ('device', 'firmware', 'wireless'),
        ('device', 'app', 'nfc'),
        ('device', 'badusb', 'security'),
        ('device', 'infrared', 'hardware'),
        ('app', 'wireless', 'security'),
        ('firmware', 'hardware', 'dev')
    ]
    
    for cat1, cat2, cat3 in triple_combinations:
        topic1 = topic_categories[cat1][0]  # Main topic
        for topic2 in topic_categories[cat2][:2]:
            for topic3 in topic_categories[cat3][:2]:
                query = f"topic:{topic1} topic:{topic2} topic:{topic3} archived:false"
                all_queries.append(query)
    
    # ────────────────────────────────────────────────────────
    # ADVANCED: Topic + Qualifiers
    # ────────────────────────────────────────────────────────
    
    qualifiers = {
        'language': ['C', 'Python', 'Rust', 'C++', 'JavaScript'],
        'stars': ['>5', '>10', '>20', '>50', '>100', '>200'],
        'forks': ['>1', '>5', '>10', '>20'],
        'size': ['<100', '100..1000', '1000..5000', '>5000']
    }
    
    main_topics = topic_categories['device'][:2]
    
    for main_topic in main_topics:
        # Topic + Language
        for lang in qualifiers['language']:
            all_queries.append(f"topic:{main_topic} language:{lang} archived:false")
        
        # Topic + Stars
        for stars in qualifiers['stars']:
            all_queries.append(f"topic:{main_topic} stars:{stars} archived:false")
        
        # Topic + Language + Stars (Triple!)
        for lang in qualifiers['language'][:3]:
            for stars in qualifiers['stars'][:3]:
                query = f"topic:{main_topic} language:{lang} stars:{stars} archived:false"
                all_queries.append(query)
    
    # ────────────────────────────────────────────────────────
    # NESTED AND/OR MEGA QUERIES
    # ────────────────────────────────────────────────────────
    
    mega_queries = [
        # Alle Wireless OR NFC mit Device
        f"topic:flipperzero AND (topic:subghz OR topic:nfc OR topic:rfid OR topic:infrared) AND archived:false",
        
        # Apps mit verschiedenen Kategorien
        f"(topic:flipper-app OR topic:fap) AND (topic:subghz OR topic:nfc OR topic:badusb) AND archived:false",
        
        # Firmware Variants
        f"(topic:unleashed OR topic:roguemaster OR topic:momentum OR topic:xtreme) AND archived:false",
        
        # Security Tools
        f"topic:flipperzero AND (topic:pentest OR topic:security OR topic:hacking) AND stars:>10 AND archived:false",
        
        # Development Tools
        f"(topic:sdk OR topic:api OR topic:library) AND (topic:flipperzero OR topic:flipper) AND archived:false",
        
        # Hardware Projects
        f"topic:flipper AND (topic:gpio OR topic:uart OR topic:i2c OR topic:esp32) AND archived:false",
        
        # Popular Multi-Topic
        f"(topic:flipperzero OR topic:subghz OR topic:nfc) AND stars:>20 AND forks:>5 AND archived:false",
        
        # Recent Active
        f"topic:flipperzero AND pushed:>2026-01-01 AND (stars:>10 OR forks:>3) AND archived:false",
        
        # Code Quality
        f"topic:flipper AND (language:C OR language:Rust) AND stars:>50 AND archived:false",
        
        # All File Types
        f"flipper AND (extension:fap OR extension:sub OR extension:nfc OR extension:ir) AND archived:false"
    ]
    
    all_queries.extend(mega_queries)
    
    print(f"  ✅ Generated {len(all_queries)} intelligent topic queries!")
    return all_queries

# ═══════════════════════════════════════════════════════════
# 3. GRAPHQL MEGA BATCH (50 Repos/Query)
# ═══════════════════════════════════════════════════════════

def graphql_mega_batch(repos: List[str], state: Dict) -> List[Dict]:
    """
    GraphQL Batch = 50 Repos in 1 Request!
    Holt: Releases, Topics, Stats, Tags
    """
    print(f"\n🔥 GRAPHQL MEGA BATCH ({len(repos)} repos)...")
    
    all_data = []
    
    for batch_start in range(0, len(repos), 50):
        batch = repos[batch_start:batch_start + 50]
        
        # Build Dynamic GraphQL Query
        queries = []
        for i, repo in enumerate(batch):
            try:
                owner, name = repo.split('/')
                queries.append(f"""
                r{i}: repository(owner: "{owner}", name: "{name}") {{
                    nameWithOwner
                    stargazerCount
                    forkCount
                    pushedAt
                    createdAt
                    
                    repositoryTopics(first: 20) {{
                        nodes {{
                            topic {{ name }}
                        }}
                    }}
                    
                    releases(first: 5, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
                        nodes {{
                            tagName
                            name
                            publishedAt
                            url
                            isPrerelease
                        }}
                    }}
                    
                    refs(refPrefix: "refs/tags/", first: 10, orderBy: {{field: TAG_COMMIT_DATE, direction: DESC}}) {{
                        nodes {{
                            name
                            target {{
                                ... on Commit {{
                                    committedDate
                                }}
                            }}
                        }}
                    }}
                    
                    defaultBranchRef {{
                        target {{
                            ... on Commit {{
                                history(first: 5) {{
                                    nodes {{
                                        message
                                        committedDate
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
                """)
            except:
                continue
        
        if not queries:
            continue
        
        full_query = "query { " + "\n".join(queries) + " }"
        
        try:
            resp = requests.post(
                "https://api.github.com/graphql",
                json={"query": full_query},
                headers={**get_headers(), "Accept": "application/vnd.github.v4+json"},
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                
                for key, value in data.items():
                    if value and value.get('nameWithOwner'):
                        all_data.append(value)
                
                print(f"  ✅ Batch {batch_start//50 + 1}: {len(batch)} repos")
            
            time.sleep(2)
        
        except Exception as e:
            print(f"  ❌ Batch error: {e}")
    
    print(f"  → {len(all_data)} repos with full data!")
    return all_data

# ═══════════════════════════════════════════════════════════
# 4. TOPIC CO-OCCURRENCE ANALYSIS
# ═══════════════════════════════════════════════════════════

def analyze_topic_patterns(graphql_data: List[Dict]) -> Dict:
    """
    Machine Learning-ähnliche Topic-Analyse:
    - Welche Topics kommen oft zusammen vor?
    - Welche Kombinationen sind am beliebtesten (Stars)?
    """
    print("\n🧠 TOPIC PATTERN ANALYSIS...")
    
    topic_pairs = defaultdict(lambda: {'count': 0, 'total_stars': 0, 'repos': []})
    topic_triples = defaultdict(lambda: {'count': 0, 'total_stars': 0})
    single_topics = defaultdict(lambda: {'count': 0, 'total_stars': 0})
    
    for repo_data in graphql_data:
        repo_name = repo_data.get('nameWithOwner')
        stars = repo_data.get('stargazerCount', 0)
        
        topics = []
        for topic_node in repo_data.get('repositoryTopics', {}).get('nodes', []):
            topic_name = topic_node.get('topic', {}).get('name')
            if topic_name:
                topics.append(topic_name)
                
                # Single topic stats
                single_topics[topic_name]['count'] += 1
                single_topics[topic_name]['total_stars'] += stars
        
        # Pairs
        for i, topic1 in enumerate(topics):
            for topic2 in topics[i+1:]:
                pair = tuple(sorted([topic1, topic2]))
                topic_pairs[pair]['count'] += 1
                topic_pairs[pair]['total_stars'] += stars
                topic_pairs[pair]['repos'].append(repo_name)
        
        # Triples
        for i, topic1 in enumerate(topics):
            for j, topic2 in enumerate(topics[i+1:], i+1):
                for topic3 in topics[j+1:]:
                    triple = tuple(sorted([topic1, topic2, topic3]))
                    topic_triples[triple]['count'] += 1
                    topic_triples[triple]['total_stars'] += stars
    
    # Top Patterns
    top_pairs = sorted(topic_pairs.items(), key=lambda x: x[1]['count'], reverse=True)[:20]
    top_triples = sorted(topic_triples.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
    
    print("\n  🔥 TOP 20 TOPIC PAIRS:")
    for (t1, t2), stats in top_pairs:
        avg_stars = stats['total_stars'] / stats['count']
        print(f"     {t1} + {t2}: {stats['count']} repos, avg {int(avg_stars)} ⭐")
    
    print("\n  🔥 TOP 10 TOPIC TRIPLES:")
    for (t1, t2, t3), stats in top_triples:
        avg_stars = stats['total_stars'] / stats['count']
        print(f"     {t1} + {t2} + {t3}: {stats['count']} repos, avg {int(avg_stars)} ⭐")
    
    return {
        'pairs': topic_pairs,
        'triples': topic_triples,
        'singles': single_topics
    }

# ═══════════════════════════════════════════════════════════
# MAIN MEGA SEARCH
# ═══════════════════════════════════════════════════════════

def main():
    state = {'known_repos': set(), 'posted_events': set()}
    
    print("=" * 70)
    print("🚀 FLIPPER ZERO MEGA SEARCH v14.0 - ABSOLUTE MAXIMUM")
    print("=" * 70)
    
    # PHASE 1: Intelligent Topic Queries
    print("\n📍 PHASE 1: INTELLIGENT TOPIC DISCOVERY...")
    topic_queries = discover_topic_combinations(state)
    
    all_repos = set()
    
    # Execute first 50 queries with 1000-limit breaking
    for i, query in enumerate(topic_queries[:50], 1):
        print(f"\n[{i}/50] Query: {query[:60]}...")
        repos = break_1000_limit_search(query)
        all_repos.update(repos)
        
        if i % 5 == 0:
            print(f"\n  📊 Progress: {len(all_repos)} total repos found")
            time.sleep(5)
    
    # PHASE 2: GraphQL Mega Batch
    print(f"\n📍 PHASE 2: GRAPHQL MEGA BATCH...")
    graphql_data = graphql_mega_batch(list(all_repos)[:500], state)
    
    # PHASE 3: Topic Pattern Analysis
    print(f"\n📍 PHASE 3: TOPIC PATTERN ANALYSIS...")
    patterns = analyze_topic_patterns(graphql_data)
    
    # PHASE 4: Generate new queries based on patterns
    print(f"\n📍 PHASE 4: PATTERN-BASED DISCOVERY...")
    
    new_queries = []
    for (t1, t2), stats in list(patterns['pairs'].items())[:30]:
        if stats['count'] >= 3:  # Mindestens 3x gesehen
            new_queries.append(f"topic:{t1} topic:{t2} archived:false")
    
    # Execute pattern-based queries
    for query in new_queries[:20]:
        repos = break_1000_limit_search(query)
        all_repos.update(repos)
    
    state['known_repos'] = all_repos
    
    print(f"\n{'='*70}")
    print(f"✅ MEGA SEARCH COMPLETE!")
    print(f"   Total Repos: {len(all_repos)}")
    print(f"   Queries Executed: {len(topic_queries[:50]) + len(new_queries[:20])}")
    print(f"   Unique Topics Found: {len(patterns['singles'])}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
