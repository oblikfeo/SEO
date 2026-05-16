# Миграция seo-landing → Laravel SSR (Blade)

## 1. Структура в mainServer

```
resources/views/seo/
  layouts/marketing-seo.blade.php   ← аналог page_shell
  partials/header.blade.php
  partials/footer.blade.php
  partials/breadcrumbs.blade.php
  partials/jsonld.blade.php
  silo/devices/index.blade.php      ← L1
  hub/devices/mobile.blade.php      ← L2
  page/devices/mobile/android.blade.php  ← L3
```

CSS: положить `seo-landing/assets/css/*` в `public/css/seo/` или подключить через `@push('styles')` как на `/nice`.

## 2. Маршруты (пример)

```php
// routes/seo.php
Route::get('/devices/{hub?}/{page?}', SeoPageController::class)
    ->where(['hub' => '[a-z0-9-]+', 'page' => '[a-z0-9-]+']);
```

Либо явный список URL из `scripts/site_data.py` → конфиг `config/seo_pages.php`.

## 3. Данные страниц

- Перенести `p0_content()` из `site_data.py` в PHP-массив или JSON в `storage/app/seo/`.
- Контент из `SEO-work/` подключать по slug при расширении.

## 4. UTM и регистрация (ТЗ §5)

Использовать хелпер:

```php
function seo_register_url(string $campaign): string {
    return url('/register?' . http_build_query([
        'utm_source' => 'seo',
        'utm_medium' => 'landing',
        'utm_campaign' => $campaign,
    ]));
}
```

В Blade: `data-page="{{ $pageSlug }}-trial"` на CTA.

## 5. JSON-LD

Структуры из сгенерированного HTML (HowTo, FAQPage, BreadcrumbList, Organization, SoftwareApplication) — вынести в `@include('seo.partials.jsonld', ['schemas' => $schemas])`.

## 6. Деплой статики до Blade

Nginx `root` на `seo-landing/public` — отдельный vhost или подпуть. После Blade — те же URL, отдача через Laravel.

## 7. robots / noindex

Кабинет `/dashboard/*`, `/nice` (auth) — `noindex` в основном приложении, не дублировать в SEO-разделе.
