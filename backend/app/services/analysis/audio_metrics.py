"""Delivery metrics computed from raw PCM16 audio with numpy."""
import io
import wave
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16000
BYTES_PER_SECOND = SAMPLE_RATE * 2
_WINDOW_SECONDS = 0.1
_WINDOW_SAMPLES = int(SAMPLE_RATE * _WINDOW_SECONDS)
_PAUSE_MIN_WINDOWS = 5
_LONG_PAUSE_MIN_WINDOWS = 15
# A little above the level of a quiet room, so that a silent recording never counts as speech.
_ABSOLUTE_MIN_RMS = 150.0
# How far above the noise floor speech must rise, as a share of the floor-to-peak range.
_FLOOR_TO_PEAK_SHARE = 0.15
# About -30 dBFS, far louder than room noise. Without this cap, a recording with no real silence would
# have its quietest speech taken as the noise floor, and soft passages would be counted as pauses.
_ALWAYS_VOICED_RMS = 1000.0


@dataclass(frozen=True)
class AudioMetrics:
    """Delivery measurements for one speech."""

    speaking_seconds: float = 0.0
    pause_count: int = 0
    long_pause_count: int = 0
    longest_pause_seconds: float = 0.0
    pause_ratio: float = 0.0
    volume_variation: float = 0.0


def _window_rms(samples: np.ndarray) -> np.ndarray:
    count = len(samples) // _WINDOW_SAMPLES
    windows = samples[: count * _WINDOW_SAMPLES].reshape(count, _WINDOW_SAMPLES)
    return np.sqrt(np.mean(np.square(windows, dtype=np.float64), axis=1))


def _speech_threshold(rms: np.ndarray) -> float:
    # The floor adapts to each recording because every microphone and room has a different level.
    floor = float(np.percentile(rms, 10))
    peak = float(np.percentile(rms, 95))
    adaptive = floor + _FLOOR_TO_PEAK_SHARE * (peak - floor)
    return max(_ABSOLUTE_MIN_RMS, min(_ALWAYS_VOICED_RMS, adaptive))


def compute_audio_metrics(pcm: bytes) -> AudioMetrics:
    """Measure speaking time, pauses and volume variation from PCM16 mono 16 kHz audio.

    Speaking time runs from the first voiced window to the last, so it excludes leading and trailing
    silence but includes pauses in between.
    """
    samples = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2")
    if len(samples) < _WINDOW_SAMPLES:
        return AudioMetrics()

    rms = _window_rms(samples)
    voiced = rms >= _speech_threshold(rms)
    voiced_indexes = np.flatnonzero(voiced)
    if voiced_indexes.size == 0:
        return AudioMetrics()

    first, last = int(voiced_indexes[0]), int(voiced_indexes[-1])
    speaking_windows = last - first + 1

    pauses = []
    run = 0
    for is_voiced in voiced[first : last + 1]:
        if is_voiced:
            if run >= _PAUSE_MIN_WINDOWS:
                pauses.append(run)
            run = 0
        else:
            run += 1

    voiced_rms = rms[voiced]
    mean_rms = float(voiced_rms.mean())
    return AudioMetrics(
        speaking_seconds=round(speaking_windows * _WINDOW_SECONDS, 1),
        pause_count=len(pauses),
        long_pause_count=sum(1 for pause in pauses if pause >= _LONG_PAUSE_MIN_WINDOWS),
        longest_pause_seconds=round(max(pauses, default=0) * _WINDOW_SECONDS, 1),
        pause_ratio=round(sum(pauses) / speaking_windows, 3),
        volume_variation=round(float(voiced_rms.std()) / mean_rms, 3) if mean_rms else 0.0,
    )


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap PCM16 mono 16 kHz audio in an in-memory WAV container. Nothing is written to disk."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return buffer.getvalue()
