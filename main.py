import os
import random
import time
import threading
import subprocess
import tempfile
import telebot
import whisper
from moviepy.editor import VideoFileClip

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()
model = whisper.load_model("base")

# إيقاف البوت تلقائيًا بعد 10 دقائق من الخمول
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا بعد 10 دقائق من الخمول.")
            os._exit(0)
        time.sleep(30)
threading.Thread(target=auto_shutdown, daemon=True).start()

def random_filename():
    return str(random.randint(1, 999)) + ".mp3"

def process_audio(input_path):
    with tempfile.NamedTemporaryFile(delete=False, dir="outputs", suffix=".wav") as temp_wav:
        wav_path = temp_wav.name

    subprocess.run(["ffmpeg", "-y", "-i", input_path, wav_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    result = model.transcribe(wav_path, verbose=False)
    segments = result.get("segments", [])
    if not segments:
        mp3_output = os.path.join("outputs", random_filename())
        subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "2", mp3_output],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return mp3_output

    segment_paths = []
    for i, seg in enumerate(segments):
        part_path = f"outputs/part_{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-ss", str(seg["start"]), "-to", str(seg["end"]),
                        "-c", "copy", part_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segment_paths.append(part_path)

    concat_list_path = "outputs/segments.txt"
    with open(concat_list_path, "w") as f:
        for p in segment_paths:
            f.write(f"file '{p}'\n")

    mp3_output = os.path.join("outputs", random_filename())
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
                    "-c:a", "libmp3lame", "-q:a", "2", mp3_output], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return mp3_output

# استقبال فيديو
@bot.message_handler(content_types=["video"])
def handle_video(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ معالجة الفيديو...")

    try:
        file_info = bot.get_file(message.video.file_id)
        video_data = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(delete=False, dir="outputs", suffix=".mp4") as temp_vid:
            video_path = temp_vid.name
            temp_vid.write(video_data)

        clip = VideoFileClip(video_path)
        audio_path = video_path.replace(".mp4", ".wav")
        clip.audio.write_audiofile(audio_path, codec="pcm_s16le")

        mp3_path = process_audio(audio_path)

        with open(mp3_path, "rb") as audio_file:
            bot.send_audio(message.chat.id, audio_file)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try: bot.delete_message(message.chat.id, msg.message_id)
        except: pass

# استقبال صوت
@bot.message_handler(content_types=["audio", "voice"])
def handle_audio(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ معالجة الصوت...")

    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_info = bot.get_file(file_id)
        file_data = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(delete=False, dir="outputs", suffix=".ogg") as temp_in:
            input_path = temp_in.name
            temp_in.write(file_data)

        mp3_path = process_audio(input_path)

        with open(mp3_path, "rb") as audio_file:
            bot.send_audio(message.chat.id, audio_file)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try: bot.delete_message(message.chat.id, msg.message_id)
        except: pass

print("✅ البوت يعمل الآن.")
bot.polling(skip_pending=True)
