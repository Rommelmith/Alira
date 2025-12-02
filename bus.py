import asyncio
import time

face_q = asyncio.Queue()
object_q = asyncio.Queue()

session_active = asyncio.Event()

TARGET_NAME = "Rommel"
TIMEOUT_S = 3000
_last_seen_ts = 0.0

def mark_target_seen():
    global _last_seen_ts
    _last_seen_ts = time.time()
    session_active.set()
    print("Rommel Seen")

def rommel_seen():
    global _last_seen_ts
    _last_seen_ts = time.time()
def time_out():
    return session_active.is_set() and (time.time() - _last_seen_ts) > TIMEOUT_S


