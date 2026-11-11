# -*- coding: utf-8 -*-
"""Дерево URL SEO-лендинга. Контент страниц лежит в content/<путь>/page.json.

Новая страница: добавить slug сюда (LEAVES / SUBLEAVES и подпись в LABELS)
и создать для неё page.json. Подробно — CLAUDE.md.
"""

# ---------- Структура URL ----------

SILO_META = {
    "devices": ("VPN для всех устройств", "Решения для Windows, Android, iOS, Smart TV и роутеров."),
    "services": ("VPN для сервисов", "YouTube, Telegram, игры и социальные сети."),
    "kb": ("База знаний VPN", "Гайды, исправление ошибок, обучение."),
    "tech": ("Технологии VPN", "Протоколы VLESS, Reality, серверы."),
    "reviews": ("Рейтинги VPN", "Сравнения и обзоры 2026."),
    "blog": ("Блог", "Статьи о VPN и доступе."),
}

HUBS = {
    "devices": [
        ("desktop", "ПК и ноутбуки", "Windows, macOS, Linux."),
        ("mobile", "Мобильные устройства", "Android, iOS, Huawei."),
        ("browsers", "Браузеры", "Chrome, Яндекс, Opera."),
        ("tv", "Smart TV", "Android TV, Apple TV."),
        ("hardware", "Сетевое оборудование", "Роутеры Keenetic, ASUS."),
    ],
    "services": [
        ("social", "Социальные сети", "Instagram, TikTok."),
        ("video", "Видеостриминг", "YouTube, Netflix."),
        ("gaming", "VPN для игр", "Пинг, Roblox, Brawl Stars, Discord."),
        ("tools", "Коммуникации и сервисы", "Telegram, ChatGPT."),
    ],
    "kb": [
        ("fixes", "Не работает VPN", "Диагностика и решения."),
        ("guides", "Инструкции", "Настройка, Happ, белые списки, пробный период."),
        ("education", "Обучение", "Что такое VPN, законность, белые списки."),
    ],
    "tech": [
        ("protocols", "Протоколы", "VLESS, Reality, Shadowsocks."),
        ("servers", "Серверы", "Приватный IP, self-hosted."),
    ],
    "reviews": [
        ("lists", "Списки и сравнения", "Обзоры и тематические материалы."),
        ("apps", "Обзоры приложений", "Happ, Amnezia, Sota, ByeDPI, VPN-боты и другие."),
    ],
    "blog": [
        ("russian-vpn", "Русский VPN: что это значит и какой выбрать", "Российские ГОСТ-VPN, приложения на русском и что работает в России."),
        ("amnezia-setup", "Амнезия VPN: настройка с нуля", "Пошаговая настройка AmneziaVPN."),
        ("vpn-config", "Конфигурация VPN: что такое конфиг", "Что такое конфиг и как его использовать."),
        ("happ-udalen-iz-app-store", "Happ удалён из App Store: что делать", "Почему Happ пропал из App Store и как установить клиент на iPhone в 2026."),
    ],
}

LEAVES = {
    ("devices", "desktop"): [
        "windows",
        "macos",
        "linux",
        "gaming",
        "streaming",
        "alternatives",
        "download",
    ],
    ("devices", "mobile"): ["android", "ios", "huawei-honor", "samsung"],
    ("devices", "browsers"): ["general", "yandex", "chrome", "opera", "firefox"],
    ("devices", "tv"): ["smart-tv", "android-tv", "apple-tv"],
    ("devices", "hardware"): ["router", "keenetic", "asus-tp-link"],
    ("services", "social"): ["instagram", "tiktok", "linkedin", "other"],
    ("services", "video"): ["youtube", "netflix", "twitch", "spotify"],
    ("services", "gaming"): ["roblox", "discord", "online-games", "steam", "ps-xbox", "brawl-stars", "minecraft"],
    ("services", "tools"): ["telegram", "chatgpt-openai", "messengers", "video-calls"],
    ("kb", "fixes"): ["vpn-not-working", "slow-speed", "android", "iphone", "windows", "happ"],
    ("kb", "guides"): ["how-to-setup", "how-to-share", "vpn-keys", "install-happ", "enable-disable", "no-registration", "whitelist-bypass", "free-trial"],
    ("kb", "education"): ["what-is-vpn", "legality-russia", "how-bypass", "vpn-vs-proxy", "vpn-types", "whitelist"],
    ("tech", "protocols"): ["modern-protocols", "vless-reality", "wireguard-amnezia", "shadowsocks", "hysteria"],
    ("tech", "servers"): ["private-ip", "self-hosted-vpn", "security", "split-tunneling"],
    ("reviews", "lists"): [
        "best-vpn-2026",
        "best-vpn-russia",
        "free-vpn-risks",
        "paid-vs-free",
        "vpn-android",
    ],
    ("reviews", "apps"): [
        "happ-vpn",
        "jump-vpn",
        "adguard-vpn",
        "radmin-vpn",
        "amnezia-vpn",
        "telegram-vpn-bots",
        "planet-vpn",
        "proton-vpn",
        "outline-vpn",
        "v2raytun",
        "browsec",
        "sota-vpn",
        "byedpi",
        "super-vpn",
    ],
}

# Описания карточек дочерних страниц в хабах (child_cards). Нет описания — «Открыть страницу.».
# При добавлении или переименовании страницы — обновить и здесь (и в HUBS для блога/силосов).
LEAF_DESC = {
    "windows": "Скачать и настроить VPN на компьютер и ноутбук.",
    "macos": "VPN для Mac и MacBook: установка и настройка.",
    "streaming": "YouTube и видео на ПК без замедления.",
    "download": "Где скачать VPN бесплатно на ПК и телефон.",
    "android": "Скачать бесплатно, выбрать и настроить VPN на андроид.",
    "ios": "Какой VPN выбрать для айфона и как его настроить.",
    "samsung": "Установка и настройка VPN на Samsung Galaxy.",
    "instagram": "Какой VPN выбрать для Instagram и как настроить.",
    "tiktok": "Свежая лента TikTok в России: VPN, кэш и SIM-карта.",
    "youtube": "YouTube без замедления: какой VPN выбрать.",
    "roblox": "Нужен ли VPN для Роблокса сейчас и какой выбрать.",
    "online-games": "Пинг, игра с друзьями по сети и игровые бустеры.",
    "brawl-stars": "VPN для Brawl Stars: скачать и настроить.",
    "telegram": "VPN для Телеграма: какой выбрать и как настроить.",
    "how-to-setup": "Пошаговая установка VPN на любое устройство.",
    "vpn-keys": "Что такое ключ для VPN, где взять и как подключить.",
    "install-happ": "Подписка, второе устройство и настройки Happ.",
    "enable-disable": "Как включить и выключить VPN на любом устройстве.",
    "no-registration": "Бесплатный VPN без регистрации и на русском.",
    "whitelist-bypass": "Какой VPN работает при белых списках и как настроить.",
    "free-trial": "8 часов бесплатно и без карты: как попробовать.",
    "what-is-vpn": "VPN простыми словами: как работает и зачем нужен.",
    "legality-russia": "Можно ли пользоваться VPN и будет ли штраф.",
    "how-bypass": "DPI, ТСПУ и почему одни VPN работают, а другие нет.",
    "vpn-vs-proxy": "Чем VPN отличается от прокси и что выбрать.",
    "vpn-types": "Какие бывают VPN и чем они отличаются.",
    "whitelist": "Что такое белые списки и какие сайты в них входят.",
    "modern-protocols": "L2TP, IPSec, PPTP и IKEv2: что с ними сейчас.",
    "vless-reality": "Почему VLESS и Reality обходят блокировки.",
    "wireguard-amnezia": "WireGuard и AmneziaWG: работают ли в России.",
    "shadowsocks": "Shadowsocks: что это и работает ли в России.",
    "hysteria": "Hysteria: быстрый протокол для нестабильных сетей.",
    "best-vpn-2026": "Мировой топ VPN и как выбрать под свою задачу.",
    "best-vpn-russia": "Какие VPN реально работают в России в 2026 году.",
    "free-vpn-risks": "Бесплатные VPN: рейтинг, риски и как пользоваться.",
    "paid-vs-free": "Тарифы, цены и чем платный VPN лучше бесплатного.",
    "happ-vpn": "Где скачать Happ, что такое Happ Plus и где взять ключ.",
    "jump-vpn": "Обзор JumpJump VPN: как скачать и стоит ли.",
    "adguard-vpn": "Работает ли AdGuard VPN в России и как скачать.",
    "radmin-vpn": "Виртуальная сеть для игр по сети, не обход блокировок.",
    "amnezia-vpn": "AmneziaWG, self-hosted и работает ли в России.",
    "telegram-vpn-bots": "Дядя Ваня, Огонь, Incy, Дед и Батя: как не попасть на клона.",
    "planet-vpn": "Бесплатная версия Planet VPN и работает ли в России.",
    "proton-vpn": "Работает ли Proton VPN в России и как скачать.",
    "outline-vpn": "Ключи Outline и работает ли он в России.",
    "v2raytun": "v2RayTun: где взять ключ и как настроить.",
    "browsec": "Расширение Browsec: обзор и работа в России.",
    "sota-vpn": "Sota Connect: как скачать официально и где взять ключ.",
    "byedpi": "ByeDPI и GoodbyeDPI: обход DPI без VPN.",
    "super-vpn": "Несколько приложений под одним именем и утечка 2023 года.",
    "apk": "Безопасный APK для Android из официальных источников.",
    "gaming": "VPN для мобильных игр на Android.",
}

# (silo, hub, leaf) -> [sub-slug, ...]  — L4 страницы (ответ автора ТЗ)
SUBLEAVES = {
    ("devices", "mobile", "android"): ["apk", "gaming", "messengers", "streaming"],
}

LABELS = {
    "devices": "Устройства",
    "services": "Сервисы",
    "kb": "База знаний",
    "tech": "Технологии",
    "reviews": "Рейтинги",
    "blog": "Блог",
    "mobile": "Мобильные устройства",
    "desktop": "ПК и ноутбуки",
    "browsers": "Браузеры",
    "tv": "Smart TV",
    "hardware": "Сетевое оборудование",
    "social": "Социальные сети",
    "video": "Видеостриминг",
    "gaming": "VPN для игр",
    "tools": "Коммуникации и сервисы",
    "fixes": "Не работает VPN",
    "guides": "Инструкции",
    "education": "Обучение",
    "protocols": "Протоколы",
    "servers": "Серверы",
    "lists": "Списки и сравнения",
    "android": "Android",
    "ios": "iOS",
    "huawei-honor": "Huawei / Honor",
    "windows": "Windows",
    "macos": "macOS",
    "linux": "Linux",
    "smart-tv": "Smart TV",
    "android-tv": "Android TV",
    "apple-tv": "Apple TV",
    "router": "Роутеры",
    "keenetic": "Keenetic",
    "asus-tp-link": "ASUS / TP-Link",
    "yandex": "Яндекс Браузер",
    "chrome": "Google Chrome",
    "opera": "Opera",
    "firefox": "Firefox",
    "general": "Все браузеры",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
    "netflix": "Netflix",
    "roblox": "Roblox",
    "discord": "Discord",
    "online-games": "VPN для игр и пинг",
    "steam": "Steam",
    "ps-xbox": "PS / Xbox",
    "telegram": "Telegram",
    "chatgpt-openai": "ChatGPT / OpenAI",
    "vpn-not-working": "VPN не работает",
    "slow-speed": "Низкая скорость",
    "how-to-setup": "Как настроить",
    "how-to-share": "Как раздать VPN",
    "what-is-vpn": "Что такое VPN",
    "legality-russia": "Законность в РФ",
    "modern-protocols": "Современные протоколы",
    "private-ip": "Приватный IP",
    "self-hosted-vpn": "Self-hosted VPN",
    "best-vpn-2026": "Лучшие VPN 2026",
    "best-vpn-russia": "Лучшие VPN для России 2026",
    "free-vpn-risks": "Риски бесплатных VPN",
    "paid-vs-free": "Платный vs бесплатный VPN",
    "vpn-android": "Сравнение VPN для Android",
    "apk": "APK без вирусов",
    "gaming": "Игры и низкий пинг",
    "messengers": "Мессенджеры в фоне",
    "streaming": "YouTube и медиа",
    "alternatives": "Сравнение альтернатив",
    "download": "Скачивание и установка",
    # --- Новые разделы (sitemap 2026) ---
    "samsung": "Samsung (Galaxy)",
    "other": "Другие соцсети",
    "twitch": "Twitch",
    "spotify": "Spotify",
    "brawl-stars": "Brawl Stars",
    "minecraft": "Minecraft",
    "video-calls": "Zoom / Teams",
    "iphone": "iPhone",
    "happ": "Happ",
    "vpn-keys": "VPN-ключи",
    "whitelist-bypass": "Обход белых списков",
    "free-trial": "VPN с пробным периодом",
    "install-happ": "Установка Happ",
    "enable-disable": "Включить / отключить VPN",
    "no-registration": "VPN без регистрации",
    "how-bypass": "Как VPN обходит блокировки",
    "vpn-vs-proxy": "VPN vs прокси",
    "vpn-types": "Типы и виды VPN",
    "whitelist": "Белые списки интернета",
    "vless-reality": "VLESS и Reality",
    "wireguard-amnezia": "AmneziaWG / WireGuard",
    "shadowsocks": "Shadowsocks",
    "hysteria": "Hysteria 2",
    "security": "Kill Switch и утечки DNS",
    "split-tunneling": "Split Tunneling",
    # Хаб и обзоры приложений (reviews/apps)
    "apps": "Обзоры приложений",
    "happ-vpn": "Happ VPN",
    "jump-vpn": "JumpJump VPN",
    "adguard-vpn": "AdGuard VPN",
    "radmin-vpn": "Radmin VPN",
    "amnezia-vpn": "Amnezia VPN",
    "telegram-vpn-bots": "VPN-боты в Telegram",
    "planet-vpn": "Planet VPN",
    "proton-vpn": "Proton VPN",
    "outline-vpn": "Outline VPN",
    "v2raytun": "v2RayTun",
    "browsec": "Browsec",
    "sota-vpn": "Sota VPN",
    "byedpi": "ByeDPI",
    "super-vpn": "Super VPN",
    # Блог
    "russian-vpn": "Русский VPN",
    "amnezia-setup": "Амнезия VPN: настройка",
    "vpn-config": "Конфигурация VPN",
    "happ-udalen-iz-app-store": "Happ удалён из App Store",
}


def build_pages_list() -> list[dict]:
    """Полный плоский список страниц с метаинформацией для рендера."""
    pages: list[dict] = [{"path": "/", "kind": "home"}]
    for silo, (title, desc) in SILO_META.items():
        pages.append({"path": f"/{silo}/", "kind": "silo", "silo": silo, "title": title, "description": desc})
    for silo, hub_list in HUBS.items():
        for hub_slug, hub_title, hub_desc in hub_list:
            pages.append(
                {
                    "path": f"/{silo}/{hub_slug}/",
                    "kind": "hub",
                    "silo": silo,
                    "hub": hub_slug,
                    "title": hub_title,
                    "description": hub_desc,
                }
            )
            for leaf in LEAVES.get((silo, hub_slug), []):
                pages.append(
                    {
                        "path": f"/{silo}/{hub_slug}/{leaf}/",
                        "kind": "leaf",
                        "silo": silo,
                        "hub": hub_slug,
                        "leaf": leaf,
                    }
                )
                for sub in SUBLEAVES.get((silo, hub_slug, leaf), []):
                    pages.append(
                        {
                            "path": f"/{silo}/{hub_slug}/{leaf}/{sub}/",
                            "kind": "sub",
                            "silo": silo,
                            "hub": hub_slug,
                            "leaf": leaf,
                            "sub": sub,
                        }
                    )
    return pages
