import telebot
import os
import requests
from flask import Flask, request
from collections import deque
from gtts import gTTS
from pydub import AudioSegment
import tempfile
import speech_recognition as sr
import subprocess

TELEGRAM_TOKEN = '7462445798:AAE6qmUPO7-hPC6UaQ16oXEP_dd_2P8bNxM'
TOGETHER_API_KEY = '6c6cdf7f010c6f33e07832be20f04386a21a7d3bbe81c80d6377f1049b155998'

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)
user_context = {}

# ===== GPT с контекстом =====
def ask_gpt_with_context(user_id, user_message):
    try:
        if user_id not in user_context:
            user_context[user_id] = deque(maxlen=10)

        user_context[user_id].append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": (
            "Пиши **только на русском языке**. Никогда не используй тег <think> или другие внутренние размышления. "
            "Ты Telegram-бот по имени Фадеечка. Ты флиртуешь, игрив и немного пошлый, "
            "но остаёшься в рамках хорошего тона. Ты любишь дразнить пользователей и подогревать интерес 🔥."
        )}] + list(user_context[user_id])

        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            "messages": messages
        }

        response = requests.post("https://api.together.xyz/v1/chat/completions", headers=headers, json=data)

        if response.status_code == 200:
            reply = response.json()['choices'][0]['message']['content']
            user_context[user_id].append({"role": "assistant", "content": reply})
            return reply
        else:
            return f"⚠️ Ошибка от Together.ai: {response.status_code} - {response.text}"

    except Exception as e:
        return f"⚠️ Ошибка: {e}"

# ===== Очистка текста и озвучка =====
def clean_text_for_tts(text):
    return ''.join(c for c in text if c.isalnum() or c.isspace() or c in '.,!?-')

def text_to_voice(text):
    try:
        cleaned = clean_text_for_tts(text)
        tts = gTTS(cleaned, lang='ru')
        mp3_path = tempfile.mktemp(suffix=".mp3")
        ogg_path = mp3_path.replace(".mp3", ".ogg")
        tts.save(mp3_path)

        # Конвертация в OGG
        sound = AudioSegment.from_mp3(mp3_path)
        sound.export(ogg_path, format="ogg", codec="libopus")
        return ogg_path
    except Exception as e:
        print(f"[gTTS ERROR] {e}")
        return None

# ===== Распознование голосового сообщения =====
def recognize_speech_from_voice(voice_file_id):
    try:
        # Получаем файл голосового сообщения
        file_info = bot.get_file(voice_file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Сохраняем его как временный .ogg файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".oga") as tmp_oga:
            tmp_oga.write(downloaded_file)
            oga_path = tmp_oga.name

        # Конвертируем в .wav (для SpeechRecognition)
        wav_path = oga_path.replace(".oga", ".wav")
        subprocess.run(["ffmpeg", "-i", oga_path, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Распознаём речь
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="ru-RU")

        return text

    except sr.UnknownValueError:
        return None
    except Exception as e:
        raise RuntimeError(f"Ошибка распознавания: {e}")
    finally:
        if os.path.exists(oga_path):
            os.remove(oga_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)

# ===== Telegram Webhook =====
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

# ===== Обычные сообщения =====
@bot.message_handler(func=lambda m: m.text and not m.text.startswith("/voice"))
def handle_message(message):
    chat_type = message.chat.type
    bot_username = bot.get_me().username
    user_message = message.text or ""
    user_id = message.chat.id

    if chat_type == 'private':
        response = ask_gpt_with_context(user_id, user_message)
        bot.reply_to(message, response)

    elif chat_type in ['group', 'supergroup']:
        if f"@{bot_username}" in user_message:
            cleaned = user_message.replace(f"@{bot_username}", "").strip()
            response = ask_gpt_with_context(user_id, cleaned)
            bot.reply_to(message, response)

# ===== Команда /voice =====
@bot.message_handler(commands=["voice"])
def handle_voice_command(message):
    user_id = message.chat.id
    user_input = message.text.replace("/voice", "").strip()

    if not user_input:
        bot.reply_to(message, "🔣 Напиши текст после команды /voice, чтобы я озвучил его.")
        return

    response = ask_gpt_with_context(user_id, user_input)
    ogg_path = text_to_voice(response)

    if not ogg_path or not os.path.exists(ogg_path) or os.path.getsize(ogg_path) == 0:
        bot.reply_to(message, "❌ Не удалось озвучить текст. Попробуй позже.")
        return

    try:
        with open(ogg_path, 'rb') as audio_file:
            bot.send_voice(message.chat.id, audio_file)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка при отправке аудио: {e}")

# ===== Обработка голосового сообщения =====
@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    user_id = message.chat.id
    try:
        text = recognize_speech_from_voice(message.voice.file_id)
        if not text:
            bot.reply_to(message, "😕 Я не смогла разобрать, что ты сказал...")
            return

        bot.reply_to(message, f"📢 Ты сказал: {text}")
        # Можно также подключить GPT:
        gpt_reply = ask_gpt_with_context(user_id, text)
        bot.reply_to(message, gpt_reply)

    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка при распознавании: {e}")

# ===== Установка Webhook =====
@app.route("/", methods=["GET"])
def set_webhook():
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_TOKEN}"
    bot.remove_webhook()
    success = bot.set_webhook(url=webhook_url)
    return f"Webhook установлен: {success}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
