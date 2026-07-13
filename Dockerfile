FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py replies.json ./

ENV AUDIO_DIR=/data/audio \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/audio
VOLUME /data

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "60", "app:app"]
