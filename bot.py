#!/usr/bin/env python3
"""
FLIPPER ZERO BOT v15.2 FINAL
Channel: -1002829439594
Topic: 186
"""

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
TOPIC_ID = os.environ.get("TOPIC_ID", "")
STATE_FILE = "flipper_v15_state.json"

RELEASE_AGE_DAYS = int(os.environ.get("RELEASE_AGE_DAYS", "90"))

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def check_rate_limit():
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
            print(f"   ✅ TOKEN AKTIV!")
        elif core['limit'] == 60:
            print(f"   ⚠️ KEIN TOKEN - nur 60/h")
        
        print(f"{'='*70}\n")
        
        return search['remaining'] > 5
    except Exception as e:
        print(f"⚠️ Rate Limit Check failed: {e}")
        return True

def optimized_search() ->
