FROM nvcr.io/nvidia/l4t-jetpack:r36.4.0

ARG WHISPER_TAG=v1.9.4
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake build-essential ca-certificates python3 curl \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${WHISPER_TAG}" \
    https://github.com/ggml-org/whisper.cpp.git /opt/whisper.cpp
WORKDIR /opt/whisper.cpp
# Orin sm_87, CUDA 12.6. Do not depend on build-time GPU discovery.
# NO_VMM avoids linking against a host driver absent during docker build.
RUN cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 \
    -DGGML_CUDA_NO_VMM=ON -DCMAKE_BUILD_TYPE=Release \
    -DWHISPER_BUILD_TESTS=OFF \
    && cmake --build build -j2 --target whisper-server whisper-cli
ENV PATH=/opt/whisper.cpp/build/bin:${PATH}
COPY protocol.py bridge.py /opt/voice/
WORKDIR /opt/voice
EXPOSE 8090
CMD ["python3", "bridge.py", "--host", "0.0.0.0", "--start-whisper", "--model", "/models/ggml-base.bin"]
