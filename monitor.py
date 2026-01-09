import requests
import os
from datetime import datetime, timedelta
from telegram import Bot

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHANNEL = os.getenv('CHANNEL_ID')
TOPIC_ID = int(os.getenv('TOPIC_ID', 40))
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

headers = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
url = 'https://api.github.com/search/repositories'
query = f'topic:flipperzero created:>{(datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d")}'
params = {'q': query, 'sort': 'created', 'order': 'asc', 'per_page': 10}

resp = requests.get(url, headers=headers, params=params)
repos
