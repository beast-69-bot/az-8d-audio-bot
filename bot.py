"""
Main Executable Runner for AZ 8D Spatial Audio & Video Bot (@azmusicstudiobot).
"""

import sys
import logging
from telebot import TeleBot
import config
import handlers
import database as db

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("az_8d_bot")

def main():
    token = config.BOT_TOKEN
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        logger.error("[!] BOT_TOKEN is missing. Please set BOT_TOKEN in .env.")
        return

    logger.info("Initializing AZ 8D Audio Studio Telegram Bot...")
    bot = TeleBot(token)
    
    # Initialize DB
    db.init_db()
    
    # Register all handlers
    handlers.register_handlers(bot)
    
    logger.info("AZ 8D Audio Bot started successfully! Listening for messages...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=15)
    except Exception as e:
        logger.critical(f"Bot polling error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
