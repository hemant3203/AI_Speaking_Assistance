/**
 * AudioWorklet that turns microphone input into 100 ms frames of 16 kHz PCM16.
 *
 * It resamples here rather than asking for new AudioContext({sampleRate: 16000}), because Firefox
 * refuses to connect a mic stream to a context whose rate differs from the device's.
 *
 * Downsampling averages every input sample that falls inside an output sample's window, weighting
 * the samples that straddle a boundary. Plain decimation would alias high frequencies into the
 * speech band, which hurts transcription.
 */
const FRAME_MS = 100;
const LEVELS_PER_SECOND = 30;

class PcmRecorderProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const targetRate = options?.processorOptions?.targetRate ?? 16000;
    // `sampleRate` is a global in AudioWorkletGlobalScope: the context's native rate.
    this.ratio = sampleRate / targetRate;
    this.frameLength = Math.round((targetRate * FRAME_MS) / 1000);
    this.frame = new Int16Array(this.frameLength);
    this.written = 0;
    this.binSum = 0;
    this.binWeight = 0;
    this.levelWindow = Math.round(sampleRate / LEVELS_PER_SECOND);
    this.levelSum = 0;
    this.levelCount = 0;
  }

  pushSample(value) {
    const clamped = Math.max(-1, Math.min(1, value));
    this.frame[this.written++] = clamped < 0 ? clamped * 32768 : clamped * 32767;
    if (this.written === this.frameLength) {
      const buffer = this.frame.buffer;
      // Transfer rather than copy: this runs on the audio thread and should stay cheap.
      this.port.postMessage({ type: 'frame', pcm: buffer }, [buffer]);
      this.frame = new Int16Array(this.frameLength);
      this.written = 0;
    }
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels || channels.length === 0) return true;
    const blockLength = channels[0].length;

    for (let i = 0; i < blockLength; i++) {
      let sample = 0;
      for (let c = 0; c < channels.length; c++) sample += channels[c][i];
      sample /= channels.length;

      this.levelSum += sample * sample;
      if (++this.levelCount >= this.levelWindow) {
        this.port.postMessage({ type: 'level', rms: Math.sqrt(this.levelSum / this.levelCount) });
        this.levelSum = 0;
        this.levelCount = 0;
      }

      // Each input sample carries a weight of 1, spread across however many output bins it touches.
      let remaining = 1;
      while (this.binWeight + remaining >= this.ratio) {
        const take = this.ratio - this.binWeight;
        this.pushSample((this.binSum + sample * take) / this.ratio);
        this.binSum = 0;
        this.binWeight = 0;
        remaining -= take;
      }
      this.binSum += sample * remaining;
      this.binWeight += remaining;
    }
    return true;
  }
}

registerProcessor('pcm-recorder', PcmRecorderProcessor);
