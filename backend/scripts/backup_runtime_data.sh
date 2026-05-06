#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BACKEND_DIR="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
DB_PATH="${BACKEND_DIR}/healthy_system.db"
STORAGE_DIR="${BACKEND_DIR}/storage"
BACKUP_ROOT="${STORAGE_DIR}/backups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
TARGET_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

mkdir -p "${TARGET_DIR}"

if [ -f "${DB_PATH}" ]; then
    python3 - "${DB_PATH}" "${TARGET_DIR}/healthy_system.db" <<'PY'
import sqlite3
import sys

src, dst = sys.argv[1], sys.argv[2]
source = sqlite3.connect(src)
target = sqlite3.connect(dst)
try:
    source.backup(target)
finally:
    target.close()
    source.close()
PY
fi

if [ -d "${STORAGE_DIR}" ]; then
    tar \
        --exclude="${STORAGE_DIR}/backups" \
        -czf "${TARGET_DIR}/storage.tar.gz" \
        -C "${BACKEND_DIR}" \
        storage
fi

{
    echo "backup_timestamp=${TIMESTAMP}"
    echo "backend_dir=${BACKEND_DIR}"
    echo "db_exists=$( [ -f "${DB_PATH}" ] && echo yes || echo no )"
    echo "storage_exists=$( [ -d "${STORAGE_DIR}" ] && echo yes || echo no )"
} > "${TARGET_DIR}/manifest.txt"

echo "backup created at ${TARGET_DIR}"
