import os
import logging
import joblib
import numpy as np
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from app.db.session import SessionLocal
from app.models.league import League
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.telegram_user import TelegramUser

logging.basicConfig(level=logging.INFO)

# Load ML models
try:
    BTTS_MODEL = joblib.load("app/ml/btts_model.joblib")
    BTTS_COLS  = joblib.load("app/ml/btts_feature_columns.joblib")
    OU_MODEL   = joblib.load("app/ml/over25_model.joblib")
    OU_COLS    = joblib.load("app/ml/over25_feature_columns.joblib")
    print("ML models loaded OK")
except Exception as e:
    print(f"ML model load warning: {e}")
    BTTS_MODEL = OU_MODEL = None


def track_user(user):
    db = SessionLocal()
    try:
        existing = db.query(TelegramUser).filter(
            TelegramUser.telegram_id == str(user.id)
        ).first()
        if not existing:
            db.add(TelegramUser(
                telegram_id=str(user.id),
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
            ))
            db.commit()
            return True  # new user
        else:
            existing.last_seen = datetime.utcnow()
            db.commit()
            return False  # returning user
    finally:
        db.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = track_user(user)
    greeting = "Welcome" if is_new else "Welcome back"
    keyboard = [
        [InlineKeyboardButton("Today Matches", callback_data="today")],
        [InlineKeyboardButton("Match Winner Predictions", callback_data="predictions")],
        [InlineKeyboardButton("BTTS Predictions", callback_data="btts")],
        [InlineKeyboardButton("Over 2.5 Predictions", callback_data="over25")],
        [InlineKeyboardButton("Leagues", callback_data="leagues")],
        [InlineKeyboardButton("Stats", callback_data="stats")],
    ]
    await update.message.reply_text(
        f"{greeting} {user.first_name} to STREAM Chief!\n\n"
        f"AI-powered football predictions across top 5 European leagues.\n\n"
        f"Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    track_user(query.from_user)
    db = SessionLocal()
    try:
        if query.data == "leagues":
            leagues = db.query(League).limit(10).all()
            text = "*Available Leagues:*\n\n"
            for l in leagues:
                text += f"- {l.name} ({l.country or 'International'})\n"
            await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "predictions":
            preds = (
                db.query(Prediction)
                .filter(Prediction.prediction_type == "match_winner")
                .order_by(Prediction.confidence.desc())
                .limit(8).all()
            )
            if not preds:
                await query.edit_message_text("No predictions available yet.")
                return
            text = "*Top Match Winner Predictions:*\n\n"
            for p in preds:
                text += (
                    f"Match {p.match_id}\n"
                    f"  Home: {p.predicted_home_win:.0%} | "
                    f"Draw: {p.predicted_draw:.0%} | "
                    f"Away: {p.predicted_away_win:.0%}\n"
                    f"  Confidence: {p.confidence:.0%}\n\n"
                )
            await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "btts":
            preds = (
                db.query(Prediction)
                .filter(Prediction.prediction_type == "btts")
                .order_by(Prediction.confidence.desc())
                .limit(8).all()
            )
            if not preds:
                await query.edit_message_text("No BTTS predictions yet. Run the prediction worker first.")
                return
            text = "*Both Teams To Score Predictions:*\n\n"
            for p in preds:
                text += f"Match {p.match_id}: {p.predicted_value} ({p.confidence:.0%} confidence)\n"
            await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "over25":
            preds = (
                db.query(Prediction)
                .filter(Prediction.prediction_type == "over25")
                .order_by(Prediction.confidence.desc())
                .limit(8).all()
            )
            if not preds:
                await query.edit_message_text("No Over 2.5 predictions yet. Run the prediction worker first.")
                return
            text = "*Over 2.5 Goals Predictions:*\n\n"
            for p in preds:
                text += f"Match {p.match_id}: {p.predicted_value} ({p.confidence:.0%} confidence)\n"
            await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "today":
            matches = (
                db.query(Match)
                .filter(Match.match_date >= date.today())
                .order_by(Match.match_date)
                .limit(8).all()
            )
            if not matches:
                await query.edit_message_text("No upcoming matches found.")
                return
            text = "*Upcoming Matches:*\n\n"
            for m in matches:
                text += f"Match {m.id} - {m.match_date.strftime('%d %b %H:%M') if m.match_date else 'TBD'}\n"
            await query.edit_message_text(text, parse_mode="Markdown")

        elif query.data == "stats":
            total_users = db.query(TelegramUser).count()
            total_preds = db.query(Prediction).count()
            total_matches = db.query(Match).count()
            text = (
                f"*STREAM Chief Stats:*\n\n"
                f"Users: {total_users}\n"
                f"Matches in DB: {total_matches}\n"
                f"Predictions generated: {total_preds}\n"
            )
            await query.edit_message_text(text, parse_mode="Markdown")

    finally:
        db.close()


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start - Main menu\n"
        "/help - This message\n"
    )


def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
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
