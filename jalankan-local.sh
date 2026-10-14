#!/usr/bin/env bash
# Membaca NGROK_PATH, NGROK_DOMAIN, dan GERBANG_LOCAL_PORT dari backend/.env, lalu menjalankan gerbang local dan ngrok
cd "$(dirname "$0")/backend" || exit 1
ambil() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r'; }
NGROK="$(ambil NGROK_PATH)"; NGROK="${NGROK:-ngrok}"
DOMAIN="$(ambil NGROK_DOMAIN)"
PORT="$(ambil GERBANG_LOCAL_PORT)"; PORT="${PORT:-8090}"
go run ./cmd/gerbang-local &
trap 'kill $!' EXIT
"$NGROK" http --url="$DOMAIN" "$PORT"