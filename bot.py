#!/usr/bin/env python3
"""
TELEGRAM CONFIG TESTER
Zeigt GENAU was falsch ist!
"""

import requests
import os
import json

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
TOPIC_ID = os.environ.get("TOPIC_ID", "")

print("=" * 70)
print("🔍 TELEGRAM CONFIG DEBUG")
print("=" * 70)
print(f"\n📋 ENVIRONMENT VARIABLES:")
print(f"   TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:15]}...{TELEGRAM_TOKEN[-10:] if len(TELEGRAM_TOKEN) > 25 else '???'}")
print(f"   CHANNEL_ID: '{CHANNEL_ID}'")
print(f"   TOPIC_ID: '{TOPIC_ID}'")
print()

# Validierung
errors = []

if not TELEGRAM_TOKEN:
    errors.append("❌ TELEGRAM_TOKEN ist leer!")
elif not TELEGRAM_TOKEN.startswith("7"):
    errors.append("⚠️ TELEGRAM_TOKEN sollte mit '7' starten!")

if not CHANNEL_ID:
    errors.append("❌ CHANNEL_ID ist leer!")
elif not CHANNEL_ID.startswith("-100"):
    errors.append(f"❌ CHANNEL_ID muss mit -100 starten! Aktuell: {CHANNEL_ID}")
    print(f"   💡 Korrigiere zu: -100{CHANNEL_ID}")
    # Auto-fix
    if CHANNEL_ID.isdigit():
        CHANNEL_ID = f"-100{CHANNEL_ID}"
        print(f"   ✅ Auto-korrigiert: {CHANNEL_ID}")

if TOPIC_ID and not TOPIC_ID.isdigit():
    errors.append(f"⚠️ TOPIC_ID sollte eine Zahl sein! Aktuell: {TOPIC_ID}")

if errors:
    print("⚠️ PROBLEME GEFUNDEN:")
    for err in errors:
        print(f"   {err}")
    print()

print("=" * 70)
print("📤 SENDE TEST-NACHRICHT...")
print("=" * 70)

# Test 1: Haupt-Channel (ohne Topic)
def test_main_channel():
    print("\n🧪 TEST 1: Haupt-Channel (ohne Topic ID)")
    
    msg = f"""🧪 <b>TEST 1: HAUPT-CHANNEL</b>

Channel ID: <code>{CHANNEL_ID}</code>
Topic ID: <b>NICHT GESETZT</b>
Zeit: Jetzt

Wenn du das siehst, ist CHANNEL_ID korrekt! ✅"""
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    data = {
        'chat_id': CHANNEL_ID,
        'text': msg,
        'parse_mode': 'HTML'
    }
    
    print(f"   Chat ID: {data['chat_id']}")
    print(f"   Sende...")
    
    try:
        resp = requests.post(api_url, json=data, timeout=10)
        
        print(f"   Status: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            chat = result['result']['chat']
            print(f"   ✅ SUCCESS!")
            print(f"   Chat Title: {chat.get('title', 'N/A')}")
            print(f"   Chat Type: {chat.get('type', 'N/A')}")
            print(f"   Message ID: {result['result']['message_id']}")
            return True
        else:
            error = resp.json()
            print(f"   ❌ FEHLER: {error.get('description', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

# Test 2: Mit Topic ID
def test_with_topic():
    if not TOPIC_ID:
        print("\n⏭️ TEST 2 übersprungen (TOPIC_ID nicht gesetzt)")
        return False
    
    print(f"\n🧪 TEST 2: Mit Topic ID = {TOPIC_ID}")
    
    msg = f"""🧪 <b>TEST 2: MIT TOPIC</b>

Channel ID: <code>{CHANNEL_ID}</code>
Topic ID: <code>{TOPIC_ID}</code>
Zeit: Jetzt

Wenn du das im RICHTIGEN TOPIC siehst: ✅
Wenn du das im FALSCHEN TOPIC siehst: ❌"""
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    data = {
        'chat_id': CHANNEL_ID,
        'text': msg,
        'parse_mode': 'HTML',
        'message_thread_id': int(TOPIC_ID)
    }
    
    print(f"   Chat ID: {data['chat_id']}")
    print(f"   Topic ID: {data['message_thread_id']}")
    print(f"   Sende...")
    
    try:
        resp = requests.post(api_url, json=data, timeout=10)
        
        print(f"   Status: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ SUCCESS!")
            print(f"   Message ID: {result['result']['message_id']}")
            if 'message_thread_id' in result['result']:
                print(f"   Thread ID in Response: {result['result']['message_thread_id']}")
            return True
        else:
            error = resp.json()
            print(f"   ❌ FEHLER: {error.get('description', 'Unknown')}")
            
            desc = error.get('description', '').lower()
            if 'thread' in desc or 'topic' in desc:
                print(f"\n   💡 TOPIC_ID {TOPIC_ID} ist FALSCH!")
                print(f"   💡 Finde die richtige Topic ID:")
                print(f"      1. Forwarde Nachricht aus richtigem Topic an @userinfobot")
                print(f"      2. Bot zeigt die Topic ID")
            
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

# Test 3: Bot Info
def test_bot_info():
    print("\n🤖 BOT INFO:")
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
    
    try:
        resp = requests.get(api_url, timeout=10)
        
        if resp.status_code == 200:
            bot = resp.json()['result']
            print(f"   Bot Name: @{bot.get('username', 'N/A')}")
            print(f"   Bot ID: {bot.get('id', 'N/A')}")
            print(f"   Can Join Groups: {bot.get('can_join_groups', False)}")
            return True
        else:
            print(f"   ❌ Token ungültig!")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

# TESTS AUSFÜHREN
print()
test_bot_info()
result1 = test_main_channel()
result2 = test_with_topic()

print("\n" + "=" * 70)
print("📊 ERGEBNISSE:")
print("=" * 70)
print(f"   Test 1 (Haupt-Channel): {'✅ OK' if result1 else '❌ FEHLER'}")
print(f"   Test 2 (Mit Topic):      {'✅ OK' if result2 else '❌ FEHLER' if TOPIC_ID else '⏭️ Übersprungen'}")
print()

if result1 and not result2 and TOPIC_ID:
    print("💡 DIAGNOSE:")
    print("   ✅ CHANNEL_ID ist korrekt")
    print("   ❌ TOPIC_ID ist FALSCH!")
    print()
    print("   🔧 LÖSUNG:")
    print("   1. Gehe zu deinem Telegram Channel")
    print("   2. Öffne das RICHTIGE Topic")
    print("   3. Forwarde eine Nachricht an @userinfobot")
    print("   4. Bot zeigt: 'Message thread identifier: XXX'")
    print("   5. Setze TOPIC_ID = XXX in GitHub Secrets")
    print()

elif not result1:
    print("💡 DIAGNOSE:")
    print("   ❌ CHANNEL_ID ist FALSCH!")
    print()
    print("   🔧 LÖSUNG:")
    print("   1. Füge @userinfobot zu deinem Channel hinzu")
    print("   2. Schreibe eine Nachricht im Channel")
    print("   3. Bot zeigt: 'Chat: -100XXXXXXXXXX'")
    print("   4. Setze CHANNEL_ID = -100XXXXXXXXXX in GitHub Secrets")
    print()
    print(f"   📝 Deine aktuelle CHANNEL_ID: {CHANNEL_ID}")
    print(f"   📝 Sollte sein: -1002829439594 (aus deinem Link)")
    print()

else:
    print("✅ ALLES OK!")
    print("   Beide Tests erfolgreich!")
    print()

print("=" * 70)
print("🔍 CHECK DEINE TELEGRAM-NACHRICHTEN!")
print("=" * 70)
print("   Wo sind die Test-Nachrichten gelandet?")
print("   → Das zeigt dir welcher Channel/Topic aktuell verwendet wird!")
print("=" * 70)
