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
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="robots" content="noindex,nofollow">
<title>{esc(title)} — Админка SEO</title>
<style>
:root {{
  --bg: #f5f6f8;
  --surface: #ffffff;
  --surface-2: #f8f9fb;
  --border: #e3e6eb;
  --border-strong: #c9cfd6;
  --text: #1f2430;
  --text-muted: #5a6472;
  --text-soft: #8a93a1;
  --primary: #2563eb;
  --primary-strong: #1d4ed8;
  --danger: #dc2626;
  --danger-strong: #b91c1c;
  --warning: #d97706;
  --warning-soft: #fef3c7;
  --success: #16a34a;
  --success-soft: #dcfce7;
  --radius: 10px;
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06), 0 1px 1px rgba(15, 23, 42, 0.04);
  --shadow: 0 4px 14px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --mono: ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, Consolas, monospace;
}}

* {{ box-sizing: border-box; }}

html, body {{
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
}}

body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}

.topbar {{
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 14px 28px;
  display: flex;
  align-items: center;
  gap: 18px;
}}
.topbar .brand {{
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
  letter-spacing: -0.01em;
}}
.topbar .brand-sub {{
  color: var(--text-soft);
  font-weight: 500;
  margin-left: 6px;
}}
.topbar nav {{
  display: flex;
  gap: 18px;
  margin-left: auto;
  font-size: 14px;
}}
.topbar a {{
  color: var(--text-muted);
  text-decoration: none;
  font-weight: 500;
}}
.topbar a:hover {{ color: var(--primary); }}

.container {{
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px;
}}

h1 {{
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
  color: var(--text);
}}
h2 {{ font-size: 16px; margin: 24px 0 10px; color: var(--text); }}
.page-meta {{
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 22px;
}}

a {{ color: var(--primary); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.flash {{
  padding: 12px 16px;
  margin: 0 0 20px;
  background: var(--success-soft);
  color: #14532d;
  border: 1px solid #bbf7d0;
  border-radius: var(--radius);
  font-size: 14px;
}}
.flash.error {{
  background: #fee2e2;
  color: #7f1d1d;
  border-color: #fecaca;
  white-space: pre-wrap;
  font-family: var(--mono);
  font-size: 12px;
}}

/* ---- Таблица ---- */
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}}

table.list {{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}}
table.list col.col-path    {{ width: 28%; }}
table.list col.col-h1      {{ width: 32%; }}
table.list col.col-title   {{ width: 30%; }}
table.list col.col-action  {{ width: 10%; min-width: 130px; }}
table.list th,
table.list td {{
  padding: 12px 16px;
  text-align: left;
  vertical-align: middle;
  font-size: 14px;
  border-bottom: 1px solid var(--border);
  overflow: hidden;
}}
table.list thead th {{
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
  border-bottom: 1px solid var(--border);
}}
table.list tbody tr:last-child td {{ border-bottom: 0; }}
table.list tbody tr:hover td {{ background: var(--surface-2); }}
table.list tr.ov td {{ background: #fffaf0; }}
table.list tr.ov:hover td {{ background: #fff5e0; }}
table.list td.col-actions {{
  text-align: right;
  white-space: nowrap;
}}
table.list td .truncate {{
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}}
table.list td .truncate.muted {{ color: var(--text-muted); }}
table.list td .path-cell {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}}
table.list td .path-cell .path {{
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}}

.path {{
  font-family: var(--mono);
  font-size: 12.5px;
  color: var(--text);
  background: var(--surface-2);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
}}

.badge {{
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2f7;
  color: #475569;
  font-weight: 600;
  letter-spacing: 0.01em;
  margin-left: 6px;
  border: 1px solid transparent;
  vertical-align: middle;
  line-height: 1.5;
}}
.badge.home    {{ background: #dbeafe; color: #1d4ed8; }}
.badge.silo    {{ background: #dcfce7; color: #15803d; }}
.badge.hub     {{ background: #fef9c3; color: #854d0e; }}
.badge.leaf    {{ background: #fee2e2; color: #b91c1c; }}
.badge.sub     {{ background: #ede9fe; color: #6d28d9; }}
.badge.override {{
  background: var(--warning-soft);
  color: var(--warning);
  border-color: #fcd34d;
}}

/* ---- Кнопки/ссылки в действиях ---- */
.btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  padding: 9px 16px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  line-height: 1.2;
  transition: background-color 0.12s ease, border-color 0.12s ease;
}}
.btn:hover {{ text-decoration: none; }}
.btn-primary {{ background: var(--primary); color: #fff; }}
.btn-primary:hover {{ background: var(--primary-strong); }}
.btn-ghost {{ background: var(--surface); color: var(--text); border-color: var(--border-strong); }}
.btn-ghost:hover {{ background: var(--surface-2); }}
.btn-danger {{ background: var(--surface); color: var(--danger); border-color: #fecaca; }}
.btn-danger:hover {{ background: #fee2e2; color: var(--danger-strong); }}
.btn-link {{
  background: transparent;
  color: var(--primary);
  border: 0;
  padding: 6px 8px;
  font-weight: 600;
}}
.btn-link:hover {{ color: var(--primary-strong); }}
.btn-sm {{ font-size: 13px; padding: 6px 12px; }}

/* ---- Форма ---- */
.editor {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  padding: 28px;
  max-width: 820px;
}}
.editor .field {{ margin-bottom: 22px; }}
.editor label {{
  display: block;
  font-weight: 600;
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--text);
}}
.editor input[type=text],
.editor textarea {{
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  line-height: 1.4;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}}
.editor input[type=text]:focus,
.editor textarea:focus {{
  outline: 0;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}}
.editor textarea {{ min-height: 90px; resize: vertical; }}
.editor .hint {{ font-size: 12px; color: var(--text-muted); margin-top: 6px; }}
.editor .default {{
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  word-break: break-word;
  line-height: 1.5;
}}
.editor .default b {{ color: var(--text); font-weight: 600; }}
.editor .actions {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid var(--border);
}}
.editor .actions .spacer {{ flex: 1; }}

.subtitle {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}}
.subtitle .path {{ font-size: 13px; }}

@media (max-width: 900px) {{
  table.list col.col-title {{ width: 0; }}
  table.list th.col-title-th, table.list td.col-title-td {{ display: none; }}
}}
@media (max-width: 720px) {{
  .container {{ padding: 18px; }}
  .topbar {{ padding: 12px 18px; }}
  .editor {{ padding: 20px; }}
}}
</style></head><body>
<header class="topbar">
  <span class="brand">SEO админка<span class="brand-sub">· Надежда VPN</span></span>
  <nav>
    <a href="{url_for('index')}">Страницы</a>
    <a href="https://nadezhda.info/" target="_blank" rel="noopener">Открыть сайт ↗</a>
  </nav>
</header>
<main class="container">
{flash_html}
{body}
</main>
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
        ov_badge = '<span class="badge override">правки</span>' if r["overridden"] else ""
        cls = ' class="ov"' if r["overridden"] else ""
        rows_html.append(
            f'<tr{cls}>'
            f'<td><div class="path-cell">'
            f'<span class="path">{esc(r["path"])}</span>'
            f'<span class="badge {esc(r["kind"])}">{esc(page_kind_label(r["kind"]))}</span>'
            f'{ov_badge}'
            f'</div></td>'
            f'<td><span class="truncate" title="{esc(r["h1"])}">{esc(r["h1"])}</span></td>'
            f'<td class="col-title-td"><span class="truncate muted" title="{esc(r["title"])}">{esc(r["title"])}</span></td>'
            f'<td class="col-actions">'
            f'<a class="btn btn-ghost btn-sm" href="{url_for("edit", path=r["path"])}">Редактировать</a></td>'
            f'</tr>'
        )

    flash = ""
    if saved:
        flash = f'Сохранено и опубликовано: <span class="path">{esc(saved)}</span>'
    elif reset:
        flash = f'Сброшено к дефолту: <span class="path">{esc(reset)}</span>'

    total = len(rows)
    overridden_n = sum(1 for r in rows if r["overridden"])
    body = (
        f'<h1>SEO-страницы лендинга</h1>'
        f'<p class="page-meta">Всего страниц: <b>{total}</b> · с переопределённым SEO: <b>{overridden_n}</b></p>'
        f'<div class="card">'
        f'<table class="list">'
        f'<colgroup>'
        f'<col class="col-path">'
        f'<col class="col-h1">'
        f'<col class="col-title">'
        f'<col class="col-action">'
        f'</colgroup>'
        f'<thead><tr><th>Путь</th><th>H1</th><th class="col-title-th">Title</th><th></th></tr></thead>'
        f'<tbody>' + "".join(rows_html) + '</tbody>'
        f'</table></div>'
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
            f'<button type="submit" class="btn btn-danger">Сбросить к дефолту</button>'
            f'</form>'
        )

    error_html = f'<div class="flash error">{esc(error)}</div>' if error else ""

    body = f"""
<h1>Редактирование SEO</h1>
<div class="subtitle">
  <span class="path">{esc(path)}</span>
  <span class="badge {esc(page['kind'])}">{esc(page_kind_label(page['kind']))}</span>
</div>
{error_html}
<form method="post" action="{url_for('save')}" class="editor">
  <input type="hidden" name="path" value="{esc(path)}">

  <div class="field">
    <label for="h1">H1 — заголовок на странице</label>
    <input type="text" id="h1" name="h1" value="{esc(ov_h1)}" placeholder="Оставьте пустым, чтобы использовать дефолт" autocomplete="off">
    <div class="default"><b>Дефолт:</b> {esc(seo['h1'])}</div>
  </div>

  <div class="field">
    <label for="title">Title — вкладка браузера и поисковая выдача</label>
    <input type="text" id="title" name="title" value="{esc(ov_title)}" placeholder="Оставьте пустым, чтобы использовать дефолт" autocomplete="off">
    <div class="hint">Рекомендуется 50–60 символов.</div>
    <div class="default"><b>Дефолт:</b> {esc(seo['title'])}</div>
  </div>

  <div class="field">
    <label for="description">Meta description — сниппет в поиске</label>
    <textarea id="description" name="description" placeholder="Оставьте пустым, чтобы использовать дефолт">{esc(ov_desc)}</textarea>
    <div class="hint">Рекомендуется 140–160 символов.</div>
    <div class="default"><b>Дефолт:</b> {esc(seo['description'])}</div>
  </div>

  <div class="actions">
    <button type="submit" class="btn btn-primary">Сохранить и опубликовать</button>
    <a class="btn btn-ghost" href="{url_for('index')}">Отмена</a>
    <span class="spacer"></span>
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
