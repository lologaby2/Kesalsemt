import os
import random
import time
import threading
import subprocess
import wave
import contextlib
import webrtcvad
import collections
import telebot
from moviepy.editor import VideoFileClip
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pydub import AudioSegment

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()
user_files = {}

# ⏱️ إيقاف تلقائي بعد 10 دقائق خمول
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

# 🎯 إزالة الصمت باستخدام webrtcvad + ffmpeg
def remove_silence_webrtc(input_path, mode):
    raw_wav = "outputs/converted.wav"
    final_output = os.path.join("outputs", random_filename())

    # تحويل الملف إلى PCM mono 16-bit 16kHz
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-ac", "1", "-ar", "16000", "-f", "wav", raw_wav
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # إعداد VAD
    vad = webrtcvad.Vad()
    vad.set_mode(mode)

    # قراءة الصوت
    with wave.open(raw_wav, 'rb') as wf:
        sample_rate = wf.getframerate()
        frame_duration = 30  # ms
        frame_size = int(sample_rate * frame_duration / 1000) * 2
        frames = []
        while True:
            frame = wf.readframes(frame_size // 2)
            if len(frame) < frame_size:
                break
            frames.append(frame)

    # استخراج التوقيتات الناطقة
    speech_times = []
    for i, frame in enumerate(frames):
        if vad.is_speech(frame, sample_rate):
            start = i * 30
            end = start + 30
            speech_times.append((start, end))

    if not speech_times:
        return None

    # دمج التوقيتات المتقاربة
    merged = []
    prev_start, prev_end = speech_times[0]
    for start, end in speech_times[1:]:
        if start - prev_end <= 300:
            prev_end = end
        else:
            merged.append((prev_start, prev_end))
            prev_start, prev_end = start, end
    merged.append((prev_start, prev_end))

    # قص الصوت بواسطة ffmpeg
    filter_parts = []
    for i, (start, end) in enumerate(merged):
        filter_parts.append(f"[0:a]atrim=start={start/1000}:end={end/1000},asetpts=PTS-STARTPTS[a{i}]")
    filter_complex = ";".join(filter_parts)
    concat_inputs = "".join([f"[a{i}]" for i in range(len(merged))])
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", f"{filter_complex};{concat_inputs}concat=n={len(merged)}:v=0:a=1[out]",
        "-map", "[out]", "-b:a", "320k", final_output
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return final_output

# 🧰 استخراج الصوت من الفيديو
def video_to_audio(video_path):
    clip = VideoFileClip(video_path)
    wav_path = "outputs/video_audio.wav"
    clip.audio.write_audiofile(wav_path, codec='pcm_s16le', fps=44100, bitrate="320k")
    return wav_path

# 🔘 قائمة خيارات الحساسية 0 إلى 3
def send_vad_options(chat_id, file_path):
    markup = InlineKeyboardMarkup()
    buttons = [InlineKeyboardButton(str(i), callback_data=f"vad_{i}") for i in range(0, 4)]
    markup.row(*buttons)
    user_files[chat_id] = file_path
    bot.send_message(chat_id, "اختر مستوى حساسية إزالة الصمت (0 = أدق, 3 = أعلى):", reply_markup=markup)

# 🖲️ تنفيذ المعالجة عند اختيار الحساسية
@bot.callback_query_handler(func=lambda call: call.data.startswith("vad_"))
def process_callback(call):
    global last_activity_time
    last_activity_time = time.time()
    vad_mode = int(call.data.split("_")[1])
    chat_id = call.message.chat.id

    try:
        bot.answer_callback_query(call.id, text=f"🔧 معالجة الصوت بحساسية {vad_mode}")
        input_path = user_files.get(chat_id)
        if not input_path:
            bot.send_message(chat_id, "❌ لا يوجد ملف لمعالجته.")
            return

        bot.send_message(chat_id, f"🔄 جاري إزالة الصمت بدقة (حساسية {vad_mode})...")
        result = remove_silence_webrtc(input_path, vad_mode)

        if not result:
            bot.send_message(chat_id, "❌ لم يتم العثور على كلام في الملف.")
            return

        with open(result, "rb") as audio_file:
            bot.send_audio(chat_id, audio_file)

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
