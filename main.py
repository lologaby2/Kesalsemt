import os
import random
import time
import threading
import wave
import webrtcvad
import contextlib
import subprocess
import telebot
from moviepy.editor import VideoFileClip
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs("outputs", exist_ok=True)
last_activity_time = time.time()
user_files = {}
user_last_segments = {}  # لحفظ نتائج القص حسب المستخدم

# ⏱️ إيقاف تلقائي بعد 10 دقائق
def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا.")
            os._exit(0)
        time.sleep(30)

threading.Thread(target=auto_shutdown, daemon=True).start()

# 🎲 اسم عشوائي للملف
def random_filename():
    return f"{random.randint(1, 999)}.mp3"

# 🧠 إزالة الصمت باستخدام webrtcvad
def remove_silence_webrtc(input_path, mode, extra_trim=0):
    raw_wav = "outputs/converted.wav"
    output_path = os.path.join("outputs", random_filename())

    # تحويل إلى WAV PCM 16-bit mono 16kHz
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-ac", "1", "-ar", "16000", "-f", "wav", raw_wav
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    vad = webrtcvad.Vad(mode)

    with contextlib.closing(wave.open(raw_wav, 'rb')) as wf:
        sample_rate = wf.getframerate()
        frame_duration = 10  # ms
        frame_bytes = int(sample_rate * frame_duration / 1000) * 2
        frames = []
        timestamps = []
        timestamp = 0

        while True:
            frame = wf.readframes(frame_bytes // 2)
            if len(frame) < frame_bytes:
                break
            is_speech = vad.is_speech(frame, sample_rate)
            frames.append((frame, is_speech))
            timestamps.append(timestamp)
            timestamp += frame_duration

    speech_segments = []
    start_time = None
    for i, (frame, is_speech) in enumerate(frames):
        if is_speech and start_time is None:
            start_time = i * frame_duration
        elif not is_speech and start_time is not None:
            end_time = i * frame_duration
            speech_segments.append((start_time, end_time))
            start_time = None
    if start_time is not None:
        speech_segments.append((start_time, len(frames) * frame_duration))

    if not speech_segments:
        return None, None

    # تطبيق القص الإضافي
    adjusted_segments = []
    for start, end in speech_segments:
        start = max(0, start - extra_trim)
        end = max(0, end - extra_trim)
        adjusted_segments.append((start, end))

    # إعداد فلتر FFmpeg لقص المقطع
    filter_parts = []
    for i, (start, end) in enumerate(adjusted_segments):
        filter_parts.append(f"[0:a]atrim=start={start/1000}:end={end/1000},asetpts=PTS-STARTPTS[a{i}]")
    concat_inputs = "".join(f"[a{i}]" for i in range(len(adjusted_segments)))
    filter_complex = ";".join(filter_parts) + f";{concat_inputs}concat=n={len(adjusted_segments)}:v=0:a=1[out]"

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]", "-b:a", "320k", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return output_path, adjusted_segments

# 🧰 استخراج صوت من فيديو
def video_to_audio(video_path):
    clip = VideoFileClip(video_path)
    wav_path = "outputs/video_audio.wav"
    clip.audio.write_audiofile(wav_path, codec='pcm_s16le', fps=44100, bitrate="320k")
    return wav_path

# 🔘 قائمة الحساسية 0–3
def send_vad_options(chat_id, file_path):
    markup = InlineKeyboardMarkup()
    buttons = [InlineKeyboardButton(str(i), callback_data=f"vad_{i}") for i in range(0, 4)]
    markup.row(*buttons)
    user_files[chat_id] = file_path
    bot.send_message(chat_id, "اختر حساسية إزالة الصمت (0 أدق – 3 أعلى):", reply_markup=markup)

# ⏺️ تنفيذ عند الضغط على زر الحساسية
@bot.callback_query_handler(func=lambda call: call.data.startswith("vad_"))
def process_callback(call):
    global last_activity_time
    last_activity_time = time.time()
    vad_mode = int(call.data.split("_")[1])
    chat_id = call.message.chat.id

    try:
        bot.answer_callback_query(call.id, text=f"🔧 جاري المعالجة بحساسية {vad_mode}")
        input_path = user_files.get(chat_id)
        if not input_path:
            bot.send_message(chat_id, "❌ لا يوجد ملف.")
            return

        bot.send_message(chat_id, f"🔄 إزالة الصمت بدقة...")
        result, segments = remove_silence_webrtc(input_path, vad_mode)

        if not result:
            bot.send_message(chat_id, "❌ لم يتم العثور على كلام.")
            return

        user_last_segments[chat_id] = (input_path, vad_mode, segments)

        with open(result, "rb") as audio_file:
            bot.send_audio(chat_id, audio_file)

        # أزرار للتحكم بالقص الإضافي
        markup = InlineKeyboardMarkup()
        for ms in [100, 150, 200, 250]:
            markup.add(InlineKeyboardButton(f"قص {ms}ms", callback_data=f"trim_{ms}"))
        bot.send_message(chat_id, "اختر مقدار القص الإضافي:", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ: {e}")

# ⏺️ تنفيذ عند الضغط على زر القص الإضافي
@bot.callback_query_handler(func=lambda call: call.data.startswith("trim_"))
def process_trim(call):
    global last_activity_time
    last_activity_time = time.time()
    extra_trim = int(call.data.split("_")[1])
    chat_id = call.message.chat.id

    try:
        bot.answer_callback_query(call.id, text=f"✂️ قص إضافي {extra_trim}ms")
        if chat_id not in user_last_segments:
            bot.send_message(chat_id, "❌ لا يوجد ملف لمعالجته.")
            return

        input_path, vad_mode, _ = user_last_segments[chat_id]
        result, _ = remove_silence_webrtc(input_path, vad_mode, extra_trim)

        if not result:
            bot.send_message(chat_id, "❌ لم يتم العثور على كلام.")
            return

        with open(result, "rb") as audio_file:
            bot.send_audio(chat_id, audio_file)

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
    msg = bot.reply_to(message, "📥 جاري تنزيل الصوت...")
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
