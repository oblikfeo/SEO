# -*- coding: utf-8 -*-
"""Мини-админка для управления SEO (title / description / H1) SEO-лендинга.

КРИТИЧНО: «Сохранить и опубликовать» пишет в content_overrides.json на сервере.
Этот файл — рабочая база SEO; в git только пустой {}. Деплой без safe_git_update.sh
(git reset --hard) СТИРАЕТ недели работы. См. AGENTS-SEO.md, content_overrides.README.txt.

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

from flask import Flask, Response, abort, redirect, request, send_file, url_for
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

# Фиксированные ключи шагов HowTo (сейчас в build_pages.py распознаются только эти).
HOWTO_KEYS = ["registration", "apk", "import"]
HOWTO_KEY_HINT = {
    "registration": "ссылка ведёт на «Регистрация в Личном Кабинете»",
    "apk": "ссылка ведёт на «Скачать Happ (APK)»",
    "import": "ссылка ведёт на «Импорт ссылки подписки в Happ»",
}

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
ADMIN_BIND = os.environ.get("ADMIN_BIND", "127.0.0.1")
ADMIN_PORT = int(os.environ.get("ADMIN_PORT", "5050"))
# Секретный токен для публичной ссылки скачивания content_overrides.json
# (страховка от потери данных при сбросе сервера). Задаётся в /etc/seo-admin.env
# через install_admin.sh. Пустое значение = публичная скачка отключена.
DOWNLOAD_TOKEN = os.environ.get("DOWNLOAD_TOKEN", "").strip()
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


def index_row_from_page(page: dict, overrides: dict) -> dict:
    path = page["path"]
    seo = default_seo(page)
    ov = overrides.get(path, {}) or {}
    return {
        "path": path,
        "kind": page["kind"],
        "silo": page.get("silo"),
        "hub": page.get("hub"),
        "leaf": page.get("leaf"),
        "sub": page.get("sub"),
        "title": (ov.get("title") or "").strip() or seo["title"],
        "h1": (ov.get("h1") or "").strip() or seo["h1"],
        "overridden": any((ov.get(k) or "").strip() for k in ("title", "description", "h1")),
    }


def _hub_page_sort_key(silo: str, hub: str, row: dict) -> tuple:
    order = LEAVES.get((silo, hub), [])
    slug = row.get("sub") or row.get("leaf") or ""
    try:
        idx = order.index(slug)
    except ValueError:
        idx = 999
    return (idx, row["path"])


def build_index_tree(rows: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Группировка для списка в админке: главная + silo → hub → страницы."""
    home: list[dict] = []
    silos: dict[str, dict] = {
        silo: {"silo_row": None, "hubs": {}}
        for silo in SILO_META
    }

    for row in rows:
        kind = row["kind"]
        if kind == "home":
            home.append(row)
            continue
        silo = row.get("silo")
        if not silo or silo not in silos:
            continue
        if kind == "silo":
            silos[silo]["silo_row"] = row
        elif kind == "hub":
            hub = row["hub"]
            if hub:
                silos[silo]["hubs"].setdefault(hub, {"hub_row": None, "pages": []})
                silos[silo]["hubs"][hub]["hub_row"] = row
        elif kind in ("leaf", "sub"):
            hub = row.get("hub")
            if hub:
                silos[silo]["hubs"].setdefault(hub, {"hub_row": None, "pages": []})
                silos[silo]["hubs"][hub]["pages"].append(row)

    for silo, data in silos.items():
        for hub, hub_data in data["hubs"].items():
            hub_data["pages"].sort(key=lambda r: _hub_page_sort_key(silo, hub, r))

    return home, silos


def index_row_display_name(row: dict) -> str:
    if row["kind"] == "home":
        return "Главная"
    if row["kind"] == "silo" and row.get("silo"):
        return SILO_META[row["silo"]][0]
    if row["kind"] == "hub" and row.get("silo") and row.get("hub"):
        for slug, title, _desc in HUBS.get(row["silo"], []):
            if slug == row["hub"]:
                return title
        return LABELS.get(row["hub"], row["hub"])
    slug = row.get("sub") or row.get("leaf")
    if slug:
        return LABELS.get(slug, slug.replace("-", " ").title())
    return row["h1"][:60]


def render_index_alt_tile(row: dict) -> str:
    name = index_row_display_name(row)
    search = " ".join(
        (row["path"], name, row["h1"], row["title"], page_kind_label(row["kind"]))
    ).lower()
    cls = "alt-tile ov" if row["overridden"] else "alt-tile"
    ov = '<span class="badge override">правки</span>' if row["overridden"] else ""
    edit = url_for("edit", path=row["path"])
    return (
        f'<a class="{cls}" href="{edit}" data-search="{esc(search)}">'
        f'<span class="alt-tile__name">{esc(name)}</span>'
        f'<span class="alt-tile__path">{esc(row["path"])}</span>'
        f'<span class="alt-tile__meta">'
        f'<span class="badge {esc(row["kind"])}">{esc(page_kind_label(row["kind"]))}</span>'
        f"{ov}"
        f"</span></a>"
    )


def _render_index_alt_hub(silo: str, hub_slug: str, hub_data: dict) -> str:
    hub_row = hub_data["hub_row"]
    pages = hub_data["pages"]
    hub_title = LABELS.get(hub_slug, hub_slug.replace("-", " ").title())
    for slug, title, _desc in HUBS.get(silo, []):
        if slug == hub_slug:
            hub_title = title
            break
    tiles = []
    if hub_row:
        tiles.append(render_index_alt_tile(hub_row))
    tiles.extend(render_index_alt_tile(r) for r in pages)
    return (
        f'<div class="alt-hub">'
        f'<h3 class="alt-hub__title">{esc(hub_title)}</h3>'
        f'<p class="alt-hub__url">/{esc(silo)}/{esc(hub_slug)}/</p>'
        f'<div class="alt-tiles">{"".join(tiles)}</div>'
        f"</div>"
    )


def render_index_alt_html(home: list[dict], silos: dict[str, dict]) -> str:
    """Плитки по разделам — только для html.admin-alt. Разделы свёрнуты по умолчанию."""
    parts: list[str] = ['<div class="alt-index">']
    hub_order = {s: [h[0] for h in hubs] for s, hubs in HUBS.items()}

    if home:
        parts.append(
            '<details class="alt-silo alt-silo--home">'
            '<summary class="alt-silo__head">'
            '<span class="alt-silo__title">Главная</span>'
            f'<span class="alt-silo__count">{len(home)} стр.</span>'
            "</summary>"
            f'<div class="alt-silo__body">'
            f'<div class="alt-tiles">{"".join(render_index_alt_tile(r) for r in home)}</div>'
            "</div></details>"
        )

    for silo in SILO_META:
        data = silos[silo]
        silo_row = data["silo_row"]
        hubs = data["hubs"]
        n = (1 if silo_row else 0) + sum(
            (1 if h["hub_row"] else 0) + len(h["pages"]) for h in hubs.values()
        )
        if not n:
            continue
        silo_title, _ = SILO_META[silo]
        body_parts: list[str] = ['<div class="alt-silo__body">']
        top_tiles = []
        if silo_row:
            top_tiles.append(render_index_alt_tile(silo_row))
        if top_tiles:
            body_parts.append(
                f'<div class="alt-tiles alt-tiles--l1">{"".join(top_tiles)}</div>'
            )
        body_parts.append('<div class="alt-hubs">')
        seen: set[str] = set()
        for hub_slug in hub_order.get(silo, []):
            if hub_slug in hubs:
                seen.add(hub_slug)
                body_parts.append(_render_index_alt_hub(silo, hub_slug, hubs[hub_slug]))
        for hub_slug in sorted(hubs.keys()):
            if hub_slug not in seen:
                body_parts.append(_render_index_alt_hub(silo, hub_slug, hubs[hub_slug]))
        body_parts.append("</div></div>")

        parts.append(
            f'<details class="alt-silo" data-silo="{esc(silo)}">'
            f'<summary class="alt-silo__head">'
            f'<span class="alt-silo__title">{esc(silo_title)}</span>'
            f'<span class="alt-silo__url">/{esc(silo)}/</span>'
            f'<span class="alt-silo__count">{n} стр.</span>'
            f"</summary>"
            + "".join(body_parts)
            + "</details>"
        )

    parts.append("</div>")
    return "".join(parts)


INDEX_LIST_JS = r"""
<script>
(function () {
  var q = document.getElementById('idx-search');
  if (!q) return;
  var tiles = document.querySelectorAll('.alt-index .alt-tile');
  var hubs = document.querySelectorAll('.alt-index .alt-hub');
  var silos = document.querySelectorAll('.alt-index details.alt-silo');
  function applyFilter() {
    var t = q.value.trim().toLowerCase();
    tiles.forEach(function (el) {
      var hay = el.getAttribute('data-search') || '';
      el.classList.toggle('alt-tile--hidden', !!(t && hay.indexOf(t) < 0));
    });
    hubs.forEach(function (hub) {
      var any = hub.querySelector('.alt-tile:not(.alt-tile--hidden)');
      hub.style.display = (!t || any) ? '' : 'none';
    });
    silos.forEach(function (det) {
      var any = det.querySelector('.alt-tile:not(.alt-tile--hidden)');
      if (t) {
        det.open = !!any;
        det.style.display = any ? '' : 'none';
      } else {
        det.style.display = '';
      }
    });
  }
  q.addEventListener('input', applyFilter);
})();
function altExpandSections() {
  document.querySelectorAll('.alt-index details.alt-silo').forEach(function (d) {
    d.open = true;
  });
}
function altCollapseSections() {
  document.querySelectorAll('.alt-index details.alt-silo').forEach(function (d) {
    d.open = false;
  });
}
</script>
"""


def find_page(path: str) -> dict | None:
    for p in build_pages_list():
        if p["path"] == path:
            return p
    return None


# ---------- Контент-блоки: дефолты, нормализация, конверсия ----------

def section_tuple_to_dict(sec) -> dict:
    """Преобразует кортеж секции из site_data.py в редактируемый dict."""
    t = sec[0]
    if t == "snippet":
        return {"type": "snippet", "text": sec[1]}
    if t == "prose":
        return {"type": "prose", "html": sec[1]}
    if t == "howto":
        return {"type": "howto", "items": [{"key": k, "label": l} for k, l in sec[1]]}
    if t == "trial":
        return {"type": "trial"}
    if t == "faq":
        return {"type": "faq", "items": [{"q": q, "a": a} for q, a in sec[1]]}
    if t == "table":
        return {
            "type": "table",
            "headers": list(sec[1]),
            "rows": [list(r) for r in sec[2]],
        }
    if t == "cards":
        return {
            "type": "cards",
            "items": [
                {"title": ti, "desc": d, "href": h, "tag": tg}
                for ti, d, h, tg in sec[1]
            ],
        }
    if t == "related":
        return {
            "type": "related",
            "title": sec[1],
            "items": [{"label": l, "href": h} for l, h in sec[2]],
        }
    return {"type": "unknown"}


# Единый набор блоков по уровню страницы (чтобы все L1/L2/L3/L4 были
# одинаковыми и одинаково редактировались в админке). Карточки навигации и
# блок «Связанные» добавляются движком автоматически и здесь не указываются.
LEVEL_SKELETON = {
    "silo": ["snippet", "prose", "trial"],
    "hub": ["snippet", "prose", "table", "trial", "faq"],
    "leaf": ["snippet", "prose", "howto", "trial", "faq", "table"],
    "sub": ["snippet", "prose", "howto", "trial", "faq", "table"],
}

# Блоки, которые можно добавлять/удалять/двигать в админке.
ADDABLE_BLOCKS = ["snippet", "prose", "howto", "trial", "faq", "table"]

ADD_BLOCK_LABELS = {
    "snippet": "Сниппет",
    "prose": "Текст",
    "howto": "Шаги Happ",
    "trial": "Тест 8 часов",
    "faq": "FAQ",
    "table": "Таблица",
}


def empty_block(t: str) -> dict:
    """Пустой блок выбранного типа для стартового шаблона/добавления."""
    if t == "snippet":
        return {"type": "snippet", "text": ""}
    if t == "prose":
        return {"type": "prose", "html": ""}
    if t == "howto":
        return {"type": "howto", "items": []}
    if t == "trial":
        return {"type": "trial"}
    if t == "faq":
        return {"type": "faq", "items": [{"q": "", "a": ""}, {"q": "", "a": ""}]}
    if t == "table":
        return {"type": "table", "headers": ["", ""], "rows": [["", ""], ["", ""]]}
    return {"type": t}


def default_sections_for_editing(page: dict) -> list[dict]:
    path = page["path"]
    if path == "/":
        return [section_tuple_to_dict(s) for s in HOME["sections"]]
    if path in CONTENT:
        return [section_tuple_to_dict(s) for s in CONTENT[path]["sections"]]
    # Единый по уровню скелет: одинаковый набор блоков для всех страниц
    # этого уровня. СЕО-специалист заполняет их текстом в админке.
    kind = page.get("kind", "leaf")
    skeleton = LEVEL_SKELETON.get(kind, LEVEL_SKELETON["leaf"])
    return [empty_block(t) for t in skeleton]


def editor_sections(page: dict) -> list[dict]:
    """Что показывать в форме редактирования: override (если есть) либо дефолт."""
    ov_secs = load_overrides().get(page["path"], {}).get("sections")
    if isinstance(ov_secs, list) and ov_secs:
        return [s for s in ov_secs if isinstance(s, dict)]
    return default_sections_for_editing(page)


def sections_normalized(secs: list) -> list[dict]:
    """Удаляет пустые поля/пары/строки. Используется и для сохранения,
    и для сравнения «изменилось ли по сравнению с дефолтом»."""
    out: list[dict] = []
    for s in secs:
        if not isinstance(s, dict):
            continue
        t = (s.get("type") or "").strip().lower()
        if t == "snippet":
            text = (s.get("text") or "").strip()
            if text:
                out.append({"type": "snippet", "text": text})
        elif t == "prose":
            h = (s.get("html") or "").strip()
            if h:
                out.append({"type": "prose", "html": h})
        elif t == "howto":
            items = []
            for it in s.get("items") or []:
                if not isinstance(it, dict):
                    continue
                k = (it.get("key") or "").strip()
                l = (it.get("label") or "").strip()
                if k:
                    items.append({"key": k, "label": l})
            if items:
                out.append({"type": "howto", "items": items})
        elif t == "trial":
            out.append({"type": "trial"})
        elif t == "faq":
            items = []
            for it in s.get("items") or []:
                if not isinstance(it, dict):
                    continue
                q = (it.get("q") or "").strip()
                a = (it.get("a") or "").strip()
                if q and a:
                    items.append({"q": q, "a": a})
            if items:
                out.append({"type": "faq", "items": items})
        elif t == "table":
            headers = [(h or "").strip() for h in s.get("headers") or []]
            rows = []
            for r in s.get("rows") or []:
                if not isinstance(r, list):
                    continue
                row = [(c or "").strip() for c in r]
                if any(row):
                    rows.append(row)
            if any(headers) and rows:
                out.append({"type": "table", "headers": headers, "rows": rows})
        elif t == "cards":
            items = []
            for it in s.get("items") or []:
                if not isinstance(it, dict):
                    continue
                ti = (it.get("title") or "").strip()
                de = (it.get("desc") or "").strip()
                he = (it.get("href") or "").strip()
                ta = (it.get("tag") or "").strip()
                if ti and he:
                    items.append({"title": ti, "desc": de, "href": he, "tag": ta})
            if items:
                out.append({"type": "cards", "items": items})
        elif t == "related":
            title = (s.get("title") or "").strip()
            items = []
            for it in s.get("items") or []:
                if not isinstance(it, dict):
                    continue
                label = (it.get("label") or "").strip()
                href = (it.get("href") or "").strip()
                if label and href:
                    items.append({"label": label, "href": href})
            if title and items:
                out.append({"type": "related", "title": title, "items": items})
    return out


def sections_equal_to_default(submitted: list, page: dict) -> bool:
    return sections_normalized(submitted) == sections_normalized(
        default_sections_for_editing(page)
    )


def parse_sections_from_form(form) -> list[dict]:
    count = int((form.get("sections_count") or "0") or "0")
    out: list[dict] = []
    for i in range(count):
        t = (form.get(f"s_{i}_type") or "").strip().lower()
        if t == "snippet":
            out.append({"type": "snippet", "text": (form.get(f"s_{i}_text") or "")})
        elif t == "prose":
            out.append({"type": "prose", "html": (form.get(f"s_{i}_html") or "")})
        elif t == "howto":
            n = int((form.get(f"s_{i}_count") or "0") or "0")
            items = []
            for j in range(n):
                items.append({
                    "key": (form.get(f"s_{i}_key_{j}") or ""),
                    "label": (form.get(f"s_{i}_label_{j}") or ""),
                })
            out.append({"type": "howto", "items": items})
        elif t == "trial":
            out.append({"type": "trial"})
        elif t == "faq":
            n = int((form.get(f"s_{i}_count") or "0") or "0")
            items = []
            for j in range(n):
                items.append({
                    "q": (form.get(f"s_{i}_q_{j}") or ""),
                    "a": (form.get(f"s_{i}_a_{j}") or ""),
                })
            out.append({"type": "faq", "items": items})
        elif t == "table":
            cols = int((form.get(f"s_{i}_cols") or "0") or "0")
            rows_n = int((form.get(f"s_{i}_rows") or "0") or "0")
            headers = [(form.get(f"s_{i}_h_{c}") or "") for c in range(cols)]
            rows = []
            for r in range(rows_n):
                row = [(form.get(f"s_{i}_cell_{r}_{c}") or "") for c in range(cols)]
                rows.append(row)
            out.append({"type": "table", "headers": headers, "rows": rows})
        elif t == "cards":
            n = int((form.get(f"s_{i}_count") or "0") or "0")
            items = []
            for j in range(n):
                items.append({
                    "title": (form.get(f"s_{i}_card_{j}_title") or ""),
                    "desc": (form.get(f"s_{i}_card_{j}_desc") or ""),
                    "href": (form.get(f"s_{i}_card_{j}_href") or ""),
                    "tag": (form.get(f"s_{i}_card_{j}_tag") or ""),
                })
            out.append({"type": "cards", "items": items})
        elif t == "related":
            n = int((form.get(f"s_{i}_count") or "0") or "0")
            items = []
            for j in range(n):
                items.append({
                    "label": (form.get(f"s_{i}_rel_{j}_label") or ""),
                    "href": (form.get(f"s_{i}_rel_{j}_href") or ""),
                })
            out.append({
                "type": "related",
                "title": (form.get(f"s_{i}_title") or ""),
                "items": items,
            })
    return out


def render_section_widget(i: int, section: dict) -> str:
    t = (section.get("type") or "").lower()
    hidden_type = f'<input type="hidden" name="s_{i}_type" value="{esc(t)}">'
    num = f'<span class="section-num">#{i + 1}</span>'

    if t == "snippet":
        text = section.get("text") or ""
        return f"""
<section class="block block--snippet">
  <header class="block-head">{num}<span class="block-title">Сниппет — короткий лид-абзац</span>
  <span class="block-hint">≤300 символов, без HTML</span></header>
  {hidden_type}
  <textarea name="s_{i}_text" rows="3" placeholder="Короткое вступление">{esc(text)}</textarea>
</section>"""

    if t == "prose":
        html = section.get("html") or ""
        return f"""
<section class="block block--prose">
  <header class="block-head">{num}<span class="block-title">Блок текста</span>
  <span class="block-hint">HTML: &lt;h2&gt;, &lt;h3&gt;, &lt;p&gt;, &lt;ul&gt;, &lt;ol&gt;, &lt;strong&gt;</span></header>
  {hidden_type}
  <textarea name="s_{i}_html" rows="12" class="mono">{esc(html)}</textarea>
</section>"""

    if t == "howto":
        items = section.get("items") or []
        items = [it for it in items if isinstance(it, dict)]
        # гарантируем 3 стандартных ключа в порядке
        by_key = {it.get("key", ""): it.get("label", "") for it in items}
        steps_html = []
        steps_html.append(f'<input type="hidden" name="s_{i}_count" value="{len(HOWTO_KEYS)}">')
        for j, key in enumerate(HOWTO_KEYS):
            label = by_key.get(key, "")
            hint = HOWTO_KEY_HINT.get(key, "")
            steps_html.append(
                f'<div class="howto-row">'
                f'<input type="hidden" name="s_{i}_key_{j}" value="{esc(key)}">'
                f'<div class="howto-meta"><b>Шаг {j + 1}</b><span class="howto-key">{esc(key)}</span>'
                f'<span class="howto-hint">{esc(hint)}</span></div>'
                f'<input type="text" name="s_{i}_label_{j}" value="{esc(label)}" placeholder="Название шага">'
                f'</div>'
            )
        return f"""
<section class="block block--howto">
  <header class="block-head">{num}<span class="block-title">Шаги настройки через Happ</span>
  <span class="block-hint">Ключи шагов фиксированы — менять только подпись</span></header>
  {hidden_type}
  {"".join(steps_html)}
</section>"""

    if t == "trial":
        return f"""
<section class="block block--locked">
  <header class="block-head">{num}<span class="block-title">Блок «Бесплатный тест 8 часов»</span>
  <span class="locked-tag">фиксированный</span></header>
  {hidden_type}
  <p class="block-note">Кнопка регистрации + краткое описание триала. Текст этого блока вшит в шаблон.</p>
</section>"""

    if t == "faq":
        items_in = section.get("items") or []
        items_in = [it for it in items_in if isinstance(it, dict)]
        # рендерим существующие + 2 пустых слота
        total = max(len(items_in), 0) + 2
        rows = [f'<input type="hidden" name="s_{i}_count" value="{total}">']
        for j in range(total):
            q = items_in[j].get("q", "") if j < len(items_in) else ""
            a = items_in[j].get("a", "") if j < len(items_in) else ""
            rows.append(
                f'<div class="faq-row">'
                f'<input type="text" name="s_{i}_q_{j}" value="{esc(q)}" placeholder="Вопрос {j + 1}">'
                f'<textarea name="s_{i}_a_{j}" rows="2" placeholder="Ответ">{esc(a)}</textarea>'
                f'</div>'
            )
        return f"""
<section class="block block--faq">
  <header class="block-head">{num}<span class="block-title">FAQ — вопросы и ответы</span>
  <span class="block-hint">Пустые пары не сохраняются. Добавляйте, заполняя пустые слоты.</span></header>
  {hidden_type}
  {"".join(rows)}
</section>"""

    if t == "table":
        headers = list(section.get("headers") or [])
        rows = list(section.get("rows") or [])
        cols = len(headers)
        if cols == 0:
            cols = 2
            headers = ["", ""]
        rows = [list(r) + [""] * max(0, cols - len(r)) for r in rows]
        rows_n = len(rows)
        thead_cells = "".join(
            f'<th><input type="text" name="s_{i}_h_{c}" value="{esc(headers[c])}" '
            f'class="th" placeholder="Заголовок {c + 1}"></th>'
            for c in range(cols)
        )
        tbody_rows = []
        for r in range(rows_n):
            tds = "".join(
                f'<td><input type="text" name="s_{i}_cell_{r}_{c}" value="{esc(rows[r][c])}"></td>'
                for c in range(cols)
            )
            tbody_rows.append(f"<tr>{tds}</tr>")
        return f"""
<section class="block block--table">
  <header class="block-head">{num}<span class="block-title">Таблица (<span class="tbl-size">{rows_n} × {cols}</span>)</span>
  <span class="block-hint">Пустые строки пропускаются. Размер меняйте кнопками ниже.</span></header>
  {hidden_type}
  <div class="tbl-wrap">
    <input type="hidden" name="s_{i}_cols" value="{cols}">
    <input type="hidden" name="s_{i}_rows" value="{rows_n}">
    <div class="tbl-scroll">
      <table class="tbl-edit">
        <thead><tr>{thead_cells}</tr></thead>
        <tbody>{"".join(tbody_rows)}</tbody>
      </table>
    </div>
    <div class="tbl-tools">
      <button type="button" class="btn btn-ghost btn-sm" data-tbl="add-row">+ строка</button>
      <button type="button" class="btn btn-ghost btn-sm" data-tbl="del-row">− строка</button>
      <span class="tbl-tools-sep"></span>
      <button type="button" class="btn btn-ghost btn-sm" data-tbl="add-col">+ столбец</button>
      <button type="button" class="btn btn-ghost btn-sm" data-tbl="del-col">− столбец</button>
    </div>
  </div>
</section>"""

    if t == "cards":
        items = [it for it in (section.get("items") or []) if isinstance(it, dict)]
        passthrough = [f'<input type="hidden" name="s_{i}_count" value="{len(items)}">']
        rows = []
        for j, it in enumerate(items):
            ti = it.get("title", "") or ""
            de = it.get("desc", "") or ""
            he = it.get("href", "") or ""
            ta = it.get("tag", "") or ""
            for k, v in (("title", ti), ("desc", de), ("href", he), ("tag", ta)):
                passthrough.append(
                    f'<input type="hidden" name="s_{i}_card_{j}_{k}" value="{esc(v)}">'
                )
            rows.append(
                f'<li><b>{esc(ti)}</b>'
                + (f' <span class="cards-desc">— {esc(de)}</span>' if de else "")
                + f' <span class="path">{esc(he)}</span></li>'
            )
        return f"""
<section class="block block--locked block--cards">
  <header class="block-head">{num}<span class="block-title">Карточки навигации ({len(items)} шт.)</span>
  <span class="locked-tag">не редактируется</span></header>
  {hidden_type}
  {"".join(passthrough)}
  <ul class="cards-preview">{"".join(rows)}</ul>
  <p class="block-note">Содержимое карточек правится в коде (scripts/site_data.py). Через админку отображается, но не меняется.</p>
</section>"""

    if t == "related":
        items = [it for it in (section.get("items") or []) if isinstance(it, dict)]
        title = section.get("title", "") or ""
        passthrough = [
            f'<input type="hidden" name="s_{i}_title" value="{esc(title)}">',
            f'<input type="hidden" name="s_{i}_count" value="{len(items)}">',
        ]
        rows = []
        for j, it in enumerate(items):
            label = it.get("label", "") or ""
            href = it.get("href", "") or ""
            for k, v in (("label", label), ("href", href)):
                passthrough.append(
                    f'<input type="hidden" name="s_{i}_rel_{j}_{k}" value="{esc(v)}">'
                )
            rows.append(f'<li><b>{esc(label)}</b> <span class="path">{esc(href)}</span></li>')
        return f"""
<section class="block block--locked">
  <header class="block-head">{num}<span class="block-title">Связанные ссылки: {esc(title)}</span>
  <span class="locked-tag">авто</span></header>
  {"".join(passthrough)}
  {hidden_type}
  <ul class="cards-preview">{"".join(rows)}</ul>
</section>"""

    return f"""
<section class="block block--locked">
  <header class="block-head">{num}<span class="block-title">Неизвестный блок «{esc(t)}»</span></header>
  {hidden_type}
</section>"""


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


# Переключатель «Альтернативный вид»: класс admin-alt на <html> + сохранение в
# localStorage. Базовый вид не меняется — это отдельная тема поверх той же вёрстки.
ALT_VIEW_HEAD = """
<script>
(function(){try{if(localStorage.getItem('adminAltView')==='1'){document.documentElement.classList.add('admin-alt');}}catch(e){}})();
function toggleAltView(){try{var on=document.documentElement.classList.toggle('admin-alt');localStorage.setItem('adminAltView',on?'1':'0');}catch(e){}}
</script>
"""

ALT_VIEW_CSS = """
/* ======== Альтернативный вид — только при class admin-alt на <html> ======== */
.view-toggle {
  font-family: inherit; font-size: 13px; font-weight: 600;
  color: var(--text-muted); background: var(--surface-2);
  border: 1px solid var(--border-strong); border-radius: 8px;
  padding: 7px 13px; cursor: pointer; line-height: 1.2;
}
.view-toggle:hover { color: var(--primary); border-color: var(--primary); }
html.admin-alt .view-toggle { background: var(--primary); color: #fff; border-color: var(--primary); }

.index-view-alt { display: none; }
.page-meta-alt { display: none; }
html.admin-alt .index-view-default { display: none !important; }
html.admin-alt .page-meta-default { display: none; }
html.admin-alt .index-view-alt { display: block; }
html.admin-alt .page-meta-alt { display: block; }

/* Список: панель поиска */
html.admin-alt .index-toolbar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  margin-bottom: 18px;
}
html.admin-alt .idx-search {
  flex: 1; min-width: 200px; max-width: 420px;
  font: inherit; font-size: 14px; padding: 10px 14px;
  border: 1px solid var(--border-strong); border-radius: 8px;
}
html.admin-alt .idx-search:focus {
  outline: none; border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
html.admin-alt .index-toolbar__hint {
  font-size: 12px; color: var(--text-muted);
}

/* Разделы сайта — сворачиваемые блоки */
html.admin-alt .alt-index { display: flex; flex-direction: column; gap: 10px; }
html.admin-alt details.alt-silo {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; box-shadow: var(--shadow-sm); overflow: hidden;
}
html.admin-alt details.alt-silo > summary {
  list-style: none; cursor: pointer; user-select: none;
}
html.admin-alt details.alt-silo > summary::-webkit-details-marker { display: none; }
html.admin-alt summary.alt-silo__head {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px;
  padding: 14px 18px; background: var(--surface-2);
}
html.admin-alt summary.alt-silo__head::before {
  content: "▸"; color: var(--text-soft); font-size: 12px; width: 14px;
}
html.admin-alt details.alt-silo[open] > summary.alt-silo__head::before { content: "▾"; }
html.admin-alt details.alt-silo[open] > summary.alt-silo__head {
  border-bottom: 2px solid var(--primary);
}
html.admin-alt .alt-silo__body { padding: 14px 18px 18px; }
html.admin-alt .alt-silo__title { font-size: 16px; font-weight: 700; flex: 1; }
html.admin-alt .alt-silo__url {
  font-family: var(--mono); font-size: 12px; color: var(--text-muted);
}
html.admin-alt .alt-silo__count {
  font-size: 12px; font-weight: 600; color: var(--primary);
  background: #eff6ff; padding: 4px 10px; border-radius: 999px;
}
html.admin-alt .alt-hubs {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px; margin-top: 12px;
}
html.admin-alt .alt-hub {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px 14px;
}
html.admin-alt .alt-hub__title { margin: 0 0 4px; font-size: 14px; font-weight: 700; }
html.admin-alt .alt-hub__url {
  margin: 0 0 10px; font-family: var(--mono); font-size: 11px;
  color: var(--text-soft);
}
html.admin-alt .alt-tiles {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}
html.admin-alt .alt-tiles--l1 { margin-bottom: 12px; }
html.admin-alt .alt-tile {
  display: flex; flex-direction: column; gap: 4px;
  padding: 10px 12px; text-decoration: none; color: inherit;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; min-height: 72px;
  transition: border-color 0.12s, box-shadow 0.12s;
}
html.admin-alt .alt-tile:hover {
  border-color: var(--primary); box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15);
  text-decoration: none;
}
html.admin-alt .alt-tile.ov { border-color: #fcd34d; background: #fffbeb; }
html.admin-alt .alt-tile--hidden { display: none !important; }
html.admin-alt .alt-tile__name { font-size: 13px; font-weight: 600; color: var(--text); line-height: 1.3; }
html.admin-alt .alt-tile__path {
  font-family: var(--mono); font-size: 10px; color: var(--text-muted);
  word-break: break-all; line-height: 1.35;
}
html.admin-alt .alt-tile__meta { margin-top: auto; display: flex; flex-wrap: wrap; gap: 4px; }

/* Форма редактирования */
html.admin-alt .editor { max-width: 880px; }
html.admin-alt .block { background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; }
html.admin-alt table.tbl-edit { border-collapse: collapse; border-spacing: 0; width: 100%; table-layout: fixed; }
html.admin-alt table.tbl-edit th,
html.admin-alt table.tbl-edit td { padding: 0; border: 1px solid var(--border); }
html.admin-alt table.tbl-edit input[type=text] { border: 0; border-radius: 0; min-width: 0; background: var(--surface); }
html.admin-alt table.tbl-edit input[type=text].th { background: var(--surface-2); font-weight: 600; }
"""


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
.admin-critical-banner {{
  padding: 12px 16px;
  margin: 0 0 20px;
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fcd34d;
  border-radius: var(--radius);
  font-size: 13px;
  line-height: 1.5;
}}
.admin-critical-banner strong {{ color: #78350f; }}

.add-bar {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
  padding: 12px 14px;
  background: var(--surface-2);
  border: 1px dashed var(--border-strong);
  border-radius: 10px;
}}
.add-bar__label {{
  font-weight: 600;
  font-size: 13px;
  color: var(--text-muted);
  margin-right: 4px;
}}
.block-ctrls {{
  display: inline-flex;
  gap: 4px;
  margin-left: 8px;
}}
.block-ctrls .bc {{
  cursor: pointer;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text-muted);
  border-radius: 6px;
  width: 28px;
  height: 28px;
  line-height: 1;
  font-size: 13px;
  padding: 0;
}}
.block-ctrls .bc:hover {{ background: var(--surface-2); color: var(--text); }}
.block-ctrls .bc-del:hover {{ background: #fee2e2; color: var(--danger); border-color: #fecaca; }}
template {{ display: none; }}

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

/* ---- Контент-блоки ---- */
.section-h {{
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid var(--border);
  font-size: 15px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--text-muted);
}}
.section-h:first-of-type {{ margin-top: 0; padding-top: 0; border-top: 0; }}
.section-note {{
  font-size: 13px;
  color: var(--text-muted);
  margin: -4px 0 16px;
  line-height: 1.55;
}}
.blocks {{ display: flex; flex-direction: column; gap: 16px; }}
.block {{
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px;
}}
.block-head {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}}
.block-title {{
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
}}
.block-hint {{
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}}
.section-num {{
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 999px;
  min-width: 30px;
  text-align: center;
}}
.locked-tag {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-soft);
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 999px;
  margin-left: auto;
}}
.block-note {{
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 6px 0 0;
}}
.block textarea,
.block input[type=text] {{
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  line-height: 1.4;
}}
.block textarea:focus,
.block input[type=text]:focus {{
  outline: 0;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}}
.block textarea {{ resize: vertical; }}
.block textarea.mono {{
  font-family: var(--mono);
  font-size: 13px;
  white-space: pre;
  overflow-wrap: normal;
  overflow-x: auto;
}}

/* HowTo */
.howto-row {{
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}}
.howto-meta {{
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  color: var(--text);
}}
.howto-meta .howto-key {{
  font-family: var(--mono);
  font-size: 11px;
  color: var(--primary);
}}
.howto-meta .howto-hint {{
  font-size: 11px;
  color: var(--text-muted);
}}

/* FAQ */
.faq-row {{
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  padding: 12px;
  margin-bottom: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}}
.faq-row textarea {{ background: var(--surface-2); }}

/* Table */
.table-grid {{
  display: grid;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
}}
.table-grid input[type=text] {{ background: var(--surface-2); }}
.table-grid input[type=text].th {{
  font-weight: 600;
  color: var(--text);
  background: var(--surface);
  border-color: var(--border-strong);
}}
.tbl-wrap {{
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 10px;
  border-radius: 8px;
}}
.tbl-scroll {{ overflow-x: auto; }}
table.tbl-edit {{ border-collapse: separate; border-spacing: 8px; width: 100%; }}
table.tbl-edit th, table.tbl-edit td {{ padding: 0; }}
table.tbl-edit input[type=text] {{
  width: 100%;
  min-width: 120px;
  box-sizing: border-box;
  background: var(--surface-2);
}}
table.tbl-edit input[type=text].th {{
  font-weight: 600;
  color: var(--text);
  background: var(--surface);
  border-color: var(--border-strong);
}}
.tbl-tools {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}}
.tbl-tools-sep {{
  width: 1px;
  align-self: stretch;
  min-height: 20px;
  background: var(--border-strong);
  margin: 0 2px;
}}

/* Cards preview */
.cards-preview {{
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
}}
.cards-preview li {{ margin-bottom: 4px; }}
.cards-preview .cards-desc {{ color: var(--text-muted); }}
.cards-preview .path {{ font-size: 11.5px; }}

.block--locked {{ background: var(--surface); }}
.block--locked textarea, .block--locked input[type=text] {{ display: none; }}

@media (max-width: 720px) {{
  .howto-row {{ grid-template-columns: 1fr; }}
}}

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
{ALT_VIEW_CSS}
</style>{ALT_VIEW_HEAD}</head><body>
<header class="topbar">
  <span class="brand">SEO админка<span class="brand-sub">· Надежда VPN</span></span>
  <nav>
    <a href="{url_for('index')}">Страницы</a>
    <a href="https://nadezhda.info/" target="_blank" rel="noopener">Открыть сайт ↗</a>
    <button type="button" class="view-toggle" onclick="toggleAltView()">Альтернативный вид</button>
  </nav>
</header>
<main class="container">
<div class="admin-critical-banner" role="note">
  <strong>Данные только на этом сервере.</strong>
  «Сохранить и опубликовать» пишет в <code>content_overrides.json</code>.
  Деплой кода — <code>scripts/safe_git_update.sh</code>; голый <code>git reset --hard</code> без бэкапа overrides удалит тексты.
</div>
{flash_html}
{body}
</main>
</body></html>"""


def render_index(saved: str | None = None, reset: str | None = None) -> str:
    overrides = load_overrides()
    pages = build_pages_list()
    rows = [index_row_from_page(page, overrides) for page in pages]
    home, silos = build_index_tree(rows)

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
        f'<p class="page-meta page-meta-default">Всего страниц: <b>{total}</b> · '
        f'с переопределённым SEO: <b>{overridden_n}</b></p>'
        f'<p class="page-meta page-meta-alt">Альтернативный вид: разделы и плитки · '
        f'всего <b>{total}</b> · с правками <b>{overridden_n}</b></p>'
        f'<div class="index-view-default">'
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
        f'</div>'
        f'<div class="index-view-alt">'
        f'<div class="index-toolbar">'
        f'<input type="search" id="idx-search" class="idx-search" '
        f'placeholder="Найти страницу: название, URL…" autocomplete="off">'
        f'<button type="button" class="btn btn-ghost btn-sm" onclick="altExpandSections()">'
        f"Развернуть разделы</button>"
        f'<button type="button" class="btn btn-ghost btn-sm" onclick="altCollapseSections()">'
        f"Свернуть разделы</button>"
        f'<span class="index-toolbar__hint">Разделы свёрнуты · клик по заголовку или плитке</span>'
        f'</div>'
        f"{render_index_alt_html(home, silos)}"
        f"{INDEX_LIST_JS}"
        f"</div>"
    )
    return layout("SEO-страницы", body, flash)


EDIT_JS = r"""
<script>
(function () {
  var form = document.querySelector('form.editor');
  if (!form) return;
  var blocks = form.querySelector('.blocks');
  var countEl = form.querySelector('input[name=sections_count]');
  if (!blocks || !countEl) return;

  function renumber() {
    var list = blocks.querySelectorAll(':scope > .block');
    list.forEach(function (b, k) {
      b.querySelectorAll('[name]').forEach(function (el) {
        el.name = el.name.replace(/^s_\d+_/, 's_' + k + '_');
      });
      var num = b.querySelector('.section-num');
      if (num) num.textContent = '#' + (k + 1);
    });
    countEl.value = list.length;
  }

  function addControls(b) {
    if (b.querySelector('.block-ctrls')) return;
    var head = b.querySelector('.block-head');
    if (!head) return;
    var box = document.createElement('span');
    box.className = 'block-ctrls';
    box.innerHTML =
      '<button type="button" class="bc" data-act="up" title="Поднять выше">&#8593;</button>' +
      '<button type="button" class="bc" data-act="down" title="Опустить ниже">&#8595;</button>' +
      '<button type="button" class="bc bc-del" data-act="del" title="Удалить блок">&#10005;</button>';
    head.appendChild(box);
  }

  blocks.querySelectorAll(':scope > .block').forEach(addControls);

  function tablePrefix(wrap) {
    var colsEl = wrap.querySelector('input[name$="_cols"]');
    return colsEl ? colsEl.name.replace(/cols$/, '') : 's_0_';
  }

  function updateTableSize(wrap) {
    var cols = parseInt(wrap.querySelector('input[name$="_cols"]').value, 10) || 0;
    var rows = parseInt(wrap.querySelector('input[name$="_rows"]').value, 10) || 0;
    var label = wrap.closest('.block').querySelector('.tbl-size');
    if (label) label.textContent = rows + ' × ' + cols;
  }

  function handleTable(btn) {
    var wrap = btn.closest('.tbl-wrap');
    if (!wrap) return;
    var table = wrap.querySelector('table.tbl-edit');
    var thead = table.tHead.rows[0];
    var tbody = table.tBodies[0];
    var colsEl = wrap.querySelector('input[name$="_cols"]');
    var rowsEl = wrap.querySelector('input[name$="_rows"]');
    var cols = parseInt(colsEl.value, 10) || 0;
    var rows = parseInt(rowsEl.value, 10) || 0;
    var pfx = tablePrefix(wrap);
    var act = btn.getAttribute('data-tbl');

    if (act === 'add-row') {
      var tr = document.createElement('tr');
      var html = '';
      for (var c = 0; c < cols; c++) {
        html += '<td><input type="text" name="' + pfx + 'cell_' + rows + '_' + c + '"></td>';
      }
      tr.innerHTML = html;
      tbody.appendChild(tr);
      rowsEl.value = rows + 1;
    } else if (act === 'del-row') {
      if (rows <= 1) return;
      if (tbody.rows.length) tbody.deleteRow(-1);
      rowsEl.value = rows - 1;
    } else if (act === 'add-col') {
      var th = document.createElement('th');
      th.innerHTML = '<input type="text" class="th" name="' + pfx + 'h_' + cols +
        '" placeholder="Заголовок ' + (cols + 1) + '">';
      thead.appendChild(th);
      Array.prototype.forEach.call(tbody.rows, function (row, r) {
        var td = document.createElement('td');
        td.innerHTML = '<input type="text" name="' + pfx + 'cell_' + r + '_' + cols + '">';
        row.appendChild(td);
      });
      colsEl.value = cols + 1;
    } else if (act === 'del-col') {
      if (cols <= 1) return;
      thead.deleteCell(-1);
      Array.prototype.forEach.call(tbody.rows, function (row) {
        if (row.cells.length) row.deleteCell(-1);
      });
      colsEl.value = cols - 1;
    }
    updateTableSize(wrap);
  }

  blocks.addEventListener('click', function (e) {
    var tbl = e.target.closest('.tbl-tools button');
    if (tbl) { handleTable(tbl); return; }
    var btn = e.target.closest('.bc');
    if (!btn) return;
    var b = btn.closest('.block');
    var act = btn.getAttribute('data-act');
    if (act === 'up' && b.previousElementSibling) {
      blocks.insertBefore(b, b.previousElementSibling);
    } else if (act === 'down' && b.nextElementSibling) {
      blocks.insertBefore(b.nextElementSibling, b);
    } else if (act === 'del') {
      if (confirm('Удалить этот блок со страницы?')) b.remove();
    }
    renumber();
  });

  document.querySelectorAll('.add-block').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var t = btn.getAttribute('data-type');
      var tpl = document.querySelector('template.block-tpl[data-type="' + t + '"]');
      if (!tpl) return;
      var node = tpl.content.firstElementChild.cloneNode(true);
      blocks.appendChild(node);
      addControls(node);
      renumber();
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });

  form.addEventListener('submit', renumber);
  renumber();
})();
</script>
"""


def render_edit(page: dict, seo: dict, ov: dict, error: str = "") -> str:
    path = page["path"]
    ov_title = ov.get("title") or ""
    ov_desc = ov.get("description") or ""
    ov_h1 = ov.get("h1") or ""
    seo_overridden = any((v or "").strip() for v in (ov_title, ov_desc, ov_h1))
    sec_overridden = isinstance(ov.get("sections"), list) and bool(ov.get("sections"))
    is_overridden = seo_overridden or sec_overridden

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

    # Контент-блоки
    secs = editor_sections(page)
    widgets = "".join(render_section_widget(i, s) for i, s in enumerate(secs))

    addbar = (
        '<div class="add-bar">'
        '<span class="add-bar__label">Добавить блок:</span>'
        + "".join(
            f'<button type="button" class="btn btn-ghost btn-sm add-block" '
            f'data-type="{esc(t)}">+ {esc(ADD_BLOCK_LABELS[t])}</button>'
            for t in ADDABLE_BLOCKS
        )
        + "</div>"
    )

    templates_html = "".join(
        f'<template class="block-tpl" data-type="{esc(t)}">'
        f"{render_section_widget(0, empty_block(t))}</template>"
        for t in ADDABLE_BLOCKS
    )

    body = f"""
<h1>Редактирование страницы</h1>
<div class="subtitle">
  <span class="path">{esc(path)}</span>
  <span class="badge {esc(page['kind'])}">{esc(page_kind_label(page['kind']))}</span>
</div>
{error_html}
<form method="post" action="{url_for('save')}" class="editor">
  <input type="hidden" name="path" value="{esc(path)}">
  <input type="hidden" name="sections_count" value="{len(secs)}">

  <h2 class="section-h">SEO</h2>

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

  <h2 class="section-h">Контент страницы</h2>
  <p class="section-note">Блоки идут сверху вниз в том же порядке, что и на сайте. Кнопками справа от заголовка блока можно поднять/опустить/удалить блок, а панелью «Добавить блок» — добавить новый. Карточки навигации формируются автоматически. «Сбросить к дефолту» вернёт страницу к стартовому шаблону уровня.</p>
  {addbar}
  <div class="blocks">
    {widgets}
  </div>

  <div class="actions">
    <button type="submit" class="btn btn-primary">Сохранить и опубликовать</button>
    <a class="btn btn-ghost" href="{url_for('index')}">Отмена</a>
    <span class="spacer"></span>
    {reset_form}
  </div>
</form>
{templates_html}
{EDIT_JS}
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

    parsed_sections = parse_sections_from_form(request.form)
    cleaned_sections = sections_normalized(parsed_sections)

    with _write_lock:
        overrides = load_overrides()
        page_ov: dict = {}
        if title:
            page_ov["title"] = title
        if description:
            page_ov["description"] = description
        if h1:
            page_ov["h1"] = h1

        # Контент сохраняем, только если он отличается от дефолта из site_data.py.
        default_secs_norm = sections_normalized(default_sections_for_editing(page))
        if cleaned_sections and cleaned_sections != default_secs_norm:
            page_ov["sections"] = cleaned_sections

        if page_ov:
            overrides[path] = page_ov
        elif path in overrides:
            del overrides[path]

        save_overrides(overrides)
        ok, msg = trigger_build()

    if not ok:
        seo = default_seo(page)
        # Сохраняем введённое, чтобы юзер не потерял редактируемые поля.
        retry_ov = {
            "title": title,
            "description": description,
            "h1": h1,
            "sections": cleaned_sections or default_sections_for_editing(page),
        }
        return render_edit(page, seo, retry_ov, error=msg), 500

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


# ---------- Публичная ссылка для скачивания content_overrides.json ----------
#
# Бэкап-страховка: сервер с SEO уже один раз был «обнулён» при переустановке и
# content_overrides.json (вся работа SEO-специалиста) был утрачен. Эта ручка
# позволяет в любой момент скачать актуальный файл по секретному 8-символьному
# токену (без HTTP Basic Auth), сохранив его локально. При неверном или
# отсутствующем токене отдаём 404, не подтверждая что URL вообще существует.
#
# Подключается на верхнем уровне nginx (location ~ ^/dl/[A-Za-z0-9]+$ → 5050),
# поэтому ссылка вида https://nadezhda.info/dl/<8 символов>.
@app.route("/dl/<token>")
def download_overrides(token: str):
    if not DOWNLOAD_TOKEN or token != DOWNLOAD_TOKEN:
        abort(404)
    if not OVERRIDES_PATH.exists():
        abort(404)
    return send_file(
        str(OVERRIDES_PATH),
        as_attachment=True,
        download_name="content_overrides.json",
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host=ADMIN_BIND, port=ADMIN_PORT, debug=False)
