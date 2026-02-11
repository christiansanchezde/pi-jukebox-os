#!/usr/bin/env python3
"""RFID-controlled jukebox.
Yocto Adaptation:
- Logs moved to /var/log/
- Music expected in /home/root/music
- VLC forced to run as root
"""
import os
import sys
import asyncio
import subprocess
import logging
from contextlib import suppress
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

# ——————— Global filter to drop AUTH ERROR lines ———————
class FilterStream:
    def __init__(self, orig):
        self.orig = orig
    def write(self, data):
        if "AUTH ERROR" in data:
            return
        self.orig.write(data)
    def flush(self):
        self.orig.flush()

sys.stdout = FilterStream(sys.stdout)
sys.stderr = FilterStream(sys.stderr)

# ——————— Paths & config ———————
# In Yocto, the script lives in /usr/bin, but data should live elsewhere.
BASE_DIR      = os.path.dirname(__file__) 

# Music should be in user home or data partition
MUSIC_ROOT    = '/home/root/music' 

# Config stays with script or goes to /etc. We'll keep it next to script for simplicity.
MAPPING_FILE  = os.path.join(BASE_DIR, 'mappings.cfg')

# Logs must go to /var/log, writing to /usr/bin will fail permissions
LOG_FILE      = '/var/log/jukebox.log'
PLAYBACK_LOG  = '/var/log/jukebox_playback.log'

# LED pins (BCM numbering)
GREEN_LED_GPIO = 6    # header pin 29
BLUE_LED_GPIO  = 12   # header pin 31
RED_LED_GPIO   = 5    # header pin 33

AUDIO_EXTS     = ('.mp3', '.wav', '.ogg', '.flac')
POLL_INTERVAL  = 0.2  # seconds between tag polls
BLINK_INTERVAL = 0.5  # seconds for blue LED blink

# ——————— Logging setup ———————
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('jukebox')

# ——————— Load tag→folder mappings ———————
def load_mappings(path):
    """Return (dict(uid→folder), default_folder_or_None)."""
    mappings, default = {}, None
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                uid, folder = map(str.strip, line.split('=', 1))
                uid = uid.upper()
                if uid == 'DEFAULT':
                    default = folder
                else:
                    mappings[uid] = folder
        logger.info(f"Loaded {len(mappings)} mappings (default={default!r})")
    except FileNotFoundError:
        logger.warning(f"No mappings file at {path!r}; only DEFAULT (if any) will apply.")
    return mappings, default

# ——————— Async playback task ———————
async def playback(folder: str, uid_hex: str, start_index: int = 0):
    """Play all tracks in _folder_ beginning with _start_index_ (0‑based)."""
    try:
        files = sorted(
            f for f in os.listdir(folder)
            if f.lower().endswith(AUDIO_EXTS)
        )
    except FileNotFoundError:
        logger.error(f"Music folder not found: {folder}")
        return

    if not files:
        logger.warning(f"No audio files in {folder!r}, skipping playback.")
        return

    # Rotate list so desired start track is first
    if start_index:
        files = files[start_index:] + files[:start_index]
    paths = [os.path.join(folder, f) for f in files]

    msg = (
        f"   Starting playback of {len(paths)} file(s) in “{os.path.basename(folder)}” "
        f"from index {start_index} for UID={uid_hex}"
    )
    print(msg)

    try:
        with open(PLAYBACK_LOG, 'a') as flog:
            flog.write(msg + '\n')
    except PermissionError as e:
        logger.error(f"Could not write to playback.log: {e}")

    try:
        # CHANGE: Added --run-as-root because systemd runs as root
        proc = await asyncio.create_subprocess_exec(
            'cvlc', '--no-video', '--loop', '--run-as-root', *paths,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.error("cvlc not found. Install VLC.")
        return

    try:
        await proc.wait()
    except asyncio.CancelledError:
        proc.terminate()
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        raise

# ——————— Async LED blink task ———————
async def blink_led(pin: int):
    state = False
    while True:
        state = not state
        GPIO.output(pin, state)
        await asyncio.sleep(BLINK_INTERVAL)

# ——————— Main loop ———————
async def main():
    # GPIO init
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in (GREEN_LED_GPIO, BLUE_LED_GPIO, RED_LED_GPIO):
        GPIO.setup(pin, GPIO.OUT)

    # Initial LED states
    GPIO.output(GREEN_LED_GPIO, GPIO.HIGH)   # ready
    GPIO.output(BLUE_LED_GPIO, GPIO.LOW)
    GPIO.output(RED_LED_GPIO, GPIO.LOW)

    reader = SimpleMFRC522()
    mappings, default_folder = load_mappings(MAPPING_FILE)
    
    last_uid = None                 # UID currently present
    play_task = blink_task = None   # async tasks
    index_map = {}                  # UID → next start index

    logger.info("Jukebox ready. Tap an RFID tag… Ctrl+C to quit.")

    try:
        while True:
            # Non‑blocking RFID poll
            try:
                uid, _ = reader.read_no_block()
            except Exception:
                uid = None

            if uid:
                uid_hex = format(uid, 'X').upper()
                if uid_hex != last_uid:
                    # ——— New tag detected ———
                    if play_task:
                        play_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await play_task
                    if blink_task:
                        blink_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await blink_task
                    
                    GPIO.output(BLUE_LED_GPIO, GPIO.LOW)
                    
                    folder_name = mappings.get(uid_hex, default_folder)
                    
                    if not folder_name:
                        logger.warning(f"No mapping for UID={uid_hex!r} and no DEFAULT set.")
                        GPIO.output(RED_LED_GPIO, GPIO.HIGH)
                    else:
                        folder_path = os.path.join(MUSIC_ROOT, folder_name)
                        if not os.path.isdir(folder_path):
                            logger.warning(f"Folder {folder_path!r} not found; skipping.")
                            GPIO.output(RED_LED_GPIO, GPIO.HIGH)
                        else:
                            # Compute next index cyclically
                            try:
                                files = sorted(
                                    f for f in os.listdir(folder_path)
                                    if f.lower().endswith(AUDIO_EXTS)
                                )
                            except FileNotFoundError:
                                files = []

                            if not files:
                                logger.warning(f"No audio files in {folder_path!r}, skipping.")
                                GPIO.output(RED_LED_GPIO, GPIO.HIGH)
                            else:
                                next_idx = (index_map.get(uid_hex, -1) + 1) % len(files)
                                index_map[uid_hex] = next_idx
                                
                                GPIO.output(RED_LED_GPIO, GPIO.LOW)
                                play_task = asyncio.create_task(
                                    playback(folder_path, uid_hex, start_index=next_idx)
                                )
                                blink_task = asyncio.create_task(blink_led(BLUE_LED_GPIO))
                    
                    last_uid = uid_hex
            else:
                # ——— No tag present ———
                if last_uid is not None:
                    logger.info("Tag removed — stopping playback & LED blink")
                    if play_task:
                        play_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await play_task
                    if blink_task:
                        blink_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await blink_task
                    
                    GPIO.output(BLUE_LED_GPIO, GPIO.LOW)
                    GPIO.output(RED_LED_GPIO, GPIO.LOW)
                    last_uid = None
            
            await asyncio.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — shutting down…")
    except Exception as exc:
        logger.exception(f"Unhandled exception in main loop: {exc}")
    finally:
        if play_task:
            play_task.cancel()
            with suppress(asyncio.CancelledError):
                await play_task
        if blink_task:
            blink_task.cancel()
            with suppress(asyncio.CancelledError):
                await blink_task
        GPIO.cleanup()
        logger.info("Jukebox stopped.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Unhandled exception at entrypoint, exiting…")
        try:
            GPIO.cleanup()
        except Exception:
            pass
        sys.exit(1)