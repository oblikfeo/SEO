# Источники дизайн-системы (/nice → seo-landing)

| Компонент / стиль | Blade (mainServer) | Статика seo-landing |
|-------------------|--------------------|---------------------|
| Базовая сетка, кнопки, контейнер | `resources/views2/partials/lp-f1-styles.blade.php` | `assets/css/lp-f1.css` |
| Шапка views2, токены mock-* | `resources/views2/partials/lp-header-views2-styles.blade.php` | `assets/css/lp-header-views2.css` |
| Адаптив | `resources/views2/partials/lp-views2-responsive-styles.blade.php` | `assets/css/lp-views2-responsive.css` |
| Hero, карточки, прогресс (/nice) | `resources/views/cabinet/nice/partials/nice-styles.blade.php` | `assets/css/nice.css` |
| Токены (дубль переменных) | см. lp-header-views2 | `assets/css/tokens.css` |
| SEO: крошки, snippet, FAQ, trial | — | `assets/css/seo-components.css` |
| Разметка страницы | `cabinet/nice/index.blade.php` + `views2::layouts.marketing` | `scripts/build_pages.py` → `public/**/index.html` |
| Шрифты Google | marketing layout `<head>` | тот же набор в `page_shell()` |

Извлечение CSS из Blade (при обновлении /nice):

```bash
python scripts/extract_css_from_blade.py
```

(или вручную скопировать содержимое `<style>` из partials в assets/css/*.css)

Префикс классов `lp-` сохранён для прямого переноса в Blade-компоненты Laravel.
