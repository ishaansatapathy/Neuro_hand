"""
=============================================================================
 VOICE FEEDBACK SYSTEM — ElevenLabs TTS for Rehab Guidance
=============================================================================

 Pre-generates rehab voice instructions using ElevenLabs API, saves them
 as mp3 files locally, then plays them with zero latency during sessions.

 Usage:
   from voice_feedback import VoiceFeedback

   vf = VoiceFeedback()
   vf.generate_all()          # one-time: creates mp3 files
   vf.speak("raise_hand")     # instant: plays cached mp3
   vf.speak_text("Custom")    # real-time: calls API for one-off phrases
=============================================================================
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

# Audio playback — try winsound (Windows built-in), else flag as browser-only
_player = None

try:
    import winsound
    _player = "winsound"
except ImportError:
    pass

# Note: For the web app, audio is played via the browser using the
# /api/voice/play/{key} endpoint — no local playback library needed.


# -- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
VOICE_DIR = BASE_DIR / "data" / "voice_cache"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = BASE_DIR / ".env"

# -- Rehab Phrases (Hinglish) ------------------------------------------------
REHAB_PHRASES = {
    # Session flow
    "welcome": "Namaste! Aapka rehabilitation session shuru hone wala hai. Chalo start karte hain.",
    "session_start": "Session ab shuru ho raha hai. Screen pe guide follow karo.",
    "session_end": "Bahut badhiya session tha! Aapka progress save ho gaya hai.",

    # Hand instructions
    "show_hand": "Apna haath camera ke saamne clearly dikhao.",
    "raise_hand": "Dheere dheere apna haath upar uthao.",
    "lower_hand": "Haath ko aaram se neeche laao.",
    "move_left": "Haath ko thoda left side mein move karo.",
    "move_right": "Haath ko thoda right side mein move karo.",

    # Gesture instructions
    "make_fist": "Apni ungliyan band karo aur mutthi banao. Halka squeeze karo.",
    "open_hand": "Haath kholo. Saari ungliyan phailao.",
    "point_finger": "Index finger seedha karo, baaki ungliyan band karo.",
    "hold_position": "Bilkul sahi! Yeh position thodi der hold karo.",

    # Finger-specific
    "curl_thumb": "Angutha andar ki taraf moro, hatheli ki taraf.",
    "curl_index": "Index finger neeche ki taraf moro.",
    "curl_middle": "Middle finger neeche ki taraf moro.",
    "curl_ring": "Ring finger neeche ki taraf moro.",
    "curl_pinky": "Chhoti ungli neeche ki taraf moro.",
    "extend_thumb": "Angutha bahar ki taraf seedha karo.",
    "extend_index": "Index finger ko seedha karo.",
    "extend_middle": "Middle finger ko seedha karo.",
    "extend_ring": "Ring finger ko seedha karo.",
    "extend_pinky": "Chhoti ungli ko seedha karo.",

    # Arm instructions
    "extend_elbow": "Apni kohni seedhi karo. Arm ko aur extend karo.",
    "relax_elbow": "Kohni ko thoda relax karo. Zyada stretch mat karo.",
    "straighten_wrist": "Kalai seedhi rakho, aligned rehni chahiye.",
    "arm_position": "Apna arm comfortably apne saamne rakho.",

    # Feedback
    "perfect": "Perfect! Ekdum sahi position hai.",
    "great_job": "Bahut accha! Tum bahut well kar rahe ho.",
    "almost_there": "Bahut kareeb ho. Thoda aur adjust karo.",
    "try_again": "Ek baar phir try karo. Guide follow karo.",
    "good_progress": "Acchi progress hai! Tum improve kar rahe ho.",
    "take_break": "Thoda rest lo. Haath ko relax karo.",
    "correct_more": "Haath ki position thodi aur adjust karo.",

    # Scoring
    "score_point": "Shabaash! Ek point mil gaya.",
    "new_exercise": "Naya exercise aa raha hai. Guide dekho.",
    "matched": "Match ho gaya! Bahut acchi form hai. Aise hi hold karo.",
}


def _load_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if key:
        return key
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


class VoiceFeedback:
    """
    Pre-generates and plays rehab voice instructions.
    Thread-safe — playback runs in background threads.
    """

    VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"   # "George" — calm male voice
    MODEL_ID = "eleven_multilingual_v2"

    def __init__(self, cooldown: float = 4.0) -> None:
        self._api_key = _load_api_key()
        self._cooldown = cooldown
        self._last_played: dict[str, float] = {}
        self._lock = threading.Lock()
        self._playing = False

    @property
    def available(self) -> bool:
        return bool(self._api_key) and _player is not None

    # ---------------------------------------------------------------- Generate

    def generate_all(self, force: bool = False) -> dict[str, bool]:
        """Generate all rehab phrases. Tries ElevenLabs first, falls back to pyttsx3."""
        results = {}

        # Check what's already cached
        all_cached = True
        for key in REHAB_PHRASES:
            path = VOICE_DIR / f"{key}.mp3"
            if path.exists() and not force:
                results[key] = True
            else:
                all_cached = False

        if all_cached and not force:
            print(f"[voice] All {len(results)} phrases already cached")
            return results

        # Try ElevenLabs first
        if self._api_key:
            try:
                from elevenlabs import ElevenLabs
                client = ElevenLabs(api_key=self._api_key)

                for key, text in REHAB_PHRASES.items():
                    if key in results and not force:
                        continue
                    path = VOICE_DIR / f"{key}.mp3"
                    try:
                        audio_gen = client.text_to_speech.convert(
                            text=text,
                            voice_id=self.VOICE_ID,
                            model_id=self.MODEL_ID,
                            output_format="mp3_44100_128",
                        )
                        audio_bytes = b"".join(audio_gen)
                        path.write_bytes(audio_bytes)
                        results[key] = True
                        print(f"  [voice] ElevenLabs: {key} ({len(audio_bytes)} bytes)")
                    except Exception as e:
                        print(f"  [voice] ElevenLabs failed for {key}, will try offline")
                        break  # Stop hitting the API if it's failing
            except ImportError:
                pass

        # Fallback: pyttsx3 (offline TTS)
        missing = [k for k in REHAB_PHRASES if k not in results]
        if missing:
            results.update(self._generate_offline(missing, force))

        print(f"[voice] Generated {sum(results.values())}/{len(REHAB_PHRASES)} phrases")
        return results

    def _generate_offline(self, keys: list[str], force: bool = False) -> dict[str, bool]:
        """Generate voice files using edge-tts (Microsoft Edge free TTS)."""
        results = {}
        try:
            import asyncio
            import edge_tts
        except ImportError:
            print("[voice] edge-tts not installed — run: pip install edge-tts")
            return {k: False for k in keys}

        VOICE = "hi-IN-MadhurNeural"  # Hindi male voice — great for Hinglish

        async def _gen_one(key: str, text: str, path: Path) -> bool:
            try:
                comm = edge_tts.Communicate(text, VOICE, rate="-10%")
                await comm.save(str(path))
                return True
            except Exception as e:
                print(f"  [voice] edge-tts FAILED: {key} — {e}")
                return False

        async def _gen_all():
            for key in keys:
                text = REHAB_PHRASES.get(key, "")
                if not text:
                    continue
                mp3_path = VOICE_DIR / f"{key}.mp3"
                if mp3_path.exists() and not force:
                    results[key] = True
                    continue

                ok = await _gen_one(key, text, mp3_path)
                results[key] = ok
                if ok:
                    print(f"  [voice] edge-tts: {key}")

        asyncio.run(_gen_all())
        return results

    def generate_custom(self, key: str, text: str) -> bool:
        """Generate a single custom phrase."""
        if not self._api_key:
            return False

        try:
            from elevenlabs import ElevenLabs
            client = ElevenLabs(api_key=self._api_key)
            audio_gen = client.text_to_speech.convert(
                text=text,
                voice_id=self.VOICE_ID,
                model_id=self.MODEL_ID,
                output_format="mp3_44100_128",
            )
            path = VOICE_DIR / f"{key}.mp3"
            path.write_bytes(b"".join(audio_gen))
            return True
        except Exception as e:
            print(f"[voice] Custom generation failed: {e}")
            return False

    # ---------------------------------------------------------------- Playback

    def speak(self, phrase_key: str) -> bool:
        """Play a pre-generated phrase (non-blocking, with cooldown)."""
        path = VOICE_DIR / f"{phrase_key}.mp3"
        if not path.exists():
            return False

        now = time.time()
        with self._lock:
            last = self._last_played.get(phrase_key, 0)
            if now - last < self._cooldown:
                return False
            if self._playing:
                return False
            self._last_played[phrase_key] = now

        threading.Thread(target=self._play_file, args=(str(path),),
                         daemon=True).start()
        return True

    def speak_for_action(self, finger_name: str, action: str) -> bool:
        """Convenience: speak based on finger + action."""
        key = f"{action}_{finger_name}"
        return self.speak(key)

    def speak_severity(self, severity: str, match_pct: float = 0.0) -> bool:
        """Speak feedback based on overall severity."""
        if severity == "correct" or match_pct >= 0.85:
            return self.speak("perfect")
        elif severity == "warning" or match_pct >= 0.6:
            return self.speak("almost_there")
        elif severity == "error":
            return self.speak("correct_more")
        return False

    def _play_file(self, filepath: str) -> None:
        self._playing = True
        try:
            if _player == "winsound":
                import subprocess
                subprocess.Popen(
                    ["powershell", "-c",
                     f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                ).wait(timeout=10)
            else:
                print(f"[voice] No local player — serve via /api/voice/play/")
        except Exception as e:
            print(f"[voice] Playback error: {e}")
        finally:
            self._playing = False

    # ---------------------------------------------------------------- Status

    def list_cached(self) -> list[str]:
        """Return list of cached phrase keys."""
        return [p.stem for p in VOICE_DIR.glob("*.mp3")]

    def cache_status(self) -> dict[str, bool]:
        """Check which phrases are cached."""
        return {key: (VOICE_DIR / f"{key}.mp3").exists()
                for key in REHAB_PHRASES}
