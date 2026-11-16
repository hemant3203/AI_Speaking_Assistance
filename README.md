# Spotlight

A gamified AI public speaking coach. Give a speech into your microphone, hear live spoken feedback from a
Gemini coach, then get a scorecard, XP, streaks, badges and charts that show where to improve.

| Part | Stack | URL |
|---|---|---|
| Frontend | React, Tailwind CSS, nginx | http://localhost:1201 |
| Backend | Python, FastAPI | http://localhost:1200 (API docs at `/docs`) |
| Database | PostgreSQL 17 | `localhost:1202` (the backend uses `db:5432` inside Docker) |
| Coach | Gemini Live API (`gemini-3.8-live`) | Called only by the backend |

## Run it

You need Docker Desktop.

1. If `.env` doesn't exist, copy `.env.example` to `.env`, then set `GEMINI_API_KEY`, `JWT_SECRET` and the database password.
2. Start the app:

   ```
   docker compose up --build -d
   ```

3. Open http://localhost:1201, create an account and allow microphone access.

To stop it, run `docker compose down`. Your data stays in the `spotlight-data` Docker volume.
`docker compose down -v` deletes it permanently.

**Use `http://localhost:1201`.** Browsers only allow microphone access on `localhost` or HTTPS.

## Deploy for free

`docs/DEPLOY-RENDER.md` deploys the whole app as one free Render web service with a free Neon database.

## Project layout

```
backend/    FastAPI app: routes, services (live, analysis, gamification), models, tests
frontend/   React app, nginx config
deploy/     render/: one-container image for single-service hosts such as Render
docs/       ARCHITECTURE.md: system design and the full API contract. DEPLOY-RENDER.md: hosting guide
logs/       Log files, created when the backend starts
```

## Logs

| File | Contents |
|---|---|
| `logs/app.log` | General application events |
| `logs/error.log` | Errors only. Check this first when something breaks |
| `logs/access.log` | One line per API request |
| `logs/client.log` | Errors reported by users' browsers |

Files rotate at 10 MB and 5 backups are kept. Passwords, keys, audio and transcripts are never logged.
`docker compose logs -f` shows live container output.

## Tests

The tests need a real PostgreSQL, because they exercise row locks and constraints. They erase the database they
run on, so they use a throwaway one on its own network and never touch `spotlight-data`:

```
docker build -t spotlight-backend ./backend
docker network create spotlight-test
docker run -d --name spotlight-test-db --network spotlight-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=spotlight_test postgres:17-alpine
docker exec spotlight-test-db sh -c "until pg_isready -h 127.0.0.1 -U postgres -d spotlight_test; do sleep 1; done"
docker run --rm --network spotlight-test -e TEST_DATABASE_URL=postgresql+psycopg://postgres:test@spotlight-test-db:5432/spotlight_test spotlight-backend sh -c "pip install -q --user -r requirements-dev.txt && python -m pytest"
docker rm -f spotlight-test-db && docker network rm spotlight-test
```

## Practice options

- **Languages:** English and Hindi. The coach, feedback and suggested topics all follow your choice.
- **Length:** 1, 2, 3, 5, 10 or 15 minutes. A speech stops automatically at 15 minutes.
- **Topic:** pick a suggestion, type your own, or choose Free talk and speak about anything.
- **Daily limit:** 30 minutes of coach time per user (`DAILY_LIVE_SECONDS_PER_USER`), because everyone shares one key.

Past about 7 minutes, spoken feedback starts after scoring rather than right away. `docs/ARCHITECTURE.md` explains why.

## Admin account

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`, then run `docker compose up -d`. The admin gets a free shop and no
daily limit, though their practice still uses your Gemini key. To change the password, edit it in `.env` and run the
same command. There is one admin, and removing these settings removes admin rights.

## Demo mode

Set `LIVE_PROVIDER=mock` in `.env` to run the whole flow without a Gemini key or any API cost. The coach and scores
are canned and the app shows a "Demo mode" banner. Never use this for real users.

## Before you put this online

- **Serve it over HTTPS** and set `COOKIE_SECURE=true`. The microphone will not work otherwise.
- **Update these settings:** set `BIND_ADDRESS=0.0.0.0` and add your domain to `ALLOWED_ORIGINS`.
- **Use a paid Gemini tier.** On the free tier, Google may use submitted content to improve its products, and the
  free tier has limits on where it can be offered. Check [Google's terms](https://ai.google.dev/gemini-api/terms).
- **Check the cost guards.** Every user shares one key, so review `DAILY_LIVE_SECONDS_PER_USER` and
  `MAX_CONCURRENT_LIVE_SESSIONS`.
- **Back up the database.** Your data lives in the `spotlight-data` volume, so schedule regular `pg_dump` backups.
- **Add password reset.** It isn't built yet.

## Roadmap

- Users add their own Gemini API key (the Settings page shows this as coming soon)
- Password reset by email
- Leaderboards
- Camera-based posture feedback
