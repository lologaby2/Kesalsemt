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

# إيقاف البوت تلقائيًا بعد 10 دقائق من عدم النشاط
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا بعد 10 دقائق من عدم النشاط.")
            os._exit(0)
        time.sleep(30)

threading.Thread(target=auto_shutdown, daemon=True).start()

# حذف ملف بعد دقيقتين
def delete_file_later(path):
    def delayed_delete():
        time.sleep(600)
        if os.path.exists(path):
            os.remove(path)
    threading.Thread(target=delayed_delete, daemon=True).start()

# اسم عشوائي
def random_filename():
    return str(random.randint(1, 999)) + ".mp3"

# معالجة الصوت عبر Whisper
def process_audio(input_path):
    wav_path = "outputs/temp.wav"
    mp3_output = os.path.join("outputs", random_filename())

    if not input_path.endswith(".wav"):
        subprocess.run(["ffmpeg", "-y", "-i", input_path, wav_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        wav_path = input_path

    result = model.transcribe(wav_path, verbose=False)
    segments = result.get("segments", [])
    if not segments:
        return wav_path

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

    with open("outputs/segments.txt", "w") as f:
        for path in segment_paths:
            f.write(f"file '{path}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
        "outputs/segments.txt", "-c:a", "libmp3lame", "-q:a", "2", mp3_output
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for path in segment_paths:
        os.remove(path)
    os.remove("outputs/segments.txt")
    os.remove(wav_path)

    return mp3_output

# عند استلام فيديو
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

        clip = VideoFileClip(video_path)
        audio_path = "outputs/extracted.wav"
        clip.audio.write_audiofile(audio_path, codec="pcm_s16le")

        mp3_path = process_audio(audio_path)

        with open(mp3_path, "rb") as audio_file:
            bot.send_audio(message.chat.id, audio_file)

        # حذف بعد دقيقتين
        delete_file_later(video_path)
        delete_file_later(audio_path)
        delete_file_later(mp3_path)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

# عند استلام صوت
@bot.message_handler(content_types=["audio", "voice"])
def handle_audio(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ معالجة الملف الصوتي...")

    try:
        file_info = bot.get_file(
            message.audio.file_id if message.audio else message.voice.file_id)
        file_data = bot.download_file(file_info.file_path)
        input_path = "outputs/input_audio.ogg"
        with open(input_path, "wb") as f:
            f.write(file_data)

        wav_path = "outputs/input.wav"
        subprocess.run(["ffmpeg", "-y", "-i", input_path, wav_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        mp3_path = process_audio(wav_path)

        with open(mp3_path, "rb") as audio_file:
            bot.send_audio(message.chat.id, audio_file)

        # حذف بعد دقيقتين
        delete_file_later(input_path)
        delete_file_later(wav_path)
        delete_file_later(mp3_path)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

bot.polling()
