#!/usr/bin/env bash
# После git pull/fetch на сервере: права на public/ и reload nginx (без apt).
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"

chown -R www-data:www-data "$INSTALL_ROOT/public"
# content_overrides.json должен оставаться writable для www-data (правит админка).
if [[ -f "$INSTALL_ROOT/content_overrides.json" ]]; then
  chown www-data:www-data "$INSTALL_ROOT/content_overrides.json"
  chmod 664 "$INSTALL_ROOT/content_overrides.json"
fi

# Если стоит мини-админка SEO — перезапустим, чтобы подхватить новый код scripts/admin.py.
if systemctl list-unit-files | grep -q '^seo-admin.service'; then
  systemctl restart seo-admin.service || true
fi

nginx -t
systemctl reload nginx
echo "Готово: файлы из $INSTALL_ROOT/public, nginx reload."
