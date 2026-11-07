# Kokoro-82M text-to-speech on the Jetson CPU, in a container. No GPU runtime needed.
# Model files are NOT in the image: they live in /home/paulcho/models/kokoro (mounted at /models).
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir kokoro-onnx==0.6.1 soundfile
WORKDIR /app
COPY tts_server.py .
EXPOSE 8092
CMD ["python3", "tts_server.py", "--model", "/models/kokoro-v1.0.onnx", "--voices", "/models/voices-v1.0.bin", "--port", "8092"]
