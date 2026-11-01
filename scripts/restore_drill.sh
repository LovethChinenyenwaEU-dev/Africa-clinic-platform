#!/usr/bin/env bash
# The restore drill (Week 12): prove a backup can be brought back, and time it.
# Run from the repository root in the Codespace:
#
#   bash scripts/restore_drill.sh backups/afripeak-<time>.dump
#
# It restores the dump into a scratch database (restore_drill) in the LOCAL Postgres of
# docker compose, never into Render, then checks the migration version, the row counts and
# every clinic's audit chain against the heads recorded at backup time. The scratch
# database is dropped at the end (KEEP=1 keeps it to look around).
set -euo pipefail

dump="${1:?Give the .dump file: bash scripts/restore_drill.sh backups/afripeak-<time>.dump}"
heads="${dump%.dump}.heads.json"
[ -f "$dump" ] || { echo "No such file: $dump"; exit 1; }
[ -f "$heads" ] || { echo "The heads file is missing: $heads"; exit 1; }

echo "1/4 Checking the file is not damaged..."
sha256sum --check --quiet "${dump}.sha256"

docker compose up -d db >/dev/null
started=$(date +%s)

echo "2/4 Making an empty scratch database..."
docker compose exec -T db sh -c 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' <<'SQL'
DROP DATABASE IF EXISTS restore_drill;
CREATE DATABASE restore_drill;
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'clinic_app') THEN
        CREATE ROLE clinic_app NOLOGIN;
    END IF;
END $$;
SQL

echo "3/4 Restoring..."
# --no-owner/--no-privileges: Render's user does not exist here. A real restore onto a
# new Render database keeps them (see docs/backup-restore.md).
docker compose exec -T db sh -c \
  'pg_restore --no-owner --no-privileges --exit-on-error -U "$POSTGRES_USER" -d restore_drill' \
  < "$dump"
restored=$(date +%s)

echo "4/4 Checking the restored copy..."
status=0
docker compose run --rm --no-deps -T api sh -c \
  'DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@db:5432/restore_drill" python -m app.backup_check verify' \
  < "$heads" || status=$?

echo "Restore took $((restored - started)) seconds; the whole drill $(( $(date +%s) - started )) seconds."

if [ "${KEEP:-0}" != "1" ]; then
  docker compose exec -T db sh -c 'psql -q -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE restore_drill"'
fi
exit "$status"
