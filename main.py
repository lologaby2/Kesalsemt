import os
import random
import telebot
import threading
import time
from openai import OpenAI
from moviepy.editor import VideoFileClip
import torch
import torchaudio

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

def random_filename(extension="mp3"):
    return str(random.randint(1, 999)) + f".{extension}"

# دالة قراءة الصوت (بديلة لـ silero_vad)
def read_audio(path, sampling_rate=16000):
    wav, sr = torchaudio.load(path)
    if sr != sampling_rate:
        wav = torchaudio.functional.resample(wav, sr, sampling_rate)
    return wav[0]

# إزالة الصمت وتحويل إلى mp3 باستخدام نموذج Silero
def remove_silence_ai(audio_path):
    wav = read_audio(audio_path, sampling_rate=16000)
    model = torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)
    from silero.utils_vad import collect_chunks
    from silero.utils_vad import get_speech_timestamps
    speech = get_speech_timestamps(wav, model, sampling_rate=16000)
    if not speech:
        return audio_path
    from silero.utils_vad import collect_chunks
    clean = collect_chunks(wav, speech)
    wav_path = os.path.join("outputs", random_filename("wav"))
    mp3_path = wav_path.replace(".wav", ".mp3")
    torchaudio.save(wav_path, clean.unsqueeze(0), 16000)
    os.system(f"ffmpeg -y -i {wav_path} -codec:a libmp3lame -qscale:a 2 {mp3_path}")
    os.remove(wav_path)
    return mp3_path

# تحويل الفيديو إلى صوت ثم إزالة الصمت
def video_to_clean_audio(video_path):
    audio_path = os.path.join("outputs", "temp.wav")
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path, codec="pcm_s16le")
    return remove_silence_ai(audio_path)

# ترجمة النص
def send_to_gpt(text):
    system_prompt = (
        "قم بترجمة النص للعربي بعدد كلمات أقل من النص الاصلي و حافظ على تدفق النص بسلاسة\n"
        "قم باستبدال أسماء الأشخاص إن وجدت بـ (الرجل، المرأة، الفتاة، الطفل، الشاب...)\n"
        "رتّب الجمل على النمط التالي:\n"
        "بعد أن ظنت أنه رجل سيء، قررت قتله، لكنها كانت مخطئة!\n"
        "داس الرجل عن طريق الخطأ على فخ، ووجد نفسه محاصرًا..."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

# فيديو
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

# صوت
@bot.message_handler(content_types=["audio", "voice"])
def handle_audio(message):
    global last_activity_time
    last_activity_time = time.time()
    msg = bot.reply_to(message, "⏳ جارٍ معالجة الصوت...")
    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_info = bot.get_file(file_id)
        audio_data = bot.download_file(file_info.file_path)
        input_path = "outputs/input_audio.wav"
        with open(input_path, "wb") as f:
            f.write(audio_data)
        out_path = remove_silence_ai(input_path)
        bot.send_audio(message.chat.id, open(out_path, "rb"))
        os.remove(input_path)
        os.remove(out_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    finally:
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

# نص
@bot.message_handler(content_types=["text"])
def handle_text(message):
    global last_activity_time
    last_activity_time = time.time()
    try:
        result = send_to_gpt(message.text)
        bot.reply_to(message, result)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ من GPT: {e}")

bot.polling()
