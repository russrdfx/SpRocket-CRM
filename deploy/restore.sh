#!/bin/sh
set -eu
if [ "$#" -ne 2 ] || [ "$2" != RESTORE ] || [ ! -f "$1" ]; then
  printf 'Usage: deploy/restore.sh backups/file.dump RESTORE\n' >&2
  exit 1
fi
# Stop the application before replacing shared data. Leave it stopped if restoration fails.
docker compose --env-file deploy/.env stop app
sh deploy/backup.sh
docker compose --env-file deploy/.env exec -T db pg_restore -U sprocket -d sprocket --clean --if-exists --single-transaction < "$1"
docker compose --env-file deploy/.env up -d app
