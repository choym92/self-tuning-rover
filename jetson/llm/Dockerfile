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
# The image carries the CUDA toolkit but not the GPU driver library (libcuda.so.1): on Jetson the
# nvidia container runtime bind-mounts the real driver only at run time, so a plain `docker build`
# cannot link against it (first attempt failed here on 2026-09-25). Two measures:
#   1. GGML_CUDA_NO_VMM=ON — drop the virtual-memory pool, the only ggml code that calls the driver API.
#   2. Point the linker at the toolkit's stub libcuda.so (link-time only; the real driver is used at run time).
# Libraries and executables are separate layers so a failed link does not repeat the 25-minute CUDA compile.
# -j4 rather than all 6 cores: nvcc is memory-hungry and the board has 8 GB shared with the desktop.
RUN ln -sf /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1 \
 && cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 -DGGML_CUDA_NO_VMM=ON \
      -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_EXE_LINKER_FLAGS="-L/usr/local/cuda/lib64/stubs -Wl,-rpath-link,/usr/local/cuda/lib64/stubs" \
      -DCMAKE_SHARED_LINKER_FLAGS="-L/usr/local/cuda/lib64/stubs -Wl,-rpath-link,/usr/local/cuda/lib64/stubs" \
 && cmake --build build --config Release -j4 --target ggml llama
RUN cmake --build build --config Release -j4 --target llama-server llama-bench llama-cli \
 && rm -rf build/CMakeFiles \
 && rm -f /usr/local/cuda/lib64/stubs/libcuda.so.1

ENV PATH=/opt/llama.cpp/build/bin:${PATH}
EXPOSE 8080
CMD ["llama-server", "--help"]
