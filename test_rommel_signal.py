"""
Simple test script to send a positive "Rommel" face recognition signal
This simulates the Android phone's face recognition without needing the actual device
"""

import asyncio
import json
import websockets

async def send_rommel_signal():
    """Send a positive face recognition signal for Rommel"""
    # WebSocket server address (change if your server is on a different machine)
    uri = "ws://127.0.0.1:8765"

    # Create the recognition event (same format as Android app)
    event = {
        "type": "face_recognized",
        "device": "test_script",
        "vision": {
            "face": {
                "name": "Rommel",
                "similarity": 0.95
            }
        }
    }

    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            # Send the signal
            await websocket.send(json.dumps(event))
            print(f"✓ Signal sent successfully!")
            print(f"  Type: {event['type']}")
            print(f"  Name: {event['vision']['face']['name']}")
            print(f"  Similarity: {event['vision']['face']['similarity']}")

            # Wait a moment before closing
            await asyncio.sleep(0.5)

    except ConnectionRefusedError:
        print("✗ Error: Could not connect to WebSocket server")
        print("  Make sure working.py is running on port 8765")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":

    print("=== Rommel Signal Test ===\n")
    while True:
        asyncio.run(send_rommel_signal())
        print("\nDone!")
