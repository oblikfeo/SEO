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

Эталонный приоритетный контент ТЗ — в scripts/site_data.py (ветки с полными текстами).
Остальные URL — заглушки с H1 и блоком trial (дерево из SEO-work/Дерево сайта.md).

Подмена SEO-полей через админку (без правок Python)
---------------------------------------------------
Файл `content_overrides.json` (в корне seo-landing/) — JSON со словарём
"<путь страницы>": { "title": "...", "description": "...", "h1": "..." }.
build_pages.py подхватывает overrides поверх дефолтов из site_data.py.
Пустые/отсутствующие поля → используется дефолт.

Мини-админка (Flask) — управление SEO через браузер:
  Локально:
    pip install -r scripts/requirements-admin.txt
    $env:ADMIN_USER='admin'; $env:ADMIN_PASSWORD='secret'   # PowerShell
    python scripts/admin.py
    http://127.0.0.1:5050/

  На сервере (доступно как https://nadezhda.info/admin/):
    bash scripts/install_admin.sh
  Логин/пароль создаются автоматически в /etc/seo-admin.env (см. вывод скрипта)
  или задаются переменными ADMIN_USER / ADMIN_PASSWORD при запуске install_admin.sh.
  Конфиг nginx (location /admin/) разворачивается из scripts/bootstrap_server.sh.

Что умеет админка:
  - список всех 66 страниц сайта (главная + silo/hub/leaf/sub);
  - редактирование title, meta description и H1 для любой страницы;
  - кнопка «Сохранить и опубликовать» — пишет в content_overrides.json,
    запускает build_pages.py и обновляет файлы в public/;
  - кнопка «Сбросить к дефолту» — убирает override для страницы.

Структуру (карточки, FAQ, таблицы, навигацию) админка НЕ редактирует —
это логика лендинга, она остаётся в коде scripts/site_data.py.

На проде: /dashboard/* и кабинет — noindex в mainServer (robots + meta), не в этой статике.

GitHub и VPS (репозиторий SEO)
------------------------------
Репозиторий: https://github.com/oblikfeo/SEO

Локально (из папки seo-landing):
  git init
  git remote add origin https://github.com/oblikfeo/SEO.git
  git add -A && git commit -m "..." && git push -u origin main

Узел продакшена и домен: см. nadezhda.space — доступы4/readme.md
  (IP 222.167.208.75; канонический домен сайта — https://nadezhda.space/ ).

На сервере (Ubuntu/Debian, после входа по SSH):
  apt-get update && apt-get install -y git ca-certificates curl
  cd /var/www && git clone https://github.com/oblikfeo/SEO.git seo && cd seo
  bash scripts/bootstrap_server.sh

Обновление после push в main (быстро, без полного bootstrap):
  cd /var/www/seo && git pull origin main && bash scripts/pull_and_reload.sh

Полная переустановка nginx + TLS из актуального bootstrap (редко):
  cd /var/www/seo && bash scripts/bootstrap_server.sh

Корень сайта для nginx: public/ (отдаётся как статика).
Пароли SSH не храните в репозитории; для прод-доступа лучше ключ и отключить вход по паролю.
