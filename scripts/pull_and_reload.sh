#!/usr/bin/env bash
# После git pull/fetch на сервере: права на public/ и reload nginx (без apt).
# Обновление кода из git — только через scripts/safe_git_update.sh
# (иначе git reset --hard сотрёт content_overrides.json с данными админки SEO).
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"

chown -R www-data:www-data "$INSTALL_ROOT/public"
# content_overrides.json должен оставаться writable для www-data (правит админка).
if [[ -f "$INSTALL_ROOT/content_overrides.json" ]]; then
  chown www-data:www-data "$INSTALL_ROOT/content_overrides.json"
  chmod 664 "$INSTALL_ROOT/content_overrides.json"
fi

# Если стоит мини-админка SEO — перезапустим, чтобы подхватить site_data.py / admin.py.
# Без рестарта Flask держит старый список страниц: новые URL есть на сайте, но не в /admin/.
if systemctl is-active --quiet seo-admin.service 2>/dev/null; then
  systemctl restart seo-admin.service
  echo "seo-admin: перезапущен (подхват новых URL для админки)"
elif systemctl list-unit-files seo-admin.service 2>/dev/null | grep -q '^seo-admin.service'; then
  systemctl start seo-admin.service
  echo "seo-admin: запущен"
fi

nginx -t
systemctl reload nginx
echo "Готово: файлы из $INSTALL_ROOT/public, nginx reload."
