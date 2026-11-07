# rover-mind: Kalman's listen-and-answer loop (stage 1). sherpa-onnx gives Silero VAD.
FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends alsa-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir sherpa-onnx==2.0.1 numpy==2.2.6
COPY mind.py persona.txt /app/
WORKDIR /app
ENTRYPOINT ["python3", "-u", "mind.py"]
