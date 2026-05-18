# -*- coding: utf-8 -*-
"""Мини-админка для управления SEO (title / description / H1) SEO-лендинга.

Один файл, один шаблон — без БД, без фронт-фреймворков.
Правки пишутся в seo-landing/content_overrides.json, после чего сразу запускается
build_pages.py и обновляются файлы в public/.

Запуск локально:
  python scripts/admin.py
  открыть http://127.0.0.1:5050/

Авторизация: HTTP Basic Auth. Логин/пароль — из переменных окружения
  ADMIN_USER, ADMIN_PASSWORD (по умолчанию admin/admin — обязательно
  переопределить в продакшене через systemd EnvironmentFile).
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import threading
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, redirect, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OVERRIDES_PATH = ROOT / "content_overrides.json"
BUILD_SCRIPT = SCRIPTS / "build_pages.py"

sys.path.insert(0, str(SCRIPTS))
from site_data import (  # noqa: E402
    CONTENT,
    HOME,
    HUBS,
    LABELS,
    LEAVES,
    SILO_META,
    SUBLEAVES,
    build_pages_list,
)

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
ADMIN_BIND = os.environ.get("ADMIN_BIND", "127.0.0.1")
ADMIN_PORT = int(os.environ.get("ADMIN_PORT", "5050"))
BRAND_TITLE_SUFFIX_DEFAULT = "Надежда VPN"

_write_lock = threading.Lock()
app = Flask(__name__)
# Чтобы при работе за nginx (location /admin/ → proxy_pass / + X-Forwarded-Prefix)
# url_for() и redirect() корректно генерировали ссылки с префиксом /admin.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


# ---------- Auth ----------

def _check_auth(user: str | None, password: str | None) -> bool:
    return bool(user) and bool(password) and user == ADMIN_USER and password == ADMIN_PASSWORD


def require_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return Response(
                "Требуется авторизация",
                status=401,
                headers={"WWW-Authenticate": 'Basic realm="SEO Admin"'},
            )
        return view(*args, **kwargs)

    return wrapper


# ---------- Overrides I/O ----------

def load_overrides() -> dict:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_overrides(data: dict) -> None:
    OVERRIDES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ---------- Дефолтные значения SEO для страницы ----------

def _brand_suffix() -> str:
    try:
        cfg = json.loads((ROOT / "site_config.json").read_text(encoding="utf-8"))
        return f"{cfg.get('brand', 'Надежда')} {cfg.get('brand_vpn', 'VPN')}"
    except Exception:
        return BRAND_TITLE_SUFFIX_DEFAULT


def default_seo(page: dict) -> dict:
    path = page["path"]
    if path == "/":
        return {
            "title": HOME["title"],
            "description": HOME["description"],
            "h1": HOME["h1"],
        }
    if path in CONTENT:
        c = CONTENT[path]
        return {
            "title": c["title"],
            "description": c["description"],
            "h1": c["h1"],
        }
    kind = page["kind"]
    brand = _brand_suffix()
    if kind == "silo":
        t, d = SILO_META[page["silo"]]
        return {"title": f"{t} — {brand}", "description": d, "h1": t}
    if kind == "hub":
        return {
            "title": f"{page['title']} — {brand}",
            "description": page["description"],
            "h1": page["title"],
        }
    leaf = page.get("sub") or page.get("leaf", "page")
    name = LABELS.get(leaf, leaf.replace("-", " ").title())
    return {
        "title": f"VPN {name} — {brand}",
        "description": (
            f"VPN-решение для запроса «{name}». 8 часов бесплатного теста в Личном Кабинете."
        ),
        "h1": f"VPN: {name}",
    }


def page_kind_label(kind: str) -> str:
    return {
        "home": "Главная",
        "silo": "Раздел (L1)",
        "hub": "Хаб (L2)",
        "leaf": "Лист (L3)",
        "sub": "Подстраница (L4)",
    }.get(kind, kind)


def find_page(path: str) -> dict | None:
    for p in build_pages_list():
        if p["path"] == path:
            return p
    return None


# ---------- Сборка ----------

def trigger_build() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "build_pages.py: таймаут (60s)"
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, f"build_pages.py exit={proc.returncode}\n{out}"
    return True, out.strip() or "ok"


# ---------- Шаблоны ----------

def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def layout(title: str, body: str, flash: str = "") -> str:
    flash_html = f'<div class="flash">{flash}</div>' if flash else ""
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>{esc(title)} — Админка SEO</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root {{ color-scheme: light dark; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       margin: 0; padding: 24px; max-width: 1100px; line-height: 1.45; color: #111; background: #fafafa; }}
h1 {{ margin: 0 0 18px; font-size: 22px; }}
h2 {{ margin: 24px 0 12px; font-size: 16px; }}
a {{ color: #0a58ca; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
nav.top {{ margin-bottom: 18px; font-size: 14px; color: #666; }}
nav.top a {{ margin-right: 12px; }}
table.list {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.05); border-radius: 8px; overflow: hidden; }}
table.list th, table.list td {{ padding: 10px 12px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; font-size: 14px; }}
table.list th {{ background: #f1f3f5; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; color: #555; }}
table.list tr:last-child td {{ border-bottom: 0; }}
table.list tr.ov td {{ background: #fff7e6; }}
.path {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; color: #333; }}
.kind {{ display: inline-block; font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #e9ecef; color: #495057; margin-left: 6px; }}
.kind.home {{ background: #d0ebff; color: #1864ab; }}
.kind.silo {{ background: #d3f9d8; color: #2b8a3e; }}
.kind.hub {{ background: #fff3bf; color: #8a6d00; }}
.kind.leaf {{ background: #ffe3e3; color: #c92a2a; }}
.kind.sub {{ background: #f3d9fa; color: #862e9c; }}
.flag-ov {{ display: inline-block; font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #fab005; color: #fff; margin-left: 6px; }}
.flash {{ padding: 12px 14px; margin-bottom: 16px; background: #d3f9d8; color: #2b8a3e; border-radius: 6px; font-size: 14px; }}
form.edit {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,.05); max-width: 720px; }}
form.edit .row {{ margin-bottom: 18px; }}
form.edit label {{ display: block; font-weight: 600; margin-bottom: 6px; font-size: 13px; }}
form.edit input[type=text], form.edit textarea {{ width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid #ced4da; border-radius: 6px; font-family: inherit; }}
form.edit textarea {{ min-height: 80px; resize: vertical; }}
form.edit .hint {{ font-size: 12px; color: #666; margin-top: 4px; }}
form.edit .default {{ font-size: 12px; color: #888; margin-top: 6px; padding: 8px 10px; background: #f8f9fa; border-radius: 4px; word-break: break-word; }}
form.edit .default b {{ color: #555; }}
form.edit .actions {{ display: flex; gap: 12px; margin-top: 20px; }}
button {{ font-size: 14px; padding: 9px 16px; border: 0; border-radius: 6px; cursor: pointer; }}
button.primary {{ background: #228be6; color: #fff; }}
button.primary:hover {{ background: #1c7ed6; }}
button.danger {{ background: #fa5252; color: #fff; }}
button.danger:hover {{ background: #e03131; }}
button.ghost {{ background: #e9ecef; color: #333; }}
.code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; background: #f1f3f5; padding: 1px 4px; border-radius: 3px; }}
@media (prefers-color-scheme: dark) {{
  body {{ background: #1a1b1e; color: #e9ecef; }}
  table.list, form.edit {{ background: #25262b; box-shadow: 0 1px 3px rgba(0,0,0,.3); }}
  table.list th {{ background: #2c2e33; color: #adb5bd; }}
  table.list th, table.list td {{ border-bottom-color: #373a40; }}
  table.list tr.ov td {{ background: #3a2f12; }}
  form.edit input[type=text], form.edit textarea {{ background: #1a1b1e; color: #e9ecef; border-color: #495057; }}
  form.edit .default {{ background: #2c2e33; color: #adb5bd; }}
  .kind {{ background: #373a40; color: #ced4da; }}
  a {{ color: #74c0fc; }}
  .flash {{ background: #1f3a23; color: #b2f2bb; }}
}}
</style></head><body>
<nav class="top">
  <a href="/">← Список страниц</a>
  <span style="color:#999">|</span>
  <a href="https://nadezhda.info/" target="_blank" rel="noopener">Открыть сайт ↗</a>
</nav>
{flash_html}
{body}
</body></html>"""


def render_index(saved: str | None = None, reset: str | None = None) -> str:
    overrides = load_overrides()
    pages = build_pages_list()
    rows = []
    for page in pages:
        path = page["path"]
        seo = default_seo(page)
        ov = overrides.get(path, {}) or {}
        is_overridden = any((ov.get(k) or "").strip() for k in ("title", "description", "h1"))
        kind = page["kind"]
        title = (ov.get("title") or "").strip() or seo["title"]
        h1 = (ov.get("h1") or "").strip() or seo["h1"]
        rows.append({
            "path": path,
            "kind": kind,
            "title": title,
            "h1": h1,
            "overridden": is_overridden,
        })

    rows_html = []
    for r in rows:
        ov_flag = '<span class="flag-ov">override</span>' if r["overridden"] else ""
        cls = ' class="ov"' if r["overridden"] else ""
        rows_html.append(
            f'<tr{cls}>'
            f'<td><span class="path">{esc(r["path"])}</span>'
            f'<span class="kind {esc(r["kind"])}">{esc(page_kind_label(r["kind"]))}</span>{ov_flag}</td>'
            f'<td>{esc(r["h1"])}</td>'
            f'<td>{esc(r["title"])}</td>'
            f'<td style="text-align:right; white-space:nowrap">'
            f'<a href="{url_for("edit", path=r["path"])}">Редактировать</a></td>'
            f'</tr>'
        )

    flash = ""
    if saved:
        flash = f"Сохранено и пересобрано: <span class='code'>{esc(saved)}</span>"
    elif reset:
        flash = f"Сброшено к дефолту: <span class='code'>{esc(reset)}</span>"

    total = len(rows)
    overridden_n = sum(1 for r in rows if r["overridden"])
    body = (
        f'<h1>SEO-страницы лендинга</h1>'
        f'<p style="font-size:14px;color:#666;margin:-8px 0 16px">Всего: {total} · с правками: {overridden_n}</p>'
        f'<table class="list">'
        f'<thead><tr><th>Путь</th><th>H1</th><th>Title</th><th></th></tr></thead>'
        f'<tbody>' + "".join(rows_html) + '</tbody>'
        f'</table>'
    )
    return layout("SEO-страницы", body, flash)


def render_edit(page: dict, seo: dict, ov: dict, error: str = "") -> str:
    path = page["path"]
    ov_title = ov.get("title") or ""
    ov_desc = ov.get("description") or ""
    ov_h1 = ov.get("h1") or ""
    is_overridden = any((v or "").strip() for v in (ov_title, ov_desc, ov_h1))

    reset_form = ""
    if is_overridden:
        reset_form = (
            f'<form method="post" action="{url_for("reset")}" '
            f'onsubmit="return confirm(\'Сбросить все правки этой страницы к дефолту?\');" '
            f'style="display:inline">'
            f'<input type="hidden" name="path" value="{esc(path)}">'
            f'<button type="submit" class="danger">Сбросить к дефолту</button>'
            f'</form>'
        )

    error_html = f'<div class="flash" style="background:#ffc9c9;color:#c92a2a">{esc(error)}</div>' if error else ""

    body = f"""
<h1>Страница <span class="code">{esc(path)}</span>
  <span class="kind {esc(page['kind'])}">{esc(page_kind_label(page['kind']))}</span>
</h1>
{error_html}
<form method="post" action="{url_for('save')}" class="edit">
  <input type="hidden" name="path" value="{esc(path)}">

  <div class="row">
    <label for="h1">H1 (заголовок страницы)</label>
    <input type="text" id="h1" name="h1" value="{esc(ov_h1)}" placeholder="Оставьте пустым, чтобы использовать дефолт">
    <div class="default"><b>Дефолт:</b> {esc(seo['h1'])}</div>
  </div>

  <div class="row">
    <label for="title">Title (вкладка браузера и поисковая выдача)</label>
    <input type="text" id="title" name="title" value="{esc(ov_title)}" placeholder="Оставьте пустым, чтобы использовать дефолт">
    <div class="hint">Рекомендуется 50–60 символов.</div>
    <div class="default"><b>Дефолт:</b> {esc(seo['title'])}</div>
  </div>

  <div class="row">
    <label for="description">Meta description (сниппет в поиске)</label>
    <textarea id="description" name="description" placeholder="Оставьте пустым, чтобы использовать дефолт">{esc(ov_desc)}</textarea>
    <div class="hint">Рекомендуется 140–160 символов.</div>
    <div class="default"><b>Дефолт:</b> {esc(seo['description'])}</div>
  </div>

  <div class="actions">
    <button type="submit" class="primary">Сохранить и опубликовать</button>
    <a href="{url_for('index')}"><button type="button" class="ghost">Отмена</button></a>
    <span style="flex:1"></span>
    {reset_form}
  </div>
</form>
"""
    return layout(f"Редактирование {path}", body)


# ---------- Routes ----------

@app.route("/")
@require_auth
def index():
    saved = request.args.get("saved")
    reset_path = request.args.get("reset")
    return render_index(saved=saved, reset=reset_path)


@app.route("/edit")
@require_auth
def edit():
    path = request.args.get("path", "")
    page = find_page(path)
    if not page:
        abort(404)
    seo = default_seo(page)
    ov = load_overrides().get(path, {}) or {}
    return render_edit(page, seo, ov)


@app.route("/save", methods=["POST"])
@require_auth
def save():
    path = (request.form.get("path") or "").strip()
    page = find_page(path)
    if not page:
        abort(400)

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    h1 = (request.form.get("h1") or "").strip()

    with _write_lock:
        overrides = load_overrides()
        page_ov: dict = {}
        if title:
            page_ov["title"] = title
        if description:
            page_ov["description"] = description
        if h1:
            page_ov["h1"] = h1

        if page_ov:
            overrides[path] = page_ov
        elif path in overrides:
            del overrides[path]

        save_overrides(overrides)
        ok, msg = trigger_build()

    if not ok:
        seo = default_seo(page)
        return render_edit(page, seo, {"title": title, "description": description, "h1": h1}, error=msg), 500

    return redirect(url_for("index", saved=path))


@app.route("/reset", methods=["POST"])
@require_auth
def reset():
    path = (request.form.get("path") or "").strip()
    if not path:
        abort(400)
    with _write_lock:
        overrides = load_overrides()
        if path in overrides:
            del overrides[path]
            save_overrides(overrides)
        ok, msg = trigger_build()
    if not ok:
        page = find_page(path)
        if page:
            return render_edit(page, default_seo(page), {}, error=msg), 500
    return redirect(url_for("index", reset=path))


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    app.run(host=ADMIN_BIND, port=ADMIN_PORT, debug=False)
