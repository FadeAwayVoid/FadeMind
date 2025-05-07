# Используем официальный образ Python
FROM python:3.10-slim

# Установка ffmpeg и других зависимостей
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    pip install --upgrade pip

# Копируем проект в контейнер
WORKDIR /app
COPY . .

# Устанавливаем Python-зависимости
RUN pip install -r requirements.txt

# Устанавливаем порт для Render (5000 по умолчанию)
ENV PORT=5000

# Запуск приложения
CMD ["python", "main.py"]

RUN ffmpeg -version