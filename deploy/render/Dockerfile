# One container for hosts that run a single service, such as Render's free plan: nginx serves the React
# app and proxies /api/ to uvicorn on loopback. Local development keeps using docker-compose.yml.
# Build from the repository root: docker build -f deploy/render/Dockerfile .

FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

# FORWARDED_ALLOW_IPS trusts only nginx, on loopback, to report the visitor's address.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    PORT=10000

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 spotlight

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=frontend /app/dist /usr/share/nginx/html

# Reuse the compose site config, so headers, caching and WebSocket timeouts stay identical. Only the
# listen port (filled in at start from $PORT) and the backend address (uvicorn on loopback) change.
# The greps fail the build if the frontend config changes shape and a substitution stops matching.
COPY frontend/nginx.conf /etc/spotlight/site.conf.template
COPY deploy/render/nginx.conf /etc/spotlight/nginx.conf
COPY deploy/render/start.sh /usr/local/bin/spotlight-start
RUN sed -i \
        -e 's/listen 1201;/listen __PORT__;/' \
        -e '/listen \[::\]:1201;/d' \
        -e '/resolver 127.0.0.11/d' \
        -e 's#http://backend:1200#http://127.0.0.1:1200#' \
        /etc/spotlight/site.conf.template \
    && grep -q 'listen __PORT__;' /etc/spotlight/site.conf.template \
    && grep -q 'http://127.0.0.1:1200' /etc/spotlight/site.conf.template \
    && ! grep -q 'backend:1200' /etc/spotlight/site.conf.template \
    && tr -d '\015' < /usr/local/bin/spotlight-start > /tmp/start && mv /tmp/start /usr/local/bin/spotlight-start \
    && chmod +x /usr/local/bin/spotlight-start \
    && mkdir -p /app/logs && chown -R spotlight:spotlight /app/logs

USER spotlight
EXPOSE 10000
CMD ["spotlight-start"]
