import os
import random
import time
import threading
import subprocess
import telebot
import whisper
from moviepy.editor import VideoFileClip

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

# إنشاء مجلد مؤقت
os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()

# تحميل نموذج Whisper
model = whisper.load_model("base")

# إيقاف البوت تلقائيًا بعد 10 دقائق
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا بعد 10 دقائق من عدم النشاط.")
            os._exit(0)
        time.sleep(30)

threading.Thread(target=auto_shutdown, daemon=True).start()

# اسم عشوائي للملف
def random_filename():
    return str(random.randint(1, 999)) + ".mp3"

# تحويل الفيديو إلى صوت وقص الصمت باستخدام Whisper
def video_to_clean_audio(video_path):
    wav_path = "outputs/temp.wav"
    mp3_output = os.path.join("outputs", random_filename())

    # استخراج الصوت من الفيديو
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(wav_path, codec="pcm_s16le")

    # تحليل الصوت لتحديد المقاطع غير الصامتة
    result = model.transcribe(wav_path, verbose=False)
    segments = result.get("segments", [])

    if not segments:
        return wav_path  # fallback في حال لم يتم الكشف عن مقاطع

    segment_paths = []
    for i, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        part_path = f"outputs/part_{i}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path, "-ss", str(start), "-to", str(end),
            "-c", "copy", part_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segment_paths.append(part_path)

    # حفظ قائمة المقاطع لدمجها
    with open("outputs/segments.txt", "w") as f:
        for path in segment_paths:
            f.write(f"file '{path}'\n")

    # دمج جميع المقاطع في ملف mp3 واحد
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
        "outputs/segments.txt", "-c:a", "libmp3lame", "-q:a", "2", mp3_output
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # تنظيف الملفات المؤقتة
    os.remove(wav_path)
    for path in segment_paths:
        os.remove(path)
    os.remove("outputs/segments.txt")

    return mp3_output

# التعامل مع الرسائل التي تحتوي على فيديو
@bot.message_handler(content_types=["video"])
def handle_video(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ تحويل الفيديو إلى صوت...")

    try:
        file_info = bot.get_file(message.video.file_id)
        video_data = bot.download_file(file_info.file_path)
        video_path = "outputs/input.mp4"
        with open(video_path, "wb") as f:
            f.write(video_data)

        audio_path = video_to_clean_audio(video_path)

        # تأكد من أن الملف مفتوح أثناء الإرسال
        with open(audio_path, "rb") as audio_file:
            bot.send_audio(message.chat.id, audio_file)

        os.remove(video_path)
        os.remove(audio_path)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

bot.polling()
