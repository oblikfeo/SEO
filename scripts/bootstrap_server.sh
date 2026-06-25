#!/usr/bin/env bash
# Разовая и повторная настройка VPS: nginx + TLS (Let's Encrypt) + репозиторий + раздача public/
# Запуск на сервере: bash scripts/bootstrap_server.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/oblikfeo/SEO.git}"
INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"
BRANCH="${BRANCH:-main}"
DOMAIN="${DOMAIN:-nadezhda.info}"
LE_CHAIN="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
LE_KEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git certbot python3-certbot-nginx

if [[ ! -d "$INSTALL_ROOT/.git" ]]; then
  mkdir -p "$(dirname "$INSTALL_ROOT")"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_ROOT"
else
  # Не затирать content_overrides.json (админка SEO) — см. safe_git_update.sh
  bash "$INSTALL_ROOT/scripts/safe_git_update.sh"
fi

chown -R www-data:www-data "$INSTALL_ROOT/public"

# Мини-админка SEO (systemd unit + python3-flask) — устанавливается до nginx-reload,
# чтобы upstream 127.0.0.1:5050 уже отвечал, когда nginx начнёт проксировать /admin/.
bash "$INSTALL_ROOT/scripts/install_admin.sh"

write_http_bootstrap() {
  cat >/etc/nginx/sites-available/seo-static <<EOF
# Первичная выдача сертификата Let's Encrypt (HTTP-01 на порту 80).
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} _;

    root ${INSTALL_ROOT}/public;
    index index.html;

    location /admin {
        return 301 /admin/;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:5050/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix /admin;
        proxy_read_timeout 90s;
    }

    location / {
        try_files \$uri \$uri/ \$uri/index.html =404;
    }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF
}

write_https_final() {
  cat >/etc/nginx/sites-available/seo-static <<EOF
# TLS: Let's Encrypt. Продление: certbot renew (cron/systemd).
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} _;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://${DOMAIN}\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate ${LE_CHAIN};
    ssl_certificate_key ${LE_KEY};
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root ${INSTALL_ROOT}/public;
    index index.html;

    location /admin {
        return 301 /admin/;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:5050/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix /admin;
        proxy_read_timeout 90s;
    }

    location / {
        try_files \$uri \$uri/ \$uri/index.html =404;
    }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}
EOF
}

mkdir -p /var/www/html
chown -R www-data:www-data /var/www/html

ln -sf /etc/nginx/sites-available/seo-static /etc/nginx/sites-enabled/seo-static
rm -f /etc/nginx/sites-enabled/default

if [[ -f "$LE_CHAIN" ]]; then
  write_https_final
else
  write_http_bootstrap
  nginx -t
  systemctl enable nginx
  systemctl reload nginx

  certbot --nginx -d "$DOMAIN" \
    --non-interactive --agree-tos \
    --register-unsafely-without-email \
    --redirect

  write_https_final
fi

nginx -t
systemctl enable nginx
systemctl reload nginx
echo "Готово: https://${DOMAIN}/"
