# Spotlight: AI public speaking coach

Architecture and API contract. This file is the source of truth shared by the
backend and frontend. Change the contract here first, then the code.

## 1. System overview

```
Browser (React)                 frontend container :1201            backend container :1200
  mic -> AudioWorklet -> WS  ->  nginx  /api/* (incl. WS upgrade) -> FastAPI -> Gemini Live API
  speaker <- PCM 24k     <- WS <-                                  -> Gemini analysis model
                                                                   -> PostgreSQL (db container)
```

- The browser only ever talks to its own origin (`http://localhost:1201`). nginx proxies `/api/*`
  to `backend:1200`. Port 1200 is also published, for `/docs` and direct API use.
- The Gemini key lives only in the backend. It never reaches the browser.
- Auth is an httpOnly, SameSite=Lax JWT cookie named `spotlight_session`. The WebSocket uses the
  same cookie and additionally validates the `Origin` header against `ALLOWED_ORIGINS`.
- Audio is held in memory for analysis and discarded. It is never written to disk.

### Environment variables (`.env` at the repo root)

| Name | Default | Purpose |
|---|---|---|
| `APP_ENV` | `production` | |
| `LOG_LEVEL` | `INFO` | |
| `GEMINI_API_KEY` | empty | Shared server key. Empty means the coach is unavailable, the rest of the app still works |
| `GEMINI_LIVE_MODEL` | `gemini-3.8-live` | |
| `GEMINI_ANALYSIS_MODEL` | `gemini-3.6-flash` | First choice for scoring. Stable, and it worked when `gemini-3.8-flash` kept returning 503 |
| `GEMINI_ANALYSIS_FALLBACK_MODELS` | `gemini-3.5-flash-lite,gemini-3.1-flash-lite` | Tried in order on 429/5xx |
| `LIVE_PROVIDER` | `gemini` | `gemini` or `mock`. `mock` is for tests and demos and needs no key |
| `JWT_SECRET` | required, min 32 chars | Refuse to start without it |
| `JWT_EXPIRE_DAYS` | `7` | |
| `COOKIE_SECURE` | `false` | Must be `true` behind HTTPS |
| `ALLOWED_ORIGINS` | `http://localhost:1201,http://127.0.0.1:1201` | CORS and WS origin allow-list |
| `DATABASE_URL` | required | `postgresql+psycopg://user:pass@db:5432/spotlight`. Keep `db:5432` here: 1202 is only the port published on the host, for local tools |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | required | Used by the `db` container |
| `LOG_DIR` | `/app/logs` | |
| `DAILY_LIVE_SECONDS_PER_USER` | `1800` | Cost guard, because the key is shared. The admin is exempt |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | empty | The one admin account, created or updated at startup. Admins get a free shop and no daily limit |
| `MAX_CONCURRENT_LIVE_SESSIONS` | `5` | Process-wide. In testing, this key rejected the 7th simultaneous Live session with `1011 quota` |
| `LIVE_MAX_SESSION_SECONDS` | `1500` | Hard stop for one WS. nginx's proxy timeouts must stay longer than this. Gemini's own limit is about 8 minutes until its first reply; see "Long speeches" |
| `MAX_SPEECH_SECONDS` | `300` | Keeps the inline WAV under Gemini's request size limit |

## 2. Verified Gemini behaviour (tested against the real API on 2026-11-05)

SDK: `google-genai` 2.34.0. Do not "fix" these from memory.

```python
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction="...",
    speech_config={"voice_config": {"prebuilt_voice_config": {"voice_name": "Kore"}}},
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    realtime_input_config={"automatic_activity_detection": {"disabled": True}},
)
async with client.aio.live.connect(model="gemini-3.8-live", config=config) as session:
    await session.send_realtime_input(activity_start=types.ActivityStart())
    await session.send_realtime_input(audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000"))
    await session.send_realtime_input(activity_end=types.ActivityEnd())
```

- **`session.receive()` stops after each turn.** Wrap it: `while True: async for msg in session.receive(): ...`
- **Manual VAD works.** The coach stayed silent through a 2 second pause and replied only after
  `activity_end`, with first audio about 0.7 s later. That is what stops it interrupting a speech.
- **An idle session closes after 120 s** with `1008 Session closed due to client inactivity`. WebSocket pings don't
  reset the timer. A short burst of silent audio does and doesn't trigger a reply, so the bridge sends one every 30 s
  outside a speech or follow-up.
- **Input transcription removes fillers.** "Um... like... uh" came back without them, so the live
  transcript is NOT usable for filler counting. Use the analysis model's verbatim transcript.
- **Input transcription may only arrive at the end of the turn**, not incrementally. The UI must not
  depend on live captions while the user is speaking.
- Model audio is `audio/pcm;rate=24000`, in `part.inline_data.data` under `server_content.model_turn.parts`.
  Transcripts are in `server_content.input_transcription.text` and `.output_transcription.text`.
- **Gemini 3.8 Live quirks:** proactive audio is permanently on (the model may choose silence, so never
  block on a reply and never set `proactive_audio`), `thinkingLevel` and `enable_affective_dialog` must be
  omitted, and language can't be set by code, only restricted through the system instruction.
- **Verbatim transcription works:** `gemini-3.6-flash`, `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` all kept um/uh/like with a JSON schema.
- **Models disagree on subjective scores:** one speech scored structure 50, 75 and 90 across those three models, so each session records `analysis_model`.
- **Analysis models can return 503 "high demand".** `gemini-3.8-flash` failed 3 of 3 tries, and others did intermittently in
  testing. Retry with backoff, walk the fallback list, cap the total at 60 s, then degrade (section 5).
- Analysis call: `client.aio.models.generate_content(model=..., contents=[types.Part.from_bytes(data=wav, mime_type="audio/wav"), prompt], config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema))`.

## 3. Conventions

- Base path `/api/v1`. JSON keys are `snake_case`. Timestamps are ISO-8601 UTC. Dates are `YYYY-MM-DD` in the user's timezone.
- Every error is `{"detail": "Human readable message", "code": "machine_code"}` with the right HTTP status.
  Validation errors are 422 with `code: "validation_error"` and `detail` holding the first message.
- Unauthenticated requests get 401 with `code: "not_authenticated"`. Another user's session is 404, never 403.

## 4. REST API

### Auth

| Method and path | Body | Response |
|---|---|---|
| `POST /auth/register` | `{email, password (8-128), display_name (2-40), timezone (IANA)}` | 201 `{user}` + cookie. 409 `email_taken` |
| `POST /auth/login` | `{email, password}` | 200 `{user}` + cookie. 401 `invalid_credentials`. 429 `too_many_attempts` |
| `POST /auth/logout` | | 204, clears cookie |
| `GET /auth/me` | | `{user}` |
| `PATCH /auth/me` | `{display_name?, timezone?}` | `{user}` |
| `DELETE /auth/me` | `{password}` | 204, deletes the user and all their data |

`user = {id, email, display_name, timezone, equipped_coach, created_at}`

### Practice

| Method and path | Notes |
|---|---|
| `GET /practice/catalog` | `{modes:[{id,name,description,icon,topics:[string],topics_hi:[string]}], durations:[60,120,180,300,600,900], languages:[{id,name}]}` |
| `POST /practice/sessions` | Body `{mode, topic (3-200), target_seconds, language}`, or `free_talk:true` in place of `topic` for a speech on any subject: nothing is marked down for its subject, and `topic` becomes `Free talk: <subject>` once scored. `retry_of:<session id>` makes a second take: the server copies that completed session's mode, topic, language and free talk, and 404s `session_not_found` if it isn't the user's own completed session. `challenge:true` takes on today's challenge: the server sets mode and topic, and `target_seconds` must be 180 or 300 (else 422). 201 `SessionDetail` with `status:"created"`. 429 `daily_limit_reached`. 503 `coach_unavailable` |
| `GET /practice/sessions?limit=20&offset=0&mode=` | `{items:[SessionSummary], total}`, newest first, excludes `created` and `abandoned` |
| `GET /practice/sessions/{id}` | `SessionDetail` |
| `DELETE /practice/sessions/{id}` | 204. XP and badges already earned are kept |

Modes: `impromptu`, `presentation`, `interview`, `storytelling`, `persuasion`.
Languages: `en` English, `hi` Hindi. `topics` are the English suggestions and `topics_hi` the Hindi ones. Icons are lucide-react icon names.

`status`: `created`, `active`, `completed`, `too_short`, `abandoned`.

```jsonc
// SessionSummary
{"id":"uuid","mode":"impromptu","topic":"...","free_talk":false,"language":"en","status":"completed","started_at":"...","local_date":"2026-11-05",
 "speaking_seconds":118.4,"overall_score":74,"wpm":142.0,"filler_per_100":3.2,"xp_awarded":96,"sparks_awarded":10,
 "retry_of":null,"challenge_date":null}   // retry_of: the take this one tried to beat. challenge_date: set on a daily challenge

// SessionDetail = SessionSummary plus:
{"target_seconds":120,"coach_id":"mentor","ended_at":"...","word_count":280,"filler_count":9,
 "filler_breakdown":{"um":4,"like":5},"hedge_count":3,"pause_count":6,"longest_pause_seconds":2.1,
 "pause_ratio":0.12,"volume_variation":0.31,"vocabulary_ratio":0.54,
 "scores":{"pace":88,"fluency":72,"vocal_variety":65,"vocabulary":70,"confidence":75,
           "structure":80,"clarity":77,"engagement":68},   // the last 3 are null when ai_scored is false
 "ai_scored":true,"analysis_model":"gemini-3.6-flash","filler_counts_reliable":true,
 "feedback":{"summary":"...","strengths":["..."],"improvements":["..."],"next_drill":"...",
   "grammar":{"score":72,"issues":[{"said":"how it was happened","better":"how it happened","why":"...","type":"tense"}]}},
   // feedback is null when ai_scored is false. grammar is null on sessions scored before it existed.
   // type: tense|agreement|articles|prepositions|word_order|word_choice|plurals|sentence|other. At most 8 issues.
 "transcript":"...","coach_transcript":"...",
 "comeback":ComebackReward|null,"challenge":ChallengeReward|null}   // copied from the session's rewards once scored
```

### Gamification

`GET /gamification/profile`:

```jsonc
{"xp":1240,"level":5,"level_title":"Confident Speaker","xp_into_level":240,"xp_for_next_level":500,"sparks":85,
 "streak":{"current":6,"longest":12,"status":"at_risk","freezes":1,"practiced_today":false,"next_milestone":7,
           "week":[{"date":"2026-10-30","state":"practiced"}]},   // last 7 days; state: practiced|frozen|missed|today_pending
 "daily_quests":{"date":"2026-11-05","all_complete":false,"bonus_sparks":10,
   "items":[{"id":"warm_up","title":"Warm up","description":"Finish 1 session","icon":"Flame","progress":0,"target":1,"xp":15,"sparks":5,"completed":false}]},
 "stats":{"total_sessions":34,"total_speaking_seconds":4120,"best_score":91},
 "recent_badges":[Badge],"next_badge":Badge,
 "limits":{"daily_live_seconds":1800,"used_seconds":240,"remaining_seconds":1560},
 "daily_challenge":{"date":"2026-11-16","mode":"storytelling","mode_name":"Storytelling","topic":"...","topic_hi":"...",
   "options":[{"target_seconds":180,"min_seconds":144,"xp":40,"sparks":10},{"target_seconds":300,"min_seconds":240,"xp":70,"sparks":15}],
   "completed":false,"session_id":null,"score":null,"total_completed":3}}
```

Streak `status`: `active_today` (practised today), `at_risk` (practised yesterday, or within what freezes
can cover, and not yet today), `none` (no live streak). `current` is computed at read time, so a broken
streak shows 0 without any write.

- `GET /gamification/badges` returns `{items:[Badge]}`.
  `Badge = {id,name,description,icon,category,tier,target,progress,unlocked,unlocked_at,xp,sparks}`,
  `tier`: `bronze|silver|gold`.
- `GET /gamification/shop` returns `{sparks,items:[{id,kind,name,description,price,icon,owned,equipped,can_buy,reason}]}`.
  `kind`: `consumable|coach`. `reason` says why `can_buy` is false.
- `POST /gamification/shop/{item_id}/purchase` returns `{sparks,item}`. 402 `insufficient_sparks`, 409 `already_owned` or `limit_reached`.
- `POST /gamification/coaches/{coach_id}/equip` returns `{user}`. 403 `coach_locked`.
- `GET /gamification/activity?limit=20` returns `{items:[{created_at,reason,xp,sparks}]}`.

Rules:

- **Qualifying session:** at least 20 s of speech and at least 15 words. Otherwise `status:"too_short"` and no rewards.
- **XP:** `(20 + min(50, 10 * minutes spoken) + overall_score * 0.5 + 15 if personal best) * (1 + 0.05 * min(streak, 10))`, rounded.
- **Sparks:** 5, +5 for the first session of the day, +5 if score >= 80.
- **Levels:** cumulative XP to reach level L is `50 * L * (L - 1)`. Titles: 1 Nervous Newcomer, 2 Mic Checker,
  3 Warm-Up Act, 4 Steady Voice, 5 Confident Speaker, 6 Room Reader, 7 Crowd Pleaser, 8 Stage Regular,
  9 Keynote Speaker, 10+ Spotlight Legend.
- **Streak:** one per local day. A gap covered by freezes consumes them and continues the streak. Otherwise it
  resets to 1. Every 7-day milestone grants 1 free freeze (max 2 held).
- **Daily quests:** 3 per day, chosen deterministically from `hash(user_id, local_date)`, always including
  `warm_up`. Pool: finish 2 sessions, speak 3 minutes in total, score at least 70, a session with at most 3 fillers
  per 100 words, a session at 120-160 WPM, practise 2 different modes. They complete automatically. All 3 grant
  `bonus_sparks`.
- **Badges:** about 20 across streaks (3/7/30/100 days), volume (1/10/50 sessions, 60/300 minutes), skill
  (score 80/90, under 1 filler per 100 words, pace in band 5 times), variety (all modes), challenges (1/10 daily
  challenges, 1/10 comebacks), and level (5/10).
- **Grammar:** the analysis model also returns `grammar_score` and up to 8 `grammar_issues`, quoting the transcript so
  the UI can underline them. Grammar is shown separately and does not change `overall_score`.
- **Second takes (comebacks):** a session with `retry_of` is compared with that take. It earns 3 XP per overall point
  gained (max 45) plus 2 XP per grammar point gained (max 30), and 5 sparks for each that improved. Each take can be
  beaten for a bonus once (`comeback:<parent id>` ledger key), and at most 5 bonuses are paid per day. On a second take
  the live coach is told up to 5 of the earlier slips and says which were fixed.
- **Daily challenge:** one topic a day for everyone, walking a shuffled list of 30 so none repeats within a cycle. 3 minutes
  pays 40 XP and 10 sparks, 5 minutes 70 XP and 15 sparks, once per day (`challenge:<date>`), and needs at least 80% of the
  time spoken. A second take of today's challenge at 3 or 5 minutes can still complete it.
- **Shop:** `streak_freeze` (40 sparks, max 2 held). Coach personas are real unlocks that change the voice and
  feedback style: `mentor` (free, default, voice Kore), `hype` (60, Puck), `storyteller` (80, Aoede), `critic` (120, Charon).

### Analytics

`GET /analytics/overview?days=7|30|90|0` (0 means all time):

```jsonc
{"range_days":30,
 "summary":{"sessions":12,"speaking_seconds":1800,"avg_score":74,"best_score":88,"avg_wpm":141,"avg_filler_per_100":3.4,
            "deltas":{"sessions":3,"avg_score":6,"avg_wpm":-4,"avg_filler_per_100":-1.2}},  // vs the previous equal period; null when no previous data
 "score_trend":[{"session_id":"uuid","date":"2026-11-01","overall":70,"pace":80,"fluency":60,"vocal_variety":66,"vocabulary":70,"confidence":72,"structure":75,"clarity":71,"engagement":64}],
 "skills":[{"id":"pace","name":"Pace","description":"...","current":80,"previous":72,"delta":8,"samples":12}],
 "focus_areas":[{"skill":"fluency","name":"Fluency","score":60,"delta":-2,"why":"...","tip":"...","drill_mode":"impromptu"}],  // 3 weakest, tips reference the user's own numbers
 "strengths":[{"skill":"pace","name":"Pace","score":80}],
 "pace_trend":[{"session_id":"uuid","date":"2026-11-01","wpm":142}],"pace_band":{"low":120,"high":160},
 "filler_trend":[{"session_id":"uuid","date":"2026-11-01","per_100":3.2}],
 "top_fillers":[{"word":"um","count":30}],
 "modes":[{"mode":"impromptu","name":"Impromptu","sessions":5,"avg_score":71}],
 "heatmap":[{"date":"2026-05-10","sessions":1,"speaking_seconds":120}]}  // always the last 182 days, only active days
```

Empty data returns zeros, nulls and empty arrays, never an error.

### System

- `GET /api/v1/health` returns `{status, version, live_provider, coach_available, database}`. No auth.
- `POST /api/v1/client-logs` with `{level, message, context?}` returns 204. Auth required, rate limited,
  sanitised, written to `client.log`.

## 5. Live WebSocket: `WS /api/v1/live/{session_id}`

Close codes before accept or at start: `4401` not authenticated, `4403` bad origin, `4404` unknown session,
`4409` session not `created` or user already live, `4429` limit reached, `4503` coach unavailable.

**Client to server:** binary frames are PCM16 mono 16 kHz little-endian, at most 64 KB, even length. Dropped unless
a speech or follow-up is active. Text frames are JSON:

| type | Meaning |
|---|---|
| `speech_start` | Begin the graded speech. Sends `activity_start`. Allowed once |
| `speech_end` | End the speech. Sends `activity_end`, so the coach replies, and starts analysis |
| `followup_start` / `followup_end` | Ungraded question for the coach. Only after `speech_end`. Interrupts coach playback |
| `end_session` | User is done. Server closes with code 1000 |

**Server to client:** binary frames are PCM16 mono 24 kHz coach audio. Text frames are JSON:

| type | Payload | Meaning |
|---|---|---|
| `ready` | `{max_speech_seconds, target_seconds, demo}` | Gemini connected. `demo` is true for the mock provider |
| `speech_limit_reached` | | Server auto-ended the speech at `MAX_SPEECH_SECONDS` |
| `input_transcript` | `{text}` | Fragment of what the user said. May arrive only at the end |
| `output_transcript` | `{text}` | Fragment of the coach's words |
| `turn_complete` | | Coach finished a turn |
| `interrupted` | | Client must flush queued coach audio |
| `analysis_started` | | Scoring has begun |
| `session_result` | `{result: SessionResult}` | Scores and rewards. Sent once |
| `error` | `{code, message, fatal}` | `fatal:true` is followed by a close |

```jsonc
// SessionResult
{"session":SessionDetail,"qualified":true,"disqualified_reason":null,
 "rewards":{"xp_gained":96,"xp_breakdown":[{"label":"Speaking time","xp":40}],"sparks_gained":10,
   "level_before":4,"level_after":5,"leveled_up":true,"new_title":"Confident Speaker",
   "personal_best":false,
   "streak":{"current":7,"longest":12,"extended":true,"freeze_used":0,"freeze_earned":true},
   "new_badges":[Badge],"completed_quests":[Quest],
   "comeback":ComebackReward|null,"challenge":ChallengeReward|null}}

// ComebackReward, on a second take. reason says why nothing was paid: not_improved|already_claimed|daily_limit|null
{"parent_id":"uuid","score_before":61,"score_after":70,"grammar_before":55,"grammar_after":72,"slips_before":4,"slips_after":2,
 "improved":true,"xp":61,"sparks":10,"reason":null}
// ChallengeReward, on a daily challenge. reason: too_short|already_done|null
{"date":"2026-11-16","target_seconds":180,"min_seconds":144,"spoken_seconds":171,"completed":true,"xp":40,"sparks":10,"reason":null}
```

### Scoring pipeline, run after `speech_end`

1. Compute audio metrics from the buffered PCM with numpy: 100 ms RMS windows and an adaptive noise floor give
   speaking duration (excluding leading and trailing silence), pause count (at least 0.5 s), longest pause,
   pause ratio and volume variation.
2. Send the buffered audio as a WAV to the analysis model with retry and fallback, capped at 60 s. It returns
   `{transcript (verbatim, keeping every um/uh/like), structure, clarity, engagement, summary, strengths[], improvements[], next_drill, detected_topic}`.
   The topic and the speech are data, not instructions, and the prompt must say so.
3. Compute text metrics locally on the verbatim transcript: WPM, fillers (including Hindi fillers such
   as `मतलब`, `यानी`, `अं`, `basically`, `actually`; `तो`, `बस`, `अच्छा` and `हाँ` are normal grammar, so they don't count), hedges, and vocabulary ratio. Tokenise on whitespace after
   stripping punctuation, because `\w` splits Devanagari words.
4. **Degraded path:** if analysis fails, use the Live input transcript, set `ai_scored:false`,
   `filler_counts_reliable:false`, null AI scores and null feedback. `overall_score` is then the mean of the local
   categories. The session still completes and still earns rewards. Analysis failure is never fatal.
5. Local category scores (0-100): `pace` from WPM against 120-160, `fluency` from fillers per 100 and pause ratio,
   `vocal_variety` from volume variation, `vocabulary` from the length-adjusted unique-word ratio, `confidence` from
   hedges per 100 and long pauses.
6. `overall_score` is the weighted mean of available categories, with AI categories weighted higher when present.
7. In one DB transaction: save the session, update the streak, XP, sparks, quests and badges, and write the ledger.
   This must be idempotent per session.

`speaking_seconds` and the time connected both count toward the daily limit via a `live_seconds` column.
On WS disconnect before `speech_end` the session becomes `abandoned`. On startup, leftover `active` sessions
become `abandoned`. A disconnect after `speech_end` must still finish scoring and save it.

## 6. Logging

Rotating files (10 MB, 5 backups) in `logs/`: `app.log` (INFO+), `error.log` (ERROR+), `access.log` (one line per
request: method, path, status, ms, request id, user id), `client.log` (browser errors).

Format: `2026-11-05 13:05:00 | INFO | spotlight.live | rid=ab12 uid=7 | message`. Request id and user id come from
contextvars. Newlines in messages are escaped to prevent log injection.

**Never log** passwords, cookies, JWTs, API keys, audio or transcripts.

If `LOG_DIR` is not writable, fall back to stdout with a warning rather than crash.

## 7. Roadmap (not built yet)

- **Bring your own API key.** `services/live/credentials.py` resolves the key for a user. It returns the shared env
  key today, and is the single place to change. The Settings page shows a disabled "Coming soon" card.
- Password reset by email, leaderboards, camera-based posture feedback.

## Long speeches

Speeches can run up to 15 minutes (`MAX_SPEECH_SECONDS`, default 900), and two Gemini limits shape how:

- **Live:** a session is closed with 1008 about 481 s after connecting if the model hasn't replied yet, including
  mid-speech. Compression and resumption don't change that. The session's reply resets the risk: one was still open
  at 13:30 after replying at 7:50.
- **Scoring:** inline requests are limited to 20 MB, and 15 minutes of 16 kHz audio is about 29 MB.

So:

1. At 420 s after connecting (`_LIVE_UNANSWERED_LIMIT_SECONDS`), if the coach hasn't replied, the bridge closes it.
   The speech keeps recording in the backend. A coach lost unexpectedly mid-speech is treated the same way.
2. When the speech ends, it is scored first. Audio over 12 MB goes through the Files API and is deleted afterwards.
   The time limits grow with the speech, and `analysis_started` tells the client the budget.
3. A fresh Live session gets the verbatim transcript as text and speaks the feedback, then takes follow-ups.

The voice is always Gemini Live, but on long speeches it starts after scoring rather than about a second after the
speech ends. If scoring fails too there may be no transcript, so the scorecard appears without spoken feedback.
