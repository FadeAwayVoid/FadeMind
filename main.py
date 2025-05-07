import telebot
import os
import requests
from flask import Flask, request
from collections import deque

TELEGRAM_TOKEN = '7462445798:AAE6qmUPO7-hPC6UaQ16oXEP_dd_2P8bNxM'
TOGETHER_API_KEY = '6c6cdf7f010c6f33e07832be20f04386a21a7d3bbe81c80d6377f1049b155998'

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# Память пользователей: user_id -> deque из сообщений
user_context = {}

# ===== GPT-запрос с контекстом =====
def ask_gpt_with_context(user_id, user_message):
    try:
        # Инициализация истории пользователя, если нет
        if user_id not in user_context:
            user_context[user_id] = deque(maxlen=10)  # 5 пар "user+assistant"

        # Добавляем текущее сообщение
        user_context[user_id].append({"role": "user", "content": user_message})

        # Формируем запрос
        messages = [{"role": "system", "content": (
            "Пиши **только на русском языке**. Никогда не используй тег <think> или другие внутренние размышления. "
            "Отвечай от первого лица, как будто ты реально пишешь это сообщение. "
            "Ты Telegram-бот по имени FadeMind. Ты флиртуешь, игрив и немного пошлый, "
            "но остаёшься в рамках хорошего тона. Ты любишь дразнить пользователей, "
            "намекаешь на его загадочность и страсть. Отвечай с лёгкой эротикой, используя смайлики 😏, 💋, 🔥, "
            "иногда называй собеседника 'милый', 'зайчик'. "
            "Будь уверенным, соблазнительным и остроумным. Главное — подогреть интерес и не перейти грань."
        )}] + list(user_context[user_id])

        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            "messages": messages
        }

        response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            reply = response.json()['choices'][0]['message']['content']
            user_context[user_id].append({"role": "assistant", "content": reply})  # Сохраняем ответ
            return reply
        else:
            return f"⚠️ Ошибка от Together.ai: {response.status_code} - {response.text}"

    except Exception as e:
        return f"⚠️ Ошибка: {e}"

# Telegram webhook обработка
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

# Обработка входящих сообщений
@bot.message_handler(func=lambda message: True)
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

# Установка webhook
@app.route("/", methods=["GET"])
def set_webhook():
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_TOKEN}"
    bot.remove_webhook()
    success = bot.set_webhook(url=webhook_url)
    return f"Webhook установлен: {success}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)