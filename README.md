# Asl Belgisi Telegram bot

Telegram orqali Asl Belgisi markirovka jarayonlarini boshqarish uchun MVP:

- `/start` dan keyin asosiy menyu;
- API kalitni tekshirish va shifrlangan holda SQLite bazada saqlash;
- mahsulot kartochkasini yaratish so'rovi;
- parent va DataMatrix kodlari orqali agregatsiya so'rovi.

## Muhim integratsiya eslatmasi

Asl Belgisi xTrace API va Milliy katalog API endpointlari berilgan ruxsatlar hamda
amaldagi API versiyasiga qarab farq qiladi. `.env` dagi uchta endpointni tashkilotingizga
berilgan rasmiy texnik hujjat bo'yicha kiriting:

- `ASL_API_KEY_CHECK_PATH`
- `ASL_CARD_CREATE_PATH`
- `ASL_AGGREGATION_CREATE_PATH`

Kartochka va agregatsiya payload maydonlari ham rasmiy sxemaga moslashtirilishi kerak.
Ular `app/asl_client.py` ichida alohida joylashtirilgan.

## Ishga tushirish

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/generate_key.py
```

Chiqqan Fernet kalitni `.env` dagi `ENCRYPTION_KEY` qiymatiga yozing. Telegram bot
tokeni va Asl Belgisi API sozlamalarini ham to'ldiring, keyin:

```powershell
python -m app.main
```

## Test

```powershell
python -m unittest discover -s tests -v
```

## Xavfsizlik

`.env` va `bot.db` Git'ga qo'shilmaydi. Ishlab chiqarishda bot serverini faqat
vakolatli xodimlar kira oladigan tarmoqda saqlang va API kalitlarni davriy almashtiring.
