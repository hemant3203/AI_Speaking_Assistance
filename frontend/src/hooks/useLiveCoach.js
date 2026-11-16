/**
 * The live practice session: microphone, WebSocket and coach audio behind one state machine.
 *
 *   idle -> connecting -> ready -> speaking -> analyzing -> feedback -> done, plus error.
 *
 * Two rules from the contract shape this hook:
 * - The scorecard is independent of the coach's voice. The coach may stay silent (the model can
 *   choose silence), so nothing here ever waits on audio or transcripts to move forward.
 * - A disconnect after speech_end does not lose the speech. The server finishes scoring, so the hook
 *   recovers the result over REST rather than showing a failure.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchMe } from '../api/auth';
import { liveSocketUrl } from '../api/client';
import { fetchSession } from '../api/practice';
import { fetchHealth } from '../api/system';
import { CoachPlayer } from '../lib/audio/player';
import { MicError, MicRecorder } from '../lib/audio/recorder';
import { logger } from '../lib/logger';

const READY_TIMEOUT_MS = 25000;
// Past this, assume the result message was lost. The server replaces it with a limit that fits the speech.
const ANALYSIS_WATCHDOG_MS = 90000;
const ANALYSIS_WATCHDOG_MARGIN_MS = 30000;
const RECOVERY_POLL_MS = 3000;
const RECOVERY_MAX_ATTEMPTS = 30;
// Connected time counts against the daily limit, so an idle scorecard should not keep the line open.
const FEEDBACK_IDLE_MS = 180000;

/** Friendly wording for each failure. `action` tells the page which way out to offer. */
export const LIVE_ERRORS = {
  4401: { title: 'Please log in again', message: 'Your session has expired, so we could not connect you to the coach.', action: 'login' },
  4403: { title: "This address isn't allowed", message: 'For security the coach only accepts connections from the address Spotlight is hosted on. Open Spotlight from its usual link and try again.', action: 'setup' },
  4404: { title: "We couldn't find that session", message: 'This practice session no longer exists. Start a new one and you will be right back on stage.', action: 'setup' },
  4409: { title: "You're already on stage", message: 'This session has already been used, or you are live in another tab. Close the other tab, then start a new session.', action: 'setup' },
  4429: { title: "That's today's stage time", message: "You've reached today's practice limit, so the coach is resting. It resets at midnight your time.", action: 'home' },
  4503: { title: 'The coach is unavailable', message: "We can't reach the coach right now. Your progress is safe. Please try again in a few minutes.", action: 'setup' },
  connect_failed: { title: "We couldn't connect to the coach", message: 'Check your connection and try again. Nothing was lost.', action: 'setup' },
  connect_timeout: { title: 'The coach is taking too long', message: 'The connection did not come up in time. Nothing was recorded. Please try again.', action: 'setup' },
  disconnected: { title: 'The connection dropped', message: "We lost the connection before you finished, so this take wasn't scored. Sorry about that. Your streak and XP are untouched.", action: 'setup' },
  analysis_timeout: { title: 'Scoring is taking longer than usual', message: 'Your speech was received. It should appear in History shortly, with your rewards.', action: 'history' },
};

const friendly = (key, fallbackMessage) => ({ code: String(key), ...(LIVE_ERRORS[key] ?? { title: 'Something went wrong', message: fallbackMessage ?? 'Please try again.', action: 'setup' }) });

export function useLiveCoach() {
  const [state, setStateValue] = useState('idle');
  const [mic, setMic] = useState({ status: 'off', code: null });
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [config, setConfig] = useState({ demo: false, maxSpeechSeconds: 900, targetSeconds: null });
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState(null);
  const [inputTranscript, setInputTranscript] = useState('');
  const [coachTurns, setCoachTurns] = useState([]);
  const [coachSpeaking, setCoachSpeaking] = useState(false);
  const [coachConnected, setCoachConnected] = useState(false);
  const [followupActive, setFollowupActive] = useState(false);

  // Audio and socket callbacks outlive renders, so everything they read lives in refs.
  const stateRef = useRef('idle');
  const socketRef = useRef(null);
  const recorderRef = useRef(null);
  const playerRef = useRef(null);
  const sessionIdRef = useRef(null);
  const streamingRef = useRef(false);
  const levelRef = useRef(0);
  const speechStartRef = useRef(0);
  const timersRef = useRef({});
  const newTurnRef = useRef(true);
  const recoveryTokenRef = useRef(0);

  const transition = useCallback((next) => {
    stateRef.current = next;
    setStateValue(next);
  }, []);

  const clearTimer = useCallback((name) => {
    const timer = timersRef.current[name];
    if (timer) {
      clearTimeout(timer);
      clearInterval(timer);
      delete timersRef.current[name];
    }
  }, []);

  const clearAllTimers = useCallback(() => {
    Object.keys(timersRef.current).forEach(clearTimer);
  }, [clearTimer]);

  const sendJson = useCallback((type) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type }));
      return true;
    }
    return false;
  }, []);

  const closeSocket = useCallback(() => {
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      try {
        socket.close(1000);
      } catch {
        // Already closing.
      }
    }
    streamingRef.current = false;
    setCoachConnected(false);
    setFollowupActive(false);
  }, []);

  const stopMic = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    levelRef.current = 0;
    setMic({ status: 'off', code: null });
  }, []);

  const closePlayer = useCallback(() => {
    playerRef.current?.close();
    playerRef.current = null;
    setCoachSpeaking(false);
  }, []);

  const ensurePlayer = useCallback(() => {
    if (!playerRef.current) playerRef.current = new CoachPlayer({ onPlayingChange: setCoachSpeaking });
    playerRef.current.unlock();
    return playerRef.current;
  }, []);

  const fail = useCallback(
    (key, fallbackMessage) => {
      recoveryTokenRef.current += 1;
      clearAllTimers();
      closeSocket();
      stopMic();
      closePlayer();
      const friendlyError = friendly(key, fallbackMessage);
      logger.warn('Live session failed', { code: friendlyError.code });
      setError(friendlyError);
      transition('error');
    },
    [clearAllTimers, closeSocket, closePlayer, stopMic, transition],
  );

  const armIdleTimer = useCallback(() => {
    clearTimer('idle');
    timersRef.current.idle = setTimeout(() => {
      if (stateRef.current !== 'feedback') return;
      sendJson('end_session');
      closeSocket();
      stopMic();
      playerRef.current?.flush();
      setNotice('We ended the coach chat after a few quiet minutes, to save your daily stage time.');
      transition('done');
    }, FEEDBACK_IDLE_MS);
  }, [clearTimer, closeSocket, sendJson, stopMic, transition]);

  const acceptResult = useCallback(
    (nextResult) => {
      recoveryTokenRef.current += 1;
      clearTimer('watchdog');
      setResult(nextResult);
      if (stateRef.current === 'error' || stateRef.current === 'done') return;
      transition('feedback');
      armIdleTimer();
    },
    [armIdleTimer, clearTimer, transition],
  );

  /** The result message never came, so ask REST. The server keeps scoring after a disconnect. */
  const recoverResult = useCallback(async () => {
    const token = ++recoveryTokenRef.current;
    clearTimer('watchdog');
    for (let attempt = 0; attempt < RECOVERY_MAX_ATTEMPTS; attempt++) {
      if (token !== recoveryTokenRef.current) return;
      try {
        const session = await fetchSession(sessionIdRef.current);
        if (token !== recoveryTokenRef.current) return;
        if (session.status === 'completed' || session.status === 'too_short') {
          // Rewards were sent only over the socket. They are saved, just not available to reveal.
          acceptResult({ session, qualified: session.status === 'completed', disqualified_reason: null, rewards: null, recovered: true });
          return;
        }
        if (session.status === 'abandoned') {
          fail('disconnected');
          return;
        }
      } catch (err) {
        if (err.status === 401 || err.status === 404) {
          fail(err.status === 401 ? 4401 : 4404);
          return;
        }
      }
      await new Promise((resolve) => setTimeout(resolve, RECOVERY_POLL_MS));
    }
    if (token === recoveryTokenRef.current) fail('analysis_timeout');
  }, [acceptResult, clearTimer, fail]);

  const enterAnalyzing = useCallback(() => {
    streamingRef.current = false;
    clearTimer('tick');
    transition('analyzing');
    clearTimer('watchdog');
    timersRef.current.watchdog = setTimeout(recoverResult, ANALYSIS_WATCHDOG_MS);
  }, [clearTimer, recoverResult, transition]);

  /**
   * Browsers report 1006 when a server rejects the upgrade before accepting it, which hides the
   * real close code. Work out the likely reason from REST so the message is still specific.
   */
  const diagnoseFailedConnect = useCallback(async () => {
    try {
      await fetchMe();
    } catch (err) {
      return err.status === 401 ? 4401 : 'connect_failed';
    }
    try {
      const health = await fetchHealth();
      if (health && health.coach_available === false) return 4503;
    } catch {
      return 'connect_failed';
    }
    try {
      const session = await fetchSession(sessionIdRef.current);
      if (session.status !== 'created') return 4409;
    } catch (err) {
      if (err.status === 404) return 4404;
    }
    return 'connect_failed';
  }, []);

  const handleServerMessage = useCallback(
    (message) => {
      switch (message.type) {
        case 'ready':
          clearTimer('ready');
          setConfig((prev) => ({
            demo: Boolean(message.demo),
            maxSpeechSeconds: message.max_speech_seconds ?? prev.maxSpeechSeconds,
            targetSeconds: message.target_seconds ?? prev.targetSeconds,
          }));
          setCoachConnected(true);
          if (stateRef.current === 'connecting') transition('ready');
          break;
        case 'speech_limit_reached':
          if (stateRef.current === 'speaking') {
            setNotice("You reached the longest speech we can score in one take, so we've wrapped it up for you.");
            enterAnalyzing();
          }
          break;
        case 'input_transcript':
          setInputTranscript((prev) => prev + (message.text ?? ''));
          break;
        case 'output_transcript': {
          const text = message.text ?? '';
          const startNew = newTurnRef.current;
          newTurnRef.current = false;
          setCoachTurns((turns) => (startNew || turns.length === 0 ? [...turns, text] : [...turns.slice(0, -1), turns[turns.length - 1] + text]));
          break;
        }
        case 'turn_complete':
          newTurnRef.current = true;
          break;
        case 'interrupted':
          playerRef.current?.flush();
          newTurnRef.current = true;
          break;
        case 'analysis_started':
          // The server can start scoring by itself, so make sure the UI follows.
          if (stateRef.current === 'speaking') enterAnalyzing();
          if (stateRef.current === 'analyzing' && message.budget_seconds) {
            clearTimer('watchdog');
            timersRef.current.watchdog = setTimeout(recoverResult, message.budget_seconds * 1000 + ANALYSIS_WATCHDOG_MARGIN_MS);
          }
          break;
        case 'session_result':
          acceptResult(message.result);
          break;
        case 'error':
          if (!message.fatal) {
            setNotice(message.message ?? null);
          } else if (stateRef.current === 'analyzing') {
            // The speech is already with the server, so this is not the end of the road for it.
            recoverResult();
          } else if (stateRef.current === 'feedback') {
            setNotice('Your coach has left the stage. Your scores are safe.');
          } else {
            fail(message.code ?? 'unknown', message.message);
          }
          break;
        default:
          logger.debug('Unknown live message', { type: message.type });
      }
    },
    [acceptResult, clearTimer, enterAnalyzing, fail, recoverResult, transition],
  );

  const handleClose = useCallback(
    async (event, opened) => {
      socketRef.current = null;
      streamingRef.current = false;
      setCoachConnected(false);
      setFollowupActive(false);
      clearTimer('ready');
      const current = stateRef.current;
      const knownCode = LIVE_ERRORS[event.code] ? event.code : null;

      if (current === 'connecting') {
        fail(knownCode ?? (opened ? 'connect_failed' : await diagnoseFailedConnect()));
      } else if (current === 'ready' || current === 'speaking') {
        fail(knownCode ?? 'disconnected');
      } else if (current === 'analyzing') {
        recoverResult();
      } else if (current === 'feedback') {
        clearTimer('idle');
        setNotice('Your coach has left the stage. Your scores are safe, and you can start another take any time.');
      }
    },
    [clearTimer, diagnoseFailedConnect, fail, recoverResult],
  );

  /** Start the mic from a click. Also unlocks coach audio, since this click is a user gesture. */
  const startMic = useCallback(async () => {
    ensurePlayer();
    if (recorderRef.current) return true;
    setMic({ status: 'requesting', code: null });
    const recorder = new MicRecorder({
      onFrame: (pcm) => {
        const socket = socketRef.current;
        if (streamingRef.current && socket?.readyState === WebSocket.OPEN) socket.send(pcm);
      },
      onLevel: (rms) => {
        levelRef.current = rms;
      },
      onEnded: () => {
        recorderRef.current?.stop();
        recorderRef.current = null;
        levelRef.current = 0;
        setMic({ status: 'error', code: 'lost' });
        if (stateRef.current === 'speaking') {
          // Score what we have. Throwing the take away would punish an unplugged headset.
          setNotice('Your microphone disconnected, so we ended your speech there and scored what we heard.');
          sendJson('speech_end');
          enterAnalyzing();
        }
      },
    });
    recorderRef.current = recorder;
    try {
      await recorder.start();
      if (recorderRef.current === recorder) setMic({ status: 'on', code: null });
      return true;
    } catch (err) {
      recorderRef.current = null;
      setMic({ status: 'error', code: err instanceof MicError ? err.code : 'unknown' });
      return false;
    }
  }, [ensurePlayer, enterAnalyzing, sendJson]);

  /** Open the socket for a created session. The caller should keep this inside a click's task chain. */
  const connect = useCallback(
    (sessionId, targetSeconds) => {
      ensurePlayer();
      closeSocket();
      recoveryTokenRef.current += 1;
      clearAllTimers();
      sessionIdRef.current = sessionId;
      newTurnRef.current = true;
      setError(null);
      setNotice(null);
      setResult(null);
      setElapsed(0);
      setInputTranscript('');
      setCoachTurns([]);
      setConfig((prev) => ({ ...prev, demo: false, targetSeconds }));
      transition('connecting');

      let opened = false;
      const socket = new WebSocket(liveSocketUrl(sessionId));
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;
      socket.onopen = () => {
        opened = true;
      };
      socket.onmessage = ({ data }) => {
        if (socketRef.current !== socket) return;
        if (typeof data !== 'string') {
          playerRef.current?.enqueue(data);
          return;
        }
        try {
          handleServerMessage(JSON.parse(data));
        } catch (err) {
          logger.warn('Bad live message', { name: err?.name });
        }
      };
      socket.onclose = (event) => {
        if (socketRef.current === socket) handleClose(event, opened);
      };
      timersRef.current.ready = setTimeout(() => {
        if (stateRef.current === 'connecting') fail('connect_timeout');
      }, READY_TIMEOUT_MS);
    },
    [clearAllTimers, closeSocket, ensurePlayer, fail, handleClose, handleServerMessage, transition],
  );

  const startSpeech = useCallback(() => {
    if (stateRef.current !== 'ready' || !sendJson('speech_start')) return;
    playerRef.current?.flush();
    speechStartRef.current = performance.now();
    streamingRef.current = true;
    setElapsed(0);
    transition('speaking');
    timersRef.current.tick = setInterval(() => {
      const seconds = Math.floor((performance.now() - speechStartRef.current) / 1000);
      setElapsed((prev) => (prev === seconds ? prev : seconds));
    }, 200);
  }, [sendJson, transition]);

  const finishSpeech = useCallback(() => {
    if (stateRef.current !== 'speaking') return;
    sendJson('speech_end');
    enterAnalyzing();
  }, [enterAnalyzing, sendJson]);

  const startFollowup = useCallback(() => {
    if (stateRef.current !== 'feedback' || streamingRef.current) return;
    // Barge-in: the coach stops at once, then the server is told, so the two never talk over each other.
    playerRef.current?.flush();
    if (!sendJson('followup_start')) return;
    newTurnRef.current = true;
    streamingRef.current = true;
    clearTimer('idle');
    setFollowupActive(true);
  }, [clearTimer, sendJson]);

  const endFollowup = useCallback(() => {
    if (!streamingRef.current || stateRef.current !== 'feedback') return;
    streamingRef.current = false;
    sendJson('followup_end');
    setFollowupActive(false);
    armIdleTimer();
  }, [armIdleTimer, sendJson]);

  /** The user is finished with the coach. Keeps the result on screen. */
  const endSession = useCallback(() => {
    sendJson('end_session');
    clearAllTimers();
    closeSocket();
    stopMic();
    playerRef.current?.flush();
    if (stateRef.current === 'feedback') transition('done');
  }, [clearAllTimers, closeSocket, sendJson, stopMic, transition]);

  /** Back to idle. `keepMic` lets "Try again" skip the mic check. */
  const reset = useCallback(
    ({ keepMic = false } = {}) => {
      recoveryTokenRef.current += 1;
      sendJson('end_session');
      clearAllTimers();
      closeSocket();
      playerRef.current?.flush();
      if (!keepMic) stopMic();
      setError(null);
      setNotice(null);
      setResult(null);
      setElapsed(0);
      setInputTranscript('');
      setCoachTurns([]);
      transition('idle');
    },
    [clearAllTimers, closeSocket, sendJson, stopMic, transition],
  );

  // Release the mic, audio contexts and socket when leaving the page.
  useEffect(
    () => () => {
      recoveryTokenRef.current += 1;
      clearAllTimers();
      closeSocket();
      recorderRef.current?.stop();
      recorderRef.current = null;
      playerRef.current?.close();
      playerRef.current = null;
      stateRef.current = 'idle';
    },
    [clearAllTimers, closeSocket],
  );

  // Closing the tab mid-speech loses the take, so ask first.
  useEffect(() => {
    if (state !== 'speaking') return undefined;
    const warn = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [state]);

  return {
    state,
    mic,
    error,
    notice,
    config,
    elapsed,
    result,
    inputTranscript,
    coachTurns,
    coachSpeaking,
    coachConnected,
    followupActive,
    levelRef,
    startMic,
    stopMic,
    unlockAudio: ensurePlayer,
    connect,
    startSpeech,
    finishSpeech,
    startFollowup,
    endFollowup,
    endSession,
    reset,
    dismissNotice: useCallback(() => setNotice(null), []),
  };
}
