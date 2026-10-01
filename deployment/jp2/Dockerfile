# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg libasound2 libssl3 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY config ./config
COPY prompts ./prompts
COPY schemas ./schemas
COPY scripts ./scripts
COPY tests ./tests
COPY migrations ./migrations
COPY run.py ./run.py
RUN mkdir -p /app/storage/database /app/storage/logs /app/storage/outputs /app/storage/uploads /app/storage/grammar
EXPOSE 5000
CMD ["waitress-serve", "--listen=127.0.0.1:5000", "run:app"]

FROM caddy:2.10-alpine AS web
COPY deployment/jp2/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/frontend/dist /srv
EXPOSE 8080
