import os
import random
import time
import threading
import subprocess
import tempfile
import telebot
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.playback import play
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()
user_files = {}

# ⏱️ إيقاف البوت تلقائيًا بعد 10 دقائق من الخمول
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ توقف البوت تلقائيًا بعد 10 دقائق من الخمول.")
            os._exit(0)
        time.sleep(30)

threading.Thread(target=auto_shutdown, daemon=True).start()

# 🎲 اسم عشوائي
def random_filename():
    return f"{random.randint(1, 999)}.mp3"

# 🧠 إزالة الصمت باستخدام dBFS
def remove_silence(input_path, silence_thresh):
    audio = AudioSegment.from_file(input_path).set_channels(1).set_frame_rate(44100)
    
    # إزالة الصمت باستخدام threshold فقط
    non_silent_parts = audio.split_to_mono()[0].strip_silence(silence_thresh=silence_thresh)

    # دمج الأجزاء المقطوعة
    cleaned_audio = sum(non_silent_parts)
    
    # تحويل النتيجة إلى MP3 بجودة عالية
    output_mp3 = os.path.join("outputs", random_filename())
    cleaned_audio.export(output_mp3, format="mp3", bitrate="320k")
    
    return output_mp3

# 🧰 استخراج الصوت من الفيديو بجودة عالية
def video_to_audio(video_path):
    clip = VideoFileClip(video_path)
    wav_path = "outputs/video_audio.wav"
    clip.audio.write_audiofile(wav_path, codec='pcm_s16le', fps=44100, bitrate="320k")
    return wav_path

# 🔘 قائمة اختيارات الحساسية
def send_vad_options(chat_id, file_path):
    markup = InlineKeyboardMarkup()
    buttons = [InlineKeyboardButton(str(i), callback_data=f"vad_{i}") for i in range(1, 11)]
    markup.row(*buttons[:5])
    markup.row(*buttons[5:])
    user_files[chat_id] = file_path
    bot.send_message(chat_id, "اختر مستوى حساسية إزالة الصمت (1 أدق - 10 أعلى):", reply_markup=markup)

# 🖲️ رد على اختيار الحساسية
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
            bot.send_message(chat_id, "❌ لا يوجد ملف لمعالجته.")
            return

        # حساب عتبة الصوت بناءً على حساسية الـ VAD
        silence_thresh = -40 + (vad_level * 2)  # النطاق من -40 ديسيبل إلى -20 ديسيبل
        processing_msg = bot.send_message(chat_id, f"🔄 جاري المعالجة بحساسية {vad_level}...")
        result = remove_silence(input_path, silence_thresh)

        with open(result, "rb") as audio_file:
            bot.send_audio(chat_id, audio_file)

        os.remove(result)
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ أثناء المعالجة: {e}")

# 📥 استقبال فيديو
@bot.message_handler(content_types=["video"])
def handle_video(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "📥 جارٍ تنزيل الفيديو...")
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
    msg = bot.reply_to(message, "📥 جارٍ تنزيل الملف الصوتي...")
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
