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
ARG SAGEMAKER_BASE=763104351884.dkr.ecr.ap-southeast-2.amazonaws.com/pytorch-inference:2.4.0-gpu-py311

FROM ${SAGEMAKER_BASE} AS model-downloader

# Pin the same versions as services/api/requirements.txt — the runtime
# pyannote needs huggingface_hub<1.0 (use_auth_token kwarg) and
# speechbrain<1.1 (k2_fsa lazy-import). Install only what's needed for
# the downloader to run; the runtime stage installs the full set.
RUN pip install --no-cache-dir \
        "pyannote.audio>=3.1,<4" \
        "huggingface_hub<1.0" \
        "speechbrain<1.1" \
        "insightface>=0.7,<0.8" \
        "onnxruntime>=1.17,<2"

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

# Project deps (mirrors services/api/requirements.txt for the GPU subset
# plus the SageMaker toolkit's own additions baked into the base image).
COPY services/gpu/requirements.txt /tmp/lineup-requirements.txt
RUN pip install --no-cache-dir -r /tmp/lineup-requirements.txt

# Copy the baked model caches forward. HuggingFace caches under
# /root/.cache/huggingface; pyannote caches under /root/.cache/torch;
# InsightFace under /root/.insightface.
COPY --from=model-downloader /root/.cache/huggingface /root/.cache/huggingface
COPY --from=model-downloader /root/.cache/torch /root/.cache/torch
COPY --from=model-downloader /root/.insightface /root/.insightface

# ffmpeg for audio/video conversion (used by diarize.py and visual_id.py)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 \
    && rm -rf /var/lib/apt/lists/*

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
