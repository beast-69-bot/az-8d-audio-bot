import config
import telebot
import handlers

bot = telebot.TeleBot(config.BOT_TOKEN)

engine_title = "AI Vocal Separation (Meta Demucs)"
card = handlers.render_progress_card(
    engine_title,
    10.0,
    stage="1/1",
    detail="Initializing engine..."
)
print("CARD:")
print(card)
try:
    # Do dry-run / send test message
    msg = bot.send_message(8615007714, card, parse_mode="Markdown")
    print("SUCCESS, message_id:", msg.message_id)
except Exception as e:
    print("SEND FAILED:", e)
