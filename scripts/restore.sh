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
if echo "$SRC" | grep -q '\.gz$'; then
  gunzip -c "$SRC" > "$DB_PATH"
else
  cp "$SRC" "$DB_PATH"
fi
echo "Base restaurada en: $DB_PATH"
