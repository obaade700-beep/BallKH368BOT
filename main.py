import logging
import json
import os
import requests
from datetime import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
SPORTSDB_KEY = "3"
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"
SUBSCRIBERS_FILE = "subscribers.json"

LEAGUE_IDS = {
    "epl": "4328",
    "laliga": "4335",
    "seriea": "4332",
    "bundesliga": "4331",
    "ligue1": "4334",
}

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
        resp = requests.get(f"{BASE_URL}/eventsday.php?d=today&s=Soccer", timeout=10)
        data = resp.json()
        events = data.get("events")
        if not events:
            return "No football fixtures found for today."
        lines = ["📅 *Today's Fixtures*\n"]
        for e in events[:15]:
            home = e.get("strHomeTeam", "?")
            away = e.get("strAwayTeam", "?")
            time_ = e.get("strTime", "TBD")
            league = e.get("strLeague", "")
            lines.append(f"🏆 {league}\n{home} vs {away} — {time_} UTC")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"fixtures fetch error: {e}")
        return None

# ---------- Command handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Welcome to BallKH368 Bot!\n\n"
        "I bring you live football scores, fixtures, team info and league tables.\n\n"
        "Type /help to see what I can do."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Commands*\n"
        "/today - Today's fixtures\n"
        "/live - Live scores right now\n"
        "/team <name> - Search a team\n"
        "/standings <league> - League table (epl, laliga, seriea, bundesliga, ligue1)\n"
        "/subscribe - Get daily fixture alerts\n"
        "/unsubscribe - Stop daily alerts\n"
        "/help - Show this menu"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Fetching today's fixtures...")
    text = get_today_fixtures_text()
    if text is None:
        await update.message.reply_text("⚠️ Couldn't fetch fixtures right now, try again later.")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔴 Checking live scores...")
    try:
        resp = requests.get(f"{BASE_URL}/eventsday.php?d=today&s=Soccer", timeout=10)
        data = resp.json()
        events = data.get("events")
        if not events:
            await update.message.reply_text("No matches found today.")
            return
        live_events = [e for e in events if e.get("strStatus") in ("1H", "2H", "HT", "Live")]
        if not live_events:
            await update.message.reply_text("No matches are live right now. Try /today for the full schedule.")
            return
        lines = []
        for e in live_events[:15]:
            home = e.get("strHomeTeam", "?")
            away = e.get("strAwayTeam", "?")
            hs = e.get("intHomeScore", "0")
            as_ = e.get("intAwayScore", "0")
            status = e.get("strStatus", "")
            lines.append(f"{home} {hs} - {as_} {away} ({status})")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error(f"live error: {e}")
        await update.message.reply_text("⚠️ Couldn't fetch live scores right now, try again later.")

async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /team Arsenal")
        return
    name = " ".join(context.args)
    try:
        resp = requests.get(f"{BASE_URL}/searchteams.php?t={name}", timeout=10)
        data = resp.json()
        teams = data.get("teams")
        if not teams:
            await update.message.reply_text(f"No team found matching '{name}'.")
            return
        t = teams[0]
        info = (
            f"🏟️ *{t.get('strTeam')}*\n"
            f"League: {t.get('strLeague')}\n"
            f"Stadium: {t.get('strStadium')}\n"
            f"Founded: {t.get('intFormedYear')}\n"
        )
        await update.message.reply_text(info, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"team error: {e}")
        await update.message.reply_text("⚠️ Couldn't fetch team info, try again later.")

async def standings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /standings epl\nOptions: epl, laliga, seriea, bundesliga, ligue1"
        )
        return
    league_key = context.args[0].lower()
    league_id = LEAGUE_IDS.get(league_key)
    if not league_id:
        await update.message.reply_text("Unknown league. Options: epl, laliga, seriea, bundesliga, ligue1")
        return
    try:
        resp = requests.get(f"{BASE_URL}/lookuptable.php?l={league_id}&s=2024-2025", timeout=10)
        data = resp.json()
        table = data.get("table")
        if not table:
            await update.message.reply_text("Standings not available right now.")
            return
        lines = [f"{row['intRank']}. {row['strTeam']} - {row['intPoints']} pts" for row in table[:10]]
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
    if text is None:
        return
    for chat_id in list(subscribers):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send to {chat_id}: {e}")
            # Optional: auto-remove chat_ids that block the bot
            if "bot was blocked" in str(e).lower():
                subscribers.discard(chat_id)
                save_subscribers(subscribers)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("standings", standings))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Run daily at 08:00 UTC
    app.job_queue.run_daily(send_daily_fixtures, time=time(hour=8, minute=0))

    logger.info("Bot starting (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
