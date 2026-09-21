"""
Telegram Bot Message and Callback Handlers for AZ 8D Audio Bot.
Provides seamless user workflows:
1. Standard Audio conversion (8D, 16D, Slowed, Nightcore, Bass Boost).
2. Dedicated Video Studio: Select wallpaper before rendering, customize visualizer wave.
3. As-Is Audio Video Rendering: Turn any pre-converted audio into video without double-processing.
4. Flexible Photo Uploads: Send custom wallpapers before or after the audio file.
"""

import os
import time
import shutil
import logging
import threading
from pathlib import Path
from telebot import TeleBot, types
import config
import database as db
import core
import uploader

logger = logging.getLogger("az_8d_bot.handlers")

USER_BUSY = {}

def is_user_busy(user_id: int) -> bool:
    busy_time = USER_BUSY.get(user_id)
    if not busy_time:
        return False
    if time.time() - busy_time > 180:
        USER_BUSY.pop(user_id, None)
        return False
    return True

def set_user_busy(user_id: int, busy: bool):
    if busy:
        USER_BUSY[user_id] = time.time()
    else:
        USER_BUSY.pop(user_id, None)

def get_effect_keyboard(session: dict):
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_8d = types.InlineKeyboardButton("🎧 8D Audio", callback_data="eff_8d")
    b_8d_bass = types.InlineKeyboardButton("🔥 8D + Beat Boost", callback_data="eff_8d_bass")
    b_16d = types.InlineKeyboardButton("🌀 16D Audio", callback_data="eff_16d")
    b_slow = types.InlineKeyboardButton("🌌 Slowed + Reverb", callback_data="eff_slowed")
    b_fast = types.InlineKeyboardButton("⚡ Nightcore", callback_data="eff_sped_up")
    b_bass = types.InlineKeyboardButton("💣 Extreme Bass Boost", callback_data="eff_bass_boost")
    b_vocal_ai = types.InlineKeyboardButton("🤖 AI Vocal Remover", callback_data="eff_vocal_ai")
    b_vocal_dsp = types.InlineKeyboardButton("⚡ Fast Karaoke (DSP)", callback_data="eff_vocal_dsp")
    
    # Video Studio entry buttons
    has_custom = bool(session.get("custom_photo_path") and os.path.exists(str(session.get("custom_photo_path"))))
    b_vid_studio = types.InlineKeyboardButton("🎬 Open Video Studio (Wallpaper & Waveform) 🌟", callback_data="menu_video_studio")
    b_custom_photo = types.InlineKeyboardButton(
        "🖼️ Custom Wallpaper: ✅ Active" if has_custom else "🖼️ Set Custom Wallpaper (Photo)",
        callback_data="prompt_custom_photo"
    )
    
    kb.add(b_8d, b_8d_bass)
    kb.add(b_16d, b_slow)
    kb.add(b_fast, b_bass)
    kb.add(b_vocal_ai, b_vocal_dsp)
    kb.add(b_vid_studio)
    kb.add(b_custom_photo)
    return kb

def get_video_studio_keyboard(session: dict):
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    current_style = session.get("selected_style", "style1_smooth_wave")
    style_name = core.VISUALIZER_STYLES.get(current_style, {}).get("name", "〰️ Smooth Wave")
    has_custom = bool(session.get("custom_photo_path") and os.path.exists(str(session.get("custom_photo_path"))))
    has_converted = bool(session.get("processed_audio_path") and os.path.exists(str(session.get("processed_audio_path"))))
    
    # 1. As-Is Render (Instant, preserves whatever audio is loaded)
    if has_converted:
        kb.add(types.InlineKeyboardButton("🎬 Render Video (Using Converted Audio As-Is)", callback_data="render_vid_asis"))
    else:
        kb.add(types.InlineKeyboardButton("🎬 Render Video (Original Audio As-Is)", callback_data="render_vid_asis"))
        
    # 2. 8D Spatial DSP Renders
    kb.add(types.InlineKeyboardButton("🎧 Render Video (with 8D Spatial Audio)", callback_data="render_vid_8d"))
    kb.add(types.InlineKeyboardButton("🔥 Render Video (with 8D + Beat Boosted)", callback_data="render_vid_8d_bass"))
    
    # 3. Customization Buttons
    wall_btn = "🖼️ Change Wallpaper Photo (Active: ✅)" if has_custom else "🖼️ Upload Wallpaper Photo"
    kb.add(types.InlineKeyboardButton(wall_btn, callback_data="prompt_custom_photo"))
    kb.add(types.InlineKeyboardButton(f"🎨 Waveform: {style_name}", callback_data="menu_styles"))
    kb.add(types.InlineKeyboardButton("⬅️ Back to Audio Effects Menu", callback_data="back_main"))
    return kb

def render_video_studio_text(session: dict):
    has_custom = bool(session.get("custom_photo_path") and os.path.exists(str(session.get("custom_photo_path"))))
    has_converted = bool(session.get("processed_audio_path") and os.path.exists(str(session.get("processed_audio_path"))))
    has_cover = bool(session.get("cover_art_path") and os.path.exists(str(session.get("cover_art_path"))))
    
    if has_custom:
        bg_status = "🖼️ Custom Photo Active ✅"
    elif has_cover:
        bg_status = "🎵 Embedded Album Cover"
    else:
        bg_status = "🌌 Default Background (Send photo to customize)"
        
    audio_type = "✨ Converted Audio" if has_converted else "🎵 Original Track"
    current_style = session.get("selected_style", "style1_smooth_wave")
    style_name = core.VISUALIZER_STYLES.get(current_style, {}).get("name", "〰️ Smooth Wave")
    song_name = session.get("last_song_name", "Audio Track")
    
    return (
        f"🎬 *8D Video Studio — Setup & Render*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 *Track:* `{song_name}`\n"
        f"🔊 *Audio:* `{audio_type}`\n"
        f"🖼️ *Wallpaper:* `{bg_status}`\n"
        f"🎨 *Waveform:* `{style_name}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 *Tip:* Video me apni photo lagane ke liye chat me photo bhej sakte ho.\n"
        f"👇 *Choose how to render your 1080p Video:*"
    )

def get_style_selection_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, v in core.VISUALIZER_STYLES.items():
        kb.add(types.InlineKeyboardButton(f"{v['name']} ({v['desc']})", callback_data=f"set_style_{k}"))
    kb.add(types.InlineKeyboardButton("⬅️ Back to Video Studio", callback_data="menu_video_studio"))
    return kb

def render_progress_card(title: str, percentage: float, stage: str = "", detail: str = ""):
    length = 10
    pct = max(0.0, min(100.0, percentage))
    filled = int(round(length * pct / 100))
    bar = "▰" * filled + "▱" * (length - filled)
    
    lines = [
        f"⚡ *{title}*",
        f"`[{bar}]` *{pct:.1f}%*"
    ]
    if stage:
        lines.append(f"📊 *Stage:* `{stage}`")
    if detail:
        lines.append(f"ℹ️ *Status:* `{detail}`")
    return "\n".join(lines)

def register_handlers(bot: TeleBot):

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        user_id = message.from_user.id
        uname = message.from_user.username
        fname = message.from_user.first_name
        db.register_user(user_id, uname, fname)
        
        welcome_text = (
            f"🎧 *Welcome to AZ 8D Audio & Video Studio, {fname}!* 🚀\n\n"
            f"Transform any standard music track or video into an immersive **320 kbps 8D Spatial Audio** experience, "
            f"isolate instrumentals with **AI Vocal Remover**, and generate **1080p Full HD Visualizer Videos**!\n\n"
            f"✨ *Key Capabilities:*\n"
            f"• **🎬 Video ➡️ 320 kbps Audio**: Send any video/reel to extract crystal-clear MP3 + cover art.\n"
            f"• **🎤 Vocal Remover / Karaoke**: Meta Demucs AI & Fast DSP to strip vocals from any song.\n"
            f"• **8D & 16D Binaural Audio**: Full 360° orbital sound with Linkwitz-Riley sub-bass anchor.\n"
            f"• **Beat Boosted 8D**: +7dB sub-bass punch combined with spatial panning.\n"
            f"• **Slowed + Reverb & Nightcore**: Atmospheric reverb and pitch manipulation.\n"
            f"• **1080p Video Studio**: 5 live frequency wave styles with custom wallpaper support.\n"
            f"• **As-Is Video Rendering**: Convert any pre-converted audio directly to video.\n\n"
            f"📤 *Simply send any Song (MP3/WAV), Video (MP4/MKV), or Wallpaper Photo to begin!*"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

    @bot.message_handler(commands=['help'])
    def handle_help(message):
        help_text = (
            f"📖 *How to use AZ 8D Studio Bot:*\n\n"
            f"1. **Audio Effects**: Send any audio track and pick 8D, 16D, Slowed, Nightcore, or Bass Boost.\n"
            f"2. **Video to Audio**: Send any video/reel to extract 320 kbps MP3 + cover art instantly.\n"
            f"3. **Vocal Remover**: Remove vocals with AI (Demucs) or Fast DSP for instant karaoke.\n"
            f"4. **Instant Video**: Click *'🎬 Open Video Studio'* to preview background and render 1080p video.\n"
            f"5. **As-Is Video**: Render any favorite or pre-converted song without re-applying 8D.\n"
            f"6. **Custom Wallpaper**: Send any photo (before or after sending your song) to set as the video background.\n"
            f"7. **Visualizer Styles**: Choose between 5 live audio frequency wave styles.\n\n"
            f"🎧 *Always use headphones for the 360° binaural experience!*"
        )
        bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

    @bot.message_handler(commands=['stats'])
    def handle_stats(message):
        stats = db.get_stats()
        text = (
            f"📊 *Bot Statistics:*\n\n"
            f"👥 *Total Users:* `{stats['total_users']}`\n"
            f"🎧 *Audio Conversions:* `{stats['total_audio']}`\n"
            f"🎬 *Video Conversions:* `{stats['total_video']}`\n"
            f"⚡ *Total Renders:* `{stats['total_conversions']}`"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    def process_and_save_photo(user_id, chat_id, file_id, reply_to_msg_id=None):
        session = db.get_session(user_id) or {}
        user_temp_dir = config.TEMP_DIR / str(user_id)
        user_temp_dir.mkdir(exist_ok=True, parents=True)
        custom_photo_path = str(user_temp_dir / "custom_background.jpg")

        status_msg = bot.send_message(chat_id, "🖼️ *Downloading and applying your custom wallpaper...*",
                                      reply_to_message_id=reply_to_msg_id, parse_mode="Markdown")
        try:
            file_info = bot.get_file(file_id)
            downloaded = bot.download_file(file_info.file_path)
            with open(custom_photo_path, 'wb') as f:
                f.write(downloaded)

            db.save_session(user_id, custom_photo_path=custom_photo_path)
            session["custom_photo_path"] = custom_photo_path

            # If no song is loaded yet, instruct user to send the song!
            if not session.get("raw_audio_path"):
                bot.edit_message_text(
                    "✅ *Custom Wallpaper Saved!*\n\n"
                    "👉 Ab aap apna **Song / Audio file** send karein.\n"
                    "Aapki video automatically is wallpaper photo ke saath create hogi!",
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id,
                    parse_mode="Markdown"
                )
                return

            # If song is active, open Video Studio menu directly!
            song_title = session.get('last_song_name', 'Song')
            kb = get_video_studio_keyboard(session)
            bot.edit_message_text(
                f"✅ *Custom Photo Saved & Applied to `{song_title}`!*\n\n"
                f"{render_video_studio_text(session)}",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            logger.error(f"Photo save error: {e}")
            bot.edit_message_text(f"❌ Failed to save photo: {e}", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

    def process_and_extract_video(user_id, chat_id, file_obj, reply_to_msg_id=None):
        if is_user_busy(user_id):
            bot.send_message(chat_id, "⚠️ You already have an active task in progress. Please wait a few moments!", reply_to_message_id=reply_to_msg_id)
            return

        file_size_mb = (getattr(file_obj, 'file_size', 0) or 0) / (1024 * 1024)
        if file_size_mb > config.MAX_AUDIO_SIZE_MB:
            bot.send_message(chat_id, f"❌ Video file too large! Maximum supported size is {config.MAX_AUDIO_SIZE_MB}MB.", reply_to_message_id=reply_to_msg_id)
            return

        status_msg = bot.send_message(chat_id, "📥 *Downloading video for 320 kbps studio audio extraction...*", reply_to_message_id=reply_to_msg_id, parse_mode="Markdown")

        def download_and_extract():
            try:
                set_user_busy(user_id, True)
                user_temp_dir = config.TEMP_DIR / str(user_id)
                user_temp_dir.mkdir(exist_ok=True, parents=True)

                raw_video_path = str(user_temp_dir / f"input_video_{int(time.time())}.mp4")
                file_info = bot.get_file(file_obj.file_id)
                downloaded = bot.download_file(file_info.file_path)
                with open(raw_video_path, 'wb') as f:
                    f.write(downloaded)

                def update_extract_progress(pct, detail):
                    try:
                        card = render_progress_card("Extracting Studio Audio", pct, stage="Audio Extraction", detail=detail)
                        bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                    except Exception:
                        pass

                extracted_mp3 = str(user_temp_dir / f"extracted_audio_{int(time.time())}.mp3")
                extracted_cover = str(user_temp_dir / "cover.jpg")

                meta = core.extract_audio_from_video(
                    raw_video_path,
                    extracted_mp3,
                    out_cover_path=extracted_cover,
                    progress_callback=update_extract_progress
                )

                existing_session = db.get_session(user_id) or {}
                keep_photo = existing_session.get("custom_photo_path")
                if keep_photo and not os.path.exists(keep_photo):
                    keep_photo = None

                # Video cover art can also serve as wallpaper if user hasn't set one
                if not keep_photo and meta.get("has_cover") and os.path.exists(extracted_cover):
                    keep_photo = extracted_cover

                db.save_session(
                    user_id=user_id,
                    last_song_name=meta.get("title") or "Video Audio Track",
                    raw_audio_path=extracted_mp3,
                    processed_audio_path=None,
                    cover_art_path=extracted_cover if meta.get("has_cover") else None,
                    custom_photo_path=keep_photo
                )

                session = db.get_session(user_id) or {}
                dur_str = time.strftime('%M:%S', time.gmtime(meta['duration'])) if meta.get('duration') else "Unknown"

                try:
                    bot.delete_message(status_msg.chat.id, status_msg.message_id)
                except Exception:
                    pass

                caption = (
                    f"🎬 *Video ➡️ 320 kbps Studio Audio Extracted!* 🎧\n\n"
                    f"🎵 *Track:* `{meta.get('title', 'Video Track')}`\n"
                    f"⏱️ *Duration:* `{dur_str}`\n"
                    f"🖼️ *Cover:* `Video Frame Captured ✅`\n\n"
                    f"👇 *Aap is audio ko 8D/16D bana sakte ho, vocals remove kar sakte ho, ya Video Studio open kar sakte ho:*"
                )

                uploader.send_audio_smart(
                    bot=bot,
                    chat_id=chat_id,
                    file_path=extracted_mp3,
                    title=meta.get("title", "Video Track"),
                    performer="AZ Studio (Video Extracted)",
                    caption=caption,
                    reply_markup=get_effect_keyboard(session)
                )
            except Exception as e:
                logger.error(f"Video extract error: {e}", exc_info=True)
                bot.send_message(chat_id, f"❌ Failed to extract audio from video: {e}")
            finally:
                set_user_busy(user_id, False)

        threading.Thread(target=download_and_extract, daemon=True).start()

    @bot.message_handler(content_types=['video', 'video_note'])
    def handle_video_upload(message):
        user_id = message.from_user.id
        logger.info(f"Received video upload from user {user_id}")
        db.register_user(user_id, message.from_user.username, message.from_user.first_name)
        video_obj = message.video or message.video_note
        if video_obj:
            process_and_extract_video(user_id, message.chat.id, video_obj, message.message_id)

    @bot.message_handler(content_types=['audio', 'document'])
    def handle_audio_upload(message):
        user_id = message.from_user.id
        logger.info(f"Received audio/document upload from user {user_id}")
        db.register_user(user_id, message.from_user.username, message.from_user.first_name)
        
        if is_user_busy(user_id):
            bot.reply_to(message, "⚠️ You already have an active task in progress. Please wait a few moments!")
            return

        file_obj = message.audio or message.document
        if not file_obj:
            return

        file_name = (getattr(file_obj, 'file_name', None) or "").lower()
        mime_type = (getattr(file_obj, 'mime_type', None) or "").lower()

        # If user sent an image as document/file, route it to photo wallpaper handler!
        if mime_type.startswith("image/") or any(file_name.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
            process_and_save_photo(user_id, message.chat.id, file_obj.file_id, message.message_id)
            return

        # If user sent a video as document/file, route it to video extractor!
        if mime_type.startswith("video/") or any(file_name.endswith(ext) for ext in ('.mp4', '.mkv', '.mov', '.webm', '.avi', '.flv', '.m4v')):
            process_and_extract_video(user_id, message.chat.id, file_obj, message.message_id)
            return

        if not file_name:
            file_name = f"audio_{int(time.time())}.mp3"
        file_size_mb = file_obj.file_size / (1024 * 1024)
        
        if file_size_mb > config.MAX_AUDIO_SIZE_MB:
            bot.reply_to(message, f"❌ File too large! Maximum supported size is {config.MAX_AUDIO_SIZE_MB}MB.")
            return

        status_msg = bot.reply_to(message, "📥 *Downloading audio file...*", parse_mode="Markdown")

        def download_and_init():
            try:
                set_user_busy(user_id, True)
                user_temp_dir = config.TEMP_DIR / str(user_id)
                user_temp_dir.mkdir(exist_ok=True, parents=True)
                
                raw_path = str(user_temp_dir / f"input_{file_name}")
                file_info = bot.get_file(file_obj.file_id)
                downloaded = bot.download_file(file_info.file_path)
                with open(raw_path, 'wb') as f:
                    f.write(downloaded)

                cover_path = str(user_temp_dir / "cover.jpg")
                meta = core.extract_metadata_and_cover(raw_path, cover_path)
                
                # Preserve existing custom photo if user sent wallpaper before song!
                existing_session = db.get_session(user_id) or {}
                keep_photo = existing_session.get("custom_photo_path")
                if keep_photo and not os.path.exists(keep_photo):
                    keep_photo = None

                db.save_session(
                    user_id=user_id,
                    last_song_name=meta["title"],
                    raw_audio_path=raw_path,
                    processed_audio_path=None,
                    cover_art_path=cover_path if meta["has_cover"] else None,
                    custom_photo_path=keep_photo
                )
                
                session = db.get_session(user_id) or {}
                dur_str = time.strftime('%M:%S', time.gmtime(meta['duration'])) if meta['duration'] else "Unknown"
                
                if keep_photo:
                    wall_status = "🖼️ Custom Photo Active ✅"
                elif meta["has_cover"]:
                    wall_status = "🎵 Embedded Cover Art Found"
                else:
                    wall_status = "🌌 Default Background"

                caption = (
                    f"🎵 *Track Detected:* `{meta['title']}`\n"
                    f"👤 *Artist:* `{meta['artist']}`\n"
                    f"⏱️ *Duration:* `{dur_str}`\n"
                    f"🖼️ *Wallpaper:* `{wall_status}`\n\n"
                    f"💡 *Custom Photo:* Video me apni photo lagane ke liye chat me direct photo send karein!\n\n"
                    f"👇 *Choose an Audio Effect or Open Video Studio:*"
                )
                
                kb = get_effect_keyboard(session)
                bot.edit_message_text(caption, chat_id=status_msg.chat.id, message_id=status_msg.message_id,
                                      parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                logger.error(f"Error handling audio: {e}", exc_info=True)
                bot.edit_message_text(f"❌ Failed to process audio: {e}", chat_id=status_msg.chat.id,
                                      message_id=status_msg.message_id)
            finally:
                set_user_busy(user_id, False)

        threading.Thread(target=download_and_init, daemon=True).start()

    @bot.message_handler(content_types=['photo'])
    def handle_photo_upload(message):
        user_id = message.from_user.id
        photo = message.photo[-1]
        process_and_save_photo(user_id, message.chat.id, photo.file_id, message.message_id)

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callbacks(call):
        user_id = call.from_user.id
        # Immediately acknowledge callback query so Telegram UI removes the button loading spinner instantly!
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        session = db.get_session(user_id)
        
        if not session or not session.get("raw_audio_path"):
            bot.send_message(call.message.chat.id, "⚠️ Session expired or no song found. Please send the song again!")
            return

        data = call.data
        logger.info(f"Received callback '{data}' from user {user_id}")

        # Video Studio Menu
        if data == "menu_video_studio":
            bot.answer_callback_query(call.id)
            kb = get_video_studio_keyboard(session)
            bot.edit_message_text(
                render_video_studio_text(session),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=kb
            )
            return

        # Visualizer Wave Styles Menu
        if data == "menu_styles":
            bot.edit_message_text(
                "🎨 *Select Visualizer Waveform Style:*\n\nChoose how you want the live audio frequency wave to look on the video base:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_style_selection_keyboard()
            )
            return

        # Style Selection
        if data.startswith("set_style_"):
            style_key = data.replace("set_style_", "")
            db.save_session(user_id, selected_style=style_key)
            session["selected_style"] = style_key
            style_info = core.VISUALIZER_STYLES.get(style_key, {})
            style_name = style_info.get("name", style_key)
            bot.answer_callback_query(call.id, f"✅ Selected: {style_name}")
            
            # Return directly to Video Studio menu
            bot.edit_message_text(
                render_video_studio_text(session),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_video_studio_keyboard(session)
            )
            return

        # Return to Main Audio Menu
        if data == "back_main":
            song_title = session.get('last_song_name', 'Song')
            bot.edit_message_text(
                f"🎵 *Track:* `{song_title}`\n\n👇 *Choose an Audio Effect or Open Video Studio:*",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_effect_keyboard(session)
            )
            return

        # Wallpaper Upload Guidance
        if data == "prompt_custom_photo":
            bot.answer_callback_query(call.id)
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Back to Video Studio", callback_data="menu_video_studio"))
            bot.send_message(
                call.message.chat.id,
                "🖼️ *How to Set Custom Wallpaper for Video:*\n\n"
                "1️⃣ Bas chat me direct koi bhi **Photo** send kar do (ya document/file format me photo bhejo).\n"
                "2️⃣ Bot us photo ko download karke 1080p video background me automatically set kar dega.\n"
                "3️⃣ Uske baad aap Video Studio me instant render button daba sakte ho!\n\n"
                "📸 *Abhi chat me koi bhi photo send karein!*",
                parse_mode="Markdown",
                reply_markup=kb
            )
            return

        # Audio Effects Processing
        if data.startswith("eff_"):
            effect_name = data.replace("eff_", "")
            if is_user_busy(user_id):
                bot.send_message(call.message.chat.id, "⚠️ A task is already processing! Please wait a moment.")
                return

            def run_audio_process():
                start_time = time.time()
                try:
                    set_user_busy(user_id, True)
                    logger.info(f"User {user_id} started audio process: {effect_name}")

                    if effect_name == "vocal_ai":
                        engine_title = "AI Vocal Separation (Meta Demucs)"
                    elif effect_name == "vocal_dsp":
                        engine_title = "Fast Karaoke Isolation (DSP)"
                    else:
                        engine_title = f"Applying {effect_name.upper()} Spatial DSP"

                    initial_card = render_progress_card(
                        engine_title,
                        10.0,
                        stage="1/1",
                        detail="Initializing engine..."
                    )
                    status_msg = bot.send_message(
                        call.message.chat.id,
                        initial_card,
                        parse_mode="Markdown"
                    )

                    user_out_dir = config.OUTPUT_DIR / str(user_id)
                    user_out_dir.mkdir(exist_ok=True, parents=True)
                    song_clean = "".join(c for c in session.get("last_song_name", "audio") if c.isalnum() or c in (' ', '_', '-')).strip()
                    out_mp3 = str(user_out_dir / f"{song_clean}_{effect_name}.mp3")

                    def update_audio_progress(pct, detail):
                        try:
                            card = render_progress_card(
                                engine_title,
                                pct,
                                stage="1/1",
                                detail=detail
                            )
                            bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                        except Exception:
                            pass

                    core.process_audio_effect(
                        session["raw_audio_path"],
                        out_mp3,
                        effect=effect_name,
                        progress_callback=update_audio_progress
                    )
                    
                    db.log_conversion(user_id, "audio", effect_name)

                    upload_card = render_progress_card(
                        "Uploading Mastered Audio",
                        99.0,
                        stage="Finalizing",
                        detail="Uploading 320kbps MP3 to Telegram..."
                    )
                    try:
                        bot.edit_message_text(upload_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                    except:
                        pass

                    if effect_name in ("vocal_ai", "vocal_dsp"):
                        inst_title = f"{song_clean} (Instrumental)"
                        # Update session raw audio so subsequent 8D or Video Studio acts on the instrumental!
                        db.save_session(user_id, processed_audio_path=out_mp3, raw_audio_path=out_mp3, last_song_name=inst_title)
                        session["processed_audio_path"] = out_mp3
                        session["raw_audio_path"] = out_mp3
                        session["last_song_name"] = inst_title

                        kb_after = types.InlineKeyboardMarkup(row_width=1)
                        kb_after.add(types.InlineKeyboardButton("🎧 Convert Instrumental to 8D Audio", callback_data="eff_8d"))
                        kb_after.add(types.InlineKeyboardButton("🔥 Convert to 8D + Beat Boost", callback_data="eff_8d_bass"))
                        kb_after.add(types.InlineKeyboardButton("🎬 Open Video Studio (Visualizer Video)", callback_data="menu_video_studio"))
                        kb_after.add(types.InlineKeyboardButton("⬅️ Back to Audio Menu", callback_data="back_main"))

                        uploader.send_audio_smart(
                            bot=bot,
                            chat_id=call.message.chat.id,
                            file_path=out_mp3,
                            title=inst_title,
                            performer="AZ Vocal Remover",
                            caption=(
                                f"🎤❌ *Vocals Removed Successfully!* 🎶\n\n"
                                f"• Mode: `{'🤖 Meta Demucs AI Neural Network' if effect_name == 'vocal_ai' else '⚡ Fast Karaoke (DSP)'}`\n"
                                f"• Bitrate: `320 kbps Studio Quality`\n"
                                f"• Mastering: `-14 LUFS Loudness Normalized`\n\n"
                                f"👇 *Is instrumental ko 8D me convert karein ya Video Studio open karein:*"
                            ),
                            reply_markup=kb_after
                        )
                    else:
                        db.save_session(user_id, processed_audio_path=out_mp3)
                        session["processed_audio_path"] = out_mp3

                        kb_after = types.InlineKeyboardMarkup(row_width=1)
                        kb_after.add(types.InlineKeyboardButton("🎬 Open Video Studio for this Audio", callback_data="menu_video_studio"))
                        kb_after.add(types.InlineKeyboardButton("🖼️ Add Wallpaper & Render Video", callback_data="prompt_custom_photo"))
                        kb_after.add(types.InlineKeyboardButton("⬅️ Back to Audio Menu", callback_data="back_main"))

                        uploader.send_audio_smart(
                            bot=bot,
                            chat_id=call.message.chat.id,
                            file_path=out_mp3,
                            title=f"{song_clean} ({effect_name.upper()})",
                            performer="AZ 8D Studio",
                            caption=f"✨ *{effect_name.upper()} Audio Ready!* 🎧\n• Mastered at: 320 kbps (-14 LUFS)\n• Use headphones for 360° spatial effect!",
                            reply_markup=kb_after
                        )
                    try:
                        bot.delete_message(status_msg.chat.id, status_msg.message_id)
                    except Exception:
                        pass
                    logger.info(f"User {user_id} finished audio process {effect_name} in {time.time() - start_time:.2f}s")
                except Exception as e:
                    logger.error(f"Audio process error: {e}", exc_info=True)
                    bot.send_message(call.message.chat.id, f"❌ Failed to process audio: {e}")
                finally:
                    set_user_busy(user_id, False)

            threading.Thread(target=run_audio_process, daemon=True).start()
            return

        # Video Rendering Workflows (As-Is, 8D Spatial, 8D Bass Boosted)
        if data in ("make_video", "render_vid_asis", "render_vid_8d", "render_vid_8d_bass"):
            if is_user_busy(user_id):
                bot.send_message(call.message.chat.id, "⚠️ A task is already processing! Please wait a moment.")
                return

            def run_video_process():
                try:
                    set_user_busy(user_id, True)
                    bot.answer_callback_query(call.id, "Rendering Video...")
                    
                    user_out_dir = config.OUTPUT_DIR / str(user_id)
                    user_out_dir.mkdir(exist_ok=True, parents=True)
                    song_clean = "".join(c for c in session.get("last_song_name", "audio") if c.isalnum() or c in (' ', '_', '-')).strip()

                    status_msg = None

                    # Flow 1: As-Is Audio Rendering (Instant, no re-encoding)
                    if data == "render_vid_asis":
                        proc_audio = session.get("processed_audio_path")
                        if not proc_audio or not os.path.exists(proc_audio):
                            proc_audio = session["raw_audio_path"]
                        video_suffix = "Video"
                        video_title = f"{song_clean} (Visualizer Video)"

                    # Flow 2: 8D + Beat Boosted Video
                    elif data == "render_vid_8d_bass":
                        proc_audio = str(user_out_dir / f"{song_clean}_8d_bass.mp3")
                        if not os.path.exists(proc_audio):
                            initial_card = render_progress_card("Generating 8D + Beat Boosted First", 10.0, stage="1/2", detail="Applying bass punch...")
                            status_msg = bot.send_message(call.message.chat.id, initial_card, parse_mode="Markdown")
                            def update_pre_audio(pct, detail):
                                try:
                                    card = render_progress_card("Generating 8D + Beat Boosted First", pct, stage="1/2", detail=detail)
                                    bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                                except:
                                    pass
                            core.process_audio_effect(session["raw_audio_path"], proc_audio, effect="8d_bass", progress_callback=update_pre_audio)
                            db.save_session(user_id, processed_audio_path=proc_audio)
                            session["processed_audio_path"] = proc_audio
                        video_suffix = "8D_Bass_Video"
                        video_title = f"{song_clean} (8D + Beat Boosted Video)"

                    # Flow 3: 8D Spatial Audio Video (or default make_video)
                    else:
                        proc_audio = session.get("processed_audio_path")
                        if not proc_audio or not os.path.exists(proc_audio) or "_8d" not in os.path.basename(proc_audio):
                            initial_card = render_progress_card("Generating 8D Audio First", 10.0, stage="1/2", detail="Applying 360° binaural pan...")
                            status_msg = bot.send_message(call.message.chat.id, initial_card, parse_mode="Markdown")
                            def update_pre_audio(pct, detail):
                                try:
                                    card = render_progress_card("Generating 8D Audio First", pct, stage="1/2", detail=detail)
                                    bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                                except:
                                    pass
                            proc_audio = str(user_out_dir / f"{song_clean}_8d.mp3")
                            core.process_audio_effect(session["raw_audio_path"], proc_audio, effect="8d", progress_callback=update_pre_audio)
                            db.save_session(user_id, processed_audio_path=proc_audio)
                            session["processed_audio_path"] = proc_audio
                        video_suffix = "8D_Video"
                        video_title = f"{song_clean} (8D Audio + Visualizer)"

                    # Video Render Stage
                    initial_video_card = render_progress_card(
                        "Rendering 1080p Video",
                        10.0,
                        stage="Visualizer Engine",
                        detail="Initializing FFmpeg hardware encoder..."
                    )
                    if status_msg:
                        try:
                            bot.edit_message_text(initial_video_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                        except:
                            status_msg = bot.send_message(call.message.chat.id, initial_video_card, parse_mode="Markdown")
                    else:
                        status_msg = bot.send_message(call.message.chat.id, initial_video_card, parse_mode="Markdown")

                    bg_image = session.get("custom_photo_path") or session.get("cover_art_path")
                    if not bg_image or not os.path.exists(bg_image):
                        bg_image = str(config.ASSETS_DIR / "default_art.jpg")

                    style_key = session.get("selected_style", "style1_smooth_wave")
                    style_info = core.VISUALIZER_STYLES.get(style_key, core.VISUALIZER_STYLES["style1_smooth_wave"])
                    
                    meta = core.extract_metadata_and_cover(proc_audio, str(config.TEMP_DIR / "temp_cov.jpg"))
                    total_dur = meta.get("duration", 0.0)

                    def update_video_progress(pct, detail):
                        try:
                            card = render_progress_card(
                                f"Rendering: {style_info['name']}",
                                pct,
                                stage="Video Encoding",
                                detail=detail
                            )
                            bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                        except Exception:
                            pass

                    out_video = str(user_out_dir / f"{song_clean}_{video_suffix}.mp4")
                    core.render_visualizer_video(
                        proc_audio,
                        bg_image,
                        out_video,
                        style_key=style_key,
                        total_duration=total_dur,
                        progress_callback=update_video_progress
                    )
                    
                    db.log_conversion(user_id, "video", data, visualizer_style=style_key)

                    def update_upload_progress(pct, detail):
                        try:
                            card = render_progress_card(
                                f"Uploading 1080p Video ({detail})",
                                pct,
                                stage="Finalizing",
                                detail="Uploading via High-Speed MTProto Engine..."
                            )
                            bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                        except Exception:
                            pass

                    uploader.send_video_smart(
                        bot=bot,
                        chat_id=call.message.chat.id,
                        file_path=out_video,
                        caption=f"🎬 *{video_title}*\n\n• Visualizer: `{style_info['name']}`\n• Resolution: 1080p Full HD\n• 🎧 *Wear Headphones for 360° Movement!*",
                        supports_streaming=True,
                        progress_callback=update_upload_progress
                    )
                    try:
                        bot.delete_message(status_msg.chat.id, status_msg.message_id)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Video process error: {e}", exc_info=True)
                    bot.send_message(call.message.chat.id, f"❌ Video rendering failed: {e}")
                finally:
                    set_user_busy(user_id, False)

            threading.Thread(target=run_video_process, daemon=True).start()
            return
