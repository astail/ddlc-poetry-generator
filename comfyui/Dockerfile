# ComfyUI (Stable Diffusion runtime) for GTX 1060 6GB.
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Pin ComfyUI to a specific release tag for reproducibility (was master HEAD,
# which could change under us / pull in unreviewed code). Bump deliberately.
ARG COMFYUI_VERSION=v0.26.0
WORKDIR /opt
RUN git clone --depth 1 --branch "${COMFYUI_VERSION}" \
    https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /opt/ComfyUI
RUN pip install -r requirements.txt

# Checkpoints come from the mounted /models (see docker-compose.yml).
RUN rm -rf models/checkpoints && ln -s /models/checkpoints models/checkpoints

EXPOSE 8188
# --lowvram keeps SD1.5 within the GTX 1060's 6GB.
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--lowvram"]
