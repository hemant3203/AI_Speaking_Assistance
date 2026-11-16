FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    FORWARDED_ALLOW_IPS=*

WORKDIR /app

RUN useradd --create-home --uid 10001 spotlight

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini pytest.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

RUN mkdir -p /app/logs && chown -R spotlight:spotlight /app/logs

USER spotlight
EXPOSE 1200

# FORWARDED_ALLOW_IPS=* trusts X-Forwarded-For because nginx, on a container IP that isn't known in
# advance, is the only public entry point. Port 1200 is published on loopback by default.
# compose's healthcheck already guarantees the database is up before this runs.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 1200 --workers 1 --proxy-headers --no-access-log --ws-max-size 1048576"]
