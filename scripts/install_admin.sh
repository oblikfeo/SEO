#!/usr/bin/env bash
# Установка/обновление мини-админки SEO-лендинга на сервере.
# Идемпотентен. Запуск:  bash scripts/install_admin.sh
#
# Переменные окружения (опционально):
#   ADMIN_USER       — логин (по умолчанию из /etc/seo-admin.env или admin)
#   ADMIN_PASSWORD   — пароль (если /etc/seo-admin.env нет — будет сгенерирован случайный)
#   INSTALL_ROOT     — корень проекта (по умолчанию /var/www/seo)
#
# После установки админка доступна на /admin/ того же домена, что и сайт
# (за nginx; nginx-конфиг обновляется отдельно из bootstrap_server.sh).
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"
ENV_FILE="/etc/seo-admin.env"
SERVICE_NAME="seo-admin.service"
SERVICE_SRC="${INSTALL_ROOT}/scripts/seo-admin.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-flask python3-werkzeug

if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "Не найден $SERVICE_SRC" >&2
  exit 1
fi

# /etc/seo-admin.env: создаём, если нет, либо обновляем поля из env переменных скрипта.
if [[ ! -f "$ENV_FILE" ]]; then
  GENERATED_PW="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 || true)"
  cat >"$ENV_FILE" <<EOF
ADMIN_USER=${ADMIN_USER:-admin}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-$GENERATED_PW}
ADMIN_BIND=127.0.0.1
ADMIN_PORT=5050
EOF
  chmod 640 "$ENV_FILE"
  chown root:www-data "$ENV_FILE"
  echo "Создан $ENV_FILE с автогенерированным паролем — см. ниже:"
  grep -E '^ADMIN_(USER|PASSWORD)=' "$ENV_FILE"
else
  # Если переменные заданы при вызове — обновим (без потери остальных строк).
  if [[ -n "${ADMIN_USER:-}" ]]; then
    sed -i -E "s|^ADMIN_USER=.*|ADMIN_USER=${ADMIN_USER}|" "$ENV_FILE"
  fi
  if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
    # экранируем для sed (символы | и \)
    ESC_PW="$(printf '%s' "$ADMIN_PASSWORD" | sed -e 's/[\\|&]/\\&/g')"
    sed -i -E "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ESC_PW}|" "$ENV_FILE"
  fi
  # Унаследованный DOWNLOAD_TOKEN из старой реализации публичного /dl/<token>
  # больше не нужен — удаляем, чтобы не висел в env.
  if grep -q '^DOWNLOAD_TOKEN=' "$ENV_FILE"; then
    sed -i -E '/^DOWNLOAD_TOKEN=/d' "$ENV_FILE"
    echo "Удалён устаревший DOWNLOAD_TOKEN из $ENV_FILE (теперь скачивание через /admin/download)."
  fi
  echo "$ENV_FILE уже существует — переиспользуем (изменения переменных применены, если переданы)."
fi

# Права: чтобы www-data мог писать в репозиторий (content_overrides.json и public/).
chown -R www-data:www-data "$INSTALL_ROOT/public"
touch "$INSTALL_ROOT/content_overrides.json"
chown www-data:www-data "$INSTALL_ROOT/content_overrides.json"
chmod 664 "$INSTALL_ROOT/content_overrides.json"

# systemd unit
install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

sleep 1
systemctl --no-pager --lines=10 status "$SERVICE_NAME" || true

# Быстрый smoke-test
if curl -fsS -o /dev/null "http://127.0.0.1:5050/health"; then
  echo "OK: admin отвечает на http://127.0.0.1:5050/health"
else
  echo "ПРЕДУПРЕЖДЕНИЕ: admin не отвечает на /health — смотри journalctl -u $SERVICE_NAME -n 100" >&2
fi

echo "Готово. Не забудь обновить nginx (location /admin/ → 127.0.0.1:5050) — см. scripts/bootstrap_server.sh"
