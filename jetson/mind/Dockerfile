# rover-mind: Kalman's listen-and-answer loop (stage 1). Python standard library only, plus ALSA tools.
FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends alsa-utils && rm -rf /var/lib/apt/lists/*
COPY mind.py persona.txt /app/
WORKDIR /app
ENTRYPOINT ["python3", "-u", "mind.py"]
