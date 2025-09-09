# Nomo Flow

تطبيق تسويقي مخصص للتجار على منصة **سلة** يضيف أدوات تفاعلية مثل:  
- كوبونات الخصم  
- التنبيهات (Email / SMS / WhatsApp / Push)  
- عداد الزوار (Live Counter)  
- جامع الإيميلات (Email Collector)  
- بيانات الزوار (Visitor Data)  
- آخر عملية شراء (Latest Conversion)  

🎯 الهدف: زيادة مبيعات المتجر وتحسين تجربة العملاء من خلال أدوات تسويقية سهلة التفعيل والإدارة.

---

## 🚀 المميزات
- **لوحة تحكم (Dashboard):** كل ميزة تظهر كبطاقة يمكن تفعيلها أو إيقافها.  
- **تكامل مع سلة (Salla Integration):** ربط OAuth 2.0 آمن مع متجر التاجر.  
- **Webhooks:** استقبال أحداث (طلب جديد، سلة متروكة، كوبون مستخدم).  
- **التقارير:** عرض وتحليل استخدام الكوبونات والتنبيهات والزوار.  
- **تخصيص:** إعدادات مرنة لكل ميزة عبر JSON.  

---

<h3>🗂️ هيكل المشروع — Nomo Flow</h3>

<div dir="ltr">

<pre><code>nomo-flow/
├─ manage.py
├─ requirements.txt
├─ .env.example
├─ README.md
│
├─ nomo_flow/
│  ├─ __init__.py
│  ├─ settings.py
│  ├─ urls.py
│  ├─ wsgi.py
│  └─ asgi.py
│
├─ core/
│  ├─ __init__.py
│  ├─ salla_client.py
│  ├─ webhooks.py
│  ├─ utils.py
│  └─ models.py
│
├─ integrations/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  └─ admin.py
│
├─ features/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  ├─ services.py
│  └─ admin.py
│
├─ coupons/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  ├─ services.py
│  └─ admin.py
│
├─ notifications/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  ├─ services.py
│  └─ admin.py
│
├─ visitors/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  └─ admin.py
│
├─ events/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  └─ admin.py
│
├─ attributions/
│  ├─ __init__.py
│  ├─ models.py
│  └─ services.py
│
├─ templates/
│  ├─ base.html
│  ├─ features/
│  ├─ coupons/
│  ├─ notifications/
│  ├─ visitors/
│  └─ integrations/
│
├─ static/
│  ├─ css/
│  ├─ js/
│  └─ images/
│
├─ scripts/
│  ├─ dev_seed.py
│  └─ export_db.sh
│
├─ tests/
│  ├─ __init__.py
│  ├─ test_features.py
│  ├─ test_coupons.py
│  └─ test_notifications.py
│
└─ docs/
   ├─ ERD.dbml
   ├─ UX-flow.md
   └─ API-notes.md
</code></pre>

</div>