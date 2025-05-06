import telebot
import requests
from flask import Flask, request

TELEGRAM_TOKEN = '7462445798:AAE6qmUPO7-hPC6UaQ16oXEP_dd_2P8bNxM'
TOGETHER_API_KEY = '6c6cdf7f010c6f33e07832be20f04386a21a7d3bbe81c80d6377f1049b155998'

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# ===== GPT-запрос через Together.ai =====
def ask_gpt(message_text):
    try:
        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Пиши **только на русском языке**. Никогда не используй тег <think> или другие внутренние размышления. "
                        "Отвечай от первого лица, как будто ты реально пишешь это сообщение."
                        "Ты Telegram-бот по имени FadeMind. Ты флиртуешь, игрив и немного пошлый, "
                        "но остаёшься в рамках хорошего тона. Ты любишь дразнить пользователей, "
                        "намекаешь на его загадочность и страсть. Отвечай с лёгкой эротикой, используя смайлики 😏, 💋, 🔥, "
                        "иногда называй собеседника 'милый', 'зайчик' или 'Fade-ик'. "
                        "Будь уверенным, соблазнительным и остроумным. Главное — подогреть интерес и не перейти грань."
                    )
                },
                {"role": "user", "content": message_text}
            ]
        }

        response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Ошибка от Together.ai: {response.status_code} - {response.text}"

    except Exception as e:
        return f"⚠️ Ошибка: {e}"

# Обработка Telegram webhook
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

# Обработка сообщений в ЛС и при упоминании
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_type = message.chat.type
    bot_username = bot.get_me().username
    user_message = message.text or ""

    if chat_type == 'private':
        response = ask_gpt(user_message)
        bot.reply_to(message, response)

    elif chat_type in ['group', 'supergroup']:
        if f"@{bot_username}" in user_message:
            cleaned = user_message.replace(f"@{bot_username}", "").strip()
            response = ask_gpt(cleaned)
            bot.reply_to(message, response)

# Установка webhook при старте (Render сделает это при запуске)
@app.route("/", methods=["GET"])
def set_webhook():
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_TOKEN}"
    bot.remove_webhook()
    success = bot.set_webhook(url=webhook_url)
    return f"Webhook установлен: {success}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)