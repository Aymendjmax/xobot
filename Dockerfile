# استخدام صورة خفيفة من بايثون
FROM python:3.11-slim

# تعيين مجهر العمل
WORKDIR /app

# نسخ ملف المتطلبات
COPY requirements.txt .

# تثبيت الحزم
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# أمر التشغيل
CMD ["python", "main.py"]
