import asyncio
import json
import websockets
import bus
from pyttsx3 import speak
PORT = 8765

async def handler(websocket):
    print("✅ client connected")
    index = 0
    try:
        async for message in websocket:
            try:
                evt = json.loads(message)
            except json.JSONDecodeError:
                # print("📩 raw (non-JSON):", message)
                continue

            etype  = evt.get("type", "")
            device = evt.get("device", "?")
            vision = evt.get("vision") or {}



            # Person condition ######
            if etype in ("face_recognized", "face_unknown") and index % 3 == 0:
                face = vision.get("face") or {}
                name = face.get("name") if etype == "face_recognized" else "Unknown"
                confidence  = face.get("similarity", "?")

                bus.face_q.put_nowait({
                    "type":etype, "name":name, "confidence":confidence
                })

            #Object condition #####
            elif isinstance(etype, str) and etype.startswith("object_seen:") and index % 3 == 0:
                obj = vision.get("object") or {}
                label = etype.split(":", 1)[1] if ":" in etype else "unknown"
                score = obj.get("score", "?")

                if float(score) > 0.50 and bus.session_active:

                    bus.object_q.put_nowait({
                        "Object":label, "Confidence":score
                    })
            index = index + 1

    except websockets.ConnectionClosed:
        print("❌ client disconnected")

async def main():
    async with websockets.serve(handler, "0.0.0.0", PORT):
        import session_logic
        asyncio.create_task(session_logic.session_starter())
        asyncio.create_task(session_logic.object_loop())
        asyncio.create_task(session_logic.watch_dog())
        print(f"🚀 server listening on ws://0.0.0.0:{PORT}")
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())