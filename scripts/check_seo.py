# -*- coding: utf-8 -*-
"""Быстрая проверка SEO-метаданных на каждой странице public/."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


def main() -> int:
    issues = []
    total = 0
    for p in sorted(PUBLIC.rglob("index.html")):
        total += 1
        t = p.read_text(encoding="utf-8")
        h1_count = len(re.findall(r"<h1\b", t))
        checks = {
            "h1==1": h1_count == 1,
            "title": bool(re.search(r"<title>[^<]+</title>", t)),
            "description": bool(re.search(r'<meta\s+name="description"\s+content="[^"]+"', t)),
            "canonical": '<link rel="canonical"' in t,
            "robots": '<meta name="robots"' in t,
            "og:title": '<meta property="og:title"' in t,
            "breadcrumb_ld": '"BreadcrumbList"' in t or p.relative_to(PUBLIC) == Path("index.html"),
            "footer_grid": 'lp-seo-footer__grid' in t,
            "header_cta": 'lp-header-cta' in t,
            "login_btn": 'lp-login-btn' in t,
        }
        failed = [k for k, v in checks.items() if not v]
        if failed:
            issues.append((str(p.relative_to(PUBLIC)), h1_count, failed))
    print(f"Total pages: {total}")
    print(f"Issues: {len(issues)}")
    for rel, h1c, fails in issues[:15]:
        print(f"  {rel}  h1={h1c}  fails={fails}")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
