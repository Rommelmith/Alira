# prepare_samples.py
import wave
import os
from pathlib import Path


def check_wav_file(filepath):
    """Check if WAV file meets Picovoice requirements"""
    try:
        with wave.open(str(filepath), 'rb') as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            framerate = wav.getframerate()
            frames = wav.getnframes()
            duration = frames / float(framerate)

            print(f"\n📁 {filepath.name}")
            print(f"   Channels: {channels} (need: 1)")
            print(f"   Sample Rate: {framerate} Hz (need: 16000)")
            print(f"   Bit Depth: {sample_width * 8} bit (need: 16)")
            print(f"   Duration: {duration:.2f} seconds (recommended: 1.5-3s)")

            # Check requirements
            issues = []
            if channels != 1:
                issues.append("❌ Must be mono (1 channel)")
            if framerate != 16000:
                issues.append("❌ Must be 16000 Hz")
            if sample_width != 2:
                issues.append("❌ Must be 16-bit")
            if duration < 1.0 or duration > 5.0:
                issues.append("⚠️  Duration should be 1.5-3 seconds")

            if issues:
                for issue in issues:
                    print(f"   {issue}")
                return False
            else:
                print("   ✅ File is good!")
                return True

    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        return False


# Check all your samples
samples_dir = Path("wake_word_samples")  # Update this path
wav_files = sorted(samples_dir.glob("alira_*.wav"))

print(f"Found {len(wav_files)} audio files")
print("=" * 50)

good_files = []
bad_files = []

for wav_file in wav_files:
    if check_wav_file(wav_file):
        good_files.append(wav_file)
    else:
        bad_files.append(wav_file)

print("\n" + "=" * 50)
print(f"✅ Good files: {len(good_files)}")
print(f"❌ Files needing conversion: {len(bad_files)}")

if len(good_files) < 3:
    print("\n⚠️  Warning: You need at least 3 samples for training!")
    print("   Recommended: 10-20 samples for best accuracy")