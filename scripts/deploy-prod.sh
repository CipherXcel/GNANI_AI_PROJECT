#!/usr/bin/env bash
set -euo pipefail

cd /opt/gnani-audio-notes

echo "Pulling latest code..."
git pull --ff-only origin main

echo "Checking Compose..."
docker compose -f docker-compose.prod.yml config >/dev/null

echo "Building images..."
docker compose -f docker-compose.prod.yml build

echo "Running database migrations..."
docker compose -f docker-compose.prod.yml run --rm migrate

echo "Starting production services..."
docker compose -f docker-compose.prod.yml up -d

echo "Production status:"
docker compose -f docker-compose.prod.yml ps
