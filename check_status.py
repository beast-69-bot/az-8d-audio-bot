import telebot
import config

bot = telebot.TeleBot(config.BOT_TOKEN)
print("Webhook info:", bot.get_webhook_info())
print("Bot me:", bot.get_me().username)
