/**
 * Gapless playback of the coach's 24 kHz PCM16 audio using scheduled AudioBufferSourceNodes.
 *
 * Each chunk starts exactly where the previous one ends. flush() stops everything at once, for
 * `interrupted` messages and when the user barges in to ask a follow-up.
 */
const COACH_RATE = 24000;
// Small head start for the first chunk of a turn, which absorbs network jitter between chunks.
const LEAD_SECONDS = 0.08;

export class CoachPlayer {
  constructor({ onPlayingChange } = {}) {
    this.onPlayingChange = onPlayingChange;
    this.context = null;
    this.nextStart = 0;
    this.sources = new Set();
    this.carry = null; // A chunk can end mid-sample, so hold the odd byte for the next one.
    this.playing = false;
  }

  /** Create and resume the context. Must be called from a click, or autoplay policy keeps it muted. */
  unlock() {
    if (!this.context) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      try {
        // Matching the coach's rate avoids resampling seams at chunk boundaries.
        this.context = new Ctx({ sampleRate: COACH_RATE, latencyHint: 'interactive' });
      } catch {
        this.context = new Ctx();
      }
    }
    if (this.context.state === 'suspended') this.context.resume().catch(() => {});
  }

  enqueue(arrayBuffer) {
    if (!this.context || this.context.state === 'closed') return;
    let bytes = new Uint8Array(arrayBuffer);
    if (this.carry) {
      const joined = new Uint8Array(bytes.length + 1);
      joined[0] = this.carry[0];
      joined.set(bytes, 1);
      bytes = joined;
      this.carry = null;
    }
    if (bytes.length % 2 === 1) {
      this.carry = bytes.slice(-1);
      bytes = bytes.subarray(0, bytes.length - 1);
    }
    if (bytes.length === 0) return;

    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const sampleCount = bytes.length / 2;
    const buffer = this.context.createBuffer(1, sampleCount, COACH_RATE);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < sampleCount; i++) channel[i] = view.getInt16(i * 2, true) / 32768;

    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    const now = this.context.currentTime;
    if (this.nextStart < now + 0.01) this.nextStart = now + LEAD_SECONDS;
    source.start(this.nextStart);
    this.nextStart += buffer.duration;

    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      if (this.sources.size === 0) this.setPlaying(false);
    };
    this.setPlaying(true);
  }

  flush() {
    this.sources.forEach((source) => {
      source.onended = null;
      try {
        source.stop();
      } catch {
        // A source that already finished throws on stop. That is the state we want anyway.
      }
    });
    this.sources.clear();
    this.nextStart = 0;
    this.carry = null;
    this.setPlaying(false);
  }

  close() {
    this.flush();
    if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {});
    this.context = null;
  }

  setPlaying(next) {
    if (this.playing !== next) {
      this.playing = next;
      this.onPlayingChange?.(next);
    }
  }
}
