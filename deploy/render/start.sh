#!/bin/bash
# Runs the backend and nginx in one container. If either stops, the other is stopped too and the
# container exits, so the host restarts the whole thing rather than serving half an app.
set -euo pipefail

# Render gives every web service its public URL. Use it as the allowed origin unless one is set.
if [ -z "${ALLOWED_ORIGINS:-}" ] && [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
    export ALLOWED_ORIGINS="$RENDER_EXTERNAL_URL"
fi

sed "s/__PORT__/${PORT:-10000}/" /etc/spotlight/site.conf.template > /tmp/spotlight-site.conf
# -e: the packaged default error log is under /var/log, which this unprivileged user can't write.
nginx -t -q -e /dev/stderr -c /etc/spotlight/nginx.conf

alembic upgrade head

uvicorn app.main:app --host 127.0.0.1 --port 1200 --workers 1 --proxy-headers \
    --no-access-log --ws-max-size 1048576 &
backend=$!
nginx -e /dev/stderr -c /etc/spotlight/nginx.conf -g 'daemon off;' &
proxy=$!

# On a deploy or restart, give uvicorn its graceful shutdown, which finishes scoring in progress.
trap 'kill -TERM "$backend" "$proxy" 2>/dev/null' TERM INT

set +e
wait -n "$backend" "$proxy"
status=$?
kill -TERM "$backend" "$proxy" 2>/dev/null
wait
exit "$status"
