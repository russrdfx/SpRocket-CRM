#!/bin/sh
set -eu
umask 077
mkdir -p backups
backup_path="backups/SpRocket-web-$(date +%Y%m%d-%H%M%S).dump"
docker compose --env-file deploy/.env exec -T db pg_dump -U sprocket -d sprocket --format=custom > "$backup_path"
printf 'Backup saved: %s\n' "$backup_path"
