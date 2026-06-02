# Инструкция для AI-агента: SEO-лендинг (nadezhda.info)

**Прочитай это перед любой задачей в `seo-landing/`.**

## Главное правило

**Тексты страниц заполняет SEO-специалист через админку.**  
Агент добавляет только **структуру** (новые URL, карточки на хабе) в `scripts/site_data.py`.

Не писать prose/FAQ/title в `content_overrides.json`. Не коммитить этот файл с данными.

## Почему это критично

Админка (`https://nadezhda.info/admin/`) сохраняет правки в **`content_overrides.json` на сервере**.  
Файл в git — пустой `{}`. Если при деплое сделать `git reset --hard` без восстановления бэкапа — **вся работа SEO стирается** (реальный инцидент, 2026).

## Чеклист агента

### Новые страницы (как desktop-сателлиты)

- [ ] Добавить slug в `LEAVES` / `SUBLEAVES`, при необходимости `LABELS`
- [ ] Добавить карточки на родительский хаб в `site_data.py` (`CONTENT`)
- [ ] `python scripts/build_pages.py`
- [ ] Коммит: `site_data.py`, `public/` — **без** `content_overrides.json`
- [ ] Сообщить пользователю: тексты — в админке на проде
- [ ] Деплой: `safe_git_update.sh` (не голый `reset --hard`)

### Запрещено без явной просьбы пользователя

- SCP отдельных файлов на SEO-сервер
- Коммит `content_overrides.json` с текстами
- `git reset --hard` на сервере без `safe_git_update.sh`
- Переписывание SEO-текстов «от себя»

## Деплой

```bash
# На сервере (после git push в oblikfeo/SEO):
cd /var/www/seo && bash scripts/safe_git_update.sh
```

С Windows: `SEO_SSH_KEY=.../доступы4/ssh-key-wifi-ed25519 python scripts/_remote_deploy_runner.py`

См. также: `content_overrides.README.txt`, `.cursor/rules/seo-landing-content.mdc`
