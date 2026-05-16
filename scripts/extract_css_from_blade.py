# -*- coding: utf-8 -*-
"""Повторно вытащить <style> из Blade partials /nice в assets/css/."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MS = ROOT / "mainServer" / "resources"
OUT = Path(__file__).resolve().parents[1] / "assets" / "css"
PAIRS = [
    (MS / "views2/partials/lp-f1-styles.blade.php", "lp-f1.css"),
    (MS / "views2/partials/lp-header-views2-styles.blade.php", "lp-header-views2.css"),
    (MS / "views2/partials/lp-views2-responsive-styles.blade.php", "lp-views2-responsive.css"),
    (MS / "views/cabinet/nice/partials/nice-styles.blade.php", "nice.css"),
]

for src, name in PAIRS:
    text = src.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", text, re.S)
    if m:
        (OUT / name).write_text(m.group(1).strip() + "\n", encoding="utf-8")
        print("OK", name)
    else:
        print("SKIP", name)
