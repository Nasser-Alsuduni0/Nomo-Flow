# Nomo Flow (Works with Salla)

> Smart marketing toolkit for Salla stores: coupons, notifications, live visitor counter, email collector, recent purchases, and social ad campaign launcher (TikTok/Snapchat/Instagram) — all from one dashboard.

## Features
- Salla OAuth 2.0 connect/callback flow with token storage per merchant
- Webhook receiver for `app.store.authorize` and event ingestion
- Coupons engine: create/issue/track discount codes with usage limits
- Live View Counter widget rendered on storefront with configurable rules
- Email Collector popup with double‑opt‑in and exportable CSV list
- Notifications center for on‑site alerts (target by page/device/behavior)
- Recent Purchases ticker for social proof (storefront widget)
- Campaign Launcher to publish ads to TikTok/Snapchat/Instagram from one UI
- Tracking module for attribution (UTM, click → order matching)
- Optimizer (rules/A‑B tests) to auto‑tune widget variants
- Admin dashboard with metrics, reports, and per‑feature toggles

---

## Project Structure (Django 5.x)

```
Nomo-Flow/
├─ README.md
├─ requirements.txt
├─ NomoFlow/
│  ├─ manage.py                         # Django entry
│  ├─ db.sqlite3                        # Dev database (local)
│  └─ NomoFlow/                         # Project module
│     ├─ settings.py                    # Real settings (env-driven)
│     ├─ urls.py                        # Root urls → core + salla
│     ├─ asgi.py | wsgi.py | __init__.py
│
│  ├─ core/                             # Public site (landing)
│  │  ├─ views.py | urls.py
│  │  ├─ templates/core/home.html       # Landing + i18n + SVG icons
│  │  └─ static/core/img/logo.png       # Logo
│
│  ├─ integrations/                     # Salla OAuth + webhook
│  │  ├─ urls.py                        # Mounted at /salla/
│  │  └─ views.py                       # connect/callback/webhook
│
│  ├─ coupons/ | features/ | notifications/ | visitors/
│  ├─ tracking/ | optimizer/ | dashboard/
│  └─ …
```

---

### عربي (مختصر)
مشروع **Nomo Flow** متوافق مع منصة **سلة** ويقدّم أدوات تسويقية جاهزة: كوبونات، تنبيهات، عدّاد زوار لحظي، جامع إيميلات، وعرض أحدث المشتريات، بالإضافة إلى إطلاق حملات إعلانية اجتماعية. الصفحة الرئيسية باللغة العربية أو الإنجليزية ويمكن التبديل بينهما بسهولة.