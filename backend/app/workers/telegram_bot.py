import os
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from app.db.session import SessionLocal
from app.models.league import League
from app.models.match import Match
from app.models.prediction import Prediction

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("Today Matches", callback_data="today")],
        [InlineKeyboardButton("Predictions", callback_data="predictions")],
        [InlineKeyboardButton("Leagues", callback_data="leagues")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Welcome {user.first_name} to SportsDB!\n\n"
        f"Get AI-powered match predictions, live scores and betting insights.\n\n"
        f"Choose an option below:",
        reply_markup=markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = SessionLocal()
    try:
        if query.data == "leagues":
            leagues = db.query(League).limit(10).all()
            text = "*Available Leagues:*\n\n"
            for l in leagues:
                text += f"- {l.name} ({l.country or 'International'})\n"
            await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "predictions":
            preds = db.query(Prediction).order_by(Prediction.id.desc()).limit(5).all()
            if not preds:
                await query.edit_message_text("No predictions available yet. Check back soon!")
            else:
                text = "*Latest Predictions:*\n\n"
                for p in preds:
                    text += f"- Match {p.match_id}: {p.prediction_type} -> {p.predicted_value}\n"
                await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "today":
            matches = db.query(Match).filter(
                Match.match_date >= date.today()
            ).limit(5).all()
            if not matches:
                await query.edit_message_text("No matches found for today.")
            else:
                text = "*Upcoming Matches:*\n\n"
                for m in matches:
                    text += f"- Match {m.id} on {m.match_date}\n"
                await query.edit_message_text(text, parse_mode="Markdown")
    finally:
        db.close()

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n/start - Main menu\n/help - This message\n/predictions - Latest predictions\n/leagues - Browse leagues"
    )

def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_bot()
