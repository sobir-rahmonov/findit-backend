# FindIt: Backend

Universitet, savdo markazi, kutubxona, aeroport va boshqa jamoat joylarida **yo'qolgan va topilgan buyumlarni**
qayd etish, qidirish va haqiqiy egasiga qaytarish jarayonini avtomatlashtiruvchi platformaning server qismi
(REST API + Django admin).

## Qanday ishlaydi

```
Yo'qotgan odam  →  LOST e'lon ─┐
                                ├→ moslashtirish algoritmi → mos e'lonlar (ball bilan)
Topgan odam     →  FOUND e'lon ─┘
        ↓
Egasi da'vo yuboradi (buyumni tasdiqlovchi belgilar)
        ↓
Moderator yashirin belgini solishtiradi → tasdiqlaydi
        ↓
Buyum topshiriladi → ikkala e'lon CLOSED
```

## Imkoniyatlar

- 3 ta rol: **User**, **Moderator**, **Admin**
- Yo'qolgan (LOST) va topilgan (FOUND) e'lonlar, rasm, joy va xarita koordinatalari
- Qidiruv, filtrlar va xarita bo'yicha qidiruv (`lat`, `lng`, `radius_km`)
- Moslashtirish algoritmi: rang, brend, joy, sana va matn bo'yicha ball (0–100)
- Moderatsiya: e'lonlarni tasdiqlash/rad etish, egalik da'volarini tekshirish, topshirishni nazorat qilish
- Yashirin belgi: topilgan buyumning faqat egasi biladigan belgisi (faqat muallif va moderatorga ko'rinadi)
- Bildirishnomalar va shikoyatlar
- Admin: foydalanuvchilar, bloklash, moderator tayinlash, kategoriya/joylar, tizim sozlamalari, statistika
- Django admin paneli (`/admin/`)

## Texnologiyalar

Python 3.13, Django, Django REST Framework, django-filter, django-cors-headers, Pillow, SQLite.

## Loyiha tuzilmasi

```
findit_backend/
├── config/            # settings.py va asosiy urls.py
├── accounts/          # foydalanuvchi, rollar, token, bloklash, admin: foydalanuvchilar API
├── posts/             # kategoriya, joy, e'lon, moslik, shikoyat, moslashtirish, moderatsiya
├── claims/            # egalik da'volari va topshirish jarayoni
├── notifications/     # bildirishnomalar
├── core/              # tizim sozlamalari, statistika, test yordamchilari
├── media/             # yuklangan rasmlar (git'ga kirmaydi)
├── manage.py
└── requirements.txt
```

Biznes mantiq `services.py` fayllarida (`posts/services.py`, `claims/services.py`, `posts/matching.py`).
Ularni API ham, Django admin ham ishlatadi.

## O'rnatish va ishga tushirish

Windows (CMD) uchun:

```cmd
cd findit_backend
python -m venv env
env\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Server `http://127.0.0.1:8000` da ishlaydi.

- API: `http://127.0.0.1:8000/api/`
- Admin panel: `http://127.0.0.1:8000/admin/`

Superuser avtomatik `admin` roliga ega bo'ladi.

## Testlar

```cmd
python manage.py test
```

Testlar vaqtinchalik baza yaratadi, `db.sqlite3` ga tegmaydi. Ular rollar va ruxsatlarni,
e'lonlar ko'rinishini, moslashtirishni, moderatsiyani, da'vo va topshirish jarayonini,
bildirishnomalar, shikoyatlar va admin API'ni tekshiradi. `core/test_flow.py` butun
qaytarish jarayonini boshidan oxirigacha o'tkazadi.

## Holatlar

| E'lon (`status`) | Ma'nosi |
|---|---|
| `pending` | Moderator tekshiruvida |
| `active` | Faol, hamma ko'radi |
| `handover` | Egasi tasdiqlandi, topshirilmoqda |
| `closed` | Buyum qaytarildi |
| `rejected` | Rad etilgan |

| Da'vo (`status`) | Ma'nosi |
|---|---|
| `pending` | Moderator ko'rib chiqmoqda |
| `approved` | Tasdiqlandi, topshirish kutilmoqda |
| `completed` | Buyum topshirildi |
| `rejected` | Rad etildi |
| `cancelled` | Bekor qilindi (da'vogar, boshqa da'vo tasdiqlangani yoki tasdiq bekor qilingani sababli) |

## Moslashtirish algoritmi

Yangi faol e'lon qarama-qarshi turdagi faol e'lonlar bilan solishtiriladi. Juft quyidagi shartlarga mos bo'lsa hisoblanadi:
bir xil kategoriya, turli muallif, sana farqi `match_date_window_days` dan oshmasligi va koordinatalar bo'lsa
masofa `match_max_distance_km` dan oshmasligi.

| Mezon | Eng ko'p ball |
|---|---|
| Matn (nom va tavsif) | 30 |
| Rang | 20 |
| Joy / masofa | 20 |
| Sana | 15 |
| Brend / model | 15 |

Jami ball `match_threshold` (standart 50) dan past bo'lmasa, moslik saqlanadi va ikkala egaga bildirishnoma yuboriladi.

## API

Asosiy manzil: `/api/`. Ro'yxatlar sahifalanadi (bir sahifada 12 ta): `{ count, next, previous, results }`
(kategoriyalar va joylar sahifalanmaydi). Kirgandan keyin olingan tokenni har so'rovga qo'shing:

```
Authorization: Token <token>
```

### Autentifikatsiya

| Manzil | Usul | Tavsif |
|---|---|---|
| `/api/auth/register/` | POST | Ro'yxatdan o'tish (rol doim `user`) |
| `/api/auth/login/` | POST | Kirish, token qaytaradi |
| `/api/auth/logout/` | POST | Chiqish |
| `/api/auth/me/` | GET, PATCH | Profil |
| `/api/auth/change-password/` | POST | Parolni almashtirish (yangi token beradi) |

### Kategoriyalar va joylar

| Manzil | Usul | Kim |
|---|---|---|
| `/api/categories/`, `/api/places/` | GET | hamma |
| `/api/categories/`, `/api/places/` | POST, PATCH, DELETE | admin |

Joylar filtri: `place_type`, `search`. Ichida e'lon bor kategoriyani o'chirib bo'lmaydi, uni nofaol qiling.

### E'lonlar

| Manzil | Usul | Kim | Tavsif |
|---|---|---|---|
| `/api/posts/` | GET | hamma | Faol e'lonlar |
| `/api/posts/` | POST | kirgan | E'lon yaratish (rasm: `multipart/form-data`) |
| `/api/posts/{id}/` | GET | hamma | Bitta e'lon (faol, o'zining yoki moderator uchun har qanday) |
| `/api/posts/{id}/` | PATCH, DELETE | muallif (DELETE: admin ham) | Tahrirlangan e'lon qayta tekshiruvga ketadi |
| `/api/posts/mine/` | GET | kirgan | Mening e'lonlarim (hamma holatda) |
| `/api/posts/{id}/matches/` | GET | muallif, moderator | Mos e'lonlar va ballari |

Filtrlar: `type`, `category` (slug), `place`, `color`, `date_from`, `date_to`, `search`,
`ordering` (`created_at`, `event_date`), xarita uchun `lat`, `lng`, `radius_km`.

### Da'volar

| Manzil | Usul | Kim | Tavsif |
|---|---|---|---|
| `/api/claims/` | POST | kirgan | Egalik da'vosi |
| `/api/claims/` | GET | kirgan | Mening da'volarim |
| `/api/claims/{id}/cancel/` | POST | da'vogar | Kutilayotgan da'voni bekor qilish |

Da'vo tasdiqlangandan keyin da'vogarga buyum saqlanayotgan joy (`pickup_info`) ko'rinadi.

### Shikoyatlar va bildirishnomalar

| Manzil | Usul | Tavsif |
|---|---|---|
| `/api/reports/` | POST, GET | Shikoyat yuborish (e'longa yoki foydalanuvchiga) va o'zinikini ko'rish |
| `/api/notifications/` | GET | Mening xabarlarim (`is_read`, `kind` filtri) |
| `/api/notifications/unread-count/` | GET | O'qilmaganlar soni |
| `/api/notifications/{id}/read/` | POST | O'qilgan qilish |
| `/api/notifications/read-all/` | POST | Hammasini o'qilgan qilish |
| `/api/notifications/{id}/` | DELETE | O'chirish |

### Moderator (moderator va admin)

| Manzil | Usul | Tavsif |
|---|---|---|
| `/api/moderation/posts/` | GET | E'lonlar navbati (standart `pending`, `?status=` bilan boshqa holatlar) |
| `/api/moderation/posts/{id}/approve/`, `reject/` | POST | Tasdiqlash / rad etish (`reason` shart) |
| `/api/moderation/claims/` | GET | Da'volar navbati, yashirin belgi bilan |
| `/api/moderation/claims/{id}/approve/`, `reject/`, `complete/`, `revoke/` | POST | Tasdiqlash, rad etish, topshirildi, tasdiqni bekor qilish |
| `/api/moderation/reports/` | GET | Shikoyatlar navbati |
| `/api/moderation/reports/{id}/resolve/`, `dismiss/` | POST | O'rinli / asossiz (`note` shart, `resolve` da `reject_post` ixtiyoriy) |

### Admin (faqat admin)

| Manzil | Usul | Tavsif |
|---|---|---|
| `/api/admin/users/` | GET | Foydalanuvchilar (`role`, `is_blocked`, `search`, `ordering`) |
| `/api/admin/users/{id}/block/`, `unblock/` | POST | Bloklash (tokenlar o'chadi) / blokdan chiqarish |
| `/api/admin/users/{id}/set-role/` | POST | `{"role": "moderator"}` yoki `{"role": "user"}` |
| `/api/admin/settings/` | GET, PATCH | Tizim sozlamalari |
| `/api/admin/statistics/` | GET | Statistika (dashboard uchun) |

Tizim sozlamalari: `require_moderation`, `match_threshold`, `match_max_distance_km`,
`match_date_window_days`, `max_active_posts_per_user`.

## Ruxsatlar

| Rol | Imkoniyat |
|---|---|
| Mehmon | Faol e'lonlarni ko'rish, kategoriya va joylar |
| User | + e'lon yaratish, da'vo, shikoyat, bildirishnomalar |
| Moderator | + e'lon, da'vo va shikoyatlarni ko'rib chiqish, yashirin belgini ko'rish |
| Admin | + foydalanuvchilar, bloklash, moderator tayinlash, kategoriya/joylar, sozlamalar, statistika |

## Eslatmalar

- Yashirin belgi (`private_detail`) faqat e'lon muallifi va moderatorlarga ko'rinadi.
- Bloklangan foydalanuvchining tokeni darhol ishlamay qoladi.
- Moderator o'z da'vosini o'zi tasdiqlay olmaydi.
- Administratorlar API orqali emas, `createsuperuser` yoki Django admin orqali yaratiladi.
- Da'vo, e'lon holatlarini Django adminida qo'lda o'zgartirsangiz, bildirishnomalar va bog'liq holatlar
  yangilanmaydi. Ularni API orqali boshqaring.
- Productionga chiqarishdan oldin: `DEBUG = False`, yangi `SECRET_KEY`, `ALLOWED_HOSTS` ni to'ldiring va
  `CORS_ALLOW_ALL_ORIGINS` o'rniga `CORS_ALLOWED_ORIGINS` ro'yxatini bering.