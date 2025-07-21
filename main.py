import os
import random
import wave
import contextlib
import telebot
import threading
import time
import webrtcvad
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

# ✅ التوكن
BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)

# ⏱️ مؤقت الإيقاف التلقائي
last_activity_time = time.time()
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا بعد 10 دقائق من عدم النشاط.")
            os._exit(0)
        time.sleep(30)
threading.Thread(target=auto_shutdown, daemon=True).start()

# 🎲 اسم عشوائي
def random_filename():
    return f"{random.randint(1, 999)}.mp3"

# 🎧 تحويل فيديو إلى wav
def convert_to_wav(video_path):
    audio = VideoFileClip(video_path).audio
    wav_path = os.path.join("outputs", "temp.wav")
    audio.write_audiofile(wav_path, codec='pcm_s16le')
    return wav_path

# ✂️ إزالة الصمت باستخدام webrtcvad
def remove_silence_webrtc(wav_path):
    vad = webrtcvad.Vad(2)
    audio = AudioSegment.from_wav(wav_path).set_channels(1).set_frame_rate(16000)
    samples = audio.raw_data
    frame_duration = 30  # ms
    sample_rate = 16000
    frame_bytes = int(sample_rate * frame_duration / 1000) * 2
    segments = []

    for i in range(0, len(samples), frame_bytes):
        frame = samples[i:i+frame_bytes]
        if len(frame) < frame_bytes:
            break
        if vad.is_speech(frame, sample_rate):
            segments.append(frame)

    cleaned_audio = b"".join(segments)
    cleaned_wav = os.path.join("outputs", "clean.wav")
    with wave.open(cleaned_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(cleaned_audio)

    output_mp3 = os.path.join("outputs", random_filename())
    AudioSegment.from_wav(cleaned_wav).export(output_mp3, format="mp3")
    os.remove(wav_path)
    os.remove(cleaned_wav)
    return output_mp3

# 📥 التعامل مع الفيديو
@bot.message_handler(content_types=["video"])
def handle_video(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "🎬 جارٍ تحويل الفيديو إلى صوت...")
    try:
        file_info = bot.get_file(message.video.file_id)
        video_data = bot.download_file(file_info.file_path)
        video_path = "outputs/input.mp4"
        with open(video_path, "wb") as f:
            f.write(video_data)
        wav_path = convert_to_wav(video_path)
        result = remove_silence_webrtc(wav_path)
        bot.send_audio(message.chat.id, open(result, "rb"))
        os.remove(video_path)
        os.remove(result)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

# 🚀 تشغيل البوت
bot.polling()
