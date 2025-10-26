import asyncio
import bus
import test

async def session_starter():
    while True:
        try:
            evt = await asyncio.wait_for(bus.face_q.get(), timeout=1)
        except asyncio.TimeoutError:
            continue

        etype = evt.get("type")
        name = evt.get("name")
        confidence = evt.get("confidence")

        if name == bus.TARGET_NAME and not bus.session_active.is_set():
            bus.session_active.set()
            print("[starter]", id(bus), id(bus.session_active))
            bus.mark_target_seen()

        if name == bus.TARGET_NAME and bus.session_active.is_set():
            bus.rommel_seen()

async def watch_dog():
    while True:
        await asyncio.sleep(0.5)
        if bus.time_out():
            bus.session_active.clear()
            import time
            print("[watchdog]", id(bus), id(bus.session_active), "now=", time.time(), "last=", bus._last_seen_ts,
                  "delta=", time.time() - bus._last_seen_ts)
            print("🛌 Session ended (timeout)")

async def object_loop():
    import asyncio
    import bus
    from SpeechRecognitionFile import SpeechRecognition

    print("[objloop] task started")

    while True:
        try:
            print("[objloop] waiting for session...")
            await bus.session_active.wait()
            print("[objloop] woke up (session active)")

            while bus.session_active.is_set():
                try:
                    text = await asyncio.to_thread(SpeechRecognition)
                    if text:
                        print(text)
                        answere = test.interaction(text)
                        print(answere)
                except Exception as e:
                    print(f"[objloop inner error] {e}")
                await asyncio.sleep(0.1)

            print("[objloop] session cleared; back to wait")

        except Exception as e:
            print(f"[objloop CRASH] {e}")
            # tiny backoff so don't tight-loop on repeated crashes
        await asyncio.sleep(0.2)
