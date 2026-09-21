import os
import telebot
from telebot import types
import config
import uploader

bot = telebot.TeleBot(config.BOT_TOKEN)
user_id = 8615007714
file_path = "/home/anshu/az-8d-audio-bot/temp/test_vocal_out.mp3"

print("File exists:", os.path.exists(file_path), "size:", os.path.getsize(file_path) if os.path.exists(file_path) else 0)

effect_name = "vocal_ai"
inst_title = "Barse/Naina (Instrumental)"

kb_after = types.InlineKeyboardMarkup(row_width=1)
kb_after.add(types.InlineKeyboardButton("🎧 Convert Instrumental to 8D Audio", callback_data="eff_8d"))
kb_after.add(types.InlineKeyboardButton("🔥 Convert to 8D + Beat Boost", callback_data="eff_8d_bass"))
kb_after.add(types.InlineKeyboardButton("🎬 Open Video Studio (Visualizer Video)", callback_data="menu_video_studio"))
kb_after.add(types.InlineKeyboardButton("⬅️ Back to Audio Menu", callback_data="back_main"))

caption = (
    f"🎤❌ *Vocals Removed Successfully!* 🎶\n\n"
    f"• Mode: `🤖 Meta Demucs AI Neural Network`\n"
    f"• Bitrate: `320 kbps Studio Quality`\n"
    f"• Mastering: `-14 LUFS Loudness Normalized`\n\n"
    f"👇 *Is instrumental ko 8D me convert karein ya Video Studio open karein:*"
)

try:
    print("Testing send_audio_smart...")
    res = uploader.send_audio_smart(
        bot=bot,
        chat_id=user_id,
        file_path=file_path,
        title=inst_title,
        performer="AZ Vocal Remover",
        caption=caption,
        reply_markup=kb_after
    )
    print("SUCCESS! Result:", res)
except Exception as e:
    import traceback
    print("FAILED TO SEND AUDIO:")
    traceback.print_exc()
