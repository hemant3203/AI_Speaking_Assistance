# Deploying Spotlight on Render (free)

The whole app runs as **one free Render web service**: nginx serves the React app and proxies `/api/` to the
backend, inside one container (`deploy/render/Dockerfile`). The database is a **free Neon Postgres**, because
Render's free Postgres is deleted after 30 days. A free **cron-job.org** ping every 10 minutes stops the service
from sleeping.

Local development is unchanged: `docker compose up --build -d` still runs the three-container setup.

## 1. Put the code on GitHub

Render deploys from a Git repository. Use a **private** repository. `.env` is in `.gitignore`, so your keys stay
on your machine; check that `git status` doesn't list it before you commit.

```
git init
git add .
git commit -m "Spotlight"
```

Create an empty private repository on GitHub, then run the two commands GitHub shows under "push an existing
repository" (`git remote add origin ...` and `git push -u origin main`).

## 2. Create the database on Neon

1. Sign up at https://neon.tech (no card needed).
2. Create a project. Choose Postgres 17 and the region **AWS Asia Pacific (Singapore)**, the same region as the
   Render service in `render.yaml`.
3. Click **Connect**. Turn **Connection pooling off**, so you get the direct connection string, and copy it. It
   looks like `postgresql://user:password@ep-....ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
4. Change the start from `postgresql://` to `postgresql+psycopg://`. Keep everything else, including
   `?sslmode=require`. This is your `DATABASE_URL`.

The app creates its tables itself on first start.

## 3. Create the service on Render

1. If Render is showing "Create a new Postgres", click **Skip**. Don't create a Render Postgres.
2. Click **New**, then **Blueprint**, connect your GitHub account, and pick the repository. Render reads
   `render.yaml` and plans one free web service called `spotlight`.
3. Fill in the values it asks for:
   - `DATABASE_URL`: the Neon string from step 2
   - `GEMINI_API_KEY`: your key
   - `ADMIN_EMAIL` and `ADMIN_PASSWORD`: optional, leave empty for no admin
   
   `JWT_SECRET` is generated for you, and `COOKIE_SECURE` is already `true`.
4. Click **Apply**. The first build takes about 5 to 10 minutes.

**Without the Blueprint**, use New, then Web Service, with these settings:
- Language: Docker
- Dockerfile path: `./deploy/render/Dockerfile`
- Docker build context: `.`
- Region: Singapore
- Instance type: Free
- Health check path (under Advanced): `/api/v1/ping`
- Environment variables: the same as step 3, plus `JWT_SECRET` set to a random string of at least 32 characters
  and `COOKIE_SECURE=true`.

## 4. Check it works

- Open `https://<your-service>.onrender.com/api/v1/health`. It should say `"status":"ok"` and `"database":"ok"`.
- Open `https://<your-service>.onrender.com`, create an account and allow the microphone.

`ALLOWED_ORIGINS` is filled in automatically from Render's public URL. If you add your own domain later, set
`ALLOWED_ORIGINS` to a comma-separated list of both URLs.

## 5. Keep it awake with a cron ping

Render's own **Cron Jobs** aren't part of the free plan, so use a free outside service:

1. Sign up at https://cron-job.org.
2. Create a cronjob with the URL `https://<your-service>.onrender.com/api/v1/ping`, scheduled **every 10 minutes**.
3. Save it, then use "Test run". A `204` response means it worked.

UptimeRobot (an HTTP monitor every 5 minutes) works the same way and also emails you if the site goes down.

Always ping `/api/v1/ping`, never `/api/v1/health`. `/ping` doesn't touch the database, so Neon can sleep
between real users and stay inside its free compute hours. Pinging `/health` would use them up in a few days.

## Limits to know

- **Free hours:** 750 a month per workspace, and one always-awake service uses about 730. Don't add other free
  services to the same workspace, or they'll share these hours and everything stops near the end of the month.
- **Deploys and restarts** end any live speech in progress. Each `git push` redeploys automatically.
- **Logs** are in the service's Logs tab on Render. The files in `/app/logs` reset on every restart.
- **Gemini cost** doesn't depend on hosting. `DAILY_LIVE_SECONDS_PER_USER` (30 minutes) is the cost guard, because
  every user shares your key.
