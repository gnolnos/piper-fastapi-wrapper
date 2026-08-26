# Piper FastAPI Wrapper — "MIỆNG" (TTS bridge)
# Base glibc (python slim) — wyoming/fastapi are pure Python.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tts_http.py .

ENV PIPER_HOST=192.168.100.112 \
    PIPER_PORT=10200 \
    VOICE="" \
    API_HOST=0.0.0.0 \
    API_PORT=5002 \
    VOICE_LANGUAGES=""

EXPOSE 5002

CMD ["python", "tts_http.py"]
