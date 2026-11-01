# Backups and the restore drill

Week 12. Render's free database comes with no backups we can restore, so we make our own,
and we prove they work by restoring one ("the drill") before we ever need to.

**A backup holds every patient's record.** Keep it private: never commit it (`backups/` is
ignored by git), never send it by chat or email, and delete old ones. Today the deployed
database holds fake demo data only.

## What a backup is

`bash scripts/backup.sh` writes three files in `backups/`:

| File | What it is |
|---|---|
| `afripeak-<time>.dump` | the whole database (`pg_dump`, custom format) |
| `afripeak-<time>.dump.sha256` | its checksum: a damaged or swapped file is noticed |
| `afripeak-<time>.heads.json` | each clinic's audit-chain head (line number and hash), read just before the dump |

The heads are the audit log's anchor (brief D3). The chain check alone cannot see someone
who rewrote the whole audit log from some point on; a head written down *outside* the
database can. The drill checks that the restored audit log still has, at each recorded line
number, the recorded hash. Keep the heads file with its dump, and ideally a copy somewhere
else too.

## Making a backup

In the Codespace, from the repository root. The database address holds its password, so
it is read without being shown, and never typed into a command:

```bash
read -rs RENDER_DB_URL && export RENDER_DB_URL
```
(paste the **External Database URL** from Render, `afripeak-db` > Connect, then Enter)

```bash
bash scripts/backup.sh
```

```bash
unset RENDER_DB_URL
```

**How often:** before every deploy that has a migration, and at least weekly during the
pilot. **What we can lose (RPO):** everything since the last backup. **Keep:** the last four
weekly backups; delete older ones.

## The restore drill

```bash
bash scripts/restore_drill.sh backups/afripeak-<time>.dump
```

It never touches Render. It:

1. checks the dump against its checksum;
2. makes an empty scratch database, `restore_drill`, in the local Postgres of docker compose;
3. restores the dump into it, and times it;
4. checks the copy: the migration version is the one this code expects; row counts of the
   main tables are printed for the record; every clinic's audit chain is unbroken and runs
   through the recorded head.

It ends with **RESTORE DRILL PASSED** (exit code 0) or **RESTORE DRILL FAILED** and the
problems found, then drops the scratch database (`KEEP=1 bash scripts/restore_drill.sh ...`
keeps it). Write the date, the backup file, the seconds it took and the result in `LOG.md`:
that time is our measured restore time (RTO) for a database this size.

Run the drill after every backup you might rely on, and at least once a month.

## A real restore (the Render database is lost or damaged)

Only after a team decision, because it replaces live data.

1. Put the site in maintenance: in Render, **suspend** `afripeak-web` so nobody writes.
2. Create a new Render Postgres (or use the existing one if it is reachable and empty).
3. In it, create the row-level security role first, as the migration would have:
   `CREATE ROLE clinic_app NOLOGIN; GRANT clinic_app TO CURRENT_USER;`
4. Restore with privileges kept (the user is Render's, so grants apply):
   `pg_restore --no-owner --exit-on-error -d "<new database URL>" backups/afripeak-<time>.dump`
   (from the Codespace: `docker compose exec -T db pg_restore ... < backups/...dump`).
5. Point `afripeak-api`'s `DATABASE_URL` at it if it is a new database, and redeploy. The API
   runs the migrations; the version should already be current.
6. Check: `/health/ready`, an admin sign-in, the audit chain (`GET /api/v1/audit/chain`, its
   head should be at or after the one in the heads file).
7. Resume `afripeak-web`. Tell staff what was lost (anything after the backup time).
