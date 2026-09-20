"""
Configuration settings for AZ 8D Audio & Video Studio Bot (@azmusicstudiobot).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Bot Token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", os.getenv("EIGHT_D_BOT_TOKEN", "8519786701:AAF6sJDRUBzbV2bBZjbI9gcH1IfMtAfSmvc"))

# Telegram MTProto API Credentials (for 2GB upload limit)
API_ID = int(os.getenv("TELEGRAM_API", os.getenv("API_ID", "38044924")))
API_HASH = os.getenv("TELEGRAM_HASH", os.getenv("API_HASH", "7e273a3aad1356d9c69381077f372ee4"))

# Directory Paths
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"

TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = BASE_DIR / "az_8d_bot.db"

# Audio & Video Constraints
MAX_AUDIO_SIZE_MB = int(os.getenv("MAX_AUDIO_SIZE_MB", "50"))
MAX_VIDEO_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB", "100"))
AUDIO_SAMPLE_RATE = 48000
MP3_BITRATE = "320k"
TARGET_LUFS = -14.0
TARGET_TP = -1.0

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
