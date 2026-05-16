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
# Порт TCP 443 на этом узле занят под Xray (VLESS Reality) — общедоступный HTTPS для лендинга
# включают через CDN (Cloudflare/Nginx proxy) поверх этого HTTP :80 или отделяют второй вход.
server {
    listen 80;
    listen [::]:80;
    server_name www.nadezhda.info;
    return 301 https://nadezhda.info$request_uri;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name nadezhda.info _;

    root /var/www/seo/public;
    index index.html;

    location / {
        try_files $uri $uri/ $uri/index.html =404;
    }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
NGINX

ln -sf /etc/nginx/sites-available/seo-static /etc/nginx/sites-enabled/seo-static
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl reload nginx
echo "Готово. Откройте http://127.0.0.1/ или IP сервера."
