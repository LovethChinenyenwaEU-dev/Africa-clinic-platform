#!/usr/bin/env bash
# Back up the Render database (Week 12). Run from the repository root in the Codespace:
#
#   read -rs RENDER_DB_URL && export RENDER_DB_URL     # paste the External Database URL
#   bash scripts/backup.sh
#
# Writes, in backups/ (never committed):
#   afripeak-<time>.dump          the whole database (pg_dump custom format)
#   afripeak-<time>.dump.sha256   its checksum, to notice a damaged copy
#   afripeak-<time>.heads.json    each clinic's audit-chain head, read just before
# The dump holds personal data: keep it somewhere private, and delete old ones.
set -euo pipefail

: "${RENDER_DB_URL:?First run: read -rs RENDER_DB_URL && export RENDER_DB_URL}"

mkdir -p backups
chmod 700 backups
stamp="$(date -u +%Y%m%dT%H%MZ)"
base="backups/afripeak-${stamp}"

docker compose up -d db >/dev/null

echo "1/3 Recording the audit-chain heads..."
docker compose run --rm --no-deps -T \
  -e DATABASE_URL="$RENDER_DB_URL" -e ENVIRONMENT=production \
  api python -m app.backup_check heads > "${base}.heads.json"

echo "2/3 Dumping the database..."
docker compose exec -T db pg_dump --format=custom --no-owner "$RENDER_DB_URL" > "${base}.dump"

echo "3/3 Writing the checksum..."
sha256sum "${base}.dump" > "${base}.dump.sha256"
chmod 600 "${base}".*

echo "Done: ${base}.dump ($(du -h "${base}.dump" | cut -f1))"
echo "Next: bash scripts/restore_drill.sh ${base}.dump"
