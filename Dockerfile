FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir aiogram==3.4.1 yt-dlp flask anthropic

RUN mkdir -p /app/downloads /app/output

CMD ["python", "/app/bot.py"]
