import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
SPORTSDB_KEY = "3"  # free public test key
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}"

LEAGUE_IDS = {
    "epl": "4328",
    "laliga": "4335",
    "seriea": "4332",
    "bundesliga": "4331",
    "ligue1": "4334",
}

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
        "/help - Show this menu"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Fetching today's fixtures...")
    try:
        resp = requests.get(f"{BASE_URL}/eventsday.php?d=today&s=Soccer", timeout=10)
        data = resp.json()
        events = data.get("events")
        if not events:
            await update.message.reply_text("No football fixtures found for today.")
            return
        lines = []
        for e in events[:15]:
            home = e.get("strHomeTeam", "?")
            away = e.get("strAwayTeam", "?")
            time_ = e.get("strTime", "TBD")
            league = e.get("strLeague", "")
            lines.append(f"🏆 {league}\n{home} vs {away} — {time_} UTC")
        await update.message.reply_text("\n\n".join(lines))
    except Exception as e:
        logger.error(f"today error: {e}")
        await update.message.reply_text("⚠️ Couldn't fetch fixtures right now, try again later.")

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

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("standings", standings))
    logger.info("Bot starting (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
