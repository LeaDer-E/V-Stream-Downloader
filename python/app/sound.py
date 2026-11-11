import logging
import math
import struct
import wave
from pathlib import Path

from app.paths import cache_dir

logger = logging.getLogger(__name__)


class SoundManager:
    """Lazy QMediaPlayer + QAudioOutput wrapped inside try/except to prevent headless segfaults."""

    def __init__(self) -> None:
        self._player = None
        self._audio_output = None
        self._initialized = False
        self._failed = False

    def _ensure_chime_file(self) -> Path:
        wav_path = cache_dir() / "v_notify_chime.wav"
        if wav_path.exists():
            return wav_path
        try:
            sample_rate = 44100
            duration = 0.28
            n_samples = int(sample_rate * duration)
            with wave.open(str(wav_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                for i in range(n_samples):
                    t = i / float(sample_rate)
                    freq = 880.0 if t < 0.12 else 1318.5
                    env = math.exp(-t * 10.5)
                    val = int(32767 * 0.28 * env * math.sin(2.0 * math.pi * freq * t))
                    wf.writeframesraw(struct.pack("<h", val))
        except Exception as exc:
            logger.debug("Could not synthesize chime wav: %s", exc)
        return wav_path

    def _lazy_init(self) -> bool:
        if self._initialized:
            return not self._failed
        self._initialized = True
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(0.65)
            self._player.setAudioOutput(self._audio_output)
            wav_file = self._ensure_chime_file()
            if wav_file.exists():
                self._player.setSource(QUrl.fromLocalFile(str(wav_file)))
            return True
        except Exception as exc:
            logger.warning("Audio subsystem unavailable: %s", exc)
            self._failed = True
            return False

    def play_chime(self, enabled: bool = True) -> None:
        if not enabled:
            return
        try:
            if self._lazy_init() and self._player is not None:
                self._player.stop()
                self._player.play()
        except Exception as exc:
            logger.debug("Audio playback skipped: %s", exc)


SOUND = SoundManager()
