# -*- coding: utf-8 -*-
"""Сборка статического SEO-лендинга в seo-landing/public/.

Запуск:  python scripts/build_pages.py
Без npm/vite. Все тексты — из site_data.py (перенесены из SEO-work дословно).

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
import shutil
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
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

CFG_PATH = ROOT / "site_config.json"
ASSETS_SRC = ROOT / "assets" / "css"
PUBLIC = ROOT / "public"
PUBLIC_ASSETS = PUBLIC / "assets" / "css"

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


# ---------- Утилиты ----------


def load_config() -> dict:
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


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


def rel_prefix(depth: int) -> str:
    return "../" * depth if depth else ""


def asset_href(depth: int, name: str) -> str:
    return rel_prefix(depth) + "assets/css/" + name


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
            "item": cfg["base_url"].rstrip("/") + p,
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
        '<nav class="lp-header__nav" aria-label="Основная навигация">'
        + "".join(links)
        + "</nav>"
        f'<a href="{attr(login)}" class="lp-login-btn">Войти</a>'
        f'<a href="{attr(reg)}" class="lp-header-cta" data-page="header">Регистрация</a>'
        "</div></header>"
    )


def footer_html(cfg: dict, depth: int, slug: str) -> str:
    reg_footer = register_url(cfg, slug + "-footer-strip")
    reg_col = register_url(cfg, slug + "-footer-col")
    cabinet = external_url(cfg, "cabinet_path")
    tg = cfg["telegram_support"]

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
    cabinet_li = (
        li("Регистрация", reg_col)
        + li("Личный Кабинет", cabinet)
        + li("Поддержка (Telegram)", tg, external=True)
    )

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
        tag_html = f'<span class="lp-hub-card__tag">{attr(tag)}</span>' if tag else ""
        items.append(
            f'<a class="lp-hub-card" href="{attr(site_path_href(depth, href))}">'
            f'<h3 class="lp-hub-card__title">{attr(title)}</h3>'
            f'<p class="lp-hub-card__desc">{attr(desc)}</p>'
            f"{tag_html}</a>"
        )
    cls = "lp-card-grid" + (f" {modifier}" if modifier else "")
    return f'<div class="{cls}">' + "".join(items) + "</div>"


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


def render_trial(cfg: dict, slug: str) -> str:
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


def render_sections(
    sections: list[tuple],
    cfg: dict,
    depth: int,
    slug: str,
    card_grid_modifier: str = "",
) -> tuple[str, list[dict]]:
    out: list[str] = []
    extras: list[dict] = []
    for sec in sections:
        kind = sec[0]
        if kind == "prose":
            out.append(f'<div class="lp-prose">{sec[1]}</div>')
        elif kind == "snippet":
            out.append(f'<p class="lp-snippet-bait">{sec[1]}</p>')
        elif kind == "cards":
            out.append(render_card_grid(sec[1], depth, card_grid_modifier))
        elif kind == "table":
            out.append(render_table(sec[1], sec[2]))
        elif kind == "howto":
            block, ld = render_howto(cfg, slug, sec[1])
            out.append(block)
            extras.append(ld)
        elif kind == "trial":
            out.append(render_trial(cfg, slug))
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
            out.append({
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": cfg["brand"],
                "url": cfg["base_url"],
                "sameAs": [cfg["telegram_support"]],
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


def render_main_block(page: dict, cfg: dict) -> tuple[str, str, str, list[dict], str | None]:
    """Возвращает (title, description, main_html, extras_ld, kicker_text)."""
    path = page["path"]
    depth = depth_for(path)
    slug = path.strip("/").replace("/", "-") or "home"

    if path == "/":
        content = HOME
        kicker = None
    elif path in CONTENT:
        content = CONTENT[path]
        # Без служебных меток вроде «Хаб», «Раздел» — только заголовок и контент
        kicker = None
    else:
        return render_stub(page, cfg, depth, slug)

    parts: list[str] = []
    if kicker:
        parts.append(f'<span class="lp-seo-kicker">{attr(kicker)}</span>')
    h1_html = content.get("h1_html")
    if h1_html:
        parts.append(f'<h1 class="lp-seo-h1">{h1_html}</h1>')
    else:
        parts.append(f'<h1 class="lp-seo-h1">{attr(content["h1"])}</h1>')

    card_modifier = "lp-card-grid--3" if page.get("kind") in ("home", "silo", "hub") else ""
    body, extras = render_sections(content["sections"], cfg, depth, slug, card_modifier)
    parts.append(body)

    extras_ld = list(extras) + schemas_for(content, cfg)
    return content["title"], content["description"], "".join(parts), extras_ld, kicker


def render_stub(
    page: dict, cfg: dict, depth: int, slug: str
) -> tuple[str, str, str, list[dict], str | None]:
    kind = page["kind"]
    if kind == "silo":
        title, desc = SILO_META[page["silo"]]
        kicker = None
        cards = [
            (hub_title, hub_desc, f"/{page['silo']}/{hub_slug}/", "")
            for hub_slug, hub_title, hub_desc in HUBS.get(page["silo"], [])
        ]
        body = render_card_grid(cards, depth, "lp-card-grid--3") if cards else ""
        main = (
            f'<h1 class="lp-seo-h1">{attr(title)}</h1>'
            f'<p class="lp-snippet-bait">{attr(desc)}</p>'
            + body
            + render_trial(cfg, slug)
        )
        return f"{title} — {cfg['brand']} {cfg['brand_vpn']}", desc, main, [], kicker
    if kind == "hub":
        title, desc = page["title"], page["description"]
        kicker = None
        cards = [
            (LABELS.get(leaf, leaf.replace("-", " ").title()), "Открыть страницу.", f"/{page['silo']}/{page['hub']}/{leaf}/", "")
            for leaf in LEAVES.get((page["silo"], page["hub"]), [])
        ]
        body = render_card_grid(cards, depth, "lp-card-grid--3") if cards else ""
        related_silo = [
            (h_title, f"/{page['silo']}/{h_slug}/")
            for h_slug, h_title, _ in HUBS.get(page["silo"], [])
            if h_slug != page["hub"]
        ]
        related_block = render_related("Ещё в этом разделе", related_silo, depth) if related_silo else ""
        main = (
            f'<h1 class="lp-seo-h1">{attr(title)}</h1>'
            f'<p class="lp-snippet-bait">{attr(desc)}</p>'
            + body
            + render_trial(cfg, slug)
            + related_block
        )
        return f"{title} — {cfg['brand']} {cfg['brand_vpn']}", desc, main, [], kicker

    # leaf / sub stubs
    leaf = page.get("sub") or page.get("leaf", "page")
    name = LABELS.get(leaf, leaf.replace("-", " ").title())
    kicker = None
    main = (
        f'<h1 class="lp-seo-h1">{attr("VPN: " + name)}</h1>'
        + render_trial(cfg, slug)
    )
    return (
        f"VPN {name} — {cfg['brand']} {cfg['brand_vpn']}",
        f"VPN-решение для запроса «{name}». 8 часов бесплатного теста в Личном Кабинете.",
        main,
        [],
        kicker,
    )


# ---------- Page shell ----------


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
    canon = cfg["base_url"].rstrip("/") + canonical_path
    css_links = "\n".join(f'  <link rel="stylesheet" href="{attr(asset_href(depth, f))}">' for f in CSS_FILES)
    crumbs_with_href = [(n, p) for n, p in crumbs if p]
    bc_ld = breadcrumbs_ld(cfg, crumbs_with_href) if crumbs_with_href else ""
    schemas_html = "\n".join(json_ld(s) for s in extras_ld)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{attr(title)}</title>\n"
        f'<meta name="description" content="{attr(description)}">\n'
        f'<link rel="canonical" href="{attr(canon)}">\n'
        '<meta name="robots" content="index,follow">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{attr(title)}">\n'
        f'<meta property="og:description" content="{attr(description)}">\n'
        f'<meta property="og:url" content="{attr(canon)}">\n'
        f'<meta property="og:site_name" content="{attr(cfg["brand"] + " " + cfg["brand_vpn"])}">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&family=Space+Grotesk:wght@500;600;700&family=Syne:wght@400;500;600;700;800&display=swap" rel="stylesheet">\n'
        f"{css_links}\n"
        f"{bc_ld}\n"
        f"{schemas_html}\n"
        "</head>\n<body>\n"
        '<div class="lp-f1 lp-f1-body"><div class="lp-container">'
        + header_html(cfg, depth, active_silo)
        + '<main class="lp-seo-main">'
        + breadcrumbs_html_block(crumbs, depth)
        + main_html
        + "</main>"
        + footer_html(cfg, depth, slug)
        + "</div></div></body></html>"
    )


# ---------- Главный билд ----------


def write_robots(cfg: dict) -> None:
    base = cfg["base_url"].rstrip("/")
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /dashboard/\n"
        "Disallow: /cabinet/\n"
        "Disallow: /nice\n"
        f"Sitemap: {base}/sitemap.xml\n",
        encoding="utf-8",
    )


def write_sitemap(cfg: dict, pages: list[dict]) -> None:
    base = cfg["base_url"].rstrip("/")
    urls = []
    for page in pages:
        loc = base + page["path"]
        urls.append(f"  <url><loc>{loc}</loc></url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (PUBLIC / "sitemap.xml").write_text(xml, encoding="utf-8")


def main() -> None:
    cfg = load_config()

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    PUBLIC_ASSETS.mkdir(parents=True)
    for f in CSS_FILES:
        src = ASSETS_SRC / f
        if src.exists():
            shutil.copy2(src, PUBLIC_ASSETS / f)

    pages = build_pages_list()
    write_robots(cfg)
    write_sitemap(cfg, pages)

    for page in pages:
        path = page["path"]
        depth = depth_for(path)
        slug = path.strip("/").replace("/", "-") or "home"
        title, desc, main_html, extras_ld, _ = render_main_block(page, cfg)
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
    main()
