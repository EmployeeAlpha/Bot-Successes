# 🐶 Lucky Puppy Bot --- My First Bot in Telegram Named "Lucky"!
Lucky Puppy is a smart, friendly, and interactive AI-powered Telegram bot designed to bring joy, wisdom, and engagement to your Telegram chats. It runs on Fly.io, uses OpenRouter.io for AI responses, and comes with thoughtful scheduling, quote delivery, and behavior-based interaction limits.

✨ Features
🎙️ AI Chatting
Responds conversationally when addressed directly in group chats or in 1:1 private chat.

Powered by OpenRouter.io (supports OpenAI, Anthropic, and others via proxy).

Limits replies to 20 messages per user per day to conserve API usage (this resets daily).

🕓 Automated Message Scheduler
Posts 4 scheduled messages daily, such as news items, inspirational quotes, or AI musings.

Messages are delivered at random or predefined times (adjustable in code or via CRON logic).

🙋 Welcomes New Users
On their first message of the day, a user is greeted with a warm and friendly AI-generated message.

First-message greetings happen only once per day per user (tracked internally via logs).

💬 Lexmilian’s Wisdom
Regularly interjects with quotes or sayings attributed to Lexmilian.

Lexmilian quotes are stored in a .txt file and pulled randomly or in sequence.

📚 Persistent Memory & Logging
The bot maintains lightweight logs for:

Users greeted per day

Message quota used

Message history for debug/reference

Logs are stored in .txt files in the same directory (e.g., logs/).

🔒 Respectful Rate Limiting
If a user exceeds their daily quota, the bot politely lets them know it's resting and will talk again tomorrow.

🛠️ Project Structure
bash
lucky-puppy-bot/
├── bot.py                # Main Python bot logic
├── fly.toml              # Fly.io deployment config
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment file (do not commit .env)
├── quotes.txt            # Lexmilian quotes file
├── logs/
│   ├── greeted_users.txt     # Users greeted today
│   ├── message_count.txt     # Daily message count
│   └── activity_log.txt      # Optional full interaction log
⚙️ Environment Variables (.env)
Set up the following variables (locally or on Fly.io secrets):

env
TELEGRAM_API_TOKEN=your-telegram-bot-token-here
OPENROUTER_API_KEY=your-openrouter-api-key-here
NEWS_API_KEY=your-news-api-key-if-needed
These credentials are not committed to GitHub. The bot reads them securely using os.environ.

🚀 Deployment
The bot is designed to be deployed via Fly.io:

🔧 fly.toml Example
toml
app = "lucky-puppy-bot"
kill_signal = "SIGINT"
kill_timeout = 5
processes = []

[deploy]
  release_command = ""

[experimental]
  allowed_public_ports = []
  auto_rollback = true
🧪 First-Time Setup
bash
flyctl launch  # if not launched yet
flyctl secrets set TELEGRAM_API_TOKEN=... OPENROUTER_API_KEY=... NEWS_API_KEY=...
flyctl deploy --remote-only
🔐 Permissions and File Access
Ensure your bot has read/write access to its log files when hosted:

Log files must be created and writable during runtime.

In local dev or Fly.io, ensure the bot doesn't attempt to write to read-only folders like /app/ (use /data/ or working directory).

File operations are handled via Python's open(..., 'a+') or with open(...).

📣 Public Access to Logs?
No, log files such as message_count.txt or greeted_users.txt are never made public and are not part of any web-accessible endpoint.

👤 Credits
💡 Concept and original quotes: Lexmilian de Mello

🤖 Codebase: Custom Python Telegram bot

☁️ Hosting: Fly.io

🧠 AI Backend: OpenRouter.io

📌 To Do / Future Features
 Admin command to reset user quota manually.

 Webhook deployment option.

 Dashboard or monitoring stats.

 Optional voice/text-to-speech replies.

📬 Contact
For feedback, improvements, or Lexmilian’s newsletter, visit https://bit.ly/m/exphabius
