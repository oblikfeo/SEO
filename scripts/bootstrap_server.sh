#!/usr/bin/env bash
# Разовая настройка VPS: nginx + клон/обновление репозитория + раздача public/
# Запуск на сервере: bash scripts/bootstrap_server.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/oblikfeo/SEO.git}"
INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"
BRANCH="${BRANCH:-main}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git

if [[ ! -d "$INSTALL_ROOT/.git" ]]; then
  mkdir -p "$(dirname "$INSTALL_ROOT")"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_ROOT"
else
  cd "$INSTALL_ROOT"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
fi

chown -R www-data:www-data "$INSTALL_ROOT/public"

cat >/etc/nginx/sites-available/seo-static <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /var/www/seo/public;
    index index.html;

    location / {
        try_files $uri $uri/ $uri/index.html =404;
    }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
}
NGINX

ln -sf /etc/nginx/sites-available/seo-static /etc/nginx/sites-enabled/seo-static
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl reload nginx
echo "Готово. Откройте http://127.0.0.1/ или IP сервера."
