import sys
import os
import traceback
import config
import database as db
import core

user_id = 8615007714
session = db.get_session(user_id)
print("SESSION:", session)

input_audio = session["raw_audio_path"]
out_mp3 = "/home/anshu/az-8d-audio-bot/temp/test_vocal_out.mp3"

import sqlite3
conn = sqlite3.connect('database.db')
print("CONVERSIONS:")
for r in conn.execute('SELECT * FROM conversions ORDER BY id DESC LIMIT 5').fetchall():
    print(r)
