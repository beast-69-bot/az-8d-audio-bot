"""
Telegram Bot Message and Callback Handlers for AZ 8D Audio Bot.
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

def get_effect_keyboard(session: dict):
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_8d = types.InlineKeyboardButton("🎧 8D Audio", callback_data="eff_8d")
    b_8d_bass = types.InlineKeyboardButton("🔥 8D + Beat Boosted", callback_data="eff_8d_bass")
    b_vid = types.InlineKeyboardButton("🎬 8D Video (MP4)", callback_data="make_video")
    b_16d = types.InlineKeyboardButton("🌀 16D Audio", callback_data="eff_16d")
    b_slow = types.InlineKeyboardButton("🌌 Slowed + Reverb", callback_data="eff_slowed")
    b_fast = types.InlineKeyboardButton("⚡ Sped Up / Nightcore", callback_data="eff_sped_up")
    b_bass = types.InlineKeyboardButton("💣 Extreme Bass Boost", callback_data="eff_bass_boost")
    
    current_style = session.get("selected_style", "style1_smooth_wave")
    style_name = core.VISUALIZER_STYLES.get(current_style, {}).get("name", "〰️ Smooth Wave")
    b_style = types.InlineKeyboardButton(f"🎨 Visualizer: {style_name}", callback_data="menu_styles")
    
    kb.add(b_8d, b_8d_bass)
    kb.add(b_vid, b_16d)
    kb.add(b_slow, b_fast)
    kb.add(b_bass)
    kb.add(b_style)
    return kb

def get_style_selection_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, v in core.VISUALIZER_STYLES.items():
        kb.add(types.InlineKeyboardButton(f"{v['name']} ({v['desc']})", callback_data=f"set_style_{k}"))
    kb.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_main"))
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
            f"👋 *Welcome {fname} to AZ 8D Spatial Audio Studio!* 🎧✨\n\n"
            f"I can convert any song into high-end **8D Spatial Audio** and render **Full HD Audio-Reactive Visualizer Videos**.\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✨ *Available Audio Effects:*\n"
            f"• 🎧 *8D Audio* (360° binaural orbit around your head)\n"
            f"• 🔥 *8D + Beat Boosted* (Heavy punchy 808/Kick + 360° orbit)\n"
            f"• 🌀 *16D Audio* (Dual counter-rotating vocals & synths)\n"
            f"• 🌌 *Slowed + Reverb* (Daycore / Chillwave)\n"
            f"• ⚡ *Sped Up / Nightcore* (Dance & high energy)\n"
            f"• 💣 *Extreme Bass Boost* (Sub-bass synthesis)\n"
            f"• 🎬 *1080p Video Visualizers* with 5 live frequency wave styles!\n"
            f"• 🖼️ *Custom Wallpaper/Photo support* for video background\n"
            f"• 🚀 *EBU R128 Mastered 320kbps MP3s*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👉 *Just send me any Audio file or Song (.mp3, .m4a, .wav) to get started!*"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

    @bot.message_handler(commands=['help'])
    def handle_help(message):
        help_text = (
            f"💡 *How to Use AZ 8D Bot:*\n\n"
            f"1. **Send a Song**: Send an MP3, audio or document file.\n"
            f"2. **Choose Audio Effect**: Select *8D Audio*, *16D*, *Slowed+Reverb*, etc.\n"
            f"3. **Make a Video**: Click `[🎬 8D Video]` to render a Full HD visualizer video.\n"
            f"4. **Custom Image**: Want your own photo in the video? Just send a photo after sending your song!\n"
            f"5. **Visualizer Styles**: Choose between 5 different wave & frequency styles.\n\n"
            f"🎧 *Always use headphones/earphones for 360° binaural movement!*"
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

    @bot.message_handler(content_types=['audio', 'document'])
    def handle_audio_upload(message):
        user_id = message.from_user.id
        db.register_user(user_id, message.from_user.username, message.from_user.first_name)
        
        if USER_BUSY.get(user_id):
            bot.reply_to(message, "⚠️ You already have an active task in progress. Please wait a few moments!")
            return

        file_obj = message.audio or message.document
        if not file_obj:
            return

        file_name = getattr(file_obj, 'file_name', None) or f"audio_{int(time.time())}.mp3"
        file_size_mb = file_obj.file_size / (1024 * 1024)
        
        if file_size_mb > config.MAX_AUDIO_SIZE_MB:
            bot.reply_to(message, f"❌ File too large! Maximum supported size is {config.MAX_AUDIO_SIZE_MB}MB.")
            return

        status_msg = bot.reply_to(message, "📥 *Downloading audio file...*", parse_mode="Markdown")

        def download_and_init():
            try:
                USER_BUSY[user_id] = True
                user_temp_dir = config.TEMP_DIR / str(user_id)
                user_temp_dir.mkdir(exist_ok=True, parents=True)
                
                raw_path = str(user_temp_dir / f"input_{file_name}")
                file_info = bot.get_file(file_obj.file_id)
                downloaded = bot.download_file(file_info.file_path)
                with open(raw_path, 'wb') as f:
                    f.write(downloaded)

                cover_path = str(user_temp_dir / "cover.jpg")
                meta = core.extract_metadata_and_cover(raw_path, cover_path)
                
                db.save_session(
                    user_id=user_id,
                    last_song_name=meta["title"],
                    raw_audio_path=raw_path,
                    processed_audio_path=None,
                    cover_art_path=cover_path if meta["has_cover"] else None,
                    custom_photo_path=None
                )
                
                session = db.get_session(user_id) or {}
                dur_str = time.strftime('%M:%S', time.gmtime(meta['duration'])) if meta['duration'] else "Unknown"
                
                caption = (
                    f"🎵 *Track Detected:* `{meta['title']}`\n"
                    f"👤 *Artist:* `{meta['artist']}`\n"
                    f"⏱️ *Duration:* `{dur_str}`\n"
                    f"🖼️ *Cover Art:* {'✅ Embedded Cover Found' if meta['has_cover'] else 'ℹ️ Default Background'}\n\n"
                    f"👇 *Choose an Audio Effect or Generate Video:*"
                )
                
                kb = get_effect_keyboard(session)
                bot.edit_message_text(caption, chat_id=status_msg.chat.id, message_id=status_msg.message_id,
                                      parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                logger.error(f"Error handling audio: {e}", exc_info=True)
                bot.edit_message_text(f"❌ Failed to process audio: {e}", chat_id=status_msg.chat.id,
                                      message_id=status_msg.message_id)
            finally:
                USER_BUSY[user_id] = False

        threading.Thread(target=download_and_init, daemon=True).start()

    @bot.message_handler(content_types=['photo'])
    def handle_photo_upload(message):
        user_id = message.from_user.id
        session = db.get_session(user_id)
        if not session or not session.get("raw_audio_path"):
            bot.reply_to(message, "ℹ️ Please send a **Song/Audio file first**, then send your custom wallpaper photo for the video background!")
            return

        status_msg = bot.reply_to(message, "🖼️ *Downloading your custom wallpaper...*", parse_mode="Markdown")
        try:
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            downloaded = bot.download_file(file_info.file_path)
            
            user_temp_dir = config.TEMP_DIR / str(user_id)
            user_temp_dir.mkdir(exist_ok=True, parents=True)
            custom_photo_path = str(user_temp_dir / "custom_background.jpg")
            with open(custom_photo_path, 'wb') as f:
                f.write(downloaded)

            db.save_session(user_id, custom_photo_path=custom_photo_path)
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🎬 Render 8D Video with this Photo", callback_data="make_video"))
            kb.add(types.InlineKeyboardButton("🎨 Change Visualizer Style", callback_data="menu_styles"))
            
            bot.edit_message_text(
                "✅ *Custom Photo Saved!*\n\nThis image will now be used as the background for your video. Click below to render:",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            logger.error(f"Photo save error: {e}")
            bot.edit_message_text(f"❌ Failed to save photo: {e}", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callbacks(call):
        user_id = call.from_user.id
        session = db.get_session(user_id)
        
        if not session or not session.get("raw_audio_path"):
            bot.answer_callback_query(call.id, "Session expired or no song found. Please send the song again!", show_alert=True)
            return

        data = call.data

        if data == "menu_styles":
            bot.edit_message_text(
                "🎨 *Select Visualizer Waveform Style:*\n\nChoose how you want the live audio frequency wave to look on the video base:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_style_selection_keyboard()
            )
            return

        if data.startswith("set_style_"):
            style_key = data.replace("set_style_", "")
            db.save_session(user_id, selected_style=style_key)
            session["selected_style"] = style_key
            style_name = core.VISUALIZER_STYLES.get(style_key, {}).get("name", style_key)
            bot.answer_callback_query(call.id, f"✅ Selected: {style_name}")
            
            caption = (
                f"🎵 *Track:* `{session.get('last_song_name', 'Song')}`\n"
                f"🎨 *Current Visualizer:* `{style_name}`\n\n"
                f"👇 *Choose an option:*"
            )
            bot.edit_message_text(
                caption,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_effect_keyboard(session)
            )
            return

        if data == "back_main":
            bot.edit_message_text(
                f"🎵 *Track:* `{session.get('last_song_name', 'Song')}`\n\n👇 *Choose an Audio Effect or Video:*",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_effect_keyboard(session)
            )
            return

        if data.startswith("eff_"):
            effect_name = data.replace("eff_", "")
            if USER_BUSY.get(user_id):
                bot.answer_callback_query(call.id, "A task is already processing!", show_alert=True)
                return

            def run_audio_process():
                try:
                    USER_BUSY[user_id] = True
                    bot.answer_callback_query(call.id, f"Applying {effect_name.upper()} processing...")
                    
                    initial_card = render_progress_card(
                        f"Applying {effect_name.upper()} Spatial DSP",
                        10.0,
                        stage="1/1",
                        detail="Initializing spatial engine..."
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
                                f"Applying {effect_name.upper()} Spatial DSP",
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
                    
                    db.save_session(user_id, processed_audio_path=out_mp3)
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
                    
                    kb_after = types.InlineKeyboardMarkup()
                    kb_after.add(types.InlineKeyboardButton("🎬 Make Video of this Song", callback_data="make_video"))

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
                except Exception as e:
                    logger.error(f"Audio process error: {e}", exc_info=True)
                    bot.send_message(call.message.chat.id, f"❌ Failed to process audio: {e}")
                finally:
                    USER_BUSY[user_id] = False

            threading.Thread(target=run_audio_process, daemon=True).start()
            return

        if data == "make_video":
            if USER_BUSY.get(user_id):
                bot.answer_callback_query(call.id, "A task is already processing!", show_alert=True)
                return

            def run_video_process():
                try:
                    USER_BUSY[user_id] = True
                    bot.answer_callback_query(call.id, "Generating 8D Video...")
                    
                    initial_card = render_progress_card(
                        "Preparing 8D Video",
                        10.0,
                        stage="1/2",
                        detail="Checking audio & background..."
                    )
                    status_msg = bot.send_message(
                        call.message.chat.id,
                        initial_card,
                        parse_mode="Markdown"
                    )

                    user_out_dir = config.OUTPUT_DIR / str(user_id)
                    user_out_dir.mkdir(exist_ok=True, parents=True)
                    song_clean = "".join(c for c in session.get("last_song_name", "audio") if c.isalnum() or c in (' ', '_', '-')).strip()

                    proc_audio = session.get("processed_audio_path")
                    if not proc_audio or not os.path.exists(proc_audio):
                        def update_pre_audio(pct, detail):
                            try:
                                card = render_progress_card("Generating 8D Audio First", pct, stage="1/2", detail=detail)
                                bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                            except:
                                pass
                        proc_audio = str(user_out_dir / f"{song_clean}_8d.mp3")
                        core.process_audio_effect(session["raw_audio_path"], proc_audio, effect="8d", progress_callback=update_pre_audio)
                        db.save_session(user_id, processed_audio_path=proc_audio)

                    bg_image = session.get("custom_photo_path") or session.get("cover_art_path")
                    if not bg_image or not os.path.exists(bg_image):
                        bg_image = str(config.ASSETS_DIR / "default_art.jpg")

                    style_key = session.get("selected_style", "style1_smooth_wave")
                    style_info = core.VISUALIZER_STYLES.get(style_key, core.VISUALIZER_STYLES["style1_smooth_wave"])
                    
                    # Extract song duration for live percentage tracking
                    meta = core.extract_metadata_and_cover(proc_audio, str(config.TEMP_DIR / "temp_cov.jpg"))
                    total_dur = meta.get("duration", 0.0)

                    def update_video_progress(pct, detail):
                        try:
                            card = render_progress_card(
                                f"Rendering Visualizer: {style_info['name']}",
                                pct,
                                stage="2/2",
                                detail=detail
                            )
                            bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                        except Exception:
                            pass

                    out_video = str(user_out_dir / f"{song_clean}_8D_Video.mp4")
                    core.render_visualizer_video(
                        proc_audio,
                        bg_image,
                        out_video,
                        style_key=style_key,
                        total_duration=total_dur,
                        progress_callback=update_video_progress
                    )
                    
                    db.log_conversion(user_id, "video", "8d", visualizer_style=style_key)

                    upload_card = render_progress_card(
                        "Uploading Full HD 8D Video",
                        99.0,
                        stage="Finalizing",
                        detail="Uploading MP4 to Telegram..."
                    )
                    try:
                        bot.edit_message_text(upload_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                    except:
                        pass

                    def update_upload_progress(pct, detail):
                        try:
                            card = render_progress_card(
                                f"Uploading 8D Video ({detail})",
                                pct,
                                stage="Finalizing",
                                detail="Uploading via MTProto Engine..."
                            )
                            bot.edit_message_text(card, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                        except Exception:
                            pass

                    uploader.send_video_smart(
                        bot=bot,
                        chat_id=call.message.chat.id,
                        file_path=out_video,
                        caption=f"🎬 *{song_clean} (8D Audio + Visualizer)*\n\n• Visualizer: `{style_info['name']}`\n• Resolution: 1080p Full HD\n• 🎧 *Wear Headphones for 360° Movement!*",
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
                    USER_BUSY[user_id] = False

            threading.Thread(target=run_video_process, daemon=True).start()
            return
