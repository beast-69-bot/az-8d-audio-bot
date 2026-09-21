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

print("Starting vocal_ai test...")
try:
    def progress_cb(pct, detail):
        print(f"PROGRESS: {pct}% - {detail}", flush=True)

    res = core.process_audio_effect(input_audio, out_mp3, effect="vocal_ai", progress_callback=progress_cb)
    print("SUCCESS! Output at:", res, "Size:", os.path.getsize(res))
except Exception as e:
    print("ERROR CAUGHT:")
    traceback.print_exc()
