import requests
import os
from datetime import datetime, timezone, timedelta

# Get secrets from GitHub Actions environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL_ID")     # ← change to "TELEGRAM_CHANNEL" if you rename the secret

# File used to store last check time (temporary in Actions)
LAST_CHECK_FILE = "/tmp/last_check_time.txt"

def get_last_check_time():
    """Read the last successful check time from file or use default (1 week ago)"""
    try:
        with open(LAST_CHECK_FILE, "r") as f:
            return datetime.fromisoformat(f.read().strip())
    except (FileNotFoundError, ValueError):
        return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_check_time():
    """Save current time as last check time"""
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


def fetch_new_flipper_projects():
    """Check GitHub for new repositories with flipperzero topic"""
    last_check = get_last_check_time()
    since_str = last_check.strftime("%Y-%m-%dT%H:%M:%SZ")

    query = f"topic:flipperzero created:>{since_str}"
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "created",
        "order": "desc",
        "per_page": 10
    }

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Flipper-Zero-News-Bot"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"GitHub API request failed: {e}")
        return

    items = data.get("items", [])
    if not items:
        print("No new projects found")
        save_last_check_time()
        return

    sent_count = 0
    for repo in items:
        if sent_count >= 3:  # limit to max 3 posts per run
            break

        created_at = repo["created_at"][:10]  # YYYY-MM-DD
        name = repo["full_name"]
        url = repo["html_url"]
        description = (repo["description"] or "No description provided").strip()
        if len(description) > 140:
            description = description[:137] + "..."
        stars = repo["stargazers_count"]

        message = (
            f"🆕 <b>New Flipper Zero Project!</b>\n"
            f"<b>{name}</b>\n"
            f"⭐ {stars} • {created_at}\n"
            f"{description}\n\n"
            f"{url}"
        )

        # Send message to Telegram channel
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            r = requests.post(telegram_url, json=payload, timeout=10)
            r.raise_for_status()
            print(f"Successfully sent: {name}")
            sent_count += 1
        except requests.RequestException as e:
            print(f"Failed to send message for {name}: {e
