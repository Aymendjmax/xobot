# 🤖 XO Bot — Telegram Interactive Game Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python" alt="Python 3.11">
  <img src="https://img.shields.io/badge/Aiogram-3.4.1-green?logo=telegram" alt="Aiogram 3.4.1">
  <img src="https://img.shields.io/badge/Aiohttp-3.9.3-orange?logo=aiohttp" alt="Aiohttp 3.9.3">
  <img src="https://img.shields.io/badge/Docker-Ready-blue?logo=docker" alt="Docker Ready">
  <img src="https://img.shields.io/badge/Render-Deployed-purple?logo=render" alt="Render Deployed">
</p>

<p align="center">
  <b>بوت تيليجرام تفاعلي للعبة XO (Tic-Tac-Toe)</b><br>
  تحدّ أصدقاءك في أي محادثة تيليجرام عبر رسائل Inline!
</p>

---

## 🎮 الميزات | Features

| الميزة | Feature |
|--------|---------|
| 🎯 **تحدي Inline** — أرسل التحدي في أي محادثة | Inline challenges in any chat |
| 🔒 **اشتراك إجباري** — يجب الانضمام للقناة أولاً | Mandatory channel subscription |
| 🏆 **نظام النقاط** — يحسب انتصارات كل لاعب | Scoring system per player |
| 🔄 **تبديل الأدوار** — عند إعادة اللعب | Automatic role swap on replay |
| 📊 **لوحة مراقبة** — ويب مدمجة لمراقبة حالة البوت | Embedded web monitoring dashboard |
| 🌐 **دعم العربية** — واجهة مستخدم كاملة بالعربية | Full Arabic (RTL) support |

---

## 🚀 التشغيل السريع | Quick Start

### 1. استنساخ المستودع

```bash
git clone https://github.com/Aymendjmax/xobot.git
cd xobot
```

### 2. إعداد متغيرات البيئة

أنشئ ملف `.env` أو عيّن المتغيرات مباشرة:

```env
BOT_TOKEN=your_telegram_bot_token
CHANNEL_ID=-1001234567890
CHANNEL_USERNAME=your_channel_username
DEVELOPER_USERNAME=your_username
PORT=8080
```

### 3. التشغيل بـ Docker

```bash
docker build -t xobot .
docker run -e BOT_TOKEN=... -e CHANNEL_ID=... -e CHANNEL_USERNAME=... -e DEVELOPER_USERNAME=... -p 8080:8080 xobot
```

### 4. التشغيل المباشر

```bash
pip install -r requirements.txt
python main.py
```

---

## 📦 المتطلبات | Requirements

```
aiogram==3.4.1
aiohttp==3.9.3
python-dotenv==1.0.1
```

---

## 🏗️ هيكل المشروع | Project Structure

```
xobot/
├── main.py              # الكود الرئيسي — كل منطق البوت
├── requirements.txt     # الحزم المطلوبة
├── Dockerfile           # إعداد Docker
└── README.md            # هذا الملف
```

---

## 🌐 نقاط النهاية | Endpoints

| المسار | الوصف | Description |
|--------|-------|-------------|
| `/` أو `/status` | لوحة مراقبة HTML جميلة | Beautiful HTML monitoring dashboard |
| `/health` | JSON API — فحص صحة البوت | JSON health check API |
| `/ping` | `pong! 🏓` | Simple ping response |

---

## 🎯 كيفية اللعب | How to Play

1. ابدأ البوت بأمر `/start`
2. انضم للقناة المطلوبة
3. اضغط **"ابدأ التحدي الآن!"**
4. اختر المحادثة وأرسل التحدي
5. اضغط **"انضم للعبة"** — أنت ❌ (X)
6. ينضم صديقك — هو ⭕ (O)
7. العب بالتناوب حتى الفوز أو التعادل!

---

## 🛠️ التقنيات | Tech Stack

- **Python 3.11** — لغة البرمجة
- **Aiogram 3** — إطار عمل بوتات تيليجرام
- **Aiohttp** — خادم ويب مدمج
- **Docker** — حاوية النشر
- **Render** — منصة الاستضافة

---

## 📄 الترخيص | License

هذا المشروع مفتوح المصدر. لا توجد قيود على الاستخدام.

---

<p align="center">
  Made with ❤️ by <a url="Akio-web.vercel.app">Akio co</a>
</p>
