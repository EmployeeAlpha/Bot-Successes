# bot.py — Lucky Puppy Bot (Telegram, polling worker)
# Features:
# - Polling (no inbound HTTP)
# - 4 scheduled posts/day (AWST) from quotes.txt + GNews twice daily alternating
# - Per-user 20 replies/day limit, resets at local midnight
# - Greet users once/day on their first message
# - Optional OpenRouter AI replies when DM or mentioned
# - Persists counters and next-quote index under /data/logs if available

from __future__ import annotations

import asyncio
import os
import re
import signal
import sys
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Set, List, Optional
from datetime import time, datetime

from loguru import logger
import httpx
from zoneinfo import ZoneInfo

from telegram import Update, MessageEntity
from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------
# Configuration & constants
# -------------------------

APP_NAME = "Lucky Puppy Bot"
TZ = ZoneInfo(os.getenv("TZ", "Australia/Perth"))  # your local time
DEFAULT_SCHEDULE_TIMES = ["09:00", "12:00", "17:00", "21:00"]
SCHEDULE_TIMES_ENV = os.getenv("SCHEDULE_TIMES")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
TARGET_CHAT_ID_ENV = os.getenv("TARGET_CHAT_ID")  # optional

# Paths
DATA_DIR = Path("/data/logs") if Path("/data").exists() else Path("./logs")
DATA_DIR.mkdir(parents=True, exist_ok=True)

QUOTES_FILE = Path("quotes.txt")
NEXT_INDEX_FILE = DATA_DIR / "next_index.txt"
MESSAGE_COUNT_FILE = DATA_DIR / "message_count.txt"
GREETED_USERS_FILE = DATA_DIR / "greeted_users.txt"

DAILY_REPLY_LIMIT = int(os.getenv("DAILY_REPLY_LIMIT", "20"))
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
OPENROUTER_BASE = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")


@dataclass
class DailyState:
    user_counts: Dict[int, int] = field(default_factory=dict)
    greeted_users: Set[int] = field(default_factory=set)
    next_quote_index: int = 0


state = DailyState()

# -------------------------
# Utilities
# -------------------------

def parse_schedule_times() -> List[time]:
    raw = SCHEDULE_TIMES_ENV.split(",") if SCHEDULE_TIMES_ENV else DEFAULT_SCHEDULE_TIMES
    times: List[time] = []
    for t in raw:
        t = t.strip()
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
        if not m:
            logger.warning(f"Ignoring invalid schedule time: {t!r}")
            continue
        hh, mm = int(m.group(1)), int(m.group(2))
        if not (0 <= hh < 24 and 0 <= mm < 60):
            logger.warning(f"Ignoring out-of-range time: {t!r}")
            continue
        times.append(time(hour=hh, minute=mm, tzinfo=TZ))
    if not times:
        times = [time(hour=int(x.split(':')[0]), minute=int(x.split(':')[1]), tzinfo=TZ) for x in DEFAULT_SCHEDULE_TIMES]
    return times


def load_quotes() -> List[str]:
    if not QUOTES_FILE.exists():
        logger.warning(f"{QUOTES_FILE} not found.")
        return []
    try:
        lines = [ln.strip() for ln in QUOTES_FILE.read_text(encoding="utf-8").splitlines()]
        quotes = [q for q in lines if q]
        logger.info(f"Loaded {len(quotes)} quotes from {QUOTES_FILE}")
        return quotes
    except Exception as e:
        logger.exception(f"Failed to read {QUOTES_FILE}: {e}")
        return []


def persist_daily_files():
    try:
        with MESSAGE_COUNT_FILE.open("w", encoding="utf-8") as f:
            for uid, cnt in sorted(state.user_counts.items()):
                f.write(f"{uid},{cnt}\n")
        with GREETED_USERS_FILE.open("w", encoding="utf-8") as f:
            for uid in sorted(state.greeted_users):
                f.write(f"{uid}\n")
        with NEXT_INDEX_FILE.open("w", encoding="utf-8") as f:
            f.write(str(state.next_quote_index))
    except Exception as e:
        logger.warning(f"Failed to persist daily files: {e}")


def load_next_index():
    try:
        if NEXT_INDEX_FILE.exists():
            val = NEXT_INDEX_FILE.read_text(encoding="utf-8").strip()
            if val.isdigit():
                state.next_quote_index = int(val)
                logger.info(f"Restored next_quote_index={state.next_quote_index}")
    except Exception as e:
        logger.warning(f"Failed to read {NEXT_INDEX_FILE}: {e}")


def next_quote(quotes: List[str]) -> str:
    if not quotes:
        return "🐶 Lucky Puppy is wagging its tail… (No quotes.txt found yet.)"
    i = state.next_quote_index % len(quotes)
    state.next_quote_index = (state.next_quote_index + 1) % len(quotes)
    persist_daily_files()
    return f"“{quotes[i]}”"


def format_user(u) -> str:
    return (u.full_name or u.username or str(u.id)).strip()

# -------------------------
# OpenRouter (optional)
# -------------------------

async def ask_openrouter(prompt: str) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are Lucky Puppy, a friendly, concise AI companion."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 300,
    }
    try:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content")
    except Exception as e:
        logger.warning(f"OpenRouter call failed: {e}")
        return None

# -------------------------
# GNews.io News fetcher
# -------------------------

async def fetch_news_headlines() -> Optional[str]:
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set, skipping news fetch.")
        return None
    url = f"https://gnews.io/api/v4/top-headlines?token={NEWS_API_KEY}&lang=en&max=3"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            articles = data.get("articles", [])
            if not articles:
                return None
            headlines = []
            for art in articles[:3]:
                title = art.get("title", "No title")
                source = art.get("source", {}).get("name", "unknown source")
                headlines.append(f"• {title} ({source})")
            return "📰 *Today's Headlines:*\n" + "\n".join(headlines)
    except Exception as e:
        logger.warning(f"News fetch failed: {e}")
        return None

# -------------------------
# Handlers
# -------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🐶 Hello! I’m Lucky Puppy.\n"
        "• I chat in DMs or when mentioned in groups.\n"
        "• I also post scheduled quotes and news each day.\n"
        "• I’m polite and won’t over-chat (20 replies per user/day)."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Help:\n"
        "• Chat with me in private, or mention me in groups.\n"
        "• I’ll post quotes and news on schedule.\n"
        "• Admin can set environment variables for schedule and limits.\n"
        "• Powered by OpenRouter (if API key is set)."
    )


def is_addressed_to_bot(update: Update, bot_username: Optional[str]) -> bool:
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    if not bot_username:
        return False
    if msg.entities:
        for ent in msg.parse_entities([MessageEntity.MENTION]).values():
            if ent.lower() == f"@{bot_username.lower()}":
                return True
    if msg.text and f"@{bot_username.lower()}" in msg.text.lower():
        return True
    return False


async def greet_if_first_today(update: Update):
    uid = update.effective_user.id
    if uid not in state.greeted_users:
        state.greeted_users.add(uid)
        persist_daily_files()
        await update.effective_message.reply_text(
            f"👋 Welcome, {format_user(update.effective_user)}! Lucky is happy to see you today."
        )


async def enforce_daily_limit(update: Update) -> bool:
    uid = update.effective_user.id
    cur = state.user_counts.get(uid, 0)
    if cur >= DAILY_REPLY_LIMIT:
        if cur == DAILY_REPLY_LIMIT:
            await update.effective_message.reply_text(
                "I’m resting now 💤 I’ll chat again with you tomorrow."
            )
        state.user_counts[uid] = cur + 1
        persist_daily_files()
        return False
    state.user_counts[uid] = cur + 1
    persist_daily_files()
    return True


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    try:
        bot_username = (await context.bot.get_me()).username
    except Exception:
        bot_username = None
    await greet_if_first_today(update)
    if not is_addressed_to_bot(update, bot_username):
        return
    if not await enforce_daily_limit(update):
        return
    text = (update.effective_message.text or "").strip()
    reply = await ask_openrouter(text) or "🐾 *Lucky is thinking…* (AI is snoozing right now.)"
    await update.effective_message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

# -------------------------
# Scheduled postings
# -------------------------

async def post_scheduled(context: ContextTypes.DEFAULT_TYPE):
    quotes = context.application.bot_data.get("quotes")
    chat_id = context.application.bot_data.get("target_chat_id")
    if not chat_id:
        logger.info("No TARGET_CHAT_ID set; skipping scheduled post.")
        return

    schedule_times = parse_schedule_times()
    now = datetime.now(TZ)

    # Determine which scheduled time just triggered the job
    triggered_time = None
    for t in schedule_times:
        # Compare scheduled time to now by hour and minute, ignoring seconds
        if now.hour == t.hour and now.minute == t.minute:
            triggered_time = t
            break

    if triggered_time is None:
        logger.warning(f"Scheduled post triggered at unexpected time: {now.time()}")
        return

    # Determine if this is an even or odd index schedule to alternate quote/news
    index = schedule_times.index(triggered_time)
    try:
        if index % 2 == 0:
            # Even schedule time: post quote
            msg = next_quote(quotes) if quotes else "🐶 Lucky says hello!"
        else:
            # Odd schedule time: post news
            news = await fetch_news_headlines()
            msg = news if news else "📰 No news available at the moment."
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Scheduled post sent to {chat_id} at {triggered_time.strftime('%H:%M')}")
    except Exception as e:
        logger.warning(f"Failed to send scheduled post: {e}")


def schedule_jobs(app: Application):
    reset_at = time(hour=0, minute=5, tzinfo=TZ)
    app.job_queue.run_daily(reset_daily, reset_at, name="daily_reset")
    for t in parse_schedule_times():
        app.job_queue.run_daily(post_scheduled, t, name=f"post_{t.hour:02d}{t.minute:02d}")
    logger.info(f"Scheduled jobs set for {[t.strftime('%H:%M') for t in parse_schedule_times()]} (TZ={TZ})")


async def reset_daily(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Resetting daily state (limits & greetings).")
    state.user_counts.clear()
    state.greeted_users.clear()
    persist_daily_files()

# -------------------------
# Startup & main
# -------------------------

def configure_logging():
    logger.remove()
    logger.add(sys.stdout, level=os.getenv("LOG_LEVEL", "INFO"), enqueue=True)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.add(DATA_DIR / "bot.log", level="INFO", rotation="1 MB", retention=5)
    except Exception:
        pass


async def on_start(app: Application):
    quotes = load_quotes()
    app.bot_data["quotes"] = quotes
    chat_id = None
    if TARGET_CHAT_ID_ENV:
        try:
            chat_id = int(TARGET_CHAT_ID_ENV)
        except ValueError:
            chat_id = TARGET_CHAT_ID_ENV
    app.bot_data["target_chat_id"] = chat_id
    schedule_jobs(app)
    logger.info(f"{APP_NAME} started. Polling in {TZ} time zone.")
    if chat_id:
        logger.info(f"Scheduled posts will go to TARGET_CHAT_ID={chat_id}")


def build_application() -> Application:
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_API_TOKEN. Set it in Fly secrets.")
        sys.exit(1)
    configure_logging()
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(on_start)
        .concurrent_updates(True)
        .rate_limiter(None)
        .build()
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app


async def main_async():
    app = build_application()
    try:
        webhook_info = await app.bot.get_webhook_info()
        if webhook_info.url:
            logger.info(f"Existing webhook found: {webhook_info.url}")
        else:
            logger.info("No existing webhook set.")
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully. Starting polling...")
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal(*_args):
        logger.info("Signal received, stopping…")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal)
        except NotImplementedError:
            pass

    runner = asyncio.create_task(app.run_polling(close_loop=False, allowed_updates=Update.ALL_TYPES))
    await stop_event.wait()
    await app.shutdown()
    await app.stop()
    runner.cancel()
    with contextlib.suppress(Exception):
        await runner


import asyncio
import sys

if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass  # If nest_asyncio isn't installed, proceed normally

    async def main_runner():
        from bot import main_async  # Assuming your async main function is named main_async in bot.py
        await main_async()

    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Running inside an existing event loop (e.g. Jupyter or some IDEs)
        loop.create_task(main_runner())
        loop.run_forever()
    else:
        try:
            loop.run_until_complete(main_runner())
        except KeyboardInterrupt:
            print("Bot stopped by user")
            sys.exit(0)
