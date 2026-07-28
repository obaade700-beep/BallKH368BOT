import logging
import json
import os
import requests
from datetime import time, datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
FD_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "PUT_YOUR_KEY_HERE")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FD_API_KEY}
SUBSCRIBERS_FILE = "subscribers.json"

COMPETITIONS = {
    "epl": "PL",
    "laliga": "PD",
    "seriea": "SA",
    "bundesliga": "BL1",
    "ligue1": "FL1",
    "ucl": "CL",
    "eredivisie": "DED",
    "primeira": "PPL",
}

# ---------- Startup sanity check ----------
logger.info(f"BOT_TOKEN loaded: {'YES' if BOT_TOKEN != 'PUT_YOUR_TOKEN_HERE' else 'NO - MISSING'}")
logger.info(f"FOOTBALL_DATA_API_KEY loaded: {'YES' if FD_API_KEY != 'PUT_YOUR_KEY_HERE' else 'NO - MISSING'}")

# ---------- Subscriber storage ----------

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(list(subs), f)

subscribers = load_subscribers()

# ---------- Helpers ----------

def get_today_fixtures_text():
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BASE_URL}/matches",
            headers=HEADERS,
            params={"dateFrom": today, "dateTo": today},
            timeout=10
        )
        logger.info(f"fixtures status={resp.status_code} body={resp.text[:300]}")
        if resp.status_code == 429:
            return "⚠️ Rate limit hit, try again in a minute."
        if resp.status_code != 200:
            return f"⚠️ API returned status {resp.status_code}. The API key may be missing or invalid on the server."
        data = resp.json()
        matches = data.get("matches", [])
        if not matches:
            return "No fixtures found for today in supported leagues."
        lines = ["📅 *Today's Fixtures*\n"]
        for m in matches[:15]:
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            comp = m["competition"]["name"]
            utc_time = m["utcDate"][11:16]
            lines.append(f"🏆 {comp}\n{home} vs {away} — {utc_time} UTC")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"fixtures fetch error: {e}")
        return "⚠️ Couldn't fetch fixtures right now, try again later."

# ---------- Command handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Welcome to BallKH368 Bot!\n\n"
        "I bring you football fixtures, live scores and league tables.\n\n"
        "Type /help to see what I can do."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Commands*\n"
        "/today - Today's fixtures\n"
        "/live - Live scores right now\n"
        "/standings <league> - League table\n"
        "  (epl, laliga, seriea, bundesliga, ligue1, ucl, eredivisie, primeira)\n"
        "/subscribe - Get daily fixture alerts\n"
        "/unsubscribe - Stop daily alerts\n"
        "/help - Show this menu"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Fetching today's fixtures...")
    text = get_today_fixtures_text()
    await update.message.reply_text(text, parse_mode="Markdown")

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔴 Checking live scores...")
    try:
        resp = requests.get(
            f"{BASE_URL}/matches",
            headers=HEADERS,
            params={"status": "LIVE"},
            timeout=10
        )
        logger.info(f"live status={resp.status_code} body={resp.text[:300]}")
        if resp.status_code == 429:
            await update.message.reply_text("⚠️ Rate limit hit, try again in a minute.")
            return
        if resp.status_code != 200:
            await update.message.reply_text(
                f"⚠️ API returned status {resp.status_code}. The API key may be missing or invalid on the server."
            )
            return
        data = resp.json()
        matches = data.get("matches", [])
        if not matches:
            await update.message.reply_text("No matches are live right now. Try /today for the full schedule.")
            return
        lines = []
        for m in matches[:15]:
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            hs = m["score"]["fullTime"]["home"]
            as_ = m["score"]["fullTime"]["away"]
            hs = hs if hs is not None else 0
            as_ = as_ if as_ is not None else 0
            lines.append(f"{home} {hs} - {as_} {away}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error(f"live error: {e}")
        await update.message.reply_text("⚠️ Couldn't fetch live scores right now, try again later.")

async def standings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /standings epl\n"
            "Options: epl, laliga, seriea, bundesliga, ligue1, ucl, eredivisie, primeira"
        )
        return
    league_key = context.args[0].lower()
    comp_code = COMPETITIONS.get(league_key)
    if not comp_code:
        await update.message.reply_text("Unknown league. Try /help for the list of options.")
        return
    try:
        resp = requests.get(
            f"{BASE_URL}/competitions/{comp_code}/standings",
            headers=HEADERS,
            timeout=10
        )
        logger.info(f"standings status={resp.status_code} body={resp.text[:300]}")
        if resp.status_code == 429:
            await update.message.reply_text("⚠️ Rate limit hit, try again in a minute.")
            return
        if resp.status_code == 403:
            await update.message.reply_text("This league isn't available on the free API tier.")
            return
        if resp.status_code != 200:
            await update.message.reply_text(
                f"⚠️ API returned status {resp.status_code}. The API key may be missing or invalid on the server."
            )
            return
        data = resp.json()
        table = data["standings"][0]["table"]
        lines = [f"{row['position']}. {row['team']['name']} - {row['points']} pts" for row in table[:10]]
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error(f"standings error: {e}")
        await update.message.reply_text("⚠️ Couldn't fetch standings, try again later.")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        await update.message.reply_text("You're already subscribed to daily fixture alerts ✅")
        return
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    await update.message.reply_text(
        "🔔 Subscribed! You'll get today's fixtures every day at 08:00 UTC.\n"
        "Use /unsubscribe anytime to stop."
    )

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribers:
        await update.message.reply_text("You're not currently subscribed.")
        return
    subscribers.discard(chat_id)
    save_subscribers(subscribers)
    await update.message.reply_text("🔕 Unsubscribed. You won't receive daily alerts anymore.")

# ---------- Scheduled job ----------

async def send_daily_fixtures(context: ContextTypes.DEFAULT_TYPE):
    if not subscribers:
        return
    text = get_today_fixtures_text()
    for chat_id in list(subscribers):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send to {chat_id}: {e}")
            if "bot was blocked" in str(e).lower():
                subscribers.discard(chat_id)
                save_subscribers(subscribers)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("standings", standings))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    app.job_queue.run_daily(send_daily_fixtures, time=time(hour=8, minute=0))

    logger.info("Bot starting (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
