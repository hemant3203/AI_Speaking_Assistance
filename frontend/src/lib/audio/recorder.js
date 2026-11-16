/**
 * Microphone capture: getUserMedia into an AudioWorklet that emits 16 kHz PCM16 frames and RMS levels.
 *
 * The context runs at the device's native rate and the worklet resamples, so this works on Firefox.
 */
const WORKLET_URL = '/audio/pcm-recorder-worklet.js';
const TARGET_RATE = 16000;

/** Mic failure with a stable code, so the UI can explain how to fix each case. */
export class MicError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'MicError';
    this.code = code;
  }
}

function toMicError(error) {
  switch (error?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return new MicError('denied', 'Microphone access is blocked for this site.');
    case 'NotFoundError':
    case 'OverconstrainedError':
      return new MicError('not_found', 'No microphone was found on this device.');
    case 'NotReadableError':
    case 'AbortError':
      return new MicError('busy', 'Your microphone is being used by another app.');
    default:
      return new MicError('unknown', 'We could not start your microphone.');
  }
}

export class MicRecorder {
  constructor({ onFrame, onLevel, onEnded }) {
    this.onFrame = onFrame;
    this.onLevel = onLevel;
    this.onEnded = onEnded;
    this.context = null;
    this.stream = null;
    this.node = null;
    this.source = null;
    this.sink = null;
    this.stopped = false;
  }

  /** Must be called from a click handler, so the AudioContext is allowed to start. */
  async start() {
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === 'undefined') {
      // mediaDevices is undefined on plain http unless the host is localhost.
      throw new MicError('unsupported', 'This browser, or this non-secure address, cannot use the microphone.');
    }
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.context = new Ctx({ latencyHint: 'interactive' });
    // Resume synchronously inside the gesture. The permission prompt below can outlive it.
    this.context.resume().catch(() => {});

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
        video: false,
      });
    } catch (error) {
      this.stop();
      throw toMicError(error);
    }
    if (this.stopped) {
      this.stop();
      return;
    }

    try {
      await this.context.audioWorklet.addModule(WORKLET_URL);
      await this.context.resume();
      if (this.stopped) return;

      this.source = this.context.createMediaStreamSource(this.stream);
      this.node = new AudioWorkletNode(this.context, 'pcm-recorder', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        channelCount: 1,
        processorOptions: { targetRate: TARGET_RATE },
      });
      this.node.port.onmessage = ({ data }) => {
        if (data.type === 'frame') this.onFrame?.(data.pcm);
        else if (data.type === 'level') this.onLevel?.(data.rms);
      };
      // Some browsers only pull nodes that reach the destination. The zero gain keeps it silent.
      this.sink = this.context.createGain();
      this.sink.gain.value = 0;
      this.source.connect(this.node);
      this.node.connect(this.sink);
      this.sink.connect(this.context.destination);
    } catch (error) {
      this.stop();
      throw error instanceof MicError ? error : new MicError('unknown', 'We could not start audio processing.');
    }

    // Fires when the mic is unplugged or the permission is revoked mid-session.
    this.stream.getAudioTracks().forEach((track) => {
      track.onended = () => {
        if (!this.stopped) this.onEnded?.();
      };
    });
  }

  stop() {
    this.stopped = true;
    this.stream?.getTracks().forEach((track) => {
      track.onended = null;
      track.stop();
    });
    this.stream = null;
    if (this.node) this.node.port.onmessage = null;
    try {
      this.source?.disconnect();
      this.node?.disconnect();
      this.sink?.disconnect();
    } catch {
      // Already disconnected: nothing left to release.
    }
    if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {});
    this.context = null;
    this.node = null;
    this.source = null;
    this.sink = null;
  }
}
