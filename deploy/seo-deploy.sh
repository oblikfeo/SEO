#!/usr/bin/env bash
# Автосборка nadezhda.info: раз в минуту смотрит ветку main и выкладывает новый коммит.
# Установлен в /usr/local/bin/seo-deploy, запускается таймером seo-deploy.timer от пользователя seo-build.
# Сборка идёт в новую папку; сайт переключается только после успешной сборки и проверки.
set -uo pipefail

REPO=/var/www/seo
RELEASES=/var/www/seo-releases
STATE=/var/lib/seo-deploy
STATUS=$STATE/status.txt
BRANCH=main
KEEP=5

exec 9>"$STATE/lock"
flock -n 9 || exit 0

write_status() {
  {
    echo "result: $1"
    echo "commit: $2"
    echo "time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    [ -n "${3:-}" ] && printf '\n%s\n' "$3"
  } > "$STATUS.tmp"
  mv -f "$STATUS.tmp" "$STATUS"
}

cd "$REPO" || exit 1
git fetch -q origin "$BRANCH" || exit 1
REMOTE=$(git rev-parse "origin/$BRANCH")
[ "$REMOTE" = "$(cat "$STATE/last-commit" 2>/dev/null)" ] && exit 0

# Коммит пробуем один раз: упавшая сборка не повторяется, пока не придёт новый коммит.
echo "$REMOTE" > "$STATE/last-commit"
git reset -q --hard "origin/$BRANCH"
git clean -fdq

SHORT=${REMOTE:0:8}
OUT=$RELEASES/$(date -u +%Y%m%d-%H%M%S)-$SHORT
LIVE=$(basename "$(readlink -f "$RELEASES/current")")

export SEO_PUBLIC_DIR=$OUT
LOG=$(timeout 120 python3 scripts/build_pages.py 2>&1)
RC=$?
if [ "$RC" -eq 0 ]; then
  CHECK=$(python3 scripts/check_seo.py 2>&1)
  RC=$?
  LOG="$LOG"$'\n'"$CHECK"
fi
if [ "$RC" -ne 0 ] || [ ! -s "$OUT/index.html" ]; then
  rm -rf "$OUT"
  write_status FAILED "$SHORT" "Сайт не изменился, работает версия $LIVE."$'\n\n'"$(echo "$LOG" | tail -n 30)"
  exit 0
fi

ln -sfn "$OUT" "$RELEASES/.current.new"
mv -Tf "$RELEASES/.current.new" "$RELEASES/current"
write_status OK "$SHORT" "$LOG"

ls -1dt "$RELEASES"/2* 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf
