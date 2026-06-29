#!/usr/bin/env sh
set -eu
if [ $# -ne 1 ]; then
  echo "Uso: ./scripts/restore.sh /backups/archivo.db.gz"
  exit 1
fi
DB_PATH="${DATABASE_PATH:-/data/checklist.db}"
SRC="$1"
if [ ! -f "$SRC" ]; then
  echo "No existe el archivo: $SRC"
  exit 1
fi
mkdir -p "$(dirname "$DB_PATH")"
TMP_DB="${DB_PATH}.restore.tmp"
if echo "$SRC" | grep -q '\.gz$'; then
  gunzip -c "$SRC" > "$TMP_DB"
else
  cp "$SRC" "$TMP_DB"
fi
mv "$TMP_DB" "$DB_PATH"
echo "Base restaurada en: $DB_PATH"
