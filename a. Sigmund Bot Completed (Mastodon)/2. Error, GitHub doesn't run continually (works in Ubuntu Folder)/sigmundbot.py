# sigmundbot.py
# Mastodon personality bot with friendly greeting, flexible input handling, and Google Sheets logging

import os
import time
import re
from mastodon import Mastodon
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()

MASTODON_ACCESS_TOKEN = os.getenv('MASTODON_ACCESS_TOKEN')
MASTODON_API_BASE_URL = os.getenv('MASTODON_API_BASE_URL', 'https://mastodon.social')

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_API_JSON = os.getenv('GOOGLE_API_JSON')  # This should be the full JSON string from your service account credentials

# Authenticate Mastodon client
mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_API_BASE_URL
)

# Authenticate Google Sheets client
credentials_info = None
if GOOGLE_API_JSON:
    import json
    credentials_info = json.loads(GOOGLE_API_JSON)

if credentials_info:
    creds = Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1
else:
    sheet = None
    print("Google Sheets credentials missing or invalid. Logging disabled.")

# Keep track of greeted users (resets on restart)
greeted_users = set()

def log_interaction(user, message, response):
    """Append a new row to the Google Sheet with the interaction."""
    if sheet:
        try:
            sheet.append_row([user, message, response, time.strftime("%Y-%m-%d %H:%M:%S")])
        except Exception as e:
            print(f"Failed to log interaction: {e}")

def send_menu(sender, reply_id):
    message = (
        f"Hi @{sender}! I'm SigmundBOT 🤖\n\n"
        "Choose a test you'd like to take by replying with the number:\n"
        "1. Big Five Personality Test\n"
        "2. MBTI Personality Type Test\n"
        "3. Stoicism Level Test\n"
        "4. HEXACO Test\n"
        "Reply with a number (e.g. 1)"
    )
    mastodon.status_post(
        status=message,
        in_reply_to_id=reply_id,
        visibility='public'
    )
    log_interaction(sender, "(menu sent)", message)

def handle_mention(notification):
    status = notification['status']
    content = status['content'].lower()
    sender = status['account']['acct']
    reply_id = status['id']

    print(f"Received mention from @{sender}: {content}")

    # Strip HTML tags (Mastodon posts often have HTML)
    clean_content = re.sub('<[^<]+?>', '', content).strip()

    if clean_content in {"1", "2", "3", "4"}:
        if clean_content == "1":
            response = f"@{sender} You selected the Big Five Test! Take it here:\nhttps://openpsychometrics.org/tests/IPIP-BFFM/"
        elif clean_content == "2":
            response = f"@{sender} You selected the MBTI Test! Take it here:\nhttps://www.16personalities.com/free-personality-test"
        elif clean_content == "3":
            response = f"@{sender} You selected the Stoicism Level Test! Try this one:\nhttps://www.idrlabs.com/stoicism/test.php"
        elif clean_content == "4":
            response = f"@{sender} You selected the HEXACO Personality Test!\nhttps://hexaco.org/hexaco-online"

        mastodon.status_post(
            status=response,
            in_reply_to_id=reply_id,
            visibility='public'
        )
        greeted_users.add(sender)
        log_interaction(sender, clean_content, response)

    else:
        if sender not in greeted_users:
            send_menu(sender, reply_id)
            greeted_users.add(sender)
        else:
            response = f"@{sender} Sorry, I didn't understand. Please reply with a number 1–4."
            mastodon.status_post(
                status=response,
                in_reply_to_id=reply_id,
                visibility='public'
            )
            log_interaction(sender, clean_content, response)

def main():
    print("Bot is running and polling for mentions...")
    last_checked_id = None

    while True:
        try:
            notifications = mastodon.notifications(since_id=last_checked_id)
            print(f"Checked mentions since ID {last_checked_id}. Found {len(notifications)} notifications.")

            max_id = last_checked_id or 0

            for notification in notifications:
                if notification['type'] == 'mention':
                    handle_mention(notification)
                max_id = max(max_id, notification['id'])

            last_checked_id = max_id
            time.sleep(60)
        except Exception as e:
            print(f"Error during polling: {e}")
            time.sleep(30)

if __name__ == '__main__':
    main()
