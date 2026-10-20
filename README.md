# Telegram dasturlar kutubxonasi

Telegram ichida ishlaydigan, Python 3.12+, aiogram 3 va PostgreSQL asosidagi dasturlar katalogi. Bot foydalanuvchiga Telegram `file_id` orqali hujjat yuboradi; faylning binary mazmunini serverga yuklab olmaydi yoki diskda saqlamaydi.

## Imkoniyatlar

- O‘zbekcha menyu, katalog, kategoriyalar, qisman moslikdagi qidiruv, kalit so‘z/sinonimlar va sahifalash.
- Admin ID ro‘yxati bilan himoyalangan Telegram admin paneli: dasturlarni joylash/tahrirlash/yashirish, kategoriyalar, so‘rovlar, foydalanuvchilar, statistika va tasdiqli ommaviy xabar.
- Foydalanuvchi so‘rovlari, admin holatlari va javoblarining bazada saqlanishi.
- PostgreSQL schema bootstrap va boshlang‘ich kategoriyalar.
- Yuklangan fayllar uchun uzluksiz, qayta tiklanadigan metadata draftlari.

Dasturni yuklash yoki tarqatishdan oldin unga nisbatan tegishli huquqlaringiz borligiga ishonch hosil qiling.

## Talablar va o‘rnatish

Python 3.12 yoki undan yangiroq barqaror Python va Telegram bot tokeni talab qilinadi. Sayt, Docker yoki pullik xizmat kerak emas.

### Windows PowerShell

```powershell
cd D:\projects\programm_store_bot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

### Linux

```bash
cd /path/to/programm_store_bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

BotFather’da `/newbot` bilan bot ochib, tokenni `.env` dagi `BOT_TOKEN` ga yozing. Telegram user ID raqamingizni ishonchli ID ko‘rsatuvchi bot yoki Telegram klienti orqali aniqlab, `ADMIN_IDS` ga kiriting; bir nechtasini vergul bilan ajrating. Tokenni hech qachon chatga, logga yoki repozitoriyga yubormang.

```dotenv
BOT_TOKEN=123456:replace_with_real_token
ADMIN_IDS=123456789,987654321
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
LOG_LEVEL=INFO
# Ixtiyoriy: faqat shu fayl kengaytmalarini qabul qiladi; bo‘sh bo‘lsa cheklov yo‘q.
ALLOWED_FILE_EXTENSIONS=.zip,.apk,.exe
```

## Ishga tushirish

Virtual muhit faollashtirilgan holda loyiha papkasidan:

```powershell
python bot.py
```

```bash
python bot.py
```

Birinchi ishga tushishda `DATABASE_URL` dagi PostgreSQL bazasida jadvallar yaratiladi. Bot polling rejimida ishlaydi; ishlab chiqarish serverida jarayonni `systemd` yoki OS xizmat boshqaruvchisi orqali nazorat qiling.

Loglar konsolga yoziladi. `LOG_LEVEL` qiymati `DEBUG`, `INFO`, `WARNING`, `ERROR` yoki `CRITICAL` bo‘lishi mumkin.

## Foydalanish

- Foydalanuvchi `/start` dan keyin tugmalar yordamida qidiradi, katalogni ko‘radi, fayl oladi yoki dastur so‘raydi.
- Admin `/admin` buyrug‘i bilan panelni ochadi. Dastur qo‘shishda faylni **Document** qilib yuboring, so‘ng nom, tavsif, kategoriya ID, sinonimlar va boshqa tavsiflarni kiriting.
- Kategoriya ID’lari admin panelidagi kategoriyalar ro‘yxatida ko‘rinadi. O‘chirish statistikani yo‘qotmaslik uchun dastur yozuvini arxivlaydi (yashiradi).
- Draftlar bazada saqlanadi; bot qayta ishga tushgach `/admin` → “Draftni davom ettirish” orqali tiklanadi. Draftni bekor qilish unga biriktirilgan metama’lumotlarni ham o‘chiradi.
- Faylni almashtirishda ham Telegram hujjatining yangi `file_id` si yoziladi. Faylning binary mazmuni olinmaydi.

Telegram `file_id` ayni bot tomonidan qayta foydalaniladigan identifikator; u faylning o‘zi yoki arxiv nusxasi emas. Faylni keyin yuborish Telegram Bot API va asl fayl mavjudligiga bog‘liq. Bot faqat `file_id` orqali qayta yuboradi; `file_unique_id` qayta yuborish uchun ishlatilmaydi. Telegram limitlari Bot API va account turiga qarab o‘zgarishi mumkin; bot o‘zboshimchalik bilan fayl hajmi chegarasi belgilamaydi.

## Zaxira nusxasi va muammolar

PostgreSQL bazasining zaxira nusxasini Neon boshqaruv paneli yoki `pg_dump` orqali oling:

```powershell
pg_dump "$env:DATABASE_URL" -Fc -f .\data\bot.backup.dump
```

```bash
pg_dump "$DATABASE_URL" -Fc -f data/bot.backup.dump
```

- `BOT_TOKEN` xatosi: `.env` qiymatini tekshiring.
- Admin paneli ko‘rinmasa: `ADMIN_IDS` dagi sonni, vergul va bo‘sh joylarni tekshiring.
- Telegram `file_id` ishlamasa: faylni shu botga qayta yuborib, dasturga yangi identifikator biriktiring.
- Polling ishlamasa: ayni token bilan boshqa polling jarayoni ishlab turganini tekshiring.
- PostgreSQL xatosi bo‘lsa: `DATABASE_URL` qiymati, Neon tarmoq ruxsati va SSL parametrlarini tekshiring.

## Sinovlar

```powershell
python -m pytest
```

Testlar vaqtinchalik SQLite bazasidan foydalanadi; Telegram API’ga haqiqiy xabar yubormaydi.
