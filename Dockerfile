# Satu service Render: backend Go dan agent Python dalam satu container, agar jatah 750 jam cukup untuk hidup 24 jam
FROM golang:1.26-alpine AS backend
WORKDIR /src
COPY backend/ .
RUN go build -tags netgo -ldflags '-s -w' -o /app ./cmd/chatbot

FROM python:3.13-slim
WORKDIR /srv
COPY agent/ agent/
COPY --from=backend /app ./app
COPY mulai.sh .
CMD ["sh", "mulai.sh"]