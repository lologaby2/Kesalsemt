import os
import random
import telebot
import threading
import time
from openai import OpenAI
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

# التوكنات
BOT_TOKEN = "8193075108:AAHCUX0hSAKY7x44zxmDZ8AsD9bR_v4QGUk"
OPENAI_API_KEY = "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"

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

os.makedirs("outputs", exist_ok=True)

# مؤقت الإيقاف التلقائي
last_activity_time = time.time()

def auto_shutdown():
    while True:
        if time.time() - last_activity_time > 600:
            print("⏹️ تم إيقاف البوت تلقائيًا بعد 10 دقائق من عدم النشاط.")
            os._exit(0)
        time.sleep(30)

threading.Thread(target=auto_shutdown, daemon=True).start()

def random_filename():
    return str(random.randint(1, 999)) + ".mp3"

def remove_silence(audio_path):
    sound = AudioSegment.from_file(audio_path)
    nonsilent_ranges = detect_nonsilent(sound, min_silence_len=200, silence_thresh=sound.dBFS - 32)
    result = AudioSegment.empty()
    for start, end in nonsilent_ranges:
        result += sound[start:end]
    out_path = os.path.join("outputs", random_filename())
    result.export(out_path, format="mp3")
    return out_path

def video_to_clean_audio(video_path):
    audio_path = os.path.join("outputs", "temp.mp3")
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path, codec="libmp3lame")
    return remove_silence(audio_path)

def send_to_gpt(text):
    system_prompt = (
        "قم بترجمة النص للعربي بعدد كلمات اقل من النص الاصلي و حافظ على تدفق النص بسلاسة\n"
        "قم باستبدال اسماء الاشخاص ان وجدت ب(الرجل،المرأة،الفتاة،الطفل،الشاب......) و هكذا\n"
        "اريد ترتيب النص العربي بهذا الشكل على سبيل المثال:\n"
        "بعد ان ظنت أنه رجل سيء، قررت قتله، لكنها كانت مخطئة!\n"
        "داس الرجل عن طريق الخطأ على فخ، ووجد نفسه محاصرًا...\n"
        "(بدون أقواس)"
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

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
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")
    finally:
        bot.delete_message(message.chat.id, msg.message_id)

@bot.message_handler(content_types=["audio", "voice"])
def handle_audio(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ معالجة الصوت...")
    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_info = bot.get_file(file_id)
        audio_data = bot.download_file(file_info.file_path)
        audio_path = "outputs/input_audio.mp3"
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        out_path = remove_silence(audio_path)
        bot.send_audio(message.chat.id, open(out_path, "rb"))
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")
    finally:
        bot.delete_message(message.chat.id, msg.message_id)

@bot.message_handler(content_types=["text"])
def handle_text(message):
    global last_activity_time
    last_activity_time = time.time()
    try:
        result = send_to_gpt(message.text)
        bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ من GPT: {e}")

bot.polling()
