SEO-лендинг «Надежда» (статика → SSR)
=====================================

Папка public/ — готовый сайт для nginx или локального просмотра.
Исходники стилей: assets/css/ (копируются в public/assets/css при сборке).

Локальный просмотр (из корня seo-landing):
  python -m http.server 8080 --directory public
  Открыть: http://127.0.0.1:8080/

Пересборка страниц после правок scripts/site_data.py или site_config.json:
  python scripts/build_pages.py

Конфиг домена и UTM: site_config.json
  base_url, register_path, utm_source, utm_medium

Эталоны по ТЗ:
  L1  /devices/
  L2  /devices/mobile/
  L3  /devices/mobile/android/

Полный текст P0 — в scripts/site_data.py (p0_content).
Остальные URL — заглушки с H1 и блоком trial (дерево из SEO-work/Дерево сайта.md).

На проде: /dashboard/* и кабинет — noindex в mainServer (robots + meta), не в этой статике.

GitHub и VPS (репозиторий SEO)
------------------------------
Репозиторий: https://github.com/oblikfeo/SEO

Локально (из папки seo-landing):
  git init
  git remote add origin https://github.com/oblikfeo/SEO.git
  git add -A && git commit -m "..." && git push -u origin main

На сервере (Ubuntu/Debian, после входа по SSH):
  apt-get update && apt-get install -y git
  cd /var/www && git clone https://github.com/oblikfeo/SEO.git seo && cd seo
  bash scripts/bootstrap_server.sh

Обновление после push в main (быстро, без apt):
  cd /var/www/seo && git pull origin main && bash scripts/pull_and_reload.sh

Полная переустановка конфигура nginx (редко):
  cd /var/www/seo && bash scripts/bootstrap_server.sh

Корень сайта для nginx: public/ (отдаётся как статика).
Пароли SSH не храните в репозитории; для прод-доступа лучше ключ и отключить вход по паролю.
