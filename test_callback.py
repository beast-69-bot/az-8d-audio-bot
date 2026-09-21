import os
import time
import telebot
from telebot import types
import config
import database as db
import core
import uploader

user_id = 8615007714
session = db.get_session(user_id)
effect_name = "vocal_ai"

bot = telebot.TeleBot(config.BOT_TOKEN)

engine_title = "AI Vocal Separation (Meta Demucs)"
initial_card = handlers_card = handlers_title = engine_title

def render_progress_card(title: str, percentage: float, stage: str = "", detail: str = ""):
    length = 10
    pct = max(0.0, min(100.0, percentage))
    filled = int(round(length * pct / 100))
    bar = "▰" * filled + "▱" * (length - filled)
    lines = [f"⚡ *{title}*", f"`[{bar}]` *{pct:.1f}%*"]
    if stage:
        lines.append(f"📊 *Stage:* `{stage}`")
    if detail:
        lines.append(f"ℹ️ *Status:* `{detail}`")
    return "\n".join(lines)

initial_card = render_progress_card(engine_title, 10.0, stage="1/1", detail="Initializing engine...")
print("Sending initial card...")
status_msg = bot.send_message(user_id, initial_card, parse_mode="Markdown")
print("status_msg sent, id:", status_msg.message_id)

user_out_dir = config.OUTPUT_DIR / str(user_id)
user_out_dir.mkdir(exist_ok=True, parents=True)
song_clean = "".join(c for c in session.get("last_song_name", "audio") if c.isalnum() or c in (' ', '_', '-')).strip()
out_mp3 = str(user_out_dir / f"{song_clean}_{effect_name}.mp3")

def update_audio_progress(pct, detail):
    try:
        card = render_progress_card(engine_title, pct, stage="1/1", detail=detail)
        bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        print(f"Updated progress: {pct}% - {detail}", flush=True)
    except Exception as e:
        print(f"Update progress failed: {e}", flush=True)

print("Starting audio effect processing...")
core.process_audio_effect(
    session["raw_audio_path"],
    out_mp3,
    effect=effect_name,
    progress_callback=update_audio_progress
)
print("Effect finished. Output exists:", os.path.exists(out_mp3))

inst_title = f"{song_clean} (Instrumental)"
db.save_session(user_id, processed_audio_path=out_mp3, raw_audio_path=out_mp3, last_song_name=inst_title)
db.log_conversion(user_id, "audio", effect_name)

kb_after = types.InlineKeyboardMarkup(row_width=1)
kb_after.add(types.InlineKeyboardButton("🎧 Convert Instrumental to 8D Audio", callback_data="eff_8d"))
kb_after.add(types.InlineKeyboardButton("🔥 Convert to 8D + Beat Boost", callback_data="eff_8d_bass"))
kb_after.add(types.InlineKeyboardButton("🎬 Open Video Studio (Visualizer Video)", callback_data="menu_video_studio"))
kb_after.add(types.InlineKeyboardButton("⬅️ Back to Audio Menu", callback_data="back_main"))

print("Uploading mastered audio...")
uploader.send_audio_smart(
    bot=bot,
    chat_id=user_id,
    file_path=out_mp3,
    title=inst_title,
    performer="AZ Vocal Remover",
    caption=(
        f"🎤❌ *Vocals Removed Successfully!* 🎶\n\n"
        f"• Mode: `🤖 Meta Demucs AI Neural Network`\n"
        f"• Bitrate: `320 kbps Studio Quality`\n"
        f"• Mastering: `-14 LUFS Loudness Normalized`\n\n"
        f"👇 *Is instrumental ko 8D me convert karein ya Video Studio open karein:*"
    ),
    reply_markup=kb_after
)

try:
    bot.delete_message(status_msg.chat.id, status_msg.message_id)
except Exception:
    pass

print("ALL DONE!")
