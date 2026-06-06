#!/usr/bin/env sh
set -eu
DB_PATH="${DATABASE_PATH:-/data/checklist.db}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-10}"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ ! -f "$DB_PATH" ]; then
  echo "No existe base de datos en $DB_PATH"
  exit 1
fi
OUT="$BACKUP_DIR/checklist_backup_$STAMP.db"
python - <<PY
import sqlite3
src = sqlite3.connect('$DB_PATH')
dst = sqlite3.connect('$OUT')
with dst:
    src.backup(dst)
src.close()
dst.close()
PY
gzip -f "$OUT"
ls -1t "$BACKUP_DIR"/checklist_backup_*.db.gz 2>/dev/null | tail -n +$((BACKUP_KEEP + 1)) | xargs -r rm -f
echo "Backup creado: $OUT.gz"
