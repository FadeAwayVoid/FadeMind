import telebot
from flask import Flask, request
from openai import OpenAI
from telebot.types import InlineQueryResultArticle, InputTextMessageContent

TELEGRAM_TOKEN = '7462445798:AAE6qmUPO7-hPC6UaQ16oXEP_dd_2P8bNxM'
OPENROUTER_API_KEY = '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'

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"  # Важно! Меняем базовый адрес
)

app = Flask(__name__)

# Ответ от OpenRouter
def ask_gpt(message_text):
    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",  # можно заменить на любую другую модель OpenRouter
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты мужчина по имени Фаде. Ты флиртуешь, игрив и немного пошлый, "
                        "но остаёшься в рамках хорошего тона. Ты любишь дразнить пользователей, "
                        "намекаешь на его загадочность и страсть. Отвечай с лёгкой эротикой, используя смайлики 😏, 💋, 🔥, "
                        "иногда называй собеседника 'милый', 'зайчик' или 'Fade-ик'. "
                        "Будь уверенным, соблазнительным и остроумным. Главное — подогреть интерес и не перейти грань."
                    )
                },
                {"role": "user", "content": message_text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка от OpenRouter: {e}"

# Обработка сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_type = message.chat.type
    bot_username = bot.get_me().username
    user_message = message.text

    if chat_type == 'private':
        response = ask_gpt(user_message)
        bot.reply_to(message, response)

    elif chat_type in ['group', 'supergroup']:
        if f"@{bot_username}" in user_message:
            cleaned_message = user_message.replace(f"@{bot_username}", "").strip()
            response = ask_gpt(cleaned_message)
            bot.reply_to(message, response)

# Webhook-путь
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# Главная страница (для Render проверки)
@app.route("/", methods=['GET'])
def index():
    return "Бот работает", 200

# Установка webhook при старте
if __name__ == '__main__':
    import os
    host_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=host_url)
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))