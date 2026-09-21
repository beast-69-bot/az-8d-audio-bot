import database as db
import os
import time

s = db.get_session(8615007714)
print("SESSION:")
print(s)
if s:
    updated = s.get('updated_at', 0)
    print("Updated at:", updated, "Seconds ago:", time.time() - updated)
