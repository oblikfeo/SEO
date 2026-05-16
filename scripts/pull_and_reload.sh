#!/usr/bin/env bash
# После git pull/fetch на сервере: права на public/ и reload nginx (без apt).
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"

chown -R www-data:www-data "$INSTALL_ROOT/public"
nginx -t
systemctl reload nginx
echo "Готово: файлы из $INSTALL_ROOT/public, nginx reload."
