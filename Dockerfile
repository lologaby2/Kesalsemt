# استخدم صورة رسمية من بايثون
FROM python:3.10-slim

# تثبيت الأدوات المطلوبة
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    build-essential \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libffi-dev \
    && apt-get clean

# نسخ ملفات المشروع
WORKDIR /app
COPY . .

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# تشغيل البوت
CMD ["python", "main.py"]
