import queue, threading, time, numpy as np, sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
BLOCK_DUR   = 0.03  # 30 ms

print("[init] loading whisper…")
# Start with 'small' to verify speed; then move to 'medium' for accuracy.
model = WhisperModel("small", device="cpu", compute_type="int8")
print("[init] whisper ready")

audio_q = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status: print("[audio status]", status)
    audio_q.put(indata.copy())

def mic_thread():
    print("[mic] opening…")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=int(SAMPLE_RATE*BLOCK_DUR), callback=audio_callback):
        print("[mic] streaming")
        while True: time.sleep(0.1)

def drain_until_silence_and_transcribe():
    # Simple “utterance when pause” segmenter using built-in VAD
    buf = np.zeros((0,), np.float32)
    last_put = time.time()
    while True:
        try:
            block = audio_q.get(timeout=2.0)
        except queue.Empty:
            print("[warn] no mic audio for 2s — check mic permissions/device")
            continue

        buf = np.concatenate([buf, block.reshape(-1)])
        # If there’s a short pause, flush to Whisper
        if time.time() - last_put > 0.4 and len(buf) > SAMPLE_RATE*0.5:
            audio = buf.copy(); buf = np.zeros((0,), np.float32)
            print(f"[asr] {len(audio)/SAMPLE_RATE:.2f}s chunk")
            segments, info = model.transcribe(
                audio,
                language=None,          # auto; set "en" if you know it
                vad_filter=True,        # use built-in VAD (no torch.hub)
                vad_parameters=dict(min_silence_duration_ms=300),
                beam_size=1             # greedy = fastest
            )
            text = "".join(s.text for s in segments).strip()
            if text: print(">>", text)
        last_put = time.time()

if __name__ == "__main__":
    threading.Thread(target=mic_thread, daemon=True).start()
    drain_until_silence_and_transcribe()
