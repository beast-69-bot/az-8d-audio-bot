import telebot
import config

bot = telebot.TeleBot(config.BOT_TOKEN)
print("Before Webhook info:", bot.get_webhook_info())

# Delete webhook and reset allowed_updates
bot.delete_webhook(drop_pending_updates=False)

# Test getting updates with full allowed_updates
import telebot.util as util
print("Update types:", util.update_types)

# Now check updates with allowed_updates specified
updates = bot.get_updates(offset=-1, allowed_updates=util.update_types)
print("Fetched updates count:", len(updates))
for u in updates:
    print("Update ID:", u.update_id, "Type:", u.content_type if hasattr(u, 'content_type') else dir(u))

print("After Webhook info:", bot.get_webhook_info())
