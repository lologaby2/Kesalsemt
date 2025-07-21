import os
import random
import telebot
import time
import threading
import whisper
import subprocess
from moviepy.editor import VideoFileClip

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()

model = whisper.load_model("base")

def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا بعد 10 دقائق من عدم النشاط.")
            os._exit(0)
        time.sleep(30)

threading.Thread(target=auto_shutdown, daemon=True).start()

def random_filename():
    return str(random.randint(1, 999)) + ".mp3"

def video_to_clean_audio(video_path):
    wav_path = "outputs/temp.wav"
    mp3_output = os.path.join("outputs", random_filename())

    # استخراج الصوت
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(wav_path, codec="pcm_s16le")

    # استخدام Whisper لاكتشاف المقاطع الصوتية
    result = model.transcribe(wav_path, verbose=False)
    segments = result.get("segments", [])

    if not segments:
        return wav_path  # فشل التحليل، أرسل الملف كما هو

    # إنشاء ملف نصي مؤقت لتجميع المقاطع
    segment_paths = []
    for i, seg in enumerate(segments):
        start = seg['start']
        end = seg['end']
        part_path = f"outputs/part_{i}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path, "-ss", str(start), "-to", str(end),
            "-c", "copy", part_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segment_paths.append(part_path)

    # دمج جميع المقاطع في ملف mp3 نهائي
    with open("outputs/segments.txt", "w") as f:
        for path in segment_paths:
            f.write(f"file '{path}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
        "outputs/segments.txt", "-c:a", "libmp3lame", "-q:a", "2", mp3_output
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # تنظيف الملفات
    os.remove(wav_path)
    for path in segment_paths:
        os.remove(path)
    os.remove("outputs/segments.txt")

    return mp3_output

@bot.message_handler(content_types=["video"])
def handle_video(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ تحويل الفيديو...")
    try:
        file_info = bot.get_file(message.video.file_id)
        video_data = bot.download_file(file_info.file_path)
        video_path = "outputs/input.mp4"
        with open(video_path, "wb") as f:
            f.write(video_data)

        audio_path = video_to_clean_audio(video_path)
        bot.send_audio(message.chat.id, open(audio_path, "rb"))

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
