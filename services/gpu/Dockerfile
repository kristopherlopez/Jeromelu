# Lineup GPU inference container for SageMaker Async (Phase 5.5).
#
# Multi-stage build:
#   1. `model-downloader` pulls all HF + InsightFace weights using a
#      build-time HF token passed via BuildKit `--secret`. This stage's
#      image layers are discarded; only the cache directories are
#      copied forward, so the token never lands in the final image.
#   2. The runtime stage starts from AWS DLC's pytorch-inference image
#      (CUDA 12.1 + torch 2.4 + the SageMaker Python inference toolkit
#      pre-installed) and grafts our extra pip deps + bake artefacts +
#      the project source on top.
#
# The base image already implements the SageMaker contract — `/ping` +
# `/invocations` on port 8080, `SAGEMAKER_PROGRAM` env var picks up our
# inference.py. We don't write a serving loop ourselves.
#
# Build with:
#   DOCKER_BUILDKIT=1 docker build \
#     --secret id=hf_token,env=HUGGINGFACE_API_KEY \
#     -t jeromelu-lineup-gpu:latest \
#     -f services/gpu/Dockerfile .

# ---------------------------------------------------------------------------
# Stage 1: download model weights
# ---------------------------------------------------------------------------
ARG SAGEMAKER_BASE=763104351884.dkr.ecr.ap-southeast-2.amazonaws.com/pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker-v1.80

FROM ${SAGEMAKER_BASE} AS model-downloader

# Bake-stage deps. pyannote 4.x hard-requires torch>=2.8, and PyTorch
# stopped shipping cu124 wheels at torch 2.6 — so we must move to cu126.
# That in turn means the SageMaker endpoint instance must be ml.g5.xlarge
# (driver supports cu126); g4dn.xlarge has driver 12.4 and would crash
# with "NVIDIA driver too old" at model load. See deploy.py:INSTANCE_TYPE.
RUN pip install --no-cache-dir --upgrade \
        --index-url https://download.pytorch.org/whl/cu126 \
        --extra-index-url https://pypi.org/simple \
        "torch>=2.8,<3" "torchaudio>=2.8,<3" "torchvision>=0.23"

# pyannote install picks up the torch we just installed (cu126 wheel) as
# satisfying its torch>=2.8 constraint. PyPI is the index again here so
# the rest of pyannote's deps resolve normally.
#
# Torchcodec is a transitive pyannote dep. We immediately uninstall it
# because its .so binaries depend on libpython3.12.so.1.0 (shared
# Python), but the AWS DLC base ships a static Python 3.12 install with
# no shared libpython. With torchcodec absent, pyannote falls back to
# torchaudio/soundfile for audio decoding (which we use anyway — the
# transcribe pipeline pre-converts to WAV via ffmpeg subprocess).
RUN pip install --no-cache-dir \
        "pyannote.audio>=4.0,<5" \
        "insightface>=0.7,<0.8" \
        "onnxruntime>=1.17,<2" \
    && pip uninstall -y torchcodec

COPY services/gpu/download_models.py /tmp/download_models.py

# BuildKit secret keeps the token out of the image layers. Mount path
# default is /run/secrets/<id>; we read it into HF_TOKEN at run time.
RUN --mount=type=secret,id=hf_token,required=true \
    HF_TOKEN="$(cat /run/secrets/hf_token)" \
    python /tmp/download_models.py


# ---------------------------------------------------------------------------
# Stage 2: runtime image
# ---------------------------------------------------------------------------
FROM ${SAGEMAKER_BASE}

# Mirror the bake stage's torch install — cu126 wheels from PyTorch's
# index, then the rest of the project deps from PyPI. Separate RUN
# layers keep the cu126 install cached when only project deps change.
RUN pip install --no-cache-dir --upgrade \
        --index-url https://download.pytorch.org/whl/cu126 \
        --extra-index-url https://pypi.org/simple \
        "torch>=2.8,<3" "torchaudio>=2.8,<3" "torchvision>=0.23"

# Project deps (mirrors services/api/requirements.txt for the GPU subset
# plus the SageMaker toolkit's own additions baked into the base image).
# Same torchcodec uninstall as the bake stage — see comment there.
COPY services/gpu/requirements.txt /tmp/lineup-requirements.txt
RUN pip install --no-cache-dir -r /tmp/lineup-requirements.txt \
    && pip uninstall -y torchcodec

# Prefer the pip-installed nvidia/* shared libs over the DLC's system
# CUDA stack. The DLC ships cuDNN 9.1.0 but our cu126 torch wheels were
# built against cuDNN 9.10.2; system libcudnn_graph.so.9 is missing the
# cudnnGetLibConfig symbol torch.cuda probes for, which kills model_fn.
#
# /etc/ld.so.conf.d/ entries do NOT override /lib/x86_64-linux-gnu —
# the GLIBC default path is searched first. LD_LIBRARY_PATH is the only
# precedence override that beats both. Hardcoded list of the 10 lib
# dirs the cu126 torch install actually populates; revisit if the
# torch wheels start shipping more or different nvidia/* subpackages.
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cusparse/lib:/usr/local/lib/python3.12/site-packages/nvidia/cuda_cupti/lib:/usr/local/lib/python3.12/site-packages/nvidia/cusolver/lib:/usr/local/lib/python3.12/site-packages/nvidia/cufile/lib:/usr/local/lib/python3.12/site-packages/nvidia/nccl/lib:/usr/local/lib/python3.12/site-packages/nvidia/nvshmem/lib:/usr/local/lib/python3.12/site-packages/nvidia/nvjitlink/lib:/usr/local/lib/python3.12/site-packages/nvidia/curand/lib

# Copy the baked model caches forward. HuggingFace caches under
# /root/.cache/huggingface — pyannote 4 routes everything through
# huggingface_hub 1.x, so the old /root/.cache/torch/pyannote/ path
# (used by pyannote 3.x) is no longer populated and doesn't get
# copied. InsightFace caches under /root/.insightface.
COPY --from=model-downloader /root/.cache/huggingface /root/.cache/huggingface
COPY --from=model-downloader /root/.insightface /root/.insightface

# FFmpeg 7 from BtbN's prebuilt shared-libs tarball. Ubuntu 22.04 ships
# FFmpeg 4 (libavutil.so.56) and torchcodec needs FFmpeg 6/7/8
# (libavutil.so.58/59/60). The savoury1 PPAs were tried first but
# cascade into a paywalled "private" PPA for some transitive deps;
# the BtbN tarball is a self-contained drop-in.
#
# libgl1 is still apt-installed for opencv/InsightFace's image loading.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl xz-utils libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o /tmp/ffmpeg.tar.xz \
        https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-lgpl-shared.tar.xz \
    && tar -xJf /tmp/ffmpeg.tar.xz -C /opt \
    && mv /opt/ffmpeg-* /opt/ffmpeg \
    && rm /tmp/ffmpeg.tar.xz \
    && ln -s /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg \
    && ln -s /opt/ffmpeg/bin/ffprobe /usr/local/bin/ffprobe \
    && echo /opt/ffmpeg/lib > /etc/ld.so.conf.d/ffmpeg.conf \
    && ldconfig

# Project source — the same Python modules the local CLI uses.
COPY packages/shared /opt/ml/code/packages/shared
COPY services/api/app /opt/ml/code/services/api/app
COPY services/gpu/inference.py /opt/ml/code/inference.py

# pip-install the in-tree shared package so jeromelu_shared imports work.
RUN pip install --no-cache-dir -e /opt/ml/code/packages/shared

# Tell the SageMaker base image where our handler lives. The base image
# imports inference.py from this directory and routes invocations to
# its model_fn / input_fn / predict_fn / output_fn callbacks.
ENV SAGEMAKER_PROGRAM=inference.py \
    SAGEMAKER_SUBMIT_DIRECTORY=/opt/ml/code \
    PYTHONPATH=/opt/ml/code:/opt/ml/code/services/api:/opt/ml/code/packages/shared \
    PYTHONUNBUFFERED=1

# The base image already ENTRYPOINTs to the SageMaker serving stack and
# EXPOSEs 8080 — don't override.
