"""Tests for delivery metrics, on synthetic PCM."""
import io
import wave

import numpy as np

from app.services.analysis.audio_metrics import SAMPLE_RATE, compute_audio_metrics, pcm_to_wav


def _tone(seconds: float, amplitude: int = 8000) -> np.ndarray:
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (np.sin(2 * np.pi * 220 * times) * amplitude).astype("<i2")


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype="<i2")


def _noise(rng: np.random.Generator, seconds: float) -> np.ndarray:
    return rng.normal(0, 400, int(seconds * SAMPLE_RATE)).astype("<i2")


def _pcm(*parts: np.ndarray) -> bytes:
    return np.concatenate(parts).tobytes()


def test_silence_has_no_speech():
    metrics = compute_audio_metrics(_pcm(_silence(5)))
    assert metrics.speaking_seconds == 0.0
    assert metrics.pause_count == 0


def test_empty_and_tiny_input():
    assert compute_audio_metrics(b"").speaking_seconds == 0.0
    assert compute_audio_metrics(b"\x00\x01" * 10).speaking_seconds == 0.0


def test_odd_length_input_does_not_crash():
    assert compute_audio_metrics(_pcm(_tone(1)) + b"\x00").speaking_seconds > 0


def test_leading_and_trailing_silence_excluded():
    metrics = compute_audio_metrics(_pcm(_silence(2), _tone(3), _silence(2)))
    assert abs(metrics.speaking_seconds - 3.0) <= 0.2
    assert metrics.pause_count == 0


def test_pause_is_counted_and_measured():
    metrics = compute_audio_metrics(_pcm(_silence(1), _tone(2), _silence(1), _tone(2), _silence(1)))
    assert abs(metrics.speaking_seconds - 5.0) <= 0.2
    assert metrics.pause_count == 1
    assert abs(metrics.longest_pause_seconds - 1.0) <= 0.2
    assert abs(metrics.pause_ratio - 0.2) <= 0.05


def test_gaps_under_half_a_second_are_not_pauses():
    assert compute_audio_metrics(_pcm(_tone(2), _silence(0.2), _tone(2), _silence(1))).pause_count == 0


def test_long_pause_counted_separately():
    metrics = compute_audio_metrics(_pcm(_tone(2), _silence(2), _tone(2), _silence(0.7), _tone(2)))
    assert metrics.pause_count == 2
    assert metrics.long_pause_count == 1


def test_noise_floor_adapts_to_a_noisy_room():
    rng = np.random.default_rng(1)
    metrics = compute_audio_metrics(_pcm(_noise(rng, 2), _tone(2) + _noise(rng, 2), _noise(rng, 2)))
    assert abs(metrics.speaking_seconds - 2.0) <= 0.3


def test_volume_variation_reflects_dynamics():
    flat = compute_audio_metrics(_pcm(_tone(4, 8000)))
    varied = compute_audio_metrics(_pcm(_tone(1, 2500), _tone(1, 12000), _tone(1, 5000), _tone(1, 20000)))
    assert flat.volume_variation < 0.05
    assert varied.volume_variation > 0.3
    # The soft opening is quiet speech, not silence, even though the recording has no real silence.
    assert abs(varied.speaking_seconds - 4.0) <= 0.2 and varied.pause_count == 0


def test_wav_round_trip():
    pcm = _pcm(_tone(1))
    with wave.open(io.BytesIO(pcm_to_wav(pcm))) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, SAMPLE_RATE)
        assert wav.readframes(wav.getnframes()) == pcm
