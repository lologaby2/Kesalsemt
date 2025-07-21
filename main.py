import os
import random
import wave
import time
import threading
import telebot
import webrtcvad
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()
user_files = {}

# ⏱️ إيقاف البوت بعد 10 دقائق
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ توقف البوت بعد 10 دقائق خمول.")
            os._exit(0)
        time.sleep(30)
threading.Thread(target=auto_shutdown, daemon=True).start()

# 🎲 اسم عشوائي
def random_filename():
    return f"{random.randint(1, 999)}.mp3"

# 🧠 إزالة الصمت بجودة ممتازة
def remove_silence(input_path, vad_level):
    sample_rate = 16000
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_sample_width(2).set_frame_rate(sample_rate)

    vad = webrtcvad.Vad(vad_level)
    samples = audio.raw_data
    frame_duration = 30
    frame_bytes = int(sample_rate * frame_duration / 1000) * 2
    segments = []

    for i in range(0, len(samples), frame_bytes):
        frame = samples[i:i+frame_bytes]
        if len(frame) < frame_bytes:
            break
        if vad.is_speech(frame, sample_rate):
            segments.append(frame)

    raw_clean = b''.join(segments)

    temp_wav = "outputs/temp_clean.wav"
    with wave.open(temp_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_clean)

    output_mp3 = os.path.join("outputs", random_filename())
    AudioSegment.from_wav(temp_wav)\
        .set_channels(2)\
        .set_frame_rate(44100)\
        .export(output_mp3, format="mp3", bitrate="320k")
    os.remove(temp_wav)
    return output_mp3

# 🧰 استخراج الصوت من الفيديو
def video_to_audio(video_path):
    clip = VideoFileClip(video_path)
    wav_path = "outputs/video_audio.wav"
    clip.audio.write_audiofile(wav_path, codec='pcm_s16le', fps=44100)
    return wav_path

# 🔘 أزرار الحساسية (0 إلى 3 فقط)
def send_vad_options(chat_id, file_path):
    markup = InlineKeyboardMarkup()
    buttons = [InlineKeyboardButton(str(i), callback_data=f"vad_{i}") for i in range(4)]
    markup.row(*buttons)
    user_files[chat_id] = file_path
    bot.send_message(chat_id, "اختر حساسية إزالة الصمت (0 أدق - 3 أعلى):", reply_markup=markup)

# 🖲️ تنفيذ المعالجة
@bot.callback_query_handler(func=lambda call: call.data.startswith("vad_"))
def process_callback(call):
    global last_activity_time
    last_activity_time = time.time()
    vad_level = int(call.data.split("_")[1])
    chat_id = call.message.chat.id
    try:
        bot.answer_callback_query(call.id, text=f"🔧 معالجة الصوت بحساسية {vad_level}")
        input_path = user_files.get(chat_id)
        if not input_path:
            bot.send_message(chat_id, "❌ لا يوجد ملف.")
            return
        msg = bot.send_message(chat_id, f"🔄 جاري المعالجة...")
        result = remove_silence(input_path, vad_level)
        with open(result, "rb") as audio_file:
            bot.send_audio(chat_id, audio_file)
        os.remove(result)
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ: {e}")

# 📥 استقبال فيديو
@bot.message_handler(content_types=["video"])
def handle_video(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "📥 جاري تنزيل الفيديو...")
    try:
        file_info = bot.get_file(message.video.file_id)
        data = bot.download_file(file_info.file_path)
        path = "outputs/input_video.mp4"
        with open(path, "wb") as f:
            f.write(data)
        wav_path = video_to_audio(path)
        os.remove(path)
        send_vad_options(message.chat.id, wav_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        bot.delete_message(message.chat.id, msg.message_id)

# 📥 استقبال صوت/voice
@bot.message_handler(content_types=["audio", "voice"])
def handle_audio(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "📥 جاري تنزيل الملف الصوتي...")
    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_info = bot.get_file(file_id)
        data = bot.download_file(file_info.file_path)
        path = "outputs/input_audio.ogg"
        with open(path, "wb") as f:
            f.write(data)
        send_vad_options(message.chat.id, path)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        bot.delete_message(message.chat.id, msg.message_id)

print("✅ البوت يعمل الآن.")
bot.polling()
