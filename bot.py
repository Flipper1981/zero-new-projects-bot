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

STATE_FILE = "/tmp/flipper_maximum_state.json"

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def check_rate_limit():
    """Detaillierter Rate Limit Check"""
    try:
        resp = requests.get("https://api.github.com/rate_limit", headers=get_headers(), timeout=5)
        data = resp.json()
        
        core = data['resources']['core']
        search = data['resources']['search']
        
        print(f"\n📊 RATE LIMIT STATUS:")
        print(f"   Core API: {core['remaining']}/{core['limit']}")
        print(f"   Search API: {search['remaining']}/{search['limit']}")
        
        reset_time = datetime.fromtimestamp(core['reset'])
        wait_seconds = (reset_time - datetime.now()).total_seconds()
        print(f"   Reset in: {int(wait_seconds/60)}min {int(wait_seconds%60)}s\n")
        
        return core['remaining'] > 10
    except:
        return True

# ═══════════════════════════════════════════════════════════
# MASSIVE QUERY GENERATOR - JEDER PARAMETER!
# ═══════════════════════════════════════════════════════════

def generate_massive_queries() -> List[str]:
    """
    ALLE GitHub Search Qualifiers - KOMPLETT!
    Generiert 500+ verschiedene Queries
    """
    all_queries = []
    
    print("\n🔧 GENERIERE ALLE QUERIES...")
    print("=" * 70)
    
    # ────────────────────────────────────────────────────────
    # 1. KEYWORDS (ALLE Variationen!)
    # ────────────────────────────────────────────────────────
    print("  1. Keywords...")
    keywords = [
        'flipper', 'flipperzero', 'flipper-zero', 'flipper_zero',
        'FlipperZero', 'FLIPPERZERO', 'Flipper-Zero',
        'subghz', 'sub-ghz', 'subGHz', 'SubGHz', 'sub_ghz',
        'nfc', 'NFC', 'Nfc',
        'rfid', 'RFID', 'Rfid',
        'badusb', 'bad-usb', 'BadUSB', 'bad_usb',
        'infrared', 'IR', 'ir', 'Infrared',
        'ibutton', 'iButton', 'i-button',
        'protpirate', 'prot-pirate', 'ProtoPirate', 'ProtoPiratein',
        'unleashed', 'Unleashed', 'unleashed-firmware',
        'roguemaster', 'RogueMaster', 'rogue-master',
        'momentum', 'Momentum', 'momentum-firmware',
        'xtreme', 'Xtreme', 'xtreme-firmware',
        'fap', 'FAP', 'Fap', '.fap',
        'flipper-app', 'flipper-application', 'flipper-plugin'
    ]
    
    # Basis Keyword Queries
    for kw in keywords:
        all_queries.append(f"{kw} archived:false")
    
    print(f"     → {len(keywords)} keyword queries")
    
    # ────────────────────────────────────────────────────────
    # 2. LANGUAGE (JEDE Sprache!)
    # ────────────────────────────────────────────────────────
    print("  2. Languages...")
    languages = [
        'C', 'Python', 'C++', 'Makefile', 'Shell', 'JavaScript',
        'Rust', 'Go', 'Assembly', 'CMake', 'Java', 'TypeScript',
        'Lua', 'Ruby', 'Perl', 'PHP', 'Swift', 'Kotlin'
    ]
    
    for kw in ['flipper', 'flipperzero', 'subghz', 'nfc', 'badusb']:
        for lang in languages:
            all_queries.append(f"{kw} language:{lang} archived:false")
    
    print(f"     → {5 * len(languages)} language queries")
    
    # ────────────────────────────────────────────────────────
    # 3. TOPICS (ALLE Topics!)
    # ────────────────────────────────────────────────────────
    print("  3. Topics...")
    topics = [
        'flipperzero', 'flipper-zero', 'flipper',
        'flipper-plugin', 'flipper-app', 'flipper-firmware',
        'flipper-application', 'flipper-tool', 'flipper-script',
        'fap', 'fap-file', 'fap-application',
        'subghz', 'sub-ghz', 'subghz-decoder', 'subghz-bruteforce',
        'subghz-analyzer', 'subghz-scanner', 'subghz-jammer',
        'nfc', 'nfc-reader', 'nfc-tools', 'nfc-card', 'nfc-emulator',
        'rfid', 'rfid-reader', 'rfid-cloner', 'rfid-tools',
        'badusb', 'bad-usb', 'rubber-ducky', 'ducky-script',
        'infrared', 'ir-remote', 'universal-remote', 'ir-blaster',
        'ibutton', 'dallas-key', 'one-wire',
        'gpio', 'uart', 'i2c', 'spi', 'serial',
        'firmware', 'custom-firmware', 'ota-update', 'bootloader',
        'pentest', 'pentesting', 'security', 'hacking', 'redteam',
        'iot', 'embedded', 'hardware', 'electronics'
    ]
    
    for topic in topics:
        all_queries.append(f"topic:{topic} archived:false")
    
    print(f"     → {len(topics)} topic queries")
    
    # ────────────────────────────────────────────────────────
    # 4. IN (name, description, readme) - JEDE Kombination!
    # ────────────────────────────────────────────────────────
    print("  4. Search Fields (in:)...")
    search_fields = ['name', 'description', 'readme']
    
    for kw in keywords[:20]:  # Top 20 Keywords
        for field in search_fields:
            all_queries.append(f"{kw} in:{field} archived:false")
    
    print(f"     → {20 * 3} in: queries")
    
    # ────────────────────────────────────────────────────────
    # 5. STARS (ALLE Ranges!)
    # ────────────────────────────────────────────────────────
    print("  5. Star Ranges...")
    star_ranges = [
        '>0', '>1', '>2', '>5', '>10', '>20', '>50', '>100', 
        '>200', '>500', '>1000',
        '1..5', '5..10', '10..20', '20..50', '50..100', '100..500',
        '500..1000', '>1000'
    ]
    
    for stars in star_ranges:
        all_queries.append(f"flipper stars:{stars} archived:false")
        all_queries.append(f"flipperzero stars:{stars} archived:false")
    
    print(f"     → {len(star_ranges) * 2} star queries")
    
    # ────────────────────────────────────────────────────────
    # 6. FORKS (ALLE Ranges!)
    # ────────────────────────────────────────────────────────
    print("  6. Fork Ranges...")
    fork_ranges = ['>0', '>1', '>2', '>5', '>10', '>20', '>50', '1..10', '10..50']
    
    for forks in fork_ranges:
        all_queries.append(f"flipperzero forks:{forks} archived:false")
    
    print(f"     → {len(fork_ranges)} fork queries")
    
    # ────────────────────────────────────────────────────────
    # 7. SIZE (ALLE Ranges!)
    # ────────────────────────────────────────────────────────
    print("  7. Size Ranges...")
    size_ranges = [
        '<10', '<50', '<100', '<500', '<1000',
        '10..100', '100..500', '500..1000', '1000..5000', '5000..10000',
        '>1000', '>5000', '>10000'
    ]
    
    for size in size_ranges:
        all_queries.append(f"flipper size:{size} archived:false")
    
    print(f"     → {len(size_ranges)} size queries")
    
    # ────────────────────────────────────────────────────────
    # 8. DATES (VIELE verschiedene Zeiträume!)
    # ────────────────────────────────────────────────────────
    print("  8. Date Ranges...")
    
    now = datetime.now(timezone.utc)
    date_configs = [
        (1, 'days'), (3, 'days'), (7, 'days'), (14, 'days'), (30, 'days'),
        (60, 'days'), (90, 'days'), (180, 'days'), (365, 'days')
    ]
    
    for amount, unit in date_configs:
        date_str = (now - timedelta(days=amount)).strftime('%Y-%m-%d')
        all_queries.append(f"flipper created:>{date_str} archived:false")
        all_queries.append(f"flipper pushed:>{date_str} archived:false")
        all_queries.append(f"flipperzero created:>{date_str} archived:false")
        all_queries.append(f"flipperzero pushed:>{date_str} archived:false")
    
    print(f"     → {len(date_configs) * 4} date queries")
    
    # ────────────────────────────────────────────────────────
    # 9. LICENSE (ALLE Lizenzen!)
    # ────────────────────────────────────────────────────────
    print("  9. Licenses...")
    licenses = [
        'mit', 'gpl', 'gpl-2.0', 'gpl-3.0', 'apache-2.0', 
        'bsd', 'bsd-3-clause', 'unlicense', 'lgpl', 'mpl-2.0',
        'cc0-1.0', 'wtfpl'
    ]
    
    for lic in licenses:
        all_queries.append(f"flipper license:{lic} archived:false")
    
    print(f"     → {len(licenses)} license queries")
    
    # ────────────────────────────────────────────────────────
    # 10. USER/ORG (ALLE bekannten Developer!)
    # ────────────────────────────────────────────────────────
    print("  10. Users/Organizations...")
    users_orgs = [
        'flipperdevices', 'DarkFlippers', 'RogueMaster', 
        'Next-Flip', 'Flipper-XFW', 'xMasterX',
        'RocketGod-git', 'UberGuidoZ', 'djsime1',
        'jblanked', 'Willy-JL', 'ClaraCrazy',
        'Lanjelin', 'eried', 'wetox-team',
        'Lonebear69', 'Z3BRO', 'hak5',
        'flipper-rs', 'instantiator', 'ebantula',
        'skotopes', 'hedger', 'flipperdevices-team'
    ]
    
    for user in users_orgs:
        all_queries.append(f"user:{user} archived:false")
        all_queries.append(f"org:{user} archived:false")
    
    print(f"     → {len(users_orgs) * 2} user/org queries")
    
    # ────────────────────────────────────────────────────────
    # 11. EXTENSION/FILENAME (ALLE Dateitypen!)
    # ────────────────────────────────────────────────────────
    print("  11. Extensions/Filenames...")
    extensions = [
        'fap', 'fam', 'sub', 'nfc', 'ir', 'ibtn', 
        'c', 'h', 'py', 'js', 'sh', 'txt',
        'md', 'yml', 'yaml', 'json', 'toml'
    ]
    
    for ext in extensions:
        all_queries.append(f"flipper extension:{ext} archived:false")
    
    filenames = [
        'application.fam', 'manifest.yml', 'fap_manifest.yml',
        'README.md', 'Makefile', 'CMakeLists.txt',
        '.gitmodules', 'requirements.txt'
    ]
    
    for fname in filenames:
        all_queries.append(f"flipper filename:{fname} archived:false")
    
    print(f"     → {len(extensions) + len(filenames)} extension/filename queries")
    
    # ────────────────────────────────────────────────────────
    # 12. PATH (ALLE wichtigen Pfade!)
    # ────────────────────────────────────────────────────────
    print("  12. Paths...")
    paths = [
        'applications', 'apps', 'plugins', 'firmware', 
        'lib', 'assets', 'src', 'include', 'docs',
        'scripts', 'tools', 'targets', 'fbt'
    ]
    
    for path in paths:
        all_queries.append(f"flipper path:{path} archived:false")
    
    print(f"     → {len(paths)} path queries")
    
    # ────────────────────────────────────────────────────────
    # 13. SPECIAL Qualifiers
    # ────────────────────────────────────────────────────────
    print("  13. Special Qualifiers...")
    
    all_queries.append(f"flipper is:public archived:false")
    all_queries.append(f"flipperzero NOT is:fork archived:false")
    all_queries.append(f"flipper mirror:false archived:false")
    all_queries.append(f"flipper template:false archived:false")
    all_queries.append(f"flipper followers:>5 archived:false")
    all_queries.append(f"flipper followers:>10 archived:false")
    all_queries.append(f"flipper good-first-issues:>0 archived:false")
    all_queries.append(f"flipper help-wanted-issues:>0 archived:false")
    
    print(f"     → 8 special queries")
    
    # ────────────────────────────────────────────────────────
    # 14. MEGA KOMBINATIONEN (AND/OR)
    # ────────────────────────────────────────────────────────
    print("  14. Complex AND/OR Queries...")
    
    complex_queries = [
        "(flipper OR flipperzero OR subghz OR nfc OR badusb OR rfid) AND archived:false",
        "(flipper OR flipperzero) AND (language:C OR language:Python OR language:Rust) AND archived:false",
        "(topic:flipperzero OR topic:flipper-plugin) AND stars:>5 AND archived:false",
        "flipper AND (extension:fap OR extension:sub OR extension:nfc OR extension:ir) AND archived:false",
        "(user:DarkFlippers OR user:RogueMaster OR user:Flipper-XFW) AND archived:false",
        "flipper AND (in:name OR in:description) AND stars:>10 AND archived:false",
        "(subghz OR nfc OR rfid OR badusb) AND language:C AND forks:>2 AND archived:false",
        "flipper AND license:mit AND stars:>20 AND archived:false",
        "(topic:firmware OR topic:plugin) AND flipper AND pushed:>2025-01-01 AND archived:false",
        "flipper AND size:>1000 AND forks:>5 AND stars:>10 AND archived:false"
    ]
    
    all_queries.extend(complex_queries)
    print(f"     → {len(complex_queries)} complex queries")
    
    print("=" * 70)
    print(f"✅ TOTAL: {len(all_queries)} QUERIES GENERIERT!\n")
    
    return all_queries

# ═══════════════════════════════════════════════════════════
# EXECUTE ALL QUERIES (mit Fortschritt!)
# ═══════════════════════════════════════════════════════════

def execute_all_queries(queries: List[str], state: Dict) -> Set[str]:
    """
    Führt WIRKLICH ALLE Queries aus!
    Zeigt Fortschritt an
    """
    print("\n🔍 STARTE VOLLSTÄNDIGE SUCHE...")
    print("=" * 70)
    
    all_repos = set()
    total_queries = len(queries)
    executed = 0
    skipped = 0
    
    start_time = time.time()
    
    for i, query in enumerate(queries, 1):
        # Rate Limit Check alle 20 Queries
        if i % 20 == 0:
            if not check_rate_limit():
                print(f"\n⚠️ Rate Limit zu niedrig! Pausiere 60s...")
                time.sleep(60)
                if not check_rate_limit():
                    print(f"⚠️ Stoppe nach {executed} von {total_queries} Queries")
                    break
        
        url = f"https://api.github.com/search/repositories?q={query}&per_page=100&sort=updated"
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=20)
            
            if resp.status_code == 403:
                print(f"\n[{i}/{total_queries}] ⚠️ 403 - Rate Limit exceeded!")
                skipped += 1
                time.sleep(10)
                continue
            
            if resp.status_code == 422:
                print(f"[{i}/{total_queries}] ⚠️ 422 - Invalid query: {query[:50]}")
                skipped += 1
                continue
            
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                total_count = data.get('total_count', 0)
                new_repos = 0
                
                for item in items:
                    repo_name = item['full_name']
                    if repo_name not in all_repos:
                        all_repos.add(repo_name)
                        new_repos += 1
                
                # Zeige nur Queries mit neuen Ergebnissen
                if new_repos > 0:
                    print(f"[{i}/{total_queries}] ✅ +{new_repos} neue (total: {total_count}): {query[:55]}...")
                elif i % 50 == 0:
                    print(f"[{i}/{total_queries}] ⏭️  Progress: {len(all_repos)} repos total")
                
                executed += 1
            
            # Rate Limit Safety
            time.sleep(2)
        
        except KeyboardInterrupt:
            print(f"\n\n⚠️ ABGEBROCHEN nach {executed} Queries")
            break
        except Exception as e:
            print(f"[{i}/{total_queries}] ❌ Error: {e}")
            skipped += 1
            continue
    
    elapsed = time.time() - start_time
    
    print("=" * 70)
    print(f"✅ SUCHE ABGESCHLOSSEN!")
    print(f"   Ausgeführt: {executed}/{total_queries} queries")
    print(f"   Übersprungen: {skipped}")
    print(f"   Gefundene Repos: {len(all_repos)}")
    print(f"   Zeit: {int(elapsed/60)}min {int(elapsed%60)}s")
    print("=" * 70)
    
    return all_repos

# ═══════════════════════════════════════════════════════════
# RSS C
