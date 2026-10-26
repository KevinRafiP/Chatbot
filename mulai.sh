#!/bin/sh
# agent hanya mendengar 127.0.0.1, jadi tidak bisa diakses dari internet, hanya oleh backend di container yang sama
cd /srv/agent && BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:${APP_PORT:-${PORT:-8080}}} AGENT_HOST=127.0.0.1 AGENT_PORT=8082 python -u main.py &
cd /srv && exec ./app