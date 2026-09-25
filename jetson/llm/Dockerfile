# llama.cpp with CUDA for the Jetson Orin Nano (compute capability 8.7), built from source
# on NVIDIA's JetPack 6 base image so nothing is installed on the host.
#
# Build (on the Jetson, 30-60 min expected):
#   sudo docker build -t rover/llama_cpp:v0.5.0 --build-arg LLAMA_TAG=v0.5.0 .
# Run:
#   sudo docker run --runtime nvidia --rm -p 127.0.0.1:8080:8080 -v /home/paulcho/models:/models \
#     rover/llama_cpp:v0.5.0 llama-server -m /models/<file>.gguf -ngl 99 -c 4096 --host 0.0.0.0 --port 8080
# Remove:
#   sudo docker rmi rover/llama_cpp:v0.5.0 nvcr.io/nvidia/l4t-jetpack:r36.4.0

FROM nvcr.io/nvidia/l4t-jetpack:r36.4.0

ARG LLAMA_TAG=v0.5.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends git cmake build-essential ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 --branch "${LLAMA_TAG}" https://github.com/ggml-org/llama.cpp.git

WORKDIR /opt/llama.cpp
# -j4 rather than all 6 cores: nvcc is memory-hungry and the board has 8 GB shared with the desktop.
RUN cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build --config Release -j4 --target llama-server llama-bench llama-cli \
 && rm -rf build/CMakeFiles

ENV PATH=/opt/llama.cpp/build/bin:${PATH}
EXPOSE 8080
CMD ["llama-server", "--help"]
