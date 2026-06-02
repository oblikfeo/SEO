#!/usr/bin/env bash
# Безопасное обновление репозитория на SEO-VPS.
# Сохраняет content_overrides.json (данные админки) перед git reset и
# восстанавливает после — иначе теряется работа SEO-специалиста.
#
# Использование на сервере:
#   cd /var/www/seo && bash scripts/safe_git_update.sh
#
# НЕ заменять на голый «git reset --hard» без бэкапа overrides.
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/var/www/seo}"
BRANCH="${BRANCH:-main}"
OVERRIDES="$INSTALL_ROOT/content_overrides.json"
BACKUP="${SEO_OVERRIDES_BACKUP:-/tmp/seo-content_overrides.backup.json}"

if [[ ! -d "$INSTALL_ROOT/.git" ]]; then
  echo "Нет git-репозитория в $INSTALL_ROOT" >&2
  exit 1
fi

had_backup=0
if [[ -f "$OVERRIDES" ]]; then
  # Бэкапим любой непустой overrides (в т.ч. только «{}» на первой установке).
  cp -a "$OVERRIDES" "$BACKUP"
  had_backup=1
  echo "Бэкап content_overrides.json → $BACKUP"
fi

cd "$INSTALL_ROOT"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

if [[ "$had_backup" -eq 1 && -f "$BACKUP" ]]; then
  cp -a "$BACKUP" "$OVERRIDES"
  echo "Восстановлен content_overrides.json с сервера (данные админки)"
fi

python3 "$INSTALL_ROOT/scripts/build_pages.py"
bash "$INSTALL_ROOT/scripts/pull_and_reload.sh"
echo "safe_git_update: OK (ветка origin/$BRANCH, overrides сохранены)"
