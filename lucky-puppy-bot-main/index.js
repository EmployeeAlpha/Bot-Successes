import dotenv from "dotenv";
dotenv.config();

import TelegramBot from "node-telegram-bot-api";
import fs from "fs";
import path from "path";
import fetch from "node-fetch";
import cron from "node-cron";

// === Constants & Paths ===
const TELEGRAM_API_TOKEN = process.env.TELEGRAM_API_TOKEN;
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const NEWS_API_KEY = process.env.NEWS_API_KEY;
const TARGET_CHAT_ID = process.env.TARGET_CHAT_ID; // Group/channel ID
const ADMIN_USER_ID = process.env.ADMIN_USER_ID;   // Your personal user ID

const QUOTES_FILE = "./quotes.txt";
const USERS_FILE = "./data/users.json";
const GREETED_USERS_FILE = "./data/greeted_users.json";
const POSTED_ARTICLES_FILE = "./data/posted_articles.txt";
const USER_QUOTE_INDEX_FILE = "./data/user_queues.json";

// === Load Quotes ===
function sanitizeQuotes(lines) {
  const cleaned = lines
    .map(l => l.replace(/^\uFEFF/, "").trim())
    .filter(l => l && !l.startsWith("#"));
  return cleaned;
}
function loadQuotes() {
  try {
    if (fs.existsSync(QUOTES_FILE)) {
      const raw = fs.readFileSync(QUOTES_FILE, "utf-8").split("\n");
      return sanitizeQuotes(raw);
    }
  } catch {}
  return [];
}
const quotes = loadQuotes();

// === Shuffle Queues per User ===
function fisherYatesShuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}
function buildNewQueue() {
  return fisherYatesShuffle([...Array(quotes.length).keys()]);
}
function loadUserQueues() {
  try {
    const raw = fs.readFileSync(USER_QUOTE_INDEX_FILE, "utf-8");
    const parsed = JSON.parse(raw);
    for (const [uid, val] of Object.entries(parsed)) {
      if (typeof val === "number") {
        parsed[uid] = { queue: [], version: quotes.length };
      }
    }
    return parsed;
  } catch {
    return {};
  }
}
function saveUserQueues(state) {
  fs.writeFileSync(USER_QUOTE_INDEX_FILE, JSON.stringify(state, null, 2));
}
function getNextQuoteForUser(userId) {
  const user = _userQueues[userId] || { queue: [], version: quotes.length };
  if (user.version !== quotes.length || user.queue.length === 0) {
    user.queue = buildNewQueue();
    user.version = quotes.length;
  }
  const nextIndex = user.queue.shift();
  _userQueues[userId] = user;
  saveUserQueues(_userQueues);
  return quotes[nextIndex];
}
const _userQueues = loadUserQueues();

// === Users & Greeted Users ===
function loadUsers() {
  try {
    return new Set(JSON.parse(fs.readFileSync(USERS_FILE, "utf-8")));
  } catch {
    return new Set();
  }
}
function saveUsers(set) {
  fs.writeFileSync(USERS_FILE, JSON.stringify([...set]));
}
const users = loadUsers();
let greetedUsers = new Set(JSON.parse(fs.readFileSync(GREETED_USERS_FILE, "utf-8") || "[]"));

// === Bot Init ===
const bot = new TelegramBot(TELEGRAM_API_TOKEN, {
  polling: {
    interval: 3000,
    autoStart: true,
    params: { timeout: 10 }
  }
});

// === Start Command ===
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(msg.chat.id, `Hello! I'm Lucky, your English AI familiar of Lexmilian. I'm a bit shy, so please message only important stuff. If we chat too much, I'll pause until tomorrow.`);
});

// === AI Chat Handler ===
bot.on("message", async (msg) => {
  const userId = msg.from.id;
  const chatId = msg.chat.id;

  // Store user
  if (!users.has(userId)) {
    users.add(userId);
    saveUsers(users);
  }

  // Greet once
  if (!greetedUsers.has(userId) && msg.text && !msg.text.startsWith("/")) {
    const introMsg = `Hi! I'm Lucky, an English AI familiar of Lexmilian. I'm a bit shy, so please message only important stuff.`;
    await bot.sendMessage(chatId, introMsg);
    greetedUsers.add(userId);
    fs.writeFileSync(GREETED_USERS_FILE, JSON.stringify([...greetedUsers]));
  }

  if (msg.text && msg.text.startsWith("/")) return;

  // AI reply
  const aiReply = await getAIReply(msg.text);
  await bot.sendMessage(chatId, aiReply);
});

async function getAIReply(userMessage) {
  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: userMessage }],
        max_tokens: 200,
        temperature: 0.7
      })
    });
    const data = await response.json();
    return data.choices?.[0]?.message?.content?.trim() || "Sorry, I couldn't think of a reply.";
  } catch (e) {
    console.error("AI error:", e.message);
    return "Oops, I had a hiccup!";
  }
}

// === Post Quote & Article ===
function postQuote(chatId) {
  const quote = quotes[Math.floor(Math.random() * quotes.length)];
  bot.sendMessage(chatId, `📜 From Lexmilian's Archives:\n\n“${quote}”`);
}
function getRandomArticle() {
  const dummy = [
    "https://example.com/article1",
    "https://example.com/article2",
    "https://example.com/article3"
  ];
  const posted = new Set(readLines(POSTED_ARTICLES_FILE));
  const options = dummy.filter(url => !posted.has(url));
  if (options.length === 0) return null;
  const choice = options[Math.floor(Math.random() * options.length)];
  appendLine(POSTED_ARTICLES_FILE, choice);
  return choice;
}
function postArticle(chatId) {
  const url = getRandomArticle();
  if (url) {
    bot.sendMessage(chatId, `📰 Here's a random article:\n${url}`);
  }
}

// === File Helpers ===
function readLines(file) {
  try {
    return fs.readFileSync(file, "utf8").split("\n").filter(Boolean);
  } catch {
    return [];
  }
}
function appendLine(file, line) {
  try {
    fs.appendFileSync(file, line + "\n");
  } catch {}
}

// === Daily Quotes to Individuals ===
function sendDailyQuotesToUsers() {
  users.forEach(async (uid) => {
    const quote = getNextQuoteForUser(uid);
    try {
      await bot.sendMessage(uid, `📜 Daily quote:\n\n“${quote}”`);
    } catch (e) {
      console.error(`Error sending quote to ${uid}:`, e.message);
    }
  });
}

// === Schedule (Perth Timezone) ===
cron.schedule("0 9,18 * * *", () => postQuote(TARGET_CHAT_ID), {
  timezone: "Australia/Perth"
});
cron.schedule("0 12,21 * * *", () => postArticle(TARGET_CHAT_ID), {
  timezone: "Australia/Perth"
});
cron.schedule("0 10 * * *", () => sendDailyQuotesToUsers(), {
  timezone: "Australia/Perth"
});
sendDailyQuotesToUsers(); // Run on startup

console.log("Lucky Puppy Bot is live with scheduled posts and AI replies!");
