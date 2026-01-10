import requests
import os
import json
from datetime import datetime, timezone, timedelta

# Secrets aus GitHub Actions holen
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["CHANNEL_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)  # Optional für höhere API-Limits

# State-Datei für letzte Checks (Repos, Releases, Commits, PRs, Issues)
STATE_FILE = "/tmp/flipper_state.json"

# Top-Repos für detaillierte Überwachung (Releases, Commits, PRs, Issues)
WATCHED_REPOS = [
    "DarkFlippers/unleashed-firmware",
    "RogueMaster/flipperzero-firmware-wPlugins",
    "Next-Flip/Momentum-Firmware",
    "Flipper-XFW/Xtreme-Firmware",
    "Flipper-Devices/flipperzero-firmware",
    "djsime1/awesome-flipperzero",
    "xMasterX/all-the-plugins",
    "jamisonderek/flipper-zero-tutorials",
    "UberGuidoZ/Flipper",
    "xMasterX/fap-store"  # Erweitert für mehr Abdeckung
]

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "last_repo_check": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
            "releases": {},
            "commits": {},
            "prs": {},
            "issues": {}
        }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def check_new_repos(state):
    since = datetime.fromisoformat(state["last_repo_check"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Breite, optimierte Suche in Teilen (mehr Ergebnisse, kein 422)
    queries = [
        f"flipperzero OR \"flipper zero\" OR fap OR plugin OR firmware OR unleashed OR rogue OR momentum OR xtreme created:>{since}",
        f"subghz OR nfc OR rfid OR badusb OR ibutton OR gpio OR ir OR \"flipper app\" OR \"flipper mod\" OR \"flipper tool\" OR \"flipper hack\" created:>{since}"
    ]
    
    all_items = []
    for q in queries:
        url = f"https://api.github.com/search/repositories?q={q}&sort=created&order=desc&per_page=50"
        print(f"Repo-Suche-Teil: {q}")
        print(f"URL: {url}")
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            all_items.extend(items)
            print(f"Gefundene in Teil: {len(items)}")
        except Exception as e:
            print("Repo-Fehler:", str(e))
    
    # Duplikate entfernen (nach full_name)
    unique_items = {item["full_name"]: item for item in all_items}.values()
    print(f"Gesamte einzigartige Repos: {len(unique_items)}")
    return list(unique_items)

def check_new_releases(state):
    new_releases = []
    releases_state = state.get("releases", {})
    
    for repo in WATCHED_REPOS:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=5"
        try:
            releases = requests.get(url, headers=get_headers(), timeout=10).json()
            if not releases:
                continue
            
            latest = releases[0]
            tag = latest["tag_name"]
            last_tag = releases_state.get(repo)
            
            if last_tag != tag:
                new_releases.append((repo, latest))
                releases_state[repo] = tag
                print(f"Neuer Release in {repo}: {tag}")
        except Exception as e:
            print(f"Release-Fehler {repo}: {e}")
    
    state["releases"] = releases_state
    return new_releases

def check_new_commits(state):
    new_commits = []
    commits_state = state.get("commits", {})
    
    for repo in WATCHED_REPOS:
        since = commits_state.get(repo, (datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        url = f"https://api.github.com/repos/{repo}/commits?since={since}&per_page=10"
        try:
            commits = requests.get(url, headers=get_headers(), timeout=10).json()
            if not commits:
                continue
            
            latest = commits[0]
            sha = latest["sha"]
            last_sha = commits_state.get(repo)
            
            if last_sha != sha:
                new_commits.append((repo, latest))
                commits_state[repo] = sha
                print(f"Neuer Commit in {repo}: {sha[:7]}")
        except Exception as e:
            print(f"Commit-Fehler {repo}: {e}")
    
    state["commits"] = commits_state
    return new_commits

def check_new_prs(state):
    new_prs = []
    pr_state = state.get("prs", {})
    
    for repo in WATCHED_REPOS:
        since = pr_state.get(repo, (datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        url = f"https://api.github.com/repos/{repo}/pulls?state=open&sort=created&direction=desc&per_page=10"
        try:
            prs = requests.get(url, headers=get_headers(), timeout=10).json()
            if not prs:
                continue
            
            latest = prs[0]
            pr_number = latest["number"]
            last_pr = pr_state.get(repo)
            
            if last_pr != pr_number:
                new_prs.append((repo, latest))
                pr_state[repo] = pr_number
                print(f"Neuer PR in {repo}: #{pr_number}")
        except Exception as e:
            print(f"PR-Fehler {repo}: {e}")
    
    state["prs"] = pr_state
    return new_prs

def check_new_issues(state):
    new_issues = []
    issues_state = state.get("issues", {})
    
    for repo in WATCHED_REPOS:
        since = issues_state.get(repo, (datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        url = f"https://api.github.com/repos/{repo}/issues?state=open&sort=created&direction=desc&per_page=10&since={since}"
        try:
            issues = requests.get(url, headers=get_headers(), timeout=10).json()
            if not issues:
                continue
            
            latest = issues[0]
            issue_number = latest["number"]
            last_issue = issues_state.get(repo)
            
            if last_issue != issue_number:
                new_issues.append((repo, latest))
                issues_state[repo] = issue_number
                print(f"Neues Issue in {repo}: #{issue_number}")
        except Exception as e:
            print(f"Issue-Fehler {repo}: {e}")
    
    state["issues"] = issues_state
    return new_issues

def post_findings(items, new_releases, new_commits, new_prs, new_issues):
    sent = 0
    
    # Neue Repos
    for repo in items:
        if sent >= 5:
            break
        message = f"""🆕 <b>Neues Repo: {repo['full_name']}</b>
⭐ {repo['stargazers_count']}
{repo['description'] or 'Keine Beschreibung'}

{repo['html_url']}"""
        send_message(message)
        sent += 1
    
    # Neue Releases
    for repo, release in new_releases:
        if sent >= 5:
            break
        message = f"""🆕 <b>Neuer Release in {repo}</b>
{release['name'] or release['tag_name']}
{release['body'][:150]}...

{release['html_url']}"""
        send_message(message)
        sent += 1
    
    # Neue Commits
    for repo, commit in new_commits:
        if sent >= 5:
            break
        message = f"""🆕 <b>Neuer Commit in {repo}</b>
{commit['commit']['message'][:150]}...

{commit['html_url']}"""
        send_message(message)
        sent += 1
    
    # Neue PRs
    for repo, pr in new_prs:
        if sent >= 5:
            break
        message = f"""🆕 <b>Neuer Pull Request in {repo}</b>
#{pr['number']}: {pr['title']}

{pr['html_url']}"""
        send_message(message)
        sent += 1
    
    # Neue Issues
    for repo, issue in new_issues:
        if sent >= 5:
            break
        message = f"""🆕 <b>Neues Issue in {repo}</b>
#{issue['number']}: {issue['title']}

{issue['html_url']}"""
        send_message(message)
        sent += 1

def send_message(message):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "message_thread_id": 40  # Dein Topic
    }
    try:
        r = requests.post(send_url, json=payload, timeout=10)
        r.raise_for_status()
        print("Gesendet: " + message.splitlines()[0])
    except Exception as e:
        print("Telegram Fehler:", str(e))

def check_flipper_updates():
    state = load_state()
    
    new_repos = check_new_repos(state)
    new_releases = check_new_releases(state)
    new_commits = check_new_commits(state)
    new_prs = check_new_prs(state)
    new_issues = check_new_issues(state)
    
    post_findings(new_repos, new_releases, new_commits, new_prs, new_issues)
    
    state["last_repo_check"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print("Check beendet")

if __name__ == "__main__":
    check_flipper_updates()
