import database as db
import os

user_id = 8615007714
session = db.get_session(user_id)
print("SESSION:", session)
if session:
    raw = session.get("raw_audio_path")
    print("RAW EXISTS:", raw, os.path.exists(raw) if raw else False)
