SEO-сайт «Надежда» — nadezhda.info
==================================

Статический сайт. Весь контент, вёрстка и стили лежат в этом репозитории.
Коммит в ветку main автоматически выкладывается на сайт примерно за минуту.

Подробная инструкция: CLAUDE.md
Статус последней сборки: https://nadezhda.info/deploy-status.txt

Локальная сборка
----------------
  python scripts/build_pages.py
  python scripts/check_seo.py
  python -m http.server 8080 --directory public

Как устроен сервер (195.133.198.100)
------------------------------------
  /var/www/seo                    копия репозитория, владелец seo-build
  /var/www/seo-releases/<дата>    собранные версии, хранятся последние 5
  /var/www/seo-releases/current   ссылка на живую версию, её раздаёт nginx
  /var/lib/seo-deploy/            статус последней сборки
  /usr/local/bin/seo-deploy       скрипт автосборки (из deploy/seo-deploy.sh)
  seo-deploy.timer                запуск раз в минуту

Сборка идёт от пользователя seo-build без прав на остальной сервер.
Сайт переключается только после успешной сборки и проверки,
поэтому ошибка в коммите не ломает живой сайт.

Обновить автосборку на сервере (файлы deploy/ сами не применяются):
  install -m 755 deploy/seo-deploy.sh /usr/local/bin/seo-deploy
  cp deploy/seo-deploy.service deploy/seo-deploy.timer /etc/systemd/system/
  systemctl daemon-reload

Откат сервера на прошлую версию без git (от root):
  ln -sfn /var/www/seo-releases/<версия> /var/www/seo-releases/current
