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
        ("gaming", "VPN для игр", "Roblox, Discord, Steam."),
        ("tools", "Коммуникации и сервисы", "Telegram, ChatGPT."),
    ],
    "kb": [
        ("fixes", "Не работает VPN", "Диагностика и решения."),
        ("guides", "Инструкции", "Настройка и раздача VPN."),
        ("education", "Обучение", "Что такое VPN, законность."),
    ],
    "tech": [
        ("protocols", "Протоколы", "VLESS, Reality, Shadowsocks."),
        ("servers", "Серверы", "Приватный IP, self-hosted."),
    ],
    "reviews": [
        ("lists", "Списки и сравнения", "Обзоры и тематические материалы."),
        ("apps", "Обзоры приложений", "Happ, JumpJump, AdGuard, Amnezia и другие."),
    ],
    "blog": [
        ("working-vpn-russia", "Какой VPN работает в России сейчас", "Рабочие технологии доступа в 2026 году."),
        ("russian-vpn", "Русский VPN — что это значит", "Разбираемся в термине и отличиях."),
        ("buy-vpn", "Купить VPN: как выбрать тариф", "Критерии выбора платного доступа."),
        ("vpn-subscription", "VPN-подписка: что входит", "Что включает подписка и как продлевать."),
        ("amnezia-setup", "Амнезия VPN: настройка с нуля", "Пошаговая настройка AmneziaVPN."),
        ("vpn-no-viruses", "VPN без вирусов: как проверить", "Как скачать безопасно и проверить файл."),
        ("tspu-whitelist", "Белый список ТСПУ: что это", "Как работает фильтрация и белые списки."),
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
    ("kb", "guides"): ["autodeploy-test", "how-to-setup", "how-to-share", "vpn-keys", "install-happ", "enable-disable", "no-registration"],
    ("kb", "education"): ["what-is-vpn", "legality-russia", "how-bypass", "vpn-vs-proxy", "vpn-types"],
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
    ],
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
    "autodeploy-test": "Тест автосборки",
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
    "online-games": "Онлайн-игры",
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
    "install-happ": "Установка Happ",
    "enable-disable": "Включить / отключить VPN",
    "no-registration": "VPN без регистрации",
    "how-bypass": "Как VPN обходит блокировки",
    "vpn-vs-proxy": "VPN vs прокси",
    "vpn-types": "Типы и виды VPN",
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
    "telegram-vpn-bots": "Telegram-боты VPN",
    "planet-vpn": "Planet VPN",
    "proton-vpn": "Proton VPN",
    "outline-vpn": "Outline VPN",
    "v2raytun": "v2RayTun",
    "browsec": "Browsec",
    # Блог
    "working-vpn-russia": "Какой VPN работает в России",
    "russian-vpn": "Русский VPN",
    "buy-vpn": "Купить VPN",
    "vpn-subscription": "VPN-подписка",
    "amnezia-setup": "Амнезия VPN: настройка",
    "vpn-no-viruses": "VPN без вирусов",
    "tspu-whitelist": "Белый список ТСПУ",
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
