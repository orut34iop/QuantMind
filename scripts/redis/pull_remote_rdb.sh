#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/redis/data"
OUTPUT_FILE="${OUTPUT_DIR}/dump.rdb"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

REMOTE_HOST="${REMOTE_REDIS_HOST:-${REDIS_HOST:-127.0.0.1}}"
REMOTE_PORT="${REMOTE_REDIS_PORT:-${REDIS_PORT:-6379}}"
REMOTE_PASSWORD="${REMOTE_REDIS_PASSWORD:-${REDIS_PASSWORD:-}}"

mkdir -p "${OUTPUT_DIR}"
cd "${OUTPUT_DIR}"

echo "[Redis] 拉取远端 RDB: ${REMOTE_HOST}:${REMOTE_PORT}"
if command -v redis-cli >/dev/null 2>&1; then
  REDIS_CLI_BIN=(redis-cli)
else
  echo "[Redis] 本机未安装 redis-cli，使用 redis:7.2-alpine 容器执行"
  REDIS_CLI_BIN=(docker run --rm -v "${OUTPUT_DIR}:/data" -w /data redis:7.2-alpine redis-cli)
fi

if [[ -n "${REMOTE_PASSWORD}" ]]; then
  "${REDIS_CLI_BIN[@]}" -h "${REMOTE_HOST}" -p "${REMOTE_PORT}" -a "${REMOTE_PASSWORD}" --rdb "$(basename "${OUTPUT_FILE}")"
else
  "${REDIS_CLI_BIN[@]}" -h "${REMOTE_HOST}" -p "${REMOTE_PORT}" --rdb "$(basename "${OUTPUT_FILE}")"
fi

echo "[Redis] 完成: ${OUTPUT_FILE}"
