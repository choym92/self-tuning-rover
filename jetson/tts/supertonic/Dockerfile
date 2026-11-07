# Supertonic 3 text-to-speech (31 languages incl. Korean) on the Jetson CPU. Model assets are
# downloaded separately into /home/paulcho/models/supertonic-3 (mounted at /models).
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir supertonic==1.3.1 "huggingface_hub>=0.25"
WORKDIR /app
COPY st_server.py .
EXPOSE 8093
CMD ["python3", "st_server.py", "--assets", "/models", "--port", "8093"]
