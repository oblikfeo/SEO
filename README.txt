SEO-лендинг «Надежда» — nadezhda.info
=====================================

!!! КРИТИЧНО — content_overrides.json и админка SEO !!!
--------------------------------------------------------
  Тексты страниц заполняет SEO-специалист через https://nadezhda.info/admin/
  Данные живут в content_overrides.json НА СЕРВЕРЕ. В git — только пустой {}.

  ЗАПРЕЩЕНО: git reset --hard без safe_git_update.sh; коммитить тексты в overrides;
             SCP файлов на сервер вместо git; писать SEO-тексты «от себя» в overrides.

  Деплой на VPS:  bash scripts/safe_git_update.sh
  Подробно:       AGENTS-SEO.md, content_overrides.README.txt,
                  .cursor/rules/seo-landing-content.mdc

Статический сайт: HTML в public/, сборка из scripts/site_data.py.

Быстрый старт (локально)
------------------------
  cd seo-landing
  python scripts/build_pages.py          # пересборка public/
  python -m http.server 8080 --directory public
  http://127.0.0.1:8080/

Админка (редактирование title / description / H1 / блоков контента)
-------------------------------------------------------------------
  Прод:     https://nadezhda.info/admin/
  Логин/пароль: см. доступы4/readme.md (на сервере — /etc/seo-admin.env)

  Локально:
    pip install -r scripts/requirements-admin.txt
    set ADMIN_USER=admin & set ADMIN_PASSWORD=secret
    python scripts/admin.py
    http://127.0.0.1:5050/

  «Сохранить и опубликовать» → content_overrides.json + build_pages.py.

  Через админку редактируются: сниппет, prose, таблица, FAQ, SEO-поля.
  Фиксированные (только в site_data.py): карточки навигации, блок trial «8 часов».
  Таблицы — только блок «Таблица», не вставлять <table> в prose.

Конфиг и данные
---------------
  site_config.json         — base_url, UTM, ссылки на кабинет
  scripts/site_data.py     — дерево URL, дефолты, карточки хабов
  content_overrides.json   — в git только {}; на сервере — работа SEO (админка)

Деплой
------
  Репозиторий: https://github.com/oblikfeo/SEO (main)
  Сервер: 222.167.208.75, каталог /var/www/seo — см. доступы4/readme.md

  cd /var/www/seo && bash scripts/safe_git_update.sh

  С ПК: SEO_SSH_KEY=.../доступы4/ssh-key-wifi-ed25519 python scripts/_remote_deploy_runner.py

  НЕ использовать: git reset --hard без восстановления content_overrides.json

  Первичная установка nginx + TLS: bash scripts/bootstrap_server.sh
  Установка админки: bash scripts/install_admin.sh
