"""
DOBBY Wake Word Daemon

Continuously listens for "도비야" and wakes DOBBY.
Prevents system sleep (caffeinate -i) but allows display sleep.
When wake word detected: wakes display + triggers DOBBY.

Usage:
    python wakeword.py
"""

import sys
import time
import subprocess
import threading
import logging
import numpy as np
import requests
import sounddevice as sd
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [wakeword] %(message)s")
log = logging.getLogger("wakeword")

SAMPLE_RATE = 16000
CHUNK_DURATION = 2.5      # seconds per transcription chunk
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
ENERGY_THRESHOLD = 0.008  # RMS threshold — below this = silence
COOLDOWN_SECONDS = 3.0    # ignore re-triggers for this long after wake

WAKE_WORDS = ["도비야", "도비", "도비 야", "도비일번", "도비 일번"]
DOBBY_URL = "http://localhost:8340"

_last_triggered = 0.0
_caffeinate_proc = None


def start_caffeinate():
    """Prevent system sleep while daemon is running."""
    global _caffeinate_proc
    _caffeinate_proc = subprocess.Popen(
        ["caffeinate", "-i"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log.info(f"caffeinate started (PID {_caffeinate_proc.pid}) — system sleep prevented")


def stop_caffeinate():
    global _caffeinate_proc
    if _caffeinate_proc:
        _caffeinate_proc.terminate()


def wake_display():
    """Wake the display if it's sleeping."""
    subprocess.run(["caffeinate", "-u", "-t", "1"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def trigger_dobby():
    """Send wake signal to DOBBY server."""
    try:
        requests.post(f"{DOBBY_URL}/api/wake", timeout=3)
        log.info("DOBBY triggered via /api/wake")
    except Exception as e:
        log.warning(f"Could not reach DOBBY server: {e}")


def is_speech(audio: np.ndarray) -> bool:
    rms = float(np.sqrt(np.mean(audio ** 2)))
    return rms > ENERGY_THRESHOLD


def contains_wake_word(text: str) -> bool:
    return any(w in text for w in WAKE_WORDS)


def main():
    global _last_triggered

    log.info("Loading Whisper tiny model (Korean)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    log.info("Model loaded. Listening for '도비야'...")

    start_caffeinate()

    # Rolling buffer — always holds the last CHUNK_DURATION seconds
    buffer = np.zeros(CHUNK_SAMPLES, dtype=np.float32)
    buffer_lock = threading.Lock()

    def audio_callback(indata, frames, time_info, status):
        audio = indata[:, 0].astype(np.float32)
        with buffer_lock:
            nonlocal buffer
            buffer = np.roll(buffer, -len(audio))
            buffer[-len(audio):] = audio

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="float32", callback=audio_callback):
            while True:
                time.sleep(CHUNK_DURATION)

                with buffer_lock:
                    chunk = buffer.copy()

                if not is_speech(chunk):
                    continue

                segments, _ = model.transcribe(
                    chunk, language="ko", beam_size=1, vad_filter=True
                )
                text = " ".join(s.text for s in segments).strip()

                if not text:
                    continue

                log.info(f"Heard: {text}")

                now = time.time()
                if contains_wake_word(text) and (now - _last_triggered) > COOLDOWN_SECONDS:
                    _last_triggered = now
                    log.info("Wake word '도비야' detected!")
                    wake_display()
                    trigger_dobby()

    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        stop_caffeinate()


if __name__ == "__main__":
    main()
