# -*- coding: utf-8 -*-
"""Сборка статического SEO-лендинга в seo-landing/public/.

Запуск:  python scripts/build_pages.py
Без npm/vite. Контент каждой страницы — content/<путь>/page.json, дерево URL — scripts/site_data.py.
Каталог сборки можно задать через SEO_PUBLIC_DIR (автосборка на сервере собирает в новую папку).

Реализует ТЗ:
- §1 silo URL
- §2 SSR (статика HTML), breadcrumbs Schema.org, без тяжёлых JS
- §3 три шаблона: silo, hub, leaf + sub-leaf
- §4 JSON-LD: BreadcrumbList, Organization, SoftwareApplication, HowTo, FAQPage
- §5 UTM + data-page на CTA регистрации
"""
from __future__ import annotations

import html
import json
import os
import re
import datetime
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from site_data import (  # noqa: E402
    HUBS,
    LABELS,
    LEAF_DESC,
    LEAVES,
    SILO_META,
    SUBLEAVES,
    build_pages_list,
)

CFG_PATH = ROOT / "site_config.json"
CONTENT_DIR = ROOT / "content"
ASSETS_SRC = ROOT / "assets" / "css"
ASSETS_ROOT = ROOT / "assets"
PUBLIC = Path(os.environ.get("SEO_PUBLIC_DIR") or ROOT / "public")
PUBLIC_ASSETS = PUBLIC / "assets" / "css"

FAVICON_FILES = ["favicon.ico", "gemini-svg.svg"]

CSS_FILES = [
    "tokens.css",
    "lp-f1.css",
    "lp-header-views2.css",
    "lp-views2-responsive.css",
    "nice.css",
    "seo-components.css",
]

NAV = [
    ("Устройства", "/devices/"),
    ("Сервисы", "/services/"),
    ("База знаний", "/kb/"),
    ("Технологии", "/tech/"),
    ("Рейтинги", "/reviews/"),
    ("Блог", "/blog/"),
]

# Служебные метки вида P0 из ТЗ не выводим на карточках.
_CARD_TAG_INTERNAL = re.compile(r"^P\d+$", re.IGNORECASE)


# ---------- Утилиты ----------


def load_config() -> dict:
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


class ContentError(Exception):
    """Ошибка в файле контента: сборка останавливается, живой сайт не меняется."""


def content_path(path: str) -> Path:
    return CONTENT_DIR / path.strip("/") / "page.json" if path != "/" else CONTENT_DIR / "page.json"


def load_page(path: str) -> dict:
    """Читает и проверяет content/<путь>/page.json."""
    file = content_path(path)
    rel = file.relative_to(ROOT).as_posix()
    if not file.exists():
        raise ContentError(f"{path}: нет файла {rel}")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContentError(f"{rel}: битый JSON, строка {e.lineno}: {e.msg}") from e
    for key in ("title", "description", "h1"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ContentError(f"{rel}: пустое поле {key}")
    if not isinstance(data.get("sections"), list):
        raise ContentError(f"{rel}: нет списка sections")
    return data


def check_no_orphans(pages: list[dict]) -> None:
    """Файл контента без страницы в дереве не попадёт на сайт — лучше сразу остановиться."""
    known = {content_path(p["path"]).resolve() for p in pages}
    for file in sorted(CONTENT_DIR.rglob("page.json")):
        if file.resolve() not in known:
            rel = file.relative_to(ROOT).as_posix()
            raise ContentError(f"{rel}: страницы нет в дереве URL, добавьте её в scripts/site_data.py")


# ---------- Секции страницы: JSON → кортежи для render_sections ----------

def _coerce(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _normalize_section_dict(item) -> tuple | None:
    """Конвертирует секцию из page.json в кортеж, который понимает render_sections."""
    if not isinstance(item, dict):
        return None
    t = _coerce(item.get("type")).lower()
    if t == "snippet":
        text = _coerce(item.get("text"))
        return ("snippet", text) if text else None
    if t == "prose":
        h = (item.get("html") or "").strip() if isinstance(item.get("html"), str) else ""
        return ("prose", h) if h else None
    if t == "howto":
        items = []
        for it in item.get("items") or []:
            if not isinstance(it, dict):
                continue
            key = _coerce(it.get("key"))
            label = _coerce(it.get("label"))
            if key:
                items.append((key, label))
        return ("howto", items) if items else None
    if t == "trial":
        return ("trial", _coerce(item.get("variant")))
    if t == "faq":
        pairs = []
        for it in item.get("items") or []:
            if not isinstance(it, dict):
                continue
            q = _coerce(it.get("q"))
            a = _coerce(it.get("a"))
            if q and a:
                pairs.append((q, a))
        return ("faq", pairs) if pairs else None
    if t == "table":
        headers = [_coerce(h) for h in (item.get("headers") or [])]
        rows: list[list[str]] = []
        for r in item.get("rows") or []:
            if not isinstance(r, list):
                continue
            row = [_coerce(c) for c in r]
            if any(row):
                rows.append(row)
        if not headers or not rows:
            return None
        return ("table", headers, rows)
    if t == "cards":
        cards = []
        for c in item.get("items") or []:
            if not isinstance(c, dict):
                continue
            title = _coerce(c.get("title"))
            desc = _coerce(c.get("desc"))
            href = _coerce(c.get("href"))
            tag = _coerce(c.get("tag"))
            if title and href:
                cards.append((title, desc, href, tag))
        modifier = "lp-card-grid--3" if item.get("columns") == 3 else ""
        return ("cards", cards, modifier) if cards else None
    if t == "child_cards":
        return ("child_cards",)
    if t == "related":
        title = _coerce(item.get("title"))
        items = []
        for it in item.get("items") or []:
            if not isinstance(it, dict):
                continue
            label = _coerce(it.get("label"))
            href = _coerce(it.get("href"))
            if label and href:
                items.append((label, href))
        if not title or not items:
            return None
        return ("related", title, items)
    raise ContentError(f"неизвестный тип секции: {t or item}")


def page_sections(path: str, data: dict) -> list:
    out: list = []
    for raw_section in data["sections"]:
        try:
            tup = _normalize_section_dict(raw_section)
        except ContentError as e:
            raise ContentError(f"{path}: {e}") from e
        if tup:
            out.append(tup)
    return out


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def register_url(cfg: dict, slug: str) -> str:
    q = {
        "utm_source": cfg["utm_source"],
        "utm_medium": cfg["utm_medium"],
        "utm_campaign": slug,
    }
    return cfg["base_url"].rstrip("/") + cfg["register_path"] + "?" + urlencode(q)


def external_url(cfg: dict, path_key: str) -> str:
    return cfg["base_url"].rstrip("/") + cfg.get(path_key, "/")


def public_site_url(cfg: dict) -> str:
    return cfg.get("site_url", "https://nadezhda.info").rstrip("/")


def rel_prefix(depth: int) -> str:
    return "../" * depth if depth else ""


def asset_href(depth: int, name: str) -> str:
    return rel_prefix(depth) + "assets/css/" + name


def root_asset_href(depth: int, name: str) -> str:
    return rel_prefix(depth) + name


def favicon_links_html(depth: int) -> str:
    # Абсолютные пути от корня домена: одинаковы на всех страницах независимо
    # от глубины и 301-редиректа на trailing slash (относительные ../../ хрупкие).
    ico = "/favicon.ico"
    svg = "/gemini-svg.svg"
    return (
        f'<link rel="icon" href="{attr(ico)}" sizes="32x32" type="image/x-icon">\n'
        f'<link rel="shortcut icon" href="{attr(ico)}" type="image/x-icon">\n'
        f'<link rel="icon" href="{attr(svg)}" type="image/svg+xml" sizes="any">\n'
    )


def site_path_href(depth: int, path: str) -> str:
    """Путь вида /a/b/ → URL без index.html (nginx отдаёт индекс по каталогу)."""
    if not path.startswith("/"):
        path = "/" + path
    if path == "/":
        return "/" if depth == 0 else rel_prefix(depth)
    if path.endswith(".html"):
        clean = path.lstrip("/")
        return ("/" + clean) if depth == 0 else rel_prefix(depth) + clean
    norm = path if path.endswith("/") else path + "/"
    clean = norm.lstrip("/")
    return ("/" + clean) if depth == 0 else rel_prefix(depth) + clean


def depth_for(path: str) -> int:
    return 0 if path == "/" else len([p for p in path.strip("/").split("/") if p])


def json_ld(obj: dict) -> str:
    return '<script type="application/ld+json">\n' + json.dumps(obj, ensure_ascii=False, indent=2) + "\n</script>"


# ---------- Breadcrumbs ----------


def breadcrumbs_for(page: dict) -> list[tuple[str, str | None]]:
    path = page["path"]
    if path == "/":
        return [("Главная", None)]
    crumbs: list[tuple[str, str | None]] = [("Главная", "/")]
    parts = path.strip("/").split("/")
    for i, part in enumerate(parts):
        acc = "/" + "/".join(parts[: i + 1]) + "/"
        label = LABELS.get(part, part.replace("-", " ").title())
        href = acc if i < len(parts) - 1 else None
        crumbs.append((label, href))
    return crumbs


def breadcrumbs_html_block(crumbs: list[tuple[str, str | None]], depth: int) -> str:
    items = []
    for name, href in crumbs:
        if href:
            items.append(f'<li><a href="{attr(site_path_href(depth, href))}">{attr(name)}</a></li>')
        else:
            items.append(f'<li><span aria-current="page">{attr(name)}</span></li>')
    return (
        '<nav aria-label="Хлебные крошки">'
        '<ol class="lp-breadcrumbs">' + "".join(items) + "</ol></nav>"
    )


def breadcrumbs_ld(cfg: dict, crumbs: list[tuple[str, str]]) -> str:
    items = [
        {
            "@type": "ListItem",
            "position": i + 1,
            "name": n,
            "item": public_site_url(cfg) + p,
        }
        for i, (n, p) in enumerate(crumbs)
    ]
    return json_ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})


# ---------- Header / Footer ----------


def header_html(cfg: dict, depth: int, active_silo: str | None) -> str:
    links = []
    for label, path in NAV:
        is_active = active_silo and path.rstrip("/") == active_silo.rstrip("/")
        cls = ' class="is-active"' if is_active else ""
        links.append(f'<a href="{attr(site_path_href(depth, path))}"{cls}>{attr(label)}</a>')
    reg = register_url(cfg, "header")
    login = external_url(cfg, "login_path")
    brand = attr(cfg["brand"].upper())
    return (
        '<header class="lp-header lp-header-v2 lp-header--drawer">'
        '<div class="lp-header__bar">'
        f'<a href="{attr(site_path_href(depth, "/"))}" class="lp-brand-line" style="text-decoration:none">'
        f'<span class="lp-logo-heavy">{brand}</span>'
        f'<span class="lp-logo-vpn">{attr(cfg["brand_vpn"])}</span>'
        "</a>"
        '<button type="button" class="lp-nav-toggle" aria-label="Меню" '
        'aria-controls="lp-primary-nav" aria-expanded="false">'
        '<span class="lp-nav-toggle__bars" aria-hidden="true"></span>'
        "</button>"
        '<nav class="lp-header__nav" id="lp-primary-nav" aria-label="Основная навигация">'
        + "".join(links)
        + "</nav>"
        f'<a href="{attr(login)}" class="lp-login-btn">Войти</a>'
        f'<a href="{attr(reg)}" class="lp-header-cta" data-page="header">Регистрация</a>'
        "</div></header>"
    )


NAV_TOGGLE_JS = (
    "<script>(function(){"
    "var t=document.querySelector('.lp-nav-toggle');"
    "var n=document.getElementById('lp-primary-nav');"
    "if(!t||!n){return;}"
    "t.addEventListener('click',function(){"
    "var open=n.classList.toggle('lp-header__nav--open');"
    "t.setAttribute('aria-expanded',open?'true':'false');"
    "});"
    "n.addEventListener('click',function(e){"
    "if(e.target.closest('a')){"
    "n.classList.remove('lp-header__nav--open');"
    "t.setAttribute('aria-expanded','false');"
    "}});"
    "})();</script>"
)


def footer_html(cfg: dict, depth: int, slug: str) -> str:
    reg_footer = register_url(cfg, slug + "-footer-strip")
    reg_col = register_url(cfg, slug + "-footer-col")
    cabinet = external_url(cfg, "cabinet_path")

    def li(label: str, href: str, external: bool = False) -> str:
        if external:
            return f'<li><a href="{attr(href)}" rel="noopener" target="_blank">{attr(label)}</a></li>'
        return f'<li><a href="{attr(href)}">{attr(label)}</a></li>'

    sections_li = "".join(li(name, site_path_href(depth, path)) for name, path in NAV)
    devices_li = "".join(
        li(LABELS.get(slug2, title), site_path_href(depth, f"/devices/{slug2}/"))
        for slug2, title, _ in HUBS["devices"]
    )
    services_li = "".join(
        li(LABELS.get(slug2, title), site_path_href(depth, f"/services/{slug2}/"))
        for slug2, title, _ in HUBS["services"]
    )
    cabinet_li = li("Регистрация", reg_col) + li("Личный Кабинет", cabinet)

    return (
        '<div class="lp-trial-strip">'
        f'Бесплатный тест 8 часов — <a href="{attr(reg_footer)}" data-page="{attr(slug)}-trial-strip">зарегистрироваться</a>'
        "</div>"
        '<footer class="lp-seo-footer">'
        '<div class="lp-seo-footer__grid">'
        f'<div class="lp-seo-footer__col"><h3 class="lp-seo-footer__col-title">Разделы</h3><ul>{sections_li}</ul></div>'
        f'<div class="lp-seo-footer__col"><h3 class="lp-seo-footer__col-title">Устройства</h3><ul>{devices_li}</ul></div>'
        f'<div class="lp-seo-footer__col"><h3 class="lp-seo-footer__col-title">Сервисы</h3><ul>{services_li}</ul></div>'
        f'<div class="lp-seo-footer__col"><h3 class="lp-seo-footer__col-title">Личный кабинет</h3><ul>{cabinet_li}</ul></div>'
        "</div>"
        '<div class="lp-seo-footer__bottom">'
        f"<span>© {attr(cfg['brand'])} {attr(cfg['brand_vpn'])} — стабильный доступ в России 2026.</span>"
        "</div>"
        "</footer>"
    )


# ---------- Рендер секций ----------


def render_card_grid(cards: list[tuple[str, str, str, str]], depth: int, modifier: str = "") -> str:
    items = []
    for title, desc, href, tag in cards:
        show_tag = bool(tag and tag.strip()) and not _CARD_TAG_INTERNAL.match(tag.strip())
        tag_html = f'<span class="lp-hub-card__tag">{attr(tag)}</span>' if show_tag else ""
        items.append(
            f'<a class="lp-hub-card" href="{attr(site_path_href(depth, href))}">'
            f'<h3 class="lp-hub-card__title">{attr(title)}</h3>'
            f'<p class="lp-hub-card__desc">{attr(desc)}</p>'
            f"{tag_html}</a>"
        )
    cls = "lp-card-grid" + (f" {modifier}" if modifier else "")
    return f'<div class="{cls}">' + "".join(items) + "</div>"


def wrap_bare_tables(html: str) -> str:
    """Оборачивает <table> из prose в lp-table-wrap (если админ вставил таблицу в HTML)."""
    if "<table" not in html.lower() or "lp-table-wrap" in html:
        return html
    return re.sub(
        r"(<table\b[\s\S]*?</table>)",
        r'<div class="lp-table-wrap">\1</div>',
        html,
        flags=re.IGNORECASE,
    )


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    thead = "".join(f"<th>{attr(h)}</th>" for h in headers)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{attr(c)}</td>" for c in row) + "</tr>" for row in rows
    )
    return (
        '<div class="lp-table-wrap"><table>'
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table></div>"
    )


def render_howto(cfg: dict, slug: str, items: list[tuple[str, str]]) -> tuple[str, dict]:
    """items = [(step_key, label), ...]. Подставляет реальные ссылки и собирает JSON-LD."""
    reg = register_url(cfg, slug + "-howto")
    cabinet = external_url(cfg, "cabinet_path")
    apk = external_url(cfg, "happ_android_apk")

    rendered_li = []
    steps_ld = []
    for idx, (key, label) in enumerate(items, start=1):
        if key in ("registration", "register"):
            html_li = (
                f'<li>Зарегистрируйтесь в <a href="{attr(reg)}" data-page="{attr(slug)}-step{idx}">Личном Кабинете</a> '
                "и получите ссылку подписки."
            )
        elif key == "apk":
            html_li = (
                f'<li><a href="{attr(apk)}">Скачайте приложение Happ</a> — для Android используйте APK '
                "из Личного Кабинета."
            )
        elif key in ("import", "link"):
            html_li = (
                f'<li>Скопируйте ссылку из <a href="{attr(cabinet)}">Личного Кабинета</a> и вставьте её в Happ.'
            )
        else:
            html_li = f"<li>{attr(label)}"
        rendered_li.append(html_li + "</li>")
        steps_ld.append({"@type": "HowToStep", "position": idx, "name": label})

    block = (
        '<section class="lp-howto" aria-label="Настройка через Happ">'
        '<h2 class="lp-howto__title">Настройка через Happ за 3 шага</h2>'
        "<ol>" + "".join(rendered_li) + "</ol></section>"
    )
    ld = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": "Настройка VPN через Happ",
        "step": steps_ld,
    }
    return block, ld


def render_trial(cfg: dict, slug: str, variant: str = "") -> str:
    if variant == "noreg":
        q = urlencode({"utm_source": cfg["utm_source"], "utm_medium": cfg["utm_medium"], "utm_campaign": slug})
        buy = cfg["base_url"].rstrip("/") + cfg.get("buy_path", "/buy") + "?" + q
        bot = cfg.get("telegram_bot", "https://t.me/nadezhdavpn_bot")
        return (
            '<aside class="lp-trial-block">'
            "<h2>Проверьте решение прямо сейчас</h2>"
            "<p>8 часов полного доступа бесплатно: тест сразу выдаёт Telegram-бот, без почты и телефона. "
            "Купить подписку тоже можно без отдельной регистрации — в боте или на сайте в 3 клика.</p>"
            '<div class="lp-trial-block__actions">'
            f'<a class="lp-btn-primary" href="{attr(bot)}" data-page="{attr(slug)}-trial-bot">Тест в Telegram-боте</a>'
            f'<a class="lp-btn-primary" href="{attr(buy)}" data-page="{attr(slug)}-trial-buy">Купить в 3 клика</a>'
            "</div>"
            "</aside>"
        )
    reg = register_url(cfg, slug)
    return (
        '<aside class="lp-trial-block">'
        "<h2>Проверьте решение прямо сейчас</h2>"
        "<p>Мы даём 8 часов полного доступа бесплатно. Зарегистрируйтесь, получите ключ в Личном Кабинете и активируйте его в Happ.</p>"
        f'<a class="lp-btn-primary" href="{attr(reg)}" data-page="{attr(slug)}-trial">Зарегистрироваться</a>'
        "</aside>"
    )


def render_faq(items: list[tuple[str, str]]) -> tuple[str, dict]:
    details = []
    entities = []
    for q, a in items:
        details.append(
            f"<details><summary>{attr(q)}</summary>"
            f'<div class="lp-faq__a"><p>{attr(a)}</p></div></details>'
        )
        entities.append(
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        )
    block = '<section class="lp-faq"><h2 class="lp-faq__title">FAQ</h2>' + "".join(details) + "</section>"
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}
    return block, ld


def render_related(title: str, items: list[tuple[str, str]], depth: int) -> str:
    lis = "".join(
        f'<li><a href="{attr(site_path_href(depth, href))}">{attr(label)}</a></li>'
        for label, href in items
    )
    return f'<section class="lp-related"><h2>{attr(title)}</h2><ul>{lis}</ul></section>'


def standard_related_html(page: dict, depth: int) -> str:
    """Единый блок навигации для hub / leaf / sub."""
    kind = page.get("kind")
    silo = page.get("silo")
    hub = page.get("hub")
    if kind not in ("hub", "leaf", "sub") or not silo or not hub:
        return ""
    blocks: list[str] = []
    hubs_links = [
        (h_title, f"/{silo}/{h_slug}/")
        for h_slug, h_title, _ in HUBS.get(silo, [])
        if h_slug != hub
    ]
    if hubs_links:
        blocks.append(render_related("Ещё в этом разделе", hubs_links, depth))

    if kind == "leaf":
        leaf = page.get("leaf")
        if not leaf:
            return "".join(blocks)
        leaves_list = LEAVES.get((silo, hub), [])
        leaf_links = [(LABELS[l], f"/{silo}/{hub}/{l}/") for l in leaves_list if l != leaf]
        if leaf_links:
            blocks.append(render_related("Другие страницы в этом разделе", leaf_links, depth))
        subs = SUBLEAVES.get((silo, hub, leaf), [])
        if subs:
            sub_links = [(LABELS[s], f"/{silo}/{hub}/{leaf}/{s}/") for s in subs]
            blocks.append(render_related("Углубитесь в тему", sub_links, depth))

    elif kind == "sub":
        leaf = page.get("leaf")
        sub = page.get("sub")
        if not leaf or not sub:
            return "".join(blocks)
        subs = SUBLEAVES.get((silo, hub, leaf), [])
        sub_links = [(LABELS[s], f"/{silo}/{hub}/{leaf}/{s}/") for s in subs if s != sub]
        if sub_links:
            blocks.append(render_related("Другие материалы по этой теме", sub_links, depth))
        leaves_list = LEAVES.get((silo, hub), [])
        leaf_links = [(LABELS[l], f"/{silo}/{hub}/{l}/") for l in leaves_list if l != leaf]
        if leaf_links:
            blocks.append(render_related("Другие страницы в этом разделе", leaf_links, depth))

    return "".join(blocks)


def child_cards(page: dict) -> list[tuple[str, str, str, str]]:
    """Карточки дочерних страниц: строятся из дерева URL, новая страница появляется в них сама."""
    if page["kind"] == "silo":
        return [
            (hub_title, hub_desc, f"/{page['silo']}/{hub_slug}/", "")
            for hub_slug, hub_title, hub_desc in HUBS.get(page["silo"], [])
        ]
    if page["kind"] == "hub":
        return [
            (LABELS.get(leaf, leaf.replace("-", " ").title()), LEAF_DESC.get(leaf) or "Открыть страницу.", f"/{page['silo']}/{page['hub']}/{leaf}/", "")
            for leaf in LEAVES.get((page["silo"], page["hub"]), [])
        ]
    return []


def render_sections(
    sections: list[tuple],
    cfg: dict,
    depth: int,
    slug: str,
    page: dict,
) -> tuple[str, list[dict]]:
    out: list[str] = []
    extras: list[dict] = []
    for sec in sections:
        kind = sec[0]
        if kind == "prose":
            out.append(f'<div class="lp-prose">{wrap_bare_tables(sec[1])}</div>')
        elif kind == "snippet":
            out.append(f'<p class="lp-snippet-bait">{sec[1]}</p>')
        elif kind == "cards":
            out.append(render_card_grid(sec[1], depth, sec[2]))
        elif kind == "child_cards":
            cards = child_cards(page)
            if cards:
                out.append(render_card_grid(cards, depth, "lp-card-grid--3"))
        elif kind == "table":
            out.append(render_table(sec[1], sec[2]))
        elif kind == "howto":
            block, ld = render_howto(cfg, slug, sec[1])
            out.append(block)
            extras.append(ld)
        elif kind == "trial":
            out.append(render_trial(cfg, slug, sec[1] if len(sec) > 1 else ""))
        elif kind == "faq":
            block, ld = render_faq(sec[1])
            out.append(block)
            extras.append(ld)
        elif kind == "related":
            out.append(render_related(sec[1], sec[2], depth))
    return "".join(out), extras


# ---------- Метаданные шаблонов ----------


def schemas_for(content: dict, cfg: dict) -> list[dict]:
    out: list[dict] = []
    for key in content.get("schemas", []):
        if key == "organization":
            site = public_site_url(cfg) + "/"
            org_id = site + "#org"
            name = f"{cfg['brand']} {cfg['brand_vpn']}"
            out.append({
                "@context": "https://schema.org",
                "@graph": [
                    {
                        "@type": "Organization",
                        "@id": org_id,
                        "name": name,
                        "url": site,
                        "slogan": "Интернет, который просто работает",
                        "sameAs": ["https://t.me/nadezhdavpn_bot"],
                    },
                    {
                        "@type": "WebSite",
                        "@id": site + "#website",
                        "url": site,
                        "name": name,
                        "inLanguage": "ru",
                        "publisher": {"@id": org_id},
                    },
                ],
            })
        elif key == "software_app":
            out.append({
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "name": "Happ",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Android, iOS, Windows, macOS, Linux",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "RUB"},
            })
    return out


def render_main_block(page: dict, cfg: dict) -> tuple[str, str, str, list[dict]]:
    """Возвращает (title, description, main_html, extras_ld)."""
    path = page["path"]
    depth = depth_for(path)
    slug = path.strip("/").replace("/", "-") or "home"
    data = load_page(path)

    h1_html = data.get("h1_html")
    h1 = f'<h1 class="lp-seo-h1">{h1_html or attr(data["h1"])}</h1>'
    body, extras = render_sections(page_sections(path, data), cfg, depth, slug, page)
    body += standard_related_html(page, depth)

    return data["title"], data["description"], h1 + body, list(extras) + schemas_for(data, cfg)


# ---------- Page shell ----------


def yandex_verification_meta(cfg: dict) -> str:
    token = (cfg.get("yandex_verification") or "").strip()
    if not token:
        return ""
    return f'<meta name="yandex-verification" content="{attr(token)}">\n'


def yandex_metrika_snippet(cfg: dict) -> tuple[str, str]:
    """Возвращает (head_script, body_noscript) для Яндекс.Метрики."""
    counter_id = cfg.get("yandex_metrika_id")
    if not counter_id:
        return "", ""
    cid = str(counter_id)
    head = (
        "<!-- Yandex.Metrika counter -->\n"
        '<script type="text/javascript">\n'
        "   (function(m,e,t,r,i,k,a){\n"
        "       m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};\n"
        "       m[i].l=1*new Date();\n"
        "       for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}\n"
        "       k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)\n"
        "   })(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=" + cid + "', 'ym');\n"
        "\n"
        "   ym(" + cid + ", 'init', {ssr:true, webvisor:true, clickmap:true, ecommerce:\"dataLayer\", referrer: document.referrer, url: location.href, accurateTrackBounce:true, trackLinks:true});\n"
        "</script>\n"
        "<!-- /Yandex.Metrika counter -->\n"
    )
    noscript = (
        "<noscript><div><img src=\"https://mc.yandex.ru/watch/" + cid + "\" "
        "style=\"position:absolute; left:-9999px;\" alt=\"\" /></div></noscript>\n"
    )
    return head, noscript


def page_shell(
    cfg: dict,
    *,
    depth: int,
    title: str,
    description: str,
    canonical_path: str,
    active_silo: str | None,
    slug: str,
    crumbs: list[tuple[str, str | None]],
    main_html: str,
    extras_ld: list[dict],
) -> str:
    canon = public_site_url(cfg) + canonical_path
    css_links = "\n".join(f'  <link rel="stylesheet" href="{attr(asset_href(depth, f))}">' for f in CSS_FILES)
    crumbs_with_href = [(n, p) for n, p in crumbs if p]
    bc_ld = breadcrumbs_ld(cfg, crumbs_with_href) if crumbs_with_href else ""
    schemas_html = "\n".join(json_ld(s) for s in extras_ld)
    yv_meta = yandex_verification_meta(cfg)
    ym_head, ym_noscript = yandex_metrika_snippet(cfg)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{attr(title)}</title>\n"
        f'<meta name="description" content="{attr(description)}">\n'
        f'<link rel="canonical" href="{attr(canon)}">\n'
        '<meta name="robots" content="index,follow">\n'
        f"{yv_meta}"
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{attr(title)}">\n'
        f'<meta property="og:description" content="{attr(description)}">\n'
        f'<meta property="og:url" content="{attr(canon)}">\n'
        f'<meta property="og:site_name" content="{attr(cfg["brand"] + " " + cfg["brand_vpn"])}">\n'
        f"{favicon_links_html(depth)}"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&family=Space+Grotesk:wght@500;600;700&family=Syne:wght@400;500;600;700;800&display=swap" rel="stylesheet">\n'
        f"{css_links}\n"
        f"{bc_ld}\n"
        f"{schemas_html}\n"
        f"{ym_head}"
        "</head>\n<body>\n"
        + ym_noscript
        + '<div class="lp-f1 lp-f1-body"><div class="lp-container">'
        + header_html(cfg, depth, active_silo)
        + '<main class="lp-seo-main">'
        + breadcrumbs_html_block(crumbs, depth)
        + main_html
        + "</main>"
        + footer_html(cfg, depth, slug)
        + "</div></div>"
        + NAV_TOGGLE_JS
        + "</body></html>"
    )


# ---------- Главный билд ----------


def write_robots(cfg: dict) -> None:
    site = public_site_url(cfg)
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {site}/sitemap.xml\n",
        encoding="utf-8",
    )


def content_lastmod() -> dict[str, str]:
    """Дата последнего изменения каждого content/**/page.json: из git (один вызов), иначе — mtime файла."""
    dates: dict[str, str] = {}
    try:
        out = subprocess.run(
            ["git", "log", "--format=@%cs", "--name-only", "--", "content"],
            cwd=ROOT, capture_output=True, text=True, timeout=60, check=True,
        ).stdout
        cur = ""
        for line in out.splitlines():
            if line.startswith("@"):
                cur = line[1:]
            elif line.endswith("page.json") and line not in dates:
                dates[line] = cur
    except Exception:
        pass
    return dates


def write_sitemap(cfg: dict, pages: list[dict]) -> None:
    base = public_site_url(cfg)
    dates = content_lastmod()
    urls = []
    for page in pages:
        loc = base + page["path"]
        rel = "content/" + (page["path"].strip("/") + "/" if page["path"].strip("/") else "") + "page.json"
        mod = dates.get(rel)
        if not mod and (ROOT / rel).exists():
            mod = datetime.date.fromtimestamp((ROOT / rel).stat().st_mtime).isoformat()
        urls.append(f"  <url><loc>{loc}</loc>" + (f"<lastmod>{mod}</lastmod>" if mod else "") + "</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (PUBLIC / "sitemap.xml").write_text(xml, encoding="utf-8")


def reset_public_dir() -> None:
    """Очистить каталог сборки, не удаляя его самого."""
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for child in PUBLIC.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def main() -> None:
    cfg = load_config()
    pages = build_pages_list()
    check_no_orphans(pages)

    reset_public_dir()
    PUBLIC_ASSETS.mkdir(parents=True)
    for f in CSS_FILES:
        src = ASSETS_SRC / f
        if src.exists():
            shutil.copy2(src, PUBLIC_ASSETS / f)
    for f in FAVICON_FILES:
        src = ASSETS_ROOT / f
        if src.exists():
            shutil.copy2(src, PUBLIC / f)
    images = ASSETS_ROOT / "img"
    if images.exists():
        shutil.copytree(images, PUBLIC / "assets" / "img")

    write_robots(cfg)
    write_sitemap(cfg, pages)

    for page in pages:
        path = page["path"]
        depth = depth_for(path)
        slug = path.strip("/").replace("/", "-") or "home"
        title, desc, main_html, extras_ld = render_main_block(page, cfg)
        active_silo = f"/{page['silo']}/" if page.get("silo") else None
        crumbs = breadcrumbs_for(page)
        html_text = page_shell(
            cfg,
            depth=depth,
            title=title,
            description=desc,
            canonical_path=path if path.endswith("/") else path + "/",
            active_silo=active_silo,
            slug=slug,
            crumbs=crumbs,
            main_html=main_html,
            extras_ld=extras_ld,
        )
        out_dir = PUBLIC if path == "/" else PUBLIC / path.strip("/")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html_text, encoding="utf-8")

    print(f"Built {len(pages)} pages -> {PUBLIC}")


if __name__ == "__main__":
    try:
        main()
    except ContentError as e:
        print(f"ОШИБКА КОНТЕНТА: {e}", file=sys.stderr)
        sys.exit(1)
