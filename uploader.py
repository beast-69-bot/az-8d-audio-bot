"""
Smart Uploader for AZ 8D Audio & Video Studio Bot.
Handles seamless uploads up to 2GB:
- Automatically uses standard Telegram Bot API for files < 45MB.
- Seamlessly falls back to Telegram MTProto API (via Kurigram / Pyrogram)
  for files >= 45MB or when encountering HTTP 413 Request Entity Too Large.
"""

import os
import logging
import asyncio
from pathlib import Path
import config

logger = logging.getLogger(__name__)

async def _pyrogram_send_video(chat_id, file_path, caption="", supports_streaming=True, progress_callback=None):
    from pyrogram import Client
    async with Client(
        "az_studio_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=str(config.TEMP_DIR)
    ) as app:
        async def pyro_progress(current, total):
            if progress_callback and total > 0:
                pct = (current / total) * 100.0
                try:
                    progress_callback(pct, f"{current / (1024*1024):.1f}MB / {total / (1024*1024):.1f}MB")
                except Exception:
                    pass

        return await app.send_video(
            chat_id=chat_id,
            video=str(file_path),
            caption=caption,
            supports_streaming=supports_streaming,
            progress=pyro_progress if progress_callback else None
        )

async def _pyrogram_send_audio(chat_id, file_path, title="", performer="", caption=""):
    from pyrogram import Client
    async with Client(
        "az_studio_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=str(config.TEMP_DIR)
    ) as app:
        return await app.send_audio(
            chat_id=chat_id,
            audio=str(file_path),
            title=title,
            performer=performer,
            caption=caption
        )

def send_video_smart(bot, chat_id, file_path, caption="", supports_streaming=True, progress_callback=None):
    """
    Sends video using standard Telegram Bot API if < 49MB.
    Automatically escalates to MTProto client (up to 2GB) if >= 49MB or on 413 error.
    """
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    logger.info(f"Attempting video upload: {file_path} ({file_size_mb:.2f} MB) to {chat_id}")

    if file_size_mb < 49.0 and bot:
        try:
            with open(file_path, 'rb') as f:
                return bot.send_video(
                    chat_id,
                    f,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=supports_streaming
                )
        except Exception as e:
            err_str = str(e)
            if "413" in err_str or "Request Entity Too Large" in err_str:
                logger.warning(f"Standard upload failed with 413 for {file_size_mb:.1f} MB. Switching to MTProto 2GB engine.")
            else:
                logger.error(f"Standard upload failed with non-413 error: {e}")
                raise e

    # Use MTProto 2GB Uploader
    logger.info(f"Using MTProto 2GB upload engine for {file_size_mb:.2f} MB file...")
    return asyncio.run(_pyrogram_send_video(
        chat_id=chat_id,
        file_path=file_path,
        caption=caption,
        supports_streaming=supports_streaming,
        progress_callback=progress_callback
    ))

def send_audio_smart(bot, chat_id, file_path, title="", performer="", caption="", reply_markup=None):
    """
    Sends audio using standard Telegram Bot API if < 45MB.
    Automatically escalates to MTProto client (up to 2GB) if >= 45MB or on 413 error.
    """
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    logger.info(f"Attempting audio upload: {file_path} ({file_size_mb:.2f} MB) to {chat_id}")

    if file_size_mb < 45.0 and bot:
        try:
            with open(file_path, 'rb') as f:
                return bot.send_audio(
                    chat_id,
                    f,
                    title=title,
                    performer=performer,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            err_str = str(e)
            if "413" in err_str or "Request Entity Too Large" in err_str:
                logger.warning(f"Standard audio upload failed with 413 for {file_size_mb:.1f} MB. Switching to MTProto 2GB engine.")
            else:
                raise e

    # Use MTProto 2GB Uploader
    logger.info(f"Using MTProto 2GB upload engine for {file_size_mb:.2f} MB audio...")
    return asyncio.run(_pyrogram_send_audio(
        chat_id=chat_id,
        file_path=file_path,
        title=title,
        performer=performer,
        caption=caption
    ))
